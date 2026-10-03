"""
Landing_Gear_Design_Project
PHASE 2E3-B14B-6 V0.1 — B13C HEAD PACKAGING / HORN ENVELOPE GATE

PURPOSE
-------
Use the real B13C upper-head validation geometry to test whether the B14B horn-root
robustness shortlist can fit inside the existing upper-head boss envelope.

This is a conservative packaging gate, not a final local-stress solution.

INPUTS
------
phase2e3b14a_freeze_record.csv
phase2e3b14b_working_geometry.csv
phase2e3b14b5_horn_robust_shortlist.csv
current_design/phase2e3b13c_geometry_validation.txt

The geometry-validation TXT is parsed for:
    Upper-head outer boss diameter
    Upper-head boss height

IMPORTANT INTERPRETATION
------------------------
The B13C outer boss is a Ø106 mm cylinder about global Z, 78 mm high.

A real radial horn attaches to the CURVED side of that boss, so its actual local
root section is smaller/more complex than a full 106 x 78 mm rectangle.

Therefore this script uses a 106 x 78 mm solid rectangular section only as an
OPTIMISTIC ABSOLUTE UPPER-BOUND gross-section screen.

If even that upper bound cannot satisfy the Kt=3.0 reserve rule, the current boss
cannot honestly be declared adequate without:
    - added local reinforcement / a larger local boss,
    - a lower demonstrated Kt from detailed CAD/FEA,
    - or a revised attachment architecture.

OUTPUTS
-------
phase2e3b14b6_shortlist_packaging.csv
phase2e3b14b6_existing_boss_upper_bound.csv
phase2e3b14b6_packaging_gate.csv
phase2e3b14b6_summary.txt
"""

from __future__ import annotations

import csv
import math
import re
from pathlib import Path


HERE = Path(__file__).resolve().parent

B14A_FREEZE = HERE / "phase2e3b14a_freeze_record.csv"
B14B_GEOM = HERE / "phase2e3b14b_working_geometry.csv"
B14B5_SHORTLIST = HERE / "phase2e3b14b5_horn_robust_shortlist.csv"

VALIDATION_CANDIDATES = [
    HERE / "current_design" / "phase2e3b13c_geometry_validation.txt",
    HERE / "phase2e3b13c_geometry_validation.txt",
]

OUT_PACKAGING = HERE / "phase2e3b14b6_shortlist_packaging.csv"
OUT_UPPER = HERE / "phase2e3b14b6_existing_boss_upper_bound.csv"
OUT_GATE = HERE / "phase2e3b14b6_packaging_gate.csv"
OUT_SUMMARY = HERE / "phase2e3b14b6_summary.txt"


ULTIMATE_FACTOR = 1.5
KT_ROBUST = 3.0
MIN_MS_LIMIT = 0.20
MIN_MS_ULT = 0.10

SY_7075_T6_MPA = 505.0
SU_7075_T6_MPA = 570.0


def read_one_csv(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Missing required source: {path}")
    with path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 1:
        raise ValueError(f"{path.name}: expected one row, got {len(rows)}")
    return rows[0]


def read_csv(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Missing required source: {path}")
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows):
    if not rows:
        raise ValueError(f"No rows to write: {path}")
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def find_validation_file():
    for p in VALIDATION_CANDIDATES:
        if p.exists():
            return p

    matches = sorted(HERE.glob("phase2e3b13c_geometry_validation*.txt"))
    if matches:
        return matches[0]

    matches = sorted((HERE / "current_design").glob("phase2e3b13c_geometry_validation*.txt")) \
        if (HERE / "current_design").exists() else []
    if matches:
        return matches[0]

    raise FileNotFoundError(
        "Could not find phase2e3b13c_geometry_validation.txt in current_design or phase2_structures."
    )


def parse_head_geometry(path: Path):
    text = path.read_text(encoding="utf-8-sig", errors="replace")

    m = re.search(
        r"Upper-head outer boss:\s*Ø?\s*([0-9.]+)\s*mm\s*x\s*([0-9.]+)\s*mm\s*high",
        text
    )
    if not m:
        raise ValueError(
            "Could not parse 'Upper-head outer boss: Ø... mm x ... mm high' from validation TXT."
        )

    boss_d = float(m.group(1))
    boss_h = float(m.group(2))

    shaft = re.search(
        r"Continuous 300M shaft:\s*Ø?\s*([0-9.]+)\s*mm\s*x\s*([0-9.]+)\s*mm",
        text
    )

    shaft_d = float(shaft.group(1)) if shaft else None
    shaft_L = float(shaft.group(2)) if shaft else None

    return {
        "boss_diameter_mm": boss_d,
        "boss_height_mm": boss_h,
        "shaft_diameter_mm": shaft_d,
        "shaft_length_mm": shaft_L,
    }


def cross(a, b):
    return (
        a[1]*b[2] - a[2]*b[1],
        a[2]*b[0] - a[0]*b[2],
        a[0]*b[1] - a[1]*b[0],
    )


def section_screen(bx_mm, hz_mm, Mx_Nmm, Mz_Nmm, V_N, kt):
    A = bx_mm * hz_mm
    Ix = bx_mm * hz_mm**3 / 12.0
    Iz = hz_mm * bx_mm**3 / 12.0
    Zx = Ix / (hz_mm / 2.0)
    Zz = Iz / (bx_mm / 2.0)

    sig_mx = abs(Mx_Nmm) / Zx
    sig_mz = abs(Mz_Nmm) / Zz
    sig = kt * (sig_mx + sig_mz)
    tau = 1.5 * V_N / A

    vm = math.sqrt(sig**2 + 3.0*tau**2)

    return {
        "area_mm2": A,
        "Ix_mm4": Ix,
        "Iz_mm4": Iz,
        "Zx_mm3": Zx,
        "Zz_mm3": Zz,
        "sigma_Mx_MPa": sig_mx,
        "sigma_Mz_MPa": sig_mz,
        "sigma_after_Kt_MPa": sig,
        "tau_rect_MPa": tau,
        "VM_MPa": vm,
    }


# -----------------------------------------------------------------------------
# Source connection
# -----------------------------------------------------------------------------

b14a = read_one_csv(B14A_FREEZE)
geom = read_one_csv(B14B_GEOM)
shortlist = read_csv(B14B5_SHORTLIST)
validation_path = find_validation_file()
head = parse_head_geometry(validation_path)

if str(b14a["superposition_pass"]).strip().lower() not in {"true", "1", "yes", "pass"}:
    raise RuntimeError("B14A superposition gate is not PASS.")

Mx_ult_kNm = float(b14a["combined_Mx_kNm"])

a_perp_m = float(geom["effective_arm_mm"]) / 1000.0
ux = float(geom["u_x"])
uy = float(geom["u_y"])
uz = float(geom["u_z"])

Bx_m = float(geom["B_x_mm"]) / 1000.0
By_m = float(geom["B_y_mm"]) / 1000.0
Bz_m = float(geom["B_z_mm"]) / 1000.0

Fbrace_ult_kN = Mx_ult_kNm / a_perp_m
F_ult_kN = (
    Fbrace_ult_kN*ux,
    Fbrace_ult_kN*uy,
    Fbrace_ult_kN*uz,
)
M_ult_kNm = cross((Bx_m, By_m, Bz_m), F_ult_kN)

V_ult_N = math.hypot(F_ult_kN[0], F_ult_kN[2]) * 1000.0
Mx_ult_Nmm = M_ult_kNm[0] * 1e6
Mz_ult_Nmm = M_ult_kNm[2] * 1e6

V_lim_N = V_ult_N / ULTIMATE_FACTOR
Mx_lim_Nmm = Mx_ult_Nmm / ULTIMATE_FACTOR
Mz_lim_Nmm = Mz_ult_Nmm / ULTIMATE_FACTOR


# -----------------------------------------------------------------------------
# Packaging check of B14B-5 robust shortlist
# -----------------------------------------------------------------------------

pack_rows = []

boss_d = head["boss_diameter_mm"]
boss_h = head["boss_height_mm"]

for r in shortlist:
    bx = float(r["bx_mm"])
    hz = float(r["hz_mm"])

    fits_rectangular_bounding_envelope = (
        bx <= boss_d + 1e-12
        and hz <= boss_h + 1e-12
    )

    pack_rows.append({
        "bx_mm": bx,
        "hz_mm": hz,
        "area_mm2": float(r["area_mm2"]),
        "Kt": float(r["Kt_bending_screen"]),
        "MS_limit": float(r["MS_generic_7075T6_yield"]),
        "MS_ultimate": float(r["MS_generic_7075T6_ultimate"]),
        "boss_diameter_mm": boss_d,
        "boss_height_mm": boss_h,
        "fits_full_rectangular_boss_bounding_box": fits_rectangular_bounding_envelope,
        "note": (
            "Bounding-box fit only. Real radial horn root on curved cylindrical boss "
            "has less usable local section than this full rectangular envelope."
        ),
    })

write_csv(OUT_PACKAGING, pack_rows)

shortlist_fit_count = sum(
    1 for r in pack_rows
    if r["fits_full_rectangular_boss_bounding_box"]
)


# -----------------------------------------------------------------------------
# Optimistic absolute upper-bound: full 106 x 78 rectangle
# -----------------------------------------------------------------------------

lim = section_screen(
    boss_d, boss_h,
    Mx_lim_Nmm, Mz_lim_Nmm, V_lim_N,
    KT_ROBUST
)
ult = section_screen(
    boss_d, boss_h,
    Mx_ult_Nmm, Mz_ult_Nmm, V_ult_N,
    KT_ROBUST
)

MS_limit = SY_7075_T6_MPA / lim["VM_MPa"] - 1.0
MS_ult = SU_7075_T6_MPA / ult["VM_MPa"] - 1.0

upper_bound_reserve_pass = (
    MS_limit >= MIN_MS_LIMIT
    and MS_ult >= MIN_MS_ULT
)

upper_row = {
    "screen": "OPTIMISTIC_FULL_BOSS_RECTANGLE",
    "bx_mm": boss_d,
    "hz_mm": boss_h,
    "Kt": KT_ROBUST,
    "VM_limit_MPa": lim["VM_MPa"],
    "MS_limit_generic_7075T6_yield": MS_limit,
    "VM_ultimate_MPa": ult["VM_MPa"],
    "MS_ultimate_generic_7075T6_strength": MS_ult,
    "reserve_rule_MS_limit_min": MIN_MS_LIMIT,
    "reserve_rule_MS_ultimate_min": MIN_MS_ULT,
    "reserve_pass": upper_bound_reserve_pass,
    "interpretation": (
        "Nonphysical optimistic upper bound: assumes the entire boss diameter and "
        "height are available as a solid rectangle normal to +y. A real curved-side "
        "horn root has less local section."
    ),
}
write_csv(OUT_UPPER, [upper_row])


# -----------------------------------------------------------------------------
# Gate
# -----------------------------------------------------------------------------

if shortlist_fit_count == 0 and not upper_bound_reserve_pass:
    disposition = "LOCAL_REINFORCEMENT_OR_LOWER_DEMONSTRATED_KT_REQUIRED"
elif shortlist_fit_count == 0:
    disposition = "NO_SHORTLIST_FIT_BUT_FULL_BOSS_UPPER_BOUND_HAS_RESERVE"
else:
    disposition = "AT_LEAST_ONE_SHORTLIST_BOUNDING_ENVELOPE_FITS"

gate_row = {
    "validation_source": str(validation_path),
    "boss_diameter_mm": boss_d,
    "boss_height_mm": boss_h,
    "robust_shortlist_count": len(pack_rows),
    "robust_shortlist_bbox_fit_count": shortlist_fit_count,
    "full_boss_upper_bound_MS_limit": MS_limit,
    "full_boss_upper_bound_MS_ultimate": MS_ult,
    "full_boss_upper_bound_reserve_pass": upper_bound_reserve_pass,
    "disposition": disposition,
}
write_csv(OUT_GATE, [gate_row])


# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------

lines = []
emit = lines.append

emit("=" * 126)
emit(" PHASE 2E3-B14B-6 V0.1 — B13C HEAD PACKAGING / HORN ENVELOPE GATE")
emit("=" * 126)
emit("")
emit("SOURCE CONNECTION")
emit("-" * 126)
emit(f"B14A freeze:       {B14A_FREEZE}")
emit(f"B14B geometry:     {B14B_GEOM}")
emit(f"B14B-5 shortlist:  {B14B5_SHORTLIST}")
emit(f"B13C validation:   {validation_path}")
emit("")
emit("B13C REAL HEAD GEOMETRY")
emit("-" * 126)
emit(f"Upper-head outer boss: Ø{boss_d:.3f} mm x {boss_h:.3f} mm high")
if head["shaft_diameter_mm"] is not None:
    emit(
        f"Continuous shaft:       Ø{head['shaft_diameter_mm']:.3f} mm x "
        f"{head['shaft_length_mm']:.3f} mm"
    )
emit("Boss axis: global Z; horn attaches radially to a CURVED cylindrical side.")
emit("")
emit("B14B-5 ROBUST SHORTLIST PACKAGING")
emit("-" * 126)
emit(f"Robust candidates checked: {len(pack_rows)}")
emit(f"Candidates fitting even the FULL rectangular 106x78 bounding envelope: {shortlist_fit_count}")
for r in pack_rows:
    emit(
        f"  {r['bx_mm']:.0f} x {r['hz_mm']:.0f} mm -> "
        f"{'BBOX FIT' if r['fits_full_rectangular_boss_bounding_box'] else 'NO FIT'}"
    )
emit("")
emit("OPTIMISTIC FULL-BOSS UPPER-BOUND SCREEN")
emit("-" * 126)
emit(
    f"Equivalent rectangle: {boss_d:.1f} x {boss_h:.1f} mm "
    f"(optimistic / nonphysical upper bound)"
)
emit(f"Kt:                   {KT_ROBUST:.2f}")
emit(f"VM limit:             {lim['VM_MPa']:.3f} MPa")
emit(f"Limit MS:             {MS_limit:+.3f}")
emit(f"VM ultimate:          {ult['VM_MPa']:.3f} MPa")
emit(f"Ultimate MS:          {MS_ult:+.3f}")
emit(
    f"Reserve rule:         MS_limit >= +{MIN_MS_LIMIT:.2f}, "
    f"MS_ultimate >= +{MIN_MS_ULT:.2f}"
)
emit(f"Reserve result:       {'PASS' if upper_bound_reserve_pass else 'FAIL'}")
emit("")
emit("INTERPRETATION")
emit("-" * 126)
emit("A real radial horn root on the Ø106 curved boss has LESS usable local section than the full 106x78 rectangular upper bound.")
emit("Therefore the upper-bound result is intentionally optimistic.")
if not upper_bound_reserve_pass:
    emit("Even that optimistic upper bound does not satisfy the current Kt=3.0 reserve target.")
    emit("Do NOT freeze a horn inside the existing boss envelope.")
    emit("The next design step must add a local reinforced horn/root envelope, or later demonstrate a sufficiently lower actual Kt by detailed CAD/FEA.")
else:
    emit("The optimistic upper bound has reserve, but actual curved-side root geometry still requires CAD/FEA before freeze.")
emit("")
emit("DISPOSITION")
emit("-" * 126)
emit(disposition)
emit("")
emit("OUTPUTS")
emit("-" * 126)
for p in [OUT_PACKAGING, OUT_UPPER, OUT_GATE, OUT_SUMMARY]:
    emit(str(p))
emit("=" * 126)

report = "\n".join(lines)
OUT_SUMMARY.write_text(report, encoding="utf-8")
print(report)
