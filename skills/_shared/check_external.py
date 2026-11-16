#!/usr/bin/env python3
"""Cek hidup/mati endpoint publik yang dirujuk skill-skill di repo ini.

Read-only: hanya GET tanpa kunci/API key, timeout singkat per endpoint.
Dipakai untuk butir 21 brief perbaikan muse-skills (last_verified).

Jalankan dari repo root:
    python3 skills/_shared/check_external.py
Keluar dengan kode 0 bila semua endpoint menjawab, 1 bila ada yang gagal.
"""

import json
import sys
import urllib.error
import urllib.request

TIMEOUT = 8  # detik per endpoint
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) muse-skills-check/1.0"}

# (nama, url, dipakai oleh skill)
CHECKS = [
    # Bitget v2 (live-confirm, candle-reader-15m, multi-token-screener)
    ("Bitget v2 tickers", "https://api.bitget.com/api/v2/spot/market/tickers?symbol=BTCUSDT",
     ["live-confirm"]),
    ("Bitget v2 candles 15m", "https://api.bitget.com/api/v2/spot/market/candles?symbol=BTCUSDT&granularity=15min&limit=1",
     ["live-confirm", "candle-reader-15m"]),
    # Sourcify v2 (free-mint-farming-agent, onchain-contract-scanner, contract-checker)
    # GET /v2/contract/{chainId}/{address} — 200 bila terverifikasi, 404 bila
    # alamat itu belum terverifikasi; keduanya berarti endpoint hidup.
    # Alamat contoh: WBNB (BSC), hampir pasti terverifikasi.
    ("Sourcify v2 contract (WBNB, BSC)",
     "https://sourcify.dev/server/v2/contract/56/0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
     ["free-mint-farming-agent", "onchain-contract-scanner", "contract-checker"]),
    # Agregator airdrop (airdrop-calendar-aggregator)
    ("airdrops.io", "https://airdrops.io/", ["airdrop-calendar-aggregator"]),
    ("CryptoRank", "https://cryptorank.io/", ["airdrop-calendar-aggregator", "unlock-catalyst-calendar"]),
    # Pelacak unlock (unlock-catalyst-calendar)
    ("Tokenomist", "https://tokenomist.ai/", ["unlock-catalyst-calendar"]),
    ("DefiLlama unlocks", "https://defillama.com/unlocks", ["unlock-catalyst-calendar", "project-due-diligence"]),
    # Dashboard riset (project-due-diligence)
    ("Dune", "https://dune.com/", ["project-due-diligence"]),
    # Agregator DEX (scalp-setup-scanner, token-liquidity-checker)
    ("DexScreener API search", "https://api.dexscreener.com/latest/dex/search?q=ETH",
     ["scalp-setup-scanner", "token-liquidity-checker"]),
    ("GeckoTerminal API networks", "https://api.geckoterminal.com/api/v2/networks",
     ["scalp-setup-scanner", "token-liquidity-checker"]),
    # Explorer (contract-checker, onchain-contract-scanner, airdrop-hunter)
    ("Etherscan", "https://etherscan.io/", ["contract-checker", "onchain-contract-scanner", "airdrop-hunter"]),
    ("BscScan", "https://bscscan.com/", ["contract-checker", "onchain-contract-scanner"]),
    ("Basescan", "https://basescan.org/", ["contract-checker", "onchain-contract-scanner"]),
    ("Arbiscan", "https://arbiscan.io/", ["contract-checker", "onchain-contract-scanner"]),
    ("Solscan", "https://solscan.io/", ["contract-checker"]),
    # Alat bantu (contract-checker, onchain-contract-scanner, wallet-hygiene)
    ("Tenderly", "https://tenderly.co/", ["contract-checker", "onchain-contract-scanner"]),
    ("Rabby", "https://rabby.io/", ["contract-checker", "airdrop-hunter"]),
    ("Revoke.cash", "https://revoke.cash/", ["contract-checker", "wallet-hygiene", "airdrop-hunter"]),
    # Platform quest (airdrop-hunter)
    ("Galxe", "https://galxe.com/", ["airdrop-hunter"]),
    ("Zealy", "https://zealy.io/", ["airdrop-hunter"]),
]


def check(name, url):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, "HIDUP"
    except urllib.error.HTTPError as e:
        # 403 = host hidup tapi menolak bot; 429 = host hidup tapi rate-limited;
        # 404 pada endpoint Sourcify v2 = alamat belum terverifikasi (endpoint hidup).
        if e.code in (403, 429):
            return e.code, "HIDUP (menolak bot / rate-limited)"
        if e.code == 404 and "sourcify" in url:
            return e.code, "HIDUP (kontrak contoh belum terverifikasi)"
        return e.code, "MATI"
    except Exception as e:  # timeout, DNS, koneksi ditolak, dst.
        return None, "TIDAK TERVERIFIKASI (%s)" % type(e).__name__


def main():
    results = []
    failed = 0
    for name, url, skills in CHECKS:
        status, verdict = check(name, url)
        results.append({"endpoint": name, "url": url, "status": status,
                        "verdict": verdict, "skills": skills})
        print("%-40s %-6s %s" % (name, str(status), verdict))
        if verdict.startswith(("MATI", "TIDAK")):
            failed += 1
    print("\n%d/%d endpoint menjawab (HIDUP)." % (len(results) - failed, len(results)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
