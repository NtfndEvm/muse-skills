#!/usr/bin/env python3
"""Pengecek order book (depth) — read-only, stdlib saja.

Input : JSON dari GET /api/v2/spot/market/orderbook?symbol=<SYM>USDT&limit=50
        {"asks": [[harga, jumlah], ...], "bids": [[harga, jumlah], ...], "ts": ...}
        (boleh dibungkus {"code","data":{...}}). Harga/jumlah string -> float.
Output: spread, total bid/ask ±1%, imbalance, 3 tembok bid & ask, depth di --level (±0,3%).
Ini membaca kondisi, bukan sinyal dan bukan nasihat keuangan.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

BAND_PCT = 1.0        # jendela total bid/ask: ±1% dari harga tengah
LEVEL_PCT = 0.3       # jendela depth di level yang ditanyakan: ±0,3%
IMB_HIGH, IMB_LOW = 0.6, 0.4
THICK_RATIO = 1.0     # TEBAL bila depth level >= rasio × depth rata-rata (lihat verdict_level)


def idn(x: Any, dec: int | None = None) -> str:
    if x is None:
        return "-"
    s = f"{x:.{dec}f}" if dec is not None else f"{x:.6g}"
    if "e" in s:
        s = f"{x:.10f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


def idn_usdt(x: float) -> str:
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def parse_book(raw: Any) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
        raw = raw["data"]
    if not isinstance(raw, dict):
        raise ValueError("format order book tidak dikenali")
    bids = sorted(((float(p), float(q)) for p, q, *_ in raw.get("bids", [])), key=lambda x: -x[0])
    asks = sorted(((float(p), float(q)) for p, q, *_ in raw.get("asks", [])), key=lambda x: x[0])
    return bids, asks


def value(lv: tuple[float, float]) -> float:
    return lv[0] * lv[1]


def walls(levels: list[tuple[float, float]], n: int = 3) -> list[dict[str, float]]:
    top = sorted(levels, key=value, reverse=True)[:n]
    return [{"price": p, "usdt": p * q} for p, q in top]


def verdict_level(depth_side: float, ref: float, thick_ratio: float) -> str:
    return "TEBAL" if depth_side > 0 and depth_side >= ref * thick_ratio else "TIPIS"


def analyze(raw: Any, level: float | None = None, band_pct: float = BAND_PCT, level_pct: float = LEVEL_PCT,
            thick_ratio: float = THICK_RATIO) -> dict[str, Any]:
    try:
        bids, asks = parse_book(raw)
    except (ValueError, TypeError) as e:
        return {"ok": False, "reason": str(e), "warnings": []}
    if not bids or not asks:
        return {"ok": False, "reason": "order book kosong di salah satu sisi", "warnings": []}
    bb, ba = bids[0][0], asks[0][0]
    if bb >= ba:
        return {"ok": False, "reason": "order book bersilangan (best bid >= best ask), data tidak valid", "warnings": []}
    mid = (bb + ba) / 2
    warnings: list[str] = []
    spread = (ba - bb) / mid * 100
    lo, hi = mid * (1 - band_pct / 100), mid * (1 + band_pct / 100)
    tot_bid = sum(value(x) for x in bids if x[0] >= lo)
    tot_ask = sum(value(x) for x in asks if x[0] <= hi)
    imb = tot_bid / (tot_bid + tot_ask) if (tot_bid + tot_ask) > 0 else None
    imb_label = (None if imb is None else "BID DOMINAN" if imb > IMB_HIGH else "ASK DOMINAN" if imb < IMB_LOW else "SEIMBANG")
    if bids[-1][0] > lo:
        warnings.append(f"bid hanya mencakup sampai {idn((bids[-1][0] / mid - 1) * 100, 2)}% dari harga tengah; total bid ±{idn(band_pct)}% tidak lengkap")
    if asks[-1][0] < hi:
        warnings.append(f"ask hanya mencakup sampai +{idn((asks[-1][0] / mid - 1) * 100, 2)}% dari harga tengah; total ask ±{idn(band_pct)}% tidak lengkap")
    out: dict[str, Any] = {
        "ok": True, "warnings": warnings, "mid": mid, "best_bid": bb, "best_ask": ba, "spread_pct": spread,
        "total_bid_usdt": tot_bid, "total_ask_usdt": tot_ask, "imbalance": imb, "imbalance_label": imb_label,
        "tembok_bid": walls(bids), "tembok_ask": walls(asks), "level": None,
    }
    if level is not None:
        l_lo, l_hi = level * (1 - level_pct / 100), level * (1 + level_pct / 100)
        d_bid = sum(value(x) for x in bids if l_lo <= x[0] <= l_hi)
        d_ask = sum(value(x) for x in asks if l_lo <= x[0] <= l_hi)
        sisi = "bid" if level <= mid else "ask"
        ref = (tot_bid + tot_ask) / 2 * (2 * level_pct / band_pct)  # rata-rata per sisi × lebar jendela relatif
        luar = level < bids[-1][0] or level > asks[-1][0]
        v = "TIDAK TERUKUR" if luar else verdict_level(d_bid if sisi == "bid" else d_ask, ref, thick_ratio)
        if luar:
            warnings.append("level di luar jangkauan order book yang diambil; depth level tidak terukur (bukan berarti tipis)")
        out["level"] = {"price": level, "depth_bid_usdt": d_bid, "depth_ask_usdt": d_ask, "sisi": sisi,
                        "acuan_usdt": ref, "verdict": v}
    return out


def to_text(r: dict[str, Any], symbol: str = "TOKEN") -> str:
    if not r.get("ok"):
        return f"{symbol}: tidak bisa dibaca — {r.get('reason')}"
    L = [f"{symbol} order book | harga tengah {idn(r['mid'])} | spread {idn(r['spread_pct'], 3)}%",
         f"Total ±1%: bid {idn_usdt(r['total_bid_usdt'])} USDT · ask {idn_usdt(r['total_ask_usdt'])} USDT · "
         f"imbalance {idn(r['imbalance'], 2)} ({r['imbalance_label'] or 'tidak ada data'})",
         "Tembok bid: " + "; ".join(f"{idn(w['price'])} ({idn_usdt(w['usdt'])} USDT)" for w in r["tembok_bid"]),
         "Tembok ask: " + "; ".join(f"{idn(w['price'])} ({idn_usdt(w['usdt'])} USDT)" for w in r["tembok_ask"])]
    lv = r.get("level")
    if lv:
        L.append(f"Level {idn(lv['price'])} (±0,3%): bid {idn_usdt(lv['depth_bid_usdt'])} · ask {idn_usdt(lv['depth_ask_usdt'])} USDT "
                 f"→ {lv['verdict']} (sisi {lv['sisi']}, acuan {idn_usdt(lv['acuan_usdt'])} USDT)")
    L += [f"⚠️ {w}" for w in r["warnings"]]
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Pengecek order book (read-only, stdlib)")
    ap.add_argument("--file", required=True, help="JSON order book, atau '-' untuk stdin")
    ap.add_argument("--symbol", default="TOKEN")
    ap.add_argument("--level", type=float, help="harga level yang dicek tebal/tipis")
    ap.add_argument("--thick-ratio", type=float, default=THICK_RATIO)
    ap.add_argument("--format", choices=["text", "json"], default="text")
    a = ap.parse_args(argv)
    raw = json.load(sys.stdin if a.file == "-" else open(a.file, encoding="utf-8"))
    r = analyze(raw, level=a.level, thick_ratio=a.thick_ratio)
    print(json.dumps(r, indent=2, ensure_ascii=False) if a.format == "json" else to_text(r, a.symbol))
    return 0 if r.get("ok") else 2


if __name__ == "__main__":
    sys.exit(main())
