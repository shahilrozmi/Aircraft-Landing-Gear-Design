"""
Landing_Gear_Design_Project
PHASE 2E3-B14B-7 V0.1 — CURVED-BOSS SADDLE-ROOT REINFORCEMENT TRADE

PURPOSE
-------
Convert the B14B horn-root concept from an impossible full rectangular section
inside the existing Ø106 x 78 upper boss into a more physical local reinforcement
trade tied to the actual curved B13C boss.

INPUTS
------
phase2e3b14a_freeze_record.csv
phase2e3b14b_working_geometry.csv
current_design/phase2e3b13c_geometry_validation.txt

MODEL
-----
The upper-head boss is treated as a ØD cylinder about global Z.

For a candidate horn-root width bx in global X, the required internal chord plane is:

    y_root = sqrt(R^2 - (bx/2)^2)

This is the plane inside the boss where the original circular boss has exactly the
candidate x-width bx.

The horn pin is already fixed by B14B at y = B_y.

Therefore the actual horn cantilever lever used here is:

    l_root_to_pin = B_y - y_root

NOT the full 260 mm trunnion-center-to-pin radius.

The existing head has a Ø50 through-passage along X.  To keep the equivalent
rectangular root screen from cutting through that passage, the root plane should
remain outside the passage radius:

    y_root > D_passage / 2

A provisional practical clearance of 6 mm is also reported/used for the working
reference selection.  This is a PROJECT GEOMETRY FILTER, not a regulatory rule.

STRENGTH SCREEN
---------------
The candidate root is screened as an equivalent solid rectangular 7075-T6 section,
normal to global +Y, using:
    Kt = 3.0 on bending normal stress
    rectangular transverse shear = 1.5 V/A
    von Mises combination

Generic 7075-T6 tensile properties:
    Sy = 505 MPa
    Su = 570 MPa

These are gross-section material screens only, NOT lug-bearing or certification
allowables.

REFERENCE-SELECTION RULE
------------------------
A WORKING CAD/FEA reference is selected only from candidates that satisfy:
    - no passage intersection
    - >= 6 mm root-plane clearance from Ø50 passage radius
    - MS_limit >= +0.20
    - MS_ultimate >= +0.20

Among those, choose:
    1) minimum added vertical height beyond the existing 78 mm boss,
    2) then minimum gross section area,
    3) then minimum embed depth.

This is a practical project selection rule, not a certification rule.

OUTPUTS
-------
phase2e3b14b7_saddle_root_trade.csv
phase2e3b14b7_reference_candidate.csv
phase2e3b14b7_geometry_handoff.csv
phase2e3b14b7_open_items.csv
phase2e3b14b7_summary.txt
"""

from __future__ import annotations

import csv
import math
import re
from pathlib import Path


HERE = Path(__file__).resolve().parent

B14A_FREEZE = HERE / "phase2e3b14a_freeze_record.csv"
B14B_GEOM = HERE / "phase2e3b14b_working_geometry.csv"

VALIDATION_CANDIDATES = [
    HERE / "current_design" / "phase2e3b13c_geometry_validation.txt",
    HERE / "phase2e3b13c_geometry_validation.txt",
]

OUT_TRADE = HERE / "phase2e3b14b7_saddle_root_trade.csv"
OUT_REFERENCE = HERE / "phase2e3b14b7_reference_candidate.csv"
OUT_HANDOFF = HERE / "phase2e3b14b7_geometry_handoff.csv"
OUT_OPEN = HERE / "phase2e3b14b7_open_items.csv"
OUT_SUMMARY = HERE / "phase2e3b14b7_summary.txt"


# =============================================================================
# 1. SCREENING / SELECTION INPUTS
# =============================================================================

ULTIMATE_FACTOR = 1.5

KT_BENDING = 3.0

SY_7075_T6_MPA = 505.0
SU_7075_T6_MPA = 570.0

MIN_PASSAGE_CLEARANCE_MM = 6.0

MIN_MS_LIMIT = 0.20
MIN_MS_ULTIMATE = 0.20

# Candidate root widths/heights.
ROOT_BX_VALUES_MM = [70, 75, 80, 85, 90, 92]
ROOT_HZ_VALUES_MM = [78, 80, 85, 90, 95, 100, 105, 110]


# =============================================================================
# 2. HELPERS
# =============================================================================

def read_one_csv(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Missing required source: {path}")
    with path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 1:
        raise ValueError(f"{path.name}: expected one row, got {len(rows)}")
    return rows[0]


def write_csv(path: Path, rows):
    if not rows:
        raise ValueError(f"No rows to write: {path}")
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def cross(a, b):
    return (
        a[1]*b[2] - a[2]*b[1],
        a[2]*b[0] - a[0]*b[2],
        a[0]*b[1] - a[1]*b[0],
    )


def find_validation_file():
    for p in VALIDATION_CANDIDATES:
        if p.exists():
            return p

    for folder in [HERE / "current_design", HERE]:
        if folder.exists():
            matches = sorted(folder.glob("phase2e3b13c_geometry_validation*.txt"))
            if matches:
                return matches[0]

    raise FileNotFoundError(
        "Could not find phase2e3b13c_geometry_validation.txt."
    )


def parse_validation(path: Path):
    text = path.read_text(encoding="utf-8-sig", errors="replace")

    boss = re.search(
        r"Upper-head outer boss:\s*Ø?\s*([0-9.]+)\s*mm\s*x\s*([0-9.]+)\s*mm\s*high",
        text
    )
    passage = re.search(
        r"Head passage:\s*Ø?\s*([0-9.]+)\s*mm\s*THROUGH",
        text
    )

    if not boss or not passage:
        raise ValueError(
            "Could not parse upper-head boss or head-passage dimensions "
            "from B13C geometry validation."
        )

    return {
        "boss_diameter_mm": float(boss.group(1)),
        "boss_height_mm": float(boss.group(2)),
        "passage_diameter_mm": float(passage.group(1)),
    }


def section_screen(
    bx_mm,
    hz_mm,
    Mx_Nmm,
    Mz_Nmm,
    V_N,
    Kt,
):
    A = bx_mm * hz_mm

    Ix = bx_mm * hz_mm**3 / 12.0
    Iz = hz_mm * bx_mm**3 / 12.0

    Zx = Ix / (hz_mm / 2.0)
    Zz = Iz / (bx_mm / 2.0)

    sig_mx = abs(Mx_Nmm) / Zx
    sig_mz = abs(Mz_Nmm) / Zz

    sig_b = Kt * (sig_mx + sig_mz)
    tau = 1.5 * V_N / A

    vm = math.sqrt(sig_b**2 + 3.0*tau**2)

    return {
        "area_mm2": A,
        "Ix_mm4": Ix,
        "Iz_mm4": Iz,
        "Zx_mm3": Zx,
        "Zz_mm3": Zz,
        "sigma_Mx_nominal_MPa": sig_mx,
        "sigma_Mz_nominal_MPa": sig_mz,
        "sigma_bending_after_Kt_MPa": sig_b,
        "tau_rect_MPa": tau,
        "VM_MPa": vm,
    }


# =============================================================================
# 3. SOURCE CONNECTION
# =============================================================================

b14a = read_one_csv(B14A_FREEZE)
geom = read_one_csv(B14B_GEOM)
validation_path = find_validation_file()
head = parse_validation(validation_path)

if str(b14a["superposition_pass"]).strip().lower() not in {
    "true", "1", "yes", "pass"
}:
    raise RuntimeError("B14A superposition gate is not PASS.")


boss_D_mm = head["boss_diameter_mm"]
boss_R_mm = boss_D_mm / 2.0
boss_H_mm = head["boss_height_mm"]

passage_D_mm = head["passage_diameter_mm"]
passage_R_mm = passage_D_mm / 2.0


Mx_ult_kNm = float(b14a["combined_Mx_kNm"])

a_perp_m = float(geom["effective_arm_mm"]) / 1000.0

ux = float(geom["u_x"])
uy = float(geom["u_y"])
uz = float(geom["u_z"])

Bx_mm = float(geom["B_x_mm"])
By_mm = float(geom["B_y_mm"])
Bz_mm = float(geom["B_z_mm"])

Fbrace_ult_kN = Mx_ult_kNm / a_perp_m

F_ult_kN = (
    Fbrace_ult_kN * ux,
    Fbrace_ult_kN * uy,
    Fbrace_ult_kN * uz,
)

Fx_ult_kN = F_ult_kN[0]
Fz_ult_kN = F_ult_kN[2]

V_ult_N = math.hypot(Fx_ult_kN, Fz_ult_kN) * 1000.0
V_limit_N = V_ult_N / ULTIMATE_FACTOR


# =============================================================================
# 4. CURVED-BOSS SADDLE ROOT TRADE
# =============================================================================

rows = []

for bx_mm in ROOT_BX_VALUES_MM:

    if bx_mm >= boss_D_mm:
        continue

    half_bx = bx_mm / 2.0

    # Original boss chord geometry.
    y_root_mm = math.sqrt(
        boss_R_mm**2 - half_bx**2
    )

    embed_depth_from_tangent_mm = (
        boss_R_mm - y_root_mm
    )

    passage_clearance_mm = (
        y_root_mm - passage_R_mm
    )

    no_passage_intersection = (
        passage_clearance_mm >= 0.0
    )

    clearance_filter_pass = (
        passage_clearance_mm
        >= MIN_PASSAGE_CLEARANCE_MM
    )

    root_to_pin_lever_mm = (
        By_mm - y_root_mm
    )

    if root_to_pin_lever_mm <= 0.0:
        raise RuntimeError(
            "Candidate root plane lies outboard of horn pin."
        )

    lever_m = root_to_pin_lever_mm / 1000.0

    # Root moments from physical brace force.
    # r = [0, lever, 0]
    # M = r x F
    Mx_root_ult_kNm = (
        lever_m * Fz_ult_kN
    )

    Mz_root_ult_kNm = (
        -lever_m * Fx_ult_kN
    )

    Mx_root_limit_kNm = (
        Mx_root_ult_kNm / ULTIMATE_FACTOR
    )

    Mz_root_limit_kNm = (
        Mz_root_ult_kNm / ULTIMATE_FACTOR
    )

    for hz_mm in ROOT_HZ_VALUES_MM:

        added_height_total_mm = max(
            0.0,
            hz_mm - boss_H_mm,
        )

        symmetric_extension_each_side_mm = (
            added_height_total_mm / 2.0
        )

        lim = section_screen(
            bx_mm,
            hz_mm,
            Mx_root_limit_kNm * 1e6,
            Mz_root_limit_kNm * 1e6,
            V_limit_N,
            KT_BENDING,
        )

        ult = section_screen(
            bx_mm,
            hz_mm,
            Mx_root_ult_kNm * 1e6,
            Mz_root_ult_kNm * 1e6,
            V_ult_N,
            KT_BENDING,
        )

        ms_limit = (
            SY_7075_T6_MPA
            / lim["VM_MPa"]
            - 1.0
        )

        ms_ultimate = (
            SU_7075_T6_MPA
            / ult["VM_MPa"]
            - 1.0
        )

        reserve_pass = (
            ms_limit >= MIN_MS_LIMIT
            and ms_ultimate >= MIN_MS_ULTIMATE
        )

        reference_eligible = (
            no_passage_intersection
            and clearance_filter_pass
            and reserve_pass
        )

        rows.append({
            "bx_mm": bx_mm,
            "hz_mm": hz_mm,
            "gross_area_mm2": bx_mm * hz_mm,

            "boss_diameter_mm": boss_D_mm,
            "boss_height_mm": boss_H_mm,
            "passage_diameter_mm": passage_D_mm,

            "root_plane_y_mm": y_root_mm,
            "embed_depth_from_outer_tangent_mm": embed_depth_from_tangent_mm,
            "passage_clearance_from_root_plane_mm": passage_clearance_mm,

            "no_passage_intersection": no_passage_intersection,
            "clearance_filter_min_mm": MIN_PASSAGE_CLEARANCE_MM,
            "clearance_filter_pass": clearance_filter_pass,

            "root_to_pin_lever_mm": root_to_pin_lever_mm,

            "Mx_root_limit_kNm": Mx_root_limit_kNm,
            "Mz_root_limit_kNm": Mz_root_limit_kNm,
            "Mx_root_ultimate_kNm": Mx_root_ult_kNm,
            "Mz_root_ultimate_kNm": Mz_root_ult_kNm,

            "Kt_bending": KT_BENDING,

            "VM_limit_MPa": lim["VM_MPa"],
            "MS_limit_generic_7075T6_yield": ms_limit,

            "VM_ultimate_MPa": ult["VM_MPa"],
            "MS_ultimate_generic_7075T6_strength": ms_ultimate,

            "added_height_total_beyond_existing_boss_mm": added_height_total_mm,
            "symmetric_extension_each_side_mm": symmetric_extension_each_side_mm,

            "reserve_pass": reserve_pass,
            "reference_eligible": reference_eligible,

            "note": (
                "Equivalent solid saddle-root rectangle at the boss chord plane. "
                "Actual fillet/taper/contact geometry still requires CAD/FEA."
            ),
        })


write_csv(OUT_TRADE, rows)


# =============================================================================
# 5. WORKING REFERENCE SELECTION
# =============================================================================

eligible = [
    r for r in rows
    if r["reference_eligible"]
]

if not eligible:
    raise RuntimeError(
        "No saddle-root candidate satisfies the working selection criteria."
    )

reference = min(
    eligible,
    key=lambda r: (
        r[
            "added_height_total_beyond_existing_boss_mm"
        ],
        r["gross_area_mm2"],
        r[
            "embed_depth_from_outer_tangent_mm"
        ],
    ),
)

reference_row = {
    **reference,
    "selection_status":
        "WORKING_CAD_FEA_REFERENCE_NOT_FROZEN",
    "selection_rule": (
        "Eligible if no passage intersection, "
        f">={MIN_PASSAGE_CLEARANCE_MM:.1f} mm passage clearance, "
        f"MS_limit>={MIN_MS_LIMIT:.2f}, "
        f"MS_ultimate>={MIN_MS_ULTIMATE:.2f}; "
        "then minimize added height, area, embed depth."
    ),
}

write_csv(
    OUT_REFERENCE,
    [reference_row],
)


# =============================================================================
# 6. CAD GEOMETRY HANDOFF
# =============================================================================

handoff = [{
    "parameter": "horn_root_equivalent_width_x",
    "value": reference["bx_mm"],
    "units": "mm",
    "classification": "WORKING_NOT_FROZEN",
    "note": "Equivalent x-width at root chord plane.",
}, {
    "parameter": "horn_root_equivalent_height_z",
    "value": reference["hz_mm"],
    "units": "mm",
    "classification": "WORKING_NOT_FROZEN",
    "note": "Equivalent z-height centered about trunnion axis for first CAD pass.",
}, {
    "parameter": "horn_root_plane_y_from_trunnion_center",
    "value": reference["root_plane_y_mm"],
    "units": "mm",
    "classification": "DERIVED_FROM_B13C_BOSS",
    "note": "Inside curved Ø106 boss; produces requested x chord width.",
}, {
    "parameter": "horn_root_embed_depth_from_outer_tangent",
    "value": reference[
        "embed_depth_from_outer_tangent_mm"
    ],
    "units": "mm",
    "classification": "DERIVED_FROM_B13C_BOSS",
    "note": "Outer tangent is y=+53 mm.",
}, {
    "parameter": "passage_clearance_at_root_plane",
    "value": reference[
        "passage_clearance_from_root_plane_mm"
    ],
    "units": "mm",
    "classification": "DERIVED_FROM_B13C_PASSAGE",
    "note": "Clearance in y between root plane and Ø50 passage radius.",
}, {
    "parameter": "added_height_total",
    "value": reference[
        "added_height_total_beyond_existing_boss_mm"
    ],
    "units": "mm",
    "classification": "WORKING_REINFORCEMENT_ENVELOPE",
    "note": "Total root height beyond the existing 78 mm boss.",
}, {
    "parameter": "added_height_each_side_if_centered",
    "value": reference[
        "symmetric_extension_each_side_mm"
    ],
    "units": "mm",
    "classification": "WORKING_REINFORCEMENT_ENVELOPE",
    "note": "Initial symmetric CAD assumption; may be redistributed after packaging review.",
}, {
    "parameter": "gear_side_pin_y",
    "value": By_mm,
    "units": "mm",
    "classification": "SOURCE_B14B",
    "note": "Existing physical-brace pin center.",
}, {
    "parameter": "root_to_pin_lever",
    "value": reference[
        "root_to_pin_lever_mm"
    ],
    "units": "mm",
    "classification": "DERIVED",
    "note": "Actual horn cantilever lever from root chord plane to pin center.",
}]

write_csv(
    OUT_HANDOFF,
    handoff,
)


# =============================================================================
# 7. OPEN ITEMS
# =============================================================================

open_items = [{
    "item": "ROOT_FILLET_TAPER",
    "status": "OPEN",
    "reason": (
        "Kt=3.0 remains a screening assumption. "
        "Actual blended root geometry must be designed and analyzed."
    ),
}, {
    "item": "LOCAL_PASSAGE_LIGAMENT_3D",
    "status": "OPEN",
    "reason": (
        "Root-plane clearance is geometric only. "
        "3D interaction with Ø50 passage, bronze seat and head curvature requires FEA."
    ),
}, {
    "item": "VERTICAL_REINFORCEMENT_PACKAGING",
    "status": "OPEN",
    "reason": (
        "Added root height is centered for the first CAD pass only. "
        "Actual top/bottom split should follow available head/barrel packaging."
    ),
}, {
    "item": "CLEVIS_INTEGRATION",
    "status": "OPEN",
    "reason": (
        "Equivalent root section does not yet include the two clevis ears, "
        "their root blending, or ear bending."
    ),
}, {
    "item": "LUG_BEARING_ALLOWABLE",
    "status": "OPEN",
    "reason": (
        "Product-form-specific 7075 lug bearing allowable remains unfrozen."
    ),
}, {
    "item": "PHYSICAL_BRACE_FEA",
    "status": "OPEN",
    "reason": (
        "Final confirmation requires actual horn, clevis, pin, brace and "
        "journal reactions in ANSYS after SUP_BRACE_RX is removed."
    ),
}]

write_csv(
    OUT_OPEN,
    open_items,
)


# =============================================================================
# 8. SUMMARY
# =============================================================================

lines = []
emit = lines.append

emit("=" * 128)
emit(" PHASE 2E3-B14B-7 V0.1 — CURVED-BOSS SADDLE-ROOT REINFORCEMENT TRADE")
emit("=" * 128)
emit("")
emit("SOURCE CONNECTION")
emit("-" * 128)
emit(f"B14A freeze:       {B14A_FREEZE}")
emit(f"B14B geometry:     {B14B_GEOM}")
emit(f"B13C validation:   {validation_path}")
emit("")
emit("B13C HEAD GEOMETRY")
emit("-" * 128)
emit(
    f"Outer boss:        Ø{boss_D_mm:.3f} mm x "
    f"{boss_H_mm:.3f} mm high"
)
emit(
    f"Head passage:      Ø{passage_D_mm:.3f} mm through"
)
emit("")
emit("PHYSICAL BRACE LOAD")
emit("-" * 128)
emit(
    f"Ultimate brace force: {Fbrace_ult_kN:+.6f} kN"
)
emit(
    f"Fx={Fx_ult_kN:+.6f} kN, "
    f"Fz={Fz_ult_kN:+.6f} kN"
)
emit("")
emit("WORKING SADDLE-ROOT REFERENCE — NOT FROZEN")
emit("-" * 128)
emit(
    f"Equivalent root section: "
    f"{reference['bx_mm']:.1f} mm x "
    f"{reference['hz_mm']:.1f} mm"
)
emit(
    f"Root chord plane y:       "
    f"{reference['root_plane_y_mm']:.3f} mm"
)
emit(
    f"Embed below y=+53 tangent:"
    f" {reference['embed_depth_from_outer_tangent_mm']:.3f} mm"
)
emit(
    f"Clearance to Ø50 passage: "
    f"{reference['passage_clearance_from_root_plane_mm']:.3f} mm"
)
emit(
    f"Root-to-pin lever:         "
    f"{reference['root_to_pin_lever_mm']:.3f} mm"
)
emit(
    f"Added root height total:   "
    f"{reference['added_height_total_beyond_existing_boss_mm']:.3f} mm"
)
emit(
    f"If centered:               "
    f"{reference['symmetric_extension_each_side_mm']:.3f} mm each side"
)
emit("")
emit("ROOT RESULTANTS")
emit("-" * 128)
emit(
    f"Mx root ultimate: "
    f"{reference['Mx_root_ultimate_kNm']:+.6f} kN*m"
)
emit(
    f"Mz root ultimate: "
    f"{reference['Mz_root_ultimate_kNm']:+.6f} kN*m"
)
emit("")
emit("7075-T6 GROSS-SECTION SCREEN")
emit("-" * 128)
emit(
    f"Kt:                   "
    f"{reference['Kt_bending']:.2f}"
)
emit(
    f"VM limit:             "
    f"{reference['VM_limit_MPa']:.3f} MPa"
)
emit(
    f"MS limit:             "
    f"{reference['MS_limit_generic_7075T6_yield']:+.3f}"
)
emit(
    f"VM ultimate:          "
    f"{reference['VM_ultimate_MPa']:.3f} MPa"
)
emit(
    f"MS ultimate:          "
    f"{reference['MS_ultimate_generic_7075T6_strength']:+.3f}"
)
emit("")
emit("DISPOSITION")
emit("-" * 128)
emit(
    "A local reinforced saddle-root concept is geometrically and "
    "statically plausible under the current conservative screen."
)
emit(
    "The selected section is a WORKING CAD/FEA reference only. "
    "It is not a final structural freeze."
)
emit(
    "Next step: create the actual blended horn/clevis geometry from this "
    "handoff and then replace SUP_BRACE_RX with the physical brace in ANSYS."
)
emit("")
emit("OUTPUTS")
emit("-" * 128)
for p in [
    OUT_TRADE,
    OUT_REFERENCE,
    OUT_HANDOFF,
    OUT_OPEN,
    OUT_SUMMARY,
]:
    emit(str(p))
emit("=" * 128)

report = "\n".join(lines)
OUT_SUMMARY.write_text(
    report,
    encoding="utf-8",
)
print(report)
