"""Depo Robotu - Test Çalıştırıcı

Kullanım (proje klasörünüzde, simulasyon.py ile aynı yerde):

    python test_calistir.py paket_ornek          (klasör)
    python test_calistir.py paket_A.zip          (zip dosyası)
    python test_calistir.py paket_A.txt          (tek metin dosyası)

Her test için simulasyon.py içindeki şu fonksiyonlar çağrılır:
    harita_oku, ayarlari_oku, komutlari_oku, simulasyonu_calistir
ve sonuç, testin beklenen.json dosyasıyla karşılaştırılır.

Bu dosyayı DEĞİŞTİRMEYİN. Demoda size verilen paket, bu betiğin
kendi kopyasıyla çalıştırılır.
"""
import importlib.util
import io
import json
import os
import re
import sys
import tempfile
import threading
import zipfile

TOPLAM_PUAN = 35
ZAMAN_ASIMI = 5  # saniye / test
EKRAN = sys.stdout  # öğrenci kodunun print'leri yutulur, sonuçlar buraya yazılır


def yaz(metin=""):
    EKRAN.write(metin + "\n")
    EKRAN.flush()


# ------------------------------------------------------------ paket okuma

def _klasorden_yukle(kok):
    testler = []
    for dizin, _, dosyalar in sorted(os.walk(kok)):
        if "beklenen.json" not in dosyalar:
            continue
        def oku(ad):
            yol = os.path.join(dizin, ad)
            if not os.path.exists(yol):
                return ""
            with open(yol, encoding="utf-8") as f:
                return f.read()
        testler.append({
            "ad": os.path.basename(dizin),
            "aciklama": oku("aciklama.txt").strip(),
            "harita": oku("harita.txt"),
            "komutlar": oku("komutlar.txt"),
            "ayarlar": oku("ayarlar.json"),
            "beklenen": json.loads(oku("beklenen.json")),
        })
    testler.sort(key=lambda t: t["ad"])
    return testler


def _metinden_yukle(metin):
    testler, test, bolum = [], None, None
    baslik = re.compile(r"^=== (\S+)(?: \| (.*?))? ===$")
    for satir in metin.splitlines():
        m = baslik.match(satir.rstrip())
        if m:
            test = {"ad": m.group(1), "aciklama": (m.group(2) or "").strip(),
                    "harita": [], "komutlar": [], "ayarlar": [], "beklenen": []}
            testler.append(test)
            bolum = None
        elif test is not None and satir.rstrip() in ("--- harita", "--- komutlar", "--- ayarlar", "--- beklenen"):
            bolum = satir.rstrip()[4:]
        elif test is not None and bolum:
            test[bolum].append(satir)
    for t in testler:
        for b in ("harita", "komutlar", "ayarlar", "beklenen"):
            satirlar = t[b]
            while satirlar and not satirlar[-1].strip():
                satirlar.pop()
            t[b] = "\n".join(satirlar) + ("\n" if satirlar else "")
        t["beklenen"] = json.loads(t["beklenen"])
    return testler


def testleri_yukle(yol):
    if os.path.isdir(yol):
        return _klasorden_yukle(yol)
    if yol.lower().endswith(".zip"):
        hedef = tempfile.mkdtemp(prefix="paket_")
        with zipfile.ZipFile(yol) as z:
            z.extractall(hedef)
        return _klasorden_yukle(hedef)
    if yol.lower().endswith(".txt"):
        with open(yol, encoding="utf-8") as f:
            return _metinden_yukle(f.read())
    raise ValueError("Paket bir klasör, .zip veya .txt olmalı: " + yol)


# ------------------------------------------------------------ karşılaştırma

def karsilastir(beklenen, bulunan):
    farklar = []
    for anahtar, b in beklenen.items():
        if anahtar not in bulunan:
            farklar.append(f"'{anahtar}' alanı sonuçta yok")
            continue
        v = bulunan[anahtar]
        if v != b or isinstance(v, bool) != isinstance(b, bool):
            farklar.append(f"{anahtar}: beklenen {json.dumps(b)}, bulunan {json.dumps(v, default=str)}")
    return farklar


def _testi_calistir(sim, test):
    """Fark listesi döner; boş liste = GEÇTİ."""
    klasor = tempfile.mkdtemp(prefix="test_")
    yollar = {}
    for ad, dosya in (("harita", "harita.txt"), ("komutlar", "komutlar.txt"), ("ayarlar", "ayarlar.json")):
        yollar[ad] = os.path.join(klasor, dosya)
        with open(yollar[ad], "w", encoding="utf-8") as f:
            f.write(test[ad])

    beklenen = dict(test["beklenen"])
    if "hata" in beklenen:
        try:
            sim.harita_oku(yollar["harita"])
        except Exception as e:
            if type(e).__name__ == beklenen["hata"]:
                return []
            return [f"beklenen hata {beklenen['hata']}, gelen {type(e).__name__}"]
        return [f"harita_oku {beklenen['hata']} fırlatmalıydı, fırlatmadı"]

    izgara, baslangic = sim.harita_oku(yollar["harita"])
    ayarlar = sim.ayarlari_oku(yollar["ayarlar"])
    komutlar, hatalar = sim.komutlari_oku(yollar["komutlar"])
    sonuc, _log = sim.simulasyonu_calistir(izgara, baslangic, komutlar, ayarlar)
    sonuc = json.loads(json.dumps(sonuc, default=list))

    farklar = []
    if "hatali_satir_nolari" in beklenen:
        beklenen_nolar = beklenen.pop("hatali_satir_nolari")
        try:
            nolar = sorted(h["satir"] for h in hatalar)
        except (TypeError, KeyError):
            nolar = None
        if nolar != beklenen_nolar:
            farklar.append(f"hatalı satırlar: beklenen {beklenen_nolar}, bulunan {nolar}")
    return farklar + karsilastir(beklenen, sonuc)


def _zaman_sinirli(sim, test):
    kutu = {}

    def is_parcacigi():
        try:
            kutu["farklar"] = _testi_calistir(sim, test)
        except Exception as e:
            kutu["farklar"] = [f"program hata verdi: {type(e).__name__}: {e}"]

    t = threading.Thread(target=is_parcacigi, daemon=True)
    t.start()
    t.join(ZAMAN_ASIMI)
    if t.is_alive():
        return [f"zaman aşımı ({ZAMAN_ASIMI} sn) - sonsuz döngü olabilir"]
    return kutu["farklar"]


# ------------------------------------------------------------ ana akış

def ogrenci_modulunu_yukle(klasor):
    yol = os.path.join(klasor, "simulasyon.py")
    if not os.path.exists(yol):
        raise FileNotFoundError(f"simulasyon.py bulunamadı: {klasor}")
    with open(yol, encoding="utf-8") as f:
        kaynak = f.read()
    if re.search(r"^\s*(import|from)\s+tkinter", kaynak, re.MULTILINE):
        return None
    sys.path.insert(0, klasor)
    spec = importlib.util.spec_from_file_location("simulasyon", yol)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def main(argv):
    try:
        EKRAN.reconfigure(errors="replace")
    except AttributeError:
        pass
    sys.stdout = io.StringIO()  # öğrenci kodunun ekran çıktısını gizle
    if len(argv) != 2:
        yaz("Kullanım: python test_calistir.py <paket klasörü | paket.zip | paket.txt>")
        return 2

    paket = argv[1]
    try:
        testler = testleri_yukle(paket)
    except (OSError, ValueError) as e:
        yaz("Paket okunamadı:", e)
        return 2
    if not testler:
        yaz("Pakette test bulunamadı:", paket)
        return 2

    try:
        sim = ogrenci_modulunu_yukle(os.getcwd())
    except Exception as e:
        yaz(f"simulasyon.py yüklenemedi: {type(e).__name__}: {e}")
        yaz(f"SONUÇ: 0/{len(testler)}  ->  0.00 / {TOPLAM_PUAN} puan")
        return 1
    if sim is None:
        yaz("KURAL İHLALİ: simulasyon.py içinde tkinter kullanılmış.")
        yaz("Mantık ve arayüz ayrı dosyalarda olmalı. Test puanı verilmez.")
        yaz(f"SONUÇ: 0/{len(testler)}  ->  0.00 / {TOPLAM_PUAN} puan")
        return 1

    yaz(f"Paket: {os.path.basename(os.path.normpath(paket))}   ({len(testler)} test)\n")
    gecen = 0
    for test in testler:
        farklar = _zaman_sinirli(sim, test)
        etiket = f"{test['ad']} {test['aciklama']}"[:44]
        if farklar:
            yaz(f"{etiket:.<46} KALDI")
            for fark in farklar:
                yaz(f"      - {fark}")
        else:
            gecen += 1
            yaz(f"{etiket:.<46} GEÇTİ")

    puan = gecen / len(testler) * TOPLAM_PUAN
    yaz(f"\nSONUÇ: {gecen}/{len(testler)}  ->  {puan:.2f} / {TOPLAM_PUAN} puan")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
