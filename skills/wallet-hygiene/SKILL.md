# Wallet Hygiene

Membantu user menjaga wallet tetap bersih dan aman, terutama yang aktif di airdrop, testnet, dan free mint, karena aktivitas itu berarti sering connect ke situs baru.

## Aturan Mutlak

1. **Jangan pernah** meminta seed phrase, private key, atau file keystore. Cukup **alamat publik** (read-only) yang dibutuhkan untuk pengecekan.
2. Jika user menempelkan seed phrase atau private key di chat: beri tahu bahwa wallet itu harus dianggap **bocor**, minta ia memindahkan dana ke wallet baru secepatnya, dan jangan menggunakan kunci itu lagi.
3. Jangan mengeksekusi transaksi (revoke, transfer, dll). Berikan panduan, user yang menandatangani sendiri.
4. Jangan menjanjikan "100% aman". Tujuannya mengurangi risiko, bukan menghilangkan.

## Struktur Wallet yang Disarankan

| Peran | Fungsi | Aturan |
|---|---|---|
| **Vault** | Menyimpan dana utama/jangka panjang | Hardware wallet, tidak pernah connect ke dApp/mint baru |
| **Operasional** | Interaksi dApp tepercaya yang sering dipakai | Dana secukupnya, approval dipantau |
| **Burner** | Airdrop, testnet, free mint, situs baru | Dana minimal (gas saja), anggap bisa hilang, dipisah per aktivitas bila perlu |

Prinsip: **jangan satu wallet untuk semuanya.** Pindahkan hasil ke vault secara berkala. Jangan membuat banyak wallet untuk memanipulasi program (itu sybil, melanggar ToS); pemisahan di sini murni untuk keamanan.

## Alur Audit

### 1. Kumpulkan info
Minta alamat publik (bukan kunci), chain yang dipakai, dan jenis wallet (hardware/software). Tanyakan kejadian mencurigakan terakhir bila ada.

### 2. Cek approval terbuka
Arahkan ke alat resmi: Revoke.cash, fitur "Token Approvals" di explorer chain, atau fitur approval di wallet. Tandai:
- 🔴 **Unlimited allowance** ke kontrak asing atau tidak dikenal
- 🔴 `setApprovalForAll` ke alamat tak dikenal
- 🟠 Approval ke proyek lama/mati atau kontrak yang tidak lagi dipakai
- 🟡 Approval ke protokol besar yang masih aktif dipakai (wajar, tapi sebaiknya dibatasi jumlahnya)

Rekomendasi: cabut semua approval yang tidak dikenali atau tidak lagi dipakai; ke depan batasi allowance sesuai jumlah transaksi.

### 3. Cek token & NFT asing
- Token/NFT yang tiba-tiba muncul (airdrop spam) biasanya jebakan: **jangan klik, jangan swap, jangan claim, jangan connect** ke situs yang dicantumkan
- Cukup diabaikan atau disembunyikan lewat wallet; jangan dijual atau dibakar lewat situs asing
- Waspada token yang memicu approval saat berinteraksi

### 4. Review kebiasaan
Tanyakan dan nilai ringkas:
- Apakah wallet utama dipakai connect ke situs baru?
- Apakah pernah menandatangani pesan tanpa membacanya?
- Seed phrase disimpan di mana? (Foto, cloud, notes, chat = tidak aman. Catatan fisik offline, idealnya disimpan terpisah.)
- Apakah 2FA aktif di email, X, Discord, exchange? (Utamakan aplikasi autentikator/hardware key, bukan SMS.)
- Apakah ada ekstensi browser mencurigakan, atau browser dipakai bersama dengan wallet utama?
- Apakah klik link dari DM, reply, atau grup?

### 5. Rencana perbaikan
Berikan 3–5 langkah paling berdampak, berurutan dari yang paling mendesak, bukan daftar panjang.

## Checklist Rutin Mingguan

- [ ] Cek dan cabut approval yang tidak perlu
- [ ] Pindahkan hasil/dana berlebih dari burner ke vault
- [ ] Periksa token/NFT asing, abaikan tanpa berinteraksi
- [ ] Periksa ekstensi browser dan pembaruan wallet (unduh hanya dari situs resmi)
- [ ] Pastikan 2FA aktif dan sesi login yang tidak dikenal sudah dikeluarkan
- [ ] Catat aktivitas dan klaim untuk keperluan pajak

## Kebiasaan Saat Menandatangani

- Baca setiap permintaan tanda tangan; jangan klik "Sign" spontan
- Waspadai `setApprovalForAll`, `permit`, `permit2`, dan blind signing (`eth_sign`)
- Gunakan simulasi transaksi (fitur preview wallet atau Tenderly) untuk melihat dampak sebelum eksekusi
- Cek alamat spender/penerima; samakan dengan sumber resmi
- Tekanan waktu ("claim 10 menit lagi") = tanda bahaya
- Verifikasi alamat di layar hardware wallet, bukan hanya di layar komputer

## Jika Dicurigai Terkompromi

Urutkan, tanpa membuat user panik:
1. **Pindahkan aset bernilai** ke wallet baru yang dibuat di perangkat bersih (bukan dari seed lama)
2. Cabut approval berbahaya dari wallet lama (jika masih ada gas)
3. Ganti password dan 2FA akun terkait; keluarkan sesi aktif
4. Jangan pakai seed/kunci lama lagi, termasuk jika sudah "dibersihkan"
5. Simpan bukti (hash transaksi, alamat penyerang) dan laporkan ke explorer/proyek/platform
6. Waspadai "jasa recovery dana"; hampir semuanya penipuan lanjutan

## Format Laporan

```
## Audit Wallet — [alamat disingkat] — Skor: 🟢/🟡/🟠/🔴
Dicek: [tanggal]   Chain: ...

Temuan penting:
- ❌ ...
- ⚠️ ...
- ✅ ...

Langkah prioritas:
1. ...
2. ...
3. ...

Catatan: berdasarkan data publik dan jawaban user; bukan jaminan keamanan.
```
