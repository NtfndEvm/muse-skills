# live_check.py — satu perintah untuk tiga tools

```bash
python3 live_check.py --symbol MAGMA [--level 0.2807] [--timeout 10] [--format json]
```
- Ambil 3 endpoint publik Bitget v2 (GET, tanpa kunci, urllib): candle `5min` (limit 100), order book (limit 50), fills (limit 100).
- Memanggil `reader_5m.analyze`, `orderbook.analyze`, `delta.analyze` lewat import; hasil dalam satu blok Bahasa Indonesia.
- Kode keluar `0` = ketiganya terbaca; `2` = ada yang gagal (baris terakhir menyebut yang mana). Satu kegagalan tidak menghentikan dua lainnya.
- `--format json` mengeluarkan satu JSON gabungan (`symbol, pair, level, ok, gagal, reader_5m, orderbook, delta`); teks tetap default. Kode keluar sama.
- Tes: `python3 -m unittest discover -s . -p 'test_*.py'` (37 tes, urllib di-mock, fixture di `fixtures/`).

## Contoh output live (MAGMA, 12 Nov 2026 ~22:18 WIB — dijalankan di VM Muse)
```
=== LIVE CHECK MAGMA (MAGMAUSDT) | level 0,2807 ===

MAGMA 0,30232 | tren 5m RANGE/CAMPUR | ATR 5m 0,0111059 (3,67%) | VWAP di atas | breakout 5m: TIDAK_ADA | bounce 5m: KANDIDAT_BOUNCE
5m: tidak ada tanda jelas → belum jelas (netral)
⚠️ candle 5m terakhir masih berjalan dan dibuang dari analisis

MAGMA order book | harga tengah 0,300765 | spread 0,090%
Total ±1%: bid 6.805,53 USDT · ask 11.314,95 USDT · imbalance 0,38 (ASK DOMINAN)
Tembok bid: 0,2998 (794,50 USDT); 0,29993 (665,81 USDT); 0,29947 (664,79 USDT)
Tembok ask: 0,30162 (1.468,89 USDT); 0,30394 (675,78 USDT); 0,30441 (675,76 USDT)
Level 0,2807 (±0,3%): bid 0,00 · ask 0,00 USDT → TIDAK TERUKUR (sisi bid, acuan 5.436,14 USDT)
⚠️ level di luar jangkauan order book yang diambil; depth level tidak terukur (bukan berarti tipis)

MAGMA delta volume | 100 trade terakhir
Beli 2.640,11 USDT (62 trade) · Jual 4.021,35 USDT (38 trade) · delta -20,7%
Trade terbesar: 0,30139 · 798,71 USDT · sell; 0,3014 · 758,08 USDT · sell; 0,30034 · 755,42 USDT · buy
Rentang: 2026-11-12 22:14:22 → 2026-11-12 22:18:30 WIB (247 detik)
Kesimpulan: agresi JUAL dominan.

Status: semua terbaca.
```
Perintah yang sama dengan `--format json` mengeluarkan satu JSON gabungan (`symbol, pair, level, ok, gagal, reader_5m, orderbook, delta`); teks tetap default.
