"""Depo Robotu Simülatörü - Tkinter arayüzü.

Tüm kurallar simulasyon.py içindedir; bu dosya yalnızca gösterir ve
kullanıcı etkileşimini yönetir.

Çalıştırma:  python arayuz.py            (klasörü butondan seçin)
             python arayuz.py <klasör>   (klasörü doğrudan yükler)
"""
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import simulasyon as sim

HUCRE_RENGI = {
    sim.DUVAR: "#37474f",
    sim.BOS: "#eceff1",
    sim.KUTU: "#ffb74d",
    sim.TESLIM: "#81c784",
    sim.SARJ_ISTASYONU: "#64b5f6",
}
HUCRE_YAZISI = {sim.KUTU: "K", sim.TESLIM: "T", sim.SARJ_ISTASYONU: "S"}
YON_ADI = {"K": "Kuzey (yukarı)", "D": "Doğu (sağ)", "G": "Güney (aşağı)", "B": "Batı (sol)"}
OLAY_RENGI = {sim.CARPISMA: "#c62828", sim.GECERSIZ: "#ef6c00",
              sim.BATARYA_BITTI: "#b71c1c", sim.YOL_YOK: "#ef6c00",
              sim.TESLIM_OLAYI: "#2e7d32"}
ROBOT_RENGI = "#d32f2f"
MAKS_HUCRE = 44


class DepoArayuzu:
    def __init__(self, kok):
        self.kok = kok
        kok.title("Depo Robotu Simülatörü")
        kok.minsize(900, 560)

        # Yüklenen veriler
        self.klasor = None
        self.izgara = None
        self.baslangic = None
        self.ayarlar = None
        self.komutlar = []
        self.hatalar = []
        # Çalışma durumu
        self.durum = None
        self.sira = 0          # sıradaki komutun indeksi
        self.log = []
        self.bitti = False

        self._arayuzu_kur()
        self._butonlari_guncelle()

    # ----------------------------------------------------------- yerleşim

    def _arayuzu_kur(self):
        ust = ttk.Frame(self.kok, padding=8)
        ust.pack(fill="x")
        self.btn_yukle = ttk.Button(ust, text="Dosyaları Yükle", command=self.dosyalari_yukle)
        self.btn_adim = ttk.Button(ust, text="Adım", command=self.adim)
        self.btn_tumu = ttk.Button(ust, text="Tümünü Çalıştır", command=self.tumunu_calistir)
        self.btn_sifirla = ttk.Button(ust, text="Sıfırla", command=self.sifirla)
        for b in (self.btn_yukle, self.btn_adim, self.btn_tumu, self.btn_sifirla):
            b.pack(side="left", padx=(0, 6))
        self.lbl_klasor = ttk.Label(ust, text="Henüz dosya yüklenmedi.", foreground="#666")
        self.lbl_klasor.pack(side="left", padx=10)

        govde = ttk.Frame(self.kok, padding=(8, 0, 8, 8))
        govde.pack(fill="both", expand=True)

        # Sol: harita
        harita_cerceve = ttk.LabelFrame(govde, text="Harita", padding=6)
        harita_cerceve.pack(side="left", fill="both", expand=True)
        self.tuval = tk.Canvas(harita_cerceve, bg="white", highlightthickness=0)
        self.tuval.pack(fill="both", expand=True)
        self.tuval.bind("<Configure>", lambda e: self.ciz())
        self._lejant_kur(harita_cerceve)

        # Sağ: bilgi paneli + log + hatalı satırlar
        sag = ttk.Frame(govde, width=330)
        sag.pack(side="right", fill="y", padx=(8, 0))
        sag.pack_propagate(False)

        bilgi = ttk.LabelFrame(sag, text="Durum", padding=8)
        bilgi.pack(fill="x")
        self.bilgi_degerleri = {}
        satirlar = [("batarya", "Batarya"), ("yon", "Yön"), ("konum", "Konum"),
                    ("yuk", "Yük"), ("teslim", "Teslim"), ("carpisma", "Çarpışma"),
                    ("adim", "Toplam adım"), ("sonraki", "Sıradaki komut"),
                    ("son_olay", "Son olay")]
        for i, (anahtar, etiket) in enumerate(satirlar):
            ttk.Label(bilgi, text=etiket + ":").grid(row=i, column=0, sticky="w", pady=1)
            deger = ttk.Label(bilgi, text="-", font=("TkDefaultFont", 10, "bold"))
            deger.grid(row=i, column=1, sticky="w", padx=(8, 0))
            self.bilgi_degerleri[anahtar] = deger
        self.batarya_cubugu = ttk.Progressbar(bilgi, length=200, maximum=100)
        self.batarya_cubugu.grid(row=len(satirlar), column=0, columnspan=2,
                                 sticky="we", pady=(6, 0))

        log_cerceve = ttk.LabelFrame(sag, text="Komut günlüğü (log)", padding=4)
        log_cerceve.pack(fill="both", expand=True, pady=(8, 0))
        sutunlar = ("adim", "komut", "konum", "batarya", "olay")
        self.log_tablosu = ttk.Treeview(log_cerceve, columns=sutunlar, show="headings", height=8)
        for s, gen in zip(sutunlar, (36, 70, 60, 56, 90)):
            self.log_tablosu.heading(s, text=s)
            self.log_tablosu.column(s, width=gen, anchor="center")
        kaydirma = ttk.Scrollbar(log_cerceve, command=self.log_tablosu.yview)
        self.log_tablosu.configure(yscrollcommand=kaydirma.set)
        self.log_tablosu.pack(side="left", fill="both", expand=True)
        kaydirma.pack(side="right", fill="y")
        for olay, renk in OLAY_RENGI.items():
            self.log_tablosu.tag_configure(olay, foreground=renk)

        hata_cerceve = ttk.LabelFrame(sag, text="Hatalı satırlar (atlandı)", padding=4)
        hata_cerceve.pack(fill="x", pady=(8, 0))
        self.hata_listesi = tk.Listbox(hata_cerceve, height=5, fg="#c62828")
        self.hata_listesi.pack(fill="x")

    def _lejant_kur(self, ana):
        lejant = ttk.Frame(ana)
        lejant.pack(fill="x", pady=(6, 0))
        ogeler = [(HUCRE_RENGI[sim.DUVAR], "Duvar"), (HUCRE_RENGI[sim.KUTU], "Kutu"),
                  (HUCRE_RENGI[sim.TESLIM], "Teslim"), (HUCRE_RENGI[sim.SARJ_ISTASYONU], "Şarj"),
                  (ROBOT_RENGI, "Robot")]
        for renk, ad in ogeler:
            tk.Label(lejant, bg=renk, width=2).pack(side="left", padx=(0, 3))
            ttk.Label(lejant, text=ad).pack(side="left", padx=(0, 10))

    # ----------------------------------------------------------- dosyalar

    def dosyalari_yukle(self, klasor=None):
        """harita.txt, komutlar.txt ve ayarlar.json içeren klasörü yükler."""
        if klasor is None:
            klasor = filedialog.askdirectory(title="harita.txt, komutlar.txt ve ayarlar.json "
                                                   "içeren klasörü seçin")
            if not klasor:
                return
        try:
            izgara, baslangic = sim.harita_oku(os.path.join(klasor, "harita.txt"))
            ayarlar = sim.ayarlari_oku(os.path.join(klasor, "ayarlar.json"))
            komutlar, hatalar = sim.komutlari_oku(os.path.join(klasor, "komutlar.txt"))
        except FileNotFoundError as e:
            messagebox.showerror("Dosya bulunamadı", f"Dosya bulunamadı:\n{e.filename}")
            return
        except ValueError as e:
            messagebox.showerror("Bozuk dosya", str(e))
            return
        except OSError as e:
            messagebox.showerror("Okuma hatası", str(e))
            return

        self.klasor = klasor
        self.izgara, self.baslangic, self.ayarlar = izgara, baslangic, ayarlar
        self.komutlar, self.hatalar = komutlar, hatalar
        self.lbl_klasor.config(text=f"{os.path.basename(klasor)}  •  {len(komutlar)} komut, "
                                    f"{len(hatalar)} hatalı satır")
        self.hata_listesi.delete(0, "end")
        for h in hatalar:
            self.hata_listesi.insert("end", f"Satır {h['satir']}: {h['icerik']!r} - {h['neden']}")
        self.sifirla()
        if hatalar:
            messagebox.showwarning("Hatalı satırlar",
                                   f"{len(hatalar)} hatalı komut satırı atlandı. "
                                   "Ayrıntılar sağdaki listede.")

    def _ciktilari_yaz(self):
        if not self.klasor:
            return
        sonuc = sim.sonuc_olustur(self.durum, self.hatalar)
        try:
            sim.sonuc_yaz(sonuc, os.path.join(self.klasor, "sonuc.json"))
            sim.log_yaz(self.log, os.path.join(self.klasor, "log.csv"))
        except OSError as e:
            messagebox.showerror("Yazma hatası", f"Çıktılar yazılamadı:\n{e}")
            return
        mesaj = "sonuc.json ve log.csv yazıldı."
        if self.durum["batarya_bitti"]:
            mesaj = "Batarya bitti, simülasyon durdu.\n" + mesaj
        self.bilgi_degerleri["son_olay"].config(text="Bitti")
        messagebox.showinfo("Simülasyon tamamlandı", mesaj)

    # ----------------------------------------------------------- çalıştırma

    def sifirla(self):
        if self.izgara is None:
            return
        self.durum = sim.yeni_durum(self.izgara, self.baslangic, self.ayarlar)
        self.sira = 0
        self.log = []
        self.bitti = False
        self.log_tablosu.delete(*self.log_tablosu.get_children())
        self.bilgi_degerleri["son_olay"].config(text="-", foreground="black")
        self.guncelle()

    def adim(self):
        """Sıradaki tek komutu çalıştırır."""
        if self.durum is None or self.bitti:
            return
        komut = self.komutlar[self.sira]
        olay = sim.komut_uygula(self.durum, komut)
        satir = sim.log_satiri(self.sira + 1, komut, self.durum, olay)
        self.log.append(satir)
        self.log_tablosu.insert("", "end", tags=(olay,), values=(
            satir["adim"], satir["komut"], f"({satir['x']},{satir['y']})",
            satir["batarya"], olay))
        self.log_tablosu.yview_moveto(1)
        self.bilgi_degerleri["son_olay"].config(text=olay,
                                                 foreground=OLAY_RENGI.get(olay, "black"))
        self.sira += 1
        if self.durum["batarya_bitti"] or self.sira >= len(self.komutlar):
            self.bitti = True
        self.guncelle()
        if self.bitti:
            self._ciktilari_yaz()

    def tumunu_calistir(self):
        if self.durum is None:
            return
        while not self.bitti:
            self.adim()

    # ----------------------------------------------------------- çizim

    def guncelle(self):
        self.ciz()
        self._bilgiyi_guncelle()
        self._butonlari_guncelle()

    def _butonlari_guncelle(self):
        yuklu = self.durum is not None
        calisabilir = yuklu and not self.bitti and len(self.komutlar) > 0
        self.btn_adim.state(["!disabled"] if calisabilir else ["disabled"])
        self.btn_tumu.state(["!disabled"] if calisabilir else ["disabled"])
        self.btn_sifirla.state(["!disabled"] if yuklu else ["disabled"])
        if yuklu and not self.komutlar:
            self.bitti = True

    def _bilgiyi_guncelle(self):
        d = self.durum
        if d is None:
            return
        kapasite = d["ayarlar"]["batarya_kapasitesi"] or 1
        b = self.bilgi_degerleri
        b["batarya"].config(text=f"{d['batarya']} / {d['ayarlar']['batarya_kapasitesi']}",
                            foreground="#c62828" if d["batarya"] < kapasite * 0.2 else "black")
        self.batarya_cubugu["value"] = d["batarya"] / kapasite * 100
        b["yon"].config(text=YON_ADI[d["yon"]])
        b["konum"].config(text=f"({d['x']}, {d['y']})")
        b["yuk"].config(text="Kutu taşıyor" if d["yuk"] else "Boş")
        b["teslim"].config(text=str(d["teslim"]))
        b["carpisma"].config(text=str(d["carpisma"]))
        b["adim"].config(text=str(d["toplam_adim"]))
        if self.bitti or self.sira >= len(self.komutlar):
            sonraki = "— (bitti)"
        else:
            sonraki = f"{self.sira + 1}/{len(self.komutlar)}: " \
                      f"{sim.komut_metni(self.komutlar[self.sira])}"
        b["sonraki"].config(text=sonraki)

    def ciz(self):
        t = self.tuval
        t.delete("all")
        if self.durum is None:
            t.create_text(t.winfo_width() // 2, t.winfo_height() // 2, fill="#888",
                          text="Başlamak için 'Dosyaları Yükle' ile bir veri klasörü seçin.")
            return
        izgara = self.durum["izgara"]
        satir, sutun = len(izgara), len(izgara[0])
        h = max(8, min(MAKS_HUCRE, (t.winfo_width() - 10) // sutun,
                       (t.winfo_height() - 10) // satir))
        ox = (t.winfo_width() - h * sutun) // 2
        oy = (t.winfo_height() - h * satir) // 2
        ziyaret = self.durum["ziyaret"]
        en_fazla = max(ziyaret.values())

        for y in range(satir):
            for x in range(sutun):
                hucre = izgara[y][x]
                x0, y0 = ox + x * h, oy + y * h
                renk = HUCRE_RENGI[hucre]
                if hucre == sim.BOS and (x, y) in ziyaret:
                    renk = self._iz_rengi(ziyaret[(x, y)] / en_fazla)
                t.create_rectangle(x0, y0, x0 + h, y0 + h, fill=renk, outline="#cfd8dc")
                if hucre in HUCRE_YAZISI and h >= 14:
                    t.create_text(x0 + h / 2, y0 + h / 2, text=HUCRE_YAZISI[hucre],
                                  font=("TkDefaultFont", max(7, h // 3), "bold"), fill="#333")
        self._robotu_ciz(ox, oy, h)

    @staticmethod
    def _iz_rengi(oran):
        """Ziyaret yoğunluğuna göre açık sarı tonu (robotun izi)."""
        r, g, b = 0xec, 0xef, 0xf1
        hedef = (0xff, 0xf1, 0x76)
        k = 0.35 + 0.65 * oran
        return "#%02x%02x%02x" % tuple(int(a + (c - a) * k) for a, c in zip((r, g, b), hedef))

    def _robotu_ciz(self, ox, oy, h):
        d = self.durum
        cx, cy = ox + d["x"] * h + h / 2, oy + d["y"] * h + h / 2
        r = h * 0.38
        dx, dy = sim.YON_VEKTORU[d["yon"]]
        px, py = -dy, dx  # yön vektörüne dik
        uc = (cx + dx * r, cy + dy * r)
        sol = (cx - dx * r * 0.7 + px * r * 0.8, cy - dy * r * 0.7 + py * r * 0.8)
        sag = (cx - dx * r * 0.7 - px * r * 0.8, cy - dy * r * 0.7 - py * r * 0.8)
        self.tuval.create_polygon(*uc, *sol, *sag, fill=ROBOT_RENGI, outline="#7f0000")
        if d["yuk"]:  # taşınan kutu küçük kare olarak gösterilir
            k = h * 0.14
            self.tuval.create_rectangle(cx - k, cy - k, cx + k, cy + k,
                                        fill=HUCRE_RENGI[sim.KUTU], outline="#5d4037")


def main():
    kok = tk.Tk()
    uygulama = DepoArayuzu(kok)
    if len(sys.argv) > 1:
        kok.after(100, lambda: uygulama.dosyalari_yukle(sys.argv[1]))
    kok.mainloop()


if __name__ == "__main__":
    main()
