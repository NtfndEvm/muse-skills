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

Hanya library standar Python (3.8+).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any

WIB = timezone(timedelta(hours=7))

DEFAULTS: dict[str, Any] = {
    "interval_min": 15,
    "ema_fast": 20, "ema_slow": 50,
    "atr_n": 14,
    "pivot_k": 3,            # swing high/low butuh k candle pembanding di tiap sisi
    "tol_atr": 0.25,         # toleransi pengelompokan level & "menyentuh" level (× ATR)
    "vol_n": 20,             # rata-rata volume dari N candle SEBELUM candle terakhir
    "vol_high": 1.5,         # rasio volume dianggap tinggi
    "vol_low": 0.8,          # rasio volume dianggap rendah
    "body_min": 0.5,         # body / range minimum untuk breakout berkualitas
    "close_pos_min": 0.7,    # posisi close dalam range (0=low, 1=high) minimum untuk breakout
    "upper_wick_max": 0.35,  # sumbu atas maksimum untuk breakout berkualitas
    "buffer_atr": 0.1,       # penutupan harus melewati level + buffer (× ATR)
    "bounce_lookback": 3,    # cari candle bounce dalam N candle terakhir
    "layer_dist_atr": 4.0,   # resistance di atas dihitung "berlapis" jika dalam jarak ini
}


# ------------------------------------------------------------------ input
def _f(x: Any) -> float:
    return float(x)


def parse_candles(raw: list[Any]) -> list[dict[str, float]]:
    out: dict[int, dict[str, float]] = {}
    for row in raw:
        if isinstance(row, dict):
            g = lambda *keys: next((row[k] for k in keys if k in row), None)  # noqa: E731
            ts, o, h, l, c, v = (g("ts", "time", "timestamp", "t"), g("open", "o"), g("high", "h"),
                                 g("low", "l"), g("close", "c"), g("volume", "vol", "v"))
        else:
            ts, o, h, l, c, v = row[0], row[1], row[2], row[3], row[4], row[5]
        ts_i = int(float(ts))
        if ts_i < 10**11:  # detik -> ms
            ts_i *= 1000
        out[ts_i] = {"ts": ts_i, "o": _f(o), "h": _f(h), "l": _f(l), "c": _f(c), "v": _f(v)}
    return [out[k] for k in sorted(out)]


# ------------------------------------------------------------- indikator
def ema(values: list[float], n: int) -> list[float | None]:
    res: list[float | None] = [None] * len(values)
    if len(values) < n:
        return res
    seed = sum(values[:n]) / n
    res[n - 1] = seed
    k = 2 / (n + 1)
    prev = seed
    for i in range(n, len(values)):
        prev = values[i] * k + prev * (1 - k)
        res[i] = prev
    return res


def atr(candles: list[dict[str, float]], n: int) -> list[float | None]:
    res: list[float | None] = [None] * len(candles)
    if len(candles) <= n:
        return res
    tr = [0.0] * len(candles)
    for i in range(1, len(candles)):
        c, p = candles[i], candles[i - 1]
        tr[i] = max(c["h"] - c["l"], abs(c["h"] - p["c"]), abs(c["l"] - p["c"]))
    prev = sum(tr[1:n + 1]) / n
    res[n] = prev
    for i in range(n + 1, len(candles)):
        prev = (prev * (n - 1) + tr[i]) / n
        res[i] = prev
    return res


def pivots(candles: list[dict[str, float]], k: int) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    highs, lows = [], []
    for i in range(k, len(candles) - k):
        h = candles[i]["h"]
        if all(h > candles[j]["h"] for j in range(i - k, i)) and all(h >= candles[j]["h"] for j in range(i + 1, i + k + 1)):
            highs.append((i, h))
        lo = candles[i]["l"]
        if all(lo < candles[j]["l"] for j in range(i - k, i)) and all(lo <= candles[j]["l"] for j in range(i + 1, i + k + 1)):
            lows.append((i, lo))
    return highs, lows


def cluster(points: list[tuple[int, float]], tol: float) -> list[dict[str, Any]]:
    groups: list[list[tuple[int, float]]] = []
    for idx, price in sorted(points, key=lambda p: p[1]):
        if groups:
            mean = sum(p[1] for p in groups[-1]) / len(groups[-1])
            if abs(price - mean) <= tol:
                groups[-1].append((idx, price))
                continue
        groups.append([(idx, price)])
    return [{"price": sum(p[1] for p in g) / len(g), "touches": len(g), "last_index": max(p[0] for p in g)}
            for g in groups]


# -------------------------------------------------------- bentuk candle
def shape(c: dict[str, float]) -> dict[str, float]:
    rng = c["h"] - c["l"]
    if rng <= 0:
        return {"range": 0.0, "body_ratio": 0.0, "close_pos": 0.5, "upper_wick": 0.0, "lower_wick": 0.0,
                "bullish": c["c"] > c["o"]}
    return {"range": rng,
            "body_ratio": abs(c["c"] - c["o"]) / rng,
            "close_pos": (c["c"] - c["l"]) / rng,
            "upper_wick": (c["h"] - max(c["o"], c["c"])) / rng,
            "lower_wick": (min(c["o"], c["c"]) - c["l"]) / rng,
            "bullish": c["c"] > c["o"]}


def vol_label(ratio: float | None, p: dict[str, Any]) -> str:
    if ratio is None:
        return "TIDAK_ADA_DATA"
    return "TINGGI" if ratio >= p["vol_high"] else "RENDAH" if ratio < p["vol_low"] else "NORMAL"


# -------------------------------------------------------------- pembacaan
def drop_forming(candles: list[dict[str, float]], interval_min: int, now_ms: int | None) -> tuple[list[dict[str, float]], bool]:
    now_ms = int(time.time() * 1000) if now_ms is None else now_ms
    if candles and candles[-1]["ts"] + interval_min * 60_000 > now_ms:
        return candles[:-1], True
    return candles, False


def read(candles: list[dict[str, float]], params: dict[str, Any] | None = None,
         now_ms: int | None = None, assume_closed: bool = False) -> dict[str, Any]:
    p = {**DEFAULTS, **(params or {})}
    warnings: list[str] = []
    dropped = False
    if not assume_closed:
        candles, dropped = drop_forming(candles, p["interval_min"], now_ms)
        if dropped:
            warnings.append("candle terakhir masih berjalan dan dibuang dari analisis")

    min_needed = max(p["ema_slow"] + 5, p["vol_n"] + 2, p["atr_n"] + 2, 4 * p["pivot_k"] + 3) + 20
    if len(candles) < min_needed:
        return {"ok": False, "reason": f"data kurang: {len(candles)} candle, butuh ≥ {min_needed}",
                "warnings": warnings}

    # celah waktu
    step = p["interval_min"] * 60_000
    gaps = sum(1 for i in range(1, len(candles)) if candles[i]["ts"] - candles[i - 1]["ts"] > step * 1.5)
    if gaps:
        warnings.append(f"ada {gaps} celah waktu antar candle; indikator bisa kurang akurat")

    closes = [c["c"] for c in candles]
    last, prev = candles[-1], candles[-2]
    i_last = len(candles) - 1
    e_fast, e_slow = ema(closes, p["ema_fast"]), ema(closes, p["ema_slow"])
    a = atr(candles, p["atr_n"])[i_last]
    if not a or a <= 0:
        return {"ok": False, "reason": "ATR tidak valid (harga datar/data buruk)", "warnings": warnings}
    tol, buf = p["tol_atr"] * a, p["buffer_atr"] * a

    # volume: rasio vs rata-rata N candle sebelum candle terakhir
    base = [c["v"] for c in candles[-p["vol_n"] - 1:-1]]
    vavg = sum(base) / len(base) if base else 0
    vratio = (last["v"] / vavg) if vavg > 0 else None
    if vratio is None:
        warnings.append("volume rata-rata nol/tidak tersedia; rasio volume tidak dihitung")

    # trend
    ef, es = e_fast[i_last], e_slow[i_last]
    ef_prev = e_fast[i_last - 5]
    slope = (ef - ef_prev) / a if ef is not None and ef_prev is not None else 0.0
    if last["c"] > ef > es and slope > 0:
        trend = "UPTREND"
    elif last["c"] < ef < es and slope < 0:
        trend = "DOWNTREND"
    else:
        trend = "RANGE/CAMPUR"

    # level
    hi_pts, lo_pts = pivots(candles, p["pivot_k"])
    res_all = cluster(hi_pts, tol)
    sup_all = cluster(lo_pts, tol)
    close = last["c"]
    above = sorted([r for r in res_all if r["price"] > close], key=lambda r: r["price"])
    below = sorted([s for s in sup_all if s["price"] < close], key=lambda s: -s["price"])
    layers = [{"price": round(r["price"], 8), "touches": r["touches"],
               "dist_atr": round((r["price"] - close) / a, 2),
               "dist_pct": round((r["price"] / close - 1) * 100, 2)} for r in above[:4]]
    layered = sum(1 for r in above if (r["price"] - close) / a <= p["layer_dist_atr"]) >= 2

    ls, pv = shape(last), shape(prev)

    # ---------------- breakout ----------------
    breakout: dict[str, Any] = {"state": "TIDAK_ADA"}
    cands = [r for r in res_all if abs(r["price"] - close) <= 2 * a or r["price"] < close and close - r["price"] <= 3 * a]
    for r in sorted(cands, key=lambda r: abs(r["price"] - close)):
        lvl = r["price"]
        thr = lvl + buf
        first_close_above = last["c"] > thr and prev["c"] <= thr
        if first_close_above:
            fails = []
            if vratio is None or vratio < p["vol_high"]:
                fails.append("volume belum tinggi")
            if ls["body_ratio"] < p["body_min"]:
                fails.append("body kecil")
            if ls["close_pos"] < p["close_pos_min"]:
                fails.append("close tidak di dekat high")
            if ls["upper_wick"] > p["upper_wick_max"]:
                fails.append("sumbu atas panjang")
            breakout = {"state": "BREAKOUT_TERKONFIRMASI" if not fails else "BREAKOUT_LEMAH",
                        "level": lvl, "touches": r["touches"], "kekurangan": fails}
            break
        if last["h"] > thr and last["c"] <= thr and ls["upper_wick"] >= 0.4:
            breakout = {"state": "PENOLAKAN_SUMBU", "level": lvl, "touches": r["touches"],
                        "kekurangan": ["high menembus level tetapi close kembali di bawah"]}
            break
        # retest hold: dalam 5 candle terakhir ada first-close-above, kini retest & bertahan
        recent = candles[-6:-1]
        crossed_recent = any(recent[j]["c"] > thr and (recent[j - 1]["c"] if j else candles[-7]["c"]) <= thr
                             for j in range(len(recent)))
        if crossed_recent and last["l"] <= lvl + tol and last["c"] > thr and last["c"] > last["o"]:
            breakout = {"state": "RETEST_BERTAHAN", "level": lvl, "touches": r["touches"], "kekurangan": []}
            break

    # ---------------- bounce ----------------
    bounce: dict[str, Any] = {"state": "TIDAK_ADA"}
    supports = [{"name": f"swing@{s['price']:.8g}", "price": s["price"], "touches": s["touches"], "type": "swing"}
                for s in sup_all if s["price"] <= close]
    if ef is not None and ef <= close:
        supports.append({"name": f"EMA{p['ema_fast']}", "price": ef, "touches": 0, "type": "ema"})
    if es is not None and es <= close:
        supports.append({"name": f"EMA{p['ema_slow']}", "price": es, "touches": 0, "type": "ema"})
    best = None
    for s in sorted(supports, key=lambda s: (s["type"] != "swing", -s["touches"], -s["price"])):
        sp = s["price"]
        for back in range(min(p["bounce_lookback"], len(candles) - 1)):
            idx = i_last - back
            c = candles[idx]
            sh = shape(c)
            touched = c["l"] <= sp + tol and c["l"] >= sp - 1.5 * a
            reclaimed = c["c"] >= sp
            reaction = c["c"] > c["o"] and (sh["lower_wick"] >= 0.3 or sh["close_pos"] >= 0.6)
            if touched and reclaimed and reaction:
                after = candles[idx + 1:]
                broken = any(x["c"] < sp - buf for x in after)
                confirmed = bool(after) and last["c"] > c["h"] and not broken
                bvr = (c["v"] / vavg) if vavg > 0 else None
                state = ("SUPPORT_JEBOL" if broken else
                         "BOUNCE_TERKONFIRMASI" if confirmed else "KANDIDAT_BOUNCE")
                best = {"state": state, "support": s["name"], "support_price": sp, "support_touches": s["touches"],
                        "bounce_candle_ts_wib": datetime.fromtimestamp(c["ts"] / 1000, WIB).strftime("%Y-%m-%d %H:%M"),
                        "bounce_high": c["h"], "volume_ratio": round(bvr, 2) if bvr is not None else None,
                        "volume": vol_label(bvr, p),
                        "catatan": ("tunggu candle berikutnya tutup di atas high candle bounce"
                                    if state == "KANDIDAT_BOUNCE" else "")}
                break
        if best:
            break
    if best:
        bounce = best
    else:
        for s in supports:  # support patah baru saja?
            if prev["c"] >= s["price"] - buf and last["c"] < s["price"] - buf and s["type"] == "swing":
                bounce = {"state": "SUPPORT_JEBOL", "support": s["name"], "support_price": s["price"]}
                break

    return {
        "ok": True, "warnings": warnings,
        "last_closed_wib": datetime.fromtimestamp(last["ts"] / 1000, WIB).strftime("%Y-%m-%d %H:%M"),
        "close": close, "atr": a, "atr_pct": round(a / close * 100, 3),
        "trend": {"state": trend, "ema_fast": ef, "ema_slow": es, "slope_atr_5c": round(slope, 3),
                  "close_vs_ema_fast": "di atas" if close > ef else "di bawah"},
        "volume": {"ratio": round(vratio, 2) if vratio is not None else None, "label": vol_label(vratio, p)},
        "last_candle": {k: (round(v, 3) if isinstance(v, float) else v) for k, v in ls.items() if k != "range"},
        "resistance": {"berlapis": layered, "level_di_atas": layers},
        "support_terdekat": [{"price": round(s["price"], 8), "touches": s["touches"],
                              "dist_atr": round((close - s["price"]) / a, 2)} for s in below[:3]],
        "breakout": breakout, "bounce": bounce, "params": {k: p[k] for k in p},
    }


def to_text(r: dict[str, Any]) -> str:
    if not r.get("ok"):
        return f"Tidak bisa dibaca: {r.get('reason')}\n" + "\n".join(f"⚠️ {w}" for w in r.get("warnings", []))
    L = [f"Candle tutup terakhir: {r['last_closed_wib']} WIB · close {r['close']} · ATR {r['atr']:.6g} ({r['atr_pct']}%)"]
    t = r["trend"]
    L.append(f"Trend: {t['state']} (close {t['close_vs_ema_fast']} EMA cepat, slope {t['slope_atr_5c']} ATR/5c)")
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
