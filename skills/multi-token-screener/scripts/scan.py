#!/usr/bin/env python3
"""
scan.py — Pemindai token spot sekali jalan (Bitget API publik, GET saja, tanpa key).

  python scan.py BEAM DOS KGEN ARIA        cek simbol yang disebut
  python scan.py --watchlist               cek trigger di watchlist.json
  python scan.py --discover 6              cari 6 kandidat dari seluruh pasar
  python scan.py BEAM --json out.json      simpan juga hasil mentah

Hanya standard library. Read-only: tidak ada order, wallet, signing, atau kredensial.
Logika candle TIDAK ditulis ulang: memakai candle_reader.read(); rumus R:R memakai trade.py.
Pembacaan kondisi, bukan sinyal dan bukan nasihat keuangan.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

WIB = timezone(timedelta(hours=7))
HERE = Path(__file__).resolve().parent
DEFAULT_BASE_URL = "https://api.bitget.com"
TICKERS_PATH = "/api/v2/spot/market/tickers"
CANDLES_PATH = "/api/v2/spot/market/candles"
GRANULARITY = "15min"           # BUKAN "15m": API menolak dengan error 400171
CANDLE_LIMIT = 100
MIN_CANDLES = 75
STALE_MINUTES = 15              # data dianggap basi bila lebih dari 1 candle tertinggal (lihat is_stale)
DEFAULT_WATCHLIST = Path("~/workspace/watchlist.json").expanduser()

BIG_CAPS = {"BTC", "ETH", "BNB", "SOL", "XRP"}
# Saham tokenisasi (awalan R + ticker saham). Daftar blokir eksplisit + pola R<ticker saham umum>.
# Sengaja TIDAK memakai pola ^R[A-Z]{2,}$ mentah: akan menyingkirkan token sah (RAY, RUNE, ...).
# "Bila ragu, ikutkan" — verdict yang akan menggugurkan.
STOCK_BLOCKLIST = {"RNVDA", "RSPY", "RQQQ", "RMU", "RAMD", "RMSFT", "RSPCX", "RSNDK", "RAAPL", "RSOXL"}
STOCK_TICKERS = {"NVDA", "SPY", "QQQ", "MU", "AMD", "MSFT", "SPCX", "SNDK", "AAPL", "SOXL", "TSLA", "AMZN", "GOOGL",
                 "GOOG", "META", "COIN", "MSTR", "NFLX", "PLTR", "INTC", "AVGO", "ORCL", "CRCL", "HOOD", "BABA",
                 "DIA", "IWM", "TQQQ", "SQQQ", "ARKK", "GLD", "SLV", "TLT", "SMCI", "UBER", "PYPL", "DIS"}


def load_sibling(module: str, folder: str, env: str):
    """Impor modul saudara tanpa menulis ulang. Urutan: env, ../../<folder>/scripts, ../../../<folder>/scripts, ~/workspace."""
    cands = []
    if os.environ.get(env):
        cands.append(Path(os.environ[env]).expanduser())
    cands += [HERE.parent.parent / folder / "scripts", HERE.parent.parent.parent / folder / "scripts",
              Path(f"~/workspace/custom-skills/{folder}/scripts").expanduser()]
    for d in cands:
        if (d / f"{module}.py").exists():
            sys.path.insert(0, str(d))
            return importlib.import_module(module)
    raise SystemExit(f"Tidak menemukan {module}.py. Taruh di custom-skills/{folder}/scripts/ atau set {env}.")


cr = load_sibling("candle_reader", "candle-reader-15m", "CANDLE_READER_DIR")
trade = load_sibling("trade", "trade-journal", "TRADE_PY_DIR")


# ------------------------------------------------------------------------------ format Indonesia
def id_num(x: float, dec: int) -> str:
    return f"{x:,.{dec}f}".replace(",", "\0").replace(".", ",").replace("\0", ".")


def fmt_px_raw(s: str) -> str:
    return s.replace(".", ",")


def fmt_sig(x: float, sig: int = 5) -> str:
    """Angka berpresisi signifikan tanpa notasi eksponen, koma desimal."""
    if x == 0:
        return "0"
    import math
    dec = max(0, sig - 1 - int(math.floor(math.log10(abs(x)))))
    s = f"{x:.{dec}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s.replace(".", ",")


def fmt_vol(v: float) -> str:
    return f"${id_num(v / 1e6, 2)} jt" if v >= 1e6 else f"${id_num(v, 0)}"


def fmt_pct(x: float, dec: int = 1, sign: bool = True) -> str:
    s = id_num(abs(x), dec)
    return (("+" if x >= 0 else "-") if sign else ("-" if x < 0 else "")) + s + "%"


def wib_now() -> datetime:
    return datetime.now(WIB)


# ------------------------------------------------------------------------------------- HTTP
class FetchError(Exception):
    pass


class Client:
    """Klien GET sederhana. Satu kali coba ulang setelah 2 detik bila gagal; 4xx berisi JSON dikembalikan apa adanya."""

    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout: int = 15, sleep=time.sleep, opener=None):
        self.base_url, self.timeout, self.sleep = base_url.rstrip("/"), timeout, sleep
        self.opener = opener or urllib.request.urlopen

    def _once(self, url: str) -> tuple[int, dict[str, Any] | None]:
        req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "scan.py/1.0"})
        try:
            with self.opener(req, timeout=self.timeout) as r:
                return r.status, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read().decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return e.code, None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            raise FetchError(type(e).__name__) from None

    def get(self, path: str, params: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
        url = self.base_url + path + (("?" + urllib.parse.urlencode(params)) if params else "")
        last = "unknown"
        for attempt in range(2):
            try:
                status, body = self._once(url)
                if status == 429 or status >= 500 or body is None:
                    last = f"HTTP {status}" + ("" if body is not None else " (bukan JSON)")
                else:
                    return status, body
            except FetchError as e:
                last = str(e)
            if attempt == 0:
                self.sleep(2)
        raise FetchError(last)


# ------------------------------------------------------------------------------------ parsing
def _f(x: Any) -> float:
    return float(x) if x not in (None, "") else 0.0


def parse_ticker(d: dict[str, Any]) -> dict[str, Any]:
    try:
        last = _f(d["lastPr"])
        t = {"symbol": str(d["symbol"]).upper(), "last": last, "last_str": str(d["lastPr"]),
             "volume": _f(d.get("usdtVolume")), "change24h": _f(d.get("change24h")),
             "bid": _f(d.get("bidPr")), "ask": _f(d.get("askPr")),
             "high": _f(d.get("high24h")), "low": _f(d.get("low24h")),
             "ts": int(d["ts"]) if str(d.get("ts", "")).isdigit() else None}
    except (KeyError, ValueError, TypeError) as e:
        raise ValueError(f"ticker tidak valid: {e}") from None
    if last <= 0:
        raise ValueError("harga terakhir ≤ 0")
    t["book_broken"] = t["bid"] <= 0 or t["ask"] <= 0
    t["spread_pct"] = None if t["book_broken"] else (t["ask"] - t["bid"]) / last * 100
    return t


def fetch_ticker(client: Client, base: str) -> tuple[str, dict[str, Any] | None]:
    """-> ('ok', ticker) | ('notfound', None). Melempar FetchError bila gagal jaringan/server."""
    status, body = client.get(TICKERS_PATH, {"symbol": base + "USDT"})
    if status == 200 and str(body.get("code")) == "00000":
        data = body.get("data") or []
        return ("ok", parse_ticker(data[0])) if data else ("notfound", None)
    if 400 <= status < 500:
        return "notfound", None
    raise FetchError(f"HTTP {status}")


def fetch_candles(client: Client, base: str) -> list[dict[str, float]]:
    status, body = client.get(CANDLES_PATH, {"symbol": base + "USDT", "granularity": GRANULARITY, "limit": CANDLE_LIMIT})
    if status != 200 or str(body.get("code")) != "00000":
        raise FetchError(f"candle: HTTP {status} code {body.get('code')} {str(body.get('msg', ''))[:60]}")
    try:
        return cr.parse_candles(body.get("data") or [])
    except (ValueError, TypeError, IndexError) as e:
        raise FetchError(f"candle tidak valid: {type(e).__name__}") from None


def is_stale(candles: list[dict[str, float]], now_ms: int) -> int | None:
    """Candle terbaru harusnya dibuka < 15 menit lalu. Bila > 30 menit, minimal satu candle hilang -> basi. Return menit."""
    age = (now_ms - candles[-1]["ts"]) / 60000
    return int(age - 15) if age > 2 * STALE_MINUTES else None


# --------------------------------------------------------------------------------- filter pasar
def base_of(sym: str) -> str:
    s = sym.upper().strip()
    return s[:-4] if s.endswith("USDT") and len(s) > 4 else s


def is_tokenized_stock(base: str) -> bool:
    return base in STOCK_BLOCKLIST or (len(base) >= 3 and base[0] == "R" and base[1:] in STOCK_TICKERS)


def discover_filter(tickers: list[dict[str, Any]], skip: set[str], n: int, min_vol: float) -> list[str]:
    cands = []
    for t in tickers:
        if not t["symbol"].endswith("USDT"):
            continue
        b = base_of(t["symbol"])
        if t["volume"] < min_vol or b in BIG_CAPS or is_tokenized_stock(b) or b in skip or t["book_broken"]:
            continue
        cands.append(t)
    cands.sort(key=lambda t: abs(t["change24h"]), reverse=True)
    return [base_of(t["symbol"]) for t in cands[:n]]


# --------------------------------------------------------------------------------- pertimbangan
def room_check(entry: float, support: float, resistances: list[float], atr: float, spread_pct: float,
               stop_override: float | None = None) -> dict[str, Any]:
    """Estimasi ruang ke resistance memakai rumus trade.py. Stop dari struktur: support − 0,2×ATR (min 0,5×ATR dari entry)."""
    stop = stop_override if stop_override is not None else support - 0.2 * atr
    stop = min(stop, entry - 0.5 * atr)
    risk = entry - stop
    target_2r = entry + trade.RR_GROSS * risk
    above = sorted(r for r in resistances if r > entry)
    nearest = above[0] if above else None
    limited = False
    target = target_2r
    if nearest is not None and nearest - 0.1 * atr < target_2r:
        target, limited = nearest - 0.1 * atr, True
    if target <= entry or risk <= 0:
        return {"ok": False, "net": float("-inf"), "entry": entry, "stop": stop, "target": target,
                "room_pct": 0.0, "limited": limited, "nearest": nearest}
    net = trade.net_rr_for_target(entry, stop, target, spread_pct)
    return {"ok": net >= trade.NET_RR_MIN, "net": net, "entry": entry, "stop": stop, "target": target,
            "room_pct": (target - entry) / entry * 100, "limited": limited, "nearest": nearest}


def evaluate(t: dict[str, Any], rd: dict[str, Any] | None, stale_min: int | None, volume_status: str,
             net_rr2: float | None) -> dict[str, Any]:
    """Verdict deterministik. Mengembalikan {verdict, alasan, setup, plan}. Aturan pemetaan didokumentasikan di README."""
    def out(v: str, why: str, setup: int | None = None, plan: dict | None = None) -> dict[str, Any]:
        return {"verdict": v, "alasan": why, "setup": setup, "plan": plan}

    if t["book_broken"]:
        return out("DITOLAK", "BOOK RUSAK (bid/ask = 0)")
    if volume_status == "GUGUR":
        return out("DITOLAK", f"volume 24j {fmt_vol(t['volume'])} di bawah {fmt_vol(trade.VOLUME_MIN_USDT)}")
    if rd is None or not rd.get("ok"):
        return out("DITOLAK", "DATA KURANG — pembacaan struktur dilewati")
    if stale_min is not None:
        return out("DITOLAK", f"DATA BASI — candle terbaru tertinggal ±{stale_min} menit")
    if net_rr2 is not None and net_rr2 < trade.NET_RR_MIN:
        return out("DITOLAK", f"spread terlalu lebar: net R:R stop 2% = {id_num(net_rr2, 2)} < {id_num(trade.NET_RR_MIN, 1)}")

    close, atr = rd["close"], rd["atr"]
    sp = t["spread_pct"] or 0.0
    trend = rd["trend"]["state"]
    bo, bn = rd["breakout"], rd["bounce"]
    res = [x["price"] for x in rd["resistance"]["level_di_atas"]]
    sup = rd["support_terdekat"]
    sup_px = sup[0]["price"] if sup else None

    # ---- setup terkonfirmasi ----
    setup = None
    if bo["state"] == "BREAKOUT_TERKONFIRMASI":
        setup, support_ref, label = 1, bo["level"], "breakout terkonfirmasi"
    elif bo["state"] == "RETEST_BERTAHAN" and rd["volume"]["label"] != "RENDAH":
        setup, support_ref, label = 1, bo["level"], "retest bertahan"
    elif bn["state"] == "BOUNCE_TERKONFIRMASI":
        if trend == "DOWNTREND":
            return out("DITOLAK", "bounce terkonfirmasi tetapi melawan tren turun")
        is_ema = str(bn.get("support", "")).startswith("EMA")
        setup = 3 if (trend == "RANGE/CAMPUR" and not is_ema) else 2
        support_ref, label = bn["support_price"], f"bounce terkonfirmasi di {bn['support']}"
    if setup:
        rc = room_check(close, support_ref, res, atr, sp)
        if not rc["ok"]:
            return out("DITOLAK", f"{label}, tetapi ruang ke resistance ${fmt_sig(rc['nearest'] or rc['target'])} cuma "
                                  f"+{id_num(rc['room_pct'], 1)}% (R:R bersih {id_num(rc['net'], 2) if rc['net'] > -1e9 else '—'} < 1,5)")
        note = f"{label} (setup {setup})"
        if rc["limited"]:
            note += f"; ⚠ resistance ${fmt_sig(rc['nearest'])} sebelum target 2R"
        return out("LOLOS", note, setup, rc)

    # ---- belum terkonfirmasi ----
    if bo["state"] in ("BREAKOUT_LEMAH", "PENOLAKAN_SUMBU", "RETEST_BERTAHAN"):
        why = ", ".join(bo.get("kekurangan") or ["volume rendah"])
        return out("PANTAU", f"tunggu close 15m di atas ${fmt_sig(bo['level'])} dengan volume ≥1,5× ({bo['state']}: {why})")
    if bn["state"] == "SUPPORT_JEBOL":
        return out("DITOLAK", f"support ${fmt_sig(bn['support_price'])} jebol")
    if bn["state"] == "KANDIDAT_BOUNCE":
        rc = room_check(close, bn["support_price"], res, atr, sp)
        if not rc["ok"]:
            return out("DITOLAK", f"range S→R cuma +{id_num(rc['room_pct'], 1)}% (R:R bersih < 1,5)")
        return out("PANTAU", f"tunggu candle tutup di atas ${fmt_sig(bn['bounce_high'])} (konfirmasi bounce di {bn['support']})")
    if trend == "UPTREND":
        lo, hi = sorted([rd["trend"]["ema_slow"], rd["trend"]["ema_fast"]])
        return out("PANTAU", f"pullback ke ${fmt_sig(lo)}–${fmt_sig(hi)}, tunggu bounce terkonfirmasi")
    if trend == "DOWNTREND":
        return out("DITOLAK", "tren turun, tanpa setup")
    if sup_px is not None and res:
        rc = room_check(sup_px, sup_px, res, atr, sp)  # skenario entry di support
        if not rc["ok"]:
            return out("DITOLAK", f"range S→R cuma +{id_num((res[0] / sup_px - 1) * 100, 1)}% (R:R bersih < 1,5)")
        return out("PANTAU", f"range: tunggu bounce terkonfirmasi di ${fmt_sig(sup_px)} (resistance ${fmt_sig(res[0])})")
    return out("DITOLAK", "struktur tidak jelas (tanpa support/resistance terdeteksi)")


# ------------------------------------------------------------------------------------- analisis
def analyze(base: str, client: Client, now: datetime, user_suggested: set[str],
            ticker: dict[str, Any] | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {"symbol": base, "status": "OK", "verdict": "—", "alasan": ""}
    if base in BIG_CAPS:
        row.update(status="BIG CAP", verdict="DILEWATI", alasan="big cap (tidak dianalisa)")
        return row
    try:
        if ticker is None:
            kind, ticker = fetch_ticker(client, base)
            if kind == "notfound":
                row.update(status="TIDAK DITEMUKAN", verdict="TIDAK DITEMUKAN", alasan="simbol tidak ada di bursa")
                return row
        assert ticker is not None
        candles = fetch_candles(client, base)
    except (FetchError, ValueError) as e:
        row.update(status="GAGAL AMBIL DATA", verdict="GAGAL AMBIL DATA", alasan=str(e))
        return row

    t = ticker
    be = None if t["book_broken"] else 2 * trade.FEE_EACH_PCT + t["spread_pct"]
    net_rr2 = None if be is None else (2 * trade.RR_GROSS - be) / (2 + be)
    if t["volume"] >= trade.VOLUME_MIN_USDT:
        vol_status = "LOLOS"
    elif base in user_suggested:
        vol_status = "LOLOS BERSYARAT"
    else:
        vol_status = "GUGUR"
    row.update(last=t["last"], last_str=t["last_str"], change24h=t["change24h"], volume24h=t["volume"],
               spread_pct=t["spread_pct"], break_even_pct=be, net_rr_stop2=net_rr2, volume_status=vol_status)

    now_ms = int(now.timestamp() * 1000)
    stale = is_stale(candles, now_ms) if candles else None
    rd = None
    if len(candles) >= MIN_CANDLES:
        rd = cr.read(candles, now_ms=now_ms)
    row["candle_running_dropped"] = bool(rd and any("masih berjalan" in w for w in rd.get("warnings", [])))
    if rd and rd.get("ok"):
        row.update(trend=rd["trend"]["state"], breakout=rd["breakout"], bounce=rd["bounce"],
                   resistance=[{"price": x["price"], "dist_atr": x["dist_atr"]} for x in rd["resistance"]["level_di_atas"]],
                   support=[{"price": x["price"], "dist_atr": x["dist_atr"]} for x in rd["support_terdekat"]],
                   atr_pct=rd["atr_pct"], last_closed_wib=rd["last_closed_wib"], volume_ratio=rd["volume"]["ratio"],
                   volume_label=rd["volume"]["label"])
    ev = evaluate(t, rd, stale, vol_status, net_rr2)
    if vol_status == "LOLOS BERSYARAT" and ev["verdict"] != "DITOLAK":
        ev["alasan"] += " [volume LOLOS BERSYARAT — disarankan user]"
    row.update(verdict=ev["verdict"], alasan=ev["alasan"], setup=ev["setup"])
    if ev["plan"]:
        row["plan_usulan"] = {k: ev["plan"][k] for k in ("entry", "stop", "target", "net", "room_pct", "limited")}
    return row


# ---------------------------------------------------------------------------------------- output
TREND_LABEL = {"UPTREND": "UPTREND", "DOWNTREND": "DOWNTREND", "RANGE/CAMPUR": "RANGE"}


def state_text(x: dict[str, Any], price_key: str) -> str:
    if x["state"] == "TIDAK_ADA":
        return "TIDAK_ADA"
    px = x.get("level") if price_key == "level" else x.get("support_price")
    return x["state"] + (f" @{fmt_sig(px)}" if px else "")


def fmt_table(rows: list[dict[str, Any]], now: datetime, mode_note: str = "") -> str:
    closed = next((r["last_closed_wib"] for r in rows if r.get("last_closed_wib")), "?")
    head = [f"## Scan 15m — {now:%Y-%m-%d, %H:%M} WIB (candle tutup terakhir {closed[-5:] if closed != '?' else '?'} WIB)",
            f"Sumber: API publik bursa · {len(rows)} token dicek{mode_note}",
            f"Biaya: fee taker 0,1% + 0,1% + spread aktual (asumsi ilustratif; fee bursa belum terverifikasi). "
            f"Candle yang masih berjalan dibuang dari analisis.", ""]
    cols = ["Pair", "Harga", "24j", "Vol 24j", "Spread", "Tren", "Breakout / Bounce", "Verdict"]
    data = []
    for r in rows:
        if "last" not in r:
            data.append([f"{r['symbol']}/USDT", "—", "—", "—", "—", "—", "—", f"{r['verdict']}" + (f" — {r['alasan']}" if r["status"] not in ("TIDAK DITEMUKAN",) and r["alasan"] else "")])
            continue
        bb = "—" if "breakout" not in r else (
            "TIDAK_ADA / TIDAK_ADA" if r["breakout"]["state"] == "TIDAK_ADA" and r["bounce"]["state"] == "TIDAK_ADA"
            else f"{state_text(r['breakout'], 'level')} / {state_text(r['bounce'], 'support')}")
        sp = "RUSAK" if r["spread_pct"] is None else fmt_pct(r["spread_pct"], 3, sign=False)
        data.append([f"{r['symbol']}/USDT", fmt_px_raw(r["last_str"]), fmt_pct(r["change24h"] * 100), fmt_vol(r["volume24h"]),
                     sp, TREND_LABEL.get(r.get("trend", ""), "—"), bb, f"{r['verdict']} — {r['alasan']}"])
    widths = [max(len(cols[i]), *(len(d[i]) for d in data)) for i in range(len(cols) - 1)]
    lines = ["  ".join(c.ljust(widths[i]) for i, c in enumerate(cols[:-1])) + "  " + cols[-1]]
    lines += ["  ".join(d[i].ljust(widths[i]) for i in range(len(cols) - 1)) + "  " + d[-1] for d in data]
    return "\n".join(head + lines)


def final_verdict(rows: list[dict[str, Any]]) -> str:
    ok = [r for r in rows if r.get("verdict") == "LOLOS"]
    if not ok:
        return "Verdict: NO TRADE (tidak ada setup terkonfirmasi)"
    ok.sort(key=lambda r: (r.get("volume_ratio") or 0, r.get("volume24h", 0)), reverse=True)
    names = ", ".join(r["symbol"] for r in ok)
    if len(ok) == 1:
        return f"Verdict: 1 KANDIDAT ({ok[0]['symbol']})"
    return f"Verdict: {len(ok)} KANDIDAT ({names}); utama: {ok[0]['symbol']} (rasio volume candle tertinggi)"


DISCLAIMER = "Catatan: pembacaan kondisi pasar, bukan sinyal dan bukan nasihat keuangan."


def to_jsonable(rows: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    return {"checked_at_wib": f"{now:%Y-%m-%d %H:%M} WIB", "verdict_akhir": final_verdict(rows), "tokens": rows}


# ------------------------------------------------------------------------------------ watchlist
SAMPLE_WATCHLIST = [
    {"symbol": "BEAM", "trigger": "close_di_atas", "level": 0.004526, "note": "breakout"},
    {"symbol": "DOS", "trigger": "close_di_atas", "level": 0.1742, "note": "breakout"},
    {"symbol": "UAI", "trigger": "close_di_atas", "level": 0.0427, "note": "breakout"},
    {"symbol": "CYBER", "trigger": "close_di_atas", "level": 0.2771, "note": "breakout"},
    {"symbol": "AIO", "trigger": "close_di_atas", "level": 0.0449, "note": "breakout"},
    {"symbol": "BR", "trigger": "close_di_atas", "level": 0.4998, "note": "breakout"},
]
TRIGGERS = {"close_di_atas", "close_di_bawah", "bounce_di"}


def load_watchlist(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Return (entri_valid, pesan_kesalahan). File dibuat dengan contoh bila belum ada."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(SAMPLE_WATCHLIST, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return [], [f"{path}: JSON rusak"]
    if not isinstance(data, list):
        return [], [f"{path}: isi harus array"]
    ok, errs = [], []
    for i, e in enumerate(data):
        if not isinstance(e, dict) or not isinstance(e.get("symbol"), str) or e.get("trigger") not in TRIGGERS \
                or not isinstance(e.get("level"), (int, float)) or isinstance(e.get("level"), bool) or e["level"] <= 0:
            errs.append(f"entri #{i + 1} tidak valid (butuh symbol, trigger ∈ {sorted(TRIGGERS)}, level > 0)")
            continue
        ok.append(e)
    return ok, errs


def check_trigger(e: dict[str, Any], rd: dict[str, Any]) -> tuple[bool, str]:
    close, lvl = rd["close"], float(e["level"])
    dist = (close - lvl) / lvl * 100
    if e["trigger"] == "close_di_atas":
        return close > lvl, f"close terakhir {fmt_sig(close)} ({fmt_pct(dist, 2)} dari level)"
    if e["trigger"] == "close_di_bawah":
        return close < lvl, f"close terakhir {fmt_sig(close)} ({fmt_pct(dist, 2)} dari level)"
    bn = rd["bounce"]
    hit = bn["state"] == "BOUNCE_TERKONFIRMASI" and abs(bn["support_price"] - lvl) <= 0.5 * rd["atr"]
    return hit, f"close terakhir {fmt_sig(close)}; bounce: {bn['state']}" + (f" di {fmt_sig(bn['support_price'])}" if "support_price" in bn else "")


def run_watchlist(client: Client, entries: list[dict[str, Any]], now: datetime) -> list[str]:
    lines = [f"## Watchlist 15m — {now:%Y-%m-%d, %H:%M} WIB", ""]
    now_ms = int(now.timestamp() * 1000)
    for e in entries:
        base = base_of(e["symbol"])
        try:
            candles = fetch_candles(client, base)
            kind, t = fetch_ticker(client, base)
        except FetchError as ex:
            lines.append(f"{base:<8} {e['trigger']} {fmt_sig(e['level'])} → GAGAL AMBIL DATA ({ex})")
            continue
        if kind == "notfound" or t is None:
            lines.append(f"{base:<8} {e['trigger']} {fmt_sig(e['level'])} → TIDAK DITEMUKAN")
            continue
        rd = cr.read(candles, now_ms=now_ms) if len(candles) >= MIN_CANDLES else None
        if not rd or not rd.get("ok"):
            lines.append(f"{base:<8} {e['trigger']} {fmt_sig(e['level'])} → DATA KURANG")
            continue
        stale = is_stale(candles, now_ms)
        hit, detail = check_trigger(e, rd)
        tag = "TERPICU" if hit else "BELUM"
        lines.append(f"{base:<8} {e['trigger']} {fmt_sig(e['level'])} → {tag} · {detail}"
                     + (f" · DATA BASI ±{stale} mnt" if stale is not None else "")
                     + (f" · {e['note']}" if e.get("note") else "") + f" · candle tutup {rd['last_closed_wib'][-5:]} WIB")
        if hit and not t["book_broken"]:
            entry = rd["close"]
            stop = e.get("stop")
            if stop is None and rd["support_terdekat"]:
                stop = min(rd["support_terdekat"][0]["price"] - 0.2 * rd["atr"], entry - 0.5 * rd["atr"])
            if stop is not None and stop < entry:
                p = trade.calc_plan(entry, float(stop), t["spread_pct"], force=True)
                lines.append(f"         usulan angka (BELUM dicatat): entry {fmt_sig(entry)} · stop {fmt_sig(p['stop'])} "
                             f"(-{id_num(p['jarak_stop_pct'], 2)}%) · target {fmt_sig(p['target'])} (+{id_num(p['target_pct'], 2)}%) · "
                             f"risiko ${id_num(p['risiko_usdt'], 2)} · net R:R {id_num(p['net_rr'], 2)} (asumsi ilustratif)")
                lines.append("         → catat hanya bila kamu mau: trade.py plan ... (tidak dibuat otomatis)")
            else:
                lines.append("         stop belum ditentukan (tambahkan field \"stop\" di watchlist atau tentukan manual)")
    lines += ["", DISCLAIMER]
    return lines


# ------------------------------------------------------------------------------------------- CLI
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Pemindai token spot (Bitget API publik, tanpa key)")
    ap.add_argument("symbols", nargs="*", help="simbol tanpa akhiran USDT (boleh huruf kecil)")
    ap.add_argument("--watchlist", action="store_true", help="cek trigger di watchlist.json")
    ap.add_argument("--watchlist-file", default=str(DEFAULT_WATCHLIST))
    ap.add_argument("--discover", type=int, metavar="N", help="cari N kandidat dari seluruh pasar")
    ap.add_argument("--skip", default="", help="simbol yang dilewati saat --discover, dipisah koma")
    ap.add_argument("--user-suggested", default="", help="simbol disarankan user (volume LOLOS BERSYARAT)")
    ap.add_argument("--json", metavar="FILE", help="simpan hasil mentah ke JSON")
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL, help="(uji) basis URL API")
    ap.add_argument("--delay", type=float, default=0.25, help="jeda antar token, detik")
    return ap


def split_csv(s: str) -> set[str]:
    return {base_of(x) for x in s.split(",") if x.strip()}


def main(argv: list[str] | None = None, client: Client | None = None, now: datetime | None = None,
         out=None) -> int:
    out = out or sys.stdout
    ap = build_parser()
    a = ap.parse_args(argv)
    if not (a.symbols or a.watchlist or a.discover):
        ap.print_help(out)
        return 0
    client = client or Client(a.base_url)
    now = now or wib_now()
    suggested = split_csv(a.user_suggested)

    if a.watchlist:
        entries, errs = load_watchlist(Path(a.watchlist_file).expanduser())
        for e in errs:
            print(f"⚠️ {e}", file=out)
        print("\n".join(run_watchlist(client, entries, now)), file=out)
        return 0

    note, preloaded = "", {}
    if a.discover:
        try:
            status, body = client.get(TICKERS_PATH)
            if status != 200 or str(body.get("code")) != "00000":
                raise FetchError(f"HTTP {status}")
            tickers = []
            for d in body.get("data", []):
                try:
                    tickers.append(parse_ticker(d))
                except ValueError:
                    continue
        except FetchError as e:
            print(f"GAGAL AMBIL DATA ticker pasar ({e}); --discover dibatalkan.", file=out)
            return 0
        picks = discover_filter(tickers, split_csv(a.skip), a.discover, trade.VOLUME_MIN_USDT)
        preloaded = {base_of(t["symbol"]): t for t in tickers}
        symbols = picks + [s for s in (base_of(x) for x in a.symbols) if s not in picks]
        note = f" · discover: {len(picks)} kandidat teratas |perubahan 24j|"
    else:
        symbols = [base_of(x) for x in a.symbols]

    rows = []
    for i, base in enumerate(dict.fromkeys(symbols)):
        rows.append(analyze(base, client, now, suggested, ticker=preloaded.get(base)))
        if a.delay and i < len(symbols) - 1:
            time.sleep(a.delay)
    print(fmt_table(rows, now, note), file=out)
    print("", file=out)
    print(final_verdict(rows), file=out)
    print(DISCLAIMER, file=out)
    if a.json:
        Path(a.json).expanduser().write_text(json.dumps(to_jsonable(rows, now), indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"JSON tersimpan: {a.json}", file=out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
