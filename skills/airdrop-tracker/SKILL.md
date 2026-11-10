# Airdrop Tracker

Menjaga semua aktivitas airdrop tetap terorganisir: apa yang sedang digarap, berapa biaya terpakai, kapan deadline, dan apakah hasilnya sepadan.

## Aturan

1. Simpan **alamat publik saja**. Jangan pernah mencatat seed phrase, private key, atau password.
2. Jangan mengarang data. Jika biaya, harga token, atau tanggal belum diketahui, kosongkan atau tandai "belum diverifikasi".
3. Semua angka reward bersifat spekulatif; pisahkan jelas antara **realisasi** (sudah diterima/dijual) dan **estimasi**.
4. Tanggal dan deadline harus dicek ulang ke sumber resmi sebelum dijadikan patokan; info airdrop cepat berubah.
5. Tracker hanya mencatat; tidak mengeksekusi transaksi apa pun.

## Struktur Data

### Tab 1: Proyek (satu baris per proyek)

| Kolom | Isi |
|---|---|
| ID | Nomor/kode singkat |
| Proyek | Nama |
| Kategori | Testnet / Mainnet / Points / Quest / Free mint / Retro |
| Chain | Jaringan utama |
| Status | 🔍 Riset · ✅ Aktif · ⏸ Pause · ⏰ Menunggu snapshot · 🎁 Siap klaim · ✔ Selesai · ❌ Dibuang |
| Skor | 🟢/🟡/🔴 (dari hasil riset) |
| Wallet | Label wallet (bukan kunci), misal "Burner-A" |
| Tugas berikutnya | Aksi konkret berikutnya |
| Frekuensi | Harian / mingguan / sekali |
| Deadline | Tanggal snapshot/season/klaim |
| Biaya terpakai (USD) | Total gas + biaya lain |
| Modal terkunci (USD) | Dana yang di-stake/bridge/LP |
| Estimasi reward (USD) | Opsional, tandai sebagai estimasi |
| Reward realisasi (USD) | Hanya yang sudah diterima/dijual |
| Link resmi | Website, docs, pengumuman |
| Catatan | Risiko, kriteria, info penting |
| Terakhir diperbarui | Tanggal |

### Tab 2: Log Aktivitas (satu baris per aksi)
`Tanggal | Proyek | Wallet | Chain | Aksi | Hash transaksi | Biaya (USD) | Catatan`

### Tab 3: Klaim & Hasil
`Tanggal | Proyek | Token/NFT | Jumlah | Harga saat diterima | Dijual? | Harga jual | Catatan pajak`

### Tab 4: Deadline
Daftar terurut menurut tanggal: `Tanggal | Proyek | Jenis (snapshot/season end/klaim/mint) | Sudah dicek ke sumber resmi?`

## Alur Kerja

### Menambah proyek
Dari input user atau hasil riset, tambahkan baris dengan status 🔍 atau ✅. Isi kolom yang diketahui; sisanya kosong. Selalu catat link resmi dan tanggal pembaruan.

### Mencatat aktivitas
Saat user melapor ("sudah swap di X, gas $0.8"), tambahkan ke Log Aktivitas, lalu perbarui total biaya di tab Proyek. Hitung ulang, jangan menebak.

### Update status & tugas berikutnya
Setelah update, selalu pastikan kolom "Tugas berikutnya" terisi untuk proyek berstatus ✅. Proyek tanpa tugas berikutnya harus dipertanyakan: selesai, atau terlupa?

### Pengingat deadline
Saat menampilkan ringkasan, urutkan deadline terdekat di paling atas dan beri penanda:
- 🔴 ≤ 3 hari · 🟠 ≤ 7 hari · 🟡 ≤ 14 hari
Ingatkan untuk memverifikasi ulang tanggal ke sumber resmi.

## Perhitungan ROI

```
Total biaya   = biaya gas/fee + biaya lain (bridge, mint, subscription)
Biaya peluang = modal terkunci × durasi (catat, jangan dihitung sebagai biaya kas)
ROI realisasi = (reward realisasi − total biaya) / total biaya
ROI estimasi  = (reward estimasi − total biaya) / total biaya   ← tandai "estimasi"
```

Tampilkan keduanya terpisah. Jika ROI realisasi masih negatif dan reward belum ada, jangan simpulkan rugi atau untung; katakan "belum ada hasil".

Beri rekomendasi berbasis data, bukan harapan:
- Biaya tinggi + tanpa konfirmasi program resmi + deadline jauh → pertimbangkan ⏸ atau ❌
- Biaya rendah + program resmi + tugas jelas → lanjutkan
- Proyek tanpa aktivitas 30+ hari → tanyakan apakah masih relevan

## Laporan Mingguan

```
## Rekap Mingguan — [rentang tanggal]

Ringkasan: proyek aktif X · biaya minggu ini $Y · total biaya $Z
Deadline mendatang: (urut terdekat)
Tugas minggu ini: (checklist per proyek)
Perlu perhatian: proyek tanpa tugas berikutnya / lama tak aktif / biaya membengkak
Rekomendasi: lanjut / pause / buang (dengan alasan singkat)
Reward realisasi sejauh ini: $... (estimasi terpisah: $...)

Catatan: reward airdrop bersifat spekulatif dan tidak dijamin.
```

## Format Output

- **Spreadsheet (.xlsx)**: jika user minta file atau tabel yang akan dipakai berulang, buat berkas dengan empat tab di atas; gunakan formula (jumlah biaya, ROI) agar otomatis terhitung, dan baca skill `xlsx` terlebih dahulu bila tersedia.
- **Tabel di chat**: untuk update cepat atau ringkasan, gunakan tabel Markdown singkat.
- Gunakan bahasa user (default Bahasa Indonesia), angka dalam USD kecuali user menetapkan mata uang lain.

## Catatan Pajak

Pencatatan hash transaksi, tanggal, harga saat diterima, dan harga jual membantu pelaporan pajak. Aturan berbeda antar negara; sarankan user berkonsultasi dengan konsultan pajak. Skill ini bukan nasihat pajak atau hukum.
