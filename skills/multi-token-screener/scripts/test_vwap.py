"""3 tes VWAP dari addendum. Pindahkan ke test_candle_reader.py bila VWAP ditempel ke candle_reader.py."""
import os
import sys
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vwap  # noqa: E402


def ts(y, mo, d, h, mi):
    return int(datetime(y, mo, d, h, mi, tzinfo=timezone.utc).timestamp() * 1000)


class TestVwap(unittest.TestCase):
    def test_vwap_dihitung_manual(self):
        # typical: (12+8+10)/3=10 ; (14+10+12)/3=12 ; (11+9+10)/3=10
        base = ts(2026, 11, 11, 0, 0)
        candles = [[base + i * vwap.CANDLE_MS, 0, h, l, c, v] for i, (h, l, c, v) in
                   enumerate([(12, 8, 10, 100), (14, 10, 12, 300), (11, 9, 10, 100)])]
        # 7 candle tambahan bervolume 0 agar lolos syarat 10 candle tanpa mengubah VWAP
        pad = [[base + (i + 3) * vwap.CANDLE_MS, 0, 5, 5, 5, 0] for i in range(7)]
        res = vwap.session_vwap(candles + pad)
        self.assertEqual(res["n_candle"], 10)
        # (10*100 + 12*300 + 10*100) / 500 = 11.2
        self.assertAlmostEqual(res["vwap"], 11.2, places=9)

    def test_reset_sesi_tengah_malam_utc(self):
        # 12 candle kemarin (harga 100) lalu 10 candle hari ini (harga 50): VWAP hari ini = 50, bukan campuran
        d0 = ts(2026, 11, 10, 21, 0)
        kemarin = [[d0 + i * vwap.CANDLE_MS, 100, 100, 100, 100, 10] for i in range(12)]  # s/d 23:45
        hari_ini0 = ts(2026, 11, 11, 0, 0)
        hari_ini = [[hari_ini0 + i * vwap.CANDLE_MS, 50, 50, 50, 50, 10] for i in range(10)]
        res = vwap.session_vwap(kemarin + hari_ini)
        self.assertEqual(res["n_candle"], 10)
        self.assertAlmostEqual(res["vwap"], 50.0, places=9)

    def test_vwap_null_bila_sesi_kurang_dari_10_candle(self):
        base = ts(2026, 11, 11, 0, 0)
        candles = [[base + i * vwap.CANDLE_MS, 1, 2, 1, 2, 5] for i in range(9)]
        res = vwap.session_vwap(candles)
        self.assertIsNone(res["vwap"])
        self.assertEqual(res["label"], "VWAP BELUM STABIL")

    def test_jarak_atr_dan_posisi(self):
        base = ts(2026, 11, 11, 0, 0)
        candles = [[base + i * vwap.CANDLE_MS, 10, 10, 10, 10, 1] for i in range(10)]
        candles[-1] = [candles[-1][0], 10, 12, 10, 12, 1]
        res = vwap.session_vwap(candles, atr=0.5)
        self.assertTrue(res["di_atas_vwap"])
        self.assertGreater(res["vwap_jarak_atr"], 0)


if __name__ == "__main__":
    unittest.main()
