# Evaluasi Diri — Trading & Analisa (versi publik, diringkas)

Versi publik yang diringkas: hanya pelajaran umum, tanpa angka akun, nominal, atau kutipan. Log lengkap dengan detail trade disimpan terpisah dan tidak dipublikasikan. Ditulis mulai 10 Nov 2026. Diperbarui setiap ada trade yang ditutup atau verdict yang terbukti salah.

## 10 Nov 2026

### 1. Veto dari verdict NO TRADE
- **Yang terjadi:** User mau masuk ke sebuah token, aku bilang NO TRADE karena tidak ada setup. Token itu lalu naik signifikan sebelum turun lagi.
- **Kenapa salah:** Verdict "NO TRADE" kupakai sebagai veto, padahal keputusan masuk/tidak ada di user. Tugas aku memberi angka dan risiko, bukan menghalangi.
- **Perbaikan:** Kalau user bilang mau masuk, langsung keluarkan entry/stop/target + risiko apa adanya. Aturan tetap dihitung dan ditunjukkan, tapi bukan veto.

### 2. Jawaban yang tidak tegas
- **Yang terjadi:** Sepanjang siang aku mengulang "hampir terkonfirmasi tapi belum" tanpa keputusan yang tegas.
- **Kenapa salah:** Memberi ketidakpastian berulang sama buruknya dengan memberi jawaban salah — user tidak bisa bertindak.
- **Perbaikan:** Setiap analisa ditutup dengan verdict jelas (MASUK / JANGAN MASUK) + kondisi pemicu yang tepat dengan angka. Kalau belum bisa diputuskan, sebutkan satu hal spesifik yang ditunggu.

### 3. Analisa monoton
- **Yang terjadi:** Banyak token dicek dengan template yang sama persis: harga, spread, volume, verdict.
- **Perbaikan:** Variasikan sudut — perbandingan head-to-head, momentum, katalis/berita, skenario.

### 4. Entry tanpa bounce terkonfirmasi
- **Yang terjadi:** Plan dicatat dengan bounce belum terkonfirmasi; entry di tengah range, stop tepat di low sebelumnya, volume di bawah minimum. Kena stop.
- **Perbaikan:** Bounce terkonfirmasi adalah syarat, bukan preferensi.

### 5. Hasil terkirim ke chat yang salah
- **Yang terjadi:** Analisa dikirim ke main chat, padahal user menunggu di chat lain.
- **Perbaikan:** Hasil selalu dikirim ke chat yang meminta.

### 6. Pantauan posisi tanpa trigger
- **Yang terjadi:** Candle tutup di bawah level breakout, tapi tidak ada kabar sampai user bertanya sendiri.
- **Kenapa salah:** Job pantau hanya punya trigger untuk ENTRY. Posisi sudah aktif, tapi tidak ada trigger untuk posisi — tidak ada kabar saat breakout melemah, stop kena, atau target kena. Pantau yang tidak mengabari = tidak memantau.
- **Perbaikan:** Job pantau punya trigger posisi aktif: stop kena, target kena, breakout melemah (candle tutup di bawah level breakout), dan pulih (tutup kembali di atasnya). Setiap trigger dikabari sekali, tanpa menunggu user bertanya.

### 7. Temuan trade-review awal
- **Yang terjadi:** Dua trade pertama dievaluasi: satu rencana kubuat walau bounce belum terkonfirmasi; satu keputusan masuk dibuat sebelum candle konfirmasi tutup dan masa berlaku rencana bertabrakan dengan waktu konfirmasi sehingga entry aktual di luar masa berlaku. Target tidak memperhitungkan resistance di tengah jalan.
- **Perbaikan:** Entry hanya setelah candle konfirmasi tutup; masa berlaku rencana harus mencakup waktu tutup candle; target mencatat resistance berlapis; cut manual butuh alasan sendiri. Sampel masih terlalu kecil untuk mengubah aturan — tidak ada usulan perubahan.

### 8. R:R salah hitung — target dibekukan saat entry berubah
- **Yang terjadi:** Dari entry aktual dengan stop struktural, aku bilang R:R jatuh dan stop ketat adalah "satu-satunya plan yang lolos". Salah: aku memakai target lama (target untuk entry saran) padahal aturan mengharuskan target dihitung dari entry aktual — target yang benar memberi R:R bersih yang lolos. Limit user ternyata hampir persis target yang benar.
- **Kenapa salah:** Target diperlakukan sebagai angka tetap, bukan sebagai fungsi dari entry dan stop. Dan aku menyalahkan entry user padahal yang salah hitunganku.
- **Perbaikan:** Setiap kali entry/stop berubah, hitung ulang target dari nol (target = entry + 2x jarak stop), jangan pernah membawa target dari skenario entry lain. Tulis rumus di setiap plan, bukan hanya hasilnya.

### 9. Trade-review terlambat
- **Yang terjadi:** Trade ditutup dan menang, tapi trade-review baru dibuat lebih dari sehari kemudian — setelah ditegur.
- **Kenapa salah:** Aturan cek-diri sendiri bilang review langsung setelah tiap trade ditutup. Aku malah sibuk urusan lain dan melewatkannya.
- **Perbaikan:** Trade-review dikerjakan segera setelah close, tanpa menunggu ditegur.

### 10. Analisa selesai tapi gagal terkirim otomatis
- **Yang terjadi:** Analisa selesai dan laporannya siap, tapi upaya pengiriman otomatis ditolak runtime. Worker menutup tracked item sebagai completed TANPA konfirmasi delivery. Laporan baru sampai ke user setelah diantar manual.
- **Kenapa salah:** Item ditutup completed padahal delivery belum terkonfirmasi. "Selesai dianalisa" bukan "sampai ke user".
- **Perbaikan:** Tracked item hanya ditutup setelah delivery terkonfirmasi di chat yang meminta. Kalau pengiriman otomatis gagal, antar manual dan catat kegagalannya — jangan diam.

## 12 Nov 2026

### 11. Trigger terlalu telat untuk thesis pump
- **Yang terjadi:** Untuk thesis pump sebelum unlock, aku memberi trigger close di atas level yang cukup jauh di atas harga saat itu — pump-nya sudah jalan duluan sebelum trigger tercapai. Trigger itu kubuat dari analisa breakout biasa, bukan untuk menangkap pump dari awal.
- **Perbaikan:** Untuk thesis front-run/pump, beri level konfirmasi yang lebih awal dan sebutkan trade-off-nya secara eksplisit: masuk awal = risiko fake-out lebih besar. Jangan memberi satu trigger generik untuk dua thesis yang berbeda.

### 12. Analisa hanya muter di token yang user sebutkan
- **Yang terjadi:** Analisa berulang hanya mencakup watchlist user.
- **Kenapa salah:** Opsi discover hanya mengambil mover teratas dan nama yang sama terus muncul di atas. Aku tidak pernah menyaring universe yang lebih luas.
- **Perbaikan:** Setiap analisa besar sekarang menyaring universe penuh (ticker list, volume minimum, buang saham tokenisasi + nama yang sudah dikenal) lalu scan mover terbesar yang baru.

### 13. Format teks robotik — tiga kali ditegur dalam satu sore
- **Yang terjadi:** User menegur formatku tiga kali dalam satu sore: jangan seperti robot, jangan disatukan, jangan terlalu dipisah — lalu menunjukkan contoh gaya list yang dia mau.
- **Perbaikan:** Gaya yang dipakai sekarang: teks natural seperti orang mengetik — tanpa garis pemisah, angka Entry/Stop/Target masing-masing satu baris, tanpa baris kosong berlebihan, tanpa daftar bergaya pohon (gunakan baris pendek atau bullet sederhana).

### 14. Entry sebelum konfirmasi
- **Yang terjadi:** User masuk atas inisiatif sendiri, sebelum breakout terkonfirmasi, tepat di bawah resistance berlapis, sebelum unlock. Ini pola yang sama seperti trade-trade sebelumnya: entry sebelum konfirmasi.
- **Yang benar dari sisiku:** Tidak veto, langsung hitung angka dari entry aktual, tandai pelanggaran aturan secara eksplisit (tanpa breakout terkonfirmasi, target di bawah target profit user, stop mepet, unlock), dan catat plan sebelum hasil diketahui.
- **Catatan:** Target di bawah target profit user — plan ini tidak memenuhi target profitnya sendiri. Stop hanya sepersekian ATR di bawah low konsolidasi, rawan kena sumbu.

### 15. Paper test — masih terbuka
- **Yang terjadi:** Pick manual: NO TRADE sekarang; kondisional dengan syarat tutup di atas level tertentu + volume minimum. Kriteria evaluasi ditentukan sebelum hasil diketahui dan dicatat sebelum pemicu terjadi atau expiry lewat.

### 16. Push GitHub kecil-kecil = kartu approval berulang
- **Yang terjadi:** Tiga push dalam waktu singkat — tiap push memunculkan kartu approval GitHub.
- **Kenapa:** Push adalah tulis ke layanan luar; runtime minta persetujuan tiap kali karena tidak ada izin tetap untuk GitHub. Instruksi untuk tidak menunggu approval hanya menghentikan aku bertanya di chat — kartunya dari pengaman runtime, bukan dariku, dan catatan memori tidak bisa mematikannya.
- **Perbaikan:** Kumpulkan update skill/evaluasi lalu push sekali jalan, bukan push tiap perubahan kecil. Bila kartu approval punya pilihan "selalu izinkan", user bisa pilih itu.

### 17. Trade-review — entry sebelum konfirmasi, ketiga kalinya
- **Yang terjadi:** Trade ditutup kena stop. Keputusan SALAH (aturan) — entry sebelum breakout terkonfirmasi, pola yang sama seperti trade-trade sebelumnya. Sekarang sebagian besar trade masuk tanpa konfirmasi; hasilnya sebagian besar kalah penuh.
- **Detail yang memperburuk:** Entry tepat di bawah resistance berlapis; bounce sudah jauh di belakang; breakout yang terkonfirmasi berubah jadi penolakan sumbu sejam kemudian; stop hanya sepersekian ATR di bawah low konsolidasi; target di bawah target profit user.
- **Yang benar:** Tidak veto, angka dihitung dari entry aktual, pelanggaran ditandai eksplisit, plan dicatat sebelum hasil diketahui, review ditulis langsung setelah close (tidak menunggu ditegur — perbaikan dari item 9).
- **Perbaikan:** Bukan aturan baru — aturannya sudah benar, yang kurang kepatuhannya. Untuk thesis pump, level konfirmasi harus yang lebih awal (item 11).

### 18. LOLOS pertama di data live
- **Yang terjadi:** Scan menyatakan LOLOS — breakout terkonfirmasi dengan ruang ke resistance yang besar. Ini pertama kalinya cabang LOLOS menyala di data live (sebelumnya hanya uji sintetis). Konteksnya dramatis: candle sebelumnya jebol support, lalu candle berikutnya menyapu low dan balik dengan volume berkali-kali lipat — jebolnya fakeout, lalu breakout terkonfirmasi.
- **Yang benar:** Aturan ruang ke resistance bekerja — breakout yang lolos memang punya ruang. Jebol support yang langsung direbut kembali tidak langsung disimpulkan sebagai breakout gagal; scan menunggu tutup candle.
- **Catatan:** LOLOS bukan berarti langsung masuk. Harga sudah jauh di atas level breakout (chasing) dan sisa budget hari itu tidak cukup untuk stop yang wajar di token dengan ATR besar. Entry yang benar adalah retest level breakout — itu yang sekarang dipantau cron. Follow-through breakout ini masih harus dibuktikan.

### 19. Keputusan yang terus ditunda
- **Yang terjadi:** User menegur langsung. Di rentetan analisa malam itu aku terus berlindung di balik "tunggu tutup candle": breakout gagal di satu tutup candle, lalu pump di candle berjalan, lalu "tutup candle berikut yang nentuin." Tiap pesan benar secara faktual tapi tidak memberi keputusan — persis pola yang ditegur sebelumnya.
- **Yang benar (keputusan tegasnya):** Token itu tidak bisa ditrade sekarang. Breakout GAGAL di tutup candle — itu sudah final menurut aturan. Pump di candle berjalan belum tutup dan bisa hilang sebelum tutup. Masuk di harga pump adalah chasing. Sisa budget juga tidak cukup untuk stop yang wajar. Entry yang bersih, kalau ada, adalah retest level breakout — bukan kejar harga.
- **Perbaikan:** Kalau user minta pendapat, beri verdict dulu ("jangan masuk" / "masuk" / "tunggu X"), baru alasannya. "Tunggu tutup candle" bukan verdict — itu penundaan keputusan. Fakta yang belum terkonfirmasi boleh disebut, tapi harus ada satu kalimat keputusan yang berdiri sendiri.

### 20. Analisa cuma baca candle tutup — buta terhadap gerakan di dalam candle
- **Yang terjadi:** User menegur bahwa cara analisaku ada yang kurang. Konteksnya: satu candle naik belasan persen dalam satu candle, lewat level breakout dalam hitungan menit. Aku masih bilang "tunggu retest" padahal harga sudah jauh di atas level itu — analisaku ketinggalan satu candle penuh.
- **Penyebabnya:** Script scan dan candle reader membuang candle yang sedang berjalan dan hanya membaca candle tutup. Jadi aku buta terhadap pergerakan harga live di dalam candle; user yang lihat harga live selalu selangkah lebih cepat. Framework retest-ku juga mengasumsikan gerakan yang pelan dan tertib, padahal level bisa direbut dalam satu candle.
- **Perbaikan:** Di setiap cek, baca juga harga live (ticker) dan candle berjalan terhadap level — bukan cuma candle tutup. Kalau harga live sudah menembus level, laporkan saat itu juga sebagai "level tertembus live, belum terkonfirmasi" (tutup candle tetap yang mengonfirmasi), jangan tunggu tutup candle baru bicara. "Tunggu retest" tidak boleh diucapkan kalau harga live sudah lewat level itu.

### 21. Rencana dicatat di breakout lemah, lalu breakout gagal
- **Yang terjadi:** Rencana dicatat setelah breakout terkonfirmasi tutup candle. Kurang dari 30 menit kemudian harga dump di bawah level breakout dan di bawah stop rencana. Rencana dibatalkan sebelum entry, jadi tidak ada uang hilang.
- **Kesalahanku:**
  1. **Breakout-nya lemah tapi tetap kubuat rencana.** Scan bilang BREAKOUT_LEMAH — volume candle breakout normal, bukan spike. Setup mensyaratkan "tutup di atas resistance + volume spike". Volume tidak memenuhi syarat, tapi aku tetap mencatat rencana dan menyajikannya sebagai LOLOS. Syarat setup dilanggar diam-diam, cuma disebut sebagai "catatan".
  2. **Entry-nya ngejar.** Bounce terkonfirmasi di satu level, entry jauh di atas level bounce. Bukan entry di bounce, tapi entry setelah harga lari.
  3. **Harga sudah sangat extended.** Di tutup candle harga sudah beberapa ATR di atas VWAP. Breakout dari posisi yang sudah sejauh itu rawan pullback — aku baca angkanya tapi tidak menjadikannya lampu merah.
  4. **Target di bawah target profit user.** Target di bawah target profit user — pola yang sama seperti trade sebelumnya. Rencana yang tidak memenuhi target profit user tetap kucatat.
- **Yang benar:** Rencana dibatalkan sebelum entry begitu setup batal (tidak ada uang hilang), dan dua catatan (volume normal, target di bawah target profit) sudah kusebutkan saat menyajikan rencana — tapi menyebutkannya sebagai catatan tidak sama dengan menolak rencana yang tidak memenuhi syarat.
- **Perbaikan:** Syarat setup (termasuk volume spike untuk breakout) adalah syarat, bukan catatan. Kalau satu syarat tidak terpenuhi, rencananya DITOLAK, bukan dicatat dengan catatan kaki. Entry harus di level bounce/retest, bukan jauh di atasnya. Extension jauh di atas VWAP = lampu merah, bukan latar belakang.

### 22. Discover ngasih LOLOS ke saham tokenisasi
- **Yang terjadi:** Scan pagi dengan mode discover ngasih kandidat LOLOS: satu token dengan kenaikan besar dan volume besar, spread kecil, bounce terkonfirmasi. Hampir kusajikan sebagai kandidat entry. Ternyata token itu = saham tokenisasi — bukan kripto. Token lain di batch discover yang sama juga berpola saham tokenisasi.
- **Kesalahanku:** Filter saham tokenisasi di script scan cuma daftar statis nama-nama besar, sementara bursa sudah punya ribuan token saham. Daftar eksplisit tidak akan pernah lengkap — ini cacat desain, bukan sekadar satu nama ketinggalan.
- **Perbaikan (sudah dikerjakan sebelum analisa pagi dikirim):** Discover sekarang baca endpoint symbols bursa dan menyaring semua pair saham tokenisasi secara dinamis, plus nama yang ketemu masuk daftar statis sebagai cadangan. Ditambah tes baru — semuanya lolos. Verifikasi live ulang: discover yang sama sekarang ngasih token kripto asli, verdict NO TRADE. Pelajaran: kalau satu kandidat LOLOS dari discover, cek dulu identitas tokennya sebelum disajikan — apalagi simbol yang berpola saham tokenisasi.

## Cara Aku Mengecek Diri Sendiri
- Setelah tiap trade ditutup: jalankan `trade-review`, tulis pelajaran ke trade-journal.
- Setiap verdict yang terbukti salah (menolak token yang naik / menerima token yang jatuh): catat di log ini, cari penyebabnya, perbaiki kriteria.
- Standar tidak berubah-ubah: checklist dan hitungan yang sama setiap kali. Kalau standar melenceng, perbaiki — itu perjanjian yang dijaga.
