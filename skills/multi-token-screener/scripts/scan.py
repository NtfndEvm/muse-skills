#!/usr/bin/env python3
"""scan.py - pemindai token 15m sekali jalan. Hanya stdlib, tanpa API key.

Hanya MEMBACA data publik Bitget (GET) dan menulis file lokal (--json, watchlist.json).
Tidak ada order, wallet, signing, atau kredensial.

  python scan.py BEAM DOS KGEN ARIA
  python scan.py --watchlist
  python scan.py --discover 6 --skip DOS,CYBER
  python scan.py BEAM --json out.json

Logika candle (EMA, ATR, pivot, breakout, bounce) TIDAK ditulis ulang di sini:
dipanggil dari candle_reader.read(). Satu-satunya titik kontak ada di
`call_reader()` + `normalize_reading()`; bila bentuk keluaran read() berbeda dari
yang diasumsikan, cukup ubah dua fungsi itu.
"""

import argparse
import importlib
import inspect
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import vwap as vwap_mod  # noqa: E402

WIB = timezone(timedelta(hours=7))
BASE_URL = "https://api.bitget.com"
CANDLE_MS = 15 * 60 * 1000
MIN_CANDLES = 75
MIN_VOLUME = 100_000.0
MAX_SPREAD_NET_RR = 1.5
ROOM_MIN_PCT = 4.0   # ruang ke resistance terdekat minimal = target R:R 1:2 untuk stop 2%
STALE_MS = 15 * 60 * 1000
VOL_RATIO_HIGH = 1.5

BIG_CAPS = {"BTC", "ETH", "BNB", "SOL", "XRP"}
# Saham tokenisasi (prefiks R). Daftar blokir eksplisit; bila ragu token diikutkan
# dan dibiarkan digugurkan oleh verdict.
TOKENIZED_STOCKS = {
    "RNVDA", "RSPY", "RQQQ", "RMU", "RAMD", "RMSFT", "RSPCX", "RSNDK", "RAAPL", "RSOXL",
    "RTSLA", "RGOOG", "RGOOGL", "RAMZN", "RMETA", "RCOIN", "RMSTR", "RNFLX", "RINTC",
    "RPLTR", "RHOOD", "RCRCL", "RAVGO", "RTSM", "RORCL", "RARKK", "RIWM", "RDIA", "RSMH",
}

DEFAULT_WATCHLIST = [
    {"symbol": "BEAM", "trigger": "close_di_atas", "level": 0.004526, "note": "breakout"},
    {"symbol": "DOS", "trigger": "close_di_atas", "level": 0.1742, "note": "breakout"},
    {"symbol": "UAI", "trigger": "close_di_atas", "level": 0.0427, "note": "breakout"},
    {"symbol": "CYBER", "trigger": "close_di_atas", "level": 0.2771, "note": "breakout"},
    {"symbol": "AIO", "trigger": "close_di_atas", "level": 0.0449, "note": "breakout"},
    {"symbol": "BR", "trigger": "close_di_atas", "level": 0.4998, "note": "breakout"},
]
TRIGGERS = {"close_di_atas", "close_di_bawah", "bounce_di"}


class FetchError(Exception):
    pass


# --------------------------------------------------------------- jaringan

def http_get_json(url, timeout=15):
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                               "User-Agent": "muse-scan/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = json.loads(exc.read().decode("utf-8")).get("msg", "")
        except Exception:
            pass
        raise FetchError(f"HTTP {exc.code} {detail}".strip()) from None
    except urllib.error.URLError as exc:
        raise FetchError(f"jaringan: {exc.reason}") from None
    except (ValueError, TimeoutError, OSError) as exc:
        raise FetchError(f"respons rusak/timeout: {exc}") from None


def fetch_data(url, sleep=time.sleep):
    """GET + cek kode API; coba sekali lagi setelah 2 detik bila gagal."""
    last = None
    for attempt in range(2):
        try:
            body = http_get_json(url)
            if not isinstance(body, dict) or str(body.get("code", "00000")) != "00000":
                raise FetchError(f"API {body.get('code')}: {body.get('msg')}" if isinstance(body, dict)
                                 else "respons bukan objek JSON")
            return body.get("data")
        except FetchError as exc:
            last = exc
            if attempt == 0:
                sleep(2)
    raise last


# ---------------------------------------------------------------- parsing

def _f(x, default=0.0):
    try:
        v = float(x)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def parse_ticker(item):
    last, bid, ask = _f(item.get("lastPr")), _f(item.get("bidPr")), _f(item.get("askPr"))
    book_rusak = bid <= 0 or ask <= 0 or last <= 0
    return {
        "symbol": str(item.get("symbol", "")).upper(),
        "last": last, "volume24h": _f(item.get("usdtVolume")),
        "change24h": _f(item.get("change24h")),
        "bid": bid, "ask": ask, "high24h": _f(item.get("high24h")), "low24h": _f(item.get("low24h")),
        "book_rusak": book_rusak,
        "spread_pct": None if book_rusak else (ask - bid) / last * 100,
    }


def parse_candles(data):
    """[[ts_ms, o, h, l, c, base_vol]] urut naik menurut timestamp (jangan andalkan urutan API)."""
    seen = {}
    for row in data or []:
        try:
            ts = int(float(row[0]))
        except (TypeError, ValueError, IndexError):
            continue
        if len(row) < 6:
            continue
        seen[ts] = [ts, _f(row[1]), _f(row[2]), _f(row[3]), _f(row[4]), _f(row[5])]
    return [seen[k] for k in sorted(seen)]


def norm_symbol(raw):
    s = raw.strip().upper()
    if s.endswith("USDT") and len(s) > 4:
        s = s[:-4]
    return s


def is_tokenized_stock(base):
    return base in TOKENIZED_STOCKS


def volume_status(volume, base, user_suggested):
    if volume >= MIN_VOLUME:
        return "LOLOS"
    return "LOLOS BERSYARAT" if base in user_suggested else "GUGUR"


def break_even_pct(spread_pct):
    return 0.1 + 0.1 + spread_pct


def net_rr_stop2(spread_pct):
    be = break_even_pct(spread_pct)
    return (4 - be) / (2 + be)


# ----------------------------------------------------------- candle_reader

_reader = None


def load_reader():
    """Muat candle_reader.py. Urutan: env CANDLE_READER_DIR, ../../candle-reader-15m/scripts, ~/workspace/..."""
    global _reader
    if _reader is not None:
        return _reader
    dirs = [os.environ.get("CANDLE_READER_DIR"),
            str(HERE.parents[1] / "candle-reader-15m" / "scripts"),
            str(Path("~/workspace/custom-skills/candle-reader-15m/scripts").expanduser())]
    for d in dirs:
        if d and (Path(d) / "candle_reader.py").exists():
            sys.path.insert(0, d)
            _reader = importlib.import_module("candle_reader")
            return _reader
    return None


def _accepts_now_ms(fn):
    try:
        return "now_ms" in inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False


def call_reader(reader, candles, now_ms=None):
    """Panggil candle_reader.read() ASLI (~/workspace/.../candle-reader-15m).

    Bentuk asli (sudah dicocokkan 12 Nov 2026 di VM):
    - input: list dict {"ts","o","h","l","c","v"} — BUKAN list [ts,o,h,l,c,v].
      Pakai reader.parse_candles() untuk mengubah baris list jadi dict
      (sekaligus dedupe + urut naik); fallback manual bila tidak ada.
    - output: dict dengan "ok" (False bila data kurang/ATR tidak valid),
      trend/resistance/support BERTINGKAT (dict), breakout/bounce dict
      dengan "state". Lihat normalize_reading().
    - candle berjalan dibuang sendiri oleh read() (drop_forming).
    - now_ms diteruskan ke read(now_ms=...) bila read() menerimanya, supaya penentuan
      candle berjalan memakai waktu acuan yang SAMA dengan scan.py (penting untuk tes
      dengan data tersimpan; di produksi nilainya sama dengan jam dinding).
    """
    if hasattr(reader, "parse_candles"):
        parsed = reader.parse_candles(candles)
    else:
        parsed = [{"ts": int(r[0]), "o": float(r[1]), "h": float(r[2]),
                   "l": float(r[3]), "c": float(r[4]), "v": float(r[5])} for r in candles]
    if now_ms is not None and _accepts_now_ms(reader.read):
        res = reader.read(parsed, now_ms=now_ms)
    else:
        res = reader.read(parsed)
    if isinstance(res, dict) and res.get("ok") is False:
        raise ValueError(res.get("reason") or "candle_reader gagal membaca")
    return res


def _get(d, *names):
    for n in names:
        if isinstance(d, dict) and n in d:
            return d[n]
    return None


def _status(x):
    if isinstance(x, dict):
        x = _get(x, "status", "state", "hasil")
    return str(x) if x is not None else "TIDAK_ADA"


def _levels(x):
    """Daftar level -> [(harga, jarak_atr|None)]. Terima list angka atau list dict/tuple."""
    out = []
    for it in x or []:
        if isinstance(it, (int, float)):
            out.append((float(it), None))
        elif isinstance(it, dict):
            p = _get(it, "harga", "price", "level")
            if p is not None:
                out.append((float(p), _get(it, "jarak_atr", "atr", "dist_atr")))
        elif isinstance(it, (list, tuple)) and it:
            out.append((float(it[0]), it[1] if len(it) > 1 else None))
    return out


def normalize_reading(res):
    """Ubah keluaran read() jadi bentuk tetap untuk scan.py. Toleran terhadap nama field.

    Bentuk ASLI candle_reader.py (dicocokkan 12 Nov 2026):
    - trend: dict {"state": "UPTREND"/"DOWNTREND"/"RANGE/CAMPUR",
      "ema_fast", "ema_slow", ...} — BUKAN string.
    - resistance: dict {"berlapis": bool, "level_di_atas": [{"price","touches",
      "dist_atr","dist_pct"}, ...]} — BUKAN list.
    - support terdekat: "support_terdekat": [{"price","touches","dist_atr"}, ...].
    - bounce: dict {"state", "support", "support_price", "bounce_high", ...};
      level bounce = "support_price".
    Bentuk lain (string/list datar) tetap diterima apa adanya.
    """
    if not isinstance(res, dict):
        res = dict(getattr(res, "__dict__", {}))
    trend = _get(res, "trend", "tren")
    if isinstance(trend, dict):
        trend_state = trend.get("state") or trend.get("status") or "?"
        ema20 = trend.get("ema_fast")
        ema50 = trend.get("ema_slow")
    else:
        trend_state = trend
        ema20 = _get(res, "ema20", "ema_20")
        ema50 = _get(res, "ema50", "ema_50")
    res_d = _get(res, "resistance", "resistances")
    if isinstance(res_d, dict):
        res_levels = res_d.get("level_di_atas") or res_d.get("levels") or []
    else:
        res_levels = res_d
    sup_d = _get(res, "support", "supports", "support_terdekat")
    if isinstance(sup_d, dict):
        sup_levels = sup_d.get("level_di_bawah") or sup_d.get("levels") or []
    else:
        sup_levels = sup_d
    bounce = _get(res, "bounce")
    bounce_level = None
    if isinstance(bounce, dict):
        bounce_level = _get(bounce, "level", "harga", "price", "support_price")
    return {
        "trend": str(trend_state or "?").upper(),
        "breakout": _status(_get(res, "breakout")),
        "bounce": _status(bounce),
        "bounce_level": bounce_level,
        "resistance": _levels(res_levels),
        "support": _levels(sup_levels),
        "atr": _get(res, "atr"),
        "atr_pct": _get(res, "atr_pct"),
        "ema20": ema20,
        "ema50": ema50,
        "vwap": _get(res, "vwap"),
        "vwap_jarak_atr": _get(res, "vwap_jarak_atr"),
        "raw": res,
    }


def vwap_bounce(closed, vwap_value):
    """Addendum: candle tutup hijau di atas VWAP setelah menyentuhnya, volume >= 1,5x rata-rata 20 sebelumnya."""
    if vwap_value is None or len(closed) < 22:
        return False
    c = closed[-1]
    prev = [x[5] for x in closed[-21:-1]]
    avg = sum(prev) / len(prev) if prev else 0
    return c[4] > c[1] and c[3] <= vwap_value < c[4] and avg > 0 and c[5] / avg >= VOL_RATIO_HIGH


# ----------------------------------------------------------------- verdict

def decide(info):
    """(label, alasan). label: LOLOS / PANTAU / DITOLAK / status khusus."""
    if info["status"] != "OK":
        return info["status"], info.get("alasan", "")
    if info["base"] in BIG_CAPS:
        return "DITOLAK", "big cap, tidak dianalisa"
    if info["volume_status"] == "GUGUR":
        return "DITOLAK", f"volume 24j ${info['volume24h']:,.0f} < $100.000".replace(",", ".")
    if info["net_rr_stop2"] < MAX_SPREAD_NET_RR:
        return "DITOLAK", f"spread {fmt_pct(info['spread_pct'], 3, sign=False)} membuat net R:R stop 2% hanya {fmt_num(info['net_rr_stop2'], 2)}"
    if info.get("reader_missing"):
        return "PANTAU", "candle_reader.py tidak ditemukan; struktur 15m belum dibaca"

    bo, bn = info["breakout"], info["bounce"]
    confirmed = bo == "BREAKOUT_TERKONFIRMASI" or bn == "BOUNCE_TERKONFIRMASI" or info.get("vwap_bounce")
    candidate = bn == "KANDIDAT_BOUNCE" or bo in ("BREAKOUT_LEMAH", "RETEST_BERTAHAN")
    if bn == "SUPPORT_JEBOL":
        return "DITOLAK", "support jebol"
    if bo == "PENOLAKAN_SUMBU":
        return "DITOLAK", "penolakan sumbu di resistance"

    room = info.get("room_pct")
    if (confirmed or candidate) and room is not None and room < ROOM_MIN_PCT:
        return "DITOLAK", f"ruang ke resistance cuma {fmt_pct(room, 1)} < target {ROOM_MIN_PCT:.0f}%"
    if confirmed:
        setup = "VWAP bounce" if info.get("vwap_bounce") and bn != "BOUNCE_TERKONFIRMASI" and bo != "BREAKOUT_TERKONFIRMASI" \
            else ("breakout" if bo == "BREAKOUT_TERKONFIRMASI" else "bounce")
        return "LOLOS", f"{setup} terkonfirmasi"
    if candidate:
        trig = {"KANDIDAT_BOUNCE": "tunggu candle konfirmasi bounce tutup",
                "BREAKOUT_LEMAH": "tunggu volume >= 1,5x dan tutup di atas level",
                "RETEST_BERTAHAN": "tunggu candle konfirmasi dari retest"}
        return "PANTAU", trig.get(bn if bn in trig else bo, "tunggu konfirmasi")
    if info["trend"].startswith("UP"):
        a, b = info.get("ema20"), info.get("ema50")
        if a and b:
            lo, hi = sorted((float(a), float(b)))
            return "PANTAU", f"pullback ke EMA 20/50 ${fmt_price(lo)}-${fmt_price(hi)}"
        return "PANTAU", "tunggu pullback ke EMA 20/50 atau VWAP"
    return "DITOLAK", "tidak ada setup"


# ----------------------------------------------------------- analisa token

def analyze(base, tickers, base_url, user_suggested, now_ms, fetcher=fetch_data):
    info = {"symbol": base, "base": base, "status": "OK", "checked_ms": now_ms}
    tk = tickers.get(base + "USDT") if tickers is not None else None
    if tickers is None:
        info.update(status="GAGAL AMBIL DATA", alasan="daftar ticker tidak bisa diambil")
        return finish(info)
    if tk is None:
        info.update(status="TIDAK DITEMUKAN", alasan="simbol tidak ada di bursa")
        return finish(info)
    info.update({k: tk[k] for k in ("last", "volume24h", "change24h", "spread_pct", "high24h", "low24h")})
    if tk["book_rusak"]:
        info.update(status="BOOK RUSAK", alasan="bid/ask 0, order book tidak bisa dipercaya")
        return finish(info)
    info["break_even_pct"] = break_even_pct(tk["spread_pct"])
    info["net_rr_stop2"] = net_rr_stop2(tk["spread_pct"])
    info["volume_status"] = volume_status(tk["volume24h"], base, user_suggested)

    url = (f"{base_url}/api/v2/spot/market/candles?symbol={urllib.parse.quote(base)}USDT"
           f"&granularity=15min&limit=100")
    try:
        candles = parse_candles(fetcher(url))
    except FetchError as exc:
        info.update(status="GAGAL AMBIL DATA", alasan=str(exc))
        return finish(info)
    closed = [c for c in candles if c[0] + CANDLE_MS <= now_ms]
    info["candle_berjalan_dibuang"] = len(candles) - len(closed)
    if len(closed) < MIN_CANDLES:
        info.update(status="DATA KURANG", alasan=f"hanya {len(closed)} candle tutup (< {MIN_CANDLES})")
        return finish(info)
    last_close_ms = closed[-1][0] + CANDLE_MS
    info["last_closed_ms"] = last_close_ms
    info["last_closed_wib"] = fmt_wib(last_close_ms)
    info["last_close"] = closed[-1][4]
    info["last_low"] = closed[-1][3]
    info["data_basi"] = now_ms - last_close_ms > STALE_MS
    info["closed"] = closed

    reader = load_reader()
    if reader is None:
        info.update(reader_missing=True, trend="?", breakout="?", bounce="?",
                    resistance=[], support=[], atr_pct=None)
    else:
        try:
            rd = normalize_reading(call_reader(reader, candles, now_ms))
        except Exception as exc:  # noqa: BLE001 - jangan crash karena satu token
            info.update(status="GAGAL AMBIL DATA", alasan=f"candle_reader error: {exc}")
            return finish(info)
        info.update({k: rd[k] for k in ("trend", "breakout", "bounce", "bounce_level", "resistance",
                                        "support", "ema20", "ema50")})
        atr = _f(rd["atr"]) or (_f(rd["atr_pct"]) / 100 * info["last_close"] if rd["atr_pct"] else 0)
        info["atr_pct"] = rd["atr_pct"] if rd["atr_pct"] is not None else (
            atr / info["last_close"] * 100 if atr else None)
        vw = rd["vwap"] if rd["vwap"] is not None else None
        if vw is None:
            vr = vwap_mod.session_vwap(closed, atr or None)
            info.update(vwap=vr["vwap"], vwap_label=vr["label"], vwap_jarak_atr=vr["vwap_jarak_atr"])
        else:
            info.update(vwap=float(vw), vwap_label=None, vwap_jarak_atr=rd["vwap_jarak_atr"])
        info["vwap_bounce"] = vwap_bounce(closed, info.get("vwap"))
        # resistance/support terdekat dari harga terakhir
        above = [p for p, _ in info["resistance"] if p > info["last_close"]]
        info["room_pct"] = (min(above) / info["last_close"] - 1) * 100 if above else None
        info["nearest_resistance"] = min(above) if above else None
    return finish(info)


def finish(info):
    label, alasan = decide(info)
    info["verdict"], info["alasan"] = label, alasan
    return info


# ------------------------------------------------------------------ format

def idn(x, d):
    s = f"{x:,.{d}f}"
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def fmt_num(x, d):
    return idn(x, d)


def fmt_pct(x, d=1, sign=True):
    return (("+" if x >= 0 else "-") if sign else "") + idn(abs(x), d) + "%"


def fmt_price(x, sig=4):
    if x is None:
        return "-"
    decimals = max(2, min(12, sig - 1 - math.floor(math.log10(abs(x))))) if x else 2
    s = f"{x:.{decimals}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s.replace(".", ",")


def fmt_vol(v):
    return f"${idn(v / 1e6, 2)} jt" if v >= 1e6 else f"${idn(v, 0)}"


def fmt_wib(ms):
    return datetime.fromtimestamp(ms / 1000, tz=WIB).strftime("%Y-%m-%d %H:%M") + " WIB"


def render_table(results, now_ms):
    closes = [r["last_closed_ms"] for r in results if r.get("last_closed_ms")]
    head = f"## Scan 15m — {fmt_wib(now_ms)}"
    if closes:
        head += f" (candle tutup terakhir {datetime.fromtimestamp(max(closes) / 1000, tz=WIB):%H:%M} WIB)"
    lines = [head, f"Sumber: API publik bursa · {len(results)} token dicek · candle berjalan dibuang", ""]
    rows = [["Pair", "Harga", "24j", "Vol 24j", "Spread", "Tren", "Breakout / Bounce", "Verdict"]]
    for r in results:
        pair = f"{r['symbol']}/USDT"
        if "last" not in r:
            rows.append([pair, "-", "-", "-", "-", "-", "-", f"{r['verdict']} — {r['alasan']}"])
            continue
        bb = "-" if r.get("reader_missing") else f"{r.get('breakout')} / {r.get('bounce')}"
        if r.get("bounce") == "KANDIDAT_BOUNCE" and r.get("bounce_level"):
            bb = bb.replace("KANDIDAT_BOUNCE", f"KANDIDAT_BOUNCE @{fmt_price(r['bounce_level'])}")
        trend = r.get("trend", "-")
        if r.get("vwap") and r.get("vwap_jarak_atr") is not None:
            trend += f" (VWAP {'+' if r['vwap_jarak_atr'] >= 0 else '-'}{idn(abs(r['vwap_jarak_atr']), 1)} ATR)"
        elif r.get("vwap_label"):
            trend += f" ({r['vwap_label']})"
        verdict = f"{r['verdict']} — {r['alasan']}" + (" [DATA BASI]" if r.get("data_basi") else "")
        if r.get("volume_status") == "LOLOS BERSYARAT":
            verdict += " [volume: LOLOS BERSYARAT]"
        spread_txt = "-" if r["spread_pct"] is None else fmt_pct(r["spread_pct"], 3, sign=False)
        if r["status"] != "OK":
            trend = bb = "-"
        rows.append([pair, fmt_price(r["last"]), fmt_pct(r["change24h"] * 100), fmt_vol(r["volume24h"]),
                     spread_txt, trend, bb, verdict])
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]) - 1)]
    for row in rows:
        lines.append("  ".join(row[i].ljust(widths[i]) for i in range(len(widths))) + "  " + row[-1])
    lolos = [r["symbol"] for r in results if r["verdict"] == "LOLOS"]
    lines += ["", "Verdict: " + ("NO TRADE" if not lolos else
                                 f"{len(lolos)} KANDIDAT ({', '.join(lolos)})"),
              "Catatan: ini pembacaan kondisi, bukan sinyal dan bukan nasihat keuangan. Biaya memakai "
              "asumsi ilustratif (fee 0,1% + 0,1% + spread aktual); fee bursa user belum terverifikasi.",
              "Net R:R stop 2% = (4 - break-even) / (2 + break-even), break-even = 0,1% + 0,1% + spread."]
    return "\n".join(lines)


def to_json_obj(r):
    keys = ["symbol", "last", "change24h", "volume24h", "spread_pct", "break_even_pct", "net_rr_stop2",
            "trend", "breakout", "bounce", "atr_pct", "last_closed_wib", "verdict", "alasan",
            "vwap", "vwap_jarak_atr", "volume_status", "status"]
    o = {k: r.get(k) for k in keys}
    o["resistance"] = [{"harga": p, "jarak_atr": a} for p, a in r.get("resistance", [])]
    o["support"] = [{"harga": p, "jarak_atr": a} for p, a in r.get("support", [])]
    return o


# --------------------------------------------------------------- watchlist

def load_watchlist(path):
    p = Path(path).expanduser()
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(DEFAULT_WATCHLIST, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"(watchlist.json belum ada; dibuat dengan contoh isi di {p})", file=sys.stderr)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise SystemExit(f"watchlist {p} bukan JSON valid: {exc}")
    return validate_watchlist(data)


def validate_watchlist(data):
    if not isinstance(data, list):
        raise SystemExit("watchlist harus berupa array objek")
    out = []
    for i, it in enumerate(data):
        if not isinstance(it, dict) or not {"symbol", "trigger", "level"} <= set(it):
            raise SystemExit(f"watchlist[{i}] harus punya symbol, trigger, level")
        if it["trigger"] not in TRIGGERS:
            raise SystemExit(f"watchlist[{i}].trigger '{it['trigger']}' tidak dikenal; pilih {sorted(TRIGGERS)}")
        try:
            level = float(it["level"])
        except (TypeError, ValueError):
            raise SystemExit(f"watchlist[{i}].level harus angka")
        out.append({**it, "symbol": norm_symbol(str(it["symbol"])), "level": level})
    return out


def eval_trigger(item, r):
    if "last_close" not in r:
        return "TIDAK BISA DICEK", r.get("alasan", r.get("verdict", ""))
    lvl, last = item["level"], r["last_close"]
    jarak = (last / lvl - 1) * 100
    if item["trigger"] == "close_di_atas":
        hit = last > lvl
    elif item["trigger"] == "close_di_bawah":
        hit = last < lvl
    else:
        bl = r.get("bounce_level")
        near = bl is None or abs(bl - lvl) / lvl <= 0.005
        hit = r.get("bounce") == "BOUNCE_TERKONFIRMASI" and near
    return ("TERPICU" if hit else "BELUM"), f"tutup terakhir ${fmt_price(last)}, jarak {fmt_pct(jarak, 2)} ke level"


def plan_numbers(item, r):
    """Angka rencana via trade.calc. Hanya dicetak, TIDAK menulis jurnal."""
    stop = item.get("stop")
    if stop is None:
        return "stop belum diisi di watchlist (tambahkan field \"stop\") — angka rencana tidak dihitung"
    tdir = HERE.parents[1] / "trade-journal" / "scripts"
    sys.path.insert(0, str(tdir))
    try:
        import trade
        c = trade.calc(r["last_close"], float(stop), r.get("spread_pct"))
    except Exception as exc:  # noqa: BLE001
        return f"angka rencana tidak bisa dihitung: {exc}"
    return (f"rencana (asumsi ilustratif): entry ${fmt_price(c['entry'], 6)} stop ${fmt_price(c['stop'], 6)} "
            f"target ${fmt_price(c['target'], 6)} ({fmt_pct(c['target_pct'], 2)}) · risiko ${idn(c['risiko_usdt'], 2)} "
            f"· net R:R {idn(c['net_rr'], 2)}")


# --------------------------------------------------------------------- main

def get_tickers(base_url, fetcher=fetch_data):
    """Semua ticker sekali jalan (satu request, bukan N). None bila gagal."""
    try:
        data = fetcher(f"{base_url}/api/v2/spot/market/tickers")
    except FetchError:
        return None
    return {t["symbol"]: t for t in map(parse_ticker, data or []) if t["symbol"]}


def discover(tickers, n, skip):
    cands = []
    for sym, t in tickers.items():
        if not sym.endswith("USDT"):
            continue
        base = sym[:-4]
        if (base in BIG_CAPS or base in skip or is_tokenized_stock(base) or t["book_rusak"]
                or t["volume24h"] < MIN_VOLUME):
            continue
        cands.append((abs(t["change24h"]), base))
    cands.sort(reverse=True)
    return [b for _, b in cands[:n]]


def main(argv=None, now_ms=None, fetcher=fetch_data):
    ap = argparse.ArgumentParser(description="Pemindai token 15m (read-only, tanpa API key)")
    ap.add_argument("symbols", nargs="*", help="simbol, mis. BEAM DOS (akhiran USDT boleh)")
    ap.add_argument("--watchlist", action="store_true", help="cek trigger di watchlist.json")
    ap.add_argument("--watchlist-file", default="~/workspace/watchlist.json")
    ap.add_argument("--discover", type=int, metavar="N", help="cari N kandidat dari seluruh pasar")
    ap.add_argument("--skip", default="", help="simbol dilewati saat --discover, pisah koma")
    ap.add_argument("--user-suggested", default="", help="simbol disarankan user (volume jadi LOLOS BERSYARAT)")
    ap.add_argument("--json", metavar="FILE", help="simpan hasil mentah ke JSON")
    ap.add_argument("--base-url", default=BASE_URL)
    args = ap.parse_args(argv)

    now_ms = now_ms or int(time.time() * 1000)
    base_url = args.base_url.rstrip("/")
    suggested = {norm_symbol(s) for s in args.user_suggested.split(",") if s.strip()}
    skip = {norm_symbol(s) for s in args.skip.split(",") if s.strip()}

    watch = load_watchlist(args.watchlist_file) if args.watchlist else []
    symbols = [norm_symbol(s) for s in args.symbols]
    symbols += [w["symbol"] for w in watch]
    tickers = get_tickers(base_url, fetcher)
    if args.discover:
        if tickers is None:
            print("GAGAL AMBIL DATA: daftar ticker tidak bisa diambil, --discover tidak bisa jalan.")
        else:
            symbols += discover(tickers, args.discover, skip)
    if not symbols:
        ap.error("beri simbol, atau --watchlist, atau --discover N")

    seen, ordered = set(), []
    for s in symbols:
        if s not in seen:
            seen.add(s)
            ordered.append(s)
    results = [analyze(s, tickers, base_url, suggested, now_ms, fetcher) for s in ordered]
    by_symbol = {r["symbol"]: r for r in results}

    if args.watchlist and not args.symbols and not args.discover:
        print(f"## Watchlist — {fmt_wib(now_ms)}")
        for w in watch:
            state, detail = eval_trigger(w, by_symbol[w["symbol"]])
            print(f"{w['symbol']:<8} {w['trigger']} {fmt_price(w['level'])} — {state} ({detail})"
                  + (f"  [{w['note']}]" if w.get("note") else ""))
            if state == "TERPICU":
                print("         " + plan_numbers(w, by_symbol[w["symbol"]]))
        print("\nPemicu terpenuhi bukan perintah beli. Rencana tidak dibuat otomatis; "
              "jalankan trade.py plan bila user memutuskan.")
    else:
        print(render_table(results, now_ms))

    if args.json:
        payload = {"checked_at_wib": fmt_wib(now_ms), "tokens": [to_json_obj(r) for r in results]}
        Path(args.json).expanduser().write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                                                encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
