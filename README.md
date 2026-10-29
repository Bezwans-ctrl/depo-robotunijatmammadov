# Depo Robotu Simülatörü

YZM217/BLM217 Programlama Lab-I — Proje 1. Python 3 (yalnızca standart kütüphane) + Tkinter.

## Dosyalar

| Dosya | İçerik |
|---|---|
| `simulasyon.py` | Tüm kurallar, dosya okuma/yazma (tkinter **yok**) |
| `arayuz.py` | Tkinter arayüzü |
| `test_calistir.py` | Hocanın verdiği test betiği (değiştirilmedi) |
| `paket_ornek/` | 6 örnek test |
| `deneme_verileri/` | 5 deneme veri seti |

## Çalıştırma

```bash
python test_calistir.py paket_ornek        # örnek testler (6/6)
python arayuz.py                           # arayüz; "Dosyaları Yükle" ile klasör seçin
python arayuz.py deneme_verileri/veri_1    # klasörü doğrudan yükler
python simulasyon.py deneme_verileri/veri_1  # arayüzsüz; sonuc.json ve log.csv üretir
```

Arayüzde simülasyon bittiğinde (son komut ya da batarya bitmesi) `sonuc.json` ve `log.csv`
yüklenen klasöre yazılır.

## Tasarım kararları

* **Koordinat:** `izgara[y][x]`; sol üst (0, 0). Robotun başlangıç hücresi ızgarada `.` olarak
  tutulur, robotun yeri durumda (`x`, `y`) saklanır.
* **Yönler** saat yönünde `["K", "D", "G", "B"]` listesinde; SAG indeksi +1, SOL −1 (mod 4).
* **ILERI n** adım adım işlenir. Önce önündeki hücre kontrol edilir (duvar/harita dışı →
  çarpışma, komutun kalanı iptal), sonra adım maliyeti (yükteyse × `yuk_carpani`) düşülür.
* **Batarya:** maliyet > batarya → işlem yapılmaz, simülasyon durur (`batarya_bitti = true`).
  Eşitse işlem yapılır, batarya 0 olur. Çarpışma cezası bataryayı eksiye düşürecekse batarya
  0 olur ve simülasyon durur.
* **Hatalı satırlar:** komut adları büyük/küçük harf duyarlıdır (`sol` hatalıdır). `ILERI` için
  tek bir pozitif tam sayı gerekir (`ILERI 0`, `ILERI -1`, `ILERI 2.5`, `ILERI` hatalı).
  Diğer komutlar parametre almaz (`AL 1`, `SAG 3` hatalı). Boş satırlar hata sayılmaz ama
  satır numarasına dahildir.
* **Ziyaret:** başlangıç hücresi 1; en çok ziyarette eşitlik → önce küçük y, sonra küçük x.
* **Olaylar (log.csv):** `HAREKET`, `CARPISMA`, `DONUS`, `AL`, `TESLIM`, `BIRAKILDI`, `SARJ`,
  `GECERSIZ`, `BATARYA_BITTI`, `YOL_YOK`.
* **Bonus — GIT x y:** BFS ile duvarlardan kaçınan en kısa yol bulunur; robot her adımda gerekli
  yöne döner (dönüş maliyetiyle) ve normal adım kurallarıyla ilerler. Hedef duvar, harita dışı
  ya da ulaşılamazsa olay `YOL_YOK`.

## sonuc.json alanları

`konum [x, y]`, `yon`, `batarya`, `yuk`, `teslim`, `carpisma`, `toplam_adim`, `batarya_bitti`,
`en_cok_ziyaret [x, y]`, `en_cok_ziyaret_sayisi`, `hatali_satirlar`.
