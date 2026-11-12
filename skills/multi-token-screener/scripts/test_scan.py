import contextlib
import io
import json
import os
import sys
import tempfile
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scan  # noqa: E402

NOW = 1_794_000_000_000 - (1_794_000_000_000 % scan.CANDLE_MS) + 5 * 60 * 1000  # 5 menit setelah batas 15m


def ticker_row(sym, last="0.004414", bid="0.004412", ask="0.004418", vol="137961", chg="0.005"):
    return {"symbol": sym + "USDT", "lastPr": last, "bidPr": bid, "askPr": ask, "usdtVolume": vol,
            "change24h": chg, "high24h": "0.0046", "low24h": "0.0043"}


def candle_rows(n=100, price=1.0):
    """n candle tutup + 1 candle berjalan, urutan TERBARU DULU seperti API."""
    last_open_running = NOW - NOW % scan.CANDLE_MS
    rows = []
    for i in range(n + 1):
        ts = last_open_running - i * scan.CANDLE_MS
        rows.append([str(ts), str(price), str(price * 1.01), str(price * 0.99), str(price), "1000", "1000", "1000"])
    return rows


class FakeNet:
    def __init__(self, tickers, candles=None, fail=False):
        self.tickers, self.candles, self.fail = tickers, candles, fail

    def __call__(self, url, sleep=None):
        if self.fail:
            raise scan.FetchError("jaringan: mati")
        if "/tickers" in url:
            return self.tickers
        assert "granularity=15min" in url, url
        return self.candles if self.candles is not None else candle_rows()


def reading(**kw):
    base = {"trend": "RANGE", "breakout": "TIDAK_ADA", "bounce": "TIDAK_ADA", "resistance": [], "support": [],
            "atr_pct": 0.8, "atr": 0.008}
    base.update(kw)
    return base


def with_reader(res):
    scan._reader = types.SimpleNamespace(read=lambda candles: res)


def run_main(args, net):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = scan.main(args, now_ms=NOW, fetcher=net)
    return code, out.getvalue()


class TestParsing(unittest.TestCase):
    def test_parse_ticker(self):
        t = scan.parse_ticker(ticker_row("BEAM"))
        self.assertAlmostEqual(t["last"], 0.004414)
        self.assertAlmostEqual(t["spread_pct"], (0.004418 - 0.004412) / 0.004414 * 100)
        self.assertFalse(t["book_rusak"])

    def test_spread_rusak_ask_nol(self):
        t = scan.parse_ticker(ticker_row("BEAM", ask="0"))
        self.assertTrue(t["book_rusak"])
        self.assertIsNone(t["spread_pct"])
        r = scan.analyze("BEAM", {"BEAMUSDT": t}, "http://x", set(), NOW, FakeNet([]))
        self.assertEqual(r["verdict"], "BOOK RUSAK")

    def test_book_rusak_tampil_di_tabel_tanpa_crash(self):
        t = scan.parse_ticker(ticker_row("BAD", ask="0"))
        r = scan.analyze("BAD", {"BADUSDT": t}, "http://x", set(), NOW, FakeNet([]))
        out = scan.render_table([r], NOW)
        self.assertIn("BOOK RUSAK", out)

    def test_parse_candles_diurutkan_naik_dan_dedupe(self):
        rows = candle_rows(5) + candle_rows(5)[:2]
        cs = scan.parse_candles(rows)
        self.assertEqual([c[0] for c in cs], sorted(c[0] for c in cs))
        self.assertEqual(len(cs), 6)
        self.assertEqual(len(cs[0]), 6)

    def test_filter_volume(self):
        self.assertEqual(scan.volume_status(99_999, "X", set()), "GUGUR")
        self.assertEqual(scan.volume_status(100_000, "X", set()), "LOLOS")
        self.assertEqual(scan.volume_status(5_000, "X", {"X"}), "LOLOS BERSYARAT")

    def test_rumus_biaya(self):
        self.assertAlmostEqual(scan.break_even_pct(0.10), 0.30)
        self.assertAlmostEqual(scan.net_rr_stop2(0.10), (4 - 0.3) / (2 + 0.3))

    def test_format_watchlist(self):
        ok = scan.validate_watchlist([{"symbol": "beam", "trigger": "close_di_atas", "level": "0.004526"}])
        self.assertEqual(ok[0]["symbol"], "BEAM")
        self.assertEqual(ok[0]["level"], 0.004526)
        for bad in ({"symbol": "A", "trigger": "ngawur", "level": 1}, {"symbol": "A"}, "bukan objek"):
            with self.assertRaises(SystemExit):
                scan.validate_watchlist([bad])

    def test_watchlist_dibuat_bila_belum_ada(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "watchlist.json")
            with contextlib.redirect_stderr(io.StringIO()):
                wl = scan.load_watchlist(p)
            self.assertEqual(len(wl), 6)
            with open(p) as fh:
                self.assertEqual(json.load(fh)[0]["symbol"], "BEAM")


class TestPipeline(unittest.TestCase):
    def tearDown(self):
        scan._reader = None

    def test_tidak_ditemukan_exit_0_dan_lanjut(self):
        with_reader(reading())
        net = FakeNet([ticker_row("TOKENYA")])
        code, out = run_main(["TOKENYA", "NGADA"], net)
        self.assertEqual(code, 0)
        self.assertIn("NGADA/USDT", out)
        self.assertIn("TIDAK DITEMUKAN", out)
        self.assertIn("TOKENYA/USDT", out)

    def test_offline_gagal_ambil_data_bukan_crash(self):
        code, out = run_main(["BEAM"], FakeNet([], fail=True))
        self.assertEqual(code, 0)
        self.assertIn("GAGAL AMBIL DATA", out)

    def test_candle_berjalan_dibuang_dan_waktu_tutup(self):
        with_reader(reading())
        r = scan.analyze("BEAM", {"BEAMUSDT": scan.parse_ticker(ticker_row("BEAM"))}, "http://x", set(), NOW,
                         FakeNet([], candle_rows()))
        self.assertEqual(r["candle_berjalan_dibuang"], 1)
        self.assertEqual(r["last_closed_ms"] % scan.CANDLE_MS, 0)
        self.assertLessEqual(r["last_closed_ms"], NOW)
        self.assertFalse(r["data_basi"])

    def test_data_kurang(self):
        with_reader(reading())
        r = scan.analyze("BEAM", {"BEAMUSDT": scan.parse_ticker(ticker_row("BEAM"))}, "http://x", set(), NOW,
                         FakeNet([], candle_rows(40)))
        self.assertEqual(r["verdict"], "DATA KURANG")

    def test_kandidat_bounce_range_sempit_ditolak(self):
        with_reader(reading(bounce="KANDIDAT_BOUNCE", resistance=[(1.006, 0.8)]))
        r = scan.analyze("BEAM", {"BEAMUSDT": scan.parse_ticker(ticker_row("BEAM", last="1.0", bid="0.9995", ask="1.0005"))},
                         "http://x", set(), NOW, FakeNet([], candle_rows()))
        self.assertEqual(r["verdict"], "DITOLAK")
        self.assertIn("ruang ke resistance", r["alasan"])

    def test_breakout_terkonfirmasi_lolos_dan_no_trade_bila_tidak_ada(self):
        with_reader(reading(breakout="BREAKOUT_TERKONFIRMASI", resistance=[(1.08, 1.0)]))
        tick = {"BEAMUSDT": scan.parse_ticker(ticker_row("BEAM", last="1.0", bid="0.9995", ask="1.0005"))}
        r = scan.analyze("BEAM", tick, "http://x", set(), NOW, FakeNet([], candle_rows()))
        self.assertEqual(r["verdict"], "LOLOS")
        self.assertIn("1 KANDIDAT (BEAM)", scan.render_table([r], NOW))
        with_reader(reading())
        r2 = scan.analyze("BEAM", tick, "http://x", set(), NOW, FakeNet([], candle_rows()))
        self.assertIn("Verdict: NO TRADE", scan.render_table([r2], NOW))

    def test_volume_kecil_ditolak_kecuali_disarankan_user(self):
        with_reader(reading(breakout="BREAKOUT_TERKONFIRMASI", resistance=[(1.08, 1.0)]))
        tick = {"BEAMUSDT": scan.parse_ticker(ticker_row("BEAM", last="1.0", bid="0.9995", ask="1.0005", vol="5000"))}
        self.assertEqual(scan.analyze("BEAM", tick, "http://x", set(), NOW, FakeNet([], candle_rows()))["verdict"], "DITOLAK")
        r = scan.analyze("BEAM", tick, "http://x", {"BEAM"}, NOW, FakeNet([], candle_rows()))
        self.assertEqual(r["verdict"], "LOLOS")
        self.assertEqual(r["volume_status"], "LOLOS BERSYARAT")

    def test_reader_tidak_ada_tidak_crash(self):
        # Sembunyikan reader dari SEMUA jalur load_reader(): env, HERE, dan
        # fallback ~/workspace (di VM ini file aslinya ADA di sana, jadi
        # tanpa HOME palsu load_reader tetap menemukannya dan tes ini gagal).
        scan._reader = None
        os.environ["CANDLE_READER_DIR"] = "/tidak/ada"
        old_home = os.environ.get("HOME")
        os.environ["HOME"] = "/tidak/ada/home"
        orig = scan.HERE
        scan.HERE = scan.Path("/tidak/ada/a/b")
        try:
            r = scan.analyze("BEAM", {"BEAMUSDT": scan.parse_ticker(ticker_row("BEAM"))}, "http://x", set(), NOW,
                             FakeNet([], candle_rows()))
        finally:
            scan.HERE = orig
            os.environ.pop("CANDLE_READER_DIR")
            if old_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = old_home
        self.assertEqual(r["verdict"], "PANTAU")
        self.assertIn("candle_reader.py tidak ditemukan", r["alasan"])

    def test_discover_menyaring_bigcap_saham_volume_dan_skip(self):
        tick = {}
        for s, vol, chg in [("BTC", 9e9, 0.9), ("RNVDA", 1e6, 0.8), ("LOWV", 5000, 0.7), ("DOS", 2e5, 0.6),
                            ("AAA", 3e5, -0.5), ("BBB", 3e5, 0.1)]:
            t = scan.parse_ticker(ticker_row(s, vol=str(vol), chg=str(chg)))
            tick[t["symbol"]] = t
        self.assertEqual(scan.discover(tick, 5, {"DOS"}), ["AAA", "BBB"])
        self.assertEqual(scan.discover(tick, 1, set()), ["DOS"])

    def test_json_output(self):
        with_reader(reading())
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "out.json")
            run_main(["BEAM", "--json", p], FakeNet([ticker_row("BEAM", last="1.0", bid="0.9995", ask="1.0005")]))
            with open(p) as fh:
                data = json.load(fh)
            self.assertIn("checked_at_wib", data)
            self.assertEqual(data["tokens"][0]["symbol"], "BEAM")
            self.assertIn("net_rr_stop2", data["tokens"][0])

    def test_watchlist_trigger(self):
        r = {"last_close": 0.0046, "spread_pct": 0.1}
        self.assertEqual(scan.eval_trigger({"trigger": "close_di_atas", "level": 0.004526}, r)[0], "TERPICU")
        self.assertEqual(scan.eval_trigger({"trigger": "close_di_atas", "level": 0.005}, r)[0], "BELUM")
        self.assertEqual(scan.eval_trigger({"trigger": "close_di_bawah", "level": 0.005}, r)[0], "TERPICU")


if __name__ == "__main__":
    unittest.main()
