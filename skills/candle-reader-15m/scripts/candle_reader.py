#!/usr/bin/env python3
"""
Candle Reader 15m — pembacaan struktur candle yang DETERMINISTIK dan konsisten.

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
skills/_shared/candles.py dan diimpor dari sana — jangan ditulis ulang di sini.
Hanya library standar Python (3.8+).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Modul bersama: path relatif terhadap lokasi file ini (skills/candle-reader-15m/scripts
# -> skills/_shared), bukan path absolut, supaya repo bisa dipindah/di-clone di mana saja.
_SHARED_DIR = Path(__file__).resolve().parents[2] / "_shared"
if str(_SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(_SHARED_DIR))
from candles import (  # noqa: E402
    WIB, VWAP_MIN_CANDLES, _f, _utc_date, atr, cluster, default_params,
    drop_forming, ema, parse_candles, pivots, read as _shared_read,
    session_vwap, shape, vol_label,
)

DEFAULTS: dict[str, Any] = default_params(15)


def read(candles: list[dict[str, float]], params: dict[str, Any] | None = None,
         now_ms: int | None = None, assume_closed: bool = False) -> dict[str, Any]:
    """Baca struktur candle 15m (delegasi ke modul bersama)."""
    p = {**DEFAULTS, **(params or {})}
    return _shared_read(candles, p, now_ms=now_ms, assume_closed=assume_closed)


def to_text(r: dict[str, Any]) -> str:
    if not r.get("ok"):
        return f"Tidak bisa dibaca: {r.get('reason')}\n" + "\n".join(f"⚠️ {w}" for w in r.get("warnings", []))
    L = [f"Candle tutup terakhir: {r['last_closed_wib']} WIB · close {r['close']} · ATR {r['atr']:.6g} ({r['atr_pct']}%)"]
    t = r["trend"]
    L.append(f"Trend: {t['state']} (close {t['close_vs_ema_fast']} EMA cepat, slope {t['slope_atr_5c']} ATR/5c)")
    if r.get("vwap") is not None:
        L.append(f"VWAP sesi (00:00 UTC): {r['vwap']:.6g} · harga {'di atas' if r['di_atas_vwap'] else 'di bawah'} "
                 f"VWAP ({r['vwap_jarak_atr']:+} ATR, {r['vwap_n_candle']} candle sesi)")
    else:
        L.append(f"VWAP sesi (00:00 UTC): {r.get('vwap_label') or 'tidak tersedia'} ({r.get('vwap_n_candle', 0)} candle sesi)")
    L.append(f"Volume candle terakhir: {r['volume']['label']} (rasio {r['volume']['ratio']})")
    lc = r["last_candle"]
    L.append(f"Bentuk: body {lc['body_ratio']}, close_pos {lc['close_pos']}, sumbu atas {lc['upper_wick']}, "
             f"sumbu bawah {lc['lower_wick']}, {'bullish' if lc['bullish'] else 'bearish'}")
    res = r["resistance"]
    L.append("Resistance di atas: " + ("; ".join(f"{x['price']} ({x['touches']}x, {x['dist_atr']} ATR, +{x['dist_pct']}%)"
                                               for x in res["level_di_atas"]) or "tidak terdeteksi")
             + (" → BERLAPIS" if res["berlapis"] else ""))
    L.append("Support di bawah: " + ("; ".join(f"{x['price']} ({x['touches']}x, {x['dist_atr']} ATR)"
                                              for x in r["support_terdekat"]) or "tidak terdeteksi"))
    b = r["breakout"]
    L.append(f"Breakout: {b['state']}" + (f" @ {b['level']:.6g} ({b['touches']}x)" if "level" in b else "")
             + (f" — kurang: {', '.join(b['kekurangan'])}" if b.get("kekurangan") else ""))
    bo = r["bounce"]
    L.append(f"Bounce: {bo['state']}" + (f" di {bo['support']} ({bo.get('support_price'):.6g})" if "support" in bo else "")
             + (f" — {bo['catatan']}" if bo.get("catatan") else ""))
    L += [f"⚠️ {w}" for w in r["warnings"]]
    L.append("Catatan: pembacaan kondisi, bukan sinyal dan bukan nasihat keuangan.")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Candle reader 15m (deterministik)")
    ap.add_argument("--file", required=True, help="JSON candle, atau '-' untuk stdin")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ap.add_argument("--last-closed", action="store_true", help="semua candle sudah tutup (jangan buang yang terakhir)")
    ap.add_argument("--now-ms", type=int, help="waktu acuan (ms) untuk menentukan candle berjalan")
    for k, v in DEFAULTS.items():
        ap.add_argument(f"--{k.replace('_', '-')}", type=type(v), default=v)
    a = ap.parse_args(argv)
    raw = json.load(sys.stdin if a.file == "-" else open(a.file, encoding="utf-8"))
    if isinstance(raw, dict) and "data" in raw:
        raw = raw["data"]
    params = {k: getattr(a, k) for k in DEFAULTS}
    res = read(parse_candles(raw), params, now_ms=a.now_ms, assume_closed=a.last_closed)
    print(json.dumps(res, indent=2, ensure_ascii=False) if a.format == "json" else to_text(res))
    return 0 if res.get("ok") else 2


if __name__ == "__main__":
    sys.exit(main())
