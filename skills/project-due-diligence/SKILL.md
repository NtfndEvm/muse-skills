# Project Due Diligence

Menghasilkan laporan riset yang ringkas dan bisa dipertanggungjawabkan untuk satu proyek. Tujuannya membantu user memutuskan apakah proyek layak dikerjakan, bukan meyakinkan atau menakut-nakuti.

## Aturan

1. **Cari data terkini lewat web search.** Info proyek crypto cepat basi; jangan mengandalkan ingatan untuk angka pendanaan, tokenomics, atau status token.
2. Utamakan **sumber primer**: dokumentasi resmi, blog proyek, repositori kode, pengumuman resmi, data on-chain, database pendanaan. Sumber sekunder (media, agregator) sebagai pendukung. Abaikan konten "shill" dan promosi berbayar.
3. Tandai setiap klaim: ✅ terverifikasi sumber primer · 🔸 dari sumber sekunder · ❓ tidak bisa diverifikasi. Jangan mengisi kekosongan dengan tebakan.
4. Jika sumber bertentangan, tampilkan konfliknya; jangan memilih diam-diam.
5. Jangan menebak harga token, valuasi masa depan, atau besaran airdrop. Bukan nasihat keuangan.
6. Jangan pernah meminta kunci atau dana user.

## Alur Riset

### 1. Identitas & tim
- Pendiri/tim: doxxed atau anonim, rekam jejak, proyek sebelumnya (sukses, gagal, rug?)
- Kantor/entitas hukum, jika ada
- Aktivitas tim: update rutin, respons di komunitas, perubahan personel mendadak

### 2. Pendanaan & investor
- Putaran, jumlah, tanggal, lead investor
- Kualitas investor (aktif membantu atau sekadar nama besar), apakah ada klaim investor yang tidak bisa diverifikasi
- Sisa runway bila bisa diperkirakan dari data publik

### 3. Produk & traksi
- Produk berfungsi di mainnet, atau baru roadmap/landing page
- Pengguna aktif, TVL, volume, transaksi (data on-chain/dashboard seperti DefiLlama, Dune, explorer)
- Apakah traksi organik atau didorong insentif sementara (volume turun drastis saat reward berhenti)
- Audit keamanan: siapa auditornya, temuan, apakah ada insiden/exploit

### 4. Tokenomics (jika ada token)
| Aspek | Yang dicek | Sinyal buruk |
|---|---|---|
| Supply | Total, circulating, FDV | Circulating sangat kecil vs FDV tinggi |
| Alokasi | Tim, investor, komunitas, treasury, airdrop | Tim+investor mendominasi |
| Vesting | Cliff, jadwal unlock, tanggal besar | Unlock besar dekat TGE tanpa lock |
| Utilitas | Fungsi token di ekosistem | Hanya untuk spekulasi |
| Insentif | Emisi, inflasi | Emisi tinggi menekan harga |
| Airdrop | Persentase supply, kriteria | Tidak ada info resmi |

### 5. Program insentif / airdrop
- Ada program resmi (points, season, kriteria)? Tautan sumber resmi
- Tim pernah mengonfirmasi atau menyangkal token? Kutip secara parafrase dengan sumber
- Peluang vs biaya aktivitas yang dibutuhkan

### 6. Komunitas & sinyal sosial
Kualitas diskusi, rasio bot, respons tim, keluhan yang berulang. (Untuk analisis mendalam, gunakan skill social-signal-scanner bila tersedia.)

### 7. Risiko
Pisahkan: risiko teknis (kontrak, bridge), risiko tim/sentralisasi, risiko regulasi, risiko likuiditas/pasar, risiko eksekusi (kompetisi, ketergantungan satu pendukung).

### 8. Perbandingan sejenis
Bandingkan dengan 2–3 proyek di kategori yang sama (valuasi, traksi, pendanaan, program insentif) agar konteksnya jelas, bukan menilai dalam ruang hampa.

## Skor Akhir

Beri skor 1–5 per dimensi: Tim · Pendanaan · Produk/Traksi · Tokenomics · Transparansi · Risiko (5 = risiko rendah). Total ringkas jadi:
- 🟢 **Layak digarap** · 🟡 **Pantau / garap ringan** · 🔴 **Hindari**

Jelaskan alasan utama dalam 2–3 kalimat. Skor adalah ringkasan penilaian, bukan prediksi hasil.

## Format Laporan

```
# Due Diligence: [Proyek] — 🟢/🟡/🔴
Dicek: [tanggal]   Sumber utama: ...

Ringkasan (3–4 kalimat)

Tim & pendanaan: ...
Produk & traksi: ...
Tokenomics: ...
Program insentif: ...
Risiko utama: ...
Perbandingan: ...

Skor: Tim x/5 · Dana x/5 · Produk x/5 · Token x/5 · Transparansi x/5 · Risiko x/5

Rekomendasi: (lanjut / garap ringan / pantau / hindari) + alasan
Belum terverifikasi: ...
Sumber: ...

Catatan: riset ini bersifat informasi, bukan nasihat keuangan; hasil airdrop tidak dijamin.
```
Satu halaman adalah target. Perpanjang hanya jika user minta rincian.
