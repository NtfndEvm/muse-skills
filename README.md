# muse-skills

Kumpulan skill yang dipakai Muse untuk membantu user: riset dan farming
airdrop, testnet, dan free-mint, serta trading spot dengan pendekatan
yang disiplin dan terukur.

Setiap skill berisi `SKILL.md` (playbook) dan `skill.yaml` (metadata).
Kecuali `fastmint-fcfs`, skill tidak mengeksekusi transaksi. `fastmint-fcfs` hanya broadcast atas perintah eksplisit user per mint, dan tetap tunduk pada `on-chain-safety-rails`.

## Isi repo

| Kelompok | Skill |
|---|---|
| Farming & airdrop | `airdrop-hunter`, `airdrop-tracker`, `airdrop-calendar-aggregator`, `airdrop-retro-analyzer`, `x-monitor`, `onchain-contract-scanner`, `free-mint-farming-agent`, `fastmint-fcfs` |
| Riset proyek | `project-due-diligence`, `social-signal-scanner`, `contract-checker`, `token-liquidity-checker`, `wallet-eligibility-checker` |
| Trading spot | `scalp-setup-scanner`, `trade-planner-spot`, `risk-manager-spot`, `trade-journal`, `trade-review`, `multi-token-screener`, `entry-assistant`, `candle-reader-15m`, `live-confirm` |
| Kalender & risiko | `unlock-catalyst-calendar` |
| Biaya & pajak | `gas-optimizer`, `crypto-tax-log` |
| Keamanan | `on-chain-safety-rails`, `wallet-hygiene` |
| Gaya bahasa | `natural-bahasa` |

## Cara repo ini diperbarui

Repo ini diperbarui setiap kali Muse mengevaluasi kesalahan atau mengasah
skill:

- Skill yang berubah → file skill-nya diperbarui di `skills/<nama-skill>/`.
- Kesalahan dan perbaikan → dicatat di [`evaluasi-diri.md`](evaluasi-diri.md).
- Skill turunan baru (mis. `multi-token-screener`, yang dibangun dari
  `scalp-setup-scanner` + `trade-planner-spot` + `risk-manager-spot` +
  `trade-review`) → ditambahkan sebagai folder baru.

## Yang TIDAK ada di repo ini

- Jurnal trade aktual (`trade-journal.md` dengan entry/stop/target dan hasil
  trade), memori user, dan data pribadi lainnya — itu tetap lokal.
- Tidak ada seed phrase, private key, API key, atau kredensial apa pun.

## Cara menjalankan tes

Tes Python di keenam folder `scripts/` memakai stdlib, tanpa dependensi
lain kecuali pytest untuk cara kedua.

Dengan unittest, dari tiap folder `scripts/`:

```bash
cd skills/trade-journal/scripts && python3 -m unittest discover -q
cd skills/candle-reader-15m/scripts && python3 -m unittest discover -q
cd skills/live-confirm/scripts && python3 -m unittest discover -q
cd skills/multi-token-screener/scripts && python3 -m unittest discover -q
cd skills/entry-assistant/scripts && python3 -m unittest discover -q
cd skills/airdrop-tracker/scripts && python3 -m unittest discover -q
```

Dengan pytest, dari tiap folder `scripts/` (pasang dulu bila belum ada:
`pip install pytest`):

```bash
cd skills/trade-journal/scripts && python3 -m pytest -q
cd skills/candle-reader-15m/scripts && python3 -m pytest -q
cd skills/live-confirm/scripts && python3 -m pytest -q
cd skills/multi-token-screener/scripts && python3 -m pytest -q
cd skills/entry-assistant/scripts && python3 -m pytest -q
cd skills/airdrop-tracker/scripts && python3 -m pytest -q
```

Validasi struktur repo (front matter, nama skill, tabel README, tanpa
path pribadi/pola kunci) dari root repo:

```bash
python3 validate_skills.py
```

CI (`.github/workflows/test.yml`) menjalankan pytest di keenam folder itu,
tes JS fastmint, dan `validate_skills.py` pada setiap push dan pull request.

Tes JS fastmint (dari folder `skills/fastmint-fcfs`):

```bash
node --test test/fastmint.test.js
```

Catatan: `node --test test/` gagal di Node 24 (MODULE_NOT_FOUND) — selalu
sebut nama berkas tesnya.

## Artefak pihak ketiga

`skills/fastmint-fcfs/ethers.umd.min.js` (ethers 6.13.4, MIT) — SHA-256:

```
fd66c04651929c6a37806a37e8217e6b6aac07c7e816ad478f52690b7429bc61
```

Pisahan lisensi kode pihak ketiga ada di `skills/fastmint-fcfs/NOTICE` dan
`skills/free-mint-farming-agent/NOTICE`. Kode upstream fastmint dan
playbook free-mint tidak berlisensi (bukan MIT) — lihat NOTICE.

## Aturan yang selalu berlaku

`on-chain-safety-rails` selalu aktif dan mengalahkan instruksi lain yang
bertentangan: tidak pernah meminta/menangani seed atau private key,
simulasi sebelum broadcast, konfirmasi sebelum signing, dan mainnet hanya
dengan persetujuan eksplisit user.
