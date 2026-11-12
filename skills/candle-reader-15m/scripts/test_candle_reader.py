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


if __name__ == "__main__":
    unittest.main()
