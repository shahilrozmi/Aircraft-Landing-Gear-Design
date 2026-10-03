"""
Landing_Gear_Design_Project
PHASE 2E3-B14B-4 V0.1 — HORN ROOT / CLEVIS / END-FITTING DETAIL TRADE

PURPOSE
-------
Continue B14B from the source-connected physical brace definition and quantify the
next level of detail without inventing final CAD geometry.

This script reads:
    phase2e3b14a_freeze_record.csv
    phase2e3b14b_working_geometry.csv

It then:
1) reconstructs the physical brace force from the frozen B14A Mx and B14B geometry,
2) computes the full gear-side horn/head interface force and moment demand,
3) performs an equivalent solid-rectangular 7075-T6 horn-root section trade,
4) performs nominal clevis lug net/shear-out material screens,
5) keeps lug bearing OPEN because no product-form-specific bearing allowable is frozen,
6) screens a short 300M eye-to-tube solid spigot/end-fitting shank trade,
7) records all remaining CAD/FEA closure items.

IMPORTANT GEOMETRY NOTE
-----------------------
The trunnion axis is global +x. The B13B bronze sleeve length is therefore an x-axis
dimension and MUST NOT be used as a y-axis horn-root location.

Accordingly, this script does NOT invent a head radius or horn free length. The horn
root trade is performed against the full force/moment resultants transferred at the
trunnion-center interface. The rectangular section is only an equivalent gross-section
screen for selecting a CAD envelope.

MATERIAL SCREEN NOTE
--------------------
7075-T6 generic tensile properties used here:
    Sy = 505 MPa
    Su = 570 MPa

These are generic material-property screens only. They are NOT substituted for
product-form-specific lug bearing, shear-out, fatigue, or certification allowables.

OUTPUTS
-------
phase2e3b14b4_horn_root_trade.csv
phase2e3b14b4_horn_reference_candidate.csv
phase2e3b14b4_clevis_nominal_screens.csv
phase2e3b14b4_end_fitting_spigot_trade.csv
phase2e3b14b4_open_items.csv
phase2e3b14b4_summary.txt
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Dict, List


HERE = Path(__file__).resolve().parent

B14A_FREEZE = HERE / "phase2e3b14a_freeze_record.csv"
B14B_GEOMETRY = HERE / "phase2e3b14b_working_geometry.csv"

OUT_HORN_TRADE = HERE / "phase2e3b14b4_horn_root_trade.csv"
OUT_HORN_REF = HERE / "phase2e3b14b4_horn_reference_candidate.csv"
OUT_CLEVIS = HERE / "phase2e3b14b4_clevis_nominal_screens.csv"
OUT_SPIGOT = HERE / "phase2e3b14b4_end_fitting_spigot_trade.csv"
OUT_OPEN = HERE / "phase2e3b14b4_open_items.csv"
OUT_SUMMARY = HERE / "phase2e3b14b4_summary.txt"


# =============================================================================
# 1. PROJECT INPUTS
# =============================================================================

ULTIMATE_FACTOR = 1.5

# Generic 7075-T6 tensile properties — gross-section material screen only.
SY_7075_T6_MPA = 505.0
SU_7075_T6_MPA = 570.0

# Isotropic von-Mises-derived pure shear screens.
# These are NOT empirical lug shear-out allowables.
TAU_Y_7075_VM_MPA = SY_7075_T6_MPA / math.sqrt(3.0)
TAU_U_7075_VM_MPA = SU_7075_T6_MPA / math.sqrt(3.0)

# 300M project screens retained from prior phases.
SY_300M_MPA = 1517.0
SU_300M_MPA = 1862.0

# Existing B14B working joint dimensions.
PIN_D_MM = 18.0
BUSHING_OD_MM = 24.0
BRACE_EYE_OD_MM = 44.0
BRACE_EYE_WIDTH_MM = 20.0
CLEVIS_EAR_T_MM = 10.0
CLEVIS_LUG_WIDTH_MM = 42.0
CLEVIS_PIN_CENTER_TO_EDGE_MM = 30.0

# Existing B14B working tube.
TUBE_OD_MM = 25.0
TUBE_WALL_MM = 3.0
TUBE_ID_MM = TUBE_OD_MM - 2.0*TUBE_WALL_MM

# Equivalent rectangular horn-root trade.
# bx is along aircraft x; hz is along aircraft z; the section normal is +y.
HORN_BX_VALUES_MM = [50, 55, 60, 65, 70, 75, 80]
HORN_HZ_VALUES_MM = [70, 75, 80, 85, 90, 95, 100, 105, 110, 115, 120]
KT_BENDING_VALUES = [1.5, 2.0, 2.5, 3.0]

# Reference-candidate selection rule.
# This does NOT freeze the geometry. It merely picks a sensible CAD/FEA starting envelope.
REFERENCE_KT = 2.5
MIN_REFERENCE_MS_LIMIT = 0.20
MIN_REFERENCE_MS_ULT = 0.10

# Short solid 300M eye-to-tube spigot/shank candidates.
SPIGOT_D_VALUES_MM = [16.0, 17.0, 18.0, 18.5, 19.0]
SPIGOT_KT_VALUES = [1.5, 2.0, 2.5]
WORKING_SPIGOT_D_MM = 18.0
WORKING_SPIGOT_KT = 2.5


# =============================================================================
# 2. HELPERS
# =============================================================================

def read_one(path: Path) -> Dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(f"Required upstream file missing: {path}")
    with path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 1:
        raise ValueError(f"{path.name}: expected one row, found {len(rows)}.")
    return rows[0]


def write_rows(path: Path, rows: List[dict], fields: List[str] | None = None):
    if not rows:
        raise ValueError(f"No rows to write: {path}")
    if fields is None:
        fields = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def ms(allowable: float, demand: float) -> float:
    return allowable / demand - 1.0


def cross(a, b):
    return (
        a[1]*b[2] - a[2]*b[1],
        a[2]*b[0] - a[0]*b[2],
        a[0]*b[1] - a[1]*b[0],
    )


# =============================================================================
# 3. READ SOURCE-CONNECTED B14A + B14B
# =============================================================================

b14a = read_one(B14A_FREEZE)
geom = read_one(B14B_GEOMETRY)

if str(b14a["superposition_pass"]).strip().lower() not in {"true", "1", "yes", "pass"}:
    raise RuntimeError("B14A superposition gate is not PASS.")

MX_ULT_SIGNED_KNM = float(b14a["combined_Mx_kNm"])
MX_ULT_ABS_KNM = abs(MX_ULT_SIGNED_KNM)
MX_LIMIT_ABS_KNM = MX_ULT_ABS_KNM / ULTIMATE_FACTOR

A_PERP_MM = float(geom["effective_arm_mm"])
A_PERP_M = A_PERP_MM / 1000.0

UX = float(geom["u_x"])
UY = float(geom["u_y"])
UZ = float(geom["u_z"])

BX_MM = float(geom["B_x_mm"])
BY_MM = float(geom["B_y_mm"])
BZ_MM = float(geom["B_z_mm"])

F_ULT_SIGNED_KN = MX_ULT_SIGNED_KNM / A_PERP_M
F_ULT_ABS_KN = abs(F_ULT_SIGNED_KN)
F_LIMIT_ABS_KN = F_ULT_ABS_KN / ULTIMATE_FACTOR

F_ULT_KN = (
    F_ULT_SIGNED_KN*UX,
    F_ULT_SIGNED_KN*UY,
    F_ULT_SIGNED_KN*UZ,
)
F_LIMIT_KN = tuple(v/ULTIMATE_FACTOR for v in F_ULT_KN)

rB_m = (BX_MM/1000.0, BY_MM/1000.0, BZ_MM/1000.0)

M_ULT_KNM = cross(rB_m, F_ULT_KN)
M_LIMIT_KNM = tuple(v/ULTIMATE_FACTOR for v in M_ULT_KNM)

FX_ULT_N = F_ULT_KN[0]*1000.0
FZ_ULT_N = F_ULT_KN[2]*1000.0
FX_LIMIT_N = F_LIMIT_KN[0]*1000.0
FZ_LIMIT_N = F_LIMIT_KN[2]*1000.0

MX_ULT_NMM = M_ULT_KNM[0]*1e6
MZ_ULT_NMM = M_ULT_KNM[2]*1e6
MX_LIMIT_NMM = M_LIMIT_KNM[0]*1e6
MZ_LIMIT_NMM = M_LIMIT_KNM[2]*1e6

V_ULT_N = math.hypot(FX_ULT_N, FZ_ULT_N)
V_LIMIT_N = math.hypot(FX_LIMIT_N, FZ_LIMIT_N)


# =============================================================================
# 4. EQUIVALENT 7075 HORN-ROOT GROSS-SECTION TRADE
# =============================================================================

horn_rows = []

for bx in HORN_BX_VALUES_MM:
    for hz in HORN_HZ_VALUES_MM:
        A = bx*hz

        Ix = bx*hz**3/12.0
        Iz = hz*bx**3/12.0

        Zx = Ix/(hz/2.0)
        Zz = Iz/(bx/2.0)

        # Absolute nominal corner bending stresses. The worst corner can see the
        # two normal-stress contributions add in magnitude.
        sig_mx_lim = abs(MX_LIMIT_NMM)/Zx
        sig_mz_lim = abs(MZ_LIMIT_NMM)/Zz
        sig_mx_ult = abs(MX_ULT_NMM)/Zx
        sig_mz_ult = abs(MZ_ULT_NMM)/Zz

        sig_nom_lim = sig_mx_lim + sig_mz_lim
        sig_nom_ult = sig_mx_ult + sig_mz_ult

        # Rectangular-section transverse-shear screen using 1.5 V/A.
        tau_lim = 1.5*V_LIMIT_N/A
        tau_ult = 1.5*V_ULT_N/A

        for kt in KT_BENDING_VALUES:
            sig_lim = kt*sig_nom_lim
            sig_ult = kt*sig_nom_ult

            vm_lim = math.sqrt(sig_lim**2 + 3.0*tau_lim**2)
            vm_ult = math.sqrt(sig_ult**2 + 3.0*tau_ult**2)

            ms_lim = ms(SY_7075_T6_MPA, vm_lim)
            ms_ult = ms(SU_7075_T6_MPA, vm_ult)

            horn_rows.append({
                "bx_mm": bx,
                "hz_mm": hz,
                "area_mm2": A,
                "Ix_mm4": Ix,
                "Iz_mm4": Iz,
                "Zx_mm3": Zx,
                "Zz_mm3": Zz,
                "Kt_bending_screen": kt,
                "sigma_Mx_limit_MPa": sig_mx_lim,
                "sigma_Mz_limit_MPa": sig_mz_lim,
                "sigma_nominal_sum_limit_MPa": sig_nom_lim,
                "tau_rect_limit_MPa": tau_lim,
                "VM_limit_MPa": vm_lim,
                "MS_generic_7075T6_yield": ms_lim,
                "sigma_Mx_ultimate_MPa": sig_mx_ult,
                "sigma_Mz_ultimate_MPa": sig_mz_ult,
                "sigma_nominal_sum_ultimate_MPa": sig_nom_ult,
                "tau_rect_ultimate_MPa": tau_ult,
                "VM_ultimate_MPa": vm_ult,
                "MS_generic_7075T6_ultimate": ms_ult,
                "gross_screen_pass": (
                    ms_lim >= 0.0 and ms_ult >= 0.0
                ),
                "note": (
                    "Equivalent solid rectangular section normal to +y. "
                    "Actual trunnion bore, head curvature, taper, fillet and local "
                    "3D load transfer are NOT represented."
                ),
            })

write_rows(OUT_HORN_TRADE, horn_rows)

# Select a non-frozen reference candidate: smallest area satisfying the reserve rule at Kt=2.5.
reference_candidates = [
    r for r in horn_rows
    if abs(r["Kt_bending_screen"] - REFERENCE_KT) < 1e-12
    and r["MS_generic_7075T6_yield"] >= MIN_REFERENCE_MS_LIMIT
    and r["MS_generic_7075T6_ultimate"] >= MIN_REFERENCE_MS_ULT
]

if not reference_candidates:
    raise RuntimeError("No horn reference candidate satisfies the requested reserve rule.")

reference = min(
    reference_candidates,
    key=lambda r: (
        r["area_mm2"],
        max(r["bx_mm"], r["hz_mm"]),
        r["hz_mm"],
    )
)

reference_row = {
    **reference,
    "selection_status": "REFERENCE_FOR_CAD_FEA_NOT_FROZEN",
    "selection_rule": (
        f"Smallest-area candidate at Kt={REFERENCE_KT:.1f} with "
        f"MS_limit>={MIN_REFERENCE_MS_LIMIT:.2f} and "
        f"MS_ultimate>={MIN_REFERENCE_MS_ULT:.2f}."
    ),
}
write_rows(OUT_HORN_REF, [reference_row])


# =============================================================================
# 5. GEAR-SIDE CLEVIS NOMINAL MATERIAL SCREENS
# =============================================================================

F_EAR_LIMIT_N = F_LIMIT_ABS_KN*1000.0/2.0
F_EAR_ULT_N = F_ULT_ABS_KN*1000.0/2.0

A_NET_MM2 = CLEVIS_EAR_T_MM*(CLEVIS_LUG_WIDTH_MM - PIN_D_MM)

ligament_mm = CLEVIS_PIN_CENTER_TO_EDGE_MM - PIN_D_MM/2.0
A_SHEAROUT_MM2 = 2.0*CLEVIS_EAR_T_MM*ligament_mm

sig_net_lim = F_EAR_LIMIT_N/A_NET_MM2
sig_net_ult = F_EAR_ULT_N/A_NET_MM2

tau_so_lim = F_EAR_LIMIT_N/A_SHEAROUT_MM2
tau_so_ult = F_EAR_ULT_N/A_SHEAROUT_MM2

p_bearing_lim = F_EAR_LIMIT_N/(PIN_D_MM*CLEVIS_EAR_T_MM)
p_bearing_ult = F_EAR_ULT_N/(PIN_D_MM*CLEVIS_EAR_T_MM)

clevis_rows = [
    {
        "check": "net_section_nominal",
        "level": "limit",
        "demand_MPa": sig_net_lim,
        "screen_allowable_MPa": SY_7075_T6_MPA,
        "margin": ms(SY_7075_T6_MPA, sig_net_lim),
        "status": "PASS_MATERIAL_SCREEN",
        "note": (
            "Generic 7075-T6 tensile-yield screen only. Hole Kt and formal lug "
            "allowable treatment remain open."
        ),
    },
    {
        "check": "net_section_nominal",
        "level": "ultimate",
        "demand_MPa": sig_net_ult,
        "screen_allowable_MPa": SU_7075_T6_MPA,
        "margin": ms(SU_7075_T6_MPA, sig_net_ult),
        "status": "PASS_MATERIAL_SCREEN",
        "note": (
            "Generic 7075-T6 tensile-strength screen only. Hole Kt and formal lug "
            "allowable treatment remain open."
        ),
    },
    {
        "check": "shear_out_nominal",
        "level": "limit",
        "demand_MPa": tau_so_lim,
        "screen_allowable_MPa": TAU_Y_7075_VM_MPA,
        "margin": ms(TAU_Y_7075_VM_MPA, tau_so_lim),
        "status": "PASS_ISOTROPIC_VM_SCREEN",
        "note": (
            "Sy/sqrt(3) is an isotropic material screen, NOT a product-form empirical "
            "lug shear-out allowable."
        ),
    },
    {
        "check": "shear_out_nominal",
        "level": "ultimate",
        "demand_MPa": tau_so_ult,
        "screen_allowable_MPa": TAU_U_7075_VM_MPA,
        "margin": ms(TAU_U_7075_VM_MPA, tau_so_ult),
        "status": "PASS_ISOTROPIC_VM_SCREEN",
        "note": (
            "Su/sqrt(3) is an isotropic material screen, NOT a product-form empirical "
            "lug shear-out allowable."
        ),
    },
    {
        "check": "projected_bearing",
        "level": "limit",
        "demand_MPa": p_bearing_lim,
        "screen_allowable_MPa": "",
        "margin": "",
        "status": "OPEN_ALLOWABLE",
        "note": "Do not compare lug bearing stress with tensile yield.",
    },
    {
        "check": "projected_bearing",
        "level": "ultimate",
        "demand_MPa": p_bearing_ult,
        "screen_allowable_MPa": "",
        "margin": "",
        "status": "OPEN_ALLOWABLE",
        "note": "Product-form/temper-specific bearing allowable is still required.",
    },
]
write_rows(OUT_CLEVIS, clevis_rows)


# =============================================================================
# 6. 300M EYE-TO-TUBE SPIGOT / SHANK TRADE
# =============================================================================

spigot_rows = []

for d in SPIGOT_D_VALUES_MM:
    A = math.pi*d**2/4.0
    sig_lim_nom = F_LIMIT_ABS_KN*1000.0/A
    sig_ult_nom = F_ULT_ABS_KN*1000.0/A

    for kt in SPIGOT_KT_VALUES:
        sig_lim = kt*sig_lim_nom
        sig_ult = kt*sig_ult_nom

        ms_lim = ms(SY_300M_MPA, sig_lim)
        ms_ult = ms(SU_300M_MPA, sig_ult)

        fit_inside_tube = d < TUBE_ID_MM
        exact_id_match = abs(d - TUBE_ID_MM) < 1e-12

        spigot_rows.append({
            "spigot_d_mm": d,
            "tube_ID_mm": TUBE_ID_MM,
            "radial_clearance_if_inserted_mm": (TUBE_ID_MM-d)/2.0,
            "Kt_axial_screen": kt,
            "sigma_limit_MPa": sig_lim,
            "MS_300M_yield": ms_lim,
            "sigma_ultimate_MPa": sig_ult,
            "MS_300M_ultimate": ms_ult,
            "strength_pass": ms_lim >= 0.0 and ms_ult >= 0.0,
            "fits_inside_tube_with_positive_clearance": fit_inside_tube,
            "exact_tube_ID_match": exact_id_match,
            "working_candidate": (
                abs(d-WORKING_SPIGOT_D_MM) < 1e-12
                and abs(kt-WORKING_SPIGOT_KT) < 1e-12
            ),
            "note": (
                "This screens the solid shank only. Weld/braze/thread/adhesive/"
                "mechanical-retention method is NOT selected or credited."
            ),
        })

write_rows(OUT_SPIGOT, spigot_rows)

working_spigot = next(
    r for r in spigot_rows
    if r["working_candidate"]
)


# =============================================================================
# 7. OPEN ITEMS
# =============================================================================

open_items = [
    {
        "item": "ACTUAL_HORN_ROOT_GEOMETRY",
        "status": "OPEN",
        "reason": (
            "Equivalent rectangular root is only a sizing envelope. Actual head radius, "
            "local bore cutout, taper and root section must come from CAD."
        ),
    },
    {
        "item": "HORN_ROOT_FILLET_KT",
        "status": "OPEN",
        "reason": (
            "Kt is swept rather than frozen. CAD/FEA must establish the actual local "
            "stress concentration."
        ),
    },
    {
        "item": "7075_LUG_BEARING_ALLOWABLE",
        "status": "OPEN",
        "reason": (
            "No product-form/temper-specific bearing allowable has been frozen. "
            "Projected bearing demand is reported only."
        ),
    },
    {
        "item": "CLEVIS_EAR_LOCAL_FEA",
        "status": "OPEN",
        "reason": (
            "Hole/contact stress, ear flexibility, root blending and pin contact require "
            "local 3D analysis."
        ),
    },
    {
        "item": "END_FITTING_JOIN_METHOD",
        "status": "OPEN",
        "reason": (
            "18 mm solid 300M spigot is a strength-screen candidate only. The method "
            "that transfers axial load into the 25x3 tube is not selected."
        ),
    },
    {
        "item": "AIRFRAME_SIDE_CLEVIS",
        "status": "OPEN",
        "reason": (
            "Airframe-side material, attachment, local structure, fasteners and load "
            "distribution are not yet defined."
        ),
    },
    {
        "item": "PHYSICAL_BRACE_ANSYS_MODEL",
        "status": "OPEN",
        "reason": (
            "SUP_BRACE_RX still must be replaced by the actual pin-ended axial brace. "
            "Journal reactions and local head stresses must then be recomputed."
        ),
    },
    {
        "item": "FATIGUE_FRACTURE_WEAR",
        "status": "OPEN",
        "reason": (
            "Static gross-section screens do not close fatigue, fracture, fretting, "
            "lubrication or wear."
        ),
    },
]
write_rows(OUT_OPEN, open_items)


# =============================================================================
# 8. SUMMARY
# =============================================================================

lines = []
emit = lines.append

emit("="*126)
emit(" PHASE 2E3-B14B-4 V0.1 — HORN ROOT / CLEVIS / END-FITTING DETAIL TRADE")
emit("="*126)
emit("")
emit("SOURCE CONNECTION")
emit("-"*126)
emit(f"B14A freeze:      {B14A_FREEZE}")
emit(f"B14B geometry:    {B14B_GEOMETRY}")
emit(f"Frozen B14A Mx:   {MX_ULT_SIGNED_KNM:+.9f} kN*m")
emit(f"B14B a_perp:      {A_PERP_MM:.6f} mm")
emit("")

emit("PHYSICAL BRACE / HORN INTERFACE DEMAND")
emit("-"*126)
emit(f"Ultimate brace axial force: {F_ULT_SIGNED_KN:+.6f} kN")
emit(f"Gear-pin force [Fx,Fy,Fz]:  [{F_ULT_KN[0]:+.6f}, {F_ULT_KN[1]:+.6f}, {F_ULT_KN[2]:+.6f}] kN")
emit(f"Moment at trunnion center:   [Mx,My,Mz] = [{M_ULT_KNM[0]:+.6f}, {M_ULT_KNM[1]:+.6f}, {M_ULT_KNM[2]:+.6f}] kN*m")
emit("")
emit("The root trade uses these FULL interface moments and therefore does not require an invented y-direction head radius.")
emit("")

emit("7075-T6 GROSS-SECTION SCREEN")
emit("-"*126)
emit(f"Generic screen properties: Sy={SY_7075_T6_MPA:.1f} MPa, Su={SU_7075_T6_MPA:.1f} MPa")
emit("These are tensile material screens only; they are NOT lug bearing/certification allowables.")
emit("")
emit(f"Reference Kt:                 {REFERENCE_KT:.2f}")
emit(f"Reference reserve rule:       MS_limit >= {MIN_REFERENCE_MS_LIMIT:.2f}, MS_ultimate >= {MIN_REFERENCE_MS_ULT:.2f}")
emit(f"Reference equivalent section: bx={reference['bx_mm']:.1f} mm x hz={reference['hz_mm']:.1f} mm")
emit(f"Reference area:               {reference['area_mm2']:.1f} mm^2")
emit(f"Reference VM, limit:          {reference['VM_limit_MPa']:.3f} MPa")
emit(f"Reference yield MS:           {reference['MS_generic_7075T6_yield']:+.3f}")
emit(f"Reference VM, ultimate:       {reference['VM_ultimate_MPa']:.3f} MPa")
emit(f"Reference ultimate MS:        {reference['MS_generic_7075T6_ultimate']:+.3f}")
emit("STATUS: REFERENCE_FOR_CAD_FEA_NOT_FROZEN")
emit("")

emit("GEAR-SIDE CLEVIS NOMINAL SCREENS")
emit("-"*126)
emit(f"Ear thickness:                {CLEVIS_EAR_T_MM:.1f} mm")
emit(f"Lug width:                    {CLEVIS_LUG_WIDTH_MM:.1f} mm")
emit(f"Pin-center to free edge:      {CLEVIS_PIN_CENTER_TO_EDGE_MM:.1f} mm")
emit(f"Net-section ultimate demand:  {sig_net_ult:.3f} MPa")
emit(f"Shear-out ultimate demand:    {tau_so_ult:.3f} MPa")
emit(f"Bearing ultimate demand:      {p_bearing_ult:.3f} MPa  [ALLOWABLE OPEN]")
emit("")

emit("300M EYE-TO-TUBE SPIGOT SCREEN")
emit("-"*126)
emit(f"Tube ID:                      {TUBE_ID_MM:.3f} mm")
emit(f"Working spigot:               {WORKING_SPIGOT_D_MM:.3f} mm solid")
emit(f"Radial insertion clearance:   {working_spigot['radial_clearance_if_inserted_mm']:.3f} mm")
emit(f"Axial Kt screen:              {WORKING_SPIGOT_KT:.2f}")
emit(f"Limit stress:                 {working_spigot['sigma_limit_MPa']:.3f} MPa")
emit(f"Yield MS:                     {working_spigot['MS_300M_yield']:+.3f}")
emit(f"Ultimate stress:              {working_spigot['sigma_ultimate_MPa']:.3f} MPa")
emit(f"Ultimate MS:                  {working_spigot['MS_300M_ultimate']:+.3f}")
emit("The load-transfer/joining method remains OPEN.")
emit("")

emit("DISPOSITION")
emit("-"*126)
emit("B14B-4 provides a CAD envelope and closes several nominal strength screens without inventing unsupported lug allowables.")
emit("The equivalent horn section and 18 mm spigot are WORKING/REFERENCE geometry only, not a final freeze.")
emit("Next: convert the reference envelope into an actual horn/clevis CAD definition, then build the physical-brace ANSYS model.")
emit("")
emit("OUTPUTS")
emit("-"*126)
for p in [OUT_HORN_TRADE, OUT_HORN_REF, OUT_CLEVIS, OUT_SPIGOT, OUT_OPEN, OUT_SUMMARY]:
    emit(str(p))
emit("="*126)

report = "\n".join(lines)
OUT_SUMMARY.write_text(report, encoding="utf-8")
print(report)
