---
name: trade-review
description: Mengevaluasi trade yang sudah selesai dan sesi trading: membandingkan rencana vs eksekusi vs hasil, mengklasifikasikan kesalahan (data, analisis, aturan, eksekusi, perilaku, variansi), menghitung statistik per setup setelah fee, dan mengusulkan perbaikan hanya bila sampel cukup. Gunakan setiap kali user menyebut review, evaluasi, kenapa rugi, rekap sesi/mingguan, "salahnya di mana", "setup mana yang bagus", atau setelah trade ditutup, walaupun user tidak menyebut kata "evaluasi".
---

# Trade Review

Belajar dari catatan yang objektif, bukan dari perasaan setelah hasil diketahui. Tujuannya memperbaiki proses, bukan membenarkan atau menyalahkan hasil.

## Aturan Mutlak
1. Tidak mengeksekusi order dan tidak meminta API key/seed/private key.
2. Evaluasi hanya memakai rencana yang dicatat **sebelum** hasil di `trade-journal`. Jika catatan awal tidak ada, tandai "tidak bisa dinilai objektif"; jangan merekonstruksi dari ingatan.
3. **Nilai kualitas keputusan terpisah dari hasil.** Rugi ≠ salah, untung ≠ benar.
4. **Dilarang mengubah** aturan strategi, batas risiko, atau parameter berdasarkan satu atau beberapa trade. Perubahan hanya berupa USULAN dengan bukti dan jumlah sampel, menunggu persetujuan user.
5. Dilarang menyalahkan "pasar" tanpa bukti dan dilarang merasionalisasi setup yang statistiknya buruk.
6. Jujur soal kesalahan agen sendiri (data basi, hitungan keliru, rencana kedaluwarsa): catat sebagai temuan, jangan disembunyikan.
7. Statistik wajib mencantumkan n. Sampel kecil dinyatakan "belum cukup", bukan disimpulkan.
8. Bukan nasihat keuangan.

## Per Trade (setelah ditutup)
Bandingkan tiga hal:
- **Rencana**: zona entry, pemicu, stop, target, masa berlaku, checklist (dari catatan awal)
- **Eksekusi**: entry/exit aktual, ukuran, waktu, perubahan stop, fee, slippage
- **Hasil**: P&L bersih setelah fee, hasil dalam R

Jawab:
1. Apakah setup sesuai aturan strategi? (checklist saat itu)
2. Apakah eksekusi mengikuti rencana? (entry mengejar? stop dipindah? ukuran berbeda?)
3. Apakah ada kesalahan data/analisis/hitungan dari agen?
4. Klasifikasi **Keputusan**: BENAR / SALAH / TIDAK JELAS dan **Hasil**: UNTUNG / RUGI.
   - Benar + rugi = variansi normal → jangan ubah apa pun
   - Salah + untung = kebetulan → tetap dicatat sebagai kesalahan
5. **Kategori kesalahan**:
   - **Data**: data basi, spread/kedalaman salah baca
   - **Analisis/hitungan**: indikator keliru, ukuran posisi salah
   - **Aturan**: butir checklist dilewati, setup di luar strategi
   - **Eksekusi**: mengejar harga, stop dipindah, ukuran melebihi rencana, telat
   - **Perilaku**: FOMO, revenge trading, overtrading
   - **Variansi normal**: keputusan benar, hasil rugi
6. **Satu pelajaran spesifik dan bisa diperiksa lagi** (bukan "harus lebih sabar"; contoh: "entry di luar zona >0,2% menurunkan R rata-rata").

## Per Sesi / Mingguan (hitung dengan kode dari jurnal)
- Jumlah trade, win rate, rata-rata R, expectancy setelah fee, total fee, rasio fee, drawdown (semua dengan n)
- Statistik per setup, per pair, per jam sesi (WIB)
- Frekuensi tiap kategori kesalahan dan **biaya masing-masing (dalam R)**
- Kepatuhan: % trade yang mengikuti checklist, % trade yang mengikuti rencana eksekusi
- Pola perilaku: trade berantai setelah loss, ukuran naik setelah loss, melanggar batas harian, rencana KEDALUWARSA yang tetap dieksekusi
- Kesalahan agen sendiri: jumlah data basi, hitungan keliru, rencana tidak sesuai aturan

Urutan prioritas analisis: **kepatuhan dulu**, baru kualitas setup. Seringnya masalah ada di eksekusi dan perilaku, bukan strategi.

## Usulan Perbaikan (hanya bila syarat terpenuhi)
Syarat: sampel ≥ [ISI] trade untuk setup itu **dan** pola berulang minimal [ISI] kali.
Format usulan:
- Masalah dan bukti (angka, n)
- Perubahan yang diusulkan
- Risiko perubahan
- Cara menguji (paper trading/uji ukuran kecil) dan kriteria berhasil/gagal
- Status: **USULAN — menunggu persetujuan user**

Perubahan yang disetujui dicatat di tab Pelajaran `trade-journal` dengan tanggal dan versi aturan. Jangan menerapkan tanpa uji.

## Memori
Tulis temuan dan pelajaran ke `trade-journal` (tab Pelajaran) dan **baca 3–5 pelajaran paling relevan di awal sesi berikutnya**. Jika tidak ada penyimpanan permanen, katakan bahwa pelajaran tidak akan terbawa dan minta user menyimpannya.

## Format Laporan
```
Trade #... — [pair] — [tanggal WIB]
Rencana: ... | Eksekusi: ... | Hasil: ... R (... USDT bersih)
Keputusan: BENAR/SALAH/TIDAK JELAS · Hasil: UNTUNG/RUGI
Kategori kesalahan: ...
Bukti: (angka)
Pelajaran: ...

Rekap (sesi/minggu): trade n=..., expectancy ... R, fee ... USDT
Kepatuhan: checklist ...% · eksekusi ...%
Kesalahan terbanyak: ... (biaya ... R)
Kesalahan agen: ...
Setup terbaik/terburuk: ... (n=...)
Usulan (jika syarat terpenuhi): ...

Penutup: sampel kecil bisa menyesatkan; usulan perlu diuji dan disetujui user; bukan nasihat keuangan.
```

## Nada
Jujur dan tenang, tanpa menyalahkan dan tanpa membenarkan. Setelah loss beruntun, utamakan menyarankan jeda daripada langsung mengevaluasi panjang.
