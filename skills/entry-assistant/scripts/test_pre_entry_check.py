"""Tes sintetis pre_entry_check.py. Jalankan: python -m unittest test_pre_entry_check (dari folder scripts)."""
import contextlib
import io
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pre_entry_check as pec  # noqa: E402


def codes(res):
    return {c["code"] for c in res["violations"]}


class TestRumus(unittest.TestCase):
    def test_target_dihitung_ulang_dari_entry_aktual(self):
        # entry 1,00 stop 0,975 -> jarak 0,025 -> target-aturan 1,05 (+5%)
        r = pec.check(1.0, 0.975, target=1.05, confirmed=True, volume_ratio=2.0,
                      resistance=1.10, vwap=0.99, atr=0.01)
        self.assertAlmostEqual(r["target_rule"], 1.05)
        self.assertAlmostEqual(r["target_rule_pct"], 5.0)
        self.assertAlmostEqual(r["jarak_stop_pct"], 2.5)
        # R:R bersih = (5 - 0,3) / (2,5 + 0,3) = 1,68
        self.assertAlmostEqual(r["net_rr_rule"], (5 - 0.3) / (2.5 + 0.3))

    def test_target_lama_tidak_dibawa(self):
        # entry berubah, target-aturan ikut berubah (evaluasi-diri 8)
        self.assertAlmostEqual(pec.check(1.0, 0.98)["target_rule"], 1.04)
        self.assertAlmostEqual(pec.check(1.02, 0.98)["target_rule"], 1.10)

    def test_target_kosong_dipakai_target_aturan_dan_ditandai(self):
        r = pec.check(1.0, 0.975)
        self.assertFalse(r["target_diberi_user"])
        self.assertAlmostEqual(r["target"], r["target_rule"])

    def test_input_tidak_valid(self):
        for kw in ({"entry": 0, "stop": 0.9}, {"entry": 1.0, "stop": 1.0},
                   {"entry": 1.0, "stop": 1.01}, {"entry": 1.0, "stop": 0.9, "target": 0}):
            with self.assertRaises(pec.CheckError):
                pec.check(**kw)


class TestKasusBersih(unittest.TestCase):
    def test_semua_aturan_terpenuhi_nol_pelanggaran(self):
        r = pec.check(1.0, 0.975, target=1.05, confirmed=True, confirmation="breakout terkonfirmasi",
                      volume_ratio=2.0, resistance=1.10, vwap=0.99, atr=0.01)
        self.assertEqual(r["n_pelanggaran"], 0)
        self.assertEqual(r["n_tidak_ada_data"], 0)
        self.assertEqual(len(r["checks"]), 8)
        self.assertTrue(all(c["status"] == "OK" for c in r["checks"]))

    def test_teks_memuat_rumus_dan_ringkasan_nol(self):
        r = pec.check(1.0, 0.975, target=1.05, confirmed=True, volume_ratio=2.0,
                      resistance=1.10, vwap=0.99, atr=0.01)
        out = pec.to_text(r)
        self.assertIn("target = entry + 2 x jarak stop", out)
        self.assertIn("0 pelanggaran dari 8 cek", out)
        self.assertIn("hanya menandai", out)


class TestPolaEntrySebelumKonfirmasi(unittest.TestCase):
    """Pola evaluasi-diri 17/14/21: tanpa konfirmasi, volume normal, ruang
    sempit, extension VWAP, target di bawah 5%, R:R di bawah 1,5."""

    def setUp(self):
        self.r = pec.check(1.0, 0.99, target=1.03, confirmed=False,
                           volume_ratio=1.0, resistance=1.02, vwap=0.95, atr=0.01)

    def test_pelanggaran_yang_diharapkan_muncul(self):
        self.assertEqual(codes(self.r),
                         {"KONFIRMASI", "VOLUME_SPIKE", "RUANG_RESISTANCE",
                          "EXTENSION_VWAP", "TARGET_PROFIT", "RR_BERSIH"})

    def test_budget_tidak_ikut_terlanggar_di_kasus_ini(self):
        # risiko stop aktual 0,44 < 2,20; risiko stop 1x ATR 0,44 < 2,20
        self.assertNotIn("BUDGET_STOP", codes(self.r))
        self.assertNotIn("BUDGET_STOP_ATR", codes(self.r))
        self.assertAlmostEqual(self.r["risiko_usdt"], 0.44)
        self.assertAlmostEqual(self.r["risiko_atr_usdt"], 0.44)
        self.assertAlmostEqual(self.r["stop_jarak_atr"], 1.0)

    def test_teks_mencantumkan_semua_pelanggaran(self):
        out = pec.to_text(self.r)
        self.assertIn("6 pelanggaran dari 8 cek", out)
        for label in ("Konfirmasi", "Volume spike", "Ruang ke resistance",
                      "Extension dari VWAP", "Target vs target profit user", "R:R bersih"):
            self.assertIn(label, out)


class TestBudgetAtr(unittest.TestCase):
    def test_budget_tidak_cukup_untuk_stop_atr(self):
        # ATR 0,05 (5%): stop 1x ATR berisiko 2,20 = pas budget; ATR 0,06 -> 2,64 > 2,20
        r = pec.check(1.0, 0.99, target=1.03, confirmed=True, volume_ratio=2.0,
                      resistance=1.10, vwap=0.99, atr=0.06)
        self.assertIn("BUDGET_STOP_ATR", codes(r))
        self.assertAlmostEqual(r["risiko_atr_usdt"], 2.64)

    def test_budget_kecil_menjatuhkan_stop_aktual_juga(self):
        r = pec.check(1.0, 0.975, target=1.05, confirmed=True, volume_ratio=2.0,
                      resistance=1.10, vwap=0.99, atr=0.01, budget=0.50)
        self.assertIn("BUDGET_STOP", codes(r))       # risiko 1,10 > 0,50
        self.assertNotIn("BUDGET_STOP_ATR", codes(r))  # risiko ATR 0,44 <= 0,50


class TestDataTidakAda(unittest.TestCase):
    def test_tanpa_data_opsional_ditandai_bukan_diam_diam_lolos(self):
        r = pec.check(1.0, 0.975, target=1.05, confirmed=True)
        self.assertEqual(r["n_tidak_ada_data"], 4)  # volume, resistance, VWAP, budget-ATR
        self.assertEqual([c["code"] for c in r["checks"] if c["status"] == "TIDAK_ADA_DATA"],
                         ["VOLUME_SPIKE", "RUANG_RESISTANCE", "EXTENSION_VWAP", "BUDGET_STOP_ATR"])
        self.assertEqual(r["n_pelanggaran"], 0)


class TestCli(unittest.TestCase):
    def test_main_kasus_bersih_exit_0(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = pec.main(["--pair", "UAI", "--entry", "1.0", "--stop", "0.975",
                             "--target", "1.05", "--confirmed", "--volume-ratio", "2.0",
                             "--resistance", "1.10", "--vwap", "0.99", "--atr", "0.01"])
        self.assertEqual(code, 0)
        self.assertIn("0 pelanggaran dari 8 cek", out.getvalue())

    def test_main_dengan_pelanggaran_tetap_exit_0_bukan_veto(self):
        # Pelanggaran ditemukan, tapi exit code tetap 0: skrip hanya menandai.
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = pec.main(["--pair", "UAI", "--entry", "1.0", "--stop", "0.99",
                             "--target", "1.03", "--volume-ratio", "1.0",
                             "--resistance", "1.02", "--vwap", "0.95", "--atr", "0.01"])
        self.assertEqual(code, 0)
        self.assertIn("6 pelanggaran dari 8 cek", out.getvalue())

    def test_main_format_json(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = pec.main(["--entry", "1.0", "--stop", "0.975", "--target", "1.05",
                             "--confirmed", "--format", "json"])
        self.assertEqual(code, 0)
        data = json.loads(out.getvalue())
        self.assertEqual(data["n_pelanggaran"], 0)
        self.assertAlmostEqual(data["target_rule"], 1.05)

    def test_main_input_tidak_valid_exit_2(self):
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = pec.main(["--entry", "1.0", "--stop", "1.01"])
        self.assertEqual(code, 2)
        self.assertIn("stop harus di bawah entry", err.getvalue())


if __name__ == "__main__":
    unittest.main()
