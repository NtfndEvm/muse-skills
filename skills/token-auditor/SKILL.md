---
name: token-auditor
description: Fast EVM token security audit — rug pull detection for ERC20/Solidity token contracts: hidden mint, honeypot, fee manipulation, LP drain, bonding curve, fake renounce, sandwich/MEV amplification, plus a deterministic regex scanner (scripts/token_scanner.py, stdlib only, no network). Use when checking whether a token contract is safe to interact with, before a mint/claim, or for a pre-investment rug check.
---

# TOKEN AUDITOR (EVM)

Audit cepat token ERC20/Solidity buat cari vektor rug pull: hidden mint,
honeypot, manipulasi fee, LP drain, otoritas yang dipertahankan, fake renounce,
dan amplifikasi MEV. Bukan audit protokol DeFi penuh — buat bug level protokol
(flash loan, oracle, accounting desync), pakai skill `web3-audit`.

Sumber: diadaptasi dari `bughunter/agents/token-auditor.md` dan
`skills/meme-coin-audit/SKILL.md` di awarexone/Agentic-Bug-Hunter
(commit 82f4512, lisensi MIT). **Hanya bagian EVM yang diambil** — bagian
Solana dihapus (di luar lane kita). Scanner `scripts/token_scanner.py` sudah
diverifikasi penuh (baca 816 baris sumber): regex + stdlib saja, tanpa network,
tanpa subprocess, tanpa eval; file yang diadaptasi ini EVM-only.

## Step 0: Pre-Scan Quick Kill

Sebelum baca satu baris kode pun, jawab ini:

```
1. Apakah kontrak terverifikasi (source code tersedia)?
   → TIDAK: STOP. Tidak bisa audit kontrak yang belum terverifikasi.
     Laporan: "Unverified — do not interact."

2. Apakah kontrak proxy/upgradeable?
   → YA: Siapa yang mengontrol upgrade? Bisakah mereka tambah mint/blacklist?

3. Apakah ownership sudah di-renounce?
   → Cek: owner() mengembalikan address(0)?
   → Kalau ya, cek fake renounce (pola override).
```

Kill langsung kalau:
- Kontrak belum terverifikasi
- Deployer punya 3+ riwayat rug pull sebelumnya (cek halaman deployer di Etherscan)
- Umur token < 30 menit DAN tidak ada tim yang dikenal

### Pre-dive kill signals (tambahan)

Hard kill (skip langsung):
- Top holder > 20% dari supply (tidak termasuk DEX pool)
- LP tidak di-burn atau dikunci di kontrak terverifikasi
- Kontrak upgradeable/proxy dengan admin yang masih dipertahankan
- Likuiditas pool < $5K

## Audit Protocol

### Class 1: Hidden Mint (CRITICAL)
```bash
grep -rn "function mint\|_mint(" src/ --include="*.sol" | grep -v "test\|lib\|node_modules"
grep -rn "_balances\[.*\] +=" src/ --include="*.sol" | grep -v "test\|_transfer\|_mint"
grep -rn "_totalSupply +=" src/ --include="*.sol" | grep -v "_mint\|test"
grep -rn "delegatecall" src/ --include="*.sol"
```
**Cek:** Apakah ada cap MAX_SUPPLY? Apakah ditegakkan di SETIAP jalur mint?
**Kill kalau:** MAX_SUPPLY immutable dan ditegakkan di mana-mana.

### Class 2: Honeypot / Transfer Restriction (CRITICAL)
```bash
grep -rn "blacklist\|isBlacklisted\|_bots\|isBot\|_blocked" src/ --include="*.sol"
grep -rn "maxTxAmount\|maxWallet\|setMaxTx\|setMaxWallet" src/ --include="*.sol"
grep -rn "function approve.*override" src/ --include="*.sol"
grep -rn "tradingEnabled\|tradingActive\|enableTrading" src/ --include="*.sol"
grep -rn "cooldown\[" src/ --include="*.sol"
```
**Cek:** Bisakah owner memblokir penjualan? Bisakah alamat mana pun dicegah transfer?
**Kill kalau:** Tidak ada blacklist, tidak ada freeze, tidak ada transfer hook, maxTx punya batas minimum.

### Class 3: Fee Manipulation (HIGH-CRITICAL)
```bash
grep -rn "setFee\|setSellFee\|setBuyFee\|setTax\|updateFee" src/ --include="*.sol"
grep -rn "function set.*Fee" -A5 src/ --include="*.sol" | grep -v "require\|MAX\|<="
grep -rn "_isExcludedFromFee\|excludeFromFee" src/ --include="*.sol"
grep -rn "setMarketingWallet\|setDevWallet\|setFeeReceiver" src/ --include="*.sol"
```
**Cek:** Apakah fee dibatasi? Bisakah melebihi 10%? Apakah owner dikecualikan dari fee?
**Kill kalau:** Fee dibatasi MAX_FEE <= 10% di require statement.

### Class 4: LP Drain (CRITICAL)
```bash
grep -rn "migrateLP\|migrateLiquidity\|function migrate" src/ --include="*.sol"
grep -rn "emergencyWithdraw\|forceWithdraw\|rescueTokens" src/ --include="*.sol"
grep -rn "\.sync()" src/ --include="*.sol"
grep -rn "setPair\|setRouter\|updatePair\|changeRouter" src/ --include="*.sol"

# Cek tujuan token LP di panggilan addLiquidity
grep -rn "addLiquidityETH\|addLiquidity" -A5 src/ --include="*.sol" | grep "owner\|msg.sender"
```
**Cek:** Bisakah owner menghapus LP? Bisakah pair/router diubah? Ke mana token auto-LP pergi?
**Kill kalau:** LP di-burn ke 0xdead, tidak ada migrasi, pair/router immutable.

### Class 5: Bonding Curve Manipulation (HIGH)
```bash
grep -rn "virtualReserve\|virtual_reserve\|setCurve\|setExponent" src/ --include="*.sol"
grep -rn "graduate\|migration\|createPool" src/ --include="*.sol"
```
**Cek:** Bisakah parameter kurva diubah setelah pembuatan? Apakah graduasi permissionless?
**Kill kalau:** Semua parameter kurva immutable, graduasi permissionless.

### Class 6: Fake Renounce (CRITICAL)
```bash
grep -rn "renounceOwnership.*override" src/ --include="*.sol"
grep -rn "_shadowAdmin\|_secondOwner\|_backupOwner\|_manager" src/ --include="*.sol"
grep -rn "constructor" -A10 src/ --include="*.sol" | grep "_approve\|type(uint256).max"
grep -rn "selfdestruct\|CREATE2" src/ --include="*.sol"
```
**Cek:** Apakah renounceOwnership benar-benar membersihkan owner? Apakah ada peran admin sekunder?
**Kill kalau:** Pakai renounce default OpenZeppelin, tidak ada shadow admin, tidak ada selfdestruct.

### Class 7: Sandwich Amplification (HIGH)
```bash
grep -rn "swapExactTokensForETH" -A5 src/ --include="*.sol" | grep "0,"
grep -rn "swapThreshold\|numTokensSellToAddToLiquidity" src/ --include="*.sol"
grep -rn "_rebase\|rebase()\|_reflect\|reflect()" src/ --include="*.sol"
```
**Cek:** Apakah auto-swap punya proteksi slippage? Apakah threshold publik dan bisa diprediksi?
**Kill kalau:** Slippage wajar (bukan 0), tidak ada mekanisme rebase.

## THE ONE RULE

> "Cek SEMUA otoritas dan fungsi owner. Otoritas yang dipertahankan ITULAH
> vektor rug-nya."
>
> Setiap rug pull butuh operasi istimewa: mint, blacklist, ubah fee, hapus LP,
> atau penyalahgunaan otoritas. Kalau kamu menemukan hak istimewanya, kamu
> menemukan bug-nya.

## Automated Scan

Setelah review grep manual, jalankan scanner otomatis:

```bash
# Satu file kontrak
python3 scripts/token_scanner.py <contract_path>

# Satu direktori (rekursif)
python3 scripts/token_scanner.py <contract_dir> --recursive

# Output JSON (buat mesin)
python3 scripts/token_scanner.py <contract_path> --json

# Laporan markdown
python3 scripts/token_scanner.py <contract_path> --output findings/token-scan.md
```

Scanner: regex deterministik, stdlib saja, tanpa network. Exit code 1 kalau ada
temuan CRITICAL/HIGH, 0 kalau tidak. Keterbatasan: tidak menganalisis bytecode
(source saja), tidak mengecek state on-chain (otoritas, LP lock, distribusi
holder) — itu dicek manual atau pakai skill `token-liquidity-checker`.

## Reporting Format

```
TOKEN AUDIT REPORT
══════════════════

Token:      <name> (<symbol>)
Chain:      EVM
Contract:   <address or file path>
Audit Date: <date>

RISK SCORE: <0-100> / <VERDICT>

FINDINGS:

[CRITICAL] #1: <title>
  Category:   <bug class>
  Location:   <file:line>
  Impact:     <what can the attacker do>
  Evidence:   <code snippet or grep output>
  Recommendation: <fix>

[HIGH] #2: ...

SAFE PATTERNS CONFIRMED:
  [✓] <pattern> — verified at <location>

CONCLUSION:
  <1-2 sentence summary: safe to interact or not>
```

## Decision Output

```
CONFIDENCE: HIGH | MEDIUM | LOW
FINDINGS:   N critical, N high, N medium, N low
VERDICT:    SAFE | CAUTION | DO NOT INTERACT
REASONING:  <1-2 sentences>
NEXT:       <recommended action>
```

## Kill if:
- Kontrak belum terverifikasi — laporkan "unverified, do not interact" langsung
- Semua kelas dicek bersih — laporkan "no rug vectors found" dan lanjut
- Temuan ambigu — flag sebagai MEDIUM, jangan naikkan ke CRITICAL tanpa bukti
