# Evaluasi Diri — Trading & Analisa

Log jujur kesalahan dan perbaikannya. Ditulis mulai 10 Nov 2026 atas permintaan user: "kembangin skill kamu dan evaluasi kesalahan kamu mulai dari sekarang." Diperbarui setiap ada trade yang ditutup atau verdict yang terbukti salah.

## 10 Nov 2026

### 1. Veto UAI — kesalahan terbesar hari ini
- **Yang terjadi:** User mau masuk UAI di ~$0,038. Aku bilang NO TRADE (momentum turun, tidak ada setup). UAI lalu naik +13% ke $0,04328, dan puncaknya mencapai ~+20% ke $0,04568 (high hari $0,04782, +25% dari $0,038), sebelum turun lagi ke ~$0,04076 jam 19:22 WIB.
- **Kenapa salah:** Verdict "NO TRADE" kupakai sebagai veto, padahal keputusan masuk/tidak ada di user. Tugas aku memberi angka dan risiko, bukan menghalangi.
- **Perbaikan:** Kalau user bilang mau masuk, langsung keluarkan entry/stop/target + risiko apa adanya. Aturan tetap dihitung dan ditunjukkan, tapi bukan veto. Sudah dicatat di MEMORY.md dan dikodekan ke skill `multi-token-screener`.

### 2. Plin-plan soal MAGMA
- **Yang terjadi:** Sepanjang siang aku mengulang "hampir terkonfirmasi tapi belum" tanpa keputusan yang tegas. User menegur: "kasih jawaban yang jelas jangan plinplan."
- **Kenapa salah:** Memberi ketidakpastian berulang sama buruknya dengan memberi jawaban salah — user tidak bisa bertindak.
- **Perbaikan:** Setiap analisa ditutup dengan verdict jelas (MASUK / JANGAN MASUK) + kondisi pemicu yang tepat dengan angka. Kalau belum bisa diputuskan, sebutkan satu hal spesifik yang ditunggu (mis. "candle 17:15 tutup di atas $0,24427").

### 3. Analisa monoton
- **Yang terjadi:** 10 token dicek dengan template yang sama persis: harga, spread, volume, verdict. User menegur: "jangan monoton."
- **Perbaikan:** Variasikan sudut — perbandingan head-to-head, momentum, katalis/berita, skenario. Dikodekan ke `multi-token-screener`.

### 4. Entry SIGN tanpa bounce terkonfirmasi
- **Yang terjadi:** Plan SIGN-20261110-01 dicatat dengan bounce belum terkonfirmasi; entry di tengah range, stop tepat di low sebelumnya, volume di bawah minimum. Kena stop −1,00R.
- **Perbaikan:** Bounce terkonfirmasi adalah syarat, bukan preferensi. Dicatat di trade-journal Pelajaran.

### 5. Analisa pre-13:00 terkirim ke main chat, bukan WhatsApp
- **Yang terjadi:** Analisa 5 token dikirim ke main chat, user menunggu di WhatsApp sampai jam 13:15.
- **Perbaikan:** Hasil selalu dikirim ke chat yang meminta. Sudah dicatat di MEMORY.md.

### 6. User harus bertanya dulu soal kabar MAGMA (18:03 WIB)
- **Yang terjadi:** Candle 17:45 tutup di bawah level breakout $0,24427 jam 18:00, tapi tidak ada kabar sampai user bertanya "mana kabarnya?" jam 18:02.
- **Kenapa salah:** Job pantau hanya punya trigger untuk ENTRY. Posisi MAGMA sudah aktif, tapi tidak ada trigger untuk posisi — tidak ada kabar saat breakout melemah, stop kena, atau target kena. Pantau yang tidak mengabari = tidak memantau.
- **Perbaikan:** Job diperbarui 18:03 WIB dengan trigger posisi aktif: stop kena (≤$0,2409), target kena (≥$0,2577), breakout melemah (candle 15m tutup di bawah $0,24427), dan pulih (tutup kembali di atasnya). Setiap trigger dikabari sekali, tanpa menunggu user bertanya.

### 7. Temuan trade-review 10 Nov 2026 (n=2, dievaluasi 19:20 WIB)
- **SIGN:** Rencana kubuat walau bounce belum terkonfirmasi — pelanggaran checklist yang kucatat sendiri di rencana. Keputusan SALAH, hasil RUGI −1,00R.
- **MAGMA:** Keputusan MASUK 17:29 dibuat sebelum candle 17:15 tutup (17:30); masa berlaku rencana (sampai 17:30) bertabrakan dengan waktu konfirmasi sehingga entry aktual 17:37 di luar masa berlaku. Target $0,2577 tidak memperhitungkan resistance $0,25 di tengah jalan. Keputusan BENAR (setup valid), hasil RUGI −0,95R — sebagian besar variansi, dengan catatan analisis di atas.
- **Perbaikan:** entry hanya setelah candle konfirmasi tutup; masa berlaku rencana harus mencakup waktu tutup candle; target mencatat resistance berlapis; cut manual butuh alasan sendiri. Sampel n=2 terlalu kecil untuk mengubah aturan — tidak ada usulan perubahan.

### 8. R:R UAI salah hitung — target dibekukan saat entry berubah (11 Nov 2026, 03:33 WIB)
- **Yang terjadi:** Dari entry aktual $0,04072 dengan stop struktural $0,0394, aku bilang R:R jatuh ke ~0,6 dan stop ketat $0,0399 adalah "satu-satunya plan yang lolos". Salah: aku memakai target lama $0,0418 (target untuk entry saran $0,0402) padahal aturan 1:2 mengharuskan target = 2x jarak stop dari entry aktual — target yang benar $0,04336 (+6,48%), R:R bersih ~1,75, LOLOS. Limit user $0,043 ternyata hampir persis target yang benar — insting user lebih tepat dari hitunganku.
- **Kenapa salah:** Target diperlakukan sebagai angka tetap, bukan sebagai fungsi dari entry dan stop. Dan aku menyalahkan entry user ("entry-mu mengubah hitungannya") padahal yang salah hitunganku.
- **Perbaikan:** Setiap kali entry/stop berubah, hitung ulang target dari nol (target = entry + 2x jarak stop), jangan pernah membawa target dari skenario entry lain. Tulis rumus di setiap plan, bukan hanya hasilnya.

### 9. Trade-review UAI terlambat 36 jam
- **Yang terjadi:** UAI ditutup 11 Nov 03:59 WIB (+0,83R, kemenangan pertama), tapi trade-review baru dibuat 12 Nov 16:01 WIB — setelah user menegur "kamu tidak mengasah skill lagi?".
- **Kenapa salah:** Aturan cek-diri sendiri bilang review langsung setelah tiap trade ditutup. Aku malah sibuk urusan lain (skill baru, README) dan melewatkannya.
- **Perbaikan:** Trade-review dikerjakan segera setelah close, tanpa menunggu ditegur. Hasilnya dicatat di trade-journal Pelajaran (UAI: keputusan SALAH karena entry sebelum bounce terkonfirmasi — sama seperti SIGN; exit manual tepat waktu; rekap kumulatif n=3: 1 menang, 2 kalah, rata-rata −0,37R).

### 10. Analisa 14:00 selesai tapi gagal terkirim otomatis
- **Yang terjadi:** Cron analisa 5 token 12 Nov 14:00 WIB selesai dan laporannya siap, tapi upaya worker mengirim ke WhatsApp ditolak runtime ("cannot target a chat connected to an external messaging service"). Worker menutup tracked item sebagai completed TANPA konfirmasi delivery. Laporan baru sampai ke user 14:06 WIB setelah aku antar manual.
- **Kenapa salah:** Item ditutup completed padahal delivery belum terkonfirmasi. "Selesai dianalisa" bukan "sampai ke user".
- **Perbaikan:** Tracked item hanya ditutup setelah delivery terkonfirmasi di chat yang meminta. Kalau pengiriman otomatis gagal, antar manual dan catat kegagalannya — jangan diam.

## 12 Nov 2026

### 11. Trigger $0,2771 terlalu telat untuk thesis pump CYBER
- **Yang terjadi:** Untuk thesis pump CYBER sebelum unlock, aku memberi trigger close di atas $0,2771. User menegur: "kalau nunggu 0.277 ya itu udah pump lah aneh." Benar: dari $0,2598 ke $0,2771 itu +6,6% — pump-nya sudah jalan duluan. Trigger itu kubuat dari analisa breakout biasa, bukan untuk menangkap pump dari awal.
- **Perbaikan:** Untuk thesis front-run/pump, beri level konfirmasi yang lebih awal (tutup di atas $0,2661, +2,4%; atau bounce di support $0,258) dan sebutkan trade-off-nya secara eksplisit: masuk awal = risiko fake-out lebih besar (buktinya breakout 17:25 yang terkonfirmasi berubah jadi penolakan sumbu sejam kemudian). Jangan memberi satu trigger generik untuk dua thesis yang berbeda.

### 12. Analisa hanya muter di token yang user sebutkan (monoton)
- **Yang terjadi:** Analisa berulang hanya mencakup watchlist user (BEAM, DOS, UAI, CYBER, AIO, BR, ARIA, dll). User menegur 18:24 WIB: "kamu ga analisa token lain selain token yg saya sebutkan... kesannya kayak monoton."
- **Kenapa salah:** `--discover` hanya mengambil 6-8 mover teratas dan nama yang sama terus muncul di atas. Aku tidak pernah menyaring universe yang lebih luas.
- **Perbaikan:** Setiap analisa besar sekarang menyaring universe penuh (ticker list, volume ≥$100k, buang saham tokenisasi + nama yang sudah dikenal) lalu scan mover terbesar yang baru. Malam itu juga ketemu MAGMA (pullback ke EMA 20/50 $0,2778-$0,2846) dari 168 token baru. Saringan baru ini masuk ke rutinitas analisa.

### 13. Format teks robotik — tiga kali ditegur dalam satu sore
- **Yang terjadi:** User menegur formatku tiga kali: "jangan robotic kayak ---- gini" (17:20), "teksnya jangan disatukan" (18:03), "jangan terlalu dipisah/garis baru" (18:06), lalu menunjukkan contoh gaya list yang dia mau.
- **Perbaikan:** Gaya yang disepakati: list tree rapat pakai ├ untuk item dan └ untuk item terakhir, pemisah ' : ', angka Entry/Stop/Target masing-masing satu baris, tanpa garis "----", tanpa baris kosong berlebihan. Dicatat di MEMORY.md dan dipakai mulai 18:07 WIB.

### 14. Entry CYBER $0,2613 sebelum konfirmasi (12 Nov 2026, 18:01 WIB)
- **Yang terjadi:** User masuk CYBER di $0,2613 atas inisiatif sendiri, sebelum breakout terkonfirmasi, tepat di bawah resistance berlapis, sebelum unlock. Ini pola yang sama seperti SIGN dan UAI: entry sebelum konfirmasi.
- **Yang benar dari sisiku:** Tidak veto (sesuai pelajaran UAI), langsung hitung angka dari entry aktual (stop $0,2565, target $0,2709, risiko $0,81, R:R bersih 1,52), tandai pelanggaran aturan secara eksplisit (tanpa breakout terkonfirmasi, target +3,67% di bawah target profit 5%, stop mepet, unlock), dan catat plan + tandai AKTIF di jurnal.
- **Catatan:** Target +3,67% di bawah target profit 5% user — plan ini tidak memenuhi target profitnya sendiri. Stop $0,2565 hanya 0,28 ATR di bawah low konsolidasi $0,2573, rawan kena sumbu.
- **Keputusan trade ini:** Belum selesai — posisi masih AKTIF. Evaluasi hasil (target/stop) ditulis setelah close, beserta review-nya.

### Verdict yang terbukti BENAR hari ini (12 Nov 2026)
- **DOS sengaja TIDAK dibuat LOLOS:** Jam 14:00 harga menempel resistance tiga sentuhan (+0,04%). Harga sesudahnya jatuh ke $0,1658 (16:56 WIB). Aturan ruang 4% bekerja dengan benar — penolakan itu benar, bukan aturan yang rusak. Cabang LOLOS tetap tercakup test sintetis.

### 15. Paper test BEAM (12 Nov 2026, 18:25 WIB) — masih terbuka
- Pick manual: NO TRADE sekarang; kondisional BEAM (tutup di atas $0,004526 + volume ≥1,5x; entry $0,00453, stop $0,004406, target $0,004778, R:R bersih 1,67). Kriteria evaluasi ditentukan sebelum hasil diketahui dan dicatat di `~/workspace/paper-trade-test.md`. Evaluasi ditulis saat pemicu terjadi atau expiry lewat (2026-11-13 07:00 WIB).

## Cara Aku Mengecek Diri Sendiri
- Setelah tiap trade ditutup: jalankan `trade-review`, tulis pelajaran ke trade-journal.
- Setiap verdict yang terbukti salah (menolak token yang naik / menerima token yang jatuh): catat di log ini, cari penyebabnya, perbaiki kriteria.
- Standar tidak berubah-ubah: checklist dan hitungan yang sama setiap kali. Kalau standarku melenceng, user menegur dan aku perbaiki — itu perjanjian kami (MEMORY.md).
