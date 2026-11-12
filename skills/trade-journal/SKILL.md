---
name: trade-journal
description: Mencatat rencana dan hasil trade spot crypto secara terstruktur (rencana bertanda waktu sebelum hasil, eksekusi aktual, fee, hasil dalam R) dan menghitung statistik dari catatan tersebut. Gunakan setiap kali user menyebut jurnal, catat trade, entry/exit sudah terjadi, trade ditutup, rekap, win rate, expectancy, total fee, atau agen lain (trade-planner-spot, trade-review, risk-manager-spot) perlu menyimpan atau membaca riwayat trade, walaupun user tidak menyebut kata "jurnal".
---

# Trade Journal

Sumber kebenaran untuk semua evaluasi. Kualitas evaluasi `trade-review` bergantung pada kejujuran dan ketepatan catatan di sini.

## Aturan Mutlak
1. Hanya mencatat dan menghitung. Tidak mengeksekusi order, tidak meminta API key, seed phrase, atau private key.
2. **Rencana dicatat SEBELUM hasil diketahui**, dengan stempel waktu (WIB). Rencana tidak boleh diedit setelah trade berjalan; perubahan dicatat sebagai entri baru berlabel "perubahan" lengkap dengan waktu dan alasannya.
3. Jangan mengarang data. Kolom yang tidak diketahui dikosongkan dan ditandai ❓.
4. Semua statistik dihitung dengan kode atau formula, bukan perkiraan. Tampilkan jumlah sampel (n) di setiap statistik.
5. Simpan alamat publik dan ID order saja. Jangan pernah menyimpan kredensial.
6. Bukan nasihat keuangan.

## Lokasi Penyimpanan
Tanyakan sekali di mana jurnal disimpan (spreadsheet, CSV, file Markdown/teks yang bisa dibaca agen) dan gunakan tempat yang sama seterusnya. Jika agen tidak punya penyimpanan permanen, katakan terus terang bahwa catatan tidak terbawa antar sesi dan minta user menyimpan keluaran tiap sesi.

## Struktur Catatan

**Tab/berkas 1 — Trade** (satu baris per trade):
`ID | Tanggal-jam rencana (WIB) | Pair | Venue (bursa CEX/DEX+chain) | Setup | Zona entry | Pemicu | Stop | Target | Berlaku sampai | Checklist (n/N) | Risiko rencana (USDT) | Ukuran rencana | Status`

Diisi saat eksekusi/penutupan:
`Entry aktual | Waktu entry | Ukuran aktual | Exit aktual | Waktu exit | Fee total (USDT) | Slippage (%) | P&L kotor | P&L bersih | Hasil (R) | Stop dipindah? | Sesuai rencana? (ya/tidak) | Catatan`

Status: RENCANA · AKTIF · DITUTUP · BATAL (tidak terpicu) · KEDALUWARSA

**Tab/berkas 2 — Perubahan** (log setiap penyimpangan dari rencana):
`ID trade | Waktu (WIB) | Apa yang diubah | Alasan | Dicatat sebelum/sesudah kejadian`

**Tab/berkas 3 — Sesi**:
`Tanggal | Jumlah rencana | Jumlah trade | P&L bersih | Fee | Batas harian tercapai? | Kondisi/catatan singkat`

**Tab/berkas 4 — Pelajaran** (diisi oleh trade-review, disetujui user):
`Tanggal | Setup | Pelajaran | Bukti (n) | Status (usulan/disetujui/ditolak)`

## Definisi Perhitungan
```
R rencana        = jarak entry ke stop (dalam USDT per ukuran) = 1R
Hasil (R)        = P&L bersih / risiko rencana
P&L bersih       = P&L kotor − fee total − biaya lain
Win rate         = trade ditutup untung / trade ditutup (n tertulis)
Expectancy (R)   = rata-rata Hasil (R) semua trade ditutup (n tertulis)
Kepatuhan rencana = trade "sesuai rencana = ya" / trade ditutup
Rasio fee        = total fee / total P&L kotor positif
```
Trade BATAL dan KEDALUWARSA dihitung terpisah (bukan menang/kalah) tetapi dilaporkan.

## Alur
1. **Catat rencana** dari trade-planner-spot (setelah lolos risk-manager-spot): isi kolom rencana, status RENCANA, waktu rencana.
2. **Saat user melapor eksekusi**: isi entry aktual, ukuran, waktu; hitung slippage (selisih dari zona entry); status AKTIF.
3. **Setiap perubahan** (stop dipindah, ukuran ditambah): tambah entri di log Perubahan, jangan menimpa rencana.
4. **Saat ditutup**: isi exit, fee, P&L, hasil dalam R; status DITUTUP. Tanya "sesuai rencana?" dan alasannya bila tidak.
5. **Akhir sesi**: isi tab Sesi dan ringkas.
6. Serahkan ke `trade-review` untuk evaluasi, dan ke `crypto-tax-log` bila user ingin mencatat transaksi untuk pajak.

## Format Ringkasan
```
## Jurnal — [rentang tanggal WIB]
Trade ditutup: n=... · Batal: ... · Kedaluwarsa: ...
P&L bersih: ... USDT · Fee: ... USDT (rasio ...) · Expectancy: ... R (n=...)
Win rate: ...% (n=...) · Kepatuhan rencana: ...%
Data belum lengkap (❓): ...
Catatan: sampel kecil bisa menyesatkan; bukan nasihat keuangan.
```

## Kebiasaan yang Perlu Diingatkan
- Catat rencana sebelum masuk, bukan setelahnya
- Catat penyimpangan saat terjadi
- Jangan menghapus trade yang rugi; jurnal yang diedit mengurangi nilainya

## Tool: trade.py
Jangan hitung angka trade dengan tangan. Pakai `scripts/trade.py` (stdlib saja; semua rumus dihitung kode — target = entry + 2× jarak stop, net R:R, risiko $, P&L, hasil R):
`python trade.py plan --pair UAI --entry 0.04072 --stop 0.0399 --setup 2 --trigger "..." --expiry "2026-11-11 05:32 WIB"` · `python trade.py close --id UAI-20261111-01 --exit 0.0414 --alasan "..."` · `python trade.py status`.
Selalu kerjakan pada jurnal asli `~/workspace/trade-journal.md` (tool membuat cadangan `.bak` sebelum menulis). Untuk uji, pakai `--journal` ke salinan di /tmp dan `--now "YYYY-MM-DD HH:mm"` — kedua flag ini ditulis SETELAH subcommand (`trade.py plan --journal ... --now ... --pair ...`). Batas rugi harian dihitung dari P&L kotor NETO hari itu (menang mengurangi rugi); sisa budget = $2,20 − max(0, −P&L neto). Tes: `python -m unittest test_trade` (23 tes). Detail, rumus, dan uji penerimaan ada di `~/workspace/spek-tools-trading.md` §2.
