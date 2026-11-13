#!/usr/bin/env python3
"""live_check.py — satu perintah untuk reader_5m + orderbook + delta (read-only, stdlib).

Pakai:  python3 live_check.py --symbol MAGMA [--level 0.2807]

Mengambil 3 endpoint publik Bitget v2 (GET, tanpa kunci), lalu menjalankan ketiga
analisa lewat import modul (bukan shell) dan menampilkan satu blok Bahasa Indonesia.
Kode keluar: 0 = ketiganya terbaca, 2 = ada yang gagal (disebutkan yang mana).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import delta  # noqa: E402
import orderbook  # noqa: E402
import reader_5m  # noqa: E402

BASE = "https://api.bitget.com"
TIMEOUT = 10
UA = "live-check/1.0 (read-only)"


def pair(symbol: str) -> str:
    s = symbol.strip().upper()
    return s if s.endswith("USDT") else s + "USDT"


def build_urls(symbol: str) -> dict[str, str]:
    p = urllib.parse.quote(pair(symbol))
    return {
        "reader_5m": f"{BASE}/api/v2/spot/market/candles?symbol={p}&granularity=5min&limit=100",
        "orderbook": f"{BASE}/api/v2/spot/market/orderbook?symbol={p}&limit=50",
        "delta": f"{BASE}/api/v2/spot/market/fills?symbol={p}&limit=100",
    }


def fetch_json(url: str, timeout: float = TIMEOUT) -> Any:
    """GET publik, tanpa kunci. Mengembalikan isi 'data' bila respons Bitget valid."""
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    if isinstance(body, dict) and "code" in body and str(body["code"]) != "00000":
        raise ValueError(f"API Bitget menolak: kode {body['code']} — {body.get('msg', '')}")
    if isinstance(body, dict) and "data" in body:
        body = body["data"]
    if not body:
        raise ValueError("respons kosong")
    return body


def _err(e: Exception) -> str:
    if isinstance(e, urllib.error.HTTPError):
        return f"HTTP {e.code}"
    if isinstance(e, urllib.error.URLError):
        return f"jaringan: {e.reason}"
    if isinstance(e, TimeoutError):
        return "timeout"
    return str(e) or e.__class__.__name__


def collect(symbol: str, level: float | None = None, timeout: float = TIMEOUT,
            now_ms: int | None = None) -> tuple[dict[str, dict], list[str]]:
    """Jalankan ketiga analisa. Kembalikan ({nama: dict hasil}, daftar nama yang gagal)."""
    urls = build_urls(symbol)
    fns: dict[str, Callable[[Any], dict]] = {
        "reader_5m": lambda raw: reader_5m.analyze(raw, now_ms=now_ms),
        "orderbook": lambda raw: orderbook.analyze(raw, level=level),
        "delta": lambda raw: delta.analyze(raw),
    }
    hasil: dict[str, dict] = {}
    gagal: list[str] = []
    for name, fn in fns.items():
        try:
            res = fn(fetch_json(urls[name], timeout))
        except Exception as e:  # satu kegagalan tidak boleh menghentikan yang lain
            res = {"ok": False, "reason": _err(e), "fetch_error": True, "warnings": []}
        hasil[name] = res
        if not res.get("ok"):
            gagal.append(name)
    return hasil, gagal


def run(symbol: str, level: float | None = None, timeout: float = TIMEOUT,
        now_ms: int | None = None) -> tuple[str, list[str]]:
    """Kembalikan (teks blok, daftar nama analisa yang gagal)."""
    label = symbol.strip().upper().removesuffix("USDT") or symbol
    hasil, gagal = collect(symbol, level, timeout, now_ms)
    fmts = {"reader_5m": reader_5m.to_line, "orderbook": orderbook.to_text, "delta": delta.to_text}
    parts = [f"{label} {n}: GAGAL — {r['reason']}" if r.get("fetch_error") else fmts[n](r, label)
             for n, r in hasil.items()]
    head = f"=== LIVE CHECK {label} ({pair(symbol)})" + (f" | level {reader_5m.idn(level)}" if level is not None else "") + " ==="
    foot = ("Status: semua terbaca." if not gagal else "Status: GAGAL — " + ", ".join(gagal) + ".")
    return head + "\n\n" + "\n\n".join(parts) + "\n\n" + foot, gagal


def run_json(symbol: str, level: float | None = None, timeout: float = TIMEOUT,
             now_ms: int | None = None) -> tuple[str, list[str]]:
    """Satu JSON gabungan: {symbol, pair, level, ok, gagal, reader_5m, orderbook, delta}."""
    hasil, gagal = collect(symbol, level, timeout, now_ms)
    out = {"symbol": symbol.strip().upper().removesuffix("USDT") or symbol, "pair": pair(symbol),
           "level": level, "ok": not gagal, "gagal": gagal, **hasil}
    return json.dumps(out, indent=2, ensure_ascii=False, default=str), gagal


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Live check: reader 5m + order book + delta (read-only, stdlib)")
    ap.add_argument("--symbol", required=True, help="token, mis. MAGMA (USDT ditambahkan otomatis)")
    ap.add_argument("--level", type=float, help="harga level yang dicek tebal/tipis di order book")
    ap.add_argument("--timeout", type=float, default=TIMEOUT, help="timeout per request, detik")
    ap.add_argument("--format", choices=["text", "json"], default="text", help="text (default) atau json gabungan")
    a = ap.parse_args(argv)
    text, gagal = (run_json if a.format == "json" else run)(a.symbol, a.level, a.timeout)
    print(text)
    return 2 if gagal else 0


if __name__ == "__main__":
    sys.exit(main())
