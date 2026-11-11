# fastmint-fcfs

**English** · [Bahasa Indonesia](README.id.md)

**FCFS mint on BNB Smart Chain through Binance Agentic Wallet, landed in a block ±2 seconds after the sale opens.**

A skill for AI agents (Claude Code, Codex, Cursor, OpenClaw, and any other agent that reads `SKILL.md`) that fires a single mint/claim/buy transaction at the exact moment a sale opens, using a Binance Agentic Wallet (`baw` CLI). No private key on the machine: signing happens in Binance's backend through Developer Mode, the agent only prepares calldata and picks the moment.

```
sale opens (T)    T+0.05s          T+0.6–0.8s        T+1.3–1.5s       T+2.1–2.2s
   │                 │                  │                  │                 │
   ▼                 ▼                  ▼                  ▼                 ▼
 start ───► preview sent ───► simulation OK ───► BROADCASTED ───► in a block
         (NTP clock trigger)    (requestId)     (baw execute)     (receipt)
```

The numbers above were measured 11 Nov 2026 from Indonesia: 3 time-gated dry-runs plus one real mint (Pocket Moons, 2 free NFTs, trigger→receipt 2.0 seconds). The previous sequential version took 5–6 seconds.

---

## Table of contents

1. [How it works](#1-how-it-works)
2. [Installation](#2-installation)
3. [Usage flow](#3-usage-flow)
4. [Command reference](#4-command-reference)
5. [Dynamic arguments](#5-dynamic-arguments)
6. [Safety rails](#6-safety-rails)
7. [Measured numbers](#7-measured-numbers)
8. [Troubleshooting](#8-troubleshooting)
9. [File layout](#9-file-layout)
10. [FAQ](#10-faq)

---

## 1. How it works

### Why the old version was slow

`baw` has no direct-send command for a contract call. The flow is two steps by design: `contract-call preview` (the backend simulates and returns a `requestId`) and then `contract-call execute --requestId`. The old version waited for a public RPC to report a successful `eth_call` (±1 second after the opening block), then previewed, then executed. Every stage waited on the previous one: T+5–6 seconds.

### Three parallel triggers

`fire.js` does not wait on a single signal. During the 3-second **burst** window after the sale opens, three triggers may each launch a preview independently (minimum spacing `--gap` 350ms, at most `--inflight` 3 at a time):

| trigger | when | source |
|---|---|---|
| **clock** | exactly T+0 by the NTP-corrected clock | `sntp` to time.apple.com / pool.ntp.org |
| **head** | the first block with `timestamp ≥ start` is seen | WebSocket `newHeads` (QuikNode, publicnode, drpc) + HTTP polling every 150ms |
| **eth_call OK** | a simulation from the wallet succeeds on one of the 4 fastest RPCs | `eth_call` on tags `latest` and `pending`, every 100ms |

The first preview that comes back with `simulationCode 000000000` is executed immediately, **exactly once**. Other previews still in flight are ignored. Previews that fail because the backend has not seen the opening block yet (error `351805`) are cheap and harmless; the next trigger retries.

Once the burst is over, only **eth_call OK** triggers previews, so a sale that opens late does not burn `--maxPreviews`; the `eth_call` spin keeps watching until `--timeout` (600 seconds).

### The ranked RPC pool

The RPC list is measured at start and re-ranked at T-10s (latency and block lag). From Indonesia: QuikNode 31ms, bloXroute 32ms, 48.club 45ms, official dataseed ±105ms, publicnode ±200ms. Nodes that strip revert data (zon, for example) are left out, because a revert with no data cannot be told apart from "not open yet".

`eth_call` race: the first success wins; a revert **with data** wins (deterministic); a revert with no data only counts after every node has answered and is never treated as fatal.

### Revert classification

Error names are decoded from the contract's Sourcify ABI, a built-in list of common errors, then 4byte. Every name maps to:

- **wait**: `NotStarted`, `NotOpen`, `NotLive`, `TooEarly`, `Paused`, … → keep retrying until `--timeout`
- **fatal**: `SoldOut`, `FreeGone`, `AlreadyClaimed`, `AgentIdRequired`, `NotEligible`, `WrongValue`, `Insufficient…` → stop immediately (±50ms)
- **unknown**: treated as wait until `start + --grace` (10s), fatal after that. Before the opening time only the hard-terminal names (sold/gone/already/agent/eligible/expired) are considered fatal.

Override with `--waitOn <regex>` and `--fatalOn <regex>`.

---

## 2. Installation

### Prerequisites

- **Node.js ≥ 20** (v26 in use). No `npm install`: `ethers` 6.13 is already bundled.
- **Binance Agentic Wallet CLI**: `npm install -g @binance/agentic-wallet@1.12.0`
- **Binance App** with Agentic Wallet and **Developer Mode** on (Agentic Wallet → Settings → Developer Mode). The wallet balance must be under the Developer Mode cap.
- The `binance-agentic-wallet` skill from https://github.com/binance/binance-skills-hub (optional but recommended, for other wallet operations).
- Optional: an **Agent ID** (`yourname.ai`) for mints that require one.

### Installing the skill

Extract the zip, then put the `fastmint-fcfs` folder wherever your agent reads skills from:

```bash
# Claude Code (per project)
mkdir -p .claude/skills && cp -r fastmint-fcfs .claude/skills/

# Claude Code (global)
mkdir -p ~/.claude/skills && cp -r fastmint-fcfs ~/.claude/skills/

# skills CLI / .agents (Codex, Cursor, etc.)
mkdir -p .agents/skills && cp -r fastmint-fcfs .agents/skills/
chmod +x fastmint-fcfs/fastmint.sh
```

### Wallet sign-in (once, session lasts 2 days / 48 hours idle)

```bash
baw auth signin --json
```

Open the `urlForWeb` that appears, match the `pairingCode` in the Binance App, approve, then:

```bash
baw auth verify --qrCodeId <qrCodeId> --json
baw wallet status --json      # must be CONNECTED
```

### Checking the environment

```bash
cd fastmint-fcfs
./fastmint.sh bench
```

Expected output: RPC ranking, WebSocket delay, clock offset, `wallet status CONNECTED`, `devMode ON`, BNB balance, Agent ID, three previews in ±0.6s, and a time estimate. All read-only.

### `.env` (premium RPC)

The `.env` file in the skill folder is sourced automatically by `fastmint.sh`:

```bash
FASTMINT_RPCS_EXTRA=https://<premium-endpoint>     # prepended to the pool, still ranked
FASTMINT_WS_EXTRA=wss://<premium-endpoint>         # used for newHeads
```

This repo ships a `.env` with a QuikNode BSC endpoint. The host is masked in every log. Other variables: `FASTMINT_RPCS` (replace the whole pool), `FASTMINT_WS`, `FASTMINT_TZ` (default `Asia/Jakarta`), `FASTMINT_CA` (CA bundle for Node, see troubleshooting).

---

## 3. Usage flow

This is the flow the agent runs when you say **"mint free at 23:00 https://mint-site"**:

```
┌──────────┐    ┌──────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────┐
│  bench   │───►│  recon   │───►│  fire --dry  │───►│    fire      │───►│  report  │
│ env OK?  │    │ CA, ABI, │    │ 10s rehearsal│    │ background,  │    │ tx, link,│
│ ~10s     │    │ getters, │    │ before open  │    │ 1x execute   │    │ TIMELINE │
│          │    │ calldata │    │ stop at prev │    │              │    │          │
└──────────┘    └──────────┘    └──────────────┘    └──────────────┘    └──────────┘
```

**Step 0, bench** (once per session). `UNCONNECTED` → sign in first. devMode OFF → turn it on in the app.

**Step 1, recon** (~5–10s):

```bash
./fastmint.sh recon https://mint-site            # or --contract 0x... if the CA is known
```

Recon fetches the HTML, the JS bundles, and agent documents (`llms.txt`, `skill.md`, `handbook.md`, …), extracting addresses, chainId, mint function names, ABI signatures, and unix times. It then runs `eth_getCode`, pulls the ABI from Sourcify v2 (or from the site bundle filtered down to selectors that actually exist in the bytecode), reads every view getter (0-arg, `(wallet)`, `(agentId)`), and prints **MINT CANDIDATES** with guessed arguments, calldata, simulation results, a `START HINT` from start getters, and ready-to-use `fire:` commands.

Read from the output: opening time, free supply left, price, per-wallet limit, `agentIdOf(wallet)`, and error names (`SoldOut`, `FreeGone`, …).

**Step 2, rehearsal** (always):

```bash
./fastmint.sh fire --to 0xSALE --data 0x195ad114 --start 23:00 --dry
```

Does everything up to the preview, then stops. Check that the `call = …` line decodes to the right function and arguments. Add `--gateSim` if the call can already be simulated now, so the rehearsal exercises the real time-gated path.

**Step 3, fire** (in the background so the chat stays responsive):

```bash
./fastmint.sh fire --to 0xSALE --data 0x195ad114 --start 23:00 --label project_free
```

**Step 4, report**: tx hash, status, BscScan link, the `TIMELINE` line (T+ offsets for trigger/preview/execute/broadcast/inclusion), what was received, and the log path. If it stopped: the decoded revert name and what it means.

---

## 4. Command reference

### `./fastmint.sh`

| command | purpose |
|---|---|
| `bench` | environment check, read-only |
| `bench --ca` | build `~/.config/certs/system-ca.pem` from the macOS keychain |
| `bench --live` | **send 1 real tx** (USDT `balanceOf`, 0 BNB, gas ±0.00002 BNB) to measure execute. Only with explicit user approval |
| `recon <url> [--contract 0x..] [--wallet 0x..] [--json]` | quick recon, read-only |
| `fire …` | execution (see below) |
| `logs [n]` | tail the last run log |
| `locks` | list execute locks |

### `fire`

```
./fastmint.sh fire --to 0xC (--data 0x... | --sig "fn(type,..)" --args '[..]') [--start <t>] [options]
```

| option | default | meaning |
|---|---|---|
| `--value <BNB>` | 0 | BNB sent, decimal. Paid mints need an explicit number from the user |
| `--maxValue <BNB>` | | cap. Required when value > 0; rejected if value > cap |
| `--start <t>` | now | unix seconds, `HH:MM[:SS]` WIB, or ISO-8601 |
| `--lead <ms>` | 3000 | start spinning before start |
| `--interval <ms>` | 100 | spacing of the eth_call spin |
| `--clockFire <ms>` | 0 | send a preview at start+ms by the clock; `-1` disables |
| `--burst <ms>` | 3000 | clock+head trigger window after start |
| `--gap <ms>` | 350 | minimum spacing between previews |
| `--inflight <n>` | 3 | maximum parallel previews |
| `--maxPreviews <n>` | 40 | give up after that many failed previews |
| `--timeout <s>` | 600 | keep retrying "not open yet" reverts for this long |
| `--grace <s>` | 10 | Unknown reverts count as wait until start+grace |
| `--once` | | one preview, one execute, no retry |
| `--dry` | | stop before execute (`--noPreview`: before preview) |
| `--gateSim` | | rehearsal: ignore eth_call OK before start |
| `--expectNft <n>` | | execute only if the preview shows exactly n NFTs from `--to` entering the wallet |
| `--noEager` / `--noWs` | | disable the head / WebSocket trigger |
| `--gasLimit <n>` | | forwarded to the preview, only on user request |
| `--from 0x..` | baw wallet | sender address |
| `--abi 0x..` | `--to` | another address whose ABI is used to decode errors |
| `--waitOn` / `--fatalOn <regex>` | | override revert classification |
| `--label <name>` | | log/lock file name |

Examples:

```bash
# free mint at 23:00 WIB, raw calldata
./fastmint.sh fire --to 0xSALE --data 0x195ad114 --start 23:00 --label feg_free

# signature + static arguments
./fastmint.sh fire --to 0xSALE --sig "claimFreeShare()" --start 23:00

# dynamic arguments: Agent ID and deadline re-read on every preview
./fastmint.sh fire --to 0xSALE --sig "mintFree(uint256,uint256,uint256,uint256,address)" \
  --args '["$agentId","1","0","$now+1800","0x0000000000000000000000000000000000000000"]' --start 21:00

# argument that must match the counter at open time
./fastmint.sh fire --to 0xSALE --sig "mint(uint256)" --args '[{"getter":"totalMinted()","add":1}]' --start 1794330000

# paid mint (user said: 2 shares @0.005 = 0.01 BNB)
./fastmint.sh fire --to 0xSALE --sig "buyWithBnb(uint256,address,uint256)" \
  --args '[2,"0x0000000000000000000000000000000000000000",0]' --value 0.01 --maxValue 0.01 --start 23:00

# already-open mint, ensure 2 NFTs are received
./fastmint.sh fire --to 0xNFT --data 0xa0712d68…0002 --value 0 --expectNft 2
```

---

## 5. Dynamic arguments

Elements in `--args` may be placeholders evaluated **right before every preview**, so values that change at open time are always fresh:

| form | value |
|---|---|
| `"$wallet"` | the baw wallet address on chain 56 |
| `"$agentId"` | Agent ID tokenId = `uint256(keccak256(handle))`, from registry `0x60B9…022F` `handleOf(wallet)` |
| `"$zero"` | `0x000…000` |
| `"$now+1800"` | unix now + 1800 (deadline) |
| `{"getter":"totalMinted()","add":1}` | `eth_call` to a getter on `--to` (tag `pending`), uint256 result + 1 |
| `{"getter":"saleStart()","at":"0x..","mul":2}` | getter on another contract, multiplied by 2 |

Lock files for calls with dynamic arguments key on `to|selector|value`, so the same mint stays locked even as its arguments change.

---

## 6. Safety rails

These are what make the agent safe to run without close supervision. None may be skipped.

1. **Fire only on an explicit user instruction** for this mint ("mint free at 23:00", "gas", "ok"). A link alone is not an instruction.
2. **Free mint = `--value 0`.** Paid mints need the amount the user stated, set as both `--value` and `--maxValue`. Rejected if value > cap, or if value > 0 without a cap.
3. **One broadcast.** `runs/lock_<hash>.json` is written before execute; the same call is refused forever after. Never retry after execute, even if execute errored or the tx reverted. A lock is removed only on a new explicit instruction.
4. **Never `baw auth signin` automatically.** Status not CONNECTED → stop and ask the user. Never ask for a private key, seed phrase, or session token.
5. **Never push through a Binance risk block** (`351803`), a `RISK` flag, or an allowance/authority change in the preview. Stop and report.
6. **Connected wallet only.** Check balance ≥ value + gas before starting.
7. **The preview must pass**: `simulationCode 000000000`, no allowance/authority change, no RISK, native outflow ≤ cap + 0.003 BNB, `parsedTx.amount` = 0 for a 0-value call, `requestId` present, and `--expectNft` when set.
8. **`PENDING_CONFIRMATION`** → the user approves in the app; do not resend.
9. **Premium RPC keys are never printed**: every log carries the host only.

---

## 7. Measured numbers

All from one machine in Indonesia, 11 Nov 2026, over encrypted DNS.

**Components**

| component | value |
|---|---|
| `baw wallet status` (CLI cold start) | 0.3–0.4s |
| `baw contract-call preview` | 0.45–0.8s (requestId valid 300s) |
| `baw contract-call execute` → BROADCASTED | 0.68–0.71s |
| broadcast → receipt | 0.54–0.77s |
| BSC block time | ±0.5s |
| fastest RPC (QuikNode / bloXroute / 48.club) | 31 / 32 / 45 ms |
| WS newHeads delay (QuikNode / publicnode) | median 0.45s / 0.56s, best 0.03s |
| local clock offset vs NTP | +0.1–0.16s (corrected automatically) |

**Real mint, already open** (Pocket Moons `mint(2)`, free, 2 NFTs): eth_call OK +35ms → preview 564ms → execute 683ms → BROADCASTED +1.2s → receipt +0.77s. **Total 2.0s.**

**Time-gated dry-runs, 3 runs** (`--gateSim`):

| run | clock | eth_call OK | head | preview OK |
|---|---|---|---|---|
| 1 | T+0.054s | T+0.087s | T+0.503s | T+0.761s |
| 2 | T+0.049s | T+0.084s | T+0.168s | T+0.619s |
| 3 | T+0.049s | T+0.083s | T+0.250s | T+0.736s |

**FCFS projection**: broadcast ≈ **T+1.3–1.5s**, in a block ≈ **T+2.1–2.2s**. If Binance's node only sees the opening block on the second preview, add ±0.4s → T+2.6s. The old version: T+5–6s.

---

## 8. Troubleshooting

| symptom | meaning | action |
|---|---|---|
| `baw wallet status` = `UNCONNECTED` | session expired (2 days idle) | user signs in again; the agent must not do it automatically |
| `351802` / `351804` | Developer Mode off / expired / balance above the cap | turn it on in the Binance App, then retry |
| `351803` `AGENT_DEV_MODE_RISK_BLOCKED` | Binance blocks the contract | stop, show the risk text, do not bypass |
| `351805` `simulation failed` repeatedly | mint not open on Binance's node, or wrong arguments | normal before the opening time; if eth_call has been OK for a while, inspect the preview JSON in `runs/` |
| `NotStarted` forever | wrong opening time | compare the contract getter against the site; is `--timeout` enough? |
| `SoldOut` / `FreeGone` | gone | terminal; do not switch to a paid mint without "ok paid" + an amount |
| `AgentIdRequired` / `NotEligible` | wallet without an Agent ID, or needs the agent argument | use `"$agentId"` |
| `AlreadyClaimed` / `AlreadyTaken` | already done | finished |
| `PaymentLow` / `WrongValue` | value ≠ price × qty | read the price getter, confirm the quantity with the user |
| `PENDING_CONFIRMATION` | tx deemed abnormal | user approves in the app; do not resend |
| execute error / no receipt | | **do not retry**; `baw wallet tx-history --json`, `baw wallet tx-lock --json` |
| `gave up after N previews` | backend keeps failing while eth_call is OK | Binance node state differs from public RPCs, or the arguments are wrong |
| `UNABLE_TO_GET_ISSUER_CERT_LOCALLY` (Node) | Node's CA store does not know the certificate chain | macOS: `./fastmint.sh bench --ca`; elsewhere: `NODE_EXTRA_CA_CERTS=/path/ca.pem` |
| `SSL_ERROR … altnames: internetbaik.telkomsel.com` / DNS answers `internetpositif.id` | the ISP hijacks DNS for binance.com (even queries to 1.1.1.1) | use encrypted DNS (Cloudflare 1.1.1.1 app, DNS-only mode) or a VPN. Do not change the system DNS from the agent |
| slow / rate-limited RPC | | `FASTMINT_RPCS=…` or `FASTMINT_RPCS_EXTRA=…` in `.env` |
| `lock exists` | this call has already been executed | delete `runs/lock_*.json` only on a new user instruction |

---

## 9. File layout

```
fastmint-fcfs/
├── SKILL.md            instructions for the agent (read automatically)
├── README.md           this document (English, the GitHub default)
├── README.id.md        Bahasa Indonesia version
├── fastmint.sh         launcher: bench | recon | fire | logs | locks; sources .env and the CA
├── fire.js             FCFS engine: precheck → wait → 3 triggers → preview → 1x execute → receipt
├── recon.js            quick recon: site + Sourcify + getters + mint candidates + calldata
├── bench.js            environment check; --ca builds the CA bundle; --live 1 test tx (with approval)
├── lib.js              RPC pool & race, WS heads, NTP, revert decoding, baw runner, Agent ID, ABI cache
├── ethers.umd.min.js   ethers 6.13.4 (bundled, no npm install)
├── .env                premium RPC (FASTMINT_RPCS_EXTRA / FASTMINT_WS_EXTRA)
├── .gitignore
├── cache/              downloaded Sourcify ABIs
└── runs/               per-run logs, preview/exec/receipt JSON, lock_*.json
```

Logs: `runs/<stamp>_<label>.log`, WIB timestamps plus `T+x.xxxs` offsets. The last line of every run is `TIMELINE`.

---

## 10. FAQ

**Why not just send the transaction directly with a private key? It is faster.**
True, under 1 second is possible. But this skill is built for Binance Agentic Wallet: no private key on the machine, a daily limit, risk blocks, and in-app approval for abnormal txs. The two-step preview/execute is the price of that safety, and 2 seconds is still far below 5 seconds.

**Can the preview be done before the sale opens so only execute remains?**
No. The backend simulates at preview time; before the sale opens the simulation fails (`351805`) and there is no `requestId`. That is why the clock trigger sends the preview at exactly T+0, not earlier.

**What if the team opens late?**
After the 3-second burst, the `eth_call` spin keeps watching for up to 600 seconds. As soon as one RPC reports success, a preview goes out.

**Why does `--gateSim` exist?**
Rehearsal tool only. When rehearsing with a call that can already be simulated, `eth_call` succeeds before the opening time and fire.js fires straight away (correct for the real case, but it does not exercise the time-gated path). `--gateSim` ignores success before start.

**Is it safe against an accidental second run?**
The lock file refuses the same call. A second run stops within the first second with `lock exists`.

**Can it be used on chains other than BSC?**
Not yet. `CHAIN_ID`, the RPC pool, the Agent ID registry, and the explorer in `lib.js` are all BSC.
