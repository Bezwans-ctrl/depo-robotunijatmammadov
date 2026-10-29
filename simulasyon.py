"""Depo Robotu Simulatoru - simulasyon mantigi.

Bu dosyada YALNIZCA kurallar ve dosya islemleri bulunyor . 

Koordinatlar (x, y) seklindedir: x sutun, y satirdr, sol ust kose (0, 0).
Izgara izgara[y][x] seklinde erisilen iki boyutlu bir karakter listesidir.
"""
import csv
import json
import os
import sys
from collections import deque

# ------------------------------------------------------------------ sabitler

DUVAR, BOS, ROBOT, KUTU, TESLIM, SARJ_ISTASYONU = "#", ".", "R", "K", "T", "S"
GECERLI_HUCRELER = {DUVAR, BOS, ROBOT, KUTU, TESLIM, SARJ_ISTASYONU}

# Yonler saat yonunde siralanir: K(yukari) -> D(sag) -> G(asagi) -> B(sol)
YONLER = ["K", "D", "G", "B"]
YON_VEKTORU = {"K": (0, -1), "D": (1, 0), "G": (0, 1), "B": (-1, 0)}

VARSAYILAN_AYARLAR = {
    "batarya_kapasitesi": 100,
    "baslangic_yonu": "D",
    "adim_maliyeti": 2,
    "yuk_carpani": 2,
    "donus_maliyeti": 1,
    "carpisma_cezasi": 5,
}

# Parametresiz komutlar ve parametre olarak tek pozitif tam sayi alan komut
PARAMETRESIZ = {"SAG", "SOL", "AL", "BIRAK", "SARJ"}

# Olay adlari (log.csv'deki "olay" sutunu)
HAREKET = "HAREKET"
CARPISMA = "CARPISMA"
DONUS = "DONUS"
AL = "AL"
TESLIM_OLAYI = "TESLIM"
BIRAKILDI = "BIRAKILDI"
SARJ_OLDU = "SARJ"
GECERSIZ = "GECERSIZ"
BATARYA_BITTI = "BATARYA_BITTI"
YOL_YOK = "YOL_YOK"


# ------------------------------------------------------------- dosya okuma

def harita_oku(dosya_yolu):
    """harita.txt dosyasini okur ve haritayi dondurur.
Robotun baslangic konumunu (x, y) olarak verir.
Haritada R yoksa, birden fazla R varsa, satir uzunluklari
farkliysa veya gecersiz karakter varsa hata verir.
    """
    with open(dosya_yolu, encoding="utf-8-sig") as f:
        satirlar = [s.rstrip("\r\n") for s in f.read().splitlines()]

    # Sondaki bos satilar haritaya dahil degil
    while satirlar and satirlar[-1].strip() == "":
        satirlar.pop()
    if not satirlar:
        raise ValueError("Harita boşdur.")

    genislik = len(satirlar[0])
    izgara = []
    robotlar = []
    for y, satir in enumerate(satirlar):
        if len(satir) != genislik:
            raise ValueError(f"Harita satir uzunluklari farkli (satir {y + 1}).")
        sira = []
        for x, hucre in enumerate(satir):
            if hucre not in GECERLI_HUCRELER:
                raise ValueError(f"Haritada gecersiz karakter '{hucre}' ({x}, {y}).")
            if hucre == ROBOT:
                robotlar.append((x, y))
                hucre = BOS  # robotun altindaki zemin bos hucredir
            sira.append(hucre)
        izgara.append(sira)

    if len(robotlar) == 0:
        raise ValueError("Haritada robot (R) yok.")
    if len(robotlar) > 1:
        raise ValueError(f"Haritada birden fazla robot (R) var: {len(robotlar)} adet.")
    return izgara, robotlar[0]


def ayarlari_oku(dosya_yolu):
    """ayarlar.json'u okur -> dict. Eksik anahtarlar varsayilanla dolduruluyor."""
    with open(dosya_yolu, encoding="utf-8-sig") as f:
        try:
            veri = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"ayarlar.json bozuk: {e}") from e
    if not isinstance(veri, dict):
        raise ValueError("ayarlar.json bir sozluk (nesne) olmali.")

    ayarlar = dict(VARSAYILAN_AYARLAR)
    ayarlar.update(veri)
    if ayarlar["baslangic_yonu"] not in YONLER:
        raise ValueError(f"Yanlis baslangic yonu: {ayarlar['baslangic_yonu']}")
    for anahtar in ("batarya_kapasitesi", "adim_maliyeti", "yuk_carpani",
                    "donus_maliyeti", "carpisma_cezasi"):
        deger = ayarlar[anahtar]
        if isinstance(deger, bool) or not isinstance(deger, (int, float)) or deger < 0:
            raise ValueError(f"Gecersiz ayar: {anahtar} = {deger!r}")
    return ayarlar


def _dogal_sayi_mi(metin):
    """Metin 0 veya pozitif tam sayiysa True ('2.5', '-1', '+3' gibi degerler degil)."""
    return metin.isascii() and metin.isdigit()


def komut_satirini_ayristir(satir):
    """sadece tek bir satiri cozer -> (komut, None) veya (None, hata_nedeni)."""
    parcalar = satir.split()
    ad, argumanlar = parcalar[0], parcalar[1:]

    if ad == "ILERI":
        if len(argumanlar) == 0:
            return None, "ILERIYE gitmek icin adim sayisi eksik"
        if len(argumanlar) > 1:
            return None, "ILERI icin daha fazla parametre"
        if not _dogal_sayi_mi(argumanlar[0]):
            return None, f"gecersiz adim sayisi: {argumanlar[0]}"
        n = int(argumanlar[0])
        if n <= 0:
            return None, "adim sayisi pozitif olmalidir"
        return ("ILERI", n), None

    if ad in PARAMETRESIZ:
        if argumanlar:
            return None, f"{ad} parametre almaz"
        return (ad, None), None

    if ad == "GIT":  # bonus: GIT x y
        if len(argumanlar) != 2:
            return None, "GIT icin iki koordinat (x y) gerekli"
        if not all(_dogal_sayi_mi(a) for a in argumanlar):
            return None, "GIT koordinatlari negatif olmayan tam sayi olmali"
        return ("GIT", (int(argumanlar[0]), int(argumanlar[1]))), None

    return None, f"bilinmeyen komut: {ad}"


def komutlari_oku(dosya_yolu):
    """komutlar.txt'yi okur -> (komutlar, hatalar).

    komutlar: [("ILERI", 3), ("SAG", None), ...]
    hatalar : [{"satir": 4, "icerik": "ILER 3", "neden": "..."}, ...]
    Bos satirlar atlanir ama satir numarasina dahildir.
    """
    with open(dosya_yolu, encoding="utf-8-sig") as f:
        satirlar = f.read().splitlines()

    komutlar, hatalar = [], []
    for no, ham in enumerate(satirlar, start=1):
        satir = ham.strip()
        if satir == "":
            continue
        komut, neden = komut_satirini_ayristir(satir)
        if komut is None:
            hatalar.append({"satir": no, "icerik": ham, "neden": neden})
        else:
            komutlar.append(komut)
    return komutlar, hatalar


# ------------------------------------------------------------- simulasyon

def yeni_durum(izgara, baslangic, ayarlar):
    """Simulasyonun baslangic durumunu (sozluk) olusturur."""
    x, y = baslangic
    return {
        "izgara": [list(sira) for sira in izgara],  
        "x": x,
        "y": y,
        "yon": ayarlar["baslangic_yonu"],
        "batarya": ayarlar["batarya_kapasitesi"],
        "ayarlar": dict(ayarlar),
        "yuk": False,
        "teslim": 0,
        "carpisma": 0,
        "toplam_adim": 0,
        "batarya_bitti": False,
        "ziyaret": {(x, y): 1},  # baslangictaki  hucre 1 kez ziyaret edilmis sayilir
    }


def komut_metni(komut):
    """("ILERI", 3) -> "ILERI 3"."""
    ad, arg = komut
    if arg is None:
        return ad
    if isinstance(arg, tuple):
        return f"{ad} {arg[0]} {arg[1]}"
    return f"{ad} {arg}"


def _harita_icinde(izgara, x, y):
    return 0 <= y < len(izgara) and 0 <= x < len(izgara[0])


def _gecilebilir(izgara, x, y):
    return _harita_icinde(izgara, x, y) and izgara[y][x] != DUVAR


def _harca(durum, maliyet):
    """Bataryadan maliyet duser. Yetmezse simulasyonu durdurur ve False doner.

    Kural 3: maliyet > batarya ise islem yapilmaz; esitse yapilir, batarya 0 olur.
    """
    if maliyet > durum["batarya"]:
        durum["batarya_bitti"] = True
        return False
    durum["batarya"] -= maliyet
    return True


def _don(durum, sag_mi):
    """90 derece  doner. Batarya yetmezse False olur ."""
    if not _harca(durum, durum["ayarlar"]["donus_maliyeti"]):
        return False
    i = YONLER.index(durum["yon"])
    durum["yon"] = YONLER[(i + (1 if sag_mi else -1)) % 4]
    return True


def _bir_adim(durum):
    """Robotu baktigi yere bir hucre ilerletir.

    Doner: HAREKET, CARPISMA veya BATARYA_BITTI.
    """
    ayar = durum["ayarlar"]
    dx, dy = YON_VEKTORU[durum["yon"]]
    nx, ny = durum["x"] + dx, durum["y"] + dy

    if not _gecilebilir(durum["izgara"], nx, ny):
        durum["carpisma"] += 1
        ceza = ayar["carpisma_cezasi"]
        if ceza > durum["batarya"]:  # ceza bataryayi eksiye dusurucek
            durum["batarya"] = 0
            durum["batarya_bitti"] = True
            return BATARYA_BITTI
        durum["batarya"] -= ceza
        return CARPISMA

    maliyet = ayar["adim_maliyeti"] * (ayar["yuk_carpani"] if durum["yuk"] else 1)
    if not _harca(durum, maliyet):
        return BATARYA_BITTI

    durum["x"], durum["y"] = nx, ny
    durum["toplam_adim"] += 1
    durum["ziyaret"][(nx, ny)] = durum["ziyaret"].get((nx, ny), 0) + 1
    return HAREKET


def _ileri(durum, n):
    """ILERI n: adim adim  ilerler, carpisma olursa  komutun kalani iptal olur."""
    for _ in range(n):
        olay = _bir_adim(durum)
        if olay != HAREKET:
            return olay
    return HAREKET


def en_kisa_yol(izgara, baslangic, hedef):
    """BFS kullanarak duvarlara carpmadan en kisa yolu bulur. Baslangic hucre haric yol listesini dondurur, yol yoksa None dondurur"""
    if not _gecilebilir(izgara, *hedef):
        return None
    onceki = {baslangic: None}
    kuyruk = deque([baslangic])
    while kuyruk:
        hucre = kuyruk.popleft()
        if hucre == hedef:
            yol = []
            while hucre != baslangic:
                yol.append(hucre)
                hucre = onceki[hucre]
            return yol[::-1]
        for yon in YONLER:
            dx, dy = YON_VEKTORU[yon]
            komsu = (hucre[0] + dx, hucre[1] + dy)
            if komsu not in onceki and _gecilebilir(izgara, *komsu):
                onceki[komsu] = hucre
                kuyruk.append(komsu)
    return None


def _git(durum, hedef):
    """Bonus GIT x y: en kisa yolu bulur, gerekli donusleri ve adimlari uygular."""
    yol = en_kisa_yol(durum["izgara"], (durum["x"], durum["y"]), hedef)
    if yol is None:
        return YOL_YOK
    for nx, ny in yol:
        istenen = next(y for y, (dx, dy) in YON_VEKTORU.items()
                       if (durum["x"] + dx, durum["y"] + dy) == (nx, ny))
        fark = (YONLER.index(istenen) - YONLER.index(durum["yon"])) % 4
        # fark 1: bir kez sağ, 3: bir kez sol, 2: iki kez sağ
        donusler = {0: [], 1: [True], 2: [True, True], 3: [False]}[fark]
        for sag_mi in donusler:
            if not _don(durum, sag_mi):
                return BATARYA_BITTI
        olay = _bir_adim(durum)
        if olay != HAREKET:
            return olay
    return HAREKET


def komut_uygula(durum, komut):
    """Tek bir komutu durum uzerinde uygular -> olay (str)."""
    if durum["batarya_bitti"]:
        return BATARYA_BITTI

    ad, arg = komut
    izgara = durum["izgara"]
    hucre = izgara[durum["y"]][durum["x"]]

    if ad == "ILERI":
        return _ileri(durum, arg)

    if ad in ("SAG", "SOL"):
        return DONUS if _don(durum, ad == "SAG") else BATARYA_BITTI

    if ad == "AL":
        if hucre == KUTU and not durum["yuk"]:
            durum["yuk"] = True
            izgara[durum["y"]][durum["x"]] = BOS
            return AL
        return GECERSIZ

    if ad == "BIRAK":
        if not durum["yuk"]:
            return GECERSIZ
        if hucre == TESLIM:
            durum["yuk"] = False
            durum["teslim"] += 1
            return TESLIM_OLAYI
        if hucre == BOS:
            durum["yuk"] = False
            izgara[durum["y"]][durum["x"]] = KUTU
            return BIRAKILDI
        return GECERSIZ

    if ad == "SARJ":
        if hucre == SARJ_ISTASYONU:
            durum["batarya"] = durum["ayarlar"]["batarya_kapasitesi"]
            return SARJ_OLDU
        return GECERSIZ

    if ad == "GIT":
        return _git(durum, arg)

    return GECERSIZ


def en_cok_ziyaret(durum):
    """En cok ziyaret edilen hucre; esitlikte once kucuk y, sonra kucuk x."""
    (x, y), sayi = min(durum["ziyaret"].items(),
                       key=lambda kv: (-kv[1], kv[0][1], kv[0][0]))
    return [x, y], sayi


def sonuc_olustur(durum, hatalar=None):
    """Durumdan sonuc.json'a yazilacak sozlugu uretir ."""
    hucre, sayi = en_cok_ziyaret(durum)
    return {
        "konum": [durum["x"], durum["y"]],
        "yon": durum["yon"],
        "batarya": durum["batarya"],
        "yuk": durum["yuk"],
        "teslim": durum["teslim"],
        "carpisma": durum["carpisma"],
        "toplam_adim": durum["toplam_adim"],
        "batarya_bitti": durum["batarya_bitti"],
        "en_cok_ziyaret": hucre,
        "en_cok_ziyaret_sayisi": sayi,
        "hatali_satirlar": list(hatalar or []),
    }


def log_satiri(adim, komut, durum, olay):
    return {
        "adim": adim,
        "komut": komut_metni(komut),
        "x": durum["x"],
        "y": durum["y"],
        "yon": durum["yon"],
        "batarya": durum["batarya"],
        "olay": olay,
    }


def simulasyonu_calistir(izgara, baslangic, komutlar, ayarlar, hatalar=None):
    """Tum komutlari sirasiyla calistirir  -> (sonuc, log).

    Batarya bittiginde simulasyon  durur, sonraki komutlar calistirilmaz.
    """
    durum = yeni_durum(izgara, baslangic, ayarlar)
    log = []
    for i, komut in enumerate(komutlar, start=1):
        olay = komut_uygula(durum, komut)
        log.append(log_satiri(i, komut, durum, olay))
        if durum["batarya_bitti"]:
            break
    return sonuc_olustur(durum, hatalar), log


# ------------------------------------------------------------- ciktilar

def sonuc_yaz(sonuc, dosya_yolu):
    with open(dosya_yolu, "w", encoding="utf-8") as f:
        json.dump(sonuc, f, ensure_ascii=False, indent=2)


LOG_SUTUNLARI = ["adim", "komut", "x", "y", "yon", "batarya", "olay"]


def log_yaz(log, dosya_yolu):
    with open(dosya_yolu, "w", encoding="utf-8", newline="") as f:
        yazici = csv.DictWriter(f, fieldnames=LOG_SUTUNLARI)
        yazici.writeheader()
        yazici.writerows(log)


def harita_metni(durum):
    """Haritayi robotla birlikte metin olarak doner (robot 'R' ile gosterilir)."""
    satirlar = []
    for y, sira in enumerate(durum["izgara"]):
        satir = list(sira)
        if y == durum["y"]:
            satir[durum["x"]] = ROBOT
        satirlar.append("".join(satir))
    return "\n".join(satirlar)


# ------------------------------------------------------------- komut satiri

def klasoru_calistir(klasor):
    """Bir klasordeki harita/komut/ayar dosyalarini calistirir , ciktilari oraya yazar."""
    izgara, baslangic = harita_oku(os.path.join(klasor, "harita.txt"))
    ayarlar = ayarlari_oku(os.path.join(klasor, "ayarlar.json"))
    komutlar, hatalar = komutlari_oku(os.path.join(klasor, "komutlar.txt"))
    sonuc, log = simulasyonu_calistir(izgara, baslangic, komutlar, ayarlar, hatalar)
    sonuc_yaz(sonuc, os.path.join(klasor, "sonuc.json"))
    log_yaz(log, os.path.join(klasor, "log.csv"))
    return sonuc


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Kullanimm: python simulasyon.py <veri klasoru>")
        sys.exit(2)
    try:
        s = klasoru_calistir(sys.argv[1])
    except (OSError, ValueError) as e:
        print("Hata:", e)
        sys.exit(1)
    print(json.dumps(s, ensure_ascii=False, indent=2))
