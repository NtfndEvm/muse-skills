"""Jalankan: python -m unittest -v test_candle_reader   (dari folder scripts)"""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import candle_reader as cr  # noqa: E402

STEP = 15 * 60_000
T0 = 1_760_000_000_000 // STEP * STEP


def mk(ts_i, o, h, l, c, v=100.0):
    return {"ts": T0 + ts_i * STEP, "o": o, "h": h, "l": l, "c": c, "v": v}


def base_range(n=100):
    """Osilasi sinus 95..99.5 dengan puncak (high ~99.8) dan lembah (low ~94.7) berulang."""
    out, prev = [], 97.0
    for i in range(n):
        c = 97.25 + 2.25 * math.sin(i * 2 * math.pi / 12)
        o = prev
        out.append(mk(i, o, max(o, c) + 0.3, min(o, c) - 0.3, c))
        prev = c
    return out


def now_after(candles):
    return candles[-1]["ts"] + STEP + 1  # semua candle sudah tutup


class IndicatorTests(unittest.TestCase):
    def test_ema_seed_and_value(self):
        vals = [1, 2, 3, 4, 5, 6]
        e = cr.ema(vals, 3)
        self.assertIsNone(e[1])
        self.assertAlmostEqual(e[2], 2.0)
        self.assertAlmostEqual(e[3], 3.0)  # 4*0.5 + 2*0.5

    def test_atr_constant_range(self):
        cs = [mk(i, 10, 11, 9, 10) for i in range(30)]
        a = cr.atr(cs, 14)
        self.assertAlmostEqual(a[-1], 2.0)

    def test_cluster_groups_close_prices(self):
        pts = [(1, 100.0), (5, 100.1), (9, 105.0)]
        cl = cr.cluster(pts, 0.5)
        self.assertEqual(len(cl), 2)
        self.assertEqual(cl[0]["touches"], 2)

    def test_parse_array_and_dict_and_seconds(self):
        raw = [[T0 // 1000, "1", "2", "0.5", "1.5", "10"], {"ts": T0 + STEP, "o": 1, "h": 2, "l": 1, "c": 2, "v": 3}]
        cs = cr.parse_candles(raw)
        self.assertEqual(cs[0]["ts"], T0)
        self.assertEqual(len(cs), 2)
        self.assertEqual(cs[0]["h"], 2.0)

    def test_parse_dedupes_and_sorts(self):
        raw = [[T0 + STEP, 1, 2, 1, 2, 1], [T0, 1, 2, 1, 2, 1], [T0, 1, 2, 1, 2, 1]]
        self.assertEqual([c["ts"] for c in cr.parse_candles(raw)], [T0, T0 + STEP])


class ReadTests(unittest.TestCase):
    def test_insufficient_data(self):
        cs = base_range(20)
        r = cr.read(cs, now_ms=now_after(cs))
        self.assertFalse(r["ok"])

    def test_forming_candle_dropped(self):
        cs = base_range(100)
        r = cr.read(cs, now_ms=cs[-1]["ts"] + 1000)  # candle terakhir belum tutup
        self.assertTrue(r["ok"])
        self.assertTrue(any("masih berjalan" in w for w in r["warnings"]))
        self.assertEqual(r["last_closed_wib"], cr.datetime.fromtimestamp(cs[-2]["ts"] / 1000, cr.WIB).strftime("%Y-%m-%d %H:%M"))

    def test_assume_closed_keeps_last(self):
        cs = base_range(100)
        r = cr.read(cs, assume_closed=True)
        self.assertEqual(r["last_closed_wib"], cr.datetime.fromtimestamp(cs[-1]["ts"] / 1000, cr.WIB).strftime("%Y-%m-%d %H:%M"))

    def _with_pullback(self):
        cs = base_range(100)
        n = len(cs)
        cs.append(mk(n, cs[-1]["c"], 99.0, 98.2, 98.5))  # close di bawah resistance ~99.8
        return cs

    def test_confirmed_breakout(self):
        cs = self._with_pullback()
        n = len(cs)
        cs.append(mk(n, 99.6, 101.7, 99.5, 101.5, v=300))
        r = cr.read(cs, now_ms=now_after(cs))
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["breakout"]["state"], "BREAKOUT_TERKONFIRMASI", r["breakout"])

    def test_weak_breakout_low_volume(self):
        cs = self._with_pullback()
        n = len(cs)
        cs.append(mk(n, 99.6, 101.7, 99.5, 101.5, v=100))
        r = cr.read(cs, now_ms=now_after(cs))
        self.assertEqual(r["breakout"]["state"], "BREAKOUT_LEMAH")
        self.assertIn("volume belum tinggi", r["breakout"]["kekurangan"])

    def test_wick_rejection(self):
        cs = self._with_pullback()
        n = len(cs)
        cs.append(mk(n, 99.0, 101.0, 98.9, 99.3, v=250))
        r = cr.read(cs, now_ms=now_after(cs))
        self.assertEqual(r["breakout"]["state"], "PENOLAKAN_SUMBU")

    def test_resistance_layers_detected_in_range(self):
        cs = base_range(100)
        r = cr.read(cs, now_ms=now_after(cs))
        self.assertTrue(r["ok"])
        self.assertIsInstance(r["resistance"]["level_di_atas"], list)

    def _support_setup(self):
        cs = base_range(100)
        n = len(cs)
        cs.append(mk(n, 96.5, 96.6, 94.7, 95.0, v=100))  # turun ke support
        return cs

    def test_bounce_candidate_then_confirmed(self):
        cs = self._support_setup()
        n = len(cs)
        cs.append(mk(n, 94.9, 96.2, 94.75, 96.0, v=150))  # candle bounce
        r1 = cr.read(cs, now_ms=now_after(cs))
        self.assertEqual(r1["bounce"]["state"], "KANDIDAT_BOUNCE", r1["bounce"])
        n = len(cs)
        cs.append(mk(n, 96.0, 97.4, 95.9, 97.2, v=140))  # tutup di atas high candle bounce
        r2 = cr.read(cs, now_ms=now_after(cs))
        self.assertEqual(r2["bounce"]["state"], "BOUNCE_TERKONFIRMASI", r2["bounce"])

    def test_support_broken(self):
        cs = self._support_setup()
        n = len(cs)
        cs.append(mk(n, 94.9, 96.2, 94.75, 96.0, v=150))
        n = len(cs)
        cs.append(mk(n, 96.0, 96.1, 92.0, 92.5, v=200))  # patah jauh di bawah support
        r = cr.read(cs, now_ms=now_after(cs))
        self.assertNotEqual(r["bounce"]["state"], "BOUNCE_TERKONFIRMASI")

    def test_trend_uptrend_on_rising_series(self):
        cs = []
        p = 100.0
        for i in range(120):
            o, c = p, p + 0.3
            cs.append(mk(i, o, c + 0.1, o - 0.1, c))
            p = c
        r = cr.read(cs, now_ms=now_after(cs))
        self.assertEqual(r["trend"]["state"], "UPTREND")

    def test_zero_volume_warns(self):
        cs = [dict(c, v=0.0) for c in base_range(100)]
        r = cr.read(cs, now_ms=now_after(cs))
        self.assertTrue(r["ok"])
        self.assertIsNone(r["volume"]["ratio"])
        self.assertTrue(any("volume" in w for w in r["warnings"]))

    def test_deterministic(self):
        cs = base_range(100)
        a = cr.read(cs, now_ms=now_after(cs))
        b = cr.read(cs, now_ms=now_after(cs))
        self.assertEqual(a, b)

    def test_text_output_has_disclaimer(self):
        cs = base_range(100)
        txt = cr.to_text(cr.read(cs, now_ms=now_after(cs)))
        self.assertIn("bukan sinyal", txt)


# --------------------------------------------------------------------- VWAP
from datetime import datetime, timezone  # noqa: E402


def utc_ms(y, mo, d, h, mi):
    return int(datetime(y, mo, d, h, mi, tzinfo=timezone.utc).timestamp() * 1000)


def mkc(ts, o, h, l, c, v):
    return {"ts": ts, "o": o, "h": h, "l": l, "c": c, "v": v}


def shifted_range(last_open_ms):
    """base_range(100) dengan timestamp digeser agar candle terakhir buka di last_open_ms."""
    return [dict(c, ts=last_open_ms - (99 - i) * STEP) for i, c in enumerate(base_range(100))]


class VwapTests(unittest.TestCase):
    def test_vwap_dihitung_manual(self):
        # typical: (12+8+10)/3=10 ; (14+10+12)/3=12 ; (11+9+10)/3=10 ; volume 100/300/100
        base = utc_ms(2026, 11, 11, 0, 0)
        cs = [mkc(base + i * STEP, 0, h, l, c, v) for i, (h, l, c, v) in
              enumerate([(12, 8, 10, 100), (14, 10, 12, 300), (11, 9, 10, 100)])]
        # 7 candle tambahan bervolume 0 agar lolos syarat 10 candle tanpa mengubah VWAP
        cs += [mkc(base + (i + 3) * STEP, 0, 5, 5, 5, 0) for i in range(7)]
        res = cr.session_vwap(cs)
        self.assertEqual(res["n_candle"], 10)
        self.assertAlmostEqual(res["vwap"], 11.2, places=9)  # (10*100+12*300+10*100)/500

    def test_vwap_reset_sesi_tengah_malam_utc(self):
        # 12 candle kemarin (harga 100, 21:00-23:45 UTC) lalu 10 candle hari ini (harga 50)
        d0 = utc_ms(2026, 11, 10, 21, 0)
        kemarin = [mkc(d0 + i * STEP, 100, 100, 100, 100, 10) for i in range(12)]
        h0 = utc_ms(2026, 11, 11, 0, 0)
        hari_ini = [mkc(h0 + i * STEP, 50, 50, 50, 50, 10) for i in range(10)]
        res = cr.session_vwap(kemarin + hari_ini)
        self.assertEqual(res["n_candle"], 10)
        self.assertAlmostEqual(res["vwap"], 50.0, places=9)  # bukan campuran 100 dan 50

    def test_vwap_null_bila_sesi_kurang_dari_10_candle(self):
        base = utc_ms(2026, 11, 11, 0, 0)
        cs = [mkc(base + i * STEP, 1, 2, 1, 2, 5) for i in range(9)]
        res = cr.session_vwap(cs)
        self.assertIsNone(res["vwap"])
        self.assertEqual(res["label"], "VWAP BELUM STABIL")

    def test_vwap_jarak_atr_dan_posisi(self):
        base = utc_ms(2026, 11, 11, 0, 0)
        cs = [mkc(base + i * STEP, 10, 10, 10, 10, 1) for i in range(10)]
        cs[-1] = mkc(cs[-1]["ts"], 10, 12, 10, 12, 1)
        res = cr.session_vwap(cs, atr_value=0.5)
        self.assertTrue(res["di_atas"])
        self.assertFalse(res["di_bawah"])
        self.assertGreater(res["jarak_atr"], 0)

    def test_read_memuat_field_vwap_dan_bentuk_lama_tetap(self):
        cs = shifted_range(utc_ms(2026, 11, 11, 12, 0))
        r = cr.read(cs, now_ms=now_after(cs))
        self.assertTrue(r["ok"])
        exp = cr.session_vwap(cs)
        self.assertEqual(r["vwap_n_candle"], 49)  # 00:00..12:00 UTC
        self.assertAlmostEqual(r["vwap"], round(exp["vwap"], 8), places=8)
        self.assertEqual(r["di_atas_vwap"], cs[-1]["c"] > exp["vwap"])
        self.assertEqual(r["di_bawah_vwap"], cs[-1]["c"] < exp["vwap"])
        self.assertIsNone(r["vwap_label"])
        # bentuk bertingkat yang dipakai scan.py tidak boleh berubah
        self.assertIsInstance(r["trend"], dict)
        self.assertIsInstance(r["resistance"], dict)
        self.assertIn("level_di_atas", r["resistance"])

    def test_read_vwap_null_dan_berlabel_bila_sesi_baru_mulai(self):
        cs = shifted_range(utc_ms(2026, 11, 11, 1, 0))  # baru 5 candle sejak 00:00 UTC
        r = cr.read(cs, now_ms=now_after(cs))
        self.assertTrue(r["ok"])
        self.assertIsNone(r["vwap"])
        self.assertIsNone(r["di_atas_vwap"])
        self.assertEqual(r["vwap_label"], "VWAP BELUM STABIL")
        self.assertEqual(r["vwap_n_candle"], 5)

    def test_teks_memuat_baris_vwap(self):
        cs = shifted_range(utc_ms(2026, 11, 11, 12, 0))
        self.assertIn("VWAP sesi (00:00 UTC)", cr.to_text(cr.read(cs, now_ms=now_after(cs))))
        cs2 = shifted_range(utc_ms(2026, 11, 11, 1, 0))
        self.assertIn("VWAP BELUM STABIL", cr.to_text(cr.read(cs2, now_ms=now_after(cs2))))


if __name__ == "__main__":
    unittest.main()
