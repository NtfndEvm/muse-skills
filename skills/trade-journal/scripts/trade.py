#!/usr/bin/env python3
"""
trade.py — Pencatat jurnal trade spot. Semua angka dihitung KODE, bukan tangan.

Perintah:
  plan    catat rencana SEBELUM hasil diketahui (hitung target, net R:R, risiko, ukuran)
  close   tutup/batalkan trade, hitung P&L dan R, update baris Sesi
  status  tampilkan sesi hari ini (sisa budget rugi, slot trade, rencana aktif)
  aktif   (tambahan kecil) ubah status RENCANA -> AKTIF setelah entry benar-benar terisi
  init    buat jurnal dari template bila belum ada

Hanya standard library. Read-only terhadap pasar, tidak ada jaringan, tidak ada kredensial.
Menulis hanya ke trade-journal.md (dengan cadangan .bak sebelum menulis).
Peringatan TIDAK memveto; satu-satunya penolakan mentah: setup di luar 1/2/3, expiry sebelum candle
pemicu tutup (kecuali --force), data tidak masuk akal, dan ID yang tidak ada.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

WIB = timezone(timedelta(hours=7))

# ======================= PARAMETER USER (TETAP — jangan ubah tanpa persetujuan user) =======================
MODAL_USDT = 44.0          # full margin: 100% modal per trade
RR_GROSS = 2.0             # R:R kotor 1:2
FEE_EACH_PCT = 0.1         # fee taker ILUSTRATIF per sisi (belum terverifikasi) -> selalu diberi label
NET_RR_MIN = 1.5
DAILY_LOSS_LIMIT = 2.20    # 5% modal
MAX_TRADES_PER_DAY = 2
VOLUME_MIN_USDT = 100_000.0
MAX_STOP_PCT = 25.0        # di atas ini dianggap tidak masuk akal (perlu --force)
SETUPS = {1: "Breakout + volume", 2: "Pullback EMA 20/50 atau VWAP + bounce", 3: "Range scalping"}
# ===========================================================================================================

DEFAULT_JOURNAL = Path("~/workspace/trade-journal.md").expanduser()
TRADE_COLS = ["ID", "Tanggal-jam rencana (WIB)", "Pair", "Venue", "Setup", "Zona entry", "Pemicu", "Stop",
              "Target", "Berlaku sampai", "Checklist", "Risiko rencana (USDT)", "Ukuran rencana", "Status"]
SESI_COLS = ["Tanggal", "Rencana", "Trade", "P&L kotor", "P&L bersih", "Batas rugi tercapai?", "Catatan"]
TEMPLATE = """# Jurnal Trade

## Trade
| {t} |
|{ts}|

## Sesi
| {s} |
|{ss}|
""".format(t=" | ".join(TRADE_COLS), ts="|".join(["---"] * len(TRADE_COLS)),
           s=" | ".join(SESI_COLS), ss="|".join(["---"] * len(SESI_COLS)))


class ToolError(Exception):
    """Ambiguitas/kesalahan input: tool BERHENTI dan menjelaskan, tidak menebak."""


# ------------------------------------------------------------------ format angka
def id_num(x: float, dec: int) -> str:
    s = f"{abs(x):,.{dec}f}".replace(",", "\0").replace(".", ",").replace("\0", ".")
    return ("-" if x < 0 and float(f"{abs(x):.{dec}f}") != 0 else "") + s


def signed(x: float, dec: int, prefix: str = "", suffix: str = "") -> str:
    s = id_num(abs(x), dec)
    sign = "+" if x > 0 and float(f"{x:.{dec}f}") != 0 else "-" if x < 0 and float(f"{x:.{dec}f}") != 0 else ""
    return f"{sign}{prefix}{s}{suffix}"


def usd(x: float) -> str:
    return "$" + id_num(x, 2)


def parse_num(s: str, label: str = "angka") -> tuple[float, int]:
    """Parse angka dari CLI (titik desimal; koma diterima bila tidak ada titik). Return (nilai, jumlah desimal)."""
    t = str(s).strip().replace("$", "")
    if "," in t and "." not in t:
        t = t.replace(",", ".")
    if not re.fullmatch(r"\d+(\.\d+)?", t):
        raise ToolError(f"{label} tidak valid: {s!r} (pakai titik desimal, mis. 0.04072)")
    return float(t), (len(t.split(".")[1]) if "." in t else 0)


def parse_id_number(s: str) -> float:
    """Angka format Indonesia dari jurnal: '0,04072' / '1.080' / '1.234,56' -> float."""
    t = s.strip().replace("$", "")
    if re.fullmatch(r"\d{1,3}(\.\d{3})+(,\d+)?", t):
        t = t.replace(".", "").replace(",", ".")
    else:
        t = t.replace(",", ".")
    return float(t)


def fmt_px(x: float, dec: int) -> str:
    return id_num(x, max(dec, 2))


def fmt_size(x: float, sym: str) -> str:
    return f"{id_num(x, 0)} {sym}" if x >= 100 else f"{id_num(x, 4)} {sym}"


# --------------------------------------------------------------------- RUMUS (WAJIB persis spek §2.3)
def calc_plan(entry: float, stop: float, spread_pct: float | None = None, force: bool = False) -> dict[str, Any]:
    """LONG spot. target = entry + 2 × |entry − stop|. Semua persen dalam satuan persen."""
    if entry <= 0 or stop <= 0:
        raise ToolError("entry dan stop harus > 0")
    if stop >= entry:
        raise ToolError("stop harus DI BAWAH entry (tool ini hanya untuk LONG spot); periksa input")
    risk_abs = abs(entry - stop)
    jarak = risk_abs / entry
    if jarak * 100 > MAX_STOP_PCT and not force:
        raise ToolError(f"jarak stop {jarak * 100:.2f}% tidak masuk akal (> {MAX_STOP_PCT:.0f}%). "
                        "Periksa harga, atau pakai --force bila memang benar.")
    target = entry + RR_GROSS * risk_abs
    target_pct = (target - entry) / entry * 100
    spread_known = spread_pct is not None
    sp = spread_pct if spread_known else 0.1
    biaya = FEE_EACH_PCT + FEE_EACH_PCT + sp
    net = (target_pct - biaya) / (jarak * 100 + biaya)
    return {"entry": entry, "stop": stop, "jarak_stop": jarak, "jarak_stop_pct": jarak * 100,
            "target": target, "target_pct": target_pct, "spread_pct": sp, "spread_known": spread_known,
            "biaya_pct": biaya, "net_rr": net, "risiko_usdt": jarak * MODAL_USDT,
            "ukuran": MODAL_USDT / entry}


def net_rr_for_target(entry: float, stop: float, target: float, spread_pct: float | None = None) -> float:
    """Net R:R untuk target sembarang (dipakai scan.py untuk cek ruang ke resistance). Rumus sama dengan calc_plan."""
    sp = 0.1 if spread_pct is None else spread_pct
    biaya = 2 * FEE_EACH_PCT + sp
    jarak_pct = abs(entry - stop) / entry * 100
    target_pct = (target - entry) / entry * 100
    return (target_pct - biaya) / (jarak_pct + biaya)


def calc_close(entry: float, stop: float, exit_px: float) -> dict[str, float]:
    ukuran = MODAL_USDT / entry
    risiko = abs(entry - stop) / entry * MODAL_USDT
    pnl = (exit_px - entry) * ukuran
    return {"ukuran": ukuran, "risiko_usdt": risiko, "pnl_kotor": pnl, "pnl_pct": pnl / MODAL_USDT * 100,
            "hasil_r": pnl / risiko if risiko else 0.0}


# ------------------------------------------------------------------------------ jurnal (markdown)
SECTION_RE = re.compile(r"^##\s+(.*?)\s*$")
META_RE = re.compile(r"<!--\s*trade-meta\s+(.*?)\s*-->")
DT_RE = re.compile(r"(\d{4}-\d{2}-\d{2})\s+(\d{2}):(\d{2})")


def split_row(line: str) -> list[str]:
    s = line.strip()
    s = s[1:] if s.startswith("|") else s
    s = s[:-1] if s.endswith("|") else s
    return [c.strip() for c in s.split("|")]


def join_row(cells: list[str]) -> str:
    return "| " + " | ".join(c.replace("|", "/").replace("\n", " ") for c in cells) + " |"


def section_bounds(lines: list[str], title: str) -> tuple[int, int] | None:
    start = next((i for i, l in enumerate(lines) if (m := SECTION_RE.match(l)) and m.group(1).strip().lower() == title.lower()), None)
    if start is None:
        return None
    end = next((j for j in range(start + 1, len(lines)) if SECTION_RE.match(lines[j])), len(lines))
    return start, end


def table_bounds(lines: list[str], start: int, end: int) -> tuple[int, int, int] | None:
    hdr = next((i for i in range(start + 1, end) if lines[i].lstrip().startswith("|")), None)
    if hdr is None or hdr + 1 >= end:
        return None
    rows_end = hdr + 2
    while rows_end < end and lines[rows_end].lstrip().startswith("|"):
        rows_end += 1
    return hdr, hdr + 1, rows_end


class Journal:
    def __init__(self, path: Path):
        self.path = path
        if not path.exists():
            raise ToolError(f"jurnal tidak ditemukan: {path}. Buat dengan 'trade.py init' atau beri --journal.")
        self.lines = path.read_text(encoding="utf-8").split("\n")
        self._backed_up = False

    # --- akses tabel Trade
    def trade_table(self) -> tuple[list[str], list[tuple[int, list[str]]], int]:
        b = section_bounds(self.lines, "Trade")
        if not b:
            raise ToolError("bagian '## Trade' tidak ada di jurnal; hentikan dan periksa format jurnal")
        t = table_bounds(self.lines, *b)
        if not t:
            raise ToolError("tabel di bagian '## Trade' tidak ditemukan")
        hdr, sep, rows_end = t
        header = split_row(self.lines[hdr])
        for need in ("ID", "Status", "Pair", "Zona entry", "Stop", "Target"):
            if need not in header:
                raise ToolError(f"kolom '{need}' tidak ada di tabel Trade; format jurnal tidak dikenali")
        rows = [(i, split_row(self.lines[i])) for i in range(sep + 1, rows_end)]
        return header, rows, rows_end

    def rows_as_dicts(self) -> list[tuple[int, dict[str, str]]]:
        header, rows, _ = self.trade_table()
        out = []
        for i, cells in rows:
            cells = cells + [""] * (len(header) - len(cells))
            out.append((i, dict(zip(header, cells))))
        return out

    def bullets(self) -> list[str]:
        b = section_bounds(self.lines, "Trade")
        if not b:
            return []
        return [l for l in self.lines[b[0]:b[1]] if l.startswith("- ")]

    # --- tulis
    def backup_once(self) -> None:
        if not self._backed_up:
            shutil.copy2(self.path, str(self.path) + ".bak")
            self._backed_up = True

    def save(self) -> None:
        self.backup_once()
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text("\n".join(self.lines), encoding="utf-8")
        tmp.replace(self.path)

    def add_trade_row(self, values: dict[str, str]) -> None:
        header, _, rows_end = self.trade_table()
        self.lines.insert(rows_end, join_row([values.get(h, "—") for h in header]))

    def set_status(self, line_idx: int, status: str) -> None:
        header, _, _ = self.trade_table()
        cells = split_row(self.lines[line_idx])
        cells += [""] * (len(header) - len(cells))
        cells[header.index("Status")] = status
        self.lines[line_idx] = join_row(cells)

    def add_bullet(self, text: str) -> None:
        b = section_bounds(self.lines, "Trade")
        assert b
        _, _, rows_end = self.trade_table()
        last_bullet = max((i for i in range(rows_end, b[1]) if self.lines[i].startswith("- ")), default=None)
        if last_bullet is not None:
            self.lines.insert(last_bullet + 1, text)
        else:
            self.lines[rows_end:rows_end] = ["", text]

    # --- tabel Sesi
    def upsert_sesi(self, date_s: str, values: dict[str, str]) -> None:
        b = section_bounds(self.lines, "Sesi")
        if not b:
            if self.lines and self.lines[-1].strip():
                self.lines.append("")
            self.lines += ["## Sesi", "| " + " | ".join(SESI_COLS) + " |", "|" + "|".join(["---"] * len(SESI_COLS)) + "|"]
            b = section_bounds(self.lines, "Sesi")
        assert b
        t = table_bounds(self.lines, *b)
        if not t:
            raise ToolError("tabel di bagian '## Sesi' tidak ditemukan")
        hdr, sep, rows_end = t
        header = split_row(self.lines[hdr])
        for i in range(sep + 1, rows_end):
            cells = split_row(self.lines[i])
            if cells and cells[0] == date_s:
                cells += [""] * (len(header) - len(cells))
                old_note = cells[header.index("Catatan")] if "Catatan" in header else ""
                merged = dict(values)
                if values.get("Catatan"):
                    merged["Catatan"] = "; ".join(x for x in [old_note.strip("—").strip(), values["Catatan"]] if x)
                else:
                    merged["Catatan"] = old_note
                for k, v in merged.items():
                    if k in header:
                        cells[header.index(k)] = v
                self.lines[i] = join_row(cells)
                return
        self.lines.insert(rows_end, join_row([values.get(h, "—") if h != "Tanggal" else date_s for h in header]))


# --------------------------------------------------------------------- state sesi (dibaca dari jurnal)
def plan_date_of(trade_id: str) -> str | None:
    m = re.search(r"-(\d{4})(\d{2})(\d{2})-\d+$", trade_id)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def closed_records(j: Journal) -> list[dict[str, Any]]:
    recs = []
    for b in j.bullets():
        idm = re.match(r"-\s+([A-Z0-9]+-\d{8}-\d+):", b)
        if not idm or "DITUTUP" not in b:
            continue
        meta = META_RE.search(b)
        if meta:
            kv = dict(p.split("=", 1) for p in meta.group(1).split() if "=" in p)
            recs.append({"id": idm.group(1), "date": kv.get("closed", ""), "gross": float(kv["gross"]),
                         "fee": None if kv.get("fee", "na") == "na" else float(kv["fee"])})
            continue
        g = re.search(r"P&L kotor[^*\n]*\*\*([+\-−])\s*\$?([\d.,]+)", b)  # bullet lama tanpa meta
        d = re.search(r"dilaporkan\s+(\d{4}-\d{2}-\d{2})", b)
        if g and d:
            val = parse_id_number(g.group(2))
            recs.append({"id": idm.group(1), "date": d.group(1), "gross": -val if g.group(1) in "-−" else val, "fee": None})
    return recs


def session_state(j: Journal, now: datetime) -> dict[str, Any]:
    today = now.strftime("%Y-%m-%d")
    rows = j.rows_as_dicts()
    todays = [(i, r) for i, r in rows if plan_date_of(r["ID"]) == today]
    traded = [r for _, r in todays if r["Status"].strip() in ("AKTIF", "DITUTUP")]
    recs = [r for r in closed_records(j) if r["date"] == today]
    loss = sum(-r["gross"] for r in recs if r["gross"] < 0)
    gross_total = sum(r["gross"] for r in recs)
    fees_known = recs and all(r["fee"] is not None for r in recs)
    net_total = gross_total - sum(r["fee"] for r in recs if r["fee"] is not None) if fees_known else None
    return {"today": today, "plans": len(todays), "trades": len(traded), "gross_total": gross_total,
            "net_total": net_total, "loss_total": loss, "budget_left": max(0.0, DAILY_LOSS_LIMIT - loss),
            "slots_left": max(0, MAX_TRADES_PER_DAY - len(traded)), "closed_today": recs}


def parse_expiry(s: str) -> datetime:
    m = re.fullmatch(r"\s*(\d{4})-(\d{2})-(\d{2})\s+(\d{1,2}):(\d{2})\s*(WIB)?\s*", s or "")
    if not m:
        raise ToolError("format --expiry harus 'YYYY-MM-DD HH:mm WIB'")
    try:
        return datetime(int(m[1]), int(m[2]), int(m[3]), int(m[4]), int(m[5]), tzinfo=WIB)
    except ValueError:
        raise ToolError("tanggal/jam --expiry tidak valid") from None


def trigger_candle_close(trigger: str, now: datetime) -> datetime | None:
    """'candle 17:15 tutup' -> waktu tutup = 17:15 + 15 menit (candle dilabeli waktu BUKA)."""
    m = re.search(r"candle\s+(\d{1,2}):(\d{2})", trigger, re.I)
    if not m:
        return None
    cand = now.replace(hour=int(m[1]), minute=int(m[2]), second=0, microsecond=0)
    if cand > now + timedelta(hours=12):
        cand -= timedelta(days=1)
    elif cand < now - timedelta(hours=12):
        cand += timedelta(days=1)
    return cand + timedelta(minutes=15)


def now_wib() -> datetime:
    return datetime.now(WIB)


# ------------------------------------------------------------------------------------ perintah plan
def validate_pair(p: str) -> str:
    sym = p.strip().upper()
    sym = sym[:-4] if sym.endswith("USDT") and len(sym) > 4 else sym
    sym = sym.replace("/", "")
    if not re.fullmatch(r"[A-Z0-9]{2,15}", sym):
        raise ToolError(f"pair tidak jelas: {p!r}")
    return sym


def cmd_plan(a: argparse.Namespace, now: datetime) -> int:
    if a.setup not in SETUPS:
        raise ToolError(f"--setup hanya menerima 1, 2, atau 3 ({'; '.join(f'{k}={v}' for k, v in SETUPS.items())}). "
                        f"Nilai {a.setup} ditolak; jurnal tidak diubah.")
    sym = validate_pair(a.pair)
    entry, e_dec = parse_num(a.entry, "entry")
    stop, s_dec = parse_num(a.stop, "stop")
    spread = parse_num(a.spread, "spread")[0] if a.spread is not None else None
    plan = calc_plan(entry, stop, spread, force=a.force)
    dec = max(e_dec, s_dec)

    expiry = parse_expiry(a.expiry)
    problems = []
    if expiry <= now:
        problems.append("expiry sudah lewat")
    close_t = trigger_candle_close(a.trigger, now)
    if close_t and expiry <= close_t:
        problems.append(f"expiry {expiry:%H:%M} tidak sesudah waktu tutup candle pemicu ({close_t:%H:%M} WIB)")
    if problems and not a.force:
        raise ToolError("⚠️ " + "; ".join(problems) + ". Ditolak (gunakan --force bila memang disengaja); jurnal tidak diubah.")

    j = Journal(Path(a.journal))
    st = session_state(j, now)

    checks: list[tuple[bool, str]] = []
    be = plan["biaya_pct"]
    checks.append((plan["net_rr"] >= NET_RR_MIN,
                   f"Net R:R {id_num(plan['net_rr'], 2)} " + ("≥" if plan["net_rr"] >= NET_RR_MIN else "<") +
                   f" batas {id_num(NET_RR_MIN, 1)}" + ("" if plan["net_rr"] >= NET_RR_MIN else " — R:R bersih di bawah batas 1,5")))
    ok_budget = plan["risiko_usdt"] <= st["budget_left"] + 1e-9
    checks.append((ok_budget, f"Risiko {usd(plan['risiko_usdt'])} " + ("≤" if ok_budget else ">") +
                   f" sisa budget harian {usd(st['budget_left'])}" + ("" if ok_budget else " — Risiko melebihi sisa budget")))
    if a.volume is not None:
        vol = parse_num(a.volume, "volume")[0]
        if vol >= VOLUME_MIN_USDT:
            checks.append((True, f"Volume 24j {usd(vol)} ≥ {usd(VOLUME_MIN_USDT)}"))
        elif a.user_suggested:
            checks.append((True, f"Volume 24j {usd(vol)} < {usd(VOLUME_MIN_USDT)} — LOLOS BERSYARAT (disarankan user)"))
        else:
            checks.append((False, f"Volume 24j {usd(vol)} < {usd(VOLUME_MIN_USDT)} — di bawah minimum"))
    unconfirmed = bool(re.search(r"belum[^.;,]*konfirmasi", a.trigger, re.I))
    checks.append((not unconfirmed, "Pemicu terkonfirmasi" if not unconfirmed else
                   "Pemicu menyebut konfirmasi BELUM terjadi — dicatat apa adanya (keputusan di user)"))
    slot_ok = st["trades"] < MAX_TRADES_PER_DAY
    checks.append((slot_ok, f"Trade hari ini {st['trades']}/{MAX_TRADES_PER_DAY}" +
                   ("" if slot_ok else " — slot trade harian habis")))
    warn = [t for ok, t in checks if not ok]

    # ID otomatis
    date_part = now.strftime("%Y%m%d")
    prefix = f"{sym}-{date_part}-"
    n = 1 + sum(1 for _, r in j.rows_as_dicts() if r["ID"].startswith(prefix))
    trade_id = f"{prefix}{n:02d}"

    sp_label = "aktual" if plan["spread_known"] else "PLACEHOLDER (spread tidak diberikan)"
    checklist = (f"Scanner: {a.scanner or '—'} · Risk-manager: stop {id_num(plan['jarak_stop_pct'], 2)}% → R:R bersih "
                 f"~{id_num(plan['net_rr'], 2)} dengan break-even ilustratif {id_num(be, 2)}% (fee 0,1%+0,1% asumsi ilustratif + "
                 f"spread {id_num(plan['spread_pct'], 2)}% {sp_label}); risiko {usd(plan['risiko_usdt'])} "
                 f"{'≤' if ok_budget else '>'} budget harian {usd(st['budget_left'])}")
    if warn:
        checklist += " · ⚠️ " + " | ".join(w.replace("|", "/") for w in warn)
        if a.lanjut:
            checklist += " · pelanggaran sadar"
    order = "market" if a.tipe == "market" else "limit"
    zona = f"${fmt_px(entry, e_dec)} ({order}{', sudah masuk' if a.sudah_masuk else ''})"
    stop_txt = f"${fmt_px(stop, s_dec)} (-{id_num(plan['jarak_stop_pct'], 2)}%" + (f", {a.stop_ket}" if a.stop_ket else "") + ")"
    target_txt = f"${fmt_px(plan['target'], dec)} (+{id_num(plan['target_pct'], 2)}%, {id_num(RR_GROSS, 0)}x jarak stop)"
    values = {"ID": trade_id, "Tanggal-jam rencana (WIB)": now.strftime("%Y-%m-%d %H:%M"), "Pair": f"{sym}/USDT",
              "Venue": a.venue, "Setup": f"{a.setup} ({SETUPS[a.setup]})", "Zona entry": zona, "Pemicu": a.trigger,
              "Stop": stop_txt, "Target": target_txt, "Berlaku sampai": expiry.strftime("%Y-%m-%d %H:%M") + " WIB",
              "Checklist": checklist, "Risiko rencana (USDT)": usd(plan["risiko_usdt"]),
              "Ukuran rencana": "≈" + fmt_size(plan["ukuran"], sym), "Status": "RENCANA"}
    j.add_trade_row(values)
    j.save()

    print(f"Rencana tercatat: {trade_id}")
    print(f"Entry ${fmt_px(entry, e_dec)} · Stop ${fmt_px(stop, s_dec)} "
          f"(-{id_num(plan['jarak_stop_pct'], 2)}%) · Target ${fmt_px(plan['target'], dec)} (+{id_num(plan['target_pct'], 2)}%)")
    print(f"Risiko {usd(plan['risiko_usdt'])} · Ukuran {fmt_size(plan['ukuran'], sym)} · "
          f"Net R:R {id_num(plan['net_rr'], 2)} (biaya {id_num(be, 2)}%: fee 0,1% + 0,1% asumsi ilustratif + spread "
          f"{id_num(plan['spread_pct'], 2)}% {sp_label})")
    print("Checklist:")
    for ok, t in checks:
        print(f"  {'✅' if ok else '⚠️'} {t}")
    if warn and not a.lanjut:
        print("Ada peringatan. Dicatat apa adanya; bila kamu tetap lanjut, tandai dengan --lanjut (label 'pelanggaran sadar').")
    if warn and a.lanjut:
        print("Dicatat dengan label 'pelanggaran sadar'.")
    print("Catatan: perhitungan dari input; bukan sinyal dan bukan nasihat keuangan.")
    return 0


# ----------------------------------------------------------------------------------- perintah close
def find_row(j: Journal, trade_id: str) -> tuple[int, dict[str, str]]:
    for i, r in j.rows_as_dicts():
        if r["ID"] == trade_id:
            return i, r
    raise ToolError(f"ID tidak ditemukan: {trade_id}. Jurnal tidak diubah.")


def cell_decimals(cell: str) -> int:
    m = re.search(r"\$\s*[\d.]*,(\d+)", cell)
    return len(m.group(1)) if m else 0


def first_price(cell: str, label: str) -> float:
    m = re.search(r"\$\s*([\d.,]+)", cell)
    if not m:
        raise ToolError(f"tidak bisa membaca harga {label} dari jurnal: {cell!r}")
    return parse_id_number(m.group(1))


def cmd_close(a: argparse.Namespace, now: datetime) -> int:
    j = Journal(Path(a.journal))
    idx, row = find_row(j, a.id)
    status = row["Status"].strip()
    if status in ("DITUTUP", "BATAL"):
        raise ToolError(f"{a.id} sudah berstatus {status}; tidak diubah lagi.")
    reported = now.strftime("%Y-%m-%d %H:%M")
    sym = row["Pair"].split("/")[0]

    if a.batal:
        j.set_status(idx, "BATAL")
        alasan = f" Alasan: {a.alasan}." if a.alasan else ""
        j.add_bullet(f"- {a.id}: **BATAL — tidak jadi dieksekusi, dilaporkan {reported} WIB.**{alasan}")
        note = f"{a.id} batal" + (f" ({a.alasan})" if a.alasan else "")
        _update_sesi(j, now, note)
        j.save()
        print(f"{a.id} ditandai BATAL (tanpa P&L).")
        return 0

    if a.exit is None:
        raise ToolError("--exit wajib untuk close (atau pakai --batal)")
    exit_px, x_dec = parse_num(a.exit, "exit")
    entry = first_price(row["Zona entry"], "entry")
    stop = first_price(row["Stop"], "stop")
    c = calc_close(entry, stop, exit_px)
    x_dec = max(x_dec, cell_decimals(row["Zona entry"]), cell_decimals(row["Stop"]))
    fee = parse_num(a.fee, "fee")[0] if a.fee is not None else None
    net = c["pnl_kotor"] - fee if fee is not None else None

    sesuai = {"ya": "Ya", "tidak": "Tidak"}.get(a.sesuai or "", "❓ (belum dinilai)")
    if a.alasan:
        sesuai += f" — {a.alasan}"
    meta = (f"<!-- trade-meta id={a.id} closed={now.strftime('%Y-%m-%d')} gross={c['pnl_kotor']:.6f} "
            f"fee={'na' if fee is None else f'{fee:.6f}'} r={c['hasil_r']:.4f} -->")
    bullet = (f"- {a.id}: **DITUTUP — close manual oleh user di ${fmt_px(exit_px, x_dec)}, dilaporkan {reported} WIB.** "
              f"Entry ${fmt_px(entry, x_dec)} → exit ${fmt_px(exit_px, x_dec)}; ukuran {fmt_size(c['ukuran'], sym)}. "
              f"P&L kotor **{signed(c['pnl_kotor'], 2, '$')} ({signed(c['pnl_pct'], 2, '', '%')})**; "
              f"fee {usd(fee) if fee is not None else '❓'}; P&L bersih "
              f"{signed(net, 2, '$') if net is not None else '❓'}. "
              f"Hasil (R) kotor **{signed(c['hasil_r'], 2, '', 'R')}**. Sesuai rencana? {sesuai}. {meta}")
    j.set_status(idx, "DITUTUP")
    j.add_bullet(bullet)
    _update_sesi(j, now, f"{a.id}: {a.alasan}" if a.alasan else "")
    j.save()

    print(f"{a.id} DITUTUP di ${fmt_px(exit_px, x_dec)}")
    print(f"P&L kotor {signed(c['pnl_kotor'], 2, '$')} ({signed(c['pnl_pct'], 2, '', '%')}) · Hasil {signed(c['hasil_r'], 2, '', 'R')} (kotor)")
    print(f"Fee {usd(fee) if fee is not None else '❓ belum diisi'} · P&L bersih "
          f"{signed(net, 2, '$') if net is not None else '❓'}")
    st = session_state(j, now)
    print(f"Sisa budget rugi hari ini {usd(st['budget_left'])} · slot trade tersisa {st['slots_left']}")
    return 0


def _update_sesi(j: Journal, now: datetime, note: str) -> None:
    st = session_state(j, now)
    gross = st["gross_total"]
    values = {
        "Rencana": str(st["plans"]), "Trade": str(st["trades"]),
        "P&L kotor": signed(gross, 2, "$") if abs(gross) >= 0.005 else "$0,00",
        "P&L bersih": (signed(st["net_total"], 2, "$") if abs(st["net_total"]) >= 0.005 else "$0,00")
        if st["net_total"] is not None else "❓",
        "Batas rugi tercapai?": "Ya" if st["loss_total"] >= DAILY_LOSS_LIMIT - 1e-9 else "Tidak",
        "Catatan": note,
    }
    j.upsert_sesi(st["today"], values)


# ---------------------------------------------------------------------------------- status & aktif
def parse_dt(s: str) -> datetime | None:
    m = DT_RE.search(s or "")
    return datetime(int(m[1][:4]), int(m[1][5:7]), int(m[1][8:10]), int(m[2]), int(m[3]), tzinfo=WIB) if m else None


def cmd_status(a: argparse.Namespace, now: datetime) -> int:
    j = Journal(Path(a.journal))
    st = session_state(j, now)
    print(f"## Status Sesi — {st['today']} ({now:%H:%M} WIB)")
    print(f"Rencana hari ini: {st['plans']} · Trade: {st['trades']}/{MAX_TRADES_PER_DAY} · slot tersisa: {st['slots_left']}")
    print(f"P&L kotor hari ini: {signed(st['gross_total'], 2, '$') if abs(st['gross_total']) >= 0.005 else '$0,00'} · "
          f"total rugi kotor: {usd(st['loss_total'])}")
    print(f"Sisa budget rugi: {usd(st['budget_left'])} (batas {usd(DAILY_LOSS_LIMIT)})")
    live, expired = [], []
    for _, r in j.rows_as_dicts():
        s = r["Status"].strip()
        if s not in ("RENCANA", "AKTIF"):
            continue
        exp = parse_dt(r.get("Berlaku sampai", ""))
        (expired if exp and exp <= now else live).append((r, exp))
    print("Rencana RENCANA/AKTIF yang belum kedaluwarsa:" + ("" if live else " tidak ada"))
    for r, exp in live:
        until = f" | berlaku s.d. {exp:%Y-%m-%d %H:%M} WIB" if exp else ""
        print(f"  - {r['ID']} [{r['Status']}] {r['Zona entry']} | {r['Stop']} | {r['Target']}{until}")
    if expired:
        print("Kedaluwarsa tapi belum ditutup/dibatalkan: " + ", ".join(r["ID"] + f" [{r['Status']}]" for r, _ in expired))
    return 0


def cmd_aktif(a: argparse.Namespace, now: datetime) -> int:
    j = Journal(Path(a.journal))
    idx, row = find_row(j, a.id)
    if row["Status"].strip() != "RENCANA":
        raise ToolError(f"{a.id} berstatus {row['Status'].strip()}, bukan RENCANA")
    j.set_status(idx, "AKTIF")
    j.save()
    print(f"{a.id} → AKTIF")
    return 0


def cmd_init(a: argparse.Namespace, now: datetime) -> int:
    p = Path(a.journal)
    if p.exists():
        raise ToolError(f"{p} sudah ada; tidak ditimpa")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(TEMPLATE, encoding="utf-8")
    print(f"Jurnal dibuat: {p}")
    return 0


# ------------------------------------------------------------------------------------------- CLI
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Pencatat jurnal trade spot (semua angka dihitung kode)")
    ap.add_argument("--journal", default=str(DEFAULT_JOURNAL), help="path trade-journal.md")
    ap.add_argument("--now", help="(uji) waktu acuan 'YYYY-MM-DD HH:mm' WIB")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("plan", help="catat rencana")
    p.add_argument("--pair", required=True)
    p.add_argument("--entry", required=True)
    p.add_argument("--stop", required=True)
    p.add_argument("--setup", required=True, type=int)
    p.add_argument("--trigger", required=True)
    p.add_argument("--expiry", required=True, help="'YYYY-MM-DD HH:mm WIB'")
    p.add_argument("--venue", default="bursa spot")
    p.add_argument("--spread", help="spread aktual dalam persen (mis. 0.136); kosong = placeholder 0,1 persen")
    p.add_argument("--volume", help="volume 24j USDT (untuk cek minimum)")
    p.add_argument("--user-suggested", action="store_true", help="pair disarankan user (volume jadi LOLOS BERSYARAT)")
    p.add_argument("--tipe", choices=["market", "limit"], default="limit")
    p.add_argument("--sudah-masuk", action="store_true")
    p.add_argument("--stop-ket", help="keterangan stop, mis. 'di bawah low candle 03:15 $0,03999'")
    p.add_argument("--scanner", help="ringkasan hasil scanner untuk kolom Checklist")
    p.add_argument("--lanjut", action="store_true", help="user tetap lanjut meski ada peringatan (label pelanggaran sadar)")
    p.add_argument("--force", action="store_true")

    c = sub.add_parser("close", help="tutup/batalkan trade")
    c.add_argument("--id", required=True)
    c.add_argument("--exit")
    c.add_argument("--fee", help="total fee USDT saat close; kosong = ❓")
    c.add_argument("--alasan")
    c.add_argument("--sesuai", choices=["ya", "tidak"], help="sesuai rencana?")
    c.add_argument("--batal", action="store_true")

    sub.add_parser("status", help="status sesi hari ini")
    k = sub.add_parser("aktif", help="RENCANA -> AKTIF")
    k.add_argument("--id", required=True)
    sub.add_parser("init", help="buat jurnal dari template")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    now = now_wib()
    if a.now:
        try:
            now = datetime.strptime(a.now, "%Y-%m-%d %H:%M").replace(tzinfo=WIB)
        except ValueError:
            print("Error: --now harus 'YYYY-MM-DD HH:mm'", file=sys.stderr)
            return 2
    try:
        return {"plan": cmd_plan, "close": cmd_close, "status": cmd_status, "aktif": cmd_aktif, "init": cmd_init}[a.cmd](a, now)
    except ToolError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
