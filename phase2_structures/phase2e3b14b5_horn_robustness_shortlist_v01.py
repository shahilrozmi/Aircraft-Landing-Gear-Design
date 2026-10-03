"""
Landing_Gear_Design_Project
PHASE 2E3-B14B-5 V0.1 — HORN ROOT ROBUSTNESS SHORTLIST

PURPOSE
-------
Take the B14B-4 gross-section horn trade and identify candidates that remain
acceptable under the harsher Kt = 3.0 screen before any CAD freeze.

This step does NOT select/freeze final horn geometry. It creates a source-connected
shortlist for packaging review against the actual B13C head geometry.

INPUT
-----
phase2e3b14b4_horn_root_trade.csv

WORKING RESERVE RULE
--------------------
At Kt = 3.0 require:
    MS_limit_yield   >= +0.20
    MS_ultimate      >= +0.10

These are project working reserve targets, not regulatory requirements.

OUTPUTS
-------
phase2e3b14b5_horn_robust_shortlist.csv
phase2e3b14b5_horn_robustness_summary.txt
"""

from __future__ import annotations

import csv
from pathlib import Path


HERE = Path(__file__).resolve().parent
INPUT = HERE / "phase2e3b14b4_horn_root_trade.csv"

OUT_CSV = HERE / "phase2e3b14b5_horn_robust_shortlist.csv"
OUT_TXT = HERE / "phase2e3b14b5_horn_robustness_summary.txt"

TARGET_KT = 3.0
MIN_MS_LIMIT = 0.20
MIN_MS_ULT = 0.10
TOP_N = 10

REFERENCE_BX_MM = 65.0
REFERENCE_HZ_MM = 105.0


def f(v):
    return float(v)


if not INPUT.exists():
    raise FileNotFoundError(
        f"Missing {INPUT.name}. Run phase2e3b14b4_horn_clevis_detail_trade_v01.py first."
    )

with INPUT.open(newline="", encoding="utf-8-sig") as fp:
    raw = list(csv.DictReader(fp))

rows = []
for r in raw:
    kt = f(r["Kt_bending_screen"])
    if abs(kt - TARGET_KT) > 1e-12:
        continue

    bx = f(r["bx_mm"])
    hz = f(r["hz_mm"])
    area = f(r["area_mm2"])
    ms_lim = f(r["MS_generic_7075T6_yield"])
    ms_ult = f(r["MS_generic_7075T6_ultimate"])

    rows.append({
        **r,
        "aspect_ratio_max_over_min": max(bx, hz) / min(bx, hz),
        "reserve_pass": (
            ms_lim >= MIN_MS_LIMIT
            and ms_ult >= MIN_MS_ULT
        ),
    })

passing = [r for r in rows if r["reserve_pass"]]
passing.sort(
    key=lambda r: (
        f(r["area_mm2"]),
        float(r["aspect_ratio_max_over_min"]),
        f(r["bx_mm"]),
        f(r["hz_mm"]),
    )
)

shortlist = passing[:TOP_N]

# Find the old B14B-4 reference candidate under the harsher Kt=3 screen.
old_ref = None
for r in rows:
    if (
        abs(f(r["bx_mm"]) - REFERENCE_BX_MM) < 1e-12
        and abs(f(r["hz_mm"]) - REFERENCE_HZ_MM) < 1e-12
    ):
        old_ref = r
        break

if old_ref is None:
    raise RuntimeError("Could not find the previous 65 x 105 mm reference in Kt=3.0 trade.")

fields = list(shortlist[0].keys()) if shortlist else list(rows[0].keys())
with OUT_CSV.open("w", newline="", encoding="utf-8") as fp:
    w = csv.DictWriter(fp, fieldnames=fields)
    w.writeheader()
    w.writerows(shortlist)

lines = []
emit = lines.append

emit("=" * 118)
emit(" PHASE 2E3-B14B-5 V0.1 — HORN ROOT ROBUSTNESS SHORTLIST")
emit("=" * 118)
emit("")
emit("SOURCE")
emit("-" * 118)
emit(str(INPUT))
emit("")
emit("WORKING ROBUSTNESS RULE")
emit("-" * 118)
emit(f"Kt screen:            {TARGET_KT:.2f}")
emit(f"Minimum limit MS:    +{MIN_MS_LIMIT:.3f}")
emit(f"Minimum ultimate MS: +{MIN_MS_ULT:.3f}")
emit("")
emit("PREVIOUS B14B-4 REFERENCE UNDER Kt=3.0")
emit("-" * 118)
emit(
    f"{REFERENCE_BX_MM:.0f} x {REFERENCE_HZ_MM:.0f} mm -> "
    f"MS_limit={f(old_ref['MS_generic_7075T6_yield']):+.3f}, "
    f"MS_ultimate={f(old_ref['MS_generic_7075T6_ultimate']):+.3f}, "
    f"reserve={'PASS' if old_ref['reserve_pass'] else 'FAIL'}"
)
emit("")
emit("ROBUST SHORTLIST — SORTED BY GROSS AREA")
emit("-" * 118)
emit(
    f"{'bx':>6} {'hz':>6} {'area':>9} {'AR':>7} "
    f"{'VM_lim':>10} {'MS_lim':>9} {'VM_ult':>10} {'MS_ult':>9}"
)
emit("-" * 118)

for r in shortlist:
    emit(
        f"{f(r['bx_mm']):6.1f} "
        f"{f(r['hz_mm']):6.1f} "
        f"{f(r['area_mm2']):9.1f} "
        f"{float(r['aspect_ratio_max_over_min']):7.3f} "
        f"{f(r['VM_limit_MPa']):10.3f} "
        f"{f(r['MS_generic_7075T6_yield']):+9.3f} "
        f"{f(r['VM_ultimate_MPa']):10.3f} "
        f"{f(r['MS_generic_7075T6_ultimate']):+9.3f}"
    )

emit("")
emit("INTERPRETATION")
emit("-" * 118)
emit("The 65 x 105 mm B14B-4 reference is NOT robust to the Kt=3.0 screen and must not be frozen.")
emit("The shortlist is intentionally not reduced to one winner because actual head/CAD packaging has not yet been checked.")
emit("Next step: compare these section envelopes against the real B13C head geometry, then select one WORKING CAD candidate.")
emit("")
emit(f"CSV: {OUT_CSV}")
emit(f"TXT: {OUT_TXT}")
emit("=" * 118)

report = "\n".join(lines)
OUT_TXT.write_text(report, encoding="utf-8")
print(report)
