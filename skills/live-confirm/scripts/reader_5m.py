#!/usr/bin/env python3
"""
Reader 5m (fast confirm) — pembacaan struktur candle yang DETERMINISTIK dan konsisten.

Input : daftar candle (JSON) dari sumber publik, urut waktu apa pun.
        Baris array [ts_ms, open, high, low, close, volume, ...] atau objek
        {ts|time|timestamp, open|o, high|h, low|l, close|c, volume|vol|v}.
        PASTIKAN urutan kolom sumbermu cocok (beberapa bursa memakai urutan lain).
Output: pembacaan terstruktur (trend, volume, level S/R berlapis, status breakout/bounce).

Prinsip:
  - HANYA candle yang sudah tutup. Candle terakhir yang masih berjalan dibuang otomatis.
  - Semua ambang adalah parameter eksplisit; tidak ada "feeling".
  - Ini membaca kondisi, BUKAN sinyal beli/jual dan bukan prediksi.

Logika candle (parse, EMA, ATR, pivot, VWAP, read) tinggal di modul bersama
skills/_shared/candles.py dan diimpor dari sana — dulu diduplikasi di file ini.
Hanya library standar Python (3.8+).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Modul bersama: path relatif terhadap lokasi file ini (skills/live-confirm/scripts
# -> skills/_shared), bukan path absolut, supaya repo bisa dipindah/di-clone di mana saja.
_SHARED_DIR = Path(__file__).resolve().parents[2] / "_shared"
if str(_SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(_SHARED_DIR))
from candles import (  # noqa: E402
    WIB, VWAP_MIN_CANDLES, _f, _utc_date, atr, cluster, default_params,
    drop_forming, ema, parse_candles, pivots, read as _shared_read,
    session_vwap, shape, vol_label,
)

DEFAULTS: dict[str, Any] = default_params(5)


def read(candles: list[dict[str, float]], params: dict[str, Any] | None = None,
         now_ms: int | None = None, assume_closed: bool = False) -> dict[str, Any]:
    """Baca struktur candle 5m (delegasi ke modul bersama)."""
    p = {**DEFAULTS, **(params or {})}
    return _shared_read(candles, p, now_ms=now_ms, assume_closed=assume_closed)


# =================== bagian khusus 5m (fast confirm) ===================
UPPER_WICK_WEAK = 0.4   # sumbu atas >= ini dianggap penolakan di 5m


def idn(x: Any, dec: int | None = None) -> str:
    """Angka dengan koma desimal Indonesia."""
    if x is None:
        return "-"
    s = f"{x:.{dec}f}" if dec is not None else f"{x:.6g}"
    if "e" in s:
        s = f"{x:.10f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


def fast_verdict(closed: list[dict[str, float]], r: dict[str, Any]) -> dict[str, Any]:
    """Apakah gerakan 15m DITERUSKAN atau MELEMAH di 5m. Aturan eksplisit:
    kuat  = higher high (vs 3 candle sebelumnya), volume TINGGI, breakout terkonfirmasi/retest bertahan,
            candle bullish dengan close di dekat high.
    lemah = sumbu atas >= 0,4, volume RENDAH, penolakan sumbu, support jebol, candle bearish besar.
    MELEMAH bila ada lemah dan jumlah lemah >= jumlah kuat; DITERUSKAN bila higher high tanpa lemah; selain itu NETRAL."""
    last = closed[-1]
    hh = last["h"] > max(c["h"] for c in closed[-4:-1])
    lc, vol = r["last_candle"], r["volume"]["label"]
    bo, bn = r["breakout"]["state"], r["bounce"]["state"]
    kuat: list[str] = []
    lemah: list[str] = []
    if hh:
        kuat.append("higher high")
    if vol == "TINGGI":
        kuat.append("volume tinggi")
    if bo in ("BREAKOUT_TERKONFIRMASI", "RETEST_BERTAHAN"):
        kuat.append("breakout 5m terkonfirmasi" if bo == "BREAKOUT_TERKONFIRMASI" else "retest bertahan")
    if lc["bullish"] and lc["close_pos"] >= 0.7:
        kuat.append("close dekat high")
    if lc["upper_wick"] >= UPPER_WICK_WEAK:
        lemah.append("sumbu atas panjang")
    if vol == "RENDAH":
        lemah.append("volume turun")
    if bo == "PENOLAKAN_SUMBU":
        lemah.append("tembusan ditolak")
    if bn == "SUPPORT_JEBOL":
        lemah.append("support jebol")
    if (not lc["bullish"]) and lc["body_ratio"] >= 0.5:
        lemah.append("candle bearish besar")
    if lemah and len(lemah) >= len(kuat):
        status, kalimat = "MELEMAH", "5m: " + ", ".join(lemah) + " → melemah"
    elif hh and not lemah:
        status, kalimat = "DITERUSKAN", "5m: " + ", ".join(kuat) + " → diteruskan"
    else:
        ket = ", ".join(kuat + lemah) or "tidak ada tanda jelas"
        status, kalimat = "NETRAL", f"5m: {ket} → belum jelas (netral)"
    return {"status": status, "kuat": kuat, "lemah": lemah, "kalimat": kalimat}


def analyze(raw: list[Any], params: dict[str, Any] | None = None, now_ms: int | None = None,
            assume_closed: bool = False) -> dict[str, Any]:
    p = {**DEFAULTS, **(params or {})}
    candles = parse_candles(raw)
    dropped = False
    if not assume_closed:
        candles, dropped = drop_forming(candles, p["interval_min"], now_ms)
    res = read(candles, p, assume_closed=True)
    if dropped:
        res.setdefault("warnings", []).insert(0, "candle 5m terakhir masih berjalan dan dibuang dari analisis")
    if res.get("ok"):
        res["fast"] = fast_verdict(candles, res)
    return res


def to_line(r: dict[str, Any], symbol: str = "TOKEN") -> str:
    if not r.get("ok"):
        return f"{symbol}: tidak bisa dibaca — {r.get('reason')}" + "".join(f"\n⚠️ {w}" for w in r.get("warnings", []))
    b, bo = r["breakout"], r["bounce"]
    bt = b["state"] + (f" @ {idn(b['level'])}" if "level" in b else "")
    vw = ("VWAP " + ("di atas" if r["di_atas_vwap"] else "di bawah")) if r.get("vwap") is not None else "VWAP belum stabil"
    L = [f"{symbol} {idn(r['close'])} | tren 5m {r['trend']['state']} | ATR 5m {idn(r['atr'])} ({idn(r['atr_pct'], 2)}%) "
         f"| {vw} | breakout 5m: {bt} | bounce 5m: {bo['state']}", r["fast"]["kalimat"]]
    L += [f"⚠️ {w}" for w in r["warnings"]]
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Reader 5m — fast confirm (read-only, stdlib)")
    ap.add_argument("--file", required=True, help="JSON candle 5m (hasil API Bitget), atau '-' untuk stdin")
    ap.add_argument("--symbol", default="TOKEN", help="label token untuk output")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ap.add_argument("--last-closed", action="store_true", help="semua candle sudah tutup (jangan buang yang terakhir)")
    ap.add_argument("--now-ms", type=int, help="waktu acuan (ms) untuk menentukan candle berjalan")
    a = ap.parse_args(argv)
    raw = json.load(sys.stdin if a.file == "-" else open(a.file, encoding="utf-8"))
    if isinstance(raw, dict) and "data" in raw:
        raw = raw["data"]
    res = analyze(raw, now_ms=a.now_ms, assume_closed=a.last_closed)
    print(json.dumps(res, indent=2, ensure_ascii=False) if a.format == "json" else to_line(res, a.symbol))
    return 0 if res.get("ok") else 2


if __name__ == "__main__":
    sys.exit(main())
