# fastmint-fcfs

[English](README.md) · **Bahasa Indonesia**

**FCFS mint di BNB Smart Chain lewat Binance Agentic Wallet, masuk blok ±2 detik setelah jam buka.**

Skill untuk AI agent (Claude Code, Codex, Cursor, OpenClaw, dan agent lain yang membaca `SKILL.md`) yang menembakkan satu transaksi mint/claim/buy tepat saat penjualan dibuka, memakai wallet Binance Agentic Wallet (`baw` CLI). Tidak ada private key di mesin: tanda tangan dilakukan oleh backend Binance lewat Developer Mode, agent hanya menyiapkan calldata dan memilih momen.

```
jam buka (T)      T+0.05s          T+0.6–0.8s        T+1.3–1.5s       T+2.1–2.2s
   │                 │                  │                  │                 │
   ▼                 ▼                  ▼                  ▼                 ▼
 start ───► preview dikirim ───► simulasi OK ───► BROADCASTED ───► masuk blok
          (pemicu jam NTP)      (requestId)     (baw execute)     (receipt)
```

Angka di atas diukur 11 Nov 2026 dari Indonesia: 3 dry-run bergerbang waktu plus satu mint nyata (Pocket Moons, 2 NFT gratis, trigger→receipt 2.0 detik). Versi sebelumnya yang berurutan butuh 5–6 detik.

---

## Daftar isi

1. [Cara kerja](#1-cara-kerja)
2. [Instalasi](#2-instalasi)
3. [Alur pemakaian](#3-alur-pemakaian)
4. [Referensi perintah](#4-referensi-perintah)
5. [Argumen dinamis](#5-argumen-dinamis)
6. [Rel pengaman](#6-rel-pengaman)
7. [Angka terukur](#7-angka-terukur)
8. [Troubleshooting](#8-troubleshooting)
9. [Struktur file](#9-struktur-file)
10. [FAQ](#10-faq)

---

## 1. Cara kerja

### Kenapa versi lama lambat

`baw` tidak punya perintah kirim-langsung untuk contract call. Alurnya wajib dua langkah: `contract-call preview` (backend mensimulasikan dan mengembalikan `requestId`) lalu `contract-call execute --requestId`. Versi lama menunggu RPC publik melaporkan `eth_call` sukses (±1 detik setelah blok pembuka), baru preview, baru execute. Tiap tahap menunggu tahap sebelumnya: T+5–6 detik.

### Tiga pemicu paralel

`fire.js` tidak menunggu satu sinyal. Dalam jendela **burst** 3 detik setelah jam buka, tiga pemicu masing-masing boleh meluncurkan preview (jarak minimal `--gap` 350ms, maksimal `--inflight` 3 sekaligus):

| pemicu | kapan | sumber |
|---|---|---|
| **clock** | tepat T+0 menurut jam yang dikoreksi NTP | `sntp` ke time.apple.com / pool.ntp.org |
| **head** | blok pertama dengan `timestamp ≥ start` terlihat | WebSocket `newHeads` (QuikNode, publicnode, drpc) + polling HTTP 150ms |
| **eth_call OK** | simulasi dari wallet sukses di salah satu dari 4 RPC tercepat | `eth_call` tag `latest` dan `pending`, tiap 100ms |

Preview pertama yang pulang dengan `simulationCode 000000000` langsung di-execute **satu kali**. Preview lain yang sedang berjalan diabaikan. Preview yang gagal karena backend belum melihat blok pembuka (error `351805`) murah dan tidak berefek, pemicu berikutnya mengulang.

Setelah burst habis, hanya **eth_call OK** yang memicu preview, jadi penjualan yang telat buka tidak menghabiskan `--maxPreviews`; spin `eth_call` terus memantau sampai `--timeout` (600 detik).

### Pool RPC yang diranking

Daftar RPC diukur saat start dan diurutkan ulang di T-10s (latensi dan lag blok). Dari Indonesia: QuikNode 31ms, bloXroute 32ms, 48.club 45ms, dataseed resmi ±105ms, publicnode ±200ms. Node yang membuang data revert (misal zan) tidak dipakai karena revert tanpa data tidak bisa dibedakan dari "belum buka".

Race `eth_call`: sukses pertama menang; revert **dengan data** menang (deterministik); revert tanpa data hanya dihitung setelah semua node menjawab dan tidak pernah dianggap fatal.

### Klasifikasi revert

Nama error didekode dari ABI Sourcify kontrak, daftar error umum bawaan, lalu 4byte. Setiap nama dipetakan ke:

- **wait**: `NotStarted`, `NotOpen`, `NotLive`, `TooEarly`, `Paused`, … → terus coba sampai `--timeout`
- **fatal**: `SoldOut`, `FreeGone`, `AlreadyClaimed`, `AgentIdRequired`, `NotEligible`, `WrongValue`, `Insufficient…` → berhenti seketika (±50ms)
- **unknown**: diperlakukan wait sampai `start + --grace` (10s), setelah itu fatal. Sebelum jam buka hanya nama hard-terminal (sold/gone/already/agent/eligible/expired) yang dianggap fatal.

Override dengan `--waitOn <regex>` dan `--fatalOn <regex>`.

---

## 2. Instalasi

### Prasyarat

- **Node.js ≥ 20** (dipakai v26). Tidak ada `npm install`: `ethers` 6.13 sudah dibundel.
- **Binance Agentic Wallet CLI**: `npm install -g @binance/agentic-wallet@1.12.0`
- **Binance App** dengan Agentic Wallet, **Developer Mode** aktif (Agentic Wallet → Settings → Developer Mode). Saldo wallet harus di bawah cap Developer Mode.
- Skill `binance-agentic-wallet` dari https://github.com/binance/binance-skills-hub (opsional tapi disarankan, untuk operasi wallet lain).
- Opsional: **Agent ID** (`namamu.ai`) untuk mint yang mensyaratkan Agent ID.

### Pasang skill

Ekstrak zip, lalu taruh folder `fastmint-fcfs` di tempat agent-mu membaca skill:

```bash
# Claude Code (per proyek)
mkdir -p .claude/skills && cp -r fastmint-fcfs .claude/skills/

# Claude Code (global)
mkdir -p ~/.claude/skills && cp -r fastmint-fcfs ~/.claude/skills/

# skills CLI / .agents (Codex, Cursor, dll)
mkdir -p .agents/skills && cp -r fastmint-fcfs .agents/skills/
chmod +x fastmint-fcfs/fastmint.sh
```

### Sign-in wallet (sekali, sesi tahan 2 hari / 48 jam idle)

```bash
baw auth signin --json
```

Buka `urlForWeb` yang muncul, cocokkan `pairingCode` di Binance App, setujui, lalu:

```bash
baw auth verify --qrCodeId <qrCodeId> --json
baw wallet status --json      # harus CONNECTED
```

### Cek lingkungan

```bash
cd fastmint-fcfs
./fastmint.sh bench
```

Keluaran yang diharapkan: ranking RPC, delay WebSocket, offset jam, `wallet status CONNECTED`, `devMode ON`, saldo BNB, Agent ID, tiga preview ±0.6s, dan estimasi waktu. Semua read-only.

### `.env` (RPC premium)

File `.env` di folder skill dibaca otomatis oleh `fastmint.sh`:

```bash
FASTMINT_RPCS_EXTRA=https://<endpoint-premium>     # ditaruh paling depan, tetap diranking
FASTMINT_WS_EXTRA=wss://<endpoint-premium>         # dipakai untuk newHeads
```

Zip ini sudah berisi `.env` dengan endpoint QuikNode BSC. Host-nya dimask di semua log. Variabel lain: `FASTMINT_RPCS` (ganti seluruh pool), `FASTMINT_WS`, `FASTMINT_TZ` (default `Asia/Jakarta`), `FASTMINT_CA` (bundel CA untuk Node, lihat troubleshooting).

---

## 3. Alur pemakaian

Ini alur yang dijalankan agent saat kamu bilang **"mint free jam 23:00 https://situs-mint"**:

```
┌──────────┐    ┌──────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────┐
│  bench   │───►│  recon   │───►│  fire --dry  │───►│    fire      │───►│  report  │
│ env OK?  │    │ CA, ABI, │    │ latihan 10s  │    │ background,  │    │ tx, link,│
│ ~10s     │    │ getter,  │    │ sebelum jam  │    │ 1x execute   │    │ TIMELINE │
│          │    │ calldata │    │ berhenti pre │    │              │    │          │
└──────────┘    └──────────┘    └──────────────┘    └──────────────┘    └──────────┘
```

**Langkah 0, bench** (sekali per sesi). Kalau `UNCONNECTED` → sign-in dulu. Kalau devMode OFF → nyalakan di app.

**Langkah 1, recon** (~5–10s):

```bash
./fastmint.sh recon https://situs-mint            # atau --contract 0x... kalau CA sudah tahu
```

Recon mengambil HTML, bundle JS, dan dokumen agent (`llms.txt`, `skill.md`, `handbook.md`, …), mengekstrak alamat, chainId, nama fungsi mint, signature ABI, dan unix time. Lalu `eth_getCode`, ABI dari Sourcify v2 (atau ABI dari bundle situs yang disaring ke selector yang benar-benar ada di bytecode), membaca semua getter view (0-arg, `(wallet)`, `(agentId)`), dan mencetak **MINT CANDIDATES** dengan tebakan argumen, calldata, hasil simulasi, `START HINT` dari getter start, dan perintah `fire:` siap pakai.

Yang dibaca dari output: jam buka, sisa free, harga, limit per wallet, `agentIdOf(wallet)`, dan nama error (`SoldOut`, `FreeGone`, …).

**Langkah 2, latihan** (selalu):

```bash
./fastmint.sh fire --to 0xSALE --data 0x195ad114 --start 23:00 --dry
```

Melakukan semua hal sampai preview lalu berhenti. Cek baris `call = …` mendekode ke fungsi dan argumen yang benar. Tambah `--gateSim` kalau call sudah bisa dimint sekarang, supaya latihan menunjukkan jalur bergerbang waktu yang sebenarnya.

**Langkah 3, tembak** (di background supaya chat tetap responsif):

```bash
./fastmint.sh fire --to 0xSALE --data 0x195ad114 --start 23:00 --label proyek_free
```

**Langkah 4, laporan**: tx hash, status, link BscScan, baris `TIMELINE` (offset T+ untuk trigger/preview/execute/broadcast/inklusi), apa yang diterima, dan path log. Kalau berhenti: nama revert yang didekode dan artinya.

---

## 4. Referensi perintah

### `./fastmint.sh`

| perintah | fungsi |
|---|---|
| `bench` | cek lingkungan, read-only |
| `bench --ca` | bangun `~/.config/certs/system-ca.pem` dari keychain macOS |
| `bench --live` | **mengirim 1 tx nyata** (USDT balanceOf, 0 BNB, gas ±0.00002 BNB) untuk mengukur execute. Hanya atas persetujuan eksplisit pengguna |
| `recon <url> [--contract 0x..] [--wallet 0x..] [--json]` | riset cepat, read-only |
| `fire …` | eksekusi (lihat di bawah) |
| `logs [n]` | tail log run terakhir |
| `locks` | daftar lock execute |

### `fire`

```
./fastmint.sh fire --to 0xC (--data 0x... | --sig "fn(type,..)" --args '[..]') [--start <t>] [opsi]
```

| opsi | default | arti |
|---|---|---|
| `--value <BNB>` | 0 | BNB yang dikirim, desimal. Mint berbayar wajib angka eksplisit dari pengguna |
| `--maxValue <BNB>` | | cap. Wajib kalau value > 0; ditolak kalau value > cap |
| `--start <t>` | sekarang | unix detik, `HH:MM[:SS]` WIB, atau ISO-8601 |
| `--lead <ms>` | 3000 | mulai spin sebelum start |
| `--interval <ms>` | 100 | jarak spin eth_call |
| `--clockFire <ms>` | 0 | kirim preview di start+ms menurut jam; `-1` mematikan |
| `--burst <ms>` | 3000 | jendela pemicu clock+head setelah start |
| `--gap <ms>` | 350 | jarak minimal antar preview |
| `--inflight <n>` | 3 | preview paralel maksimal |
| `--maxPreviews <n>` | 40 | menyerah setelah sekian preview gagal |
| `--timeout <s>` | 600 | terus coba revert "belum buka" selama ini |
| `--grace <s>` | 10 | revert Unknown dianggap wait sampai start+grace |
| `--once` | | satu preview, satu execute, tanpa retry |
| `--dry` | | berhenti sebelum execute (`--noPreview`: sebelum preview) |
| `--gateSim` | | latihan: abaikan eth_call OK sebelum start |
| `--expectNft <n>` | | execute hanya jika preview menunjukkan tepat n NFT dari `--to` masuk ke wallet |
| `--noEager` / `--noWs` | | matikan pemicu head / WebSocket |
| `--gasLimit <n>` | | diteruskan ke preview, hanya kalau pengguna minta |
| `--from 0x..` | wallet baw | alamat pengirim |
| `--abi 0x..` | `--to` | alamat lain yang ABI-nya dipakai untuk dekode error |
| `--waitOn` / `--fatalOn <regex>` | | override klasifikasi revert |
| `--label <nama>` | | nama file log/lock |

Contoh:

```bash
# free mint jam 23:00 WIB, calldata mentah
./fastmint.sh fire --to 0xSALE --data 0x195ad114 --start 23:00 --label feg_free

# signature + argumen statis
./fastmint.sh fire --to 0xSALE --sig "claimFreeShare()" --start 23:00

# argumen dinamis: Agent ID dan deadline dibaca ulang tiap preview
./fastmint.sh fire --to 0xSALE --sig "mintFree(uint256,uint256,uint256,uint256,address)" \
  --args '["$agentId","1","0","$now+1800","0x0000000000000000000000000000000000000000"]' --start 21:00

# argumen yang harus sama dengan counter saat buka
./fastmint.sh fire --to 0xSALE --sig "mint(uint256)" --args '[{"getter":"totalMinted()","add":1}]' --start 1794330000

# mint berbayar (pengguna bilang: 2 share @0.005 = 0.01 BNB)
./fastmint.sh fire --to 0xSALE --sig "buyWithBnb(uint256,address,uint256)" \
  --args '[2,"0x0000000000000000000000000000000000000000",0]' --value 0.01 --maxValue 0.01 --start 23:00

# mint yang sudah buka, pastikan dapat 2 NFT
./fastmint.sh fire --to 0xNFT --data 0xa0712d68…0002 --value 0 --expectNft 2
```

---

## 5. Argumen dinamis

Elemen di `--args` boleh berupa placeholder yang dievaluasi **tepat sebelum setiap preview**, jadi nilai yang berubah saat buka selalu segar:

| bentuk | nilai |
|---|---|
| `"$wallet"` | alamat wallet baw di chain 56 |
| `"$agentId"` | tokenId Agent ID = `uint256(keccak256(handle))`, dari registry `0x60B9…022F` `handleOf(wallet)` |
| `"$zero"` | `0x000…000` |
| `"$now+1800"` | unix sekarang + 1800 (deadline) |
| `{"getter":"totalMinted()","add":1}` | `eth_call` getter di `--to` (tag `pending`), hasil uint256 + 1 |
| `{"getter":"saleStart()","at":"0x..","mul":2}` | getter di kontrak lain, dikali 2 |

Lock file untuk call dengan argumen dinamis memakai `to|selector|value`, jadi mint yang sama tetap terkunci walau argumennya berubah.

---

## 6. Rel pengaman

Ini yang membuat agent aman dijalankan tanpa pengawasan ketat. Tidak ada yang boleh dilewati.

1. **Tembak hanya atas perintah eksplisit pengguna** untuk mint ini ("mint free jam 23:00", "gas", "ok"). Link saja bukan perintah.
2. **Free mint = `--value 0`.** Mint berbayar butuh jumlah yang disebut pengguna, dipasang sebagai `--value` dan `--maxValue`. Ditolak kalau value > cap atau value > 0 tanpa cap.
3. **Satu broadcast.** `runs/lock_<hash>.json` ditulis sebelum execute; call yang sama ditolak selamanya. Tidak pernah retry setelah execute, walau execute error atau tx revert. Lock dihapus hanya atas perintah baru yang eksplisit.
4. **Tidak pernah `baw auth signin` otomatis.** Status bukan CONNECTED → berhenti dan tanya pengguna. Tidak pernah minta private key, seed phrase, atau session token.
5. **Tidak menembus blokir risiko Binance** (`351803`), flag `RISK`, atau perubahan allowance/authority di preview. Berhenti dan laporkan.
6. **Hanya wallet yang terhubung.** Cek saldo ≥ value + gas sebelum mulai.
7. **Preview wajib lolos**: `simulationCode 000000000`, tanpa allowance/authority change, tanpa RISK, outflow native ≤ cap + 0.003 BNB, `parsedTx.amount` = 0 untuk call value 0, `requestId` ada, dan `--expectNft` kalau dipasang.
8. **`PENDING_CONFIRMATION`** → pengguna menyetujui di app, tidak dikirim ulang.
9. **Kunci RPC premium** tidak pernah tercetak: semua log hanya memuat host.

---

## 7. Angka terukur

Semua dari satu mesin di Indonesia, 11 Nov 2026, via DNS terenkripsi.

**Komponen**

| komponen | nilai |
|---|---|
| `baw wallet status` (cold start CLI) | 0.3–0.4s |
| `baw contract-call preview` | 0.45–0.8s (requestId berlaku 300s) |
| `baw contract-call execute` → BROADCASTED | 0.68–0.71s |
| broadcast → receipt | 0.54–0.77s |
| blok BSC | ±0.5s |
| RPC tercepat (QuikNode / bloXroute / 48.club) | 31 / 32 / 45 ms |
| WS newHeads delay (QuikNode / publicnode) | median 0.45s / 0.56s, tercepat 0.03s |
| offset jam lokal vs NTP | +0.1–0.16s (dikoreksi otomatis) |

**Mint nyata, sudah buka** (Pocket Moons `mint(2)`, gratis, 2 NFT): eth_call OK +35ms → preview 564ms → execute 683ms → BROADCASTED +1.2s → receipt +0.77s. **Total 2.0s.**

**Dry-run bergerbang waktu, 3 run** (`--gateSim`):

| run | clock | eth_call OK | head | preview OK |
|---|---|---|---|---|
| 1 | T+0.054s | T+0.087s | T+0.503s | T+0.761s |
| 2 | T+0.049s | T+0.084s | T+0.168s | T+0.619s |
| 3 | T+0.049s | T+0.083s | T+0.250s | T+0.736s |

**Proyeksi FCFS**: broadcast ≈ **T+1.3–1.5s**, masuk blok ≈ **T+2.1–2.2s**. Kalau node Binance baru melihat blok pembuka pada preview kedua, tambah ±0.4s → T+2.6s. Versi lama: T+5–6s.

---

## 8. Troubleshooting

| gejala | arti | tindakan |
|---|---|---|
| `baw wallet status` = `UNCONNECTED` | sesi habis (2 hari idle) | pengguna sign-in ulang; agent tidak boleh otomatis |
| `351802` / `351804` | Developer Mode mati / kedaluwarsa / saldo melebihi cap | nyalakan di Binance App, lalu ulang |
| `351803` `AGENT_DEV_MODE_RISK_BLOCKED` | Binance memblokir kontrak | berhenti, tunjukkan teks risiko, jangan dibypass |
| `351805` `simulation failed` terus-menerus | mint belum buka di node Binance, atau argumen salah | normal sebelum jam buka; kalau eth_call sudah OK lama, cek JSON preview di `runs/` |
| `NotStarted` selamanya | jam buka salah | bandingkan getter kontrak vs situs; `--timeout` cukup? |
| `SoldOut` / `FreeGone` | habis | terminal; jangan pindah ke mint berbayar tanpa "ok paid" + jumlah |
| `AgentIdRequired` / `NotEligible` | wallet tanpa Agent ID, atau butuh arg id | pakai `"$agentId"` |
| `AlreadyClaimed` / `AlreadyTaken` | sudah pernah | selesai |
| `PaymentLow` / `WrongValue` | value ≠ harga × qty | baca getter harga, konfirmasi jumlah ke pengguna |
| `PENDING_CONFIRMATION` | tx dianggap abnormal | pengguna setujui di app; jangan kirim ulang |
| execute error / receipt tidak ada | | **jangan retry**; `baw wallet tx-history --json`, `baw wallet tx-lock --json` |
| `gave up after N previews` | backend terus gagal padahal eth_call OK | state node Binance beda dengan RPC publik, atau arg salah |
| `UNABLE_TO_GET_ISSUER_CERT_LOCALLY` (Node) | CA store Node tidak kenal rantai sertifikat | macOS: `./fastmint.sh bench --ca`; lainnya: `NODE_EXTRA_CA_CERTS=/path/ca.pem` |
| `SSL_ERROR … altnames: internetbaik.telkomsel.com` / DNS jawab `internetpositif.id` | ISP membajak DNS binance.com (query ke 1.1.1.1 pun dibajak) | pakai DNS terenkripsi (app Cloudflare 1.1.1.1 mode DNS-only) atau VPN. Jangan ubah DNS sistem dari agent |
| RPC lambat / rate-limited | | `FASTMINT_RPCS=…` atau `FASTMINT_RPCS_EXTRA=…` di `.env` |
| `lock exists` | call ini sudah pernah di-execute | hapus `runs/lock_*.json` hanya atas perintah baru pengguna |

---

## 9. Struktur file

```
fastmint-fcfs/
├── SKILL.md            instruksi untuk agent (dibaca otomatis)
├── README.md           dokumen ini (English, default di GitHub)
├── README.id.md        versi Bahasa Indonesia
├── fastmint.sh         launcher: bench | recon | fire | logs | locks; memuat .env dan CA
├── fire.js             mesin FCFS: precheck → tunggu → 3 pemicu → preview → 1x execute → receipt
├── recon.js            riset cepat: situs + Sourcify + getter + kandidat mint + calldata
├── bench.js            cek lingkungan; --ca bangun bundel CA; --live 1 tx uji (atas izin)
├── lib.js              RPC pool & race, WS heads, NTP, dekode revert, runner baw, Agent ID, cache ABI
├── ethers.umd.min.js   ethers 6.13.4 (bundel, tanpa npm install)
├── .env                RPC premium (FASTMINT_RPCS_EXTRA / FASTMINT_WS_EXTRA)
├── .gitignore
├── cache/              ABI Sourcify yang sudah diunduh
└── runs/               log per run, JSON preview/exec/receipt, lock_*.json
```

Log: `runs/<stamp>_<label>.log`, waktu WIB plus offset `T+x.xxxs`. Baris terakhir setiap run adalah `TIMELINE`.

---

## 10. FAQ

**Kenapa bukan kirim transaksi langsung dengan private key? Lebih cepat.**
Benar, bisa <1 detik. Tapi skill ini dibuat untuk Binance Agentic Wallet: tidak ada private key di mesin, ada limit harian, blokir risiko, dan approval di app untuk tx abnormal. Dua langkah preview/execute adalah harga dari keamanan itu, dan 2 detik masih jauh di bawah 5 detik.

**Apakah preview bisa dilakukan sebelum jam buka supaya tinggal execute?**
Tidak. Backend mensimulasikan saat preview; sebelum buka simulasinya gagal (`351805`) dan tidak ada `requestId`. Itulah kenapa pemicu jam mengirim preview tepat di T+0, bukan sebelumnya.

**Bagaimana kalau tim telat membuka?**
Setelah burst 3 detik, spin `eth_call` terus memantau sampai 600 detik. Begitu satu RPC melaporkan sukses, preview dikirim.

**Kenapa ada `--gateSim`?**
Hanya alat latihan. Saat berlatih dengan call yang sudah bisa dimint, `eth_call` sukses sebelum jam buka dan fire.js langsung menembak (benar untuk kasus nyata, tapi tidak mencerminkan jalur bergerbang waktu). `--gateSim` mengabaikan sukses sebelum start.

**Apakah aman dijalankan dua kali tanpa sengaja?**
Lock file menolak call yang sama. Run kedua berhenti di detik pertama dengan pesan `lock exists`.

**Bisa dipakai di chain selain BSC?**
Belum. `CHAIN_ID`, pool RPC, registry Agent ID, dan explorer di `lib.js` masih BSC.
