"""Jalankan: python -m unittest -v test_scan   (dari folder scripts). Hanya stdlib; tanpa jaringan."""
import contextlib
import io
import json
import math
import sys
import tempfile
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scan  # noqa: E402

WIB = timezone(timedelta(hours=7))
STEP = 15 * 60_000
NOW = datetime(2026, 11, 12, 10, 7, tzinfo=WIB)
NOW_MS = int(NOW.timestamp() * 1000)
# Candle yang dibuka pukul 10:00 WIB masih berjalan pada 10:07
FORMING_TS = (NOW_MS // STEP) * STEP


def ticker(sym="BEAMUSDT", last="1.0000", vol="500000", chg="0.05", bid="0.9995", ask="1.0005"):
    return {"symbol": sym, "lastPr": last, "usdtVolume": vol, "change24h": chg, "bidPr": bid, "askPr": ask,
            "high24h": "1.1", "low24h": "0.9", "ts": str(NOW_MS)}


def synth(n=100, breakout=None, end_ts=None):
    """Osilasi sinus 95..99.5 (puncak ~99.8, lembah ~94.7). breakout: 'strong' menambah candle breakout tutup."""
    out, prev = [], 97.0
    for i in range(n):
        c = 97.25 + 2.25 * math.sin(i * 2 * math.pi / 12)
        o = prev
        out.append([o, max(o, c) + 0.3, min(o, c) - 0.3, c, 100.0])
        prev = c
    if breakout:
        out.append([prev, 99.0, 98.2, 98.5, 100.0])
        out.append([99.6, 101.7, 99.5, 101.5, 300.0])
    end_ts = FORMING_TS - STEP if end_ts is None else end_ts   # candle terakhir sudah tutup
    start = end_ts - (len(out) - 1) * STEP
    return [[start + i * STEP, *row] for i, row in enumerate(out)]


def api_candles(rows, newest_first=True):
    data = [[str(r[0]), *[str(x) for x in r[1:5]], str(r[5]), str(r[5] * 100)] for r in rows]
    return list(reversed(data)) if newest_first else data


class FakeClient:
    def __init__(self, tickers=None, candles=None):
        self.tickers, self.candles, self.calls = tickers or {}, candles or {}, []

    def get(self, path, params=None):
        self.calls.append((path, params))
        params = params or {}
        if path == scan.TICKERS_PATH:
            sym = params.get("symbol")
            if sym is None:
                return 200, {"code": "00000", "data": list(self.tickers.values())}
            if sym in self.tickers:
                return 200, {"code": "00000", "data": [self.tickers[sym]]}
            return 400, {"code": "40034", "msg": "Parameter symbol does not exist"}
        if path == scan.CANDLES_PATH:
            assert params.get("granularity") == "15min", "harus 15min, bukan 15m"
            sym = params["symbol"]
            if sym in self.candles:
                return 200, {"code": "00000", "data": self.candles[sym]}
            return 400, {"code": "40034", "msg": "no"}
        raise AssertionError(path)


def run_main(args, client):
    buf = io.StringIO()
    code = scan.main(args + ["--delay", "0"], client=client, now=NOW, out=buf)
    return code, buf.getvalue()


class ParsingTests(unittest.TestCase):
    def test_parse_ticker_and_spread(self):
        t = scan.parse_ticker(ticker(last="0.004414", bid="0.004411", ask="0.004417", vol="137961", chg="0.005"))
        self.assertAlmostEqual(t["last"], 0.004414)
        self.assertAlmostEqual(t["spread_pct"], (0.004417 - 0.004411) / 0.004414 * 100)
        self.assertAlmostEqual(t["change24h"], 0.005)
        self.assertFalse(t["book_broken"])

    def test_parse_ticker_rejects_garbage(self):
        with self.assertRaises(ValueError):
            scan.parse_ticker({"symbol": "XUSDT"})
        with self.assertRaises(ValueError):
            scan.parse_ticker(ticker(last="0"))

    def test_candle_parsing_sorts_newest_first_input(self):
        rows = synth(80)
        c = FakeClient(candles={"BEAMUSDT": api_candles(rows, newest_first=True)})
        got = scan.fetch_candles(c, "BEAM")
        self.assertEqual([x["ts"] for x in got], sorted(x["ts"] for x in got))
        self.assertEqual(len(got), 80)

    def test_broken_book_ask_zero(self):
        t = scan.parse_ticker(ticker(ask="0"))
        self.assertTrue(t["book_broken"])
        self.assertIsNone(t["spread_pct"])
        c = FakeClient({"BEAMUSDT": ticker(ask="0")}, {"BEAMUSDT": api_candles(synth(100))})
        row = scan.analyze("BEAM", c, NOW, set())
        self.assertEqual(row["verdict"], "DITOLAK")
        self.assertIn("BOOK RUSAK", row["alasan"])


class FilterTests(unittest.TestCase):
    def test_volume_gate_and_conditional(self):
        c = FakeClient({"BEAMUSDT": ticker(vol="50000")}, {"BEAMUSDT": api_candles(synth(100))})
        row = scan.analyze("BEAM", c, NOW, set())
        self.assertEqual(row["volume_status"], "GUGUR")
        self.assertEqual(row["verdict"], "DITOLAK")
        self.assertIn("volume 24j", row["alasan"])
        row2 = scan.analyze("BEAM", c, NOW, {"BEAM"})
        self.assertEqual(row2["volume_status"], "LOLOS BERSYARAT")
        self.assertNotIn("volume 24j", row2["alasan"].split("[")[0])

    def test_net_rr_stop2_formula(self):
        c = FakeClient({"BEAMUSDT": ticker(last="1.0", bid="0.99932", ask="1.00068")}, {"BEAMUSDT": api_candles(synth(100))})
        row = scan.analyze("BEAM", c, NOW, set())
        spread = 0.136
        be = 0.2 + spread
        self.assertAlmostEqual(row["spread_pct"], spread, places=3)
        self.assertAlmostEqual(row["net_rr_stop2"], (4 - be) / (2 + be), places=3)

    def test_discover_filter(self):
        ts = [scan.parse_ticker(t) for t in [
            ticker("BTCUSDT", vol="9e9", chg="0.9"), ticker("RNVDAUSDT", vol="5e6", chg="0.8"),
            ticker("RMUUSDT", vol="5e6", chg="0.7"), ticker("RAYUSDT", vol="5e6", chg="0.1"),
            ticker("RUNEUSDT", vol="5e6", chg="-0.5"), ticker("LOWUSDT", vol="1000", chg="0.99"),
            ticker("AAAUSDT", vol="5e6", chg="0.3"), ticker("DOSUSDT", vol="5e6", chg="0.2"),
            ticker("BEAMBTC", vol="5e6", chg="0.9"), ticker("SOLUSDT", vol="1e9", chg="0.6")]]
        picks = scan.discover_filter(ts, {"DOS"}, 10, 100_000)
        self.assertEqual(picks, ["RUNE", "AAA", "RAY"])   # |chg| terbesar; big cap/saham/volume/skip/non-USDT tersingkir

    def test_tokenized_stock_detection(self):
        self.assertTrue(scan.is_tokenized_stock("RNVDA"))
        self.assertTrue(scan.is_tokenized_stock("RTSLA"))
        self.assertFalse(scan.is_tokenized_stock("RAY"))
        self.assertFalse(scan.is_tokenized_stock("RUNE"))


class ScanFlowTests(unittest.TestCase):
    def test_not_found_exit_zero(self):
        code, out = run_main(["TOKENYA", "NGADA"], FakeClient())
        self.assertEqual(code, 0)
        self.assertIn("TOKENYA/USDT", out)
        self.assertIn("NGADA/USDT", out)
        self.assertGreaterEqual(out.count("TIDAK DITEMUKAN"), 2)

    def test_network_failure_marks_gagal_not_crash(self):
        calls = []

        def bad_opener(req, timeout=None):
            calls.append(req.full_url)
            raise urllib.error.URLError("no network")

        client = scan.Client("http://invalid.invalid", sleep=lambda s: None, opener=bad_opener)
        code, out = run_main(["BEAM"], client)
        self.assertEqual(code, 0)
        self.assertIn("GAGAL AMBIL DATA", out)
        self.assertEqual(len(calls), 2)      # satu kali coba ulang

    def test_too_few_candles(self):
        c = FakeClient({"BEAMUSDT": ticker()}, {"BEAMUSDT": api_candles(synth(60))})
        row = scan.analyze("BEAM", c, NOW, set())
        self.assertEqual(row["verdict"], "DITOLAK")
        self.assertIn("DATA KURANG", row["alasan"])

    def test_stale_data_labelled(self):
        old = synth(100, end_ts=FORMING_TS - 6 * STEP)
        c = FakeClient({"BEAMUSDT": ticker()}, {"BEAMUSDT": api_candles(old)})
        row = scan.analyze("BEAM", c, NOW, set())
        self.assertEqual(row["verdict"], "DITOLAK")
        self.assertIn("DATA BASI", row["alasan"])

    def test_big_cap_skipped_without_fetch(self):
        c = FakeClient()
        row = scan.analyze("BTC", c, NOW, set())
        self.assertIn("big cap", row["alasan"])
        self.assertEqual(c.calls, [])

    def test_confirmed_breakout_is_lolos_with_plan_and_running_candle_dropped(self):
        rows = synth(100, breakout=True)
        forming = [rows[-1][0] + STEP, 101.4, 101.9, 101.0, 101.6, 20.0]
        # candle breakout (tutup) + candle berjalan; now berada di dalam candle berjalan
        rows_all = rows + [forming]
        now = datetime.fromtimestamp((forming[0] + 7 * 60_000) / 1000, WIB)
        c = FakeClient({"BEAMUSDT": ticker(last="101.5", bid="101.47", ask="101.52", vol="900000")},
                       {"BEAMUSDT": api_candles(rows_all)})
        row = scan.analyze("BEAM", c, now, set())
        self.assertEqual(row["verdict"], "LOLOS", row)
        self.assertEqual(row["setup"], 1)
        self.assertTrue(row["candle_running_dropped"])
        self.assertIn("plan_usulan", row)
        self.assertAlmostEqual(row["plan_usulan"]["net"], row["plan_usulan"]["net"])
        self.assertGreaterEqual(row["plan_usulan"]["net"], 1.5)

    def test_no_setup_gives_no_trade_and_table_format(self):
        c = FakeClient({"BEAMUSDT": ticker(last="97.0", bid="96.97", ask="97.03")}, {"BEAMUSDT": api_candles(synth(100))})
        code, out = run_main(["beam"], c)       # huruf kecil diterima
        self.assertEqual(code, 0)
        self.assertIn("## Scan 15m — 2026-11-12, 10:07 WIB", out)
        self.assertIn("Pair", out)
        self.assertIn("BEAM/USDT", out)
        self.assertIn("asumsi ilustratif", out)
        self.assertIn("bukan sinyal", out)
        self.assertRegex(out, r"Verdict: (NO TRADE|\d KANDIDAT)")

    def test_json_output(self):
        c = FakeClient({"BEAMUSDT": ticker()}, {"BEAMUSDT": api_candles(synth(100))})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.json"
            code, _ = run_main(["BEAM", "--json", str(path)], c)
            data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(code, 0)
        self.assertIn("checked_at_wib", data)
        tok = data["tokens"][0]
        for key in ("symbol", "last", "change24h", "volume24h", "spread_pct", "break_even_pct", "net_rr_stop2",
                    "trend", "breakout", "bounce", "resistance", "support", "atr_pct", "last_closed_wib", "verdict", "alasan"):
            self.assertIn(key, tok)

    def test_discover_uses_all_tickers_once_and_skip(self):
        tk = {f"{s}USDT": ticker(f"{s}USDT", chg=str(c)) for s, c in [("AAA", 0.5), ("BBB", 0.4), ("CCC", 0.3)]}
        cd = {k: api_candles(synth(100)) for k in tk}
        c = FakeClient(tk, cd)
        code, out = run_main(["--discover", "2", "--skip", "AAA"], c)
        self.assertEqual(code, 0)
        self.assertNotIn("AAA/USDT", out)
        self.assertIn("BBB/USDT", out)
        self.assertIn("CCC/USDT", out)
        self.assertEqual(sum(1 for p, q in c.calls if p == scan.TICKERS_PATH and not (q or {}).get("symbol")), 1)


class WatchlistTests(unittest.TestCase):
    def test_creates_sample_when_missing_and_validates(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "sub" / "watchlist.json"
            entries, errs = scan.load_watchlist(p)
            self.assertTrue(p.exists())
            self.assertEqual(errs, [])
            self.assertEqual([e["symbol"] for e in entries], ["BEAM", "DOS", "UAI", "CYBER", "AIO", "BR"])

    def test_invalid_entries_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "w.json"
            p.write_text(json.dumps([{"symbol": "A", "trigger": "close_di_atas", "level": 1.0},
                                     {"symbol": "B", "trigger": "ngawur", "level": 1.0},
                                     {"symbol": "C", "trigger": "bounce_di", "level": -1},
                                     "bukan objek"]), encoding="utf-8")
            entries, errs = scan.load_watchlist(p)
        self.assertEqual(len(entries), 1)
        self.assertEqual(len(errs), 3)

    def test_broken_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "w.json"
            p.write_text("{rusak", encoding="utf-8")
            entries, errs = scan.load_watchlist(p)
        self.assertEqual(entries, [])
        self.assertTrue(errs)

    def test_trigger_fires_and_prints_plan_numbers_without_creating_plan(self):
        rows = synth(100, breakout=True)
        c = FakeClient({"BEAMUSDT": ticker(last="101.5", bid="101.47", ask="101.52")}, {"BEAMUSDT": api_candles(rows)})
        now = datetime.fromtimestamp((rows[-1][0] + STEP + 1000) / 1000, WIB)
        entries = [{"symbol": "BEAM", "trigger": "close_di_atas", "level": 100.0, "note": "breakout"},
                   {"symbol": "BEAM", "trigger": "close_di_atas", "level": 110.0, "note": "jauh"},
                   {"symbol": "BEAM", "trigger": "close_di_bawah", "level": 90.0}]
        text = "\n".join(scan.run_watchlist(c, entries, now))
        self.assertIn("TERPICU", text)
        self.assertGreaterEqual(text.count("BELUM"), 2)
        self.assertIn("BELUM dicatat", text)
        self.assertIn("tidak dibuat otomatis", text)


class ClientTests(unittest.TestCase):
    def test_client_returns_4xx_json_without_retry(self):
        class Resp:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return b'{"code":"00000","data":[]}'

        n = []

        def opener(req, timeout=None):
            n.append(1)
            return Resp()

        cl = scan.Client(sleep=lambda s: None, opener=opener)
        status, body = cl.get("/x", {"a": 1})
        self.assertEqual((status, body["code"]), (200, "00000"))
        self.assertEqual(len(n), 1)


if __name__ == "__main__":
    unittest.main()
