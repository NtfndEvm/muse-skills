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

## Cara Aku Mengecek Diri Sendiri
- Setelah tiap trade ditutup: jalankan `trade-review`, tulis pelajaran ke trade-journal.
- Setiap verdict yang terbukti salah (menolak token yang naik / menerima token yang jatuh): catat di log ini, cari penyebabnya, perbaiki kriteria.
- Standar tidak berubah-ubah: checklist dan hitungan yang sama setiap kali. Kalau standarku melenceng, user menegur dan aku perbaiki — itu perjanjian kami (MEMORY.md).
