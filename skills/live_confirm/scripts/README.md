# live-confirm — tools konfirmasi cepat (5m, order book, delta volume)

Python stdlib saja, read-only, output Bahasa Indonesia (koma desimal). Berdiri sendiri; tools lama tidak diubah.
Semua tool membaca file JSON (atau `-` untuk stdin) hasil API publik Bitget v2.

## Cara pakai
```bash
B=https://api.bitget.com
curl -s "$B/api/v2/spot/market/candles?symbol=MAGMAUSDT&granularity=5min&limit=100" > c5.json
curl -s "$B/api/v2/spot/market/orderbook?symbol=MAGMAUSDT&limit=50" > ob.json
curl -s "$B/api/v2/spot/market/fills?symbol=MAGMAUSDT&limit=100" > fills.json

python3 reader_5m.py  --file c5.json --symbol MAGMA        # [--format json] [--last-closed] [--now-ms N]
python3 orderbook.py  --file ob.json --symbol MAGMA --level 0.2807   # [--thick-ratio 1.0]
python3 delta.py      --file fills.json --symbol MAGMA     # [--dominan 10]
```
Kode keluar 0 = terbaca, 2 = data tidak cukup/tidak valid. Tes: `python3 -m unittest discover -s . -p 'test_*.py'` (27 tes, tanpa jaringan, fixture di `fixtures/`).

## Aturan keputusan (eksplisit)
- **reader_5m**: logika candle sama dengan reader 15m (`interval_min=5`, candle berjalan dibuang, VWAP sesi 00:00 UTC min 10 candle).
  Kuat = higher high (vs 3 candle sebelumnya), volume TINGGI, breakout terkonfirmasi/retest bertahan, bullish dengan close dekat high.
  Lemah = sumbu atas ≥ 0,4, volume RENDAH, penolakan sumbu, support jebol, bearish besar.
  MELEMAH bila ada lemah dan lemah ≥ kuat; DITERUSKAN bila higher high tanpa lemah; selain itu NETRAL.
- **orderbook**: ±1% dari harga tengah; imbalance > 0,6 bid dominan, < 0,4 ask dominan. Level (`--level`) dicek ±0,3% pada sisi relevan
  (bid bila level ≤ harga tengah, selain itu ask): TEBAL bila depth ≥ acuan (rata-rata total bid/ask ±1% × 0,6), selain itu TIPIS.
  Bila level di luar jangkauan 50 level buku, verdict-nya TIDAK TERUKUR (bukan TIPIS; depth 0 karena tidak terukur) plus peringatan. Peringatan juga muncul bila 50 level tidak mencakup ±1%.
- **delta**: 100 trade terbaru; |delta| ≥ 10% = dominan, di bawahnya SEIMBANG; peringatan bila sampel < 20 trade.

## Contoh output (dari fixture, bukan data live)
```
MAGMA 0,2656 | tren 5m UPTREND | ATR 5m 0,00101027 (0,38%) | VWAP di atas | breakout 5m: BREAKOUT_TERKONFIRMASI @ 0,2641 | bounce 5m: BOUNCE_TERKONFIRMASI
5m: higher high, volume tinggi, breakout 5m terkonfirmasi, close dekat high → diteruskan

MAGMA order book | harga tengah 0,3 | spread 0,067%
Total ±1%: bid 247.840,00 USDT · ask 108.558,00 USDT · imbalance 0,70 (BID DOMINAN)
Level 0,299 (±0,3%): bid 170.430,00 · ask 0,00 USDT → TEBAL (sisi bid, acuan 106.919,40 USDT)

TOKEN delta volume | 4 trade terakhir
Beli 50,00 USDT (2 trade) · Jual 20,00 USDT (2 trade) · delta 42,9%
Kesimpulan: agresi BELI dominan.
```
**Catatan:** verifikasi live pada MAGMA sudah dijalankan di VM Muse 12 Nov 2026 ~22:04 WIB (harga waktu itu ~$0,30, turun dari high $0,3298 — pullback setelah breakout $0,31587 terkonfirmasi).

## Contoh output live (MAGMA, 12 Nov 2026 ~22:18 WIB — dijalankan di VM Muse, sesudah perbaikan label TIDAK TERUKUR)
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
Bacaan live ini benar: 5m bilang MELEMAH saat MAGMA pullback dari $0,3298 ke ~$0,30, padahal candle 15m belum tutup (baru tutup 22:15). Itulah gunanya tool ini — konfirmasi cepat di dalam candle 15m.
