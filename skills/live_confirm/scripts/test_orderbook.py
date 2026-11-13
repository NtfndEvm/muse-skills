import json, os, sys, unittest
sys.path.insert(0, os.path.dirname(__file__))
import orderbook as ob

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def load(name):
    return json.load(open(os.path.join(FIX, name), encoding="utf-8"))


class OrderbookTest(unittest.TestCase):
    def test_angka_pasti_buku_kecil(self):
        r = ob.analyze(load("orderbook_kecil.json"))
        self.assertTrue(r["ok"])
        self.assertAlmostEqual(r["mid"], 1.0)
        self.assertAlmostEqual(r["spread_pct"], 2.0)
        self.assertAlmostEqual(r["total_bid_usdt"], 99.0)   # hanya 0.99 x 100 dalam ±1%
        self.assertAlmostEqual(r["total_ask_usdt"], 101.0)
        self.assertAlmostEqual(r["imbalance"], 0.495)
        self.assertEqual(r["imbalance_label"], "SEIMBANG")
        self.assertEqual([round(w["usdt"], 2) for w in r["tembok_bid"]], [900.0, 196.0, 99.0])
        self.assertEqual([round(w["usdt"], 2) for w in r["tembok_ask"]], [600.0, 306.0, 101.0])

    def test_level_tebal_dan_tipis(self):
        tebal = ob.analyze(load("orderbook_kecil.json"), level=0.98)
        self.assertAlmostEqual(tebal["level"]["depth_bid_usdt"], 196.0)
        self.assertEqual(tebal["level"]["verdict"], "TEBAL")
        tipis = ob.analyze(load("orderbook_kecil.json"), level=1.1)
        self.assertEqual(tipis["level"]["verdict"], "TIPIS")
        self.assertEqual(tipis["level"]["depth_ask_usdt"], 0.0)

    def test_level_di_luar_jangkauan_diberi_peringatan(self):
        r = ob.analyze(load("orderbook_kecil.json"), level=0.5)
        self.assertTrue(any("luar jangkauan" in w for w in r["warnings"]))
        self.assertEqual(r["level"]["verdict"], "TIDAK TERUKUR")  # depth 0 karena tak terukur, bukan tipis
        self.assertIn("TIDAK TERUKUR", ob.to_text(r))
        self.assertNotIn("TIPIS", ob.to_text(r))

    def test_buku_besar_dibungkus_data(self):
        r = ob.analyze(load("orderbook_besar.json"))
        self.assertTrue(r["ok"])
        self.assertGreater(r["imbalance"], 0.6)
        self.assertEqual(r["imbalance_label"], "BID DOMINAN")
        self.assertAlmostEqual(r["tembok_bid"][0]["price"], 0.2990)
        self.assertAlmostEqual(r["tembok_ask"][0]["price"], 0.3040)
        self.assertEqual(r["warnings"], [])

    def test_urutan_input_acak_tidak_masalah(self):
        raw = load("orderbook_kecil.json")
        raw["bids"].reverse(); raw["asks"].reverse()
        self.assertAlmostEqual(ob.analyze(raw)["best_bid"], 0.99)

    def test_jangkauan_tipis_diperingatkan(self):
        r = ob.analyze(load("orderbook_kecil.json"))
        self.assertTrue(any("tidak lengkap" in w for w in r["warnings"]) is False)  # bid 0.90 & ask 1.20 melewati ±1%
        pendek = {"bids": [["0.999", "10"]], "asks": [["1.001", "10"]]}
        self.assertEqual(len(ob.analyze(pendek)["warnings"]), 2)

    def test_data_buruk(self):
        self.assertFalse(ob.analyze({"bids": [], "asks": [["1", "1"]]})["ok"])
        self.assertFalse(ob.analyze({"bids": [["1.1", "1"]], "asks": [["1.0", "1"]]})["ok"])
        self.assertFalse(ob.analyze([1, 2])["ok"])

    def test_format_indonesia(self):
        t = ob.to_text(ob.analyze(load("orderbook_besar.json"), level=0.2990), "MAGMA")
        self.assertIn("imbalance 0,70", t)
        self.assertIn("247.840,00 USDT", t)
        self.assertIn("TEBAL", t)

    def test_idn_usdt(self):
        self.assertEqual(ob.idn_usdt(1234567.891), "1.234.567,89")


if __name__ == "__main__":
    unittest.main()
