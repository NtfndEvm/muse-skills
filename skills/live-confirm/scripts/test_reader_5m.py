import json, os, re, sys, unittest
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(__file__))
import reader_5m as r

FIX = os.path.join(os.path.dirname(__file__), "fixtures")
NOW = int(datetime(2026, 11, 12, 12, 57, tzinfo=timezone.utc).timestamp() * 1000)  # candle 12:55 masih berjalan


def load(name):
    return json.load(open(os.path.join(FIX, name), encoding="utf-8"))["data"]


class Reader5mTest(unittest.TestCase):
    def test_interval_default_5(self):
        self.assertEqual(r.DEFAULTS["interval_min"], 5)

    def test_urutan_dan_candle_berjalan_dibuang(self):
        raw = load("candles5m_lanjut.json")  # terbaru dulu
        self.assertGreater(int(raw[0][0]), int(raw[-1][0]))
        c = r.parse_candles(raw)
        self.assertTrue(all(c[i]["ts"] < c[i + 1]["ts"] for i in range(len(c) - 1)))
        res = r.analyze(raw, now_ms=NOW)
        self.assertTrue(res["ok"])
        self.assertEqual(res["last_closed_wib"], "2026-11-12 19:50")
        self.assertTrue(any("berjalan" in w for w in res["warnings"]))

    def test_assume_closed_tidak_membuang(self):
        res = r.analyze(load("candles5m_lanjut.json"), assume_closed=True)
        self.assertEqual(res["last_closed_wib"], "2026-11-12 19:55")

    def test_diteruskan(self):
        res = r.analyze(load("candles5m_lanjut.json"), now_ms=NOW)
        self.assertEqual(res["fast"]["status"], "DITERUSKAN")
        self.assertIn("higher high", res["fast"]["kalimat"])
        self.assertIn("diteruskan", res["fast"]["kalimat"])
        self.assertEqual(res["volume"]["label"], "TINGGI")

    def test_melemah(self):
        res = r.analyze(load("candles5m_lemah.json"), now_ms=NOW)
        self.assertEqual(res["fast"]["status"], "MELEMAH")
        self.assertIn("sumbu atas panjang", res["fast"]["lemah"])
        self.assertIn("volume turun", res["fast"]["lemah"])
        self.assertIn("melemah", res["fast"]["kalimat"])

    def test_vwap_sesi_tersedia(self):
        res = r.analyze(load("candles5m_lanjut.json"), now_ms=NOW)
        self.assertIsNotNone(res["vwap"])
        self.assertGreaterEqual(res["vwap_n_candle"], 10)

    def test_data_kurang(self):
        res = r.analyze(load("candles5m_lanjut.json")[:20], now_ms=NOW)
        self.assertFalse(res["ok"])
        self.assertIn("tidak bisa dibaca", r.to_line(res, "X"))

    def test_format_koma_indonesia(self):
        line = r.to_line(r.analyze(load("candles5m_lanjut.json"), now_ms=NOW), "MAGMA").splitlines()[0]
        self.assertTrue(line.startswith("MAGMA 0,2656"))
        self.assertIsNone(re.search(r"\d\.\d", line))

    def test_idn(self):
        self.assertEqual(r.idn(0.30178), "0,30178")
        self.assertEqual(r.idn(0.000001234), "0,000001234")
        self.assertEqual(r.idn(None), "-")

    def test_cli_json(self):
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = r.main(["--file", os.path.join(FIX, "candles5m_lemah.json"), "--now-ms", str(NOW), "--format", "json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(buf.getvalue())["fast"]["status"], "MELEMAH")


if __name__ == "__main__":
    unittest.main()
