import contextlib
import io
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trade  # noqa: E402

TRIGGER_UAI = ("Bounce dari low $0,03928; candle 03:15 tutup $0,04069, DI BAWAH level konfirmasi "
               "$0,0408; bounce BELUM terkonfirmasi")


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = trade.main(args)
    return code, out.getvalue(), err.getvalue()


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.j = os.path.join(self.dir.name, "trade-journal.md")

    def tearDown(self):
        self.dir.cleanup()

    def plan(self, stop="0.0399", now="2026-11-11 03:40", pair="UAI", entry="0.04072",
             setup="2", expiry="2026-11-11 05:32 WIB", trigger=TRIGGER_UAI, extra=()):
        return run(["plan", "--journal", self.j, "--now", now, "--pair", pair, "--entry", entry,
                    "--stop", stop, "--setup", setup, "--trigger", trigger, "--venue", "bursa spot",
                    "--expiry", expiry, "--spread", "0.10", *extra])

    def text(self):
        with open(self.j, encoding="utf-8") as fh:
            return fh.read()


class TestFormula(unittest.TestCase):
    def test_target_formula(self):
        c = trade.calc(0.04072, 0.0399)
        self.assertAlmostEqual(c["target"], 0.04236, places=8)
        self.assertAlmostEqual(c["target_pct"], 4.0275, places=3)

    def test_net_rr(self):
        c = trade.calc(0.04072, 0.0399, 0.10)
        self.assertAlmostEqual(c["biaya_pct"], 0.30, places=9)
        self.assertAlmostEqual(c["net_rr"], 1.61, places=2)

    def test_contoh_uji_1(self):
        c = trade.calc(0.04072, 0.0399, 0.10)
        self.assertAlmostEqual(c["jarak_stop_pct"], 2.01, places=2)
        self.assertAlmostEqual(c["risiko_usdt"], 0.89, places=2)
        self.assertAlmostEqual(c["ukuran"], 1080.55, delta=0.1)
        r = trade.calc_close(0.04072, 0.0399, 0.0414)
        self.assertAlmostEqual(r["pnl_kotor"], 0.73, places=2)
        self.assertAlmostEqual(r["hasil_r"], 0.83, places=2)

    def test_contoh_uji_2_kasus_uai(self):
        c = trade.calc(0.04072, 0.0394, 0.10)
        self.assertAlmostEqual(c["target"], 0.04336, places=8)
        self.assertNotAlmostEqual(c["target"], 0.0418, places=4)
        self.assertAlmostEqual(c["target_pct"], 6.48, places=2)
        self.assertAlmostEqual(c["net_rr"], 1.75, places=2)
        self.assertAlmostEqual(c["risiko_usdt"], 1.43, places=2)

    def test_stop_di_atas_entry_ditolak(self):
        with self.assertRaises(trade.ToolError):
            trade.calc(0.04, 0.05)

    def test_format_indonesia(self):
        self.assertEqual(trade.idn(1080.55, 0), "1.081")
        self.assertEqual(trade.price(0.04236), "0,04236")
        self.assertEqual(trade.parse_price("$0,04072 (market, sudah masuk)"), 0.04072)


class TestPlan(Base):
    def test_id_otomatis(self):
        code, out, _ = self.plan()
        self.assertEqual(code, 0)
        self.assertIn("UAI-20261111-01", out)
        self.plan()
        self.plan(pair="DOS")
        t = self.text()
        self.assertIn("UAI-20261111-02", t)
        self.assertIn("DOS-20261111-01", t)

    def test_setup_di_luar_1_3_ditolak_file_tidak_berubah(self):
        self.plan()
        before = self.text()
        code, _, err = self.plan(setup="4")
        self.assertEqual(code, 2)
        self.assertIn("setup harus 1, 2, atau 3", err)
        self.assertEqual(self.text(), before)

    def test_baris_14_kolom_dan_target_benar(self):
        self.plan(stop="0.0394")
        row = [ln for ln in self.text().split("\n") if ln.startswith("| UAI-")][0]
        cells = [c.strip() for c in row.strip("|").split("|")]
        self.assertEqual(len(cells), 14)
        self.assertIn("$0,04336 (+6,48%", cells[8])
        self.assertEqual(cells[13], "RENCANA")

    def test_pemicu_belum_terkonfirmasi_memberi_peringatan_tapi_tetap_dicatat(self):
        code, out, _ = self.plan()
        self.assertEqual(code, 0)
        self.assertIn("⚠️ Pemicu belum terkonfirmasi", out)
        self.assertNotIn("pelanggaran sadar", self.text())
        self.plan(extra=["--lanjut"])
        self.assertIn("pelanggaran sadar", self.text())

    def test_expiry_lebih_awal_dari_tutup_candle_ditolak(self):
        trig = "Breakout, candle 17:15 tutup di atas $0,0450"
        code, _, err = self.plan(now="2026-11-11 17:10", trigger=trig, expiry="2026-11-11 17:30 WIB")
        self.assertEqual(code, 2)
        self.assertIn("tidak mencakup", err)
        self.assertFalse(os.path.exists(self.j))
        code, _, _ = self.plan(now="2026-11-11 17:10", trigger=trig, expiry="2026-11-11 17:45 WIB")
        self.assertEqual(code, 0)

    def test_backup_dibuat_saat_menulis_jurnal_yang_sudah_ada(self):
        self.plan()
        self.plan()
        self.assertTrue(os.path.exists(self.j + ".bak"))


class TestCloseStatus(Base):
    def test_close_id_tidak_ada_file_tidak_berubah(self):
        self.plan()
        before = self.text()
        code, _, err = run(["close", "--journal", self.j, "--id", "NGADA-20261111-01", "--exit", "1"])
        self.assertEqual(code, 2)
        self.assertIn("tidak ada di jurnal", err)
        self.assertEqual(self.text(), before)

    def test_close_contoh_uji_1_lalu_status(self):
        self.plan()
        code, out, _ = run(["close", "--journal", self.j, "--now", "2026-11-11 03:59", "--id",
                            "UAI-20261111-01", "--exit", "0.0414", "--alasan", "volume mengering"])
        self.assertEqual(code, 0)
        self.assertIn("+$0,73", out)
        self.assertIn("+0,83R", out)
        t = self.text()
        self.assertIn("DITUTUP", t)
        self.assertIn("**+$0,73 (+1,67%)**", t)
        self.assertIn("volume mengering", t)
        code, out, _ = run(["status", "--journal", self.j, "--now", "2026-11-11 04:00"])
        self.assertEqual(code, 0)
        self.assertIn("Sisa budget rugi : $2,20", out)
        self.assertIn("slot tersisa 1", out)

    def test_rugi_mengurangi_budget_dan_batas_tercapai(self):
        self.plan(stop="0.0394")
        run(["close", "--journal", self.j, "--now", "2026-11-11 04:10", "--id", "UAI-20261111-01",
             "--exit", "0.0394", "--fee", "0.09"])
        _, out, _ = run(["status", "--journal", self.j, "--now", "2026-11-11 04:11"])
        self.assertIn("Sisa budget rugi : $0,77", out)
        self.assertIn("| Tidak |", self.text().split("## Sesi")[1])

    def test_tidak_bisa_tutup_dua_kali(self):
        self.plan()
        run(["close", "--journal", self.j, "--now", "2026-11-11 04:00", "--id", "UAI-20261111-01", "--exit", "0.0414"])
        code, _, err = run(["close", "--journal", self.j, "--id", "UAI-20261111-01", "--exit", "0.0414"])
        self.assertEqual(code, 2)
        self.assertIn("sudah berstatus", err)

    def test_batal(self):
        self.plan()
        code, out, _ = run(["close", "--journal", self.j, "--now", "2026-11-11 04:00", "--id",
                            "UAI-20261111-01", "--batal", "--alasan", "tidak terpicu"])
        self.assertEqual(code, 0)
        self.assertIn("BATAL", self.text())


if __name__ == "__main__":
    unittest.main()
