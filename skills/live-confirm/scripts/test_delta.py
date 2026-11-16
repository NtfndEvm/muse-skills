import json, os, sys, unittest
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(__file__))
import delta as d

FIX = os.path.join(os.path.dirname(__file__), "fixtures")
WIB = timezone(timedelta(hours=7))


def load(name):
    return json.load(open(os.path.join(FIX, name), encoding="utf-8"))


class DeltaTest(unittest.TestCase):
    def test_hitungan_pasti_beli(self):
        r = d.analyze(load("fills_beli.json"))  # dibungkus {"data": ...}, terbaru dulu
        self.assertTrue(r["ok"])
        self.assertAlmostEqual(r["volume_beli_usdt"], 50.0)
        self.assertAlmostEqual(r["volume_jual_usdt"], 20.0)
        self.assertAlmostEqual(r["delta_pct"], 30 / 70 * 100)
        self.assertEqual((r["n_buy"], r["n_sell"]), (2, 2))
        self.assertEqual(r["dominan"], "BELI")
        self.assertEqual([round(t["usdt"], 2) for t in r["trade_terbesar"]], [30.0, 20.0, 10.0])
        self.assertAlmostEqual(r["durasi_detik"], 3.0)
        exp = datetime.fromtimestamp(1762952400, WIB).strftime("%Y-%m-%d %H:%M:%S")
        self.assertEqual(r["dari_wib"], exp)

    def test_jual_dominan_array_telanjang(self):
        r = d.analyze(load("fills_jual.json"))
        self.assertAlmostEqual(r["volume_jual_usdt"], 180.0)
        self.assertAlmostEqual(r["volume_beli_usdt"], 30.0)
        self.assertEqual(r["dominan"], "JUAL")
        self.assertLess(r["delta_pct"], 0)

    def test_seimbang(self):
        raw = [{"side": "buy", "price": "1", "size": "10", "ts": "1000000000000"},
               {"side": "sell", "price": "1", "size": "10", "ts": "1000000001000"}]
        r = d.analyze(raw)
        self.assertEqual(r["dominan"], "SEIMBANG")
        self.assertAlmostEqual(r["delta_pct"], 0.0)

    def test_batas_100_trade_terbaru(self):
        raw = [{"side": "buy", "price": "1", "size": "1", "ts": str(1000000000000 + i)} for i in range(150)]
        r = d.analyze(raw)
        self.assertEqual(r["n_trade"], 100)
        self.assertEqual(r["durasi_detik"], 0.099)

    def test_trade_tidak_valid_dilewati(self):
        raw = load("fills_jual.json") + [{"side": "foo", "price": "1", "size": "1", "ts": "1"}, {"price": "x"}]
        r = d.analyze(raw)
        self.assertEqual(r["n_trade"], 3)
        self.assertTrue(any("2 trade dilewati" in w for w in r["warnings"]))

    def test_kosong_dan_format_salah(self):
        self.assertFalse(d.analyze([])["ok"])
        self.assertFalse(d.analyze("x")["ok"])

    def test_teks_indonesia(self):
        t = d.to_text(d.analyze(load("fills_beli.json")), "MAGMA")
        self.assertIn("delta 42,9%", t)
        self.assertIn("agresi BELI dominan", t)
        self.assertIn("sampel hanya 4 trade", t)

    def test_ts_detik_dikonversi(self):
        r = d.analyze([{"side": "buy", "price": "1", "size": "1", "ts": "1762952400"}])
        self.assertEqual(r["dari_wib"], datetime.fromtimestamp(1762952400, WIB).strftime("%Y-%m-%d %H:%M:%S"))


if __name__ == "__main__":
    unittest.main()
