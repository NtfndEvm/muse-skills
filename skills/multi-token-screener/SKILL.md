---
name: multi-token-screener
description: Memindai banyak pair spot sekaligus dalam satu jalan, memberi peringkat sesuai aturan scalping user (volume, spread, R:R bersih, budget harian), dan mengeluarkan daftar teratas dengan verdict tegas plus kondisi pemicu yang tepat. Gunakan saat user minta "cari token", "pair mana yang bagus", sebelum sesi, atau saat satu token tidak memberi entry — jangan cek satu-satu.
---

# Multi-Token Screener (Spot)

Turunan dari `scalp-setup-scanner`, `trade-planner-spot`, `risk-manager-spot`, dan `trade-review`. Bedanya: memindai **banyak pair sekaligus**, bukan satu-satu, supaya user tidak menunggu seharian tanpa entry.

## Aturan Mutlak
1. Read-only. Tidak mengeksekusi order, tidak meminta API key, seed, atau private key. Cukup data pasar publik (bursa spot: ticker + candle 15m).
2. Parameter user — tetap, jangan diubah tanpa persetujuan user: modal $44 USDT di bursa CEX spot, posisi full margin (100%), R:R 1:2, R:R bersih ≥ 1,5, batas rugi harian $2,20, maks 1–2 trade/hari, volume 24j ≥ $100k (kecuali pair disarankan user sendiri), timeframe 15m, hanya 3 setup yang disetujui (breakout + volume; pullback dengan bounce terkonfirmasi; range scalping di support teruji).
3. Fee bursa user belum terverifikasi — pakai asumsi ilustratif taker 0,1% + 0,1% dan sebut itu asumsi, bukan fee sebenarnya.
4. Verdict tegas: LOLOS / LOLOS BERSYARAT / DITOLAK, plus kondisi pemicu yang tepat (harga dan volume) yang mengubah verdict. Tidak ada "hampir" tanpa angka.
5. Bukan nasihat keuangan. Bukan sinyal beli/jual.

## Pelajaran yang Dikodekan ke Skill Ini
- **(UAI, 10 Nov 2026) Jangan veto keputusan user.** Kalau user bilang mau masuk, keluarkan entry/stop/target + risiko apa adanya dan biarkan user memutuskan. Verdict scanner bukan veto.
- **(MAGMA, 10 Nov 2026) Jangan plin-plan.** Setiap analisa ditutup dengan verdict jelas + kondisi pemicu yang tepat, bukan "tunggu" tanpa angka.
- **(SIGN, 10 Nov 2026) Entry tanpa bounce terkonfirmasi = kesalahan.** Bounce harus terkonfirmasi, kecuali user secara eksplisit memerintahkan sebaliknya dengan risiko yang sudah dijelaskan.
- **(10 Nov 2026) Jangan monoton.** Variasikan sudut analisa — perbandingan head-to-head, momentum, katalis/berita, skenario — bukan template yang sama setiap token.
- **(10 Nov 2026) Kirim hasil ke chat yang meminta** (WhatsApp), bukan ke main chat.

## Alur
1. Ambil daftar kandidat: pair yang user sebut + pair dari pantauan + pair bervolume besar di bursa spot.
2. Untuk tiap pair: ticker (harga, volume 24j, spread, kedalaman top-of-book) + candle 15m (30 candle) — catat jam WIB.
3. Hitung dengan kode/kalkulator: spread%, range 24j, break-even ilustratif, R:R bersih untuk stop 1% / 2% / 2,5%, risiko dolar pada modal $44, dan apakah muat di sisa budget harian.
4. Nilai setup 15m: posisi harga vs support/resistance, arah candle terakhir, volume.
5. Peringkat: lolos struktur dulu, lalu yang paling dekat dengan pemicu.
6. Keluarkan: 1 rekomendasi utama ATAU NO TRADE dengan alasan + kondisi pemicu tiap kandidat.
7. Serahkan yang lolos ke `trade-planner-spot` + `risk-manager-spot`, catat rencana di `trade-journal` sebelum hasil diketahui.

## Format Laporan
```
## Pindai Multi-Token — [tanggal, jam WIB]
Sumber: bursa publik · Data diambil: ... WIB · Sisa budget harian: $...
Diperiksa: N · Lolos: X · Lolos bersyarat: Y · Ditolak: Z

Ranking:
1. [Pair] 🟢/🟡 — harga ... · vol ... · spread ...% · R:R bersih (stop 2%) ... · risiko $...
   Setup: ... · Pemicu: ...
2. ...

Ditolak: [pair] — alasan singkat

Rekomendasi: [pair + angka entry/stop/target] ATAU NO TRADE — alasan.
```

## Evaluasi Diri
Setelah tiap trade ditutup, jalankan `trade-review` dan tulis pelajarannya ke Pelajaran di `trade-journal` + log evaluasi. Bandingkan verdict vs hasil. Kalau verdict salah (mis. menolak token yang lalu naik), catat kenapa dan perbaiki kriteria — jangan sembunyikan.

## Tool: scan.py
Jangan fetch ticker/candle manual lagi. Pakai `scripts/scan.py` (stdlib saja, API publik, read-only):
`python scan.py BEAM DOS KGEN` · `python scan.py --watchlist` (cek trigger di `~/workspace/watchlist.json`) · `python scan.py --discover 6` · `python scan.py BEAM --json out.json`.
Logika candle diambil dari `candle-reader-15m/scripts/candle_reader.py` (jangan ditulis ulang), rumus R:R dari `trade-journal/scripts/trade.py`. Tes: `python -m unittest test_scan` (22 tes). Detail dan uji penerimaan ada di `~/workspace/spek-tools-trading.md` §1.
Catatan: VWAP didukung sejak 12 Nov 2026 lewat `scripts/vwap.py` (VWAP sesi 00:00 UTC, dipakai scan.py bila reader belum punya field vwap; kolom Tren menampilkan jarak ke VWAP dalam ATR). Jalur LOLOS di data live belum pernah teruji (semua run live sejauh ini NO TRADE; BEAM 16:48 WIB sempat BOUNCE_TERKONFIRMASI tapi ditolak aturan ruang ke resistance).
