"""
Landing_Gear_Design_Project
PHASE 2E3-B14B-10 V0.1 — PHYSICAL BRACE FEA HANDOFF

PURPOSE
-------
Prepare a source-connected handoff for replacing the artificial ANSYS anti-rotation
support SUP_BRACE_RX with the actual pin-ended two-force brace.

This script DOES NOT solve the ANSYS model. It:
1) reads the frozen B14A reaction result,
2) reads the B14B physical-brace geometry,
3) verifies the B14B-9 CAD geometry gate,
4) reconstructs the physical B->A brace line,
5) predicts the axial brace force required by moment equilibrium,
6) creates an ANSYS setup / result-extraction checklist.

No governing load, brace force, or brace coordinate is copied from chat.

REQUIRED INPUTS
---------------
phase2e3b14a_freeze_record.csv
phase2e3b14b_working_geometry.csv
phase2e3b14b8_cad_handoff.csv
phase2e3b14b8_joint_frame.csv
phase2e3b14b9_geometry_definition.csv
phase2e3b14b9_geometry_validation.csv
phase2e3b14b9_head_horn_clevis_v01.step

OPTIONAL INPUTS FOR BRACE SECTION / STIFFNESS
--------------------------------------------
phase2e3b14b_member_joint_checks.csv
phase2_upper_brace_sizing.csv

If an authoritative tube free length / OD / wall / E cannot be found, the geometry and
load-path handoff still runs, but stiffness-related fields are left OPEN.

OUTPUTS
-------
phase2e3b14b10_fea_handoff.csv
phase2e3b14b10_load_path_checks.csv
phase2e3b14b10_open_items.csv
phase2e3b14b10_ansys_setup.txt
phase2e3b14b10_summary.txt
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent

B14A_FREEZE = HERE / "phase2e3b14a_freeze_record.csv"
B14B_GEOM = HERE / "phase2e3b14b_working_geometry.csv"
B14B8_HANDOFF = HERE / "phase2e3b14b8_cad_handoff.csv"
B14B8_FRAME = HERE / "phase2e3b14b8_joint_frame.csv"
B14B9_GEOM = HERE / "phase2e3b14b9_geometry_definition.csv"
B14B9_VALID = HERE / "phase2e3b14b9_geometry_validation.csv"
B14B9_STEP = HERE / "phase2e3b14b9_head_horn_clevis_v01.step"

OPTIONAL_SECTION_FILES = [
    HERE / "phase2e3b14b_member_joint_checks.csv",
    HERE / "phase2_upper_brace_sizing.csv",
]

OUT_HANDOFF = HERE / "phase2e3b14b10_fea_handoff.csv"
OUT_CHECKS = HERE / "phase2e3b14b10_load_path_checks.csv"
OUT_OPEN = HERE / "phase2e3b14b10_open_items.csv"
OUT_SETUP = HERE / "phase2e3b14b10_ansys_setup.txt"
OUT_SUMMARY = HERE / "phase2e3b14b10_summary.txt"

TOL = 1e-9
GEOM_TOL_MM = 1e-3
FORCE_TARGET_BAND = 0.05  # diagnostic band only, not a certification criterion


# =============================================================================
# HELPERS
# =============================================================================

def read_rows(path: Path) -> List[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Required input missing: {path}")
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def read_one(path: Path) -> dict:
    rows = read_rows(path)
    if len(rows) != 1:
        raise ValueError(f"{path.name}: expected one row, found {len(rows)}")
    return rows[0]


def write_rows(path: Path, rows: List[dict]):
    if not rows:
        rows = [{"status": "NONE"}]
    fields = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def f(x) -> float:
    return float(str(x).strip())


def truthy(x) -> bool:
    return str(x).strip().lower() in {"true", "1", "yes", "y", "pass"}


def norm(v):
    return math.sqrt(sum(c*c for c in v))


def dot(a, b):
    return sum(a[i]*b[i] for i in range(3))


def cross(a, b):
    return (
        a[1]*b[2] - a[2]*b[1],
        a[2]*b[0] - a[0]*b[2],
        a[0]*b[1] - a[1]*b[0],
    )


def add(a, b):
    return tuple(a[i] + b[i] for i in range(3))


def sub(a, b):
    return tuple(a[i] - b[i] for i in range(3))


def scale(a, s):
    return tuple(a[i]*s for i in range(3))


def dist(a, b):
    return norm(sub(a, b))


def parse_xyz_string(s: str) -> Tuple[float, float, float]:
    vals = [float(x.strip()) for x in str(s).split(",")]
    if len(vals) != 3:
        raise ValueError(f"Expected 3 comma-separated values, got: {s}")
    return tuple(vals)


def row_by_parameter(rows: List[dict], key: str) -> dict:
    matches = [r for r in rows if str(r.get("parameter", "")).strip() == key]
    if len(matches) != 1:
        raise ValueError(f"Expected one parameter '{key}', found {len(matches)}")
    return matches[0]


def row_by_axis(rows: List[dict], key: str) -> dict:
    matches = [r for r in rows if str(r.get("axis", "")).strip() == key]
    if len(matches) != 1:
        raise ValueError(f"Expected one axis '{key}', found {len(matches)}")
    return matches[0]


def xyz_from_parameter(rows: List[dict], key: str) -> Tuple[float, float, float]:
    r = row_by_parameter(rows, key)
    return (f(r["x"]), f(r["y"]), f(r["z"]))


def xyz_from_axis(rows: List[dict], key: str) -> Tuple[float, float, float]:
    r = row_by_axis(rows, key)
    return (f(r["x"]), f(r["y"]), f(r["z"]))


def value_from_geomdef(rows: List[dict], feature: str, parameter: str):
    matches = [
        r for r in rows
        if str(r.get("feature", "")).strip() == feature
        and str(r.get("parameter", "")).strip() == parameter
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Expected one geometry-definition row for {feature}/{parameter}, "
            f"found {len(matches)}"
        )
    return matches[0]["value"]


def add_check(rows, name, actual, expected, units="-", tol=TOL, note=""):
    try:
        passed = abs(float(actual) - float(expected)) <= tol
    except Exception:
        passed = actual == expected
    rows.append({
        "check": name,
        "actual": actual,
        "expected": expected,
        "units": units,
        "tolerance": tol,
        "status": "PASS" if passed else "FAIL",
        "note": note,
    })


def add_bool_check(rows, name, passed, note=""):
    rows.append({
        "check": name,
        "actual": bool(passed),
        "expected": True,
        "units": "-",
        "tolerance": "-",
        "status": "PASS" if passed else "FAIL",
        "note": note,
    })


def find_numeric_in_row(row: dict, aliases: List[str]) -> Optional[float]:
    for key in aliases:
        if key in row:
            val = str(row[key]).strip()
            if val and val.lower() not in {"nan", "none"}:
                try:
                    return float(val)
                except ValueError:
                    pass
    return None


def selected_rows(rows: List[dict]) -> List[dict]:
    flag_cols = [
        "working_candidate", "selected", "working", "reference_candidate",
        "working_reference", "selected_reference", "eligible_reference"
    ]
    out = []
    for r in rows:
        for c in flag_cols:
            if c in r and truthy(r[c]):
                out.append(r)
                break
    return out


def source_brace_section_and_length(
    geom_row: dict,
) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float], str]:
    """
    Returns:
        length_mm, OD_mm, wall_mm, E_MPa, source_note
    """
    L_aliases = [
        "link_free_length_mm", "pin_to_pin_length_mm", "brace_length_mm",
        "free_length_mm", "member_length_mm", "L_mm"
    ]
    OD_aliases = [
        "tube_OD_mm", "brace_tube_OD_mm", "OD_mm", "outer_diameter_mm"
    ]
    t_aliases = [
        "tube_wall_mm", "brace_tube_wall_mm", "wall_mm", "wall_thickness_mm"
    ]
    E_aliases = [
        "E_MPa", "elastic_modulus_MPa", "E_300M_MPa"
    ]

    L = find_numeric_in_row(geom_row, L_aliases)
    OD = find_numeric_in_row(geom_row, OD_aliases)
    wall = find_numeric_in_row(geom_row, t_aliases)
    E = find_numeric_in_row(geom_row, E_aliases)

    if all(v is not None for v in [L, OD, wall, E]):
        return L, OD, wall, E, B14B_GEOM.name

    for path in OPTIONAL_SECTION_FILES:
        if not path.exists():
            continue
        rows = read_rows(path)
        candidates = selected_rows(rows)
        if not candidates:
            candidates = rows if len(rows) == 1 else []

        for r in candidates:
            L2 = L if L is not None else find_numeric_in_row(r, L_aliases)
            OD2 = OD if OD is not None else find_numeric_in_row(r, OD_aliases)
            wall2 = wall if wall is not None else find_numeric_in_row(r, t_aliases)
            E2 = E if E is not None else find_numeric_in_row(r, E_aliases)
            if any(v is not None for v in [L2, OD2, wall2, E2]):
                L, OD, wall, E = L2, OD2, wall2, E2
                if all(v is not None for v in [L, OD, wall, E]):
                    return L, OD, wall, E, path.name

    return L, OD, wall, E, "PARTIAL_SOURCE_DISCOVERY"


# =============================================================================
# READ SOURCES
# =============================================================================

for p in [
    B14A_FREEZE, B14B_GEOM, B14B8_HANDOFF, B14B8_FRAME,
    B14B9_GEOM, B14B9_VALID, B14B9_STEP
]:
    if not p.exists():
        raise FileNotFoundError(f"Required B14B-10 source missing: {p}")

b14a = read_one(B14A_FREEZE)
b14b = read_one(B14B_GEOM)
b8 = read_rows(B14B8_HANDOFF)
frame = read_rows(B14B8_FRAME)
g9 = read_rows(B14B9_GEOM)
v9 = read_rows(B14B9_VALID)

checks = []

# Frozen B14A gate
add_bool_check(
    checks,
    "B14A_superposition_gate",
    truthy(b14a["superposition_pass"]),
    "B14A must remain source-connected and superposition-validated."
)
if not truthy(b14a["superposition_pass"]):
    write_rows(OUT_CHECKS, checks)
    raise RuntimeError("B14A superposition gate is not PASS.")

Mx_ult_kNm = f(b14a["combined_Mx_kNm"])
governing_case = str(
    b14a.get("governing_case", b14a.get("case", "B14A_COMBINED_GOVERNING"))
).strip()

# B14B working geometry
a_perp_mm = f(b14b["effective_arm_mm"])
u_b14b = (f(b14b["u_x"]), f(b14b["u_y"]), f(b14b["u_z"]))
B_local_b14b = (f(b14b["B_x_mm"]), f(b14b["B_y_mm"]), f(b14b["B_z_mm"]))

# B14B-8
u_b8 = xyz_from_axis(frame, "brace_axis_u_b")
e_p = xyz_from_axis(frame, "pin_axis_e_p")
B_local_b8 = xyz_from_parameter(b8, "pin_center")

# B14B-9
O_global = parse_xyz_string(value_from_geomdef(g9, "coordinate_frame", "trunnion_center_global"))
B_global_g9 = parse_xyz_string(value_from_geomdef(g9, "pin_bore", "center_global"))
pin_d_mm = float(value_from_geomdef(g9, "pin_bore", "diameter"))

# B14B-9 gate: every persisted check must pass.
g9_failures = [r for r in v9 if str(r.get("status", "")).strip().upper() != "PASS"]
add_check(checks, "B14B9_validation_fail_count", len(g9_failures), 0, "-", 0)

# Cross-source geometry consistency
for i, lab in enumerate(["x", "y", "z"]):
    add_check(
        checks, f"brace_axis_B14B_vs_B14B8_{lab}",
        u_b14b[i], u_b8[i], "-", 1e-9
    )
    add_check(
        checks, f"B_local_B14B_vs_B14B8_{lab}",
        B_local_b14b[i], B_local_b8[i], "mm", GEOM_TOL_MM
    )

B_global_reconstructed = add(O_global, B_local_b14b)
for i, lab in enumerate(["x", "y", "z"]):
    add_check(
        checks, f"B_global_transform_{lab}",
        B_global_reconstructed[i], B_global_g9[i], "mm", GEOM_TOL_MM
    )

add_check(checks, "brace_axis_norm", norm(u_b14b), 1.0, "-", 1e-9)
add_check(checks, "pin_axis_norm", norm(e_p), 1.0, "-", 1e-9)
add_check(checks, "brace_pin_axis_orthogonality", dot(u_b14b, e_p), 0.0, "-", 1e-9)

# Effective moment arm reconstructed from actual B and brace direction.
arm_vec_mm = cross(B_local_b14b, u_b14b)
a_perp_reconstructed_mm = abs(arm_vec_mm[0])
add_check(
    checks, "effective_arm_reconstruction",
    a_perp_reconstructed_mm, a_perp_mm, "mm", GEOM_TOL_MM
)

if a_perp_mm <= 0.0:
    raise ValueError("Effective arm must be positive.")

# Source-connected analytical brace demand.
F_brace_ult_kN = Mx_ult_kNm / (a_perp_mm / 1000.0)
F_B_kN = scale(u_b14b, F_brace_ult_kN)

rB_m = scale(B_local_b14b, 1.0 / 1000.0)
M_from_brace_kNm = cross(rB_m, F_B_kN)

add_check(
    checks, "physical_brace_reproduces_B14A_Mx",
    M_from_brace_kNm[0], Mx_ult_kNm, "kN*m", 1e-9
)

# Resolve source length / section.
L_mm, tube_OD_mm, tube_wall_mm, E_MPa, section_source = source_brace_section_and_length(b14b)

# If B14B working geometry already has explicit A coordinates, use those as authority.
A_alias_sets = [
    ("A_x_mm", "A_y_mm", "A_z_mm"),
    ("airframe_pin_x_mm", "airframe_pin_y_mm", "airframe_pin_z_mm"),
]
A_local = None
A_source = None
for ax, ay, az in A_alias_sets:
    if all(k in b14b and str(b14b[k]).strip() for k in (ax, ay, az)):
        A_local = (f(b14b[ax]), f(b14b[ay]), f(b14b[az]))
        A_source = f"{B14B_GEOM.name}:{ax}/{ay}/{az}"
        break

if A_local is not None:
    L_from_A_mm = dist(A_local, B_local_b14b)
    if L_mm is None:
        L_mm = L_from_A_mm
        section_source = B14B_GEOM.name
    else:
        add_check(
            checks, "brace_length_explicit_A_vs_section_source",
            L_from_A_mm, L_mm, "mm", GEOM_TOL_MM
        )
else:
    if L_mm is not None:
        A_local = add(B_local_b14b, scale(u_b14b, L_mm))
        A_source = f"derived_from_B_plus_u_times_L ({section_source})"

A_global = add(O_global, A_local) if A_local is not None else None

# Section-derived quantities if all required source values exist.
brace_area_mm2 = None
brace_ID_mm = None
axial_stiffness_N_per_mm = None
analytical_axial_extension_mm = None
analytical_axial_stress_MPa = None

if tube_OD_mm is not None and tube_wall_mm is not None:
    brace_ID_mm = tube_OD_mm - 2.0*tube_wall_mm
    if brace_ID_mm <= 0.0:
        raise ValueError("Sourced brace tube dimensions produce non-positive ID.")
    brace_area_mm2 = math.pi/4.0*(tube_OD_mm**2 - brace_ID_mm**2)
    analytical_axial_stress_MPa = abs(F_brace_ult_kN*1000.0) / brace_area_mm2

if (
    brace_area_mm2 is not None
    and E_MPa is not None
    and L_mm is not None
):
    axial_stiffness_N_per_mm = E_MPa * brace_area_mm2 / L_mm
    analytical_axial_extension_mm = (
        F_brace_ult_kN*1000.0 / axial_stiffness_N_per_mm
    )

# Source readiness checks
add_bool_check(checks, "airframe_point_A_resolved", A_local is not None)
add_bool_check(checks, "brace_length_resolved", L_mm is not None)
add_bool_check(checks, "brace_tube_OD_resolved", tube_OD_mm is not None)
add_bool_check(checks, "brace_tube_wall_resolved", tube_wall_mm is not None)
add_bool_check(checks, "brace_E_resolved", E_MPa is not None)

# Hard gate only for geometry/load-path values. Section/stiffness is allowed to remain open.
hard_gate_names = {
    "B14A_superposition_gate",
    "B14B9_validation_fail_count",
    "effective_arm_reconstruction",
    "physical_brace_reproduces_B14A_Mx",
    "airframe_point_A_resolved",
    "brace_length_resolved",
}
hard_failures = [
    r for r in checks
    if r["check"] in hard_gate_names and r["status"] == "FAIL"
]

write_rows(OUT_CHECKS, checks)

if hard_failures:
    raise RuntimeError(
        "B14B-10 hard source/geometry gate failed. "
        "Review phase2e3b14b10_load_path_checks.csv."
    )


# =============================================================================
# HANDOFF TABLE
# =============================================================================

handoff = []

def add_handoff(category, parameter, value, units, status, source, note=""):
    handoff.append({
        "category": category,
        "parameter": parameter,
        "value": value,
        "units": units,
        "status": status,
        "source": source,
        "note": note,
    })

add_handoff("model", "geometry_STEP", B14B9_STEP.name, "-", "USE", B14B9_STEP.name)
add_handoff("model", "remove_support", "SUP_BRACE_RX", "-", "REMOVE", "B14A model")
add_handoff("model", "retain_existing_combined_external_loads", True, "-", "USE", "B14A solved combined model",
            "Duplicate the solved B14A combined model; do not recreate loads from memory.")

add_handoff("load", "governing_case", governing_case, "-", "SOURCE", B14A_FREEZE.name)
add_handoff("load", "B14A_combined_Mx", Mx_ult_kNm, "kN*m", "SOURCE", B14A_FREEZE.name)
add_handoff("load", "expected_brace_axial_force_signed", F_brace_ult_kN, "kN", "PREDICTION", "B14A+B14B")
add_handoff("load", "expected_brace_force_Fx", F_B_kN[0], "kN", "PREDICTION", "B14A+B14B")
add_handoff("load", "expected_brace_force_Fy", F_B_kN[1], "kN", "PREDICTION", "B14A+B14B")
add_handoff("load", "expected_brace_force_Fz", F_B_kN[2], "kN", "PREDICTION", "B14A+B14B")
add_handoff("load", "expected_secondary_Mz_from_brace", M_from_brace_kNm[2], "kN*m", "PREDICTION", "B14A+B14B")

for lab, val in zip(["x","y","z"], B_global_g9):
    add_handoff("geometry", f"B_global_{lab}", val, "mm", "SOURCE", B14B9_GEOM.name)
for lab, val in zip(["x","y","z"], A_global):
    add_handoff("geometry", f"A_global_{lab}", val, "mm", "SOURCE_DERIVED", A_source)

for lab, val in zip(["x","y","z"], u_b14b):
    add_handoff("geometry", f"brace_axis_u_{lab}", val, "-", "SOURCE", B14B_GEOM.name)
for lab, val in zip(["x","y","z"], e_p):
    add_handoff("geometry", f"pin_axis_e_p_{lab}", val, "-", "SOURCE", B14B8_FRAME.name)

add_handoff("geometry", "effective_Mx_arm", a_perp_mm, "mm", "SOURCE", B14B_GEOM.name)
add_handoff("geometry", "pin_bore_diameter", pin_d_mm, "mm", "SOURCE", B14B9_GEOM.name)
add_handoff("geometry", "brace_pin_to_pin_length", L_mm, "mm", "SOURCE", section_source)

if tube_OD_mm is not None:
    add_handoff("brace_section", "tube_OD", tube_OD_mm, "mm", "SOURCE", section_source)
if tube_wall_mm is not None:
    add_handoff("brace_section", "tube_wall", tube_wall_mm, "mm", "SOURCE", section_source)
if brace_ID_mm is not None:
    add_handoff("brace_section", "tube_ID", brace_ID_mm, "mm", "DERIVED", section_source)
if brace_area_mm2 is not None:
    add_handoff("brace_section", "area", brace_area_mm2, "mm^2", "DERIVED", section_source)
if E_MPa is not None:
    add_handoff("brace_section", "E", E_MPa, "MPa", "SOURCE", section_source)
if axial_stiffness_N_per_mm is not None:
    add_handoff("brace_section", "axial_stiffness_EA_over_L", axial_stiffness_N_per_mm, "N/mm", "DERIVED", section_source)
if analytical_axial_extension_mm is not None:
    add_handoff("sanity", "analytical_axial_extension_at_governing_load", analytical_axial_extension_mm, "mm", "PREDICTION", "B14A+B14B")
if analytical_axial_stress_MPa is not None:
    add_handoff("sanity", "analytical_axial_stress_at_governing_load", analytical_axial_stress_MPa, "MPa", "PREDICTION", "B14A+B14B")

add_handoff(
    "diagnostic",
    "initial_brace_force_target_low",
    F_brace_ult_kN*(1.0+FORCE_TARGET_BAND) if F_brace_ult_kN < 0 else F_brace_ult_kN*(1.0-FORCE_TARGET_BAND),
    "kN", "DIAGNOSTIC_ONLY", "B14B10",
    "5% initial sanity band; not an acceptance/certification allowable."
)
add_handoff(
    "diagnostic",
    "initial_brace_force_target_high",
    F_brace_ult_kN*(1.0-FORCE_TARGET_BAND) if F_brace_ult_kN < 0 else F_brace_ult_kN*(1.0+FORCE_TARGET_BAND),
    "kN", "DIAGNOSTIC_ONLY", "B14B10",
    "5% initial sanity band; not an acceptance/certification allowable."
)

write_rows(OUT_HANDOFF, handoff)


# =============================================================================
# OPEN ITEMS
# =============================================================================

open_items = [
    {
        "item": "LOCAL_ROOT_FILLET",
        "status": "OPEN",
        "reason": "B14B-9 intentionally left the external saddle/root fillet open for local FEA-driven refinement."
    },
    {
        "item": "CLEVIS_PIN_CONTACT",
        "status": "SIMPLIFIED_FIRST_RUN",
        "reason": (
            "First physical-brace load-path run should use a deformable distributed coupling "
            "from both Ø18 bore faces to RP_BRACE_B. Explicit pin/bushing contact is a later refinement."
        )
    },
    {
        "item": "AIRFRAME_SIDE_FITTING",
        "status": "IDEALIZED",
        "reason": (
            "Point A is treated as a fixed translational anchor for the two-force member. "
            "Actual airframe lug/fitting/fasteners remain outside this local landing-gear model."
        )
    },
    {
        "item": "JOURNAL_REACTION_REDISTRIBUTION",
        "status": "MUST_BE_RECOMPUTED",
        "reason": (
            "The physical brace introduces Fx/Fz at B and secondary Mz, so journal reactions "
            "from the SUP_BRACE_RX model cannot be reused."
        )
    },
    {
        "item": "MESH_CONVERGENCE_NEW_HORN",
        "status": "REQUIRED",
        "reason": (
            "B14B-9 adds a new horn/root/clevis stress field. Reuse the old model only as the "
            "starting mesh philosophy; perform a new local convergence study before freezing stress results."
        )
    },
    {
        "item": "FATIGUE_FRETTING_WEAR_FRACTURE",
        "status": "OPEN",
        "reason": "B14B-10 is a static physical load-path FEA handoff only."
    },
]
write_rows(OUT_OPEN, open_items)


# =============================================================================
# ANSYS SETUP TEXT
# =============================================================================

def fmtv(v):
    return f"[{v[0]:+.6f}, {v[1]:+.6f}, {v[2]:+.6f}]"

setup = f"""
PHASE 2E3-B14B-10 — ANSYS PHYSICAL-BRACE FIRST-RUN SETUP
========================================================================================================================

MODEL BASIS
-----------
1. DUPLICATE the already-solved B14A COMBINED governing Static Structural model.
   Do not reconstruct the applied force/moment/pressure values from chat or memory.
2. Replace/remap the geometry to:
      {B14B9_STEP.name}
3. Retain the existing journal/support/contact definitions from the solved B14A model wherever they remain valid.
4. REMOVE / suppress only:
      SUP_BRACE_RX

PHYSICAL BRACE IDEALIZATION — FIRST LOAD-PATH RUN
-------------------------------------------------
Use a two-force axial-only member between the following GLOBAL points:

Gear-side clevis pin center B:
      {fmtv(B_global_g9)} mm

Airframe-side ideal anchor A:
      {fmtv(A_global)} mm

Brace direction u_b:
      {fmtv(u_b14b)}

Pin axis e_p:
      {fmtv(e_p)}

Pin bore:
      Ø{pin_d_mm:.6f} mm

Pin-to-pin length:
      {L_mm:.6f} mm

Recommended first-run representation:
- Create RP_BRACE_B at B.
- Scope RP_BRACE_B to BOTH cylindrical Ø18 clevis-hole surfaces.
- Use DEFORMABLE / distributed coupling behavior so the pilot point transfers the resultant
  without intentionally making the entire clevis rigid.
- Create RP_BRACE_A at A.
- Fix translations of RP_BRACE_A.
- Connect B -> A with an AXIAL-ONLY spring / truss / LINK-type member.
- Do NOT give the brace bending or torsional stiffness in this first load-path validation.

"""
if axial_stiffness_N_per_mm is not None:
    setup += f"""Source-connected axial stiffness for spring representation:
      k = EA/L = {axial_stiffness_N_per_mm:.6f} N/mm

"""
else:
    setup += """Axial stiffness:
      OPEN in this handoff because one or more section/material source values were not found.
      Use the source B14B 300M tube definition; do not invent a stiffness.

"""

if brace_area_mm2 is not None:
    setup += f"""Source-connected tube area:
      A = {brace_area_mm2:.6f} mm^2
"""
if tube_OD_mm is not None and tube_wall_mm is not None:
    setup += f"""Tube reference:
      OD = {tube_OD_mm:.6f} mm
      wall = {tube_wall_mm:.6f} mm
"""
setup += f"""
LOAD STATE
----------
Use the SAME B14A COMBINED governing external load state already present in the duplicated model.

Frozen B14A brace-support moment being physicalized:
      Mx = {Mx_ult_kNm:+.9f} kN*m

Analytical two-force-member prediction:
      Fbrace = {F_brace_ult_kN:+.6f} kN
      F_B    = {fmtv(F_B_kN)} kN
      r_B x F_B = {fmtv(M_from_brace_kNm)} kN*m

The physical brace reproduces the target Mx analytically, but it ALSO introduces translational
Fx/Fz at B and a secondary Mz. Therefore journal reactions MUST be re-solved.

RESULTS TO REQUEST
------------------
- Axial force in physical brace / spring / LINK member.
- Reaction at RP_BRACE_A.
- Resultant force transferred at RP_BRACE_B.
- Left and right journal/bearing reactions.
- Total structural force equilibrium.
- Total structural moment equilibrium about O_global.
- 7075 head/horn equivalent stress.
- Stress at saddle/root transition.
- Stress around both Ø18 clevis holes.
- Clevis-ear deformation / relative opening.
- Total deformation of head/horn.
- Contact/bearing pressure only if the chosen first-run coupling actually resolves it.

FIRST-RUN SANITY TARGET
-----------------------
Expected brace axial force from source-connected moment equilibrium:
      {F_brace_ult_kN:+.6f} kN

A ±5% band may be used ONLY as an initial modeling diagnostic:
      [{min(F_brace_ult_kN*(1-FORCE_TARGET_BAND), F_brace_ult_kN*(1+FORCE_TARGET_BAND)):+.6f},
       {max(F_brace_ult_kN*(1-FORCE_TARGET_BAND), F_brace_ult_kN*(1+FORCE_TARGET_BAND)):+.6f}] kN

If the solved force is materially outside that band, do not tune the model to force agreement.
Instead inspect:
- accidental residual rotational restraint about x,
- over-constrained journal supports,
- rigid coupling at the clevis,
- wrong brace axis / point coordinates,
- wrong load case,
- unit errors,
- brace carrying bending instead of axial load.

MESH
----
Do not freeze a new stress result from a single mesh.
Use the old converged upper-head mesh philosophy as the starting point, then perform NEW local
refinement/convergence at:
- saddle/root transition,
- throat transition,
- U-slot root,
- both Ø18 pin bores.

STATUS
------
B14B-10 is a PHYSICAL LOAD-PATH VALIDATION stage.
It is NOT final clevis contact design, final fillet design, fatigue closure, or airframe-fitting design.
========================================================================================================================
"""

OUT_SETUP.write_text(setup, encoding="utf-8")


# =============================================================================
# SUMMARY
# =============================================================================

fail_count = sum(r["status"] == "FAIL" for r in checks)
section_ready = all(v is not None for v in [tube_OD_mm, tube_wall_mm, E_MPa, brace_area_mm2, axial_stiffness_N_per_mm])

lines = []
emit = lines.append
emit("="*132)
emit(" PHASE 2E3-B14B-10 V0.1 — PHYSICAL BRACE FEA HANDOFF")
emit("="*132)
emit("")
emit("SOURCE GATES")
emit("-"*132)
emit(f"B14A superposition:                  {'PASS' if truthy(b14a['superposition_pass']) else 'FAIL'}")
emit(f"B14B-9 persisted validation fails:   {len(g9_failures)}")
emit(f"Load-path check failures:            {fail_count}")
emit("")
emit("PHYSICAL BRACE GEOMETRY")
emit("-"*132)
emit(f"O_global:                            {fmtv(O_global)} mm")
emit(f"B_global:                            {fmtv(B_global_g9)} mm")
emit(f"A_global:                            {fmtv(A_global)} mm")
emit(f"u_b:                                 {fmtv(u_b14b)}")
emit(f"e_p:                                 {fmtv(e_p)}")
emit(f"Effective Mx arm:                    {a_perp_mm:.6f} mm")
emit(f"Pin-to-pin length:                   {L_mm:.6f} mm")
emit("")
emit("SOURCE-CONNECTED LOAD-PATH PREDICTION")
emit("-"*132)
emit(f"B14A combined Mx:                    {Mx_ult_kNm:+.9f} kN*m")
emit(f"Expected signed brace force:         {F_brace_ult_kN:+.6f} kN")
emit(f"Expected gear-pin force:             {fmtv(F_B_kN)} kN")
emit(f"Moment from physical brace:          {fmtv(M_from_brace_kNm)} kN*m")
emit("")
emit("BRACE SECTION / STIFFNESS")
emit("-"*132)
emit(f"Section source:                      {section_source}")
emit(f"Section/stiffness fully resolved:    {section_ready}")
if tube_OD_mm is not None:
    emit(f"Tube OD:                             {tube_OD_mm:.6f} mm")
if tube_wall_mm is not None:
    emit(f"Tube wall:                           {tube_wall_mm:.6f} mm")
if brace_area_mm2 is not None:
    emit(f"Tube area:                           {brace_area_mm2:.6f} mm^2")
if E_MPa is not None:
    emit(f"E:                                   {E_MPa:.3f} MPa")
if axial_stiffness_N_per_mm is not None:
    emit(f"EA/L:                                {axial_stiffness_N_per_mm:.6f} N/mm")
if analytical_axial_extension_mm is not None:
    emit(f"Predicted axial extension:           {analytical_axial_extension_mm:+.6f} mm")
if analytical_axial_stress_MPa is not None:
    emit(f"Predicted axial stress magnitude:    {analytical_axial_stress_MPa:.6f} MPa")
emit("")
emit("FEA DISPOSITION")
emit("-"*132)
emit("REMOVE SUP_BRACE_RX.")
emit("Retain the solved B14A combined external load state and journal support architecture.")
emit("Insert an axial-only two-force member from B to A and re-solve the complete reaction distribution.")
emit("Journal reactions from B14A are not reusable after the physical brace is introduced.")
emit("")
emit("GATE")
emit("-"*132)
emit("PASS_B14B10_READY_FOR_FIRST_PHYSICAL_BRACE_FEA")
emit("")
emit("OUTPUTS")
emit("-"*132)
for p in [OUT_HANDOFF, OUT_CHECKS, OUT_OPEN, OUT_SETUP, OUT_SUMMARY]:
    emit(str(p))
emit("="*132)

report = "\n".join(lines)
OUT_SUMMARY.write_text(report, encoding="utf-8")
print(report)
