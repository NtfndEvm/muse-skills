"""VWAP sesi harian (anchor 00:00 UTC). Hanya stdlib.

Dulu menduplikasi `session_vwap` dari candle_reader.py; sekarang mendelegasikan
ke modul bersama skills/_shared/candles.py (satu sumber kebenaran). Fungsi ini
tinggal sebagai cadangan bila hasil reader belum punya field `vwap` — scan.py
memakainya lewat `vwap_mod.session_vwap(closed, atr)`.

Candle: [ts_ms, open, high, low, close, base_volume, ...], HANYA candle yang sudah tutup.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

# Modul bersama: path relatif terhadap lokasi file ini
# (skills/multi-token-screener/scripts -> skills/_shared), bukan path absolut.
_SHARED_DIR = Path(__file__).resolve().parents[2] / "_shared"
if str(_SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(_SHARED_DIR))
from candles import _utc_date, session_vwap as _shared_vwap  # noqa: E402

MIN_CANDLE_SESI = 10
CANDLE_MS = 15 * 60 * 1000


def _utc_day(ts_ms):
    return _utc_date(ts_ms)


def session_vwap(closed, atr=None):
    """Hitung VWAP sesi UTC yang memuat candle tutup terakhir.

    Sesi = semua candle dengan tanggal UTC (waktu buka candle) sama dengan candle terakhir.
    typical = (high+low+close)/3, bobot = volume base.
    Mengembalikan dict: vwap (None bila < 10 candle sesi atau volume 0), label, n_candle,
    vwap_jarak_atr, di_atas_vwap, di_bawah_vwap.
    """
    dicts = [{"ts": c[0], "o": c[1], "h": c[2], "l": c[3], "c": c[4], "v": c[5]}
             for c in (closed or [])]
    res = _shared_vwap(dicts, atr)
    return {"vwap": res["vwap"], "label": res["label"], "n_candle": res["n_candle"],
            "vwap_jarak_atr": res["jarak_atr"],
            "di_atas_vwap": res["di_atas"], "di_bawah_vwap": res["di_bawah"]}
