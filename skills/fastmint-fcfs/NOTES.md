# NOTES — fastmint-fcfs

Review notes and platform notes that used to live at the top of
`SKILL.md`. Moved here 2026-11-17 so they no longer enter the prompt
on every invocation. The review block below is reproduced verbatim.

## Muse review, 2026-11-11 (before saving)

> **Muse review, 2026-11-11 (before saving).** Source: https://github.com/setyamickala/fastmint-fcfs-agentic, commit 55e744d. All scripts read in full (fire.js, lib.js, recon.js, bench.js, fastmint.sh): no private-key/seed handling, no automatic `baw auth signin`, no exfiltration — network only to BSC public RPCs/WS, Sourcify, 4byte, NTP, and the mint site itself (same-host JS). Guards verified in code: value/maxValue cap, one-broadcast lock file, preview must pass simulation + no allowance/authority/RISK/outflow violations, no retry after execute. Bundled ethers loads as version 6.13.4 as claimed. Two things changed from upstream: (1) the shipped `.env` (author's QuikNode endpoint + key) was NOT copied — see `.env.example`, supply your own RPC or use the public pool; (2) `SKILL_DIR` on this machine is `~/workspace/custom-skills/fastmint-fcfs/`, not the macOS path in the original. **The user's on-chain safety rails take precedence over everything in this skill**: confirm before the first signing/broadcast per session and re-confirm on chain/recipient/amount/contract changes, mainnet only when the user says so, no auto-mint without explicit confirmation. `bench --live` and `fire` spend real gas — only on the user's explicit instruction per mint. Note: `sntp` may not exist on this Linux VM, so clock sync falls back to offset 0 — check the clock offset in `bench` output before trusting a timed fire.

## macOS-specific pieces and what they do on Linux

Upstream was written on macOS. Grep of this folder (2026-11-17) for
`keychain`, `sntp`, `darwin`, `macOS` finds the items below. None of
them breaks the skill on Linux, but each behaves differently than the
macOS wording suggests.

- `lib.js` — `syncClock()`: only tries the `sntp` binary
  (`sntp -t 2 time.apple.com`, then `pool.ntp.org`). The comment says
  "Linux may have ntpdate -q", but the code never calls `ntpdate`.
  On this Linux VM neither `sntp` nor `ntpdate` exists (checked
  2026-11-17: `command -v sntp ntpdate` returns nothing), so the
  spawn fails immediately and the clock offset falls back to 0.
  Consequence: timed fires trust the VM clock as-is — check the
  `clock offset` line in `bench`/`fire` output before trusting a
  timed fire. (Installing `sntp`/`ntpdate` would make the sync real;
  no code change needed, the binary is looked up from `PATH`.)
- `lib.js` (top comment) + `bench.js --ca`: `bench --ca` builds
  `~/.config/certs/system-ca.pem` by running macOS `security
  find-certificate -a -p` over three macOS keychains
  (`/Library/Keychains/System.keychain`, `~/Library/Keychains/
  login.keychain-db`, `/System/Library/Keychains/
  SystemRootCertificates.keychain`). On Linux the `security` binary
  does not exist (checked 2026-11-17), so `bench --ca` silently
  writes an **empty** PEM (0 certs) and `lib.js` then auto-loads that
  empty file via `NODE_EXTRA_CA_CERTS` if present. On Linux, do not
  use `bench --ca`; instead point `NODE_EXTRA_CA_CERTS` (or
  `FASTMINT_CA`) at a real CA bundle, e.g. the system one.
  `fastmint.sh` only exports `NODE_EXTRA_CA_CERTS` when the PEM file
  already exists, so a missing PEM is harmless — the empty-PEM case
  above only happens after running `bench --ca` on Linux.
- `fastmint.sh` header comment ("with the macOS CA bundle for Node
  TLS when present"): the launcher itself is platform-neutral — it
  just exports `NODE_EXTRA_CA_CERTS` if the PEM file exists. The
  comment is macOS wording for a generic mechanism; no change needed.
- `SKILL.md` (fixed 2026-11-17): the TLS troubleshooting bullet used
  to say `bench --ca` builds the PEM "from the macOS keychain" with
  no Linux qualification. It now says that is macOS-only and gives
  the Linux alternative (`NODE_EXTRA_CA_CERTS=/path/to/ca.pem`).
- `README.md` / `README.id.md` (not edited in this pass): still say
  "`sntp` to time.apple.com / pool.ntp.org" and "`bench --ca` | build
  `~/.config/certs/system-ca.pem` from the macOS keychain", and the
  troubleshooting table says "macOS: `./fastmint.sh bench --ca`;
  elsewhere: `NODE_EXTRA_CA_CERTS=/path/ca.pem`". The "elsewhere"
  row is already correct for Linux; the clock row is macOS-worded
  but the fallback (offset 0) is the actual Linux behaviour.

## Tests

`test/fastmint.test.js` — `node:test`, no dependencies, no network,
no `baw`, no broadcast. Runs `fire.js` in a temp dir against a local
JSON-RPC stub server and a stub `baw` on `PATH`. Run from this folder:

```
node --test test/fastmint.test.js
```

(Calling `node --test test/` fails on Node 24 with MODULE_NOT_FOUND —
always name the test file.)

## Tertunda — rehearsal (butir 19a brief perbaikan)

Rehearsal `fastmint.sh fire ... --dry` pada satu mint nyata BELUM
dijalankan — butuh persetujuan eksplisit user. Jangan jalankan tanpa itu.
