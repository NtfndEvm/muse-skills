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

### 16. Push GitHub kecil-kecil = kartu approval berulang (12 Nov 2026, 18:29 WIB)
- **Yang terjadi:** Tiga push dalam ~20 menit (VWAP merge, perintah `aktif`, evaluasi) — tiap push memunculkan kartu approval GitHub. User menegur: "kenapa selalu minta approval ke github."
- **Kenapa:** Push adalah tulis ke layanan luar; runtime minta persetujuan tiap kali karena tidak ada izin tetap untuk GitHub (dicek via daftar izin: hanya ada izin browser sementara). Instruksi user "gausah nunggu approval" hanya menghentikan aku bertanya di chat — kartunya dari pengaman runtime, bukan dariku, dan catatan memori tidak bisa mematikannya.
- **Perbaikan:** Kumpulkan update skill/evaluasi lalu push sekali jalan, bukan push tiap perubahan kecil. Bila kartu approval punya pilihan "selalu izinkan", user bisa pilih itu.

### 17. Trade-review CYBER — entry sebelum konfirmasi, ketiga kalinya (12 Nov 2026, 18:33 WIB)
- **Yang terjadi:** CYBER-20261112-01 ditutup kena stop $0,2565, −$0,81 / −1,00R. User mengakui sendiri: "murni kesalahan saya." Keputusan SALAH (aturan) — entry $0,2613 sebelum breakout terkonfirmasi, pola yang sama seperti SIGN dan UAI. Sekarang 3 dari 4 trade masuk tanpa konfirmasi; hasilnya 1 menang (UAI, diselamatkan exit manual) dan 2 kalah penuh −1,00R.
- **Detail yang memperburuk:** Entry tepat di bawah resistance berlapis; bounce $0,2480 sudah +5% di belakang; breakout 17:25 berubah jadi penolakan sumbu jam 17:45; stop hanya 0,28 ATR di bawah low konsolidasi; target +3,67% di bawah target profit 5%.
- **Yang benar:** Tidak veto, angka dihitung dari entry aktual, pelanggaran ditandai eksplisit, plan dicatat + AKTIF sebelum hasil diketahui, review ditulis langsung setelah close (tidak menunggu ditegur — perbaikan dari item 9).
- **Perbaikan:** Bukan aturan baru — aturannya sudah benar, yang kurang kepatuhannya. Untuk thesis pump, level konfirmasi harus yang lebih awal (item 11). Rekap kumulatif n=4: 1 menang, 3 kalah, rata-rata −0,53R, total −$1,68 kotor.

### 18. LOLOS pertama di data live — MAGMA 19:17 WIB (12 Nov 2026)
- **Yang terjadi:** Scan 19:17 WIB menyatakan MAGMA LOLOS — breakout terkonfirmasi di $0,280663 (3x) dengan ruang ke resistance +10,6%. Ini pertama kalinya cabang LOLOS menyala di data live (sebelumnya hanya uji sintetis). Konteksnya dramatis: candle 18:45 jebol support $0,2707 (tutup $0,2579), lalu candle 19:00 menyapu low $0,2451 dan balik ke $0,2855 dengan volume 6,8x — jebolnya fakeout, lalu breakout terkonfirmasi.
- **Yang benar:** Aturan room 4% bekerja — breakout yang lolos memang punya ruang. Jebol support yang langsung direbut kembali tidak langsung disimpulkan sebagai breakout gagal; scan menunggu tutup candle.
- **Catatan:** LOLOS bukan berarti langsung masuk. Harga sudah +6% di atas level breakout (chasing) dan sisa budget hari ini $1,39 tidak cukup untuk stop yang wajar di token dengan ATR 4,66%. Entry yang benar adalah retest $0,2807 — itu yang sekarang dipantau cron. Follow-through breakout ini masih harus dibuktikan.

### 19. Ditegur "masih plin-plan" — MAGMA 20:18 WIB (12 Nov 2026)
- **Yang terjadi:** User menegur langsung: "kamu masih pinplan." Di rentetan MAGMA malam ini aku terus berlindung di balik "tunggu tutup candle": breakout gagal (tutup 20:00 $0,2654 di bawah $0,2707), lalu pump ke $0,303 (candle 20:15 berjalan), lalu "tutup 20:30 yang nentuin." Tiap pesan benar secara faktual tapi tidak memberi keputusan — persis pola yang ditegur user soal MAGMA tanggal 10 Nov (item 2).
- **Yang benar (keputusan tegasnya):** MAGMA tidak bisa ditrade sekarang. Breakout GAGAL di tutup 20:00 — itu sudah final menurut aturan. Pump ke $0,303 adalah candle berjalan yang belum tutup dan bisa hilang sebelum 20:30. Masuk di $0,30 adalah chasing (+13% di atas level breakout). Sisa budget $1,39 juga tidak cukup untuk stop yang wajar di ATR 4,66%. Entry yang bersih, kalau ada, adalah retest $0,2807 — bukan kejar harga.
- **Perbaikan:** Kalau user minta pendapat, beri verdict dulu ("jangan masuk" / "masuk" / "tunggu X"), baru alasannya. "Tunggu tutup candle" bukan verdict — itu penundaan keputusan. Fakta yang belum terkonfirmasi boleh disebut, tapi harus ada satu kalimat keputusan yang berdiri sendiri.

### 20. Analisa cuma baca candle tutup — buta terhadap gerakan di dalam candle (12 Nov 2026)
- **Yang terjadi:** User menegur: "cara analisa kamu ada yang kurang." Konteksnya MAGMA: candle 20:15 naik 15% dalam satu candle ($0,2654 → $0,3067), lewat level breakout $0,2807 dalam hitungan menit. Aku masih bilang "tunggu retest $0,2807" padahal harga sudah di $0,30 — analisaku ketinggalan satu candle penuh.
- **Penyebabnya:** scan.py dan candle_reader membuang candle yang sedang berjalan dan hanya membaca candle tutup. Jadi aku buta terhadap pergerakan harga live di dalam candle; user yang lihat harga live selalu selangkah lebih cepat. Framework retest-ku juga mengasumsikan gerakan yang pelan dan tertib (sentuh level → tutup di atasnya → candle berikut tutup di atas high), padahal MAGMA merebut level dalam satu candle.
- **Perbaikan:** Di setiap cek, baca juga harga live (ticker) dan candle berjalan terhadap level — bukan cuma candle tutup. Kalau harga live sudah menembus level, laporkan saat itu juga sebagai "level tertembus live, belum terkonfirmasi" (tutup candle tetap yang mengonfirmasi), jangan tunggu tutup candle baru bicara. "Tunggu retest" tidak boleh diucapkan kalau harga live sudah lewat level itu.

### 21. BLESS — rencana dicatat di breakout lemah, lalu breakout gagal (12 Nov 2026)
- **Yang terjadi:** BLESS-20261112-01 dicatat 20:31 WIB (entry $0,00853, stop $0,00835, target $0,00889, net R:R 1,60) setelah breakout high 24j $0,008420 terkonfirmasi tutup 20:15 ($0,0084897). Kurang dari 30 menit kemudian harga dump ke $0,0082171 di candle 20:45 dengan volume 2,3 juta — di bawah level breakout dan di bawah stop rencana. Rencana dibatalkan 20:58 WIB sebelum entry, jadi tidak ada uang hilang.
- **Kesalahanku:**
  1. **Breakout-nya lemah tapi tetap kubuat rencana.** Scan bilang BREAKOUT_LEMAH — volume candle breakout cuma 1,09x (normal), bukan spike. Setup 1 mensyaratkan "tutup di atas resistance + volume spike". Volume tidak memenuhi syarat, tapi aku tetap mencatat rencana dan menyajikannya sebagai LOLOS. Syarat setup dilanggar diam-diam, cuma disebut sebagai "catatan".
  2. **Entry-nya ngejar.** Bounce terkonfirmasi di EMA20 $0,00829, entry $0,00853 itu +2,9% di atas level bounce. Bukan entry di bounce, tapi entry setelah harga lari.
  3. **Harga sudah sangat extended.** Di tutup 20:15 harga +3,8 ATR di atas VWAP. Breakout dari posisi yang sudah sejauh itu rawan pullback — aku baca angkanya tapi tidak menjadikannya lampu merah.
  4. **Target di bawah target profit user.** Target +4,22%, di bawah target 5% — pola yang sama seperti CYBER (+3,67%). Rencana yang tidak memenuhi target profit user tetap kucatat.
- **Yang benar:** Rencana dibatalkan sebelum entry begitu setup batal (tidak ada uang hilang), dan dua catatan (volume normal, target <5%) sudah kusebutkan saat menyajikan rencana — tapi menyebutkannya sebagai catatan tidak sama dengan menolak rencana yang tidak memenuhi syarat.
- **Perbaikan:** Syarat setup (termasuk volume spike untuk breakout) adalah syarat, bukan catatan. Kalau satu syarat tidak terpenuhi, rencananya DITOLAK, bukan dicatat dengan catatan kaki. Entry harus di level bounce/retest, bukan +3% di atasnya. Extension >3 ATR di atas VWAP = lampu merah, bukan latar belakang.

### 22. Discover ngasih LOLOS ke saham tokenisasi — RPARA 13 Nov 2026
- **Yang terjadi:** Scan pagi 13 Nov 2026 (`--discover 8`) ngasih 1 KANDIDAT LOLOS: RPARA/USDT $0,13, +41,5% 24j, volume $17,7 jt, spread 0,077%, bounce terkonfirmasi. Hampir kusajikan sebagai kandidat entry. Ternyata RPARA = saham tokenisasi Banzai International (rToken Bitget, listing 6 Nov 2026) — bukan kripto. RCDNL/RCADL/RCBRG di batch discover yang sama juga berpola rToken.
- **Kesalahanku:** Filter saham-tokenisasi di scan.py cuma daftar statis ~30 nama besar (TOKENIZED_STOCKS), sementara Bitget sudah >3.000 rToken. Daftar eksplisit tidak akan pernah lengkap — ini cacat desain, bukan sekadar satu nama ketinggalan.
- **Perbaikan (sudah dikerjakan 13 Nov 2026, sebelum analisa pagi dikirim):** discover sekarang baca endpoint symbols Bitget dan menyaring semua pair `areaSymbol=yes` secara dinamis, plus RPARA masuk daftar statis sebagai cadangan. 3 tes baru, total test_scan 28 tes — semuanya lolos. Verifikasi live ulang: discover yang sama sekarang ngasih 8 token kripto asli (JCT, BARD, MTX, IDOL, MAGMA, DODO, NES, KOR), verdict NO TRADE. Pelajaran: kalau satu kandidat LOLOS dari discover, cek dulu identitas tokennya (baseCoin + areaSymbol di endpoint symbols) sebelum disajikan — apalagi simbol berawalan R.

## Cara Aku Mengecek Diri Sendiri
- Setelah tiap trade ditutup: jalankan `trade-review`, tulis pelajaran ke trade-journal.
- Setiap verdict yang terbukti salah (menolak token yang naik / menerima token yang jatuh): catat di log ini, cari penyebabnya, perbaiki kriteria.
- Standar tidak berubah-ubah: checklist dan hitungan yang sama setiap kali. Kalau standarku melenceng, user menegur dan aku perbaiki — itu perjanjian kami (MEMORY.md).
