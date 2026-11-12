#!/usr/bin/env python3
"""trade.py - pencatat jurnal trade (spot LONG). Hanya stdlib.

Semua angka dihitung kode, bukan tangan. Tool ini TIDAK mengeksekusi order,
tidak konek wallet, tidak memakai key apa pun. Satu-satunya file yang ditulis:
trade-journal.md (+ cadangan trade-journal.md.bak sebelum menulis).

  python trade.py plan --pair UAI --entry 0.04072 --stop 0.0399 --setup 2 \
      --trigger "..." --venue "bursa spot" --expiry "2026-11-11 05:32 WIB"
  python trade.py close --id UAI-20261111-01 --exit 0.0414 --alasan "..."
  python trade.py status

Lokasi jurnal: --journal, atau env TRADE_JOURNAL, atau ~/workspace/trade-journal.md
"""

import argparse
import math
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

WIB = timezone(timedelta(hours=7))

# Parameter user (TETAP, jangan diubah tanpa persetujuan user)
MODAL = 44.0
FEE_PCT = 0.1            # per sisi, ilustratif (fee bursa belum terverifikasi)
BUDGET_HARIAN = 2.20     # 5% modal
MAX_TRADE_HARIAN = 2
MIN_NET_RR = 1.5
MIN_VOLUME = 100_000.0
MAX_JARAK_STOP_PCT = 20.0  # di atas ini dianggap tidak masuk akal -> berhenti
BIG_CAPS = {"BTC", "ETH", "BNB", "SOL", "XRP"}
DEFAULT_JOURNAL = Path(os.environ.get("TRADE_JOURNAL", "~/workspace/trade-journal.md")).expanduser()

COLUMNS = ["ID", "Tanggal-jam rencana (WIB)", "Pair", "Venue", "Setup", "Zona entry",
           "Pemicu", "Stop", "Target", "Berlaku sampai", "Checklist",
           "Risiko rencana (USDT)", "Ukuran rencana", "Status"]
SESI_COLUMNS = ["Tanggal", "Rencana", "Trade", "P&L kotor", "P&L bersih",
                "Batas rugi tercapai?", "Catatan"]

IDX_ID, IDX_DATE, IDX_PAIR, IDX_ENTRY, IDX_STOP, IDX_EXPIRY, IDX_STATUS = 0, 1, 2, 5, 7, 9, 13


class ToolError(Exception):
    """Kesalahan yang menghentikan perintah; file jurnal tidak diubah."""


# ---------------------------------------------------------------- rumus (§2.3)

def calc(entry, stop, spread_pct=None):
    """Rumus persis spek. Tidak ada pembulatan sebelum hasil akhir."""
    if not (entry > 0 and stop > 0):
        raise ToolError("entry dan stop harus > 0")
    if stop >= entry:
        raise ToolError("stop harus di bawah entry (tool ini untuk spot LONG)")
    dist = entry - stop
    jarak_stop = dist / entry
    jarak_stop_pct = jarak_stop * 100
    if jarak_stop_pct > MAX_JARAK_STOP_PCT:
        raise ToolError(f"jarak stop {jarak_stop_pct:.1f}% tidak masuk akal (> {MAX_JARAK_STOP_PCT:.0f}%). "
                        "Cek lagi harga entry/stop, atau pakai --force bila memang disengaja.")
    target = entry + 2 * dist
    target_pct = (target - entry) / entry * 100
    spread_asumsi = spread_pct is None
    spread_used = 0.1 if spread_asumsi else spread_pct
    biaya_pct = FEE_PCT + FEE_PCT + spread_used
    net_rr = (target_pct - biaya_pct) / (jarak_stop_pct + biaya_pct)
    return {
        "entry": entry, "stop": stop, "target": target,
        "jarak_stop_pct": jarak_stop_pct, "target_pct": target_pct,
        "biaya_pct": biaya_pct, "spread_asumsi": spread_asumsi, "spread_pct": spread_used,
        "net_rr": net_rr,
        "risiko_usdt": jarak_stop * MODAL,
        "ukuran": MODAL / entry,
    }


def calc_close(entry, stop, exit_price):
    ukuran = MODAL / entry
    pnl_kotor = (exit_price - entry) * ukuran
    risiko = (entry - stop) / entry * MODAL
    return {"ukuran": ukuran, "pnl_kotor": pnl_kotor,
            "pnl_pct": (exit_price - entry) / entry * 100,
            "risiko_usdt": risiko, "hasil_r": pnl_kotor / risiko}


# ------------------------------------------------------------------ format

def idn(x, d):
    """Format Indonesia: titik ribuan, koma desimal."""
    s = f"{x:,.{d}f}"
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def signed_usd(x):
    if abs(x) < 0.005:
        return "$0,00"
    return ("+" if x > 0 else "-") + "$" + idn(abs(x), 2)


def signed_pct(x, d=2):
    return ("+" if x >= 0 else "-") + idn(abs(x), d) + "%"


def price(x, sig=6):
    """Harga dengan `sig` digit signifikan, koma desimal, tanpa nol di ujung."""
    decimals = max(2, min(12, sig - 1 - math.floor(math.log10(abs(x))))) if x else 2
    s = f"{x:.{decimals}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s.replace(".", ",")


def sig_digits(text):
    digits = text.replace(".", "").replace("-", "").lstrip("0").rstrip("0")
    return len(digits)


def parse_price(cell):
    m = re.search(r"\$\s*([\d.,]+)", cell)
    if not m:
        raise ToolError(f"tidak bisa membaca harga dari kolom: {cell!r}")
    tok = m.group(1).rstrip(".,")
    if "," in tok:
        tok = tok.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", tok):
        tok = tok.replace(".", "")
    return float(tok)


def parse_wib(text, allow_wib_suffix=True):
    m = re.search(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}):(\d{2})", text)
    if not m:
        raise ToolError(f"format waktu salah: {text!r} (pakai 'YYYY-MM-DD HH:mm WIB')")
    return datetime.strptime(f"{m.group(1)} {m.group(2)}:{m.group(3)}", "%Y-%m-%d %H:%M").replace(tzinfo=WIB)


def fmt_wib(dt):
    return dt.astimezone(WIB).strftime("%Y-%m-%d %H:%M") + " WIB"


def clean_cell(text):
    return re.sub(r"\s+", " ", text.replace("|", "/")).strip()


# ------------------------------------------------------------------- jurnal

SKELETON = (
    "# Jurnal Trade\n\n## Trade\n\n"
    "| " + " | ".join(COLUMNS) + " |\n|" + "|".join("---" for _ in COLUMNS) + "|\n\n"
    "## Sesi\n\n"
    "| " + " | ".join(SESI_COLUMNS) + " |\n|" + "|".join("---" for _ in SESI_COLUMNS) + "|\n"
)


class Journal:
    def __init__(self, path):
        self.path = Path(path).expanduser()
        self.backed_up = False
        if self.path.exists():
            self.lines = self.path.read_text(encoding="utf-8").split("\n")
        else:
            self.lines = SKELETON.split("\n")
            self.is_new = True
            return
        self.is_new = False

    # -- struktur
    def section(self, name):
        start = None
        for i, ln in enumerate(self.lines):
            if re.match(rf"^##\s+{name}\b", ln):
                start = i
                break
        if start is None:
            raise ToolError(f"bagian '## {name}' tidak ada di {self.path}. Jurnal tidak diubah; "
                            "periksa file jurnal atau hapus file agar dibuat ulang dari kerangka.")
        end = len(self.lines)
        for j in range(start + 1, len(self.lines)):
            if self.lines[j].startswith("## "):
                end = j
                break
        return start, end

    def table(self, name):
        """(header_idx, [row_idx...]) untuk tabel pertama di bagian itu."""
        start, end = self.section(name)
        first = next((i for i in range(start, end) if self.lines[i].lstrip().startswith("|")), None)
        if first is None:
            raise ToolError(f"tabel di bagian '## {name}' tidak ditemukan")
        last = first
        while last + 1 < end and self.lines[last + 1].lstrip().startswith("|"):
            last += 1
        return first, list(range(first + 2, last + 1))

    @staticmethod
    def cells(line):
        return [c.strip() for c in line.strip().strip("|").split("|")]

    @staticmethod
    def row(cells):
        return "| " + " | ".join(cells) + " |"

    def trade_rows(self):
        _, rows = self.table("Trade")
        out = []
        for i in rows:
            c = self.cells(self.lines[i])
            if len(c) >= len(COLUMNS):
                out.append((i, c))
        return out

    def add_trade_row(self, cells):
        _, rows = self.table("Trade")
        pos = (rows[-1] if rows else self.table("Trade")[0] + 1) + 1
        self.lines.insert(pos, self.row(cells))

    def add_bullet(self, text):
        start, end = self.section("Trade")
        last_bullet = None
        last_table = None
        for i in range(start, end):
            if self.lines[i].startswith("- "):
                last_bullet = i
            if self.lines[i].lstrip().startswith("|"):
                last_table = i
        if last_bullet is not None:
            self.lines.insert(last_bullet + 1, text)
        else:
            self.lines[last_table + 1:last_table + 1] = ["", text]

    def bullets(self):
        start, end = self.section("Trade")
        return [ln for ln in self.lines[start:end] if ln.startswith("- ")]

    # -- tulis
    def save(self):
        if self.path.exists() and not self.backed_up:
            shutil.copy2(self.path, str(self.path) + ".bak")
            self.backed_up = True
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".trade-journal-", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("\n".join(self.lines).rstrip("\n") + "\n")
        os.replace(tmp, self.path)


def _num(sign, digits):
    v = float(digits.replace(".", "").replace(",", ".")) if "," in digits else float(digits)
    return -v if sign in "-−" else v


def closed_reports(journal):
    """[(id, tanggal_lapor, pnl_kotor, pnl_bersih|None)] dari bullet DITUTUP."""
    out = []
    for b in journal.bullets():
        m = re.match(r"^- (\S+?): \*\*DITUTUP", b)
        if not m:
            continue
        d = re.search(r"dilaporkan (\d{4}-\d{2}-\d{2})", b)
        g = re.search(r"P&L kotor.*?\*\*([+\-−]?)\$\s*([\d.,]+)", b)
        if not d or not g:
            continue
        n = re.search(r"P&L bersih\s*\*\*([+\-−]?)\$\s*([\d.,]+)", b)
        out.append((m.group(1), d.group(1), _num(g.group(1) or "+", g.group(2)),
                    _num(n.group(1) or "+", n.group(2)) if n else None))
    return out


def snapshot(journal, now):
    today = now.strftime("%Y-%m-%d")
    rows = journal.trade_rows()
    today_rows = [c for _, c in rows if c[IDX_DATE].startswith(today)]
    trades_today = [c for c in today_rows if c[IDX_STATUS].strip().upper() in ("AKTIF", "DITUTUP")]
    reports = [r for r in closed_reports(journal) if r[1] == today]
    pnl_kotor = sum(r[2] for r in reports)
    # Batas rugi dihitung atas P&L kotor NETO sesi hari ini (lihat README).
    rugi = max(0.0, -pnl_kotor)
    return {
        "today": today, "rencana_n": len(today_rows), "trade_n": len(trades_today),
        "reports": reports, "pnl_kotor": pnl_kotor, "rugi": rugi,
        "sisa_budget": max(0.0, BUDGET_HARIAN - rugi),
        "slot": max(0, MAX_TRADE_HARIAN - len(trades_today)),
        "rows": rows,
    }


def update_session_row(journal, now, extra_note):
    snap = snapshot(journal, now)
    today = snap["today"]
    reports = snap["reports"]
    bersih = "❓" if (not reports or any(r[3] is None for r in reports)) else \
        signed_usd(sum(r[3] for r in reports))
    start, end = journal.section("Sesi")
    hdr, rows = journal.table("Sesi")
    target = next((i for i in rows if today in journal.lines[i].split("|")[1]), None)
    old_note = ""
    if target is not None:
        c = journal.cells(journal.lines[target])
        old_note = c[6] if len(c) > 6 else ""
    note = old_note
    if extra_note and extra_note not in note:
        note = f"{note}; {extra_note}" if note else extra_note
    cells = [today, str(snap["rencana_n"]), str(snap["trade_n"]),
             signed_usd(snap["pnl_kotor"]) if reports else "$0,00", bersih,
             "Ya" if snap["rugi"] >= BUDGET_HARIAN - 1e-9 else "Tidak", note]
    if target is not None:
        journal.lines[target] = journal.row(cells)
    else:
        journal.lines.insert((rows[-1] if rows else hdr + 1) + 1, journal.row(cells))


def next_id(journal, symbol, now):
    stem = f"{symbol}-{now.strftime('%Y%m%d')}-"
    used = [int(m.group(1)) for _, c in journal.trade_rows()
            if (m := re.fullmatch(re.escape(stem) + r"(\d+)", c[IDX_ID].strip()))]
    return f"{stem}{(max(used) + 1) if used else 1:02d}"


# ------------------------------------------------------------------ perintah

def get_now(args):
    return parse_wib(args.now) if args.now else datetime.now(WIB)


def norm_symbol(pair):
    s = pair.strip().upper().replace("-", "/")
    s = s.split("/")[0]
    if s.endswith("USDT") and len(s) > 4:
        s = s[:-4]
    if not re.fullmatch(r"[A-Z0-9]{2,15}", s):
        raise ToolError(f"pair tidak jelas: {pair!r}")
    return s


def candle_close_conflict(trigger, expiry, now):
    """Bila pemicu menyebut 'candle HH:MM tutup' yang BELUM tutup, expiry harus sesudah tutupnya."""
    m = re.search(r"candle\s+(\d{1,2}):(\d{2})\s+tutup", trigger, re.I)
    if not m:
        return None
    opened = now.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
    closes = opened + timedelta(minutes=15)
    if closes <= now:
        return None  # candle itu sudah tutup; bukan syarat masa depan
    return closes if expiry <= closes else None


def cmd_plan(args):
    now = get_now(args)
    journal = Journal(args.journal)
    symbol = norm_symbol(args.pair)
    if args.setup not in (1, 2, 3):
        raise ToolError("setup harus 1, 2, atau 3 (1=Breakout+volume, 2=Pullback EMA20/50 atau VWAP, "
                        "3=Range scalping). Rencana ditolak, jurnal tidak diubah.")
    try:
        c = calc(args.entry, args.stop, args.spread)
    except ToolError as e:
        if args.force and "tidak masuk akal" in str(e):
            saved = globals()["MAX_JARAK_STOP_PCT"]
            globals()["MAX_JARAK_STOP_PCT"] = 100.0
            try:
                c = calc(args.entry, args.stop, args.spread)
            finally:
                globals()["MAX_JARAK_STOP_PCT"] = saved
        else:
            raise
    expiry = parse_wib(args.expiry)
    conflict = candle_close_conflict(args.trigger, expiry, now)
    if conflict and not args.force:
        raise ToolError(f"masa berlaku {fmt_wib(expiry)} tidak mencakup waktu tutup candle konfirmasi "
                        f"({fmt_wib(conflict)}). Perpanjang --expiry, atau pakai --force. Jurnal tidak diubah.")

    snap = snapshot(journal, now)
    checks = []

    def add(ok, text):
        checks.append((ok, text))

    add(c["net_rr"] >= MIN_NET_RR,
        f"Net R:R {idn(c['net_rr'], 2)}" + ("" if c["net_rr"] >= MIN_NET_RR
                                             else f" - R:R bersih di bawah batas {idn(MIN_NET_RR, 1)}"))
    add(c["risiko_usdt"] <= snap["sisa_budget"] + 1e-9,
        f"Risiko ${idn(c['risiko_usdt'], 2)} " +
        ("≤" if c["risiko_usdt"] <= snap["sisa_budget"] + 1e-9 else ">") +
        f" sisa budget harian ${idn(snap['sisa_budget'], 2)}" +
        ("" if c["risiko_usdt"] <= snap["sisa_budget"] + 1e-9 else " - risiko melebihi sisa budget"))
    if args.volume is not None:
        if args.volume >= MIN_VOLUME:
            add(True, f"Volume 24j ${idn(args.volume, 0)} ≥ $100.000")
        elif args.user_suggested:
            add(True, f"Volume 24j ${idn(args.volume, 0)} < $100.000 - LOLOS BERSYARAT (disarankan user)")
        else:
            add(False, f"Volume 24j ${idn(args.volume, 0)} < $100.000")
    if re.search(r"belum\s+(?:terkonfirmasi|konfirmasi)", args.trigger, re.I):
        add(False, "Pemicu belum terkonfirmasi (dicatat apa adanya; keputusan di user)")
    if snap["slot"] <= 0:
        add(False, f"Slot trade hari ini habis (maks {MAX_TRADE_HARIAN})")
    if symbol in BIG_CAPS:
        add(False, f"{symbol} termasuk big cap yang tidak dianalisa")
    if expiry <= now:
        add(False, "Masa berlaku sudah lewat")
    if args.force and conflict:
        add(False, "Expiry lebih awal dari tutup candle pemicu (dipaksa --force)")

    warnings = [t for ok, t in checks if not ok]
    plan_id = next_id(journal, symbol, now)
    sig = min(10, max(6, sig_digits(str(args.entry_text)), sig_digits(str(args.stop_text))))
    p = lambda x: price(x, sig)  # noqa: E731

    spread_txt = ("spread asumsi 0,10% (belum ada data spread)" if c["spread_asumsi"]
                  else f"spread {idn(c['spread_pct'], 3)}%")
    checklist = (f"Scanner: {clean_cell(args.scanner) if args.scanner else '-'} · "
                 f"Risk-manager: stop {idn(c['jarak_stop_pct'], 2)}% → R:R bersih ~{idn(c['net_rr'], 2)} "
                 f"dengan break-even ilustratif {idn(c['biaya_pct'], 2)}% (fee 0,1%+0,1% + {spread_txt}; asumsi ilustratif); "
                 f"risiko ${idn(c['risiko_usdt'], 2)} {'≤' if c['risiko_usdt'] <= snap['sisa_budget'] + 1e-9 else '>'} "
                 f"sisa budget harian ${idn(snap['sisa_budget'], 2)}")
    if warnings:
        checklist += " · ⚠️ " + "; ".join(warnings)
        if args.lanjut:
            checklist += " · pelanggaran sadar"

    entry_kind = "market, sudah masuk" if args.entry_type == "market" else "limit"
    stop_note = f", {clean_cell(args.stop_note)}" if args.stop_note else ""
    cells = [
        plan_id, fmt_wib(now), f"{symbol}/USDT", clean_cell(args.venue), str(args.setup),
        f"${p(c['entry'])} ({entry_kind})",
        clean_cell(args.trigger),
        f"${p(c['stop'])} (-{idn(c['jarak_stop_pct'], 2)}%{stop_note})",
        f"${p(c['target'])} (+{idn(c['target_pct'], 2)}%, 2x jarak stop)",
        fmt_wib(expiry), checklist, f"${idn(c['risiko_usdt'], 2)}",
        f"{idn(c['ukuran'], 0 if c['ukuran'] >= 100 else 2)} {symbol}", "RENCANA",
    ]
    journal.add_trade_row(cells)
    journal.save()

    print(f"Rencana dicatat: {plan_id}  ({symbol}/USDT, setup {args.setup})")
    print(f"  Entry   ${p(c['entry'])}   Stop ${p(c['stop'])} (-{idn(c['jarak_stop_pct'], 2)}%)   "
          f"Target ${p(c['target'])} (+{idn(c['target_pct'], 2)}%)")
    print(f"  Risiko  ${idn(c['risiko_usdt'], 2)}   Ukuran {cells[12]}   Net R:R {idn(c['net_rr'], 2)}")
    print(f"  Biaya   {idn(c['biaya_pct'], 2)}% = fee 0,1% + 0,1% + {spread_txt}  [asumsi ilustratif]")
    print("Pemeriksaan:")
    for ok, text in checks:
        print(f"  {'✅' if ok else '⚠️'} {text}")
    if warnings and not args.lanjut:
        print("Ada peringatan. Rencana tetap dicatat (tool tidak memveto). Bila user memutuskan "
              "tetap lanjut, catat dengan --lanjut agar tertulis 'pelanggaran sadar'.")
    if warnings and args.lanjut:
        print("Dicatat dengan label 'pelanggaran sadar'.")
    print(f"Jurnal: {journal.path}")


def cmd_close(args):
    now = get_now(args)
    journal = Journal(args.journal)
    if journal.is_new:
        raise ToolError(f"jurnal {journal.path} belum ada; tidak ada ID yang bisa ditutup.")
    rows = journal.trade_rows()
    hit = next(((i, c) for i, c in rows if c[IDX_ID].strip().lower() == args.id.strip().lower()), None)
    if hit is None:
        raise ToolError(f"ID '{args.id}' tidak ada di jurnal. Jurnal tidak diubah. (Cek: trade.py status)")
    i, cells = hit
    status = cells[IDX_STATUS].strip().upper()
    if status in ("DITUTUP", "BATAL"):
        raise ToolError(f"{cells[IDX_ID]} sudah berstatus {status}; tidak ditutup dua kali. Jurnal tidak diubah.")
    entry, stop = parse_price(cells[IDX_ENTRY]), parse_price(cells[IDX_STOP])
    pair = cells[IDX_PAIR]
    symbol = pair.split("/")[0]
    sig = 8
    p = lambda x: price(x, sig)  # noqa: E731
    stamp = fmt_wib(now)
    alasan = clean_cell(args.alasan) if args.alasan else ""

    if args.batal:
        cells[IDX_STATUS] = "BATAL"
        journal.lines[i] = journal.row(cells)
        journal.add_bullet(f"- {cells[IDX_ID]}: **BATAL — dibatalkan, dilaporkan {stamp}.**"
                           + (f" Alasan: {alasan}." if alasan else ""))
        update_session_row(journal, now, f"{cells[IDX_ID]} batal" + (f" ({alasan})" if alasan else ""))
        journal.save()
        print(f"{cells[IDX_ID]} dibatalkan. Tidak ada P&L yang dihitung.")
        return

    if args.exit is None:
        raise ToolError("--exit wajib untuk close (atau pakai --batal).")
    if args.exit <= 0:
        raise ToolError("--exit harus > 0")
    r = calc_close(entry, stop, args.exit)
    if abs(args.exit - entry) / entry > 0.5:
        raise ToolError(f"harga exit {args.exit} berjarak > 50% dari entry {p(entry)}; tidak masuk akal. "
                        "Periksa input. Jurnal tidak diubah.")
    bersih = r["pnl_kotor"] - args.fee if args.fee is not None else None
    bersih_txt = (f"P&L bersih **{signed_usd(bersih)}** (fee ${idn(args.fee, 2)})" if bersih is not None
                  else "P&L bersih ❓ (fee belum diisi)")
    bullet = (f"- {cells[IDX_ID]}: **DITUTUP — close manual oleh user di ${p(args.exit)}, dilaporkan {stamp}.** "
              f"Entry ${p(entry)} → exit ${p(args.exit)}, ukuran {idn(r['ukuran'], 0 if r['ukuran'] >= 100 else 2)} {symbol}. "
              f"P&L kotor **{signed_usd(r['pnl_kotor'])} ({signed_pct(r['pnl_pct'])})**; {bersih_txt}. "
              f"Hasil (R) kotor **{'+' if r['hasil_r'] >= 0 else '-'}{idn(abs(r['hasil_r']), 2)}R**."
              + (f" Alasan: {alasan}." if alasan else "") + " Sesuai rencana? ❓ (isi manual)")
    cells[IDX_STATUS] = "DITUTUP"
    journal.lines[i] = journal.row(cells)
    journal.add_bullet(bullet)
    update_session_row(journal, now, f"{cells[IDX_ID]}: {alasan}" if alasan else "")
    journal.save()

    snap = snapshot(journal, now)
    print(f"{cells[IDX_ID]} ditutup di ${p(args.exit)}")
    print(f"  P&L kotor {signed_usd(r['pnl_kotor'])} ({signed_pct(r['pnl_pct'])})   Hasil {'+' if r['hasil_r'] >= 0 else '-'}{idn(abs(r['hasil_r']), 2)}R")
    print(f"  P&L bersih {signed_usd(bersih) if bersih is not None else '❓ (fee belum diisi)'}")
    print(f"  Sisa budget rugi hari ini ${idn(snap['sisa_budget'], 2)} · slot trade tersisa {snap['slot']}")
    if snap["rugi"] >= BUDGET_HARIAN - 1e-9:
        print("  ⚠️ Batas rugi harian tercapai. Berhenti trading hari ini.")


def cmd_status(args):
    now = get_now(args)
    journal = Journal(args.journal)
    snap = snapshot(journal, now)
    print(f"Status sesi — {fmt_wib(now)}")
    print(f"  Rencana hari ini : {snap['rencana_n']}")
    print(f"  Trade hari ini   : {snap['trade_n']} (maks {MAX_TRADE_HARIAN}) → slot tersisa {snap['slot']}")
    print(f"  P&L kotor hari ini: {signed_usd(snap['pnl_kotor']) if snap['reports'] else '$0,00'}")
    print(f"  Sisa budget rugi : ${idn(snap['sisa_budget'], 2)} dari ${idn(BUDGET_HARIAN, 2)}")
    live = []
    for _, c in snap["rows"]:
        if c[IDX_STATUS].strip().upper() not in ("RENCANA", "AKTIF"):
            continue
        try:
            exp = parse_wib(c[IDX_EXPIRY])
        except ToolError:
            exp = None
        if exp is None or exp > now:
            live.append((c, exp))
    print("  Rencana berlaku  :" + (" -" if not live else ""))
    for c, exp in live:
        print(f"    - {c[IDX_ID]} [{c[IDX_STATUS]}] {c[IDX_PAIR]} entry {c[IDX_ENTRY]} stop {c[IDX_STOP]} "
              f"sampai {fmt_wib(exp) if exp else '?'}")


# ----------------------------------------------------------------------- CLI

def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--journal", default=str(DEFAULT_JOURNAL), help="path trade-journal.md")
    common.add_argument("--now", help="(uji) waktu WIB 'YYYY-MM-DD HH:mm'")

    p = argparse.ArgumentParser(description="Pencatat jurnal trade (spot LONG, modal $44)")
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("plan", parents=[common], help="catat rencana trade")
    pl.add_argument("--pair", required=True)
    pl.add_argument("--entry", required=True, type=str)
    pl.add_argument("--stop", required=True, type=str)
    pl.add_argument("--setup", required=True, type=int, help="1, 2, atau 3")
    pl.add_argument("--trigger", required=True)
    pl.add_argument("--venue", default="bursa spot")
    pl.add_argument("--expiry", required=True, help="'YYYY-MM-DD HH:mm WIB'")
    pl.add_argument("--entry-type", choices=["market", "limit"], default="limit")
    pl.add_argument("--stop-note", help="mis. 'di bawah low candle 03:15 $0,03999'")
    pl.add_argument("--scanner", help="ringkasan hasil scan untuk kolom Checklist")
    pl.add_argument("--spread", type=float, help="spread aktual dalam persen (mis. 0.10)")
    pl.add_argument("--volume", type=float, help="volume 24j USDT")
    pl.add_argument("--user-suggested", action="store_true")
    pl.add_argument("--lanjut", action="store_true", help="user tetap lanjut meski ada peringatan")
    pl.add_argument("--force", action="store_true")
    pl.set_defaults(fn=cmd_plan)

    cl = sub.add_parser("close", parents=[common], help="tutup atau batalkan trade")
    cl.add_argument("--id", required=True)
    cl.add_argument("--exit", type=float)
    cl.add_argument("--fee", type=float, help="total fee USDT saat close")
    cl.add_argument("--alasan")
    cl.add_argument("--batal", action="store_true")
    cl.set_defaults(fn=cmd_close)

    st = sub.add_parser("status", parents=[common], help="tampilkan sesi hari ini")
    st.set_defaults(fn=cmd_status)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "plan":
            for name in ("entry", "stop"):
                raw = getattr(args, name)
                try:
                    val = float(raw)
                except ValueError:
                    raise ToolError(f"--{name} harus angka desimal dengan titik, bukan {raw!r}")
                setattr(args, f"{name}_text", raw)
                setattr(args, name, val)
        args.fn(args)
        return 0
    except ToolError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
