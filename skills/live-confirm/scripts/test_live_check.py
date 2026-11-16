import io, json, os, sys, unittest, urllib.error
from unittest import mock
sys.path.insert(0, os.path.dirname(__file__))
import live_check as lc

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def fx(name):
    return open(os.path.join(FIX, name), "rb").read()


class FakeResp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False


def make_urlopen(routes, calls):
    """routes: potongan-url -> bytes | Exception."""
    def fake(req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else req
        calls.append((url, req.get_method() if hasattr(req, "get_method") else "GET", dict(req.headers)))
        for key, val in routes.items():
            if key in url:
                if isinstance(val, Exception):
                    raise val
                return FakeResp(val)
        raise AssertionError("URL tak terduga: " + url)
    return fake


OK = {"/candles": fx("candles5m_lanjut.json"), "/orderbook": fx("orderbook_besar.json"), "/fills": fx("fills_beli.json")}
NOW = 1794488100000 + 60_000  # candle terakhir fixture masih berjalan


def jalan(routes, level=None):
    calls = []
    with mock.patch("urllib.request.urlopen", make_urlopen(routes, calls)):
        out = lc.run("magma", level, now_ms=NOW)
    return out, calls


class LiveCheckTest(unittest.TestCase):
    def test_semua_sukses(self):
        (teks, gagal), calls = jalan(OK, 0.299)
        self.assertEqual(gagal, [])
        self.assertIn("MAGMA order book", teks)
        self.assertIn("MAGMA delta volume", teks)
        self.assertIn("tren 5m", teks)
        self.assertIn("Level 0,299", teks)
        self.assertIn("semua terbaca", teks)

    def test_url_dan_read_only(self):
        _, calls = jalan(OK)
        urls = [c[0] for c in calls]
        self.assertEqual(len(urls), 3)
        self.assertTrue(any("symbol=MAGMAUSDT&granularity=5min&limit=100" in u for u in urls))
        self.assertTrue(any("/orderbook?symbol=MAGMAUSDT&limit=50" in u for u in urls))
        self.assertTrue(any("/fills?symbol=MAGMAUSDT&limit=100" in u for u in urls))
        for u, m, h in calls:
            self.assertTrue(u.startswith("https://api.bitget.com/api/v2/spot/market/"))
            self.assertEqual(m, "GET")
            self.assertFalse(any(k.lower().startswith("access-") for k in h))

    def test_satu_gagal_yang_lain_tetap_tampil(self):
        routes = dict(OK); routes["/orderbook"] = urllib.error.URLError("tidak ada koneksi")
        (teks, gagal), _ = jalan(routes)
        self.assertEqual(gagal, ["orderbook"])
        self.assertIn("orderbook: GAGAL", teks)
        self.assertIn("MAGMA delta volume", teks)
        self.assertIn("Status: GAGAL — orderbook", teks)

    def test_kode_api_bukan_sukses(self):
        routes = dict(OK); routes["/fills"] = json.dumps({"code": "40009", "msg": "sign error", "data": None}).encode()
        (teks, gagal), _ = jalan(routes)
        self.assertEqual(gagal, ["delta"])
        self.assertIn("40009", teks)

    def test_data_tidak_cukup_dihitung_gagal(self):
        routes = dict(OK); routes["/candles"] = json.dumps({"code": "00000", "data": [["1", "1", "1", "1", "1", "1", "1"]]}).encode()
        (_, gagal), _ = jalan(routes)
        self.assertEqual(gagal, ["reader_5m"])

    def test_http_error_dan_semua_gagal(self):
        err = urllib.error.HTTPError("u", 429, "Too Many", {}, None)
        (teks, gagal), _ = jalan({"/candles": err, "/orderbook": err, "/fills": err})
        self.assertEqual(gagal, ["reader_5m", "orderbook", "delta"])
        self.assertIn("HTTP 429", teks)

    def test_main_kode_keluar(self):
        for routes, kode in ((OK, 0), ({**OK, "/fills": urllib.error.URLError("x")}, 2)):
            with mock.patch("urllib.request.urlopen", make_urlopen(routes, [])), \
                 mock.patch("sys.stdout", new_callable=io.StringIO) as out:
                self.assertEqual(lc.main(["--symbol", "MAGMA", "--level", "0.299"]), kode)
            self.assertIn("LIVE CHECK MAGMA", out.getvalue())

    def test_json_gabungan(self):
        calls = []
        with mock.patch("urllib.request.urlopen", make_urlopen(OK, calls)):
            teks, gagal = lc.run_json("magma", 0.299, now_ms=NOW)
        d = json.loads(teks)
        self.assertEqual(gagal, [])
        self.assertTrue(d["ok"])
        self.assertEqual((d["symbol"], d["pair"], d["level"], d["gagal"]), ("MAGMA", "MAGMAUSDT", 0.299, []))
        for k in ("reader_5m", "orderbook", "delta"):
            self.assertTrue(d[k]["ok"])
        self.assertEqual(d["orderbook"]["level"]["verdict"], "TEBAL")
        self.assertEqual(d["delta"]["dominan"], "BELI")

    def test_json_satu_gagal_kode_2_dan_teks_tetap_default(self):
        routes = {**OK, "/orderbook": urllib.error.URLError("putus")}
        with mock.patch("urllib.request.urlopen", make_urlopen(routes, [])), \
             mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            self.assertEqual(lc.main(["--symbol", "MAGMA", "--format", "json"]), 2)
        d = json.loads(out.getvalue())
        self.assertFalse(d["ok"])
        self.assertEqual(d["gagal"], ["orderbook"])
        self.assertIn("putus", d["orderbook"]["reason"])
        self.assertTrue(d["delta"]["ok"])
        with mock.patch("urllib.request.urlopen", make_urlopen(OK, [])), \
             mock.patch("sys.stdout", new_callable=io.StringIO) as out2:
            lc.main(["--symbol", "MAGMA"])
        self.assertTrue(out2.getvalue().startswith("=== LIVE CHECK"))

    def test_simbol_sudah_usdt(self):
        self.assertEqual(lc.pair("magmausdt"), "MAGMAUSDT")
        self.assertEqual(lc.pair(" magma "), "MAGMAUSDT")


if __name__ == "__main__":
    unittest.main()
