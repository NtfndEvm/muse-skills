# muse-skills

Kumpulan skill yang dipakai Muse untuk membantu user: riset dan farming
airdrop/testnet/free-mint, serta scalping spot di Bitget.

Setiap skill berisi `SKILL.md` (playbook) dan `skill.yaml` (metadata).
Skill tidak mengeksekusi transaksi apa pun — user yang mengeksekusi sendiri,
dan semua aturan keamanan on-chain berlaku.

## Isi repo

| Kelompok | Skill |
|---|---|
| Farming & airdrop | `airdrop-hunter`, `airdrop-tracker`, `airdrop-calendar-aggregator`, `airdrop-retro-analyzer`, `x-monitor`, `onchain-contract-scanner`, `free-mint-farming-agent`, `fastmint-fcfs` |
| Riset proyek | `project-due-diligence`, `social-signal-scanner`, `contract-checker`, `token-liquidity-checker`, `wallet-eligibility-checker` |
| Trading spot | `scalp-setup-scanner`, `trade-planner-spot`, `risk-manager-spot`, `trade-journal`, `trade-review`, `multi-token-screener` |
| Biaya & pajak | `gas-optimizer`, `crypto-tax-log` |
| Keamanan | `on-chain-safety-rails`, `wallet-hygiene` |

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

## Aturan yang selalu berlaku

`on-chain-safety-rails` selalu aktif dan mengalahkan instruksi lain yang
bertentangan: tidak pernah meminta/menangani seed atau private key,
simulasi sebelum broadcast, konfirmasi sebelum signing, dan mainnet hanya
dengan persetujuan eksplisit user.
