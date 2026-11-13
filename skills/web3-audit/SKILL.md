---
name: web3-audit
description: Smart contract security audit for EVM/Solidity DeFi — 10 bug classes with real paid examples and grep patterns (accounting desync, access control, incomplete path, off-by-one, oracle, ERC4626, reentrancy, flash loan, signature replay, proxy), pre-dive kill signals, and a Foundry PoC template. Use when auditing a Solidity target or generating hypotheses for a bug bounty.
---

# WEB3 SMART CONTRACT AUDIT

10 bug classes. Pre-dive kill signals. Foundry PoC template. Real paid examples.

Sumber: diadaptasi dari `skills/web3-audit` di awarexone/Agentic-Bug-Hunter
(commit 82f4512, lisensi MIT). Disesuaikan buat workflow kita: audit kontrak
Solidity EVM buat program Immunefi/Cantina, dipakai di Fase 3 (hipotesis) —
pasangan dari `target-criteria.md`. Angka persen di bawah ini klaim penulis
sumber tanpa referensi yang bisa dicek; pakai sebagai prioritas checklist,
bukan dalil.

## PRE-DIVE KILL SIGNALS (cek SEBELUM baca kode)

1. **TVL < $500K** → payout maksimal terlalu kecil buat effort-nya
2. **2+ audit top-tier** (Halborn, ToB, Cyfrin, OpenZeppelin) di protokol sederhana → bug sudah ketemu
3. **Protokol < 500 baris, alur tunggal A→B→C** → attack surface minimal
4. **Rumus**: `max_realistic_payout = min(10% × TVL, program_cap)` — kalau < $10K, skip

**Soft kill:** audit OZ/ToB/Cyfrin di versi sekarang + codebase > 500K LOC →
perkirakan 40+ jam buat mungkin 1 temuan. Lanjut hanya kalau bounty floor >
$50K DAN kamu punya keahlian spesifik di protokol itu.

**Target scoring (lanjut kalau >= 6/10):**
- TVL > $10M: +2
- Program Immunefi dengan Critical >= $50K: +2
- Belum ada audit top-tier di versi sekarang: +2
- < 30 hari sejak deploy: +1
- Protokol yang pernah diburu sebelumnya: +1
- Source code + komentar natspec: +1
- Proxy yang bisa di-upgrade: +1

## THE ONE RULE

> "Baca SEMUA sibling function. Kalau `vote()` punya modifier, cek `poke()`,
> `reset()`, `harvest()`. Modifier yang hilang di sibling ITULAH bug-nya."

## 1. ACCOUNTING STATE DESYNCHRONIZATION
> Kelas bug Critical #1 menurut sumber — 28% dari semua Critical di Immunefi.

Dua state variable yang harusnya selalu sinkron. Satu jalur kode update A tapi
lupa B. Kode lain baca keduanya dan bikin keputusan dari B yang basi.

```
Real Value = A - B
Kalau A di-update tapi B tidak → Real Value kelihatan lebih besar → phantom value
```

**Varian 1: Phantom Yield** (Yeet — 35 laporan duplikat)
```solidity
function startUnstake(uint256 amount) external {
    totalSupply -= amount;  // dikurangi SEBELUM transfer
    // aToken.balanceOf(this) masih mencerminkan nilai lama
    // yieldAmount = aToken.balanceOf - totalSupply = phantom yield
}
```

**Varian 2: Fast Path melewatkan update state** (Alchemix V3)
```solidity
function claimRedemption(uint256 tokenId) external {
    if (transmuter.balance >= amount) {
        transmuter.transfer(user, amount);
        _burn(tokenId);
        return;  // EARLY RETURN — cumulativeEarmarked, _redemptionWeight, totalDebt tidak pernah di-update
    }
    // Slow path: update semua state var dengan benar
    alchemist.redeem(...);
}
```

**Varian 3: Update terjadi dalam urutan yang salah** (Alchemix)
```solidity
function deposit(uint256 amount) external {
    _shares = (amount * totalShares) / totalAssets;  // dihitung SEBELUM deposit
    totalAssets += amount;   // aset ditambah SETELAH shares dihitung → rate salah
}
```

### Grep Patterns
```bash
# Cari semua accounting variable
grep -rn "totalSupply\|totalShares\|totalAssets\|totalDebt\|cumulativeReward\|rewardPerShare" contracts/

# Cari semua early return di fungsi claim/redeem
grep -rn "\breturn\b" contracts/ -B3 | grep -B3 "if\b"

# Untuk tiap early return: update state apa di jalur normal yang dilewati?
```

## 2. ACCESS CONTROL
> Critical #2 menurut sumber — 19% dari semua Critical. $953M hilang di 2024 saja.

### Varian 1: Modifier hilang di sibling function
```solidity
function vote(uint256 tokenId) external onlyNewEpoch(tokenId) {  // dijaga
function reset(uint256 tokenId) external onlyNewEpoch(tokenId) { // dijaga
function poke(uint256 tokenId) external {                         // TANPA GUARD → inflasi FLUX tak terbatas
}
```

### Varian 2: Cek yang salah (eksistensi vs kepemilikan)
```solidity
function split(uint256 tokenId, uint256 amount) external {
    _requireOwned(tokenId);  // cek token ADA, bukan caller yang PUNYA
    _burn(tokenId);
    _mint(msg.sender, amount);  // attacker curi token yang bukan miliknya
}
```

### Varian 3: Modifier diam-diam (if vs require)
```solidity
// RENTAN — non-admin lolos diam-diam:
modifier onlyAdmin() {
    if (msg.sender == admin) {
        _;  // body cuma jalan buat admin, tapi non-admin tidak revert
    }
}
// BENAR: require(msg.sender == admin, "Not admin"); _;
```

### Varian 4: Proxy belum di-initialize
```solidity
function initialize(address _owner) public {  // HILANG: modifier initializer
    owner = _owner;  // siapa pun bisa panggil → jadi owner
}
// Fix: constructor() { _disableInitializers(); }
```

### Grep Patterns
```bash
# Cari keluarga sibling function — apakah SEMUA punya set modifier yang sama?
grep -rn "function vote\|function poke\|function reset\|function update\|function claim\|function harvest" contracts/ -A2

# Cek kepemilikan: eksistensi vs kepemilikan?
grep -rn "_requireOwned\|ownerOf\|_isApprovedOrOwner\|_checkAuthorized" contracts/ -B5

# Modifier diam-diam
grep -rn "modifier\b" contracts/ -A8 | grep -B3 "if (" | grep -v "require\|revert"

# Initializer yang belum diamankan
grep -rn "function initialize\b" contracts/ -A3
grep -rn "_disableInitializers()" contracts/
```

### Contoh berbayar beneran

| Protokol | Payout | Bug |
|---|---|---|
| Wormhole | $10M | Proxy UUPS belum di-initialize → siapa pun bisa panggil initialize() |
| ZeroLend | n/a | split() pakai cek eksistensi, bukan kepemilikan |
| Alchemix | n/a | poke() hilang onlyNewEpoch → inflasi FLUX tak terbatas |
| Parity | $150M frozen | Tidak ada access control di initWallet() library |

## 3. INCOMPLETE CODE PATH
> Critical #3 menurut sumber — 17% dari semua Critical.

### Function Family Comparison Test
```
1. List semua perubahan state di fungsi A (deposit/place/create)
2. List semua perubahan state di fungsi B (withdraw/update/cancel)
3. Untuk tiap perubahan state di A: apakah B punya kebalikannya?
4. Untuk tiap transfer token di A: apakah B punya refund-nya?
Kalau A melakukan X tapi B tidak melakukan kebalikan X → BUG.
```

### Varian 1: Fungsi update kehilangan refund (ThunderNFT)
```solidity
function place_order(OrderInput calldata order) external {
    token.safeTransferFrom(msg.sender, address(this), order.price);  // ambil token
    orders[orderId] = order;
}
function update_order(OrderInput calldata updatedOrder) external {
    // BUG: TIDAK ADA REFUND buat sell order saat harga turun → token nyangkut permanen
    orders[orderId] = updatedOrder;
}
```

### Varian 2: Partial fill, token nyangkut (Plume)
```solidity
function swapForETH(uint256 amountIn) external {
    token.safeTransferFrom(msg.sender, address(this), amountIn);
    uint256 filled = dex.swap(amountIn);  // partial fill mungkin terjadi
    _refundExcessEth(amountIn - filled);  // BUG: refund ETH saja, bukan ERC20
}
```

### Varian 3: mint() melewati cek yang dimiliki deposit() (MetaPool)
```solidity
function deposit(uint256 assets, address receiver) public override {
    shares = _deposit(assets, receiver);  // termasuk validasi receipt
}
function mint(uint256 shares, address receiver) public override {
    assets = convertToAssets(shares);
    _mint(receiver, shares);  // HILANG: validasi _deposit() → mint tanpa menerima aset
}
```

### Grep Patterns
```bash
grep -rn "function place_\|function create_\|function add_\|function open_" contracts/ -A5
grep -rn "function update_\|function modify_\|function cancel_" contracts/ -A5
grep -rn "safeApprove\b" contracts/    # safeApprove tanpa zero-reset sebelumnya
grep -rn "delete\b" contracts/ -B5 -A5  # delete sebelum operasi selesai
grep -rn "function deposit\|function mint\|function withdraw\|function redeem" contracts/ -A10
```

## 4. OFF-BY-ONE & BOUNDARY CONDITIONS
> High #4 menurut sumber — 22% dari semua High. Satu karakter berubah. Dampak besar.

### Akar masalah
```solidity
// VeChain Stargate — post-exit reward drain:
function _claimableDelegationPeriods(address delegator) internal view returns (uint256) {
    if (endPeriod > nextClaimablePeriod) {  // BUG: harusnya >=
        return 0;  // user yang sudah exit dapat 0
    }
    return nextClaimablePeriod - lastClaimedPeriod;  // reward untuk periode SETELAH exit
}
```

### Tes mental buat tiap perbandingan
> Untuk tiap `if (A > B)`: "Apa yang terjadi saat A == B?" Apakah itu benar?

### 6 lokasi boundary yang harus dicek
1. Batas periode/epoch: `>` vs `>=` di akhir periode
2. Lock berbasis waktu: apakah `block.timestamp == deadline` mengunci atau membuka?
3. Kondisi break di loop: `break` dengan `>` vs `>=`
4. Batas indeks array: `i <= array.length` (harusnya `i < array.length`)
5. Batas jumlah/saldo: `>= amount` mengizinkan penarikan penuh persis?
6. Rounding/presisi: bisakah input menghasilkan output 0 yang harusnya bukan 0?

### Grep Patterns
```bash
# Boundary di perbandingan
grep -rn "Period\|Epoch\|Round\|Deadline\|period\|epoch\|deadline" contracts/ -A3 | grep "[<>][^=]"

# Loop break
grep -rn "\bbreak\b" contracts/ -B10

# Off-by-one di akses array
grep -rn "\.length\s*-\s*1\|i\s*<=\s*.*\.length\b" contracts/
```

## 5. ORACLE / PRICE MANIPULATION
> 12% dari semua laporan menurut sumber. Payout individu terbesar. $117M Mango, $70M Curve.

### Bug A: Tidak ada cek staleness (paling umum)
```solidity
// RENTAN:
(, int256 price,,,) = priceFeed.latestRoundData();
return uint256(price);  // Kalau node Chainlink mati, harga basi dikembalikan selamanya

// BENAR:
(, int256 price,, uint256 updatedAt,) = priceFeed.latestRoundData();
require(block.timestamp - updatedAt <= MAX_PRICE_AGE, "Stale price");
require(price > 0, "Invalid price");
```

### Bug B: Tidak ada confidence interval (Pyth)
```solidity
// RENTAN:
PythStructs.Price memory p = pyth.getPriceUnsafe(priceFeed);
return p.price;  // mengabaikan p.conf (confidence interval)

// BENAR:
require(p.conf * 10 <= uint64(p.price), "Price too uncertain");
// conf > 10% dari harga = tidak bisa dipercaya
```

### Bug C: TWAP terlalu pendek (bisa dimanipulasi flash loan)
```solidity
// RENTAN: TWAP 60 detik
uint32[] memory secondsAgos = new uint32[](2);
secondsAgos[0] = 60; secondsAgos[1] = 0;
// Flash loan bisa geser harga selama seluruh window 60 detik

// BENAR: TWAP minimum 1800 detik (30 menit)
```

### Bug D: Oracle sumber tunggal
```solidity
// RENTAN: hanya harga spot Uniswap
uint price = getUniswapSpotPrice(token);  // bisa dimanipulasi flash loan

// BENAR: Chainlink utama, TWAP Uniswap sebagai fallback, wajib sepakat berdekatan
```

### Grep Patterns
```bash
# Cek staleness hilang
grep -rn "latestRoundData" contracts/ -A5 | grep -v "updatedAt\|timestamp"

# Pemakaian harga Pyth — confidence interval dicek?
grep -rn "getPriceUnsafe\|getPrice\b" contracts/ -A8 | grep -v "conf\|confidence"

# Window TWAP — flag TWAP pendek
grep -rn "secondsAgo\|TWAP\|cardinality" contracts/ -A5
```

## 6. ERC4626 VAULT ATTACKS

### Manipulasi exchange rate (vault hampir kosong)
```solidity
// RENTAN — serangan first depositor:
// 1. Attacker deposit 1 wei → dapat 1 share
// 2. Attacker donasi besar langsung (transfer, bukan deposit)
// 3. Exchange rate: 1 share = (1 + donasi) aset
// 4. Korban deposit → dibulatkan ke 0 share → donasi gratis buat attacker

// BENAR: virtual shares (OpenZeppelin v4.9+)
function _decimalsOffset() internal view virtual override returns (uint8) {
    return 9;  // tambah 1e9 virtual shares + aset buat cegah manipulasi
}
```

### Transfer ERC4626 (share pindah tapi catatan stake/lock tidak)
```solidity
// RENTAN: share ditransfer, tapi catatan lock tetap di pemilik lama
// → share nyangkut, tidak bisa redeem → freeze permanen (pola Belong)
function transfer(address to, uint256 amount) external override {
    _transfer(msg.sender, to, amount);  // share pindah
    // HILANG: transfer catatan lock dari msg.sender ke `to`
}
```

### Grep Patterns
```bash
grep -rn "function transfer\|function transferFrom" contracts/ -A15
grep -rn "function deposit\|function mint\|function withdraw\|function redeem" contracts/ -A10
```

## 7. REENTRANCY
> 2016–sekarang. Pola CEI mencegahnya. Masih ketemu di DeFi.

### Varian
- **Single-function**: attacker masuk lagi ke fungsi yang sama sebelum state di-update
- **Cross-function**: masuk lagi ke sibling function dengan state basi
- **Cross-contract**: masuk lagi lewat callback ke protokol lain
- **Read-only**: masuk lagi ke view function yang mengembalikan data basi yang dipakai attacker

### Pola akar masalah
```solidity
// RENTAN (efek setelah interaksi):
function withdraw(uint256 amount) external {
    require(balances[msg.sender] >= amount);
    (bool success,) = msg.sender.call{value: amount}("");  // INTERAKSI dulu
    require(success);
    balances[msg.sender] -= amount;  // EFEK sesudah → jendela reentrancy
}

// BENAR (CEI — Checks, Effects, Interactions):
function withdraw(uint256 amount) external {
    require(balances[msg.sender] >= amount);  // CHECK
    balances[msg.sender] -= amount;            // EFFECT
    (bool success,) = msg.sender.call{value: amount}("");  // INTERAKSI terakhir
    require(success);
}
```

### Grep Patterns
```bash
# External call sebelum update state
grep -rn "\.call{value\|safeTransfer\|transfer(" contracts/ -B10 | grep -v "require\|revert"

# Modifier nonReentrant hilang di fungsi kritis
grep -rn "function withdraw\|function redeem\|function claim" contracts/ -A2 | grep -v "nonReentrant"

# Storage slot buat reentrancy guard
grep -rn "nonReentrant\|ReentrancyGuard\|_notEntered" contracts/
```

## 8. FLASH LOAN ATTACKS

### Manipulasi oracle via flash loan
```solidity
// Alur serangan:
// 1. Pinjam $100M dari flash loan Aave
// 2. Buang token di pool Uniswap → harga spot jatuh
// 3. Protokol baca harga spot Uniswap → pinjaman undercollateralized diterima
// 4. Pinjam maksimal dengan kolateral murah
// 5. Lunasi flash loan, simpan profit
```

### Sanity check harga oracle (yang dicari)
```bash
grep -rn "getReserves\|getAmountsOut\|slot0\b" contracts/ -A5
# harga spot dari reserves = bisa dimanipulasi flash loan
# slot0 = harga spot Uniswap V3 = bisa dimanipulasi
```

## 9. SIGNATURE REPLAY

### Nonce hilang
```solidity
// RENTAN:
function permit(address owner, address spender, uint256 value,
                uint256 deadline, uint8 v, bytes32 r, bytes32 s) external {
    bytes32 hash = keccak256(abi.encodePacked(owner, spender, value, deadline));
    // HILANG: nonce tidak dimasukkan → tanda tangan yang sama bisa dipakai berkali-kali
    require(ecrecover(hash, v, r, s) == owner);
}
```

### Chain ID hilang
```solidity
// RENTAN: tanda tangan valid di mainnet DAN testnet DAN semua fork
bytes32 hash = keccak256(abi.encodePacked(params));
// HILANG: block.chainid tidak ada di hash → berlaku di chain mana pun
```

### Grep Patterns
```bash
grep -rn "ecrecover\|ECDSA\.recover" contracts/ -B20
# Cek: apakah hash yang ditandatangani mencakup nonce + chainId + alamat kontrak?

grep -rn "nonce\|_nonces\|nonces\[" contracts/
```

## 10. PROXY / UPGRADE ISSUES

### Storage collision
```solidity
// Implementation dan proxy berbagi layout storage
// Slot 0 proxy: _owner
// Slot 0 implementation: _initialized
// → tulis ke _initialized menimpa _owner
```

### Implementation belum di-initialize
```solidity
// Kalau implementation bisa di-initialize langsung → siapa pun jadi owner implementation
// Serangan: panggil initialize() di kontrak implementation → panggil upgradeTo() → ganti logika
```

### delegatecall ke alamat yang dikontrol user
```solidity
function execute(address target, bytes calldata data) external onlyOwner {
    target.delegatecall(data);  // target divalidasi, tapi bagaimana kalau owner dikompromi?
}
```

### Grep Patterns
```bash
# Proteksi inisialisasi UUPS
grep -rn "function initialize\b\|_disableInitializers\|initializer" contracts/

# Delegate call
grep -rn "delegatecall\b" contracts/ -B3 -A5

# Layout storage — proxy pakai slot EIP-1967?
grep -rn "0x360894\|EIP1967\|_IMPLEMENTATION_SLOT" contracts/
```

## FOUNDRY POC TEMPLATE

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "forge-std/Test.sol";
import "../src/VulnerableContract.sol";

contract ExploitTest is Test {
    VulnerableContract target;
    address attacker = makeAddr("attacker");
    address victim = makeAddr("victim");

    function setUp() public {
        // Fork mainnet di block tertentu
        vm.createSelectFork("mainnet", BLOCK_NUMBER);

        // Deploy atau load target
        target = VulnerableContract(TARGET_ADDRESS);

        // Danai akun
        deal(address(token), attacker, INITIAL_BALANCE);
        deal(address(token), victim, VICTIM_BALANCE);
    }

    function test_exploit() public {
        console.log("Attacker balance before:", token.balanceOf(attacker));

        vm.startPrank(attacker);

        // Step 1: Siapkan kondisi
        // Step 2: Jalankan exploit
        // Step 3: Verifikasi dampak

        vm.stopPrank();

        console.log("Attacker balance after:", token.balanceOf(attacker));
        assertGt(token.balanceOf(attacker), INITIAL_BALANCE, "Exploit failed");
    }
}
```

### Cheatcode Foundry kunci
```solidity
vm.prank(address)           // call berikutnya dari address
vm.startPrank(address)      // semua call dari address sampai stopPrank()
vm.deal(address, amount)    // set saldo ETH
deal(token, address, amount) // set saldo ERC20
vm.warp(timestamp)          // set block.timestamp
vm.roll(blockNumber)        // set block.number
vm.createSelectFork("mainnet", blockNumber)  // fork mainnet
vm.expectRevert(bytes)      // call berikutnya harus revert
vm.label(address, "name")   // label buat output trace
vm.assume(condition)        // fuzz: buang input yang tidak memenuhi
```

### Menjalankan test
```bash
# Jalankan test tertentu
forge test --match-test test_exploit -vvvv

# Jalankan dengan fork
forge test --match-test test_exploit -vvvv --fork-url $MAINNET_RPC

# Laporan gas
forge test --gas-report

# Coverage
forge coverage --report summary
```
