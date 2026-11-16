#!/usr/bin/env python3
"""pre_entry_check.py — cek aturan disiplin dari entry/stop/target AKTUAL, sebelum masuk.

Latar: evaluasi-diri 17 — 3 dari 4 trade masuk tanpa konfirmasi, 2 kalah penuh
-1,00R. Aturannya sudah benar, yang kurang kepatuhannya. Skrip ini menegakkan
aturan yang sudah ada (bukan aturan baru, bukan perubahan dari sampel kecil):
konfirmasi, volume spike, ruang ke resistance, extension dari VWAP, target
profit user, budget untuk stop berbasis ATR, dan R:R bersih.

Skrip ini HANYA MENANDAI — tidak menolak, tidak memveto, tidak mengunci
keputusan user (prinsip "Tanpa Veto" entry-assistant; pelajaran UAI di
evaluasi-diri 1). Exit code selalu 0 bila input valid, berapa pun pelanggaran
yang ditemukan; keputusan tetap di user, pelanggaran dicatat di jurnal
sebagai "pelanggaran sadar" bila user tetap lanjut.

Rumus (ditulis di output, evaluasi-diri 8 — hitung ulang dari entry aktual,
jangan pernah membawa target dari skenario entry lain):
    jarak stop  = entry - stop
    target      = entry + 2 x jarak stop
    R:R bersih  = (target% - biaya%) / (jarak stop% + biaya%),
                  biaya% = fee 0,1% + 0,1% + spread (asumsi ilustratif)

Parameter user (tetap, jangan diubah tanpa persetujuan user):
  modal $44, posisi penuh; batas rugi harian $2,20; R:R bersih minimum 1,5;
  target profit user 5% per trade; volume spike >= 1,5x rata-rata 20 candle;
  ruang ke resistance minimum 4%; extension > 3 ATR di atas VWAP = lampu merah.

Hanya library standar Python (3.8+). Tidak mengeksekusi order, tidak memakai key.

  python pre_entry_check.py --pair UAI --entry 0.04072 --stop 0.0399 --target 0.04236 \\
      --confirmed --volume-ratio 2.1 --resistance 0.045 --vwap 0.040 --atr 0.0004
  python pre_entry_check.py --pair UAI --entry 0.04072 --stop 0.0399
"""
from __future__ import annotations

import argparse
import json
import sys

# Parameter user (TETAP, jangan diubah tanpa persetujuan user)
MODAL = 44.0
BUDGET_HARIAN = 2.20
MIN_NET_RR = 1.5
TARGET_PROFIT_PCT = 5.0   # target profit user per trade (evaluasi-diri 14, 21)
VOL_SPIKE = 1.5           # rasio volume candle pemicu vs rata-rata 20 candle
ROOM_MIN_PCT = 4.0        # ruang ke resistance terdekat minimum (aturan scan.py)
VWAP_EXT_ATR = 3.0        # extension di atas VWAP > ini = lampu merah (evaluasi-diri 21)
FEE_PCT = 0.1             # per sisi, asumsi ilustratif (fee bursa belum terverifikasi)
ATR_STOP_MULT = 1.0       # stop berbasis ATR: 1 x ATR di bawah entry


class CheckError(Exception):
    """Input tidak valid; tidak ada cek yang dijalankan."""


def check(entry, stop, target=None, confirmed=False, confirmation="",
          volume_ratio=None, resistance=None, vwap=None, atr=None,
          budget=BUDGET_HARIAN, capital=MODAL, spread_pct=0.1,
          atr_mult=ATR_STOP_MULT):
    """Cek entry/stop/target aktual terhadap aturan disiplin. Kembalikan dict hasil.

    `target` boleh None: dipakai target-aturan (entry + 2 x jarak stop) dan
    ditandai sebagai turunan rumus, bukan target yang user isi.
    Cek yang datanya tidak diberi (volume_ratio/resistance/vwap/atr) dilaporkan
    sebagai TIDAK_ADA_DATA — bukan lolos diam-diam, bukan pelanggaran.
    """
    if not (entry > 0 and stop > 0):
        raise CheckError("entry dan stop harus > 0")
    if stop >= entry:
        raise CheckError("stop harus di bawah entry (skrip ini untuk spot LONG)")
    if target is not None and target <= 0:
        raise CheckError("target harus > 0")
    if budget < 0 or capital <= 0:
        raise CheckError("budget harus >= 0 dan modal harus > 0")

    dist = entry - stop
    jarak_stop_pct = dist / entry * 100
    target_rule = entry + 2 * dist          # target = entry + 2 x jarak stop
    target_rule_pct = (target_rule - entry) / entry * 100
    target_given = target is not None
    target_used = target if target_given else target_rule
    target_pct = (target_used - entry) / entry * 100
    biaya_pct = FEE_PCT + FEE_PCT + spread_pct
    # R:R bersih dihitung ulang dari entry AKTUAL dan target-aturan (bukan dari
    # target skenario lain); R:R aktual dari target yang user isi juga dilaporkan.
    net_rr_rule = (target_rule_pct - biaya_pct) / (jarak_stop_pct + biaya_pct)
    net_rr_actual = (target_pct - biaya_pct) / (jarak_stop_pct + biaya_pct)
    risiko = dist / entry * capital         # posisi penuh: risiko = jarak stop% x modal
    stop_atr = dist / atr if atr else None
    risiko_atr = atr_mult * atr / entry * capital if atr else None

    checks = []

    def add(code, label, status, detail):
        checks.append({"code": code, "label": label, "status": status, "detail": detail})

    # 1. Konfirmasi (evaluasi-diri 17: entry sebelum konfirmasi, 3 dari 4 trade)
    if confirmed:
        add("KONFIRMASI", "Konfirmasi", "OK",
            f"ada konfirmasi{': ' + confirmation if confirmation else ''}")
    else:
        add("KONFIRMASI", "Konfirmasi", "PELANGGARAN",
            "belum ada konfirmasi — breakout/bounce belum terkonfirmasi tutup candle")

    # 2. Volume spike (syarat setup breakout: tutup di atas resistance + volume spike)
    if volume_ratio is None:
        add("VOLUME_SPIKE", "Volume spike", "TIDAK_ADA_DATA",
            "rasio volume tidak diisi (--volume-ratio)")
    elif volume_ratio >= VOL_SPIKE:
        add("VOLUME_SPIKE", "Volume spike", "OK",
            f"rasio volume {volume_ratio:.2f}x >= {VOL_SPIKE:.1f}x")
    else:
        add("VOLUME_SPIKE", "Volume spike", "PELANGGARAN",
            f"rasio volume {volume_ratio:.2f}x < {VOL_SPIKE:.1f}x — bukan spike")

    # 3. Ruang ke resistance (aturan scan: minimum 4%)
    if resistance is None:
        add("RUANG_RESISTANCE", "Ruang ke resistance", "TIDAK_ADA_DATA",
            "resistance terdekat tidak diisi (--resistance)")
    else:
        room_pct = (resistance / entry - 1) * 100
        if room_pct >= ROOM_MIN_PCT:
            add("RUANG_RESISTANCE", "Ruang ke resistance", "OK",
                f"resistance {resistance:.6g} (+{room_pct:.2f}%) >= {ROOM_MIN_PCT:.0f}%")
        else:
            add("RUANG_RESISTANCE", "Ruang ke resistance", "PELANGGARAN",
                f"resistance {resistance:.6g} cuma +{room_pct:.2f}% < {ROOM_MIN_PCT:.0f}% — ruang naik sempit")

    # 4. Extension dari VWAP (evaluasi-diri 21: > 3 ATR di atas VWAP = lampu merah)
    if vwap is None or atr is None:
        add("EXTENSION_VWAP", "Extension dari VWAP", "TIDAK_ADA_DATA",
            "VWAP/ATR tidak diisi (--vwap --atr)")
    else:
        jarak_atr = (entry - vwap) / atr
        if jarak_atr > VWAP_EXT_ATR:
            add("EXTENSION_VWAP", "Extension dari VWAP", "PELANGGARAN",
                f"entry {jarak_atr:.1f} ATR di atas VWAP (> {VWAP_EXT_ATR:.0f} ATR) — lampu merah, rawan pullback")
        else:
            add("EXTENSION_VWAP", "Extension dari VWAP", "OK",
                f"entry {jarak_atr:.1f} ATR dari VWAP (<= {VWAP_EXT_ATR:.0f} ATR)")

    # 5. Target >= target profit user 5% (evaluasi-diri 14, 21)
    if target_pct >= TARGET_PROFIT_PCT:
        add("TARGET_PROFIT", "Target vs target profit user", "OK",
            f"target +{target_pct:.2f}% >= {TARGET_PROFIT_PCT:.0f}%")
    else:
        add("TARGET_PROFIT", "Target vs target profit user", "PELANGGARAN",
            f"target +{target_pct:.2f}% < target profit user {TARGET_PROFIT_PCT:.0f}% — "
            "rencana tidak memenuhi target profitnya sendiri")

    # 6. R:R bersih (dari target-aturan yang dihitung ulang dari entry aktual)
    if net_rr_rule >= MIN_NET_RR:
        add("RR_BERSIH", "R:R bersih", "OK",
            f"net R:R {net_rr_rule:.2f} >= {MIN_NET_RR:.1f}")
    else:
        add("RR_BERSIH", "R:R bersih", "PELANGGARAN",
            f"net R:R {net_rr_rule:.2f} < {MIN_NET_RR:.1f}")

    # 7. Budget cukup untuk stop aktual (risiko = jarak stop% x modal $44)
    if risiko <= budget:
        add("BUDGET_STOP", "Budget untuk stop aktual", "OK",
            f"risiko ${risiko:.2f} <= sisa budget ${budget:.2f}")
    else:
        add("BUDGET_STOP", "Budget untuk stop aktual", "PELANGGARAN",
            f"risiko ${risiko:.2f} > sisa budget ${budget:.2f}")

    # 8. Budget cukup untuk stop berbasis ATR (1 x ATR di bawah entry)
    if atr is None:
        add("BUDGET_STOP_ATR", "Budget untuk stop 1x ATR", "TIDAK_ADA_DATA",
            "ATR tidak diisi (--atr)")
    elif risiko_atr <= budget:
        add("BUDGET_STOP_ATR", "Budget untuk stop 1x ATR", "OK",
            f"risiko stop 1x ATR ${risiko_atr:.2f} <= sisa budget ${budget:.2f}")
    else:
        add("BUDGET_STOP_ATR", "Budget untuk stop 1x ATR", "PELANGGARAN",
            f"risiko stop 1x ATR ${risiko_atr:.2f} > sisa budget ${budget:.2f} — "
            "sisa budget tidak cukup untuk stop berbasis ATR")

    violations = [c for c in checks if c["status"] == "PELANGGARAN"]
    unknown = [c for c in checks if c["status"] == "TIDAK_ADA_DATA"]
    return {
        "entry": entry, "stop": stop,
        "target": target_used, "target_diberi_user": target_given,
        "target_rule": target_rule,
        "jarak_stop_pct": jarak_stop_pct, "target_pct": target_pct,
        "target_rule_pct": target_rule_pct,
        "biaya_pct": biaya_pct, "net_rr_rule": net_rr_rule,
        "net_rr_actual": net_rr_actual,
        "risiko_usdt": risiko, "risiko_atr_usdt": risiko_atr,
        "stop_jarak_atr": stop_atr,
        "checks": checks, "violations": violations,
        "n_pelanggaran": len(violations), "n_tidak_ada_data": len(unknown),
    }


def to_text(r):
    L = [f"Pre-entry check — entry {r['entry']:.6g} · stop {r['stop']:.6g} "
         f"(-{r['jarak_stop_pct']:.2f}%) · target {r['target']:.6g} (+{r['target_pct']:.2f}%)"
         + ("" if r["target_diberi_user"] else " (target dari rumus, bukan diisi user)"),
         "Rumus: target = entry + 2 x jarak stop = "
         f"{r['entry']:.6g} + 2 x {r['entry'] - r['stop']:.6g} = {r['target_rule']:.6g} "
         f"(+{r['target_rule_pct']:.2f}%); R:R bersih = "
         f"(target% - biaya%) / (jarak stop% + biaya%) = "
         f"({r['target_rule_pct']:.2f}% - {r['biaya_pct']:.2f}%) / "
         f"({r['jarak_stop_pct']:.2f}% + {r['biaya_pct']:.2f}%) = {r['net_rr_rule']:.2f}"
         + (f"; R:R aktual dari target yang diisi: {r['net_rr_actual']:.2f}"
            if r["target_diberi_user"] and abs(r["net_rr_actual"] - r["net_rr_rule"]) > 1e-9 else ""),
         f"Risiko stop aktual: ${r['risiko_usdt']:.2f}"
         + (f" · stop {r['stop_jarak_atr']:.2f}x ATR di bawah entry"
            if r["stop_jarak_atr"] is not None else "")
         + (f" · risiko stop 1x ATR: ${r['risiko_atr_usdt']:.2f}"
            if r["risiko_atr_usdt"] is not None else "")]
    for c in r["checks"]:
        mark = {"OK": "✅", "PELANGGARAN": "⚠️", "TIDAK_ADA_DATA": "❓"}[c["status"]]
        L.append(f"  {mark} {c['label']}: {c['detail']}")
    L.append(f"Ringkasan: {r['n_pelanggaran']} pelanggaran dari {len(r['checks'])} cek"
             + (f" · {r['n_tidak_ada_data']} cek tanpa data" if r["n_tidak_ada_data"] else "")
             + (" — semua aturan terpenuhi" if r["n_pelanggaran"] == 0 else ""))
    L.append("Skrip ini hanya menandai — bukan veto; keputusan tetap di user. "
             "Bila user tetap lanjut, catat pelanggaran di jurnal sebagai 'pelanggaran sadar'.")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pre-entry check — hanya menandai, bukan veto (stdlib)")
    ap.add_argument("--pair", default="TOKEN")
    ap.add_argument("--entry", required=True, type=float)
    ap.add_argument("--stop", required=True, type=float)
    ap.add_argument("--target", type=float, help="target aktual (bila kosong, dipakai target-aturan)")
    ap.add_argument("--confirmed", action="store_true",
                    help="breakout/bounce sudah terkonfirmasi tutup candle")
    ap.add_argument("--confirmation", default="", help="keterangan konfirmasi, mis. 'breakout terkonfirmasi'")
    ap.add_argument("--volume-ratio", type=float, help="rasio volume candle pemicu vs rata-rata 20 candle")
    ap.add_argument("--resistance", type=float, help="resistance terdekat")
    ap.add_argument("--vwap", type=float)
    ap.add_argument("--atr", type=float)
    ap.add_argument("--budget", type=float, default=BUDGET_HARIAN, help="sisa budget rugi harian USDT")
    ap.add_argument("--capital", type=float, default=MODAL)
    ap.add_argument("--spread", type=float, default=0.1, help="spread aktual persen (asumsi 0,10 bila kosong)")
    ap.add_argument("--atr-mult", type=float, default=ATR_STOP_MULT)
    ap.add_argument("--format", choices=["text", "json"], default="text")
    a = ap.parse_args(argv)
    try:
        res = check(a.entry, a.stop, a.target, a.confirmed, a.confirmation,
                    a.volume_ratio, a.resistance, a.vwap, a.atr,
                    a.budget, a.capital, a.spread, a.atr_mult)
    except CheckError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    res["pair"] = a.pair
    if a.format == "json":
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        print(f"## Pre-entry check — {a.pair}")
        print(to_text(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
