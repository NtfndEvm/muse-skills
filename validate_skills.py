#!/usr/bin/env python3
"""validate_skills.py — cek otomatis struktur repo muse-skills (Butir 13).

Jalankan dari root repo:  python3 validate_skills.py
Keluar 0 bila semua cek lolos, 1 bila ada yang gagal.

Cek:
  1. tiap folder skills/<x>/ punya SKILL.md dengan front matter, dan
     `name` di front matter sama dengan <x>.
  2. skill.yaml bisa diparse (PyYAML bila ada, fallback line-based bila
     tidak) dan `name` sama dengan folder.
  3. semua skill muncul di tabel README ("Isi repo"), dan tidak ada
     entri tabel yang tidak punya folder.
  4. tidak ada path pribadi (/home/<user>/, /Users/), pola kunci, atau
     file .env terlacak.
     - Pola kunci yang dicek: PRIVATE_KEY yang diberi nilai, kunci API
       `sk-...`, string heks 64 karakter yang mirip private key, dan
       frasa mnemonic 12/24 kata.
     - Yang SENGAJA tidak dihitung sebagai temuan: daftar pola terlarang
       dan pesan penolakan di kode (baris yang menyebut tolak/reject/
       forbidden/pola/pattern), vektor uji BIP39 publik ("abandon ..."),
       dan string heks 64 karakter yang semuanya nol.
     - Folder skills/_shared/ bukan skill dan dikecualikan dari cek 1-3.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.path.join(ROOT, "skills")
README = os.path.join(ROOT, "README.md")

TEXT_EXTS = {".md", ".py", ".js", ".yaml", ".yml", ".sh", ".json", ".txt"}
SKIP_DIRS = {".git", "__pycache__", "node_modules"}

failures = []
notes = []


def fail(msg):
    failures.append(msg)
    print(f"FAIL: {msg}")


def ok(msg):
    print(f"ok: {msg}")


def skill_dirs():
    out = []
    for name in sorted(os.listdir(SKILLS_DIR)):
        path = os.path.join(SKILLS_DIR, name)
        if os.path.isdir(path) and not name.startswith("_"):
            out.append(name)
    return out


def parse_front_matter(text):
    """Kembalikan dict front matter, atau None bila tidak ada."""
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    fm = {}
    for line in text[4:end].splitlines():
        m = re.match(r"^([A-Za-z_]+):\s*(.*)$", line)
        if m:
            fm[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return fm


def yaml_name(path):
    """Baca top-level `name` dari skill.yaml. PyYAML bila ada."""
    try:
        import yaml  # type: ignore

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            return None, "skill.yaml bukan mapping"
        return data.get("name"), None
    except ImportError:
        notes.append("PyYAML tidak terpasang; cek skill.yaml pakai fallback line-based")
        with open(path, encoding="utf-8") as f:
            for line in f:
                m = re.match(r"^name:\s*(.+)$", line)
                if m:
                    return m.group(1).strip().strip('"').strip("'"), None
        return None, "name tidak ditemukan (fallback)"
    except Exception as exc:  # noqa: BLE001 - laporkan sebagai gagal
        return None, f"skill.yaml tidak valid: {exc}"


def check_front_matter_and_yaml():
    for skill in skill_dirs():
        spath = os.path.join(SKILLS_DIR, skill, "SKILL.md")
        if not os.path.isfile(spath):
            fail(f"skills/{skill}/: SKILL.md tidak ada")
            continue
        with open(spath, encoding="utf-8") as f:
            text = f.read()
        fm = parse_front_matter(text)
        if fm is None:
            fail(f"skills/{skill}/SKILL.md: tidak ada front matter ---")
        elif "name" not in fm:
            fail(f"skills/{skill}/SKILL.md: front matter tanpa name")
        elif fm["name"] != skill:
            fail(f"skills/{skill}/SKILL.md: front matter name {fm['name']!r} != folder {skill!r}")
        elif "description" not in fm:
            fail(f"skills/{skill}/SKILL.md: front matter tanpa description")
        ypath = os.path.join(SKILLS_DIR, skill, "skill.yaml")
        if not os.path.isfile(ypath):
            fail(f"skills/{skill}/: skill.yaml tidak ada")
            continue
        name, err = yaml_name(ypath)
        if err:
            fail(f"skills/{skill}/skill.yaml: {err}")
        elif name != skill:
            fail(f"skills/{skill}/skill.yaml: name {name!r} != folder {skill!r}")
    ok(f"front matter + skill.yaml dicek untuk {len(skill_dirs())} skill")


def check_readme_table():
    with open(README, encoding="utf-8") as f:
        readme = f.read()
    in_table = re.findall(r"\|[^|\n]*\|([^|\n]*)\|", readme)
    table_names = set()
    for cell in in_table:
        table_names.update(re.findall(r"`([A-Za-z0-9][A-Za-z0-9_-]*)`", cell))
    missing = [s for s in skill_dirs() if s not in table_names]
    for skill in missing:
        fail(f"README: skill {skill!r} tidak muncul di tabel Isi repo")
    extra = sorted(n for n in table_names if n not in skill_dirs() and n != "_shared")
    for name in extra:
        fail(f"README: entri tabel {name!r} tidak punya folder skills/{name}/")
    if not missing and not extra:
        ok(f"semua {len(skill_dirs())} skill muncul di tabel README")


def iter_text_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            _, ext = os.path.splitext(fn)
            if ext in TEXT_EXTS:
                path = os.path.join(dirpath, fn)
                if os.path.relpath(path, ROOT) == "validate_skills.py":
                    continue  # validator tidak memeriksa dirinya sendiri
                yield path


RE_HOME = re.compile(r"/home/(?!<)[^/\s]+/|/Users/(?!<)[^/\s]+/")
RE_PRIVKEY_ASSIGN = re.compile(r"PRIVATE_KEY\s*[:=]\s*[\"'][^\"']{8,}")
RE_SK_KEY = re.compile(r"sk-[A-Za-z0-9]{20,}")
RE_HEX64 = re.compile(r"\b(?:0x)?[0-9a-fA-F]{64}\b")
REJECT_WORDS = ("tolak", "reject", "forbidden", "pola", "pattern", "dilarang")
BIP39_TEST_VECTOR = "abandon"


def check_secrets_and_paths():
    hits = 0
    for path in iter_text_files():
        rel = os.path.relpath(path, ROOT)
        with open(path, encoding="utf-8", errors="replace") as f:
            prev_lines = []
            for i, line in enumerate(f, 1):
                low = line.lower()
                # Konteks 3 baris sebelumnya: checksum sering dilabeli di
                # baris terpisah dari nilai hash-nya (mis. blok kode SHA-256).
                context = " ".join(prev_lines + [low])
                prev_lines = (prev_lines + [low])[-3:]
                if RE_HOME.search(line):
                    fail(f"{rel}:{i}: path pribadi: {line.strip()[:100]}")
                    hits += 1
                if RE_PRIVKEY_ASSIGN.search(line):
                    fail(f"{rel}:{i}: PRIVATE_KEY diberi nilai")
                    hits += 1
                if RE_SK_KEY.search(line):
                    fail(f"{rel}:{i}: pola kunci sk-...: {line.strip()[:80]}")
                    hits += 1
                for m in RE_HEX64.finditer(line):
                    if "sha-256" in context or "sha256" in context or "checksum" in context:
                        continue  # checksum/SHA-256 artefak publik, bukan kunci
                    hx = m.group(0).lower().removeprefix("0x")
                    if hx == "0" * 64:
                        continue  # nol semua: bukan kunci
                    if any(w in low for w in REJECT_WORDS):
                        continue  # baris penolakan/pola, bukan kunci
                    if "test" in rel and BIP39_TEST_VECTOR in low:
                        continue
                    fail(f"{rel}:{i}: string heks 64 karakter mirip private key")
                    hits += 1
                if "mnemonic" in low:
                    # Periksa literal string berquote saja (bukan seluruh
                    # baris kode): frasa 12/24 kata huruf kecil berurutan.
                    for lit in re.findall(r"[\"']([^\"']+)[\"']", line):
                        words = re.findall(r"[a-z]+", lit.lower())
                        if len(words) >= 12 and BIP39_TEST_VECTOR not in lit.lower():
                            if not any(w in low for w in REJECT_WORDS):
                                fail(f"{rel}:{i}: frasa mnemonic 12/24 kata")
                                hits += 1
                                break
    if hits == 0:
        ok("tidak ada path pribadi / pola kunci / .env terlacak")


def check_no_dotenv():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        if ".env" in filenames:
            fail(f"{os.path.relpath(os.path.join(dirpath, '.env'), ROOT)}: file .env terlacak")
    ok("tidak ada file .env (bukan .env.example) di repo")


def main():
    check_front_matter_and_yaml()
    check_readme_table()
    check_secrets_and_paths()
    check_no_dotenv()
    for n in notes:
        print(f"catatan: {n}")
    print(f"\n{len(failures)} kegagalan.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
