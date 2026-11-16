#!/usr/bin/env python3
"""airdrop.py - tracker airdrop/testnet/quest/free-mint dengan state tetap (JSON). Hanya stdlib.

Satu sumber data untuk semua sesi (menggantikan xlsx yang dibuat ulang tiap sesi).
Tool ini HANYA mencatat; tidak mengeksekusi transaksi apa pun, tidak konek wallet,
tidak memakai key apa pun. Satu-satunya file yang ditulis: airdrop-state.json
(+ cadangan airdrop-state.json.bak sebelum menulis).

  python airdrop.py add --name "Proyek X" --category Testnet --chain Ethereum \
      --wallet Burner-A --deadline 2026-12-01 --deadline-type klaim --cost 1.2
  python airdrop.py log --project P001 --action "swap" --cost 0.8 --tx 0xabc...
  python airdrop.py status
  python airdrop.py deadlines
  python airdrop.py roi
  python airdrop.py export-xlsx --out airdrop-tracker.xlsx

Lokasi state: --state, atau env AIRDROP_STATE, atau $MUSE_WORKSPACE/airdrop-state.json
(env MUSE_WORKSPACE default ~/workspace; AIRDROP_STATE menang atas MUSE_WORKSPACE)

KEAMANAN: hanya alamat publik/label wallet yang boleh disimpan. Input yang cocok
pola kunci/seed DITOLAK dan perintah gagal (exit code bukan 0):
  - string heks 64 karakter, dengan/tanpa awalan 0x (bentuk private key)
  - 12 atau 24 kata huruf kecil semua (bentuk mnemonic)
  - input yang mengandung "mnemonic", "seed phrase", atau "private key"
Pengecualian: --tx menerima hash transaksi (64 heks, data publik on-chain) karena
kolom hash memang bagian dari Log Aktivitas; semua kolom lain menolak pola itu.
"""

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

WIB = timezone(timedelta(hours=7))

MUSE_WORKSPACE = Path(os.environ.get("MUSE_WORKSPACE") or "~/workspace").expanduser()
DEFAULT_STATE = Path(os.environ.get("AIRDROP_STATE") or str(MUSE_WORKSPACE / "airdrop-state.json")).expanduser()

CATEGORIES = ["Testnet", "Mainnet", "Points", "Quest", "Free mint", "Retro"]
STATUSES = {
    "riset": "🔍 Riset", "🔍 riset": "🔍 Riset",
    "aktif": "✅ Aktif", "✅ aktif": "✅ Aktif",
    "pause": "⏸ Pause", "⏸ pause": "⏸ Pause",
    "menunggu snapshot": "⏰ Menunggu snapshot", "⏰ menunggu snapshot": "⏰ Menunggu snapshot",
    "siap klaim": "🎁 Siap klaim", "🎁 siap klaim": "🎁 Siap klaim",
    "selesai": "✔ Selesai", "✔ selesai": "✔ Selesai",
    "dibuang": "❌ Dibuang", "❌ dibuang": "❌ Dibuang",
}
SCORES = {"🟢": "🟢", "hijau": "🟢", "green": "🟢",
          "🟡": "🟡", "kuning": "🟡", "yellow": "🟡",
          "🔴": "🔴", "merah": "🔴", "red": "🔴"}
DEADLINE_TYPES = ["snapshot", "season end", "klaim", "mint"]
FREQUENCIES = ["Harian", "Mingguan", "Sekali"]


class ToolError(Exception):
    """Kesalahan yang menghentikan perintah; file state tidak diubah."""


# ------------------------------------------------------------- penolakan kunci/seed

_HEX64 = re.compile(r"^(0x)?[0-9a-fA-F]{64}$")
_HEX64_TOKEN = re.compile(r"(0x)?[0-9a-fA-F]{64}")
_WORD = re.compile(r"^[a-z]{3,8}$")
_FORBIDDEN_WORDS = ("mnemonic", "seed phrase", "seedphrase", "private key", "privatekey")


def reject_secret(value, field):
    """Tolak nilai yang cocok pola kunci/seed. Kembalikan value bila aman."""
    if value is None:
        return value
    text = str(value)
    low = text.lower()
    for word in _FORBIDDEN_WORDS:
        if word in low:
            raise ToolError(
                f"input --{field} ditolak: mengandung frasa terlarang {word!r}. "
                "Tracker hanya menyimpan alamat publik/label wallet; jangan pernah memasukkan "
                "seed phrase atau private key. Perintah dibatalkan, state tidak diubah.")
    stripped = text.strip()
    if _HEX64.match(stripped) or _HEX64_TOKEN.search(stripped):
        raise ToolError(
            f"input --{field} ditolak: cocok pola kunci heks 64 karakter (bentuk private key). "
            "Tracker hanya menyimpan alamat publik/label wallet; jangan pernah memasukkan "
            "private key. Perintah dibatalkan, state tidak diubah.")
    words = stripped.split()
    if len(words) in (12, 24) and all(_WORD.match(w) for w in words):
        raise ToolError(
            f"input --{field} ditolak: {len(words)} kata huruf kecil, cocok pola mnemonic. "
            "Tracker hanya menyimpan alamat publik/label wallet; jangan pernah memasukkan "
            "seed phrase. Perintah dibatalkan, state tidak diubah.")
    return value


# --------------------------------------------------------------------- format

def idn(x, d=2):
    """Format Indonesia: titik ribuan, koma desimal."""
    s = f"{x:,.{d}f}"
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def usd(x):
    if abs(x) < 0.005:
        return "$0,00"
    return ("-" if x < 0 else "") + "$" + idn(abs(x), 2)


def signed_pct(x, d=1):
    return ("+" if x >= 0 else "-") + idn(abs(x), d) + "%"


def parse_date(text, field="tanggal"):
    try:
        return datetime.strptime(text.strip(), "%Y-%m-%d").date()
    except (ValueError, AttributeError):
        raise ToolError(f"format {field} salah: {text!r} (pakai 'YYYY-MM-DD')")


def parse_now(text):
    """'YYYY-MM-DD' atau 'YYYY-MM-DD HH:mm' -> datetime WIB (untuk --now / tes)."""
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text.strip(), fmt).replace(tzinfo=WIB)
        except ValueError:
            continue
    raise ToolError(f"format --now salah: {text!r} (pakai 'YYYY-MM-DD' atau 'YYYY-MM-DD HH:mm')")


def get_now(args):
    return parse_now(args.now) if getattr(args, "now", None) else datetime.now(WIB)


def deadline_marker(days_left):
    """Penanda SKILL.md: 🔴 ≤3 hari · 🟠 ≤7 hari · 🟡 ≤14 hari."""
    if days_left <= 3:
        return "🔴"
    if days_left <= 7:
        return "🟠"
    if days_left <= 14:
        return "🟡"
    return "  "


# ---------------------------------------------------------------------- state

EMPTY_STATE = {"projects": [], "log": [], "claims": []}


def load_state(path):
    path = Path(path).expanduser()
    if not path.exists():
        # Salinan baru setiap kali: dict(EMPTY_STATE) saja tidak cukup karena
        # list di dalamnya masih berbagi objek dengan EMPTY_STATE.
        return {"projects": [], "log": [], "claims": []}, True
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ToolError(f"state {path} rusak (bukan JSON valid): {exc}. State tidak diubah.")
    if not isinstance(data, dict):
        raise ToolError(f"state {path} rusak: isi harus objek JSON. State tidak diubah.")
    for key in EMPTY_STATE:
        data.setdefault(key, [])
    return data, False


def save_state(path, data):
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copy2(path, str(path) + ".bak")
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".airdrop-state-", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, path)


def next_project_id(state):
    used = [int(m.group(1)) for p in state["projects"]
            if (m := re.fullmatch(r"P(\d+)", p.get("id", "")))]
    return f"P{(max(used) + 1) if used else 1:03d}"


def find_project(state, ref):
    """Cari proyek berdasarkan ID atau nama (tidak peka huruf besar/kecil)."""
    ref = ref.strip()
    for p in state["projects"]:
        if p["id"].lower() == ref.lower() or p["name"].lower() == ref.lower():
            return p
    raise ToolError(f"proyek {ref!r} tidak ada di state. Cek: airdrop.py status")


def nonneg(value, field):
    if value is None:
        return 0.0
    if value < 0:
        raise ToolError(f"--{field} tidak boleh negatif: {value}")
    return float(value)


# ------------------------------------------------------------------- perintah

def cmd_add(args):
    state, _ = load_state(args.state)
    for field in ("name", "wallet", "link", "notes", "next_task"):
        reject_secret(getattr(args, field, None), field)
    if any(p["name"].lower() == args.name.strip().lower() for p in state["projects"]):
        raise ToolError(f"proyek {args.name!r} sudah ada di state. Pakai nama lain atau cek status.")
    if args.category not in CATEGORIES:
        raise ToolError(f"--category harus salah satu: {', '.join(CATEGORIES)}")
    status = STATUSES.get(args.status.strip().lower())
    if status is None:
        raise ToolError("--status harus salah satu: " + ", ".join(sorted(set(STATUSES.values()))))
    score = None
    if args.score is not None:
        score = SCORES.get(args.score.strip().lower())
        if score is None:
            raise ToolError("--score harus 🟢, 🟡, atau 🔴")
    deadline = None
    if args.deadline is not None:
        deadline = parse_date(args.deadline, "--deadline").isoformat()
    if args.deadline_type not in DEADLINE_TYPES:
        raise ToolError(f"--deadline-type harus salah satu: {', '.join(DEADLINE_TYPES)}")
    if args.frequency not in FREQUENCIES:
        raise ToolError(f"--frequency harus salah satu: {', '.join(FREQUENCIES)}")
    now = get_now(args)
    pid = args.id.strip() if args.id else next_project_id(state)
    if any(p["id"].lower() == pid.lower() for p in state["projects"]):
        raise ToolError(f"ID {pid!r} sudah dipakai proyek lain.")
    project = {
        "id": pid,
        "name": args.name.strip(),
        "category": args.category,
        "chain": args.chain or "",
        "status": status,
        "score": score or "",
        "wallet": args.wallet or "",
        "next_task": args.next_task or "",
        "frequency": args.frequency,
        "deadline": deadline or "",
        "deadline_type": args.deadline_type,
        "deadline_verified": bool(args.deadline_verified),
        "cost": nonneg(args.cost, "cost"),
        "locked": nonneg(args.locked, "locked"),
        "est_reward": nonneg(args.est_reward, "est-reward"),
        "real_reward": nonneg(args.real_reward, "real-reward"),
        "link": args.link or "",
        "notes": args.notes or "",
        "updated": now.strftime("%Y-%m-%d"),
    }
    state["projects"].append(project)
    save_state(args.state, state)
    print(f"Proyek ditambahkan: {pid} — {project['name']} [{project['status']}]")
    if deadline:
        print(f"  Deadline {deadline} ({args.deadline_type})"
              + (" · sudah diverifikasi ke sumber resmi" if project["deadline_verified"]
                 else " · BELUM diverifikasi — cek ke sumber resmi"))
    print(f"State: {Path(args.state).expanduser()}")


def cmd_log(args):
    state, _ = load_state(args.state)
    for field in ("wallet", "note"):
        reject_secret(getattr(args, field, None), field)
    # --tx sengaja TIDAK dicek pola heks 64: hash transaksi adalah data publik on-chain.
    project = find_project(state, args.project)
    now = get_now(args)
    date = parse_date(args.date, "--date") if args.date else now.date()
    cost = nonneg(args.cost, "cost")
    entry = {
        "date": date.isoformat(),
        "project": project["id"],
        "wallet": args.wallet or project.get("wallet", ""),
        "chain": args.chain or project.get("chain", ""),
        "action": args.action.strip(),
        "tx": args.tx or "",
        "cost": cost,
        "note": args.note or "",
    }
    state["log"].append(entry)
    project["cost"] = round(project.get("cost", 0.0) + cost, 2)
    if args.real_reward is not None:
        project["real_reward"] = round(project.get("real_reward", 0.0) + args.real_reward, 2)
    if args.est_reward is not None:
        project["est_reward"] = round(project.get("est_reward", 0.0) + args.est_reward, 2)
    if args.token:
        amount = args.amount if args.amount is not None else 0.0
        price = args.price if args.price is not None else 0.0
        state["claims"].append({
            "date": date.isoformat(),
            "project": project["id"],
            "token": args.token,
            "amount": amount,
            "price_at_receipt": price,
            "sold": bool(args.sold),
            "sell_price": args.sell_price if args.sell_price is not None else "",
            "note": args.note or "",
        })
        if price and amount:
            project["real_reward"] = round(project.get("real_reward", 0.0) + amount * price, 2)
    project["updated"] = date.isoformat()
    save_state(args.state, state)
    print(f"Log dicatat: {project['id']} {project['name']} — {entry['action']} "
          f"({date.isoformat()}, biaya {usd(cost)})")
    print(f"  Total biaya proyek sekarang {usd(project['cost'])}")
    print(f"State: {Path(args.state).expanduser()}")


def cmd_status(args):
    state, is_new = load_state(args.state)
    now = get_now(args)
    today = now.date()
    projects = state["projects"]
    active = [p for p in projects if p["status"] in ("✅ Aktif", "🔍 Riset", "⏰ Menunggu snapshot", "🎁 Siap klaim")]
    total_cost = sum(p.get("cost", 0.0) for p in projects)
    total_locked = sum(p.get("locked", 0.0) for p in projects)
    total_real = sum(p.get("real_reward", 0.0) for p in projects)
    total_est = sum(p.get("est_reward", 0.0) for p in projects)
    print(f"Status tracker — {today.isoformat()}"
          + (" (state baru, belum ada proyek)" if is_new else ""))
    print(f"  Proyek total   : {len(projects)} · aktif {len(active)}")
    print(f"  Total biaya    : {usd(total_cost)}")
    print(f"  Modal terkunci : {usd(total_locked)} (dicatat, bukan biaya kas)")
    print(f"  Reward realisasi: {usd(total_real)} · estimasi: {usd(total_est)} (terpisah)")
    print("  Proyek aktif   :")
    if not active:
        print("    -")
    for p in active:
        task = p.get("next_task") or "⚠️ TANPA tugas berikutnya — selesai, atau terlupa?"
        stale = ""
        try:
            upd = parse_date(p.get("updated") or today.isoformat())
            if (today - upd).days >= 30:
                stale = f" · ⚠️ tidak ada aktivitas {(today - upd).days} hari"
        except ToolError:
            pass
        print(f"    - {p['id']} {p['name']} [{p['status']}] biaya {usd(p.get('cost', 0.0))}"
              f" · tugas: {task}{stale}")
    print(f"State: {Path(args.state).expanduser()}")


def cmd_deadlines(args):
    state, _ = load_state(args.state)
    now = get_now(args)
    today = now.date()
    rows = []
    for p in state["projects"]:
        if not p.get("deadline"):
            continue
        try:
            dl = parse_date(p["deadline"], "deadline")
        except ToolError:
            continue
        rows.append((dl, p))
    rows.sort(key=lambda r: r[0])
    print(f"Deadline — {today.isoformat()} (🔴 ≤3 hari · 🟠 ≤7 hari · 🟡 ≤14 hari)")
    if not rows:
        print("  Tidak ada proyek dengan deadline.")
        return
    for dl, p in rows:
        days = (dl - today).days
        marker = deadline_marker(days)
        when = f"lewat {-days} hari" if days < 0 else ("hari ini" if days == 0 else f"{days} hari lagi")
        verified = "terverifikasi ✓" if p.get("deadline_verified") else "BELUM dicek — verifikasi ke sumber resmi"
        print(f"  {marker} {dl.isoformat()} ({when}) · {p['id']} {p['name']} "
              f"[{p.get('deadline_type', '')}] · {verified}")


def roi_values(cost, reward):
    """(teks ROI) mengikuti rumus SKILL.md; None bila tidak bisa dihitung."""
    if cost <= 0:
        return None
    return (reward - cost) / cost * 100


def cmd_roi(args):
    state, _ = load_state(args.state)
    projects = state["projects"]
    if args.project:
        projects = [find_project(state, args.project)]
    if not projects:
        print("Belum ada proyek di state.")
        return
    print("ROI — realisasi dan estimasi TERPISAH (rumus SKILL.md)")
    print("  ROI realisasi = (reward realisasi − total biaya) / total biaya")
    print("  ROI estimasi  = (reward estimasi − total biaya) / total biaya  ← tandai 'estimasi'")
    total_cost = total_real = total_est = 0.0
    for p in projects:
        cost = p.get("cost", 0.0)
        real = p.get("real_reward", 0.0)
        est = p.get("est_reward", 0.0)
        total_cost += cost
        total_real += real
        total_est += est
        r_real = roi_values(cost, real)
        r_est = roi_values(cost, est)
        if cost <= 0:
            real_txt = "— (belum ada biaya)"
        elif real <= 0:
            real_txt = "belum ada hasil"
        else:
            real_txt = f"{signed_pct(r_real)} ({usd(real)} − {usd(cost)})"
        est_txt = "— (belum ada biaya)" if cost <= 0 else f"{signed_pct(r_est)} (estimasi)"
        locked = p.get("locked", 0.0)
        print(f"  {p['id']} {p['name']}: biaya {usd(cost)} · modal terkunci {usd(locked)} (bukan biaya kas)")
        print(f"    realisasi: {real_txt}")
        print(f"    estimasi : {est_txt}")
    if len(projects) > 1 or args.project is None:
        r_real = roi_values(total_cost, total_real)
        r_est = roi_values(total_cost, total_est)
        print(f"  TOTAL: biaya {usd(total_cost)} · realisasi {usd(total_real)} · estimasi {usd(total_est)}")
        if total_cost <= 0:
            print("    ROI realisasi: — (belum ada biaya) · ROI estimasi: — (belum ada biaya)")
        else:
            real_txt = "belum ada hasil" if total_real <= 0 else signed_pct(r_real)
            print(f"    ROI realisasi: {real_txt} · ROI estimasi: {signed_pct(r_est)} (estimasi)")


# -------------------------------------------------------------- export (xlsx/csv)

PROJECT_HEADERS = ["ID", "Proyek", "Kategori", "Chain", "Status", "Skor", "Wallet",
                   "Tugas berikutnya", "Frekuensi", "Deadline", "Jenis deadline",
                   "Deadline terverifikasi", "Biaya terpakai (USD)", "Modal terkunci (USD)",
                   "Estimasi reward (USD)", "Reward realisasi (USD)", "Link resmi",
                   "Catatan", "Terakhir diperbarui"]
LOG_HEADERS = ["Tanggal", "Proyek", "Wallet", "Chain", "Aksi", "Hash transaksi",
               "Biaya (USD)", "Catatan"]
CLAIM_HEADERS = ["Tanggal", "Proyek", "Token/NFT", "Jumlah", "Harga saat diterima",
                 "Dijual?", "Harga jual", "Catatan pajak"]
DEADLINE_HEADERS = ["Tanggal", "Proyek", "Jenis (snapshot/season end/klaim/mint)",
                    "Sudah dicek ke sumber resmi?"]


def project_row(p):
    return [p.get("id", ""), p.get("name", ""), p.get("category", ""), p.get("chain", ""),
            p.get("status", ""), p.get("score", ""), p.get("wallet", ""),
            p.get("next_task", ""), p.get("frequency", ""), p.get("deadline", ""),
            p.get("deadline_type", ""), "Ya" if p.get("deadline_verified") else "Tidak",
            p.get("cost", 0.0), p.get("locked", 0.0), p.get("est_reward", 0.0),
            p.get("real_reward", 0.0), p.get("link", ""), p.get("notes", ""),
            p.get("updated", "")]


def log_row(e):
    return [e.get("date", ""), e.get("project", ""), e.get("wallet", ""), e.get("chain", ""),
            e.get("action", ""), e.get("tx", ""), e.get("cost", 0.0), e.get("note", "")]


def claim_row(c):
    return [c.get("date", ""), c.get("project", ""), c.get("token", ""), c.get("amount", ""),
            c.get("price_at_receipt", ""), "Ya" if c.get("sold") else "Tidak",
            c.get("sell_price", ""), c.get("note", "")]


def deadline_rows(state):
    rows = []
    for p in state["projects"]:
        if p.get("deadline"):
            rows.append([p["deadline"], p["id"] + " " + p["name"], p.get("deadline_type", ""),
                         "Ya" if p.get("deadline_verified") else "Tidak"])
    rows.sort(key=lambda r: r[0])
    return rows


def cmd_export_xlsx(args):
    state, _ = load_state(args.state)
    out = Path(args.out).expanduser() if args.out else \
        Path(args.state).expanduser().parent / "airdrop-tracker.xlsx"
    tabs = [
        ("Proyek", PROJECT_HEADERS, [project_row(p) for p in state["projects"]]),
        ("Log Aktivitas", LOG_HEADERS, [log_row(e) for e in state["log"]]),
        ("Klaim & Hasil", CLAIM_HEADERS, [claim_row(c) for c in state["claims"]]),
        ("Deadline", DEADLINE_HEADERS, deadline_rows(state)),
    ]
    try:
        import openpyxl  # noqa: F401  (opsional; fallback ke CSV bila tidak ada)
    except ImportError:
        out = out.with_suffix("")
        written = []
        for name, headers, rows in tabs:
            csv_path = out.parent / f"{out.name}-{name.lower().replace(' ', '-').replace('&', 'dan')}.csv"
            import csv
            with open(csv_path, "w", encoding="utf-8", newline="") as fh:
                writer = csv.writer(fh)
                writer.writerow(headers)
                writer.writerows(rows)
            written.append(csv_path)
        print("openpyxl tidak tersedia — xlsx butuh openpyxl (pip install openpyxl).")
        print("Diekspor sebagai CSV sebagai gantinya:")
        for path in written:
            print(f"  {path}")
        return
    from openpyxl import Workbook
    wb = Workbook()
    for i, (name, headers, rows) in enumerate(tabs):
        ws = wb.active if i == 0 else wb.create_sheet(name)
        ws.title = name
        ws.append(headers)
        for row in rows:
            ws.append(row)
        if name == "Proyek" and rows:
            n = len(rows) + 1  # baris terakhir data (baris 1 = header)
            ws.append(["TOTAL"] + [""] * 11 + [
                f"=SUM(M2:M{n})", f"=SUM(N2:N{n})", f"=SUM(O2:O{n})", f"=SUM(P2:P{n})",
                "", "", ""])
    wb.save(out)
    print(f"Diekspor ke {out} (4 tab: Proyek, Log Aktivitas, Klaim & Hasil, Deadline)")
    print("Catatan: angka reward bersifat spekulatif; realisasi dan estimasi tetap terpisah.")


# ----------------------------------------------------------------------- CLI

def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--state", default=str(DEFAULT_STATE), help="path airdrop-state.json")
    common.add_argument("--now", help="(uji) waktu WIB 'YYYY-MM-DD' atau 'YYYY-MM-DD HH:mm'")

    p = argparse.ArgumentParser(
        description="Tracker airdrop/testnet/quest/free-mint dengan state tetap (JSON). "
                    "Hanya mencatat; tidak mengeksekusi transaksi.")
    sub = p.add_subparsers(dest="cmd", required=True)

    ad = sub.add_parser("add", parents=[common], help="tambah proyek")
    ad.add_argument("--name", required=True)
    ad.add_argument("--id", help="ID manual (default P001, P002, ...)")
    ad.add_argument("--category", default="Testnet", help=", ".join(CATEGORIES))
    ad.add_argument("--chain", default="")
    ad.add_argument("--status", default="Riset", help="Riset/Aktif/Pause/Menunggu snapshot/Siap klaim/Selesai/Dibuang")
    ad.add_argument("--score", help="🟢/🟡/🔴")
    ad.add_argument("--wallet", default="", help="label wallet SAJA, bukan kunci")
    ad.add_argument("--next-task", default="")
    ad.add_argument("--frequency", default="Sekali", help=", ".join(FREQUENCIES))
    ad.add_argument("--deadline", help="'YYYY-MM-DD'")
    ad.add_argument("--deadline-type", default="klaim", help=", ".join(DEADLINE_TYPES))
    ad.add_argument("--deadline-verified", action="store_true",
                    help="deadline sudah dicek ke sumber resmi")
    ad.add_argument("--cost", type=float, default=0.0, help="biaya terpakai USD")
    ad.add_argument("--locked", type=float, default=0.0, help="modal terkunci USD")
    ad.add_argument("--est-reward", type=float, default=0.0, help="estimasi reward USD")
    ad.add_argument("--real-reward", type=float, default=0.0, help="reward realisasi USD")
    ad.add_argument("--link", default="")
    ad.add_argument("--notes", default="")
    ad.set_defaults(fn=cmd_add)

    lg = sub.add_parser("log", parents=[common], help="catat aktivitas (dan klaim)")
    lg.add_argument("--project", required=True, help="ID atau nama proyek")
    lg.add_argument("--action", required=True)
    lg.add_argument("--cost", type=float, default=0.0, help="biaya USD, ditambah ke total proyek")
    lg.add_argument("--date", help="'YYYY-MM-DD' (default hari ini)")
    lg.add_argument("--wallet", default="")
    lg.add_argument("--chain", default="")
    lg.add_argument("--tx", default="", help="hash transaksi (data publik on-chain)")
    lg.add_argument("--note", default="")
    lg.add_argument("--real-reward", type=float, help="tambah reward realisasi USD")
    lg.add_argument("--est-reward", type=float, help="tambah estimasi reward USD")
    lg.add_argument("--token", help="bila klaim: nama token/NFT yang diterima")
    lg.add_argument("--amount", type=float, help="jumlah token/NFT yang diterima")
    lg.add_argument("--price", type=float, help="harga saat diterima (USD)")
    lg.add_argument("--sold", action="store_true")
    lg.add_argument("--sell-price", type=float, help="harga jual (USD)")
    lg.set_defaults(fn=cmd_log)

    st = sub.add_parser("status", parents=[common], help="ringkasan tracker")
    st.set_defaults(fn=cmd_status)

    dl = sub.add_parser("deadlines", parents=[common], help="daftar deadline terurut")
    dl.set_defaults(fn=cmd_deadlines)

    ro = sub.add_parser("roi", parents=[common], help="ROI realisasi vs estimasi (terpisah)")
    ro.add_argument("--project", help="ID atau nama proyek (default: semua + total)")
    ro.set_defaults(fn=cmd_roi)

    ex = sub.add_parser("export-xlsx", parents=[common],
                        help="ekspor 4 tab ke .xlsx (butuh openpyxl; bila tidak ada, CSV)")
    ex.add_argument("--out", help="path berkas keluaran")
    ex.set_defaults(fn=cmd_export_xlsx)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.fn(args)
        return 0
    except ToolError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
