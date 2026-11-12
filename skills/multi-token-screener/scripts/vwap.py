"""VWAP sesi harian (anchor 00:00 UTC). Hanya stdlib.

Dibuat terpisah karena candle_reader.py tidak ikut tersedia saat tool ini dibangun.
Fungsi ini siap ditempel/di-import dari candle_reader.read() (addendum 12 Nov 2026),
dan scan.py memakainya sebagai cadangan bila hasil reader belum punya field `vwap`.

Candle: [ts_ms, open, high, low, close, base_volume, ...], HANYA candle yang sudah tutup.
"""

from datetime import datetime, timezone

MIN_CANDLE_SESI = 10
CANDLE_MS = 15 * 60 * 1000


def _utc_day(ts_ms):
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).date()


def session_vwap(closed, atr=None):
    """Hitung VWAP sesi UTC yang memuat candle tutup terakhir.

    Sesi = semua candle dengan tanggal UTC (waktu buka candle) sama dengan candle terakhir.
    typical = (high+low+close)/3, bobot = volume base.
    Mengembalikan dict: vwap (None bila < 10 candle sesi atau volume 0), label, n_candle,
    vwap_jarak_atr, di_atas_vwap, di_bawah_vwap.
    """
    out = {"vwap": None, "label": None, "n_candle": 0, "vwap_jarak_atr": None,
           "di_atas_vwap": None, "di_bawah_vwap": None}
    if not closed:
        out["label"] = "VWAP BELUM STABIL"
        return out
    day = _utc_day(closed[-1][0])
    sesi = [c for c in closed if _utc_day(c[0]) == day]
    out["n_candle"] = len(sesi)
    vol = sum(c[5] for c in sesi)
    if len(sesi) < MIN_CANDLE_SESI or vol <= 0:
        out["label"] = "VWAP BELUM STABIL"
        return out
    vwap = sum(((c[2] + c[3] + c[4]) / 3) * c[5] for c in sesi) / vol
    last = closed[-1][4]
    out.update(vwap=vwap, di_atas_vwap=last > vwap, di_bawah_vwap=last < vwap)
    if atr:
        out["vwap_jarak_atr"] = (last - vwap) / atr
    return out
