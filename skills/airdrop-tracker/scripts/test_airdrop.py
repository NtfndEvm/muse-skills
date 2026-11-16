"""Tes airdrop.py: add/status, log, deadlines (3 penanda), roi terpisah,
penolakan pola kunci/seed, path state lewat env var, export-xlsx.

Jalankan dari folder scripts/:  python3 -m unittest test_airdrop -v
atau:  python3 -m pytest -q test_airdrop.py
"""

import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import airdrop  # noqa: E402

HEX64 = "a" * 64
HEX64_0X = "0x" + "b" * 64
MNEMONIC_12 = "abandon ability able about above absent absorb abstract absurd abuse access accident"
MNEMONIC_24 = " ".join(["abandon"] * 24)


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = airdrop.main(args)
    return code, out.getvalue(), err.getvalue()


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.state = os.path.join(self.dir.name, "airdrop-state.json")

    def tearDown(self):
        self.dir.cleanup()

    def add(self, name="Proyek X", **kw):
        args = ["add", "--state", self.state, "--name", name, "--now", "2026-11-17"]
        for key, val in kw.items():
            args += [f"--{key.replace('_', '-')}", str(val)]
        code, out, err = run(args)
        self.assertEqual(code, 0, f"add gagal: {err or out}")
        return out

    def load(self):
        with open(self.state, encoding="utf-8") as fh:
            return json.load(fh)


class TestAddStatus(Base):
    def test_add_dan_status(self):
        self.add(category="Testnet", chain="Ethereum", wallet="Burner-A",
                 next_task="klaim faucet", deadline="2026-12-01", cost="1.2",
                 locked="50", est_reward="100")
        data = self.load()
        self.assertEqual(len(data["projects"]), 1)
        p = data["projects"][0]
        self.assertEqual(p["id"], "P001")
        self.assertEqual(p["name"], "Proyek X")
        self.assertEqual(p["status"], "🔍 Riset")
        self.assertEqual(p["wallet"], "Burner-A")  # label saja, bukan kunci
        self.assertEqual(p["cost"], 1.2)
        self.assertEqual(p["locked"], 50.0)
        code, out, err = run(["status", "--state", self.state, "--now", "2026-11-17"])
        self.assertEqual(code, 0, err)
        self.assertIn("Proyek X", out)
        self.assertIn("$1,20", out)          # total biaya
        self.assertIn("$50,00", out)         # modal terkunci
        self.assertIn("$100,00", out)        # estimasi

    def test_add_duplikat_ditolak(self):
        self.add()
        code, out, err = run(["add", "--state", self.state, "--name", "Proyek X"])
        self.assertNotEqual(code, 0)
        self.assertIn("sudah ada", err)
        self.assertEqual(len(self.load()["projects"]), 1)

    def test_kategori_tidak_dikenal_ditolak(self):
        code, out, err = run(["add", "--state", self.state, "--name", "Y",
                              "--category", "BukanKategori"])
        self.assertNotEqual(code, 0)
        self.assertIn("category", err)


class TestLog(Base):
    def test_log_menambah_biaya_proyek(self):
        self.add(cost="1.2")
        code, out, err = run(["log", "--state", self.state, "--project", "P001",
                              "--action", "swap", "--cost", "0.8",
                              "--tx", "0x" + "c" * 64, "--now", "2026-11-17"])
        self.assertEqual(code, 0, err)
        data = self.load()
        self.assertEqual(len(data["log"]), 1)
        self.assertEqual(data["log"][0]["action"], "swap")
        self.assertEqual(data["log"][0]["tx"], "0x" + "c" * 64)  # hash tx BOLEH (publik)
        self.assertEqual(data["projects"][0]["cost"], 2.0)        # 1,2 + 0,8 dihitung ulang
        self.assertIn("Total biaya proyek sekarang $2,00", out)

    def test_log_proyek_tidak_ada_ditolak(self):
        code, out, err = run(["log", "--state", self.state, "--project", "P999",
                              "--action", "swap"])
        self.assertNotEqual(code, 0)
        self.assertIn("tidak ada", err)

    def test_log_klaim_mencatat_claim_dan_reward(self):
        self.add()
        code, out, err = run(["log", "--state", self.state, "--project", "P001",
                              "--action", "klaim", "--token", "XYZ", "--amount", "10",
                              "--price", "2.5", "--now", "2026-11-17"])
        self.assertEqual(code, 0, err)
        data = self.load()
        self.assertEqual(len(data["claims"]), 1)
        self.assertEqual(data["claims"][0]["token"], "XYZ")
        self.assertEqual(data["projects"][0]["real_reward"], 25.0)  # 10 x $2,5


class TestDeadlines(Base):
    def test_ketiga_penanda(self):
        # "hari ini" 2026-11-17: 2 hari -> 🔴, 5 hari -> 🟠, 10 hari -> 🟡, 30 hari -> tanpa penanda
        self.add("Dekat", deadline="2026-11-19")
        self.add("Sedang", deadline="2026-11-22")
        self.add("Jauh", deadline="2026-11-27")
        self.add("SangatJauh", deadline="2026-12-17")
        code, out, err = run(["deadlines", "--state", self.state, "--now", "2026-11-17"])
        self.assertEqual(code, 0, err)
        lines = out.splitlines()
        self.assertTrue(any("🔴" in ln and "Dekat" in ln for ln in lines))
        self.assertTrue(any("🟠" in ln and "Sedang" in ln for ln in lines))
        self.assertTrue(any("🟡" in ln and "Jauh" in ln for ln in lines))
        self.assertTrue(any("SangatJauh" in ln and "🔴" not in ln and "🟠" not in ln
                            and "🟡" not in ln for ln in lines))
        # terurut terdekat dulu (hanya baris proyek, bukan header)
        order = [ln for ln in lines if "· P0" in ln]
        self.assertEqual(len(order), 4)
        dates = [re.search(r"(\d{4}-\d{2}-\d{2})", ln).group(1) for ln in order]
        self.assertEqual(dates, ["2026-11-19", "2026-11-22", "2026-11-27", "2026-12-17"])

    def test_deadline_lewat_juga_merah(self):
        self.add("Telat", deadline="2026-11-10")
        code, out, err = run(["deadlines", "--state", self.state, "--now", "2026-11-17"])
        self.assertEqual(code, 0, err)
        self.assertTrue(any("🔴" in ln and "lewat 7 hari" in ln for ln in out.splitlines()))


class TestRoi(Base):
    def test_realisasi_dan_estimasi_terpisah(self):
        # biaya $10, realisasi $25, estimasi $100 -> ROI real +150%, estimasi +900%
        self.add(cost="10", real_reward="25", est_reward="100")
        code, out, err = run(["roi", "--state", self.state])
        self.assertEqual(code, 0, err)
        self.assertIn("realisasi: +150,0%", out)
        self.assertIn("estimasi : +900,0% (estimasi)", out)
        self.assertIn("ROI realisasi: +150,0%", out)  # baris TOTAL
        self.assertIn("ROI estimasi: +900,0% (estimasi)", out)

    def test_belum_ada_hasil_bukan_rugi(self):
        # biaya $10, belum ada reward realisasi -> "belum ada hasil", bukan -100%
        # (estimasi -100% tetap tampil karena estimasi memang 0 — itu rumus, bukan kesimpulan rugi)
        self.add(cost="10")
        code, out, err = run(["roi", "--state", self.state])
        self.assertEqual(code, 0, err)
        self.assertIn("realisasi: belum ada hasil", out)
        self.assertIn("ROI realisasi: belum ada hasil", out)

    def test_tanpa_biaya_roi_tidak_dihitung(self):
        self.add()
        code, out, err = run(["roi", "--state", self.state])
        self.assertEqual(code, 0, err)
        self.assertIn("belum ada biaya", out)


class TestSecretRejection(Base):
    def test_heks_64_ditolak(self):
        for value in (HEX64, HEX64_0X):
            code, out, err = run(["add", "--state", self.state, "--name", "Y",
                                  "--wallet", value])
            self.assertNotEqual(code, 0, f"heks 64 lolos: {value[:20]}...")
            self.assertIn("d", err.lower())
        self.assertFalse(os.path.exists(self.state))  # state tidak dibuat

    def test_mnemonic_ditolak(self):
        for words in (MNEMONIC_12, MNEMONIC_24):
            code, out, err = run(["add", "--state", self.state, "--name", "Y",
                                  "--notes", words])
            self.assertNotEqual(code, 0)
            self.assertIn("mnemonic", err.lower())
        self.assertFalse(os.path.exists(self.state))

    def test_frasa_terlarang_ditolak(self):
        for phrase in ("my mnemonic is secret", "seed phrase saya", "ini private key"):
            code, out, err = run(["add", "--state", self.state, "--name", "Y",
                                  "--notes", phrase])
            self.assertNotEqual(code, 0, phrase)
            self.assertIn("terlarang", err)
        self.assertFalse(os.path.exists(self.state))

    def test_log_juga_menolak(self):
        self.add()
        code, out, err = run(["log", "--state", self.state, "--project", "P001",
                              "--action", "x", "--note", MNEMONIC_12])
        self.assertNotEqual(code, 0)
        self.assertEqual(self.load()["log"], [])

    def test_alamat_publik_diterima(self):
        # alamat EVM 0x + 40 heks adalah data publik, bukan kunci
        self.add(wallet="0x" + "d" * 40)
        self.assertEqual(self.load()["projects"][0]["wallet"], "0x" + "d" * 40)


class TestEnvVarStatePath(unittest.TestCase):
    def test_airdrop_state_env_var(self):
        """Path state lewat env var AIRDROP_STATE (subproses, seperti pemakaian nyata)."""
        with tempfile.TemporaryDirectory() as d:
            env_state = os.path.join(d, "custom-state.json")
            env = dict(os.environ, AIRDROP_STATE=env_state)
            script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "airdrop.py")
            r = subprocess.run([sys.executable, script, "add", "--name", "EnvTest",
                                "--now", "2026-11-17"],
                               env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(os.path.exists(env_state), "state tidak dibuat di path env var")
            with open(env_state, encoding="utf-8") as fh:
                data = json.load(fh)
            self.assertEqual(data["projects"][0]["name"], "EnvTest")
            # default ~/workspace TIDAK dipakai
            self.assertFalse(os.path.exists(
                os.path.expanduser("~/workspace/airdrop-state.json")))


class TestExportXlsx(Base):
    def test_export_xlsx_atau_csv(self):
        self.add("P1", deadline="2026-12-01", cost="2")
        run(["log", "--state", self.state, "--project", "P001", "--action", "swap",
             "--cost", "0.5", "--now", "2026-11-17"])
        out_path = os.path.join(self.dir.name, "tracker.xlsx")
        code, out, err = run(["export-xlsx", "--state", self.state, "--out", out_path])
        self.assertEqual(code, 0, err)
        try:
            import openpyxl
        except ImportError:
            openpyxl = None
        if openpyxl is not None:
            self.assertTrue(os.path.exists(out_path), "xlsx tidak dibuat")
            wb = openpyxl.load_workbook(out_path)
            try:
                self.assertEqual(wb.sheetnames,
                                 ["Proyek", "Log Aktivitas", "Klaim & Hasil", "Deadline"])
                ws = wb["Proyek"]
                self.assertEqual(ws.cell(row=2, column=2).value, "P1")
                self.assertEqual(ws.cell(row=2, column=13).value, 2.5)
            finally:
                wb.close()
        else:
            self.assertIn("openpyxl tidak tersedia", out)
            self.assertTrue(os.path.exists(
                os.path.join(self.dir.name, "tracker-proyek.csv")))


if __name__ == "__main__":
    unittest.main()
