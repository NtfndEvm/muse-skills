"""Jalankan: python -m unittest -v test_trade   (dari folder scripts). Hanya stdlib."""
import contextlib
import io
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trade  # noqa: E402

NOW = "2026-11-11 03:40"


def run(journal, *args, now=NOW):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = trade.main(["--journal", str(journal), "--now", now, *args])
    return code, out.getvalue(), err.getvalue()


def plan_args(entry="0.04072", stop="0.0399", **kw):
    a = ["plan", "--pair", kw.get("pair", "UAI"), "--entry", entry, "--stop", stop, "--setup", str(kw.get("setup", 2)),
         "--trigger", kw.get("trigger", "Bounce terkonfirmasi; candle 03:15 tutup di atas level"),
         "--expiry", kw.get("expiry", "2026-11-11 05:32 WIB"), "--spread", "0.10"]
    return a


class FormulaTests(unittest.TestCase):
    def test_target_is_entry_plus_two_times_stop_distance(self):
        p = trade.calc_plan(0.04072, 0.0399, 0.10)
        self.assertAlmostEqual(p["target"], 0.04072 + 2 * 0.00082, places=10)

    def test_example1_numbers_from_exact_formula(self):
        p = trade.calc_plan(0.04072, 0.0399, 0.10)
        self.assertAlmostEqual(p["jarak_stop_pct"], 2.01, places=2)
        self.assertAlmostEqual(p["biaya_pct"], 0.30, places=6)
        self.assertAlmostEqual(p["risiko_usdt"], 0.89, places=2)
        self.assertAlmostEqual(p["ukuran"], 1080.5, delta=1.0)
        # Rumus persis -> target 0,04236 (+4,03%) dan net R:R 1,61.
        # (Contoh di spek memakai target dibulatkan 0,0424 -> 1,65; lihat README, perlu keputusan user.)
        self.assertAlmostEqual(p["target_pct"], 4.0275, places=3)
        self.assertAlmostEqual(p["net_rr"], 1.611, places=3)

    def test_example1_close_pnl_and_r(self):
        c = trade.calc_close(0.04072, 0.0399, 0.0414)
        self.assertAlmostEqual(c["pnl_kotor"], 0.73, places=2)
        self.assertAlmostEqual(c["hasil_r"], 0.83, places=2)

    def test_example2_uai_miscalc_case(self):
        p = trade.calc_plan(0.04072, 0.0394, 0.10)
        self.assertAlmostEqual(p["target"], 0.04336, places=8)        # HARUS 0,04336, bukan 0,0418
        self.assertAlmostEqual(p["target_pct"], 6.48, places=2)
        self.assertAlmostEqual(p["net_rr"], 1.75, places=2)
        self.assertAlmostEqual(p["risiko_usdt"], 1.43, places=2)
        self.assertNotAlmostEqual(p["target"], 0.0418, places=4)

    def test_missing_spread_uses_labeled_placeholder(self):
        p = trade.calc_plan(1.0, 0.98)
        self.assertFalse(p["spread_known"])
        self.assertAlmostEqual(p["biaya_pct"], 0.30)

    def test_stop_above_entry_rejected(self):
        with self.assertRaises(trade.ToolError):
            trade.calc_plan(1.0, 1.1)

    def test_absurd_stop_rejected_unless_force(self):
        with self.assertRaises(trade.ToolError):
            trade.calc_plan(1.0, 0.5)
        self.assertIsNotNone(trade.calc_plan(1.0, 0.5, force=True))

    def test_net_rr_for_target_matches_calc_plan(self):
        p = trade.calc_plan(0.04072, 0.0394, 0.10)
        self.assertAlmostEqual(trade.net_rr_for_target(0.04072, 0.0394, p["target"], 0.10), p["net_rr"], places=9)

    def test_parse_id_number(self):
        self.assertAlmostEqual(trade.parse_id_number("0,04072"), 0.04072)
        self.assertAlmostEqual(trade.parse_id_number("1.080"), 1080.0)
        self.assertAlmostEqual(trade.parse_id_number("1.234,56"), 1234.56)


class JournalFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.j = self.tmp / "trade-journal.md"
        run(self.j, "init")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_auto_id_increments_per_day_and_symbol(self):
        run(self.j, *plan_args())
        run(self.j, *plan_args())
        run(self.j, *plan_args(pair="BEAM"))
        text = self.j.read_text(encoding="utf-8")
        self.assertIn("UAI-20261111-01", text)
        self.assertIn("UAI-20261111-02", text)
        self.assertIn("BEAM-20261111-01", text)

    def test_setup_outside_1_to_3_rejected_file_unchanged(self):
        before = self.j.read_text(encoding="utf-8")
        code, _, err = run(self.j, *plan_args(setup=4))
        self.assertEqual(code, 2)
        self.assertIn("1, 2, atau 3", err)
        self.assertEqual(before, self.j.read_text(encoding="utf-8"))

    def test_close_unknown_id_errors_file_unchanged(self):
        run(self.j, *plan_args())
        before = self.j.read_text(encoding="utf-8")
        code, _, err = run(self.j, "close", "--id", "NADA-20261111-01", "--exit", "1.0")
        self.assertEqual(code, 2)
        self.assertIn("tidak ditemukan", err)
        self.assertEqual(before, self.j.read_text(encoding="utf-8"))

    def test_expiry_before_trigger_candle_close_rejected_without_force(self):
        before = self.j.read_text(encoding="utf-8")
        a = plan_args(trigger="Menunggu candle 17:15 tutup di atas level", expiry="2026-11-11 17:30 WIB")
        code, _, err = run(self.j, *a, now="2026-11-11 17:00")
        self.assertEqual(code, 2)
        self.assertIn("expiry", err)
        self.assertEqual(before, self.j.read_text(encoding="utf-8"))
        code2, _, _ = run(self.j, *a, "--force", now="2026-11-11 17:00")
        self.assertEqual(code2, 0)

    def test_expiry_after_trigger_candle_close_ok(self):
        a = plan_args(trigger="Menunggu candle 17:15 tutup di atas level", expiry="2026-11-11 17:45 WIB")
        code, _, _ = run(self.j, *a, now="2026-11-11 17:00")
        self.assertEqual(code, 0)

    def test_warnings_recorded_not_vetoed_and_label_with_lanjut(self):
        a = plan_args(entry="1.0", stop="0.99", trigger="Bounce BELUM terkonfirmasi")  # net R:R rendah & pemicu belum
        code, out, _ = run(self.j, *a, "--lanjut")
        self.assertEqual(code, 0)
        text = self.j.read_text(encoding="utf-8")
        self.assertIn("pelanggaran sadar", text)
        self.assertIn("⚠️", out)

    def test_low_net_rr_warning_and_budget_warning(self):
        code, out, _ = run(self.j, "plan", "--pair", "ABC", "--entry", "1.0", "--stop", "0.9", "--setup", "1",
                           "--trigger", "Breakout terkonfirmasi", "--expiry", "2026-11-11 05:00 WIB", "--spread", "0.1")
        self.assertEqual(code, 0)
        self.assertIn("Risiko melebihi sisa budget", out)  # risiko 10% x 44 = $4,40 > $2,20

    def test_backup_created_before_writing(self):
        run(self.j, *plan_args())
        self.assertTrue(Path(str(self.j) + ".bak").exists())

    def test_full_flow_example1_and_status(self):
        run(self.j, *plan_args())
        code, out, _ = run(self.j, "close", "--id", "UAI-20261111-01", "--exit", "0.0414", "--alasan", "volume mengering",
                           now="2026-11-11 03:59")
        self.assertEqual(code, 0)
        self.assertIn("+$0,73", out)
        self.assertIn("+0,83R", out)
        text = self.j.read_text(encoding="utf-8")
        self.assertIn("| DITUTUP |", text)
        self.assertIn("## Sesi", text)
        self.assertIn("| Tidak |", text)
        code, out, _ = run(self.j, "status", now="2026-11-11 04:00")
        self.assertIn("Sisa budget rugi: $2,20", out)
        self.assertIn("slot tersisa: 1", out)

    def test_loss_reduces_budget_and_triggers_limit_flag(self):
        run(self.j, *plan_args())
        # exit jauh di bawah stop -> rugi besar
        run(self.j, "close", "--id", "UAI-20261111-01", "--exit", "0.0380", "--fee", "0.05", now="2026-11-11 04:10")
        text = self.j.read_text(encoding="utf-8")
        self.assertIn("| Ya |", text)           # rugi kotor >= $2,20
        _, out, _ = run(self.j, "status", now="2026-11-11 04:11")
        self.assertIn("Sisa budget rugi: $0,00", out)

    def test_cannot_close_twice(self):
        run(self.j, *plan_args())
        run(self.j, "close", "--id", "UAI-20261111-01", "--exit", "0.0414")
        code, _, err = run(self.j, "close", "--id", "UAI-20261111-01", "--exit", "0.0414")
        self.assertEqual(code, 2)
        self.assertIn("sudah berstatus", err)

    def test_batal_has_no_pnl(self):
        run(self.j, *plan_args())
        code, out, _ = run(self.j, "close", "--id", "UAI-20261111-01", "--batal", "--alasan", "tidak terpicu")
        self.assertEqual(code, 0)
        self.assertIn("BATAL", self.j.read_text(encoding="utf-8"))

    def test_other_rows_untouched(self):
        run(self.j, *plan_args(pair="BEAM"))
        run(self.j, *plan_args(pair="UAI"))
        lines_before = [l for l in self.j.read_text(encoding="utf-8").split("\n") if l.startswith("| BEAM-")]
        run(self.j, "close", "--id", "UAI-20261111-01", "--exit", "0.0414")
        lines_after = [l for l in self.j.read_text(encoding="utf-8").split("\n") if l.startswith("| BEAM-")]
        self.assertEqual(lines_before, lines_after)

    def test_legacy_bullet_without_meta_is_parsed(self):
        run(self.j, *plan_args())
        text = self.j.read_text(encoding="utf-8")
        text = text.replace("## Sesi", "- UAI-20261111-09: **DITUTUP — close manual, dilaporkan 2026-11-11 03:59 WIB.** "
                            "P&L kotor **-$1,50 (-3,41%)**.\n\n## Sesi")
        self.j.write_text(text, encoding="utf-8")
        _, out, _ = run(self.j, "status", now="2026-11-11 04:00")
        self.assertIn("Sisa budget rugi: $0,70", out)


if __name__ == "__main__":
    unittest.main()
