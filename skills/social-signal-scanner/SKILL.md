# Social Signal Scanner

Mengukur kualitas sinyal sosial di sekitar sebuah proyek. Hasilnya adalah **indikator**, bukan bukti; jangan menuduh pihak tertentu melakukan penipuan tanpa bukti kuat.

## Aturan

1. Gunakan **data publik** saja. Jangan mencoba masuk ke akun/grup privat, men-scrape dengan cara melanggar ToS, atau mengumpulkan data pribadi individu.
2. Jangan mengungkap atau menyebarkan identitas pribadi orang (doxxing). Analisis akun sebagai pola perilaku, bukan menyerang individu.
3. Katakan "pola menyerupai…" atau "ada indikasi…", bukan "pasti bot/scam", kecuali ada bukti kuat.
4. Pisahkan tegas antara **fakta yang teramati** dan **kesimpulan/dugaan**.
5. Sinyal sosial hanyalah satu dimensi; jangan jadikan satu-satunya dasar keputusan. Kombinasikan dengan riset proyek dan cek kontrak.

## Yang Dianalisis

### 1. Akun resmi (X/Twitter, dll.)
| Indikator | Sehat | Mencurigakan |
|---|---|---|
| Rasio follower vs interaksi | Seimbang, ada diskusi nyata | Follower puluhan ribu, like/komen sangat rendah |
| Pola pertumbuhan | Bertahap, ada lonjakan wajar saat pengumuman | Lonjakan tajam tanpa peristiwa |
| Komentar | Beragam, relevan | Seragam, emoji/slogan berulang, akun baru |
| Umur & riwayat akun | Aktivitas panjang | Akun baru/rename berkali-kali |
| Konten | Pengumuman teknis, update produk | Hanya hype, janji profit, countdown |

### 2. Discord / Telegram
- Rasio anggota online vs total; aktivitas percakapan nyata
- Moderasi: pertanyaan kritis dijawab atau dihapus/dibungkam?
- Bot yang menyapa di DM, link tanpa konteks, "support" yang menghubungi duluan
- Channel kosong/hanya spam "gm", atau role/quest yang dikejar tanpa diskusi isi
- Apakah tim menjawab pertanyaan teknis

### 3. Kampanye influencer / KOL
- Banyak akun memposting hal serupa pada waktu berdekatan (indikasi kampanye berbayar)
- Tidak ada pengungkapan sponsor; narasi seragam
- KOL pernah mempromosikan proyek yang kemudian gagal/rug
- Hype didorong oleh insentif ("posting dapat poin") bukan minat nyata

### 4. Sinyal off-platform
- Hasil pencarian: laporan scam, thread kritik, diskusi independen
- Aktivitas on-chain yang konsisten dengan klaim komunitas (pengguna nyata vs wallet baru bergerombol)
- Aktivitas developer (commit repositori, rilis)

### 5. Pola scam yang dikenal
Janji profit pasti, tekanan waktu, tim anonim dengan klaim besar, whitelist/mint "terbatas" yang di-push agresif, minta connect wallet cepat-cepat, tautan klaim dari DM, imitasi proyek terkenal.

## Skor

Beri 1–5 per dimensi: **Keaslian komunitas · Kualitas moderasi · Independensi hype · Konsistensi dengan on-chain/produk**.

- 🟢 **Organik** (sinyal sehat, minim indikator buruk)
- 🟡 **Campuran** (ada hype terdorong insentif, tapi komunitas dan produk nyata)
- 🟠 **Dibuat-buat** (banyak indikator bot/shill, produk tak mendukung)
- 🔴 **Pola scam** (banyak indikator sekaligus; hindari)

Cantumkan **tingkat keyakinan** (rendah/sedang/tinggi) dan alasan, karena data sosial mudah berisik.

## Format Laporan

```
## Sinyal Sosial: [Proyek] — 🟢/🟡/🟠/🔴 (keyakinan: ...)
Dicek: [tanggal]   Platform: ...

Teramati (fakta):
- ...
Dugaan (interpretasi):
- ...

Skor: Keaslian x/5 · Moderasi x/5 · Independensi hype x/5 · Konsistensi on-chain x/5

Rekomendasi: (lanjut riset / garap ringan dengan burner / hindari) + alasan
Yang belum bisa diverifikasi: ...

Catatan: indikator sosial bisa menyesatkan; gabungkan dengan due diligence dan cek kontrak.
```

## Batasan

Jika agent tidak bisa mengakses platform tertentu (login, rate limit), katakan sejujurnya dan jelaskan bagian mana yang tidak teranalisis. Jangan mengisi kekosongan dengan tebakan.
