#!/usr/bin/env python3
"""Delta volume beli vs jual — read-only, stdlib saja.

Input : JSON dari GET /api/v2/spot/market/fills?symbol=<SYM>USDT&limit=100
        array {"tradeId","side":"buy"|"sell","price","size","ts"} (boleh dibungkus {"data":[...]}).
Output: volume beli/jual (USDT), delta %, jumlah trade, 3 trade terbesar, rentang waktu (WIB).
Ini membaca kondisi, bukan sinyal dan bukan nasihat keuangan.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

WIB = timezone(timedelta(hours=7))
MAX_TRADES = 100
DOMINAN_PCT = 10.0    # |delta| >= ini dianggap dominan; di bawahnya SEIMBANG
MIN_SAMPLE = 20


def idn(x: Any, dec: int | None = None) -> str:
    if x is None:
        return "-"
    s = f"{x:.{dec}f}" if dec is not None else f"{x:.6g}"
    if "e" in s:
        s = f"{x:.10f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


def idn_usdt(x: float) -> str:
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def wib(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, WIB).strftime("%Y-%m-%d %H:%M:%S")


def analyze(raw: Any, dominan_pct: float = DOMINAN_PCT, max_trades: int = MAX_TRADES) -> dict[str, Any]:
    if isinstance(raw, dict) and "data" in raw:
        raw = raw["data"]
    if not isinstance(raw, list):
        return {"ok": False, "reason": "format trade tidak dikenali", "warnings": []}
    trades, skipped = [], 0
    for t in raw:
        try:
            side = str(t["side"]).lower()
            if side not in ("buy", "sell"):
                raise ValueError
            ts = int(float(t["ts"]))
            if ts < 10**11:
                ts *= 1000
            trades.append({"side": side, "price": float(t["price"]), "usdt": float(t["price"]) * float(t["size"]), "ts": ts})
        except (KeyError, ValueError, TypeError):
            skipped += 1
    warnings: list[str] = []
    if skipped:
        warnings.append(f"{skipped} trade dilewati karena data tidak valid")
    trades.sort(key=lambda x: -x["ts"])
    trades = trades[:max_trades]
    if not trades:
        return {"ok": False, "reason": "tidak ada trade valid", "warnings": warnings}
    buy = sum(t["usdt"] for t in trades if t["side"] == "buy")
    sell = sum(t["usdt"] for t in trades if t["side"] == "sell")
    total = buy + sell
    delta = (buy - sell) / total * 100 if total > 0 else 0.0
    label = "BELI" if delta >= dominan_pct else "JUAL" if delta <= -dominan_pct else "SEIMBANG"
    if len(trades) < MIN_SAMPLE:
        warnings.append(f"sampel hanya {len(trades)} trade; delta kurang representatif")
    t_old, t_new = trades[-1]["ts"], trades[0]["ts"]
    return {"ok": True, "warnings": warnings, "n_trade": len(trades),
            "n_buy": sum(1 for t in trades if t["side"] == "buy"), "n_sell": sum(1 for t in trades if t["side"] == "sell"),
            "volume_beli_usdt": buy, "volume_jual_usdt": sell, "delta_pct": delta, "dominan": label,
            "trade_terbesar": [{"price": t["price"], "usdt": t["usdt"], "side": t["side"]}
                               for t in sorted(trades, key=lambda x: -x["usdt"])[:3]],
            "dari_wib": wib(t_old), "sampai_wib": wib(t_new), "durasi_detik": (t_new - t_old) / 1000}


def to_text(r: dict[str, Any], symbol: str = "TOKEN") -> str:
    if not r.get("ok"):
        return f"{symbol}: tidak bisa dibaca — {r.get('reason')}"
    kal = {"BELI": "agresi BELI dominan", "JUAL": "agresi JUAL dominan", "SEIMBANG": "agresi seimbang (tidak ada sisi dominan)"}[r["dominan"]]
    L = [f"{symbol} delta volume | {r['n_trade']} trade terakhir",
         f"Beli {idn_usdt(r['volume_beli_usdt'])} USDT ({r['n_buy']} trade) · Jual {idn_usdt(r['volume_jual_usdt'])} USDT ({r['n_sell']} trade) "
         f"· delta {idn(r['delta_pct'], 1)}%",
         "Trade terbesar: " + "; ".join(f"{idn(t['price'])} · {idn_usdt(t['usdt'])} USDT · {t['side']}" for t in r["trade_terbesar"]),
         f"Rentang: {r['dari_wib']} → {r['sampai_wib']} WIB ({idn(r['durasi_detik'], 0)} detik)",
         f"Kesimpulan: {kal}."]
    L += [f"⚠️ {w}" for w in r["warnings"]]
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Delta volume beli vs jual (read-only, stdlib)")
    ap.add_argument("--file", required=True, help="JSON trade, atau '-' untuk stdin")
    ap.add_argument("--symbol", default="TOKEN")
    ap.add_argument("--dominan", type=float, default=DOMINAN_PCT, help="ambang |delta|%% dianggap dominan")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    a = ap.parse_args(argv)
    raw = json.load(sys.stdin if a.file == "-" else open(a.file, encoding="utf-8"))
    r = analyze(raw, dominan_pct=a.dominan)
    print(json.dumps(r, indent=2, ensure_ascii=False) if a.format == "json" else to_text(r, a.symbol))
    return 0 if r.get("ok") else 2


if __name__ == "__main__":
    sys.exit(main())
