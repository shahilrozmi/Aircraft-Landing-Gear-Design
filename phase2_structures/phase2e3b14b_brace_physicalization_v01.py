"""
Landing_Gear_Design_Project
PHASE 2E3-B14B V0.1 — PHYSICAL BRACE GEOMETRY / MEMBER / JOINT PRELIMINARY SIZING

PURPOSE
-------
Replace the provisional "moment-only" SUP_BRACE_RX concept with a physically
defined two-force anti-rotation brace and document the preliminary structural
sizing in Python.

SOURCE CONNECTION
-----------------
This script MUST read:
    phase2e3b14a_freeze_record.csv

The governing brace moment is never pasted into this script.

B14B V0.1 scope
---------------
1) Read and validate the B14A frozen ANSYS reaction.
2) Define a physical brace line and compute its true effective Mx arm.
3) Compute limit/ultimate brace axial load and force/moment decomposition.
4) Screen the legacy 300M tube for axial stress + column buckling.
5) Screen an 18 mm 300M double-shear pin, including pin bending.
6) Screen the C63000 bronze bushing projected bearing.
7) Report preliminary 300M eye and clevis-ear stress demands.
8) Record unresolved detail-design items explicitly.

This is NOT yet a final CAD freeze. The gear-side horn/root, clevis root bending,
airframe fitting, fatigue/fracture, fit/wear/fretting, and the final physical FEA
replacement of SUP_BRACE_RX remain open.

OUTPUTS
-------
phase2e3b14b_geometry_trade.csv
phase2e3b14b_working_geometry.csv
phase2e3b14b_load_decomposition.csv
phase2e3b14b_member_joint_checks.csv
phase2e3b14b_open_items.csv
phase2e3b14b_summary.txt
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Dict, List


HERE = Path(__file__).resolve().parent

B14A_FREEZE = HERE / "phase2e3b14a_freeze_record.csv"

OUT_GEOM_TRADE = HERE / "phase2e3b14b_geometry_trade.csv"
OUT_WORKING_GEOM = HERE / "phase2e3b14b_working_geometry.csv"
OUT_DECOMP = HERE / "phase2e3b14b_load_decomposition.csv"
OUT_CHECKS = HERE / "phase2e3b14b_member_joint_checks.csv"
OUT_OPEN = HERE / "phase2e3b14b_open_items.csv"
OUT_SUMMARY = HERE / "phase2e3b14b_summary.txt"


# =============================================================================
# 1. PROJECT / DESIGN INPUTS
# =============================================================================

ULTIMATE_FACTOR = 1.5

# -------------------------------------------------------------------------
# Physical brace geometry — WORKING, NOT YET FROZEN.
#
# +x = aircraft forward
# +y = aircraft right
# +z = aircraft up
#
# O = trunnion-axis center
# B = gear-side brace pin
# A = airframe-side brace pin
#
# B is placed at +y on a torque arm/horn.  A is chosen so that the brace
# line gives exactly the target Mx effective arm while retaining a 350 mm
# pin-to-pin length.
# -------------------------------------------------------------------------
TARGET_EFFECTIVE_ARM_MM = 250.0
WORKING_PHYSICAL_RADIUS_MM = 260.0
WORKING_PIN_TO_PIN_MM = 350.0

# Geometry sensitivity around the working radial arm.
RADIAL_ARM_CANDIDATES_MM = [250.0, 260.0, 275.0, 300.0]
PIN_TO_PIN_CANDIDATES_MM = [300.0, 350.0, 400.0]

# -------------------------------------------------------------------------
# Working brace member from Phase 2D10.
# -------------------------------------------------------------------------
TUBE_OD_MM = 25.0
TUBE_WALL_MM = 3.0
TUBE_K = 1.0                  # pin-pin column idealization
STEEL_DENSITY_KG_M3 = 7850.0

# Project 300M preliminary static material screens.
E_300M_MPA = 200000.0
SY_300M_MPA = 1517.0
SU_300M_MPA = 1862.0
TAU_Y_300M_MPA = 875.840
TAU_U_300M_MPA = 1075.026

# -------------------------------------------------------------------------
# Working pin / bushing / eye / clevis geometry.
# -------------------------------------------------------------------------
PIN_D_MM = 18.0

BUSHING_ID_MM = 18.0
BUSHING_OD_MM = 24.0
BUSHING_LENGTH_MM = 20.0
BRONZE_STATIC_BEARING_SCREEN_MPA = 413.685

BRACE_EYE_OD_MM = 44.0
BRACE_EYE_WIDTH_MM = 20.0
BRACE_EYE_BORE_MM = 24.0

CLEVIS_EAR_T_MM = 10.0
CLEVIS_SIDE_CLEARANCE_MM = 1.0
CLEVIS_LUG_WIDTH_MM = 42.0
CLEVIS_PIN_CENTER_TO_EDGE_MM = 30.0

# No 7075 bearing/lug allowable is frozen here.  Stress DEMANDS are reported.
# A tensile yield value is deliberately NOT substituted for a bearing allowable.


# =============================================================================
# 2. HELPERS
# =============================================================================

def read_one_csv(path: Path) -> Dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(
            f"Required upstream source is missing: {path}\n"
            "Run/restore Phase 2E3-B14A first."
        )
    with path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 1:
        raise ValueError(f"{path.name}: expected exactly one freeze row, got {len(rows)}.")
    return rows[0]


def as_bool(v) -> bool:
    return str(v).strip().lower() in {"true", "1", "yes", "pass"}


def write_csv(path: Path, rows: List[dict], fieldnames: List[str] | None = None):
    if not rows:
        raise ValueError(f"Refusing to write empty output: {path}")
    if fieldnames is None:
        fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def ms(allowable: float, demand: float) -> float:
    return allowable / demand - 1.0


def fmt_pass(margin: float) -> str:
    return "PASS" if margin >= 0.0 else "FAIL"


def vector_cross(a, b):
    return (
        a[1]*b[2] - a[2]*b[1],
        a[2]*b[0] - a[0]*b[2],
        a[0]*b[1] - a[1]*b[0],
    )


# =============================================================================
# 3. READ + VALIDATE B14A
# =============================================================================

b14a = read_one_csv(B14A_FREEZE)

required_fields = [
    "combined_Mx_kNm",
    "combined_abs_Mx_kNm",
    "force_only_Mx_kNm",
    "moment_only_Mx_kNm",
    "pressure_only_Mx_kNm",
    "superposition_residual_fraction",
    "superposition_pass",
]
for key in required_fields:
    if key not in b14a:
        raise KeyError(f"B14A freeze file is missing required field: {key}")

if not as_bool(b14a["superposition_pass"]):
    raise RuntimeError("B14A superposition check is not PASS. B14B is blocked.")

MX_ULT_SIGNED_KNM = float(b14a["combined_Mx_kNm"])
MX_ULT_ABS_KNM = float(b14a["combined_abs_Mx_kNm"])
MX_FORCE_ONLY_KNM = float(b14a["force_only_Mx_kNm"])
MX_MOMENT_ONLY_KNM = float(b14a["moment_only_Mx_kNm"])
MX_PRESSURE_ONLY_KNM = float(b14a["pressure_only_Mx_kNm"])

MX_LIMIT_ABS_KNM = MX_ULT_ABS_KNM / ULTIMATE_FACTOR


# =============================================================================
# 4. PHYSICAL GEOMETRY
# =============================================================================

def physical_geometry(radius_mm: float, pin_to_pin_mm: float):
    """
    Construct a brace line satisfying:
        a_perp = |(r_B x u_BA)_x| = target effective Mx arm.

    Working topology:
        r_B = [0, radius, 0]
        u_BA = [ux, 0, uz]

    Thus:
        a_perp = radius * uz
        uz = a_perp / radius
        ux = sqrt(1 - uz^2)

    A = B + L*u.
    """
    if radius_mm < TARGET_EFFECTIVE_ARM_MM:
        raise ValueError("Physical radial arm cannot be smaller than target effective arm.")

    uz = TARGET_EFFECTIVE_ARM_MM / radius_mm
    ux = math.sqrt(max(0.0, 1.0 - uz**2))

    dx_mm = pin_to_pin_mm * ux
    dz_mm = pin_to_pin_mm * uz

    rB = (0.0, radius_mm, 0.0)
    u = (ux, 0.0, uz)
    rA = (dx_mm, radius_mm, dz_mm)

    cross = vector_cross(rB, u)
    a_perp_mm = abs(cross[0])

    return {
        "physical_radius_mm": radius_mm,
        "pin_to_pin_mm": pin_to_pin_mm,
        "B_x_mm": rB[0],
        "B_y_mm": rB[1],
        "B_z_mm": rB[2],
        "A_x_mm": rA[0],
        "A_y_mm": rA[1],
        "A_z_mm": rA[2],
        "delta_x_mm": dx_mm,
        "delta_y_mm": 0.0,
        "delta_z_mm": dz_mm,
        "u_x": ux,
        "u_y": 0.0,
        "u_z": uz,
        "effective_arm_mm": a_perp_mm,
        "secondary_mz_per_unit_force_mm": abs(cross[2]),
    }


geometry_trade = []
for r in RADIAL_ARM_CANDIDATES_MM:
    for L in PIN_TO_PIN_CANDIDATES_MM:
        g = physical_geometry(r, L)
        geometry_trade.append({
            **g,
            "geometry_status": (
                "WORKING_CANDIDATE"
                if abs(r - WORKING_PHYSICAL_RADIUS_MM) < 1e-12
                and abs(L - WORKING_PIN_TO_PIN_MM) < 1e-12
                else "TRADE"
            ),
        })

working_geom = physical_geometry(
    WORKING_PHYSICAL_RADIUS_MM,
    WORKING_PIN_TO_PIN_MM,
)

if abs(working_geom["effective_arm_mm"] - TARGET_EFFECTIVE_ARM_MM) > 1e-9:
    raise RuntimeError("Working geometry does not reproduce the target effective arm.")


# =============================================================================
# 5. BRACE LOADS FROM B14A
# =============================================================================

a_m = working_geom["effective_arm_mm"] / 1000.0

F_ULT_SIGNED_KN = MX_ULT_SIGNED_KNM / a_m
F_ULT_ABS_KN = abs(F_ULT_SIGNED_KN)
F_LIMIT_ABS_KN = MX_LIMIT_ABS_KNM / a_m

F_FORCE_ONLY_KN = MX_FORCE_ONLY_KNM / a_m
F_MOMENT_ONLY_KN = MX_MOMENT_ONLY_KNM / a_m
F_PRESSURE_ONLY_KN = MX_PRESSURE_ONLY_KNM / a_m

ux = working_geom["u_x"]
uy = working_geom["u_y"]
uz = working_geom["u_z"]

# Signed gear-side force for the +y working attachment.
FX_ULT_KN = F_ULT_SIGNED_KN * ux
FY_ULT_KN = F_ULT_SIGNED_KN * uy
FZ_ULT_KN = F_ULT_SIGNED_KN * uz

# Moment at O generated by the physical brace force acting at B.
rB_m = (
    working_geom["B_x_mm"] / 1000.0,
    working_geom["B_y_mm"] / 1000.0,
    working_geom["B_z_mm"] / 1000.0,
)
Fvec_kN = (FX_ULT_KN, FY_ULT_KN, FZ_ULT_KN)
M_from_brace_kNm = vector_cross(rB_m, Fvec_kN)

decomp_rows = [
    {
        "component": "combined",
        "Mx_kNm": MX_ULT_SIGNED_KNM,
        "brace_axial_kN": F_ULT_SIGNED_KN,
    },
    {
        "component": "force_only",
        "Mx_kNm": MX_FORCE_ONLY_KNM,
        "brace_axial_kN": F_FORCE_ONLY_KN,
    },
    {
        "component": "moment_only",
        "Mx_kNm": MX_MOMENT_ONLY_KNM,
        "brace_axial_kN": F_MOMENT_ONLY_KN,
    },
    {
        "component": "pressure_only",
        "Mx_kNm": MX_PRESSURE_ONLY_KNM,
        "brace_axial_kN": F_PRESSURE_ONLY_KN,
    },
]


# =============================================================================
# 6. 300M TUBE — AXIAL + JOHNSON/EULER COLUMN SCREEN
# =============================================================================

TUBE_ID_MM = TUBE_OD_MM - 2.0*TUBE_WALL_MM
if TUBE_ID_MM <= 0:
    raise ValueError("Invalid tube wall/OD combination.")

A_TUBE_MM2 = math.pi/4.0 * (TUBE_OD_MM**2 - TUBE_ID_MM**2)
I_TUBE_MM4 = math.pi/64.0 * (TUBE_OD_MM**4 - TUBE_ID_MM**4)
RG_TUBE_MM = math.sqrt(I_TUBE_MM4 / A_TUBE_MM2)

SIGMA_LIMIT_MPA = F_LIMIT_ABS_KN*1000.0 / A_TUBE_MM2
SIGMA_ULT_MPA = F_ULT_ABS_KN*1000.0 / A_TUBE_MM2

SLENDERNESS = TUBE_K * WORKING_PIN_TO_PIN_MM / RG_TUBE_MM
CC = math.sqrt(2.0 * math.pi**2 * E_300M_MPA / SY_300M_MPA)

if SLENDERNESS <= CC:
    BUCKLING_MODEL = "JOHNSON_PARABOLIC"
    SIGMA_CR_MPA = (
        SY_300M_MPA
        * (
            1.0
            - SY_300M_MPA
            / (4.0 * math.pi**2 * E_300M_MPA)
            * SLENDERNESS**2
        )
    )
else:
    BUCKLING_MODEL = "EULER"
    SIGMA_CR_MPA = (
        math.pi**2 * E_300M_MPA / SLENDERNESS**2
    )

PCR_KN = SIGMA_CR_MPA * A_TUBE_MM2 / 1000.0

MS_TUBE_LIMIT_YIELD = ms(SY_300M_MPA, SIGMA_LIMIT_MPA)
MS_TUBE_ULTIMATE = ms(SU_300M_MPA, SIGMA_ULT_MPA)
MS_TUBE_BUCKLING = PCR_KN/F_ULT_ABS_KN - 1.0

TUBE_MASS_KG = (
    A_TUBE_MM2 * 1e-6
    * (WORKING_PIN_TO_PIN_MM / 1000.0)
    * STEEL_DENSITY_KG_M3
)


# =============================================================================
# 7. 300M PIN — DOUBLE SHEAR + BENDING
# =============================================================================

A_PIN_MM2 = math.pi/4.0 * PIN_D_MM**2

TAU_PIN_LIMIT_MPA = F_LIMIT_ABS_KN*1000.0 / (2.0*A_PIN_MM2)
TAU_PIN_ULT_MPA = F_ULT_ABS_KN*1000.0 / (2.0*A_PIN_MM2)

# Exact half-pin distributed-bearing free body for the working clevis stack:
#
# Eye occupies y = [-b/2,+b/2] with uniform total load F.
# Each ear carries F/2 uniformly.
# Ear centroid distance from pin center:
#     b/2 + clearance + t_ear/2
# Half of eye load F/2 acts at b/4 from pin center.
#
# Therefore:
# M_center = F/2 * [(b/2+c+t/2) - b/4]
#
b = BRACE_EYE_WIDTH_MM
c = CLEVIS_SIDE_CLEARANCE_MM
te = CLEVIS_EAR_T_MM

ear_centroid_from_center_mm = b/2.0 + c + te/2.0
half_eye_centroid_from_center_mm = b/4.0
distributed_lever_mm = (
    ear_centroid_from_center_mm - half_eye_centroid_from_center_mm
)

M_PIN_DIST_LIMIT_NMM = F_LIMIT_ABS_KN*1000.0/2.0 * distributed_lever_mm
M_PIN_DIST_ULT_NMM = F_ULT_ABS_KN*1000.0/2.0 * distributed_lever_mm

SIGMA_PIN_B_DIST_LIMIT_MPA = (
    32.0*M_PIN_DIST_LIMIT_NMM / (math.pi*PIN_D_MM**3)
)
SIGMA_PIN_B_DIST_ULT_MPA = (
    32.0*M_PIN_DIST_ULT_NMM / (math.pi*PIN_D_MM**3)
)

# Conservative combination: peak bending and nominal double-shear stress are
# combined even though they do not strictly peak at the same material point.
VM_PIN_DIST_LIMIT_MPA = math.sqrt(
    SIGMA_PIN_B_DIST_LIMIT_MPA**2 + 3.0*TAU_PIN_LIMIT_MPA**2
)
VM_PIN_DIST_ULT_MPA = math.sqrt(
    SIGMA_PIN_B_DIST_ULT_MPA**2 + 3.0*TAU_PIN_ULT_MPA**2
)

# Harsher concentrated-contact bound: ignore the balancing moment of the
# distributed half-eye load and use the ear-centroid offset directly.
M_PIN_BOUND_LIMIT_NMM = F_LIMIT_ABS_KN*1000.0/2.0 * ear_centroid_from_center_mm
M_PIN_BOUND_ULT_NMM = F_ULT_ABS_KN*1000.0/2.0 * ear_centroid_from_center_mm

SIGMA_PIN_B_BOUND_LIMIT_MPA = (
    32.0*M_PIN_BOUND_LIMIT_NMM / (math.pi*PIN_D_MM**3)
)
SIGMA_PIN_B_BOUND_ULT_MPA = (
    32.0*M_PIN_BOUND_ULT_NMM / (math.pi*PIN_D_MM**3)
)

VM_PIN_BOUND_LIMIT_MPA = math.sqrt(
    SIGMA_PIN_B_BOUND_LIMIT_MPA**2 + 3.0*TAU_PIN_LIMIT_MPA**2
)
VM_PIN_BOUND_ULT_MPA = math.sqrt(
    SIGMA_PIN_B_BOUND_ULT_MPA**2 + 3.0*TAU_PIN_ULT_MPA**2
)

MS_PIN_SHEAR_LIMIT = ms(TAU_Y_300M_MPA, TAU_PIN_LIMIT_MPA)
MS_PIN_SHEAR_ULT = ms(TAU_U_300M_MPA, TAU_PIN_ULT_MPA)

MS_PIN_DIST_LIMIT = ms(SY_300M_MPA, VM_PIN_DIST_LIMIT_MPA)
MS_PIN_DIST_ULT = ms(SU_300M_MPA, VM_PIN_DIST_ULT_MPA)

MS_PIN_BOUND_LIMIT = ms(SY_300M_MPA, VM_PIN_BOUND_LIMIT_MPA)
MS_PIN_BOUND_ULT = ms(SU_300M_MPA, VM_PIN_BOUND_ULT_MPA)


# =============================================================================
# 8. BRONZE BUSHING
# =============================================================================

BUSHING_RADIAL_WALL_MM = (BUSHING_OD_MM - BUSHING_ID_MM)/2.0

P_BUSH_LIMIT_MPA = (
    F_LIMIT_ABS_KN*1000.0
    / (PIN_D_MM*BUSHING_LENGTH_MM)
)
P_BUSH_ULT_MPA = (
    F_ULT_ABS_KN*1000.0
    / (PIN_D_MM*BUSHING_LENGTH_MM)
)

MS_BUSH_LIMIT = ms(BRONZE_STATIC_BEARING_SCREEN_MPA, P_BUSH_LIMIT_MPA)
MS_BUSH_ULT = ms(BRONZE_STATIC_BEARING_SCREEN_MPA, P_BUSH_ULT_MPA)


# =============================================================================
# 9. BRACE EYE — PRELIMINARY LOCAL DEMANDS
# =============================================================================

EYE_NET_AREA_MM2 = BRACE_EYE_WIDTH_MM * (BRACE_EYE_OD_MM - BRACE_EYE_BORE_MM)
EYE_RADIAL_LIGAMENT_MM = (BRACE_EYE_OD_MM - BRACE_EYE_BORE_MM)/2.0
EYE_SHEAROUT_AREA_MM2 = (
    2.0 * BRACE_EYE_WIDTH_MM * EYE_RADIAL_LIGAMENT_MM
)

SIGMA_EYE_NET_LIMIT_MPA = F_LIMIT_ABS_KN*1000.0 / EYE_NET_AREA_MM2
SIGMA_EYE_NET_ULT_MPA = F_ULT_ABS_KN*1000.0 / EYE_NET_AREA_MM2

TAU_EYE_SO_LIMIT_MPA = F_LIMIT_ABS_KN*1000.0 / EYE_SHEAROUT_AREA_MM2
TAU_EYE_SO_ULT_MPA = F_ULT_ABS_KN*1000.0 / EYE_SHEAROUT_AREA_MM2

P_BUSH_TO_EYE_LIMIT_MPA = (
    F_LIMIT_ABS_KN*1000.0
    / (BUSHING_OD_MM*BRACE_EYE_WIDTH_MM)
)
P_BUSH_TO_EYE_ULT_MPA = (
    F_ULT_ABS_KN*1000.0
    / (BUSHING_OD_MM*BRACE_EYE_WIDTH_MM)
)

MS_EYE_NET_LIMIT = ms(SY_300M_MPA, SIGMA_EYE_NET_LIMIT_MPA)
MS_EYE_NET_ULT = ms(SU_300M_MPA, SIGMA_EYE_NET_ULT_MPA)
MS_EYE_SO_LIMIT = ms(TAU_Y_300M_MPA, TAU_EYE_SO_LIMIT_MPA)
MS_EYE_SO_ULT = ms(TAU_U_300M_MPA, TAU_EYE_SO_ULT_MPA)


# =============================================================================
# 10. CLEVIS EARS — DEMAND ONLY UNTIL LUG ALLOWABLES / ROOT GEOMETRY FREEZE
# =============================================================================

F_EAR_LIMIT_N = F_LIMIT_ABS_KN*1000.0/2.0
F_EAR_ULT_N = F_ULT_ABS_KN*1000.0/2.0

P_EAR_LIMIT_MPA = F_EAR_LIMIT_N / (PIN_D_MM*CLEVIS_EAR_T_MM)
P_EAR_ULT_MPA = F_EAR_ULT_N / (PIN_D_MM*CLEVIS_EAR_T_MM)

A_EAR_NET_MM2 = CLEVIS_EAR_T_MM * (CLEVIS_LUG_WIDTH_MM - PIN_D_MM)
SIGMA_EAR_NET_LIMIT_MPA = F_EAR_LIMIT_N / A_EAR_NET_MM2
SIGMA_EAR_NET_ULT_MPA = F_EAR_ULT_N / A_EAR_NET_MM2

EAR_CLEAR_LIGAMENT_MM = CLEVIS_PIN_CENTER_TO_EDGE_MM - PIN_D_MM/2.0
A_EAR_SHEAROUT_MM2 = 2.0*CLEVIS_EAR_T_MM*EAR_CLEAR_LIGAMENT_MM
TAU_EAR_SO_LIMIT_MPA = F_EAR_LIMIT_N / A_EAR_SHEAROUT_MM2
TAU_EAR_SO_ULT_MPA = F_EAR_ULT_N / A_EAR_SHEAROUT_MM2

CLEVIS_GAP_MM = BRACE_EYE_WIDTH_MM + 2.0*CLEVIS_SIDE_CLEARANCE_MM
STRUCTURAL_PIN_GRIP_MM = (
    CLEVIS_EAR_T_MM
    + CLEVIS_SIDE_CLEARANCE_MM
    + BRACE_EYE_WIDTH_MM
    + CLEVIS_SIDE_CLEARANCE_MM
    + CLEVIS_EAR_T_MM
)


# =============================================================================
# 11. RESULTS TABLE
# =============================================================================

checks = []

def add_check(component, check, level, demand, units, allowable, margin, status, note=""):
    checks.append({
        "component": component,
        "check": check,
        "level": level,
        "demand": demand,
        "units": units,
        "allowable_or_capacity": allowable,
        "margin": margin,
        "status": status,
        "note": note,
    })

add_check(
    "300M tube", "axial yield", "limit",
    SIGMA_LIMIT_MPA, "MPa", SY_300M_MPA,
    MS_TUBE_LIMIT_YIELD, fmt_pass(MS_TUBE_LIMIT_YIELD),
)
add_check(
    "300M tube", "axial ultimate", "ultimate",
    SIGMA_ULT_MPA, "MPa", SU_300M_MPA,
    MS_TUBE_ULTIMATE, fmt_pass(MS_TUBE_ULTIMATE),
)
add_check(
    "300M tube", f"column buckling ({BUCKLING_MODEL})", "ultimate",
    F_ULT_ABS_KN, "kN", PCR_KN,
    MS_TUBE_BUCKLING, fmt_pass(MS_TUBE_BUCKLING),
)

add_check(
    "300M pin", "double-shear", "limit",
    TAU_PIN_LIMIT_MPA, "MPa", TAU_Y_300M_MPA,
    MS_PIN_SHEAR_LIMIT, fmt_pass(MS_PIN_SHEAR_LIMIT),
)
add_check(
    "300M pin", "double-shear", "ultimate",
    TAU_PIN_ULT_MPA, "MPa", TAU_U_300M_MPA,
    MS_PIN_SHEAR_ULT, fmt_pass(MS_PIN_SHEAR_ULT),
)
add_check(
    "300M pin", "distributed-bearing bending + nominal shear VM", "limit",
    VM_PIN_DIST_LIMIT_MPA, "MPa", SY_300M_MPA,
    MS_PIN_DIST_LIMIT, fmt_pass(MS_PIN_DIST_LIMIT),
    "Exact symmetric uniform-bearing half-pin free body for working stack."
)
add_check(
    "300M pin", "distributed-bearing bending + nominal shear VM", "ultimate",
    VM_PIN_DIST_ULT_MPA, "MPa", SU_300M_MPA,
    MS_PIN_DIST_ULT, fmt_pass(MS_PIN_DIST_ULT),
    "Exact symmetric uniform-bearing half-pin free body for working stack."
)
add_check(
    "300M pin", "concentrated-contact conservative bound VM", "limit",
    VM_PIN_BOUND_LIMIT_MPA, "MPa", SY_300M_MPA,
    MS_PIN_BOUND_LIMIT, fmt_pass(MS_PIN_BOUND_LIMIT),
)
add_check(
    "300M pin", "concentrated-contact conservative bound VM", "ultimate",
    VM_PIN_BOUND_ULT_MPA, "MPa", SU_300M_MPA,
    MS_PIN_BOUND_ULT, fmt_pass(MS_PIN_BOUND_ULT),
)

add_check(
    "C63000 bronze bushing", "projected pin bearing", "limit",
    P_BUSH_LIMIT_MPA, "MPa", BRONZE_STATIC_BEARING_SCREEN_MPA,
    MS_BUSH_LIMIT, fmt_pass(MS_BUSH_LIMIT),
    "Preliminary project static bearing screen only."
)
add_check(
    "C63000 bronze bushing", "projected pin bearing", "ultimate",
    P_BUSH_ULT_MPA, "MPa", BRONZE_STATIC_BEARING_SCREEN_MPA,
    MS_BUSH_ULT, fmt_pass(MS_BUSH_ULT),
    "Preliminary project static bearing screen only."
)

add_check(
    "300M brace eye", "net section", "limit",
    SIGMA_EYE_NET_LIMIT_MPA, "MPa", SY_300M_MPA,
    MS_EYE_NET_LIMIT, fmt_pass(MS_EYE_NET_LIMIT),
    "Simplified annular-eye net-section screen; transition/fillet still open."
)
add_check(
    "300M brace eye", "net section", "ultimate",
    SIGMA_EYE_NET_ULT_MPA, "MPa", SU_300M_MPA,
    MS_EYE_NET_ULT, fmt_pass(MS_EYE_NET_ULT),
    "Simplified annular-eye net-section screen; transition/fillet still open."
)
add_check(
    "300M brace eye", "radial shear-out", "limit",
    TAU_EYE_SO_LIMIT_MPA, "MPa", TAU_Y_300M_MPA,
    MS_EYE_SO_LIMIT, fmt_pass(MS_EYE_SO_LIMIT),
    "Simplified two-plane eye-ligament screen."
)
add_check(
    "300M brace eye", "radial shear-out", "ultimate",
    TAU_EYE_SO_ULT_MPA, "MPa", TAU_U_300M_MPA,
    MS_EYE_SO_ULT, fmt_pass(MS_EYE_SO_ULT),
    "Simplified two-plane eye-ligament screen."
)

# Clevis ears: report demand only — no false bearing/lug allowable.
add_check(
    "clevis ears", "projected bearing", "limit",
    P_EAR_LIMIT_MPA, "MPa", "", "", "OPEN_ALLOWABLE",
    "Gear-side 7075 product form/temper-specific lug bearing allowable is not frozen."
)
add_check(
    "clevis ears", "projected bearing", "ultimate",
    P_EAR_ULT_MPA, "MPa", "", "", "OPEN_ALLOWABLE",
    "Gear-side 7075 product form/temper-specific lug bearing allowable is not frozen."
)
add_check(
    "clevis ears", "net-section demand", "limit",
    SIGMA_EAR_NET_LIMIT_MPA, "MPa", "", "", "DEMAND_ONLY",
    "Final lug allowable and stress-concentration treatment remain open."
)
add_check(
    "clevis ears", "net-section demand", "ultimate",
    SIGMA_EAR_NET_ULT_MPA, "MPa", "", "", "DEMAND_ONLY",
    "Final lug allowable and stress-concentration treatment remain open."
)
add_check(
    "clevis ears", "shear-out demand", "limit",
    TAU_EAR_SO_LIMIT_MPA, "MPa", "", "", "DEMAND_ONLY",
    "Final lug allowable and edge/fillet geometry remain open."
)
add_check(
    "clevis ears", "shear-out demand", "ultimate",
    TAU_EAR_SO_ULT_MPA, "MPa", "", "", "DEMAND_ONLY",
    "Final lug allowable and edge/fillet geometry remain open."
)


# =============================================================================
# 12. OPEN ITEMS
# =============================================================================

open_items = [
    {
        "item": "GEAR_SIDE_HORN_ROOT",
        "status": "OPEN",
        "reason": (
            "The 260 mm physical radial arm implies a substantial torque arm/horn. "
            "Root thickness, width, fillet and local 7075 load path are not yet defined."
        ),
    },
    {
        "item": "CLEVIS_EAR_BENDING",
        "status": "OPEN",
        "reason": (
            "Ear root stand-off / root section is not frozen, so clevis-ear bending "
            "cannot yet be calculated honestly."
        ),
    },
    {
        "item": "7075_LUG_ALLOWABLES",
        "status": "OPEN",
        "reason": (
            "Product form, temper-specific bearing/net/shear-out allowables are not "
            "frozen; tensile yield is not substituted as a bearing allowable."
        ),
    },
    {
        "item": "AIRFRAME_SIDE_FITTING",
        "status": "OPEN",
        "reason": (
            "Airframe clevis material, thickness, root geometry and attachment to "
            "primary structure are not yet defined."
        ),
    },
    {
        "item": "BRACE_END_FITTING_TO_TUBE",
        "status": "OPEN",
        "reason": (
            "The 44 x 20 mm eye cannot simply be assumed to merge into a 25 x 3 mm "
            "tube; machined/forged end fitting and joining method must be defined."
        ),
    },
    {
        "item": "FIT_WEAR_FRETTING",
        "status": "OPEN",
        "reason": "Pin/bushing fit, lubrication, fretting and wear are detail-design items.",
    },
    {
        "item": "FATIGUE_FRACTURE",
        "status": "OPEN",
        "reason": "Static screens do not close fatigue or fracture mechanics.",
    },
    {
        "item": "PHYSICAL_FEA_REPLACEMENT",
        "status": "OPEN",
        "reason": (
            "SUP_BRACE_RX must later be removed and replaced by a pin-ended axial brace "
            "at the actual B/A pin centers. Journal reactions must then be re-solved."
        ),
    },
]


# =============================================================================
# 13. OUTPUT FILES
# =============================================================================

write_csv(OUT_GEOM_TRADE, geometry_trade)

working_geometry_row = {
    **working_geom,
    "target_effective_arm_mm": TARGET_EFFECTIVE_ARM_MM,
    "status": "WORKING_NOT_FROZEN",
    "note": (
        "Physical geometry reproduces the 250 mm Mx arm exactly. "
        "It introduces real translational force components and a secondary Mz."
    ),
}
write_csv(OUT_WORKING_GEOM, [working_geometry_row])

write_csv(OUT_DECOMP, decomp_rows)
write_csv(OUT_CHECKS, checks)
write_csv(OUT_OPEN, open_items)


# =============================================================================
# 14. CONSOLE / TXT REPORT
# =============================================================================

all_closed_static_checks_pass = all(
    row["status"] == "PASS"
    for row in checks
    if row["status"] in {"PASS", "FAIL"}
)

lines = []
emit = lines.append

emit("=" * 124)
emit(" PHASE 2E3-B14B V0.1 — PHYSICAL BRACE GEOMETRY / MEMBER / JOINT PRELIMINARY SIZING")
emit("=" * 124)
emit("")
emit("SOURCE CONNECTION")
emit("-" * 124)
emit(f"B14A freeze record: {B14A_FREEZE}")
emit(f"B14A superposition pass: {b14a['superposition_pass']}")
emit(f"Frozen governing ultimate Mx: {MX_ULT_SIGNED_KNM:+.9f} kN*m")
emit(f"Ultimate factor: {ULTIMATE_FACTOR:.3f}")
emit("")

emit("WORKING PHYSICAL GEOMETRY — NOT YET FROZEN")
emit("-" * 124)
emit(f"Gear pin B [x,y,z]:     [{working_geom['B_x_mm']:.3f}, {working_geom['B_y_mm']:.3f}, {working_geom['B_z_mm']:.3f}] mm")
emit(f"Airframe pin A [x,y,z]: [{working_geom['A_x_mm']:.3f}, {working_geom['A_y_mm']:.3f}, {working_geom['A_z_mm']:.3f}] mm")
emit(f"Pin-to-pin length:       {working_geom['pin_to_pin_mm']:.3f} mm")
emit(f"Brace unit vector:       [{ux:.9f}, {uy:.9f}, {uz:.9f}]")
emit(f"Physical radial arm:     {working_geom['physical_radius_mm']:.3f} mm")
emit(f"Effective Mx arm:        {working_geom['effective_arm_mm']:.6f} mm")
emit("")

emit("BRACE LOAD")
emit("-" * 124)
emit(f"Limit |Mx|:              {MX_LIMIT_ABS_KNM:.6f} kN*m")
emit(f"Ultimate |Mx|:           {MX_ULT_ABS_KNM:.6f} kN*m")
emit(f"Limit |Fbrace|:          {F_LIMIT_ABS_KN:.6f} kN")
emit(f"Ultimate |Fbrace|:       {F_ULT_ABS_KN:.6f} kN")
emit(f"Signed ultimate Fbrace:  {F_ULT_SIGNED_KN:+.6f} kN")
emit(f"Physical gear-pin force: Fx={FX_ULT_KN:+.6f}, Fy={FY_ULT_KN:+.6f}, Fz={FZ_ULT_KN:+.6f} kN")
emit(f"Moment from r_B x F:     Mx={M_from_brace_kNm[0]:+.6f}, My={M_from_brace_kNm[1]:+.6f}, Mz={M_from_brace_kNm[2]:+.6f} kN*m")
emit("")
emit("IMPORTANT: the physical brace reproduces Mx but also introduces translational reactions")
emit("and a secondary Mz because the working brace line has a nonzero x component.")
emit("Journal/support reactions therefore must be recomputed in the later physical-brace FEA.")
emit("")

emit("300M TUBE")
emit("-" * 124)
emit(f"Section:                  {TUBE_OD_MM:.1f} OD x {TUBE_WALL_MM:.1f} wall mm (ID {TUBE_ID_MM:.1f} mm)")
emit(f"Area:                     {A_TUBE_MM2:.3f} mm^2")
emit(f"Radius of gyration:       {RG_TUBE_MM:.3f} mm")
emit(f"KL/r:                     {SLENDERNESS:.3f}")
emit(f"Johnson/Euler transition: {CC:.3f}")
emit(f"Buckling model:           {BUCKLING_MODEL}")
emit(f"Critical stress:          {SIGMA_CR_MPA:.3f} MPa")
emit(f"Critical load:            {PCR_KN:.3f} kN")
emit(f"Limit axial stress:       {SIGMA_LIMIT_MPA:.3f} MPa  MS={MS_TUBE_LIMIT_YIELD:+.3f}")
emit(f"Ultimate axial stress:    {SIGMA_ULT_MPA:.3f} MPa  MS={MS_TUBE_ULTIMATE:+.3f}")
emit(f"Ultimate buckling MS:     {MS_TUBE_BUCKLING:+.3f}")
emit(f"Approx. tube mass:        {TUBE_MASS_KG:.3f} kg")
emit("")

emit("300M PIN")
emit("-" * 124)
emit(f"Pin diameter:             {PIN_D_MM:.1f} mm")
emit(f"Double-shear tau, limit:  {TAU_PIN_LIMIT_MPA:.3f} MPa")
emit(f"Double-shear tau, ult:    {TAU_PIN_ULT_MPA:.3f} MPa")
emit(f"Distributed lever:        {distributed_lever_mm:.3f} mm")
emit(f"Distributed pin VM, lim:  {VM_PIN_DIST_LIMIT_MPA:.3f} MPa  MS={MS_PIN_DIST_LIMIT:+.3f}")
emit(f"Distributed pin VM, ult:  {VM_PIN_DIST_ULT_MPA:.3f} MPa  MS={MS_PIN_DIST_ULT:+.3f}")
emit(f"Bound pin VM, limit:      {VM_PIN_BOUND_LIMIT_MPA:.3f} MPa  MS={MS_PIN_BOUND_LIMIT:+.3f}")
emit(f"Bound pin VM, ultimate:   {VM_PIN_BOUND_ULT_MPA:.3f} MPa  MS={MS_PIN_BOUND_ULT:+.3f}")
emit("")

emit("BUSHING / CLEVIS STACK")
emit("-" * 124)
emit(f"Bronze bushing:           {BUSHING_OD_MM:.1f} OD x {BUSHING_ID_MM:.1f} ID x {BUSHING_LENGTH_MM:.1f} long mm")
emit(f"Bushing radial wall:      {BUSHING_RADIAL_WALL_MM:.3f} mm")
emit(f"Bronze bearing, limit:    {P_BUSH_LIMIT_MPA:.3f} MPa  MS={MS_BUSH_LIMIT:+.3f}")
emit(f"Bronze bearing, ultimate: {P_BUSH_ULT_MPA:.3f} MPa  MS={MS_BUSH_ULT:+.3f}")
emit(f"Brace eye:                {BRACE_EYE_OD_MM:.1f} OD x {BRACE_EYE_WIDTH_MM:.1f} wide, {BRACE_EYE_BORE_MM:.1f} bore mm")
emit(f"Clevis ears:              2 x {CLEVIS_EAR_T_MM:.1f} mm")
emit(f"Clevis internal gap:      {CLEVIS_GAP_MM:.1f} mm")
emit(f"Structural pin grip:      {STRUCTURAL_PIN_GRIP_MM:.1f} mm")
emit(f"Ear bearing demand, ult:  {P_EAR_ULT_MPA:.3f} MPa  [ALLOWABLE OPEN]")
emit(f"Ear net demand, ult:      {SIGMA_EAR_NET_ULT_MPA:.3f} MPa  [ALLOWABLE OPEN]")
emit(f"Ear shear-out, ult:       {TAU_EAR_SO_ULT_MPA:.3f} MPa  [ALLOWABLE OPEN]")
emit("")

emit("STATIC SCREEN STATUS")
emit("-" * 124)
emit(f"Closed static checks:     {'PASS' if all_closed_static_checks_pass else 'FAIL'}")
emit("Clevis/lug material checks remain OPEN where a valid lug/bearing allowable is not frozen.")
emit("")

emit("OPEN ITEMS BEFORE CAD FREEZE / PHYSICAL FEA")
emit("-" * 124)
for item in open_items:
    emit(f"- {item['item']}: {item['reason']}")
emit("")

emit("DISPOSITION")
emit("-" * 124)
emit("B14B V0.1 establishes a source-connected working physical brace and preliminary member/joint screen.")
emit("Do NOT call the geometry a final freeze yet.")
emit("Next engineering step: B14B-4 physical horn/clevis/root geometry + lug allowables + root bending,")
emit("followed by replacement of SUP_BRACE_RX with the actual pin-ended brace in ANSYS.")
emit("")
emit("OUTPUTS")
emit("-" * 124)
for p in [OUT_GEOM_TRADE, OUT_WORKING_GEOM, OUT_DECOMP, OUT_CHECKS, OUT_OPEN, OUT_SUMMARY]:
    emit(str(p))
emit("=" * 124)

report = "\n".join(lines)
OUT_SUMMARY.write_text(report, encoding="utf-8")
print(report)
