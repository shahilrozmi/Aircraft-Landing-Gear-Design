"""
Landing_Gear_Design_Project
PHASE 2E3-B14B-9 V0.1 — PHYSICAL HORN / CLEVIS CAD BUILD

PURPOSE
-------
Build the first source-connected physical gear-side horn/clevis directly onto the
validated CURRENT B13F-3C upper-head parent geometry.

This builder does NOT use the old B13C STEP as its parent.

REQUIRED UPSTREAM ARTIFACTS
---------------------------
phase2e3_b13f3c_current_parent_record.csv
phase2e3b14b7_geometry_handoff.csv
phase2e3b14b7_reference_candidate.csv
phase2e3b14b8_cad_handoff.csv
phase2e3b14b8_joint_frame.csv
phase2e3b14b8_reference_geometry.csv

CURRENT PARENT STEP
-------------------
phase2e3_b13f_3c_d44_r1p5_t3p5_left_collar_partial_relief*.step

ARCHITECTURE
------------
- The B13F-3C 7075 head/barrel remains the parent structural body.
- A source-connected saddle/horn is fused into that head on +y.
- The horn starts at the B14B-7 equivalent root section embedded inside the Ø106 boss.
- It transitions by a linear ruled loft to the B14B-8 clevis throat section.
- The fork then continues to the B14B-8 free-end station.
- A U-shaped center slot creates two ears.
- The slot-root radius is derived as half the source slot width; this is a WORKING CAD
  assumption for the first local-FEA model, not a final manufacturing freeze.
- The Ø18 pin bore is cut along the source-defined pin axis e_p.
- The existing shaft, bushings and two thrust collars are preserved unchanged.
- No physical brace eye/tube is added here; that belongs to the later physical-brace
  replacement / ANSYS stage.

IMPORTANT STATUS
----------------
B14B-9 is a CAD/FEA reference geometry, NOT a final detail-design freeze.
Lug bearing allowable, final root fillets, brace eye joining method, airframe-side joint,
fatigue/fretting/wear and final local contact design remain open.

OUTPUTS
-------
phase2e3b14b9_head_horn_clevis_v01.step
phase2e3b14b9_source_manifest.csv
phase2e3b14b9_geometry_definition.csv
phase2e3b14b9_geometry_validation.csv
phase2e3b14b9_open_items.csv
phase2e3b14b9_summary.txt
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Dict, List, Tuple

import cadquery as cq


HERE = Path(__file__).resolve().parent

PARENT_RECORD_NAME = "phase2e3_b13f3c_current_parent_record.csv"

B7_HANDOFF_NAME = "phase2e3b14b7_geometry_handoff.csv"
B7_REFERENCE_NAME = "phase2e3b14b7_reference_candidate.csv"

B8_HANDOFF_NAME = "phase2e3b14b8_cad_handoff.csv"
B8_FRAME_NAME = "phase2e3b14b8_joint_frame.csv"
B8_REFERENCE_NAME = "phase2e3b14b8_reference_geometry.csv"

PARENT_STEP_PATTERNS = [
    "phase2e3_b13f_3c_d44_r1p5_t3p5_left_collar_partial_relief.step",
    "phase2e3_b13f_3c_d44_r1p5_t3p5_left_collar_partial_relief*.step",
]

OUT_STEP = HERE / "phase2e3b14b9_head_horn_clevis_v01.step"
OUT_MANIFEST = HERE / "phase2e3b14b9_source_manifest.csv"
OUT_GEOMETRY = HERE / "phase2e3b14b9_geometry_definition.csv"
OUT_VALIDATION = HERE / "phase2e3b14b9_geometry_validation.csv"
OUT_OPEN = HERE / "phase2e3b14b9_open_items.csv"
OUT_SUMMARY = HERE / "phase2e3b14b9_summary.txt"

ABS_TOL = 1e-6
GEOM_TOL_MM = 1e-3
VOLUME_TOL_MM3 = 1e-3

EXPECTED_BODY_NAMES = [
    "HEAD_BARREL_7075",
    "SHAFT_300M_CONTINUOUS",
    "BUSHING_LEFT_AMS4640",
    "BUSHING_RIGHT_AMS4640",
    "THRUST_COLLAR_LEFT_300M",
    "THRUST_COLLAR_RIGHT_300M",
]


# =============================================================================
# 1. GENERIC HELPERS
# =============================================================================

def write_rows(path: Path, rows: List[dict], fields: List[str] | None = None):
    if not rows:
        rows = [{"status": "NONE"}]
    if fields is None:
        fields = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def read_rows(path: Path) -> List[dict]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def read_one(path: Path) -> dict:
    rows = read_rows(path)
    if len(rows) != 1:
        raise ValueError(f"{path.name}: expected exactly one row, found {len(rows)}.")
    return rows[0]


def as_float(x) -> float:
    return float(str(x).strip())


def as_bool(x) -> bool:
    return str(x).strip().lower() in {"true", "1", "yes", "y", "pass"}


def find_project_file(filename: str) -> Path:
    direct = HERE / filename
    if direct.exists():
        return direct

    matches = sorted(HERE.rglob(filename))
    if len(matches) == 1:
        return matches[0]
    if len(matches) == 0:
        raise FileNotFoundError(f"Required project file not found under {HERE}: {filename}")
    raise RuntimeError(
        f"Ambiguous project file '{filename}': found {len(matches)} copies. "
        "Keep one authoritative copy or place the intended copy beside this script."
    )


def find_parent_step() -> Path:
    # Prefer the exact no-suffix filename.
    exact = HERE / PARENT_STEP_PATTERNS[0]
    if exact.exists():
        return exact

    matches = []
    for pat in PARENT_STEP_PATTERNS[1:]:
        matches.extend(HERE.rglob(pat))
    matches = sorted(set(matches))

    if len(matches) == 1:
        return matches[0]
    if len(matches) == 0:
        raise FileNotFoundError(
            "Could not find the validated B13F-3C current-parent STEP under the project."
        )
    raise RuntimeError(
        "Multiple B13F-3C parent STEP candidates were found. "
        "Keep the authoritative parent named exactly "
        "'phase2e3_b13f_3c_d44_r1p5_t3p5_left_collar_partial_relief.step' "
        "beside this script."
    )


def vdot(a, b):
    return sum(float(a[i]) * float(b[i]) for i in range(3))


def vnorm(a):
    return math.sqrt(vdot(a, a))


def vcross(a, b):
    return (
        a[1]*b[2] - a[2]*b[1],
        a[2]*b[0] - a[0]*b[2],
        a[0]*b[1] - a[1]*b[0],
    )


def vadd(a, b):
    return tuple(a[i] + b[i] for i in range(3))


def vsub(a, b):
    return tuple(a[i] - b[i] for i in range(3))


def vscale(a, s):
    return tuple(a[i] * s for i in range(3))


def distance(a, b):
    return vnorm(vsub(a, b))


def add_check(rows, name, actual, expected, units="-", tol=ABS_TOL, note=""):
    passed = abs(float(actual) - float(expected)) <= tol
    rows.append({
        "check": name,
        "actual": actual,
        "expected": expected,
        "units": units,
        "tolerance": tol,
        "status": "PASS" if passed else "FAIL",
        "note": note,
    })


def add_bool_check(rows, name, actual: bool, note=""):
    rows.append({
        "check": name,
        "actual": bool(actual),
        "expected": True,
        "units": "-",
        "tolerance": "-",
        "status": "PASS" if actual else "FAIL",
        "note": note,
    })


def parameter_row(rows: List[dict], key: str) -> dict:
    found = [r for r in rows if r.get("parameter") == key]
    if len(found) != 1:
        raise ValueError(f"Expected one parameter '{key}', found {len(found)}.")
    return found[0]


def frame_row(rows: List[dict], key: str) -> dict:
    found = [r for r in rows if r.get("axis") == key]
    if len(found) != 1:
        raise ValueError(f"Expected one frame axis '{key}', found {len(found)}.")
    return found[0]


def vector_from_row(r: dict) -> Tuple[float, float, float]:
    return (as_float(r["x"]), as_float(r["y"]), as_float(r["z"]))


def scalar_from_parameter(rows: List[dict], key: str) -> float:
    r = parameter_row(rows, key)
    return as_float(r["value"])


def point_from_parameter(rows: List[dict], key: str) -> Tuple[float, float, float]:
    r = parameter_row(rows, key)
    return (as_float(r["x"]), as_float(r["y"]), as_float(r["z"]))


def bbox_record(shape):
    bb = shape.BoundingBox()
    return {
        "xmin": bb.xmin, "xmax": bb.xmax,
        "ymin": bb.ymin, "ymax": bb.ymax,
        "zmin": bb.zmin, "zmax": bb.zmax,
        "xlen": bb.xlen, "ylen": bb.ylen, "zlen": bb.zlen,
    }


# =============================================================================
# 2. LOCATE AND READ AUTHORITATIVE SOURCES
# =============================================================================

parent_record_path = find_project_file(PARENT_RECORD_NAME)
b7_handoff_path = find_project_file(B7_HANDOFF_NAME)
b7_reference_path = find_project_file(B7_REFERENCE_NAME)
b8_handoff_path = find_project_file(B8_HANDOFF_NAME)
b8_frame_path = find_project_file(B8_FRAME_NAME)
b8_reference_path = find_project_file(B8_REFERENCE_NAME)
parent_step_path = find_parent_step()

parent_record = read_one(parent_record_path)
b7_handoff = read_rows(b7_handoff_path)
b7_reference = read_one(b7_reference_path)
b8_handoff = read_rows(b8_handoff_path)
b8_frame = read_rows(b8_frame_path)
b8_reference = read_one(b8_reference_path)

manifest = [
    {"role": "validated_current_parent_record", "file": str(parent_record_path), "required": True},
    {"role": "validated_current_parent_STEP", "file": str(parent_step_path), "required": True},
    {"role": "B14B7_geometry_handoff", "file": str(b7_handoff_path), "required": True},
    {"role": "B14B7_reference_candidate", "file": str(b7_reference_path), "required": True},
    {"role": "B14B8_CAD_handoff", "file": str(b8_handoff_path), "required": True},
    {"role": "B14B8_joint_frame", "file": str(b8_frame_path), "required": True},
    {"role": "B14B8_reference_geometry", "file": str(b8_reference_path), "required": True},
]
write_rows(OUT_MANIFEST, manifest)


# =============================================================================
# 3. PARENT GATE
# =============================================================================

if not as_bool(parent_record["approved_as_B14B9_parent"]):
    raise RuntimeError(
        "Current-parent record does not approve the STEP for B14B-9. "
        "Re-run the B13F-3C current-parent validation first."
    )

if parent_record["geometry_gate"].strip() != "PASS_CURRENT_PARENT_VALIDATED_FOR_B14B9":
    raise RuntimeError(
        f"Unexpected current-parent geometry gate: {parent_record['geometry_gate']}"
    )

O_global = (
    as_float(parent_record["trunnion_center_x_mm"]),
    as_float(parent_record["trunnion_center_y_mm"]),
    as_float(parent_record["trunnion_center_z_mm"]),
)


# =============================================================================
# 4. READ B14B-7 ROOT GEOMETRY
# =============================================================================

root_width_x = scalar_from_parameter(b7_handoff, "horn_root_equivalent_width_x")
root_height_z = scalar_from_parameter(b7_handoff, "horn_root_equivalent_height_z")
root_y_local = scalar_from_parameter(b7_handoff, "horn_root_plane_y_from_trunnion_center")
root_embed = scalar_from_parameter(b7_handoff, "horn_root_embed_depth_from_outer_tangent")
root_passage_clearance = scalar_from_parameter(b7_handoff, "passage_clearance_at_root_plane")
added_root_height = scalar_from_parameter(b7_handoff, "added_height_total")
pin_y_b7 = scalar_from_parameter(b7_handoff, "gear_side_pin_y")
root_to_pin_b7 = scalar_from_parameter(b7_handoff, "root_to_pin_lever")

if not as_bool(b7_reference["reference_eligible"]):
    raise RuntimeError("B14B-7 reference candidate is not eligible.")

if b7_reference["selection_status"].strip() != "WORKING_CAD_FEA_REFERENCE_NOT_FROZEN":
    raise RuntimeError(
        "Unexpected B14B-7 selection status. Refusing to silently reinterpret the source."
    )


# =============================================================================
# 5. READ B14B-8 FRAME / CLEVIS GEOMETRY
# =============================================================================

e_h = vector_from_row(frame_row(b8_frame, "horn_radial_e_h"))
u_b = vector_from_row(frame_row(b8_frame, "brace_axis_u_b"))
e_p = vector_from_row(frame_row(b8_frame, "pin_axis_e_p"))

saddle_root_center_local = point_from_parameter(b8_handoff, "saddle_root_center")
throat_center_local = point_from_parameter(b8_handoff, "clevis_throat_center")
pin_center_local = point_from_parameter(b8_handoff, "pin_center")
pin_minus_local = point_from_parameter(b8_handoff, "pin_axis_minus_endpoint")
pin_plus_local = point_from_parameter(b8_handoff, "pin_axis_plus_endpoint")

plate_width_u = scalar_from_parameter(b8_handoff, "clevis_base_local_width_along_brace")
grip_ep = scalar_from_parameter(b8_handoff, "clevis_base_total_grip_along_pin_axis")
ear_t = scalar_from_parameter(b8_handoff, "ear_thickness")
slot_width_ep = scalar_from_parameter(b8_handoff, "central_slot_width_along_pin_axis")
pin_d = scalar_from_parameter(b8_handoff, "pin_diameter")
brace_eye_OD = scalar_from_parameter(b8_handoff, "brace_eye_OD")
brace_eye_width = scalar_from_parameter(b8_handoff, "brace_eye_width_along_pin_axis")
free_y_local = scalar_from_parameter(b8_handoff, "fork_free_end_y")
taper_length_source = scalar_from_parameter(b8_handoff, "taper_length_saddle_to_clevis_throat")

if not as_bool(b8_reference["eligible_reference"]):
    raise RuntimeError("B14B-8 reference geometry is not eligible.")

if b8_reference["selection_status"].strip() != "WORKING_CAD_FEA_REFERENCE_NOT_FROZEN":
    raise RuntimeError(
        "Unexpected B14B-8 selection status. Refusing to silently reinterpret the source."
    )

# First-pass CAD choice for the U-slot termination.
# It is fully derived from the already-selected slot width, not an independent frozen dimension.
slot_root_r = 0.5 * slot_width_ep
slot_circle_center_y_local = throat_center_local[1] + slot_root_r

# The straight part starts at the center of the semicircular slot root and runs past
# the free end so that the clevis is physically open.
slot_cut_overshoot_y = 5.0  # modeling overshoot only, not physical geometry
slot_straight_end_y_local = free_y_local + slot_cut_overshoot_y

# Cutter overtravel only; these are not design dimensions.
slot_cutter_half_depth_u = max(50.0, 0.5*plate_width_u + 10.0)
pin_cutter_half_length_ep = max(50.0, 0.5*grip_ep + 10.0)


# =============================================================================
# 6. SOURCE CONSISTENCY CHECKS BEFORE CAD
# =============================================================================

checks: List[dict] = []

add_bool_check(
    checks,
    "parent_record_approved_for_B14B9",
    as_bool(parent_record["approved_as_B14B9_parent"]),
)

add_check(
    checks, "root_width_B7_handoff_vs_reference",
    root_width_x, as_float(b7_reference["bx_mm"]), "mm", GEOM_TOL_MM
)
add_check(
    checks, "root_height_B7_handoff_vs_reference",
    root_height_z, as_float(b7_reference["hz_mm"]), "mm", GEOM_TOL_MM
)
add_check(
    checks, "root_plane_y_B7_handoff_vs_reference",
    root_y_local, as_float(b7_reference["root_plane_y_mm"]), "mm", GEOM_TOL_MM
)
add_check(
    checks, "root_to_pin_B7_handoff_vs_reference",
    root_to_pin_b7, as_float(b7_reference["root_to_pin_lever_mm"]), "mm", GEOM_TOL_MM
)

add_check(checks, "norm_e_h", vnorm(e_h), 1.0, "-", 1e-9)
add_check(checks, "norm_u_b", vnorm(u_b), 1.0, "-", 1e-9)
add_check(checks, "norm_e_p", vnorm(e_p), 1.0, "-", 1e-9)
add_check(checks, "dot_e_h_u_b", vdot(e_h, u_b), 0.0, "-", 1e-9)
add_check(checks, "dot_e_h_e_p", vdot(e_h, e_p), 0.0, "-", 1e-9)
add_check(checks, "dot_u_b_e_p", vdot(u_b, e_p), 0.0, "-", 1e-9)

cross_eh_ub = vcross(e_h, u_b)
add_check(checks, "cross_e_h_u_b_x", cross_eh_ub[0], e_p[0], "-", 1e-9)
add_check(checks, "cross_e_h_u_b_y", cross_eh_ub[1], e_p[1], "-", 1e-9)
add_check(checks, "cross_e_h_u_b_z", cross_eh_ub[2], e_p[2], "-", 1e-9)

add_check(
    checks, "root_center_y_B8_vs_B7",
    saddle_root_center_local[1], root_y_local, "mm", GEOM_TOL_MM
)
add_check(
    checks, "pin_y_B8_vs_B7",
    pin_center_local[1], pin_y_b7, "mm", GEOM_TOL_MM
)
add_check(
    checks, "taper_length_source_reconstruction",
    throat_center_local[1] - root_y_local, taper_length_source, "mm", GEOM_TOL_MM
)

add_check(
    checks, "clevis_grip_identity",
    2.0*ear_t + slot_width_ep, grip_ep, "mm", GEOM_TOL_MM,
    note="Two ears plus central slot must reconstruct the source structural grip."
)

add_check(
    checks, "ear_t_B8_handoff_vs_reference",
    ear_t, as_float(b8_reference["ear_t_mm"]), "mm", GEOM_TOL_MM
)
add_check(
    checks, "plate_width_B8_handoff_vs_reference",
    plate_width_u, as_float(b8_reference["plate_width_along_brace_axis_mm"]),
    "mm", GEOM_TOL_MM
)
add_check(
    checks, "grip_B8_handoff_vs_reference",
    grip_ep, as_float(b8_reference["structural_pin_grip_mm"]), "mm", GEOM_TOL_MM
)
add_check(
    checks, "throat_y_B8_handoff_vs_reference",
    throat_center_local[1], as_float(b8_reference["throat_y_mm"]), "mm", GEOM_TOL_MM
)
add_check(
    checks, "free_y_B8_handoff_vs_reference",
    free_y_local, as_float(b8_reference["free_y_mm"]), "mm", GEOM_TOL_MM
)

expected_bbox_x = abs(grip_ep*e_p[0]) + abs(plate_width_u*u_b[0])
expected_bbox_z = abs(grip_ep*e_p[2]) + abs(plate_width_u*u_b[2])

add_check(
    checks, "clevis_bbox_x_reconstruction",
    expected_bbox_x, as_float(b8_reference["clevis_base_bbox_x_mm"]), "mm", 2e-6
)
add_check(
    checks, "clevis_bbox_z_reconstruction",
    expected_bbox_z, as_float(b8_reference["clevis_base_bbox_z_mm"]), "mm", 2e-6
)

add_check(
    checks, "pin_structural_grip_endpoint_distance",
    distance(pin_minus_local, pin_plus_local), grip_ep, "mm", 2e-6
)

if any(r["status"] == "FAIL" for r in checks):
    write_rows(OUT_VALIDATION, checks)
    raise RuntimeError(
        "B14B-7/B14B-8 source consistency gate failed. "
        "See phase2e3b14b9_geometry_validation.csv."
    )


# =============================================================================
# 7. IMPORT / CLASSIFY CURRENT B13F-3C PARENT
# =============================================================================

parent_import = cq.importers.importStep(str(parent_step_path))
parent_solids = parent_import.solids().vals()

add_check(checks, "parent_STEP_solid_count", len(parent_solids), 6, "-", 0)

if len(parent_solids) != 6:
    write_rows(OUT_VALIDATION, checks)
    raise RuntimeError(
        f"Current B13F-3C parent must contain 6 solids, found {len(parent_solids)}."
    )

body_records = []
for i, s in enumerate(parent_solids):
    bb = bbox_record(s)
    body_records.append({
        "index": i,
        "shape": s,
        "volume": s.Volume(),
        **bb,
        "xmid": 0.5*(bb["xmin"] + bb["xmax"]),
    })

head_rec = max(body_records, key=lambda r: r["volume"])

shaft_candidates = [
    r for r in body_records
    if r is not head_rec
    and abs(r["xlen"] - 175.0) < 0.05
    and abs(r["ylen"] - 38.0) < 0.05
    and abs(r["zlen"] - 38.0) < 0.05
]
if len(shaft_candidates) != 1:
    raise RuntimeError("Could not uniquely identify the current 300M shaft.")
shaft_rec = shaft_candidates[0]

collar_recs = [
    r for r in body_records
    if r not in (head_rec, shaft_rec)
    and abs(r["xlen"] - 3.0) < 0.05
    and abs(r["ylen"] - 58.0) < 0.05
    and abs(r["zlen"] - 58.0) < 0.05
]
if len(collar_recs) != 2:
    raise RuntimeError("Could not identify the two current thrust collars.")

bushing_recs = [
    r for r in body_records
    if r not in (head_rec, shaft_rec) and r not in collar_recs
]
if len(bushing_recs) != 2:
    raise RuntimeError("Could not identify the two current bronze bushings.")

left_bushing_rec = min(bushing_recs, key=lambda r: r["xmid"])
right_bushing_rec = max(bushing_recs, key=lambda r: r["xmid"])
left_collar_rec = min(collar_recs, key=lambda r: r["xmid"])
right_collar_rec = max(collar_recs, key=lambda r: r["xmid"])

parent_named = {
    "HEAD_BARREL_7075": head_rec,
    "SHAFT_300M_CONTINUOUS": shaft_rec,
    "BUSHING_LEFT_AMS4640": left_bushing_rec,
    "BUSHING_RIGHT_AMS4640": right_bushing_rec,
    "THRUST_COLLAR_LEFT_300M": left_collar_rec,
    "THRUST_COLLAR_RIGHT_300M": right_collar_rec,
}

add_check(
    checks, "parent_trunnion_center_y_from_shaft_bbox",
    0.5*(shaft_rec["ymin"] + shaft_rec["ymax"]), O_global[1], "mm", GEOM_TOL_MM
)
add_check(
    checks, "parent_trunnion_center_z_from_shaft_bbox",
    0.5*(shaft_rec["zmin"] + shaft_rec["zmax"]), O_global[2], "mm", GEOM_TOL_MM
)


# =============================================================================
# 8. LOCAL -> GLOBAL GEOMETRY
# =============================================================================

def local_to_global(p_local):
    return vadd(O_global, p_local)

root_center_global = local_to_global(saddle_root_center_local)
throat_center_global = local_to_global(throat_center_local)
pin_center_global = local_to_global(pin_center_local)
pin_minus_global = local_to_global(pin_minus_local)
pin_plus_global = local_to_global(pin_plus_local)

free_center_global = (
    O_global[0],
    O_global[1] + free_y_local,
    O_global[2],
)


# =============================================================================
# 9. BUILD THE 7075 SADDLE / HORN / CLEVIS
# =============================================================================

# Root plane: global x-z section, normal +y.
root_plane = cq.Plane(
    origin=root_center_global,
    xDir=(1.0, 0.0, 0.0),
    normal=e_h,
)

# Clevis throat plane: xDir along pin axis e_p; second in-plane axis is ±u_b.
throat_plane = cq.Plane(
    origin=throat_center_global,
    xDir=e_p,
    normal=e_h,
)

root_wire = cq.Workplane(root_plane).rect(root_width_x, root_height_z).val()
throat_wire = cq.Workplane(throat_plane).rect(grip_ep, plate_width_u).val()

# Auditable first-pass taper: ruled linear loft between the two source sections.
taper_solid = cq.Solid.makeLoft([root_wire, throat_wire], ruled=True)

# Constant fork envelope from throat to free end.
fork_outer = (
    cq.Workplane(throat_plane)
    .rect(grip_ep, plate_width_u)
    .extrude(free_y_local - throat_center_local[1])
    .val()
)

horn_before_cuts = taper_solid.fuse(fork_outer)

# -------------------------------------------------------------------------
# U-slot cutter
# -------------------------------------------------------------------------
#
# In the e_p / e_h plane:
#   - slot width = source 22 mm along e_p
#   - root tip = source throat station
#   - semicircular root radius = slot_width / 2
#   - straight slot begins one radius outboard and runs beyond the free end
#
# Cutter normal is u_b, so it removes material across the full clevis width.

slot_straight_start_y_global = O_global[1] + slot_circle_center_y_local
slot_straight_end_y_global = O_global[1] + slot_straight_end_y_local
slot_straight_length = slot_straight_end_y_global - slot_straight_start_y_global
slot_straight_mid_y = 0.5*(slot_straight_start_y_global + slot_straight_end_y_global)

slot_plane = cq.Plane(
    origin=(O_global[0], slot_straight_mid_y, O_global[2]),
    xDir=e_p,
    normal=u_b,
)

slot_rect = (
    cq.Workplane(slot_plane)
    .rect(slot_width_ep, slot_straight_length)
    .extrude(2.0*slot_cutter_half_depth_u, both=True)
    .val()
)

slot_circle_center_global = (
    O_global[0],
    O_global[1] + slot_circle_center_y_local,
    O_global[2],
)

slot_cyl_start = vsub(
    slot_circle_center_global,
    vscale(u_b, slot_cutter_half_depth_u),
)

slot_root_cyl = cq.Solid.makeCylinder(
    slot_root_r,
    2.0*slot_cutter_half_depth_u,
    cq.Vector(*slot_cyl_start),
    cq.Vector(*u_b),
)

slot_cutter = slot_rect.fuse(slot_root_cyl)
horn_after_slot = horn_before_cuts.cut(slot_cutter)

# -------------------------------------------------------------------------
# Ø18 pin bore cutter
# -------------------------------------------------------------------------

pin_hole_start = vsub(
    pin_center_global,
    vscale(e_p, pin_cutter_half_length_ep),
)

pin_hole_cutter = cq.Solid.makeCylinder(
    0.5*pin_d,
    2.0*pin_cutter_half_length_ep,
    cq.Vector(*pin_hole_start),
    cq.Vector(*e_p),
)

horn_final = horn_after_slot.cut(pin_hole_cutter)

if len(horn_final.Solids()) != 1:
    raise RuntimeError(
        f"Horn/clevis operation produced {len(horn_final.Solids())} solids; expected one."
    )

# Fuse the 7075 horn into the existing 7075 parent head.
parent_head = parent_named["HEAD_BARREL_7075"]["shape"]
modified_head = parent_head.fuse(horn_final)

if len(modified_head.Solids()) != 1:
    raise RuntimeError(
        f"Fused 7075 head/horn has {len(modified_head.Solids())} solids; expected one."
    )


# =============================================================================
# 10. POST-BUILD GEOMETRY / INTERFERENCE VALIDATION
# =============================================================================

parent_head_volume = parent_head.Volume()
horn_final_volume = horn_final.Volume()
modified_head_volume = modified_head.Volume()
head_horn_overlap_volume = parent_head_volume + horn_final_volume - modified_head_volume

add_bool_check(
    checks,
    "horn_is_single_connected_solid_before_head_fuse",
    len(horn_final.Solids()) == 1,
)
add_bool_check(
    checks,
    "modified_head_is_single_connected_solid",
    len(modified_head.Solids()) == 1,
)
add_bool_check(
    checks,
    "horn_has_positive_embed_overlap_with_parent_head",
    head_horn_overlap_volume > 1.0,
    note="Positive common volume proves the horn is embedded/fused into the current head rather than merely touching it."
)

mod_bb = bbox_record(modified_head)

add_check(
    checks, "modified_head_ymax_equals_fork_free_end",
    mod_bb["ymax"], O_global[1] + free_y_local, "mm", 2e-3
)

expected_root_zmax = O_global[2] + 0.5*root_height_z
expected_root_zmin = O_global[2] - 0.5*root_height_z

add_check(
    checks, "modified_head_zmax_contains_root_envelope",
    mod_bb["zmax"], expected_root_zmax, "mm", 2e-3
)
# The original barrel extends far below the root; do not compare the global zmin to root zmin.

# Preserve every non-head body exactly.
for body_name in EXPECTED_BODY_NAMES[1:]:
    rec = parent_named[body_name]
    add_bool_check(
        checks,
        f"preserve_{body_name}_positive_volume",
        rec["volume"] > 0.0,
    )

# Modified head must not overlap the other five physical bodies.
for body_name in EXPECTED_BODY_NAMES[1:]:
    other = parent_named[body_name]["shape"]
    iv = modified_head.intersect(other).Volume()
    add_check(
        checks,
        f"intersection_modified_head__{body_name}",
        iv, 0.0, "mm^3", 1e-6,
        note="Separate material bodies must not have positive common volume."
    )

# Check all remaining original non-head pairs too.
for i in range(1, len(EXPECTED_BODY_NAMES)):
    for j in range(i+1, len(EXPECTED_BODY_NAMES)):
        ni = EXPECTED_BODY_NAMES[i]
        nj = EXPECTED_BODY_NAMES[j]
        iv = parent_named[ni]["shape"].intersect(parent_named[nj]["shape"]).Volume()
        add_check(
            checks,
            f"intersection_{ni}__{nj}",
            iv, 0.0, "mm^3", 1e-6,
        )


# =============================================================================
# 11. EXPORT NAMED SIX-BODY STEP
# =============================================================================

out_assembly = cq.Assembly(name="B14B9_HEAD_HORN_CLEVIS")

out_assembly.add(modified_head, name="HEAD_BARREL_7075")
for body_name in EXPECTED_BODY_NAMES[1:]:
    out_assembly.add(parent_named[body_name]["shape"], name=body_name)

out_assembly.save(str(OUT_STEP))

# Re-import the exact exported artifact.
reimport = cq.importers.importStep(str(OUT_STEP))
reimport_solids = reimport.solids().vals()

add_check(
    checks, "exported_reimported_solid_count",
    len(reimport_solids), 6, "-", 0
)

# Check product/body labels survived export.
step_text = OUT_STEP.read_text(encoding="utf-8", errors="replace")
add_bool_check(
    checks,
    "export_product_B14B9_HEAD_HORN_CLEVIS",
    "B14B9_HEAD_HORN_CLEVIS" in step_text,
)
for body_name in EXPECTED_BODY_NAMES:
    add_bool_check(
        checks,
        f"export_body_label_{body_name}",
        body_name in step_text,
    )


# =============================================================================
# 12. MACHINE-READABLE GEOMETRY DEFINITION
# =============================================================================

geometry_rows = [
    {
        "feature": "current_parent",
        "parameter": "parent_STEP",
        "value": parent_step_path.name,
        "units": "-",
        "classification": "VALIDATED_B13F3C_PARENT",
        "source": PARENT_RECORD_NAME,
    },
    {
        "feature": "coordinate_frame",
        "parameter": "trunnion_center_global",
        "value": f"{O_global[0]:.9f},{O_global[1]:.9f},{O_global[2]:.9f}",
        "units": "mm",
        "classification": "SOURCE_CURRENT_PARENT_RECORD",
        "source": PARENT_RECORD_NAME,
    },
    {
        "feature": "saddle_root",
        "parameter": "center_global",
        "value": f"{root_center_global[0]:.9f},{root_center_global[1]:.9f},{root_center_global[2]:.9f}",
        "units": "mm",
        "classification": "SOURCE_B14B7_PLUS_PARENT_TRANSFORM",
        "source": B7_HANDOFF_NAME,
    },
    {
        "feature": "saddle_root",
        "parameter": "equivalent_width_x",
        "value": root_width_x,
        "units": "mm",
        "classification": "WORKING_NOT_FROZEN",
        "source": B7_HANDOFF_NAME,
    },
    {
        "feature": "saddle_root",
        "parameter": "equivalent_height_z",
        "value": root_height_z,
        "units": "mm",
        "classification": "WORKING_NOT_FROZEN",
        "source": B7_HANDOFF_NAME,
    },
    {
        "feature": "saddle_root",
        "parameter": "embed_depth_from_boss_tangent",
        "value": root_embed,
        "units": "mm",
        "classification": "SOURCE_B14B7",
        "source": B7_HANDOFF_NAME,
    },
    {
        "feature": "saddle_root",
        "parameter": "source_min_passage_clearance",
        "value": root_passage_clearance,
        "units": "mm",
        "classification": "SOURCE_B14B7",
        "source": B7_HANDOFF_NAME,
    },
    {
        "feature": "horn_taper",
        "parameter": "type",
        "value": "LINEAR_RULED_LOFT",
        "units": "-",
        "classification": "WORKING_CAD_FEA_ASSUMPTION",
        "source": "B14B9",
    },
    {
        "feature": "horn_taper",
        "parameter": "length",
        "value": taper_length_source,
        "units": "mm",
        "classification": "DERIVED_SOURCE_CONNECTED",
        "source": B8_HANDOFF_NAME,
    },
    {
        "feature": "clevis_throat",
        "parameter": "center_global",
        "value": f"{throat_center_global[0]:.9f},{throat_center_global[1]:.9f},{throat_center_global[2]:.9f}",
        "units": "mm",
        "classification": "SOURCE_B14B8_PLUS_PARENT_TRANSFORM",
        "source": B8_HANDOFF_NAME,
    },
    {
        "feature": "clevis",
        "parameter": "plate_width_along_brace_axis",
        "value": plate_width_u,
        "units": "mm",
        "classification": "WORKING_NOT_FROZEN",
        "source": B8_HANDOFF_NAME,
    },
    {
        "feature": "clevis",
        "parameter": "structural_grip_along_pin_axis",
        "value": grip_ep,
        "units": "mm",
        "classification": "WORKING_NOT_FROZEN",
        "source": B8_HANDOFF_NAME,
    },
    {
        "feature": "clevis",
        "parameter": "ear_thickness",
        "value": ear_t,
        "units": "mm",
        "classification": "WORKING_NOT_FROZEN",
        "source": B8_HANDOFF_NAME,
    },
    {
        "feature": "clevis",
        "parameter": "slot_width_along_pin_axis",
        "value": slot_width_ep,
        "units": "mm",
        "classification": "WORKING_NOT_FROZEN",
        "source": B8_HANDOFF_NAME,
    },
    {
        "feature": "clevis",
        "parameter": "slot_root_radius",
        "value": slot_root_r,
        "units": "mm",
        "classification": "WORKING_CAD_FEA_DERIVED_NOT_FROZEN",
        "source": "B14B9 = slot_width/2",
    },
    {
        "feature": "clevis",
        "parameter": "free_end_y_global",
        "value": O_global[1] + free_y_local,
        "units": "mm",
        "classification": "SOURCE_B14B8_PLUS_PARENT_TRANSFORM",
        "source": B8_HANDOFF_NAME,
    },
    {
        "feature": "pin_bore",
        "parameter": "center_global",
        "value": f"{pin_center_global[0]:.9f},{pin_center_global[1]:.9f},{pin_center_global[2]:.9f}",
        "units": "mm",
        "classification": "SOURCE_B14B8_PLUS_PARENT_TRANSFORM",
        "source": B8_HANDOFF_NAME,
    },
    {
        "feature": "pin_bore",
        "parameter": "diameter",
        "value": pin_d,
        "units": "mm",
        "classification": "WORKING_NOT_FROZEN",
        "source": B8_HANDOFF_NAME,
    },
    {
        "feature": "joint_frame",
        "parameter": "horn_radial_e_h",
        "value": f"{e_h[0]:.12f},{e_h[1]:.12f},{e_h[2]:.12f}",
        "units": "-",
        "classification": "SOURCE_B14B8",
        "source": B8_FRAME_NAME,
    },
    {
        "feature": "joint_frame",
        "parameter": "brace_axis_u_b",
        "value": f"{u_b[0]:.12f},{u_b[1]:.12f},{u_b[2]:.12f}",
        "units": "-",
        "classification": "SOURCE_B14B8",
        "source": B8_FRAME_NAME,
    },
    {
        "feature": "joint_frame",
        "parameter": "pin_axis_e_p",
        "value": f"{e_p[0]:.12f},{e_p[1]:.12f},{e_p[2]:.12f}",
        "units": "-",
        "classification": "SOURCE_B14B8",
        "source": B8_FRAME_NAME,
    },
    {
        "feature": "mass_geometry",
        "parameter": "parent_head_volume",
        "value": parent_head_volume,
        "units": "mm^3",
        "classification": "GEOMETRY_MEASURED",
        "source": parent_step_path.name,
    },
    {
        "feature": "mass_geometry",
        "parameter": "standalone_horn_after_slot_and_pin_bore_volume",
        "value": horn_final_volume,
        "units": "mm^3",
        "classification": "GEOMETRY_MEASURED",
        "source": "B14B9",
    },
    {
        "feature": "mass_geometry",
        "parameter": "head_horn_embed_overlap_volume",
        "value": head_horn_overlap_volume,
        "units": "mm^3",
        "classification": "GEOMETRY_MEASURED",
        "source": "B14B9",
    },
    {
        "feature": "mass_geometry",
        "parameter": "final_modified_head_volume",
        "value": modified_head_volume,
        "units": "mm^3",
        "classification": "GEOMETRY_MEASURED",
        "source": OUT_STEP.name,
    },
]

write_rows(OUT_GEOMETRY, geometry_rows)


# =============================================================================
# 13. OPEN ITEMS
# =============================================================================

open_items = [
    {
        "item": "SADDLE_ROOT_EXTERNAL_FILLET",
        "status": "OPEN_NOT_FROZEN",
        "reason": (
            "V0.1 uses an embedded linear ruled loft without a separately selected "
            "external root fillet. The B14B-7 Kt=3 screen remains the conservative "
            "pre-FEA basis. Local FEA must establish a practical blend/fillet."
        ),
    },
    {
        "item": "CLEVIS_SLOT_ROOT_DETAIL",
        "status": "WORKING_NOT_FROZEN",
        "reason": (
            f"V0.1 uses a U-slot root radius equal to half the source slot width "
            f"(R={slot_root_r:.3f} mm). This is a clean first-pass CAD/FEA choice, "
            "not a final manufacturing detail."
        ),
    },
    {
        "item": "LUG_BEARING_ALLOWABLE",
        "status": "OPEN",
        "reason": (
            "B14B-8 reports projected bearing demand but no valid product-form-specific "
            "7075 lug bearing allowable is frozen."
        ),
    },
    {
        "item": "BRACE_EYE_END_FITTING",
        "status": "OPEN",
        "reason": (
            "The gear-side clevis is now modeled, but the 44 mm brace eye, 25x3 tube "
            "and joining method are not added in B14B-9."
        ),
    },
    {
        "item": "AIRFRAME_SIDE_JOINT",
        "status": "OPEN",
        "reason": (
            "The opposite brace-end fitting and airframe structural attachment remain "
            "outside the landing-gear head CAD."
        ),
    },
    {
        "item": "PHYSICAL_BRACE_ANSYS_REPLACEMENT",
        "status": "NEXT",
        "reason": (
            "After accepting B14B-9 geometry, remove SUP_BRACE_RX and replace it with "
            "the actual pin-ended axial brace. Recompute journal reactions and local "
            "head/horn stresses."
        ),
    },
    {
        "item": "FATIGUE_FRETTING_WEAR_FRACTURE",
        "status": "OPEN",
        "reason": (
            "The present work is static preliminary geometry and strength screening only."
        ),
    },
]
write_rows(OUT_OPEN, open_items)


# =============================================================================
# 14. FINAL GATE
# =============================================================================

write_rows(OUT_VALIDATION, checks)

failures = [r for r in checks if r["status"] == "FAIL"]

if failures:
    gate = "FAIL_B14B9_GEOMETRY_VALIDATION"
else:
    gate = "PASS_B14B9_GEOMETRY_FOR_LOCAL_FEA"


# =============================================================================
# 15. SUMMARY
# =============================================================================

lines = []
emit = lines.append

emit("=" * 144)
emit(" PHASE 2E3-B14B-9 V0.1 — PHYSICAL HORN / CLEVIS CAD BUILD")
emit("=" * 144)
emit("")
emit("SOURCE CONNECTION")
emit("-" * 144)
for r in manifest:
    emit(f"{r['role']:<34s}: {r['file']}")
emit("")
emit("CURRENT PARENT")
emit("-" * 144)
emit(f"Parent STEP:                         {parent_step_path}")
emit(f"Parent gate:                         {parent_record['geometry_gate']}")
emit(f"Trunnion center O_global:            [{O_global[0]:.3f}, {O_global[1]:.3f}, {O_global[2]:.3f}] mm")
emit("")
emit("B14B-7 SADDLE / ROOT INPUT")
emit("-" * 144)
emit(f"Equivalent root section:             {root_width_x:.3f} x {root_height_z:.3f} mm")
emit(f"Root center global:                  [{root_center_global[0]:.3f}, {root_center_global[1]:.3f}, {root_center_global[2]:.3f}] mm")
emit(f"Embed depth from Ø106 tangent:       {root_embed:.6f} mm")
emit(f"Source passage clearance:            {root_passage_clearance:.6f} mm")
emit(f"Added root height envelope:          {added_root_height:.3f} mm")
emit("")
emit("B14B-8 CLEVIS INPUT")
emit("-" * 144)
emit(f"Throat center global:                [{throat_center_global[0]:.3f}, {throat_center_global[1]:.3f}, {throat_center_global[2]:.3f}] mm")
emit(f"Plate width along brace axis u_b:    {plate_width_u:.3f} mm")
emit(f"Total structural grip along e_p:     {grip_ep:.3f} mm")
emit(f"Ear thickness:                       {ear_t:.3f} mm each")
emit(f"Central slot width:                  {slot_width_ep:.3f} mm")
emit(f"Fork free end y:                     {O_global[1] + free_y_local:.3f} mm global")
emit(f"Pin center global:                   [{pin_center_global[0]:.3f}, {pin_center_global[1]:.3f}, {pin_center_global[2]:.3f}] mm")
emit(f"Pin bore:                            Ø{pin_d:.3f} mm")
emit(f"Brace eye reference envelope:        Ø{brace_eye_OD:.3f} x {brace_eye_width:.3f} mm [NOT BUILT HERE]")
emit("")
emit("LOCAL FRAME")
emit("-" * 144)
emit(f"e_h = [{e_h[0]:+.9f}, {e_h[1]:+.9f}, {e_h[2]:+.9f}]")
emit(f"u_b = [{u_b[0]:+.9f}, {u_b[1]:+.9f}, {u_b[2]:+.9f}]")
emit(f"e_p = [{e_p[0]:+.9f}, {e_p[1]:+.9f}, {e_p[2]:+.9f}]")
emit("")
emit("B14B-9 CAD CHOICES")
emit("-" * 144)
emit("Saddle-to-throat transition:         LINEAR RULED LOFT")
emit(f"U-slot root radius:                  {slot_root_r:.3f} mm = slot_width/2 [WORKING, NOT FROZEN]")
emit("External saddle-root fillet:         NOT ADDED / OPEN FOR LOCAL FEA")
emit("Physical brace eye/tube:             NOT ADDED IN B14B-9")
emit("")
emit("GEOMETRY RESULT")
emit("-" * 144)
emit(f"Parent 7075 head volume:             {parent_head_volume:.3f} mm^3")
emit(f"Standalone horn after cuts:          {horn_final_volume:.3f} mm^3")
emit(f"Head/horn embed overlap:             {head_horn_overlap_volume:.3f} mm^3")
emit(f"Final fused 7075 head volume:        {modified_head_volume:.3f} mm^3")
emit(f"Exported/re-imported solid count:    {len(reimport_solids)}")
emit("")
emit("VALIDATION")
emit("-" * 144)
emit(f"PASS checks:                         {sum(r['status']=='PASS' for r in checks)}")
emit(f"FAIL checks:                         {sum(r['status']=='FAIL' for r in checks)}")
if failures:
    for r in failures:
        emit(f"FAIL  {r['check']}: actual={r['actual']} expected={r['expected']} {r['units']}")
emit("")
emit("GATE")
emit("-" * 144)
emit(gate)
if not failures:
    emit("The current B13F-3C geometry has been retained and the source-connected B14B-9 horn/clevis has been added.")
    emit("The result is suitable for the first local physical-brace / horn FEA handoff, not final detail-design freeze.")
else:
    emit("Do not use the generated geometry for FEA until the failed validation items are resolved.")
emit("")
emit("OUTPUTS")
emit("-" * 144)
for p in [OUT_STEP, OUT_MANIFEST, OUT_GEOMETRY, OUT_VALIDATION, OUT_OPEN, OUT_SUMMARY]:
    emit(str(p))
emit("=" * 144)

report = "\n".join(lines)
OUT_SUMMARY.write_text(report, encoding="utf-8")
print(report)

if failures:
    raise SystemExit(2)
