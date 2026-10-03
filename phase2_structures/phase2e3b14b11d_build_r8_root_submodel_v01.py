"""
Landing_Gear_Design_Project
PHASE 2E3-B14B-11D V0.1 — R8 ROOT LOCAL SUBMODEL CAD BUILD

Purpose
-------
Build a compact, source-connected local R8 root submodel from the exact validated
B14B-9 architecture and the B14B-11C R8 = 8 mm root-fillet definition.

The local model keeps the physical journal assembly unchanged and crops only the
7075 head/horn body. Two artificial cut boundaries are created deliberately:
  1) barrel cut plane at global z = 850 mm
  2) horn/taper cut plane at global y = 180 mm

The full x-width is retained so the R8 root fillet and the complete local boss width
are unchanged. The current R8 FEA hotspot is kept well inside the submodel.

Status
------
WORKING LOCAL-FEA SUBMODEL GEOMETRY — NOT DETAIL-DESIGN FREEZE.
"""
from __future__ import annotations

import csv
import math
import runpy
from pathlib import Path
import cadquery as cq

HERE = Path(__file__).resolve().parent
BASE_BUILDER = HERE / "phase2e3b14b9_build_physical_horn_clevis_v01.py"

OUT_STEP = HERE / "phase2e3b14b11d_r8_root_submodel_v01.step"
OUT_HEAD_ONLY_STEP = HERE / "phase2e3b14b11d_r8_root_submodel_head_only_v01.step"
OUT_GEOM = HERE / "phase2e3b14b11d_r8_root_submodel_geometry_v01.csv"
OUT_VAL = HERE / "phase2e3b14b11d_r8_root_submodel_validation_v01.csv"
OUT_SUMMARY = HERE / "phase2e3b14b11d_r8_root_submodel_summary_v01.txt"

R8_MM = 8.0
# Current refined R8 head hotspot from the latest full-model run.
HOTSPOT = (18.702387, 49.818011, 964.937219)

# Local crop envelope. X exceeds the physical head width and therefore does not
# create an artificial x-cut. Y/Z create the two intended cut boundaries.
XMIN, XMAX = -60.0, 60.0
YMIN, YMAX = -60.0, 180.0
ZMIN, ZMAX = 850.0, 1070.0

ABS_TOL = 1e-6
GEOM_TOL = 1e-4


def write_rows(path: Path, rows):
    if not rows:
        rows = [{"status": "NONE"}]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), extrasaction="ignore")
        w.writeheader(); w.writerows(rows)


def check(rows, name, actual, expected, units="-", tol=ABS_TOL, note=""):
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        ok = abs(float(actual) - float(expected)) <= tol
    else:
        ok = actual == expected
    rows.append({
        "check": name, "actual": actual, "expected": expected,
        "units": units, "tolerance": tol,
        "status": "PASS" if ok else "FAIL", "note": note,
    })
    return ok


def check_bool(rows, name, cond, note=""):
    return check(rows, name, bool(cond), True, "-", 0, note)


def bbox_tuple(shape):
    b = shape.BoundingBox()
    return (b.xmin, b.xmax, b.ymin, b.ymax, b.zmin, b.zmax)


def min_hotspot_distance_to_artificial_cut(h):
    # Only y=YMAX and z=ZMIN are artificial cuts for the 7075 head.
    return min(YMAX - h[1], h[2] - ZMIN)


# -----------------------------------------------------------------------------
# Rebuild the exact B14B-9 in-memory source geometry, then create R8 exactly as
# B14B-11C did. This avoids reconstructing dimensions from chat or screenshots.
# -----------------------------------------------------------------------------
g = runpy.run_path(str(BASE_BUILDER))

horn_before_cuts = g["horn_before_cuts"]
slot_cutter = g["slot_cutter"]
pin_hole_cutter = g["pin_hole_cutter"]
parent_head = g["parent_head"]
parent_named = g["parent_named"]
expected_body_names = g["EXPECTED_BODY_NAMES"]
root_center_global = g["root_center_global"]
root_width_x = float(g["root_width_x"])
root_height_z = float(g["root_height_z"])

root_y = float(root_center_global[1])
root_edges = []
for edge in horn_before_cuts.Edges():
    bb = edge.BoundingBox()
    if abs(bb.ymin - root_y) <= 1e-7 and abs(bb.ymax - root_y) <= 1e-7:
        root_edges.append(edge)
if len(root_edges) != 4:
    raise RuntimeError(f"Expected four B14B root edges, found {len(root_edges)}")

horn_r8 = horn_before_cuts.fillet(R8_MM, root_edges).cut(slot_cutter).cut(pin_hole_cutter)
head_r8 = parent_head.fuse(horn_r8)

# Crop only the head/horn body.
crop_box = cq.Workplane("XY").box(
    XMAX - XMIN,
    YMAX - YMIN,
    ZMAX - ZMIN,
    centered=(False, False, False),
).translate((XMIN, YMIN, ZMIN)).val()

head_local = head_r8.intersect(crop_box)

# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------
checks = []
check(checks, "r8_root_edge_count", len(root_edges), 4)
check_bool(checks, "r8_full_head_single_solid", len(head_r8.Solids()) == 1)
check_bool(checks, "r8_local_head_single_solid", len(head_local.Solids()) == 1)
check_bool(checks, "r8_hotspot_inside_crop",
           XMIN < HOTSPOT[0] < XMAX and YMIN < HOTSPOT[1] < YMAX and ZMIN < HOTSPOT[2] < ZMAX)
check_bool(checks, "r8_hotspot_farther_than_100mm_from_artificial_cut",
           min_hotspot_distance_to_artificial_cut(HOTSPOT) > 100.0,
           f"minimum distance={min_hotspot_distance_to_artificial_cut(HOTSPOT):.6f} mm")

bb_full = bbox_tuple(head_r8)
bb_local = bbox_tuple(head_local)
# Full physical x/min-y/max-z should remain untouched by crop envelope.
check(checks, "local_bbox_xmin", bb_local[0], bb_full[0], "mm", GEOM_TOL)
check(checks, "local_bbox_xmax", bb_local[1], bb_full[1], "mm", GEOM_TOL)
check(checks, "local_bbox_ymin", bb_local[2], bb_full[2], "mm", GEOM_TOL)
check(checks, "local_bbox_ymax_cut", bb_local[3], YMAX, "mm", GEOM_TOL)
check(checks, "local_bbox_zmin_cut", bb_local[4], ZMIN, "mm", GEOM_TOL)
check(checks, "local_bbox_zmax", bb_local[5], bb_full[5], "mm", GEOM_TOL)
check_bool(checks, "local_volume_less_than_full", head_local.Volume() < head_r8.Volume())

# Identify artificial cut faces for ANSYS handoff.
y_cut_faces = []
z_cut_faces = []
for face in head_local.Faces():
    bb = face.BoundingBox()
    c = face.Center()
    if abs(bb.ymin - YMAX) < GEOM_TOL and abs(bb.ymax - YMAX) < GEOM_TOL:
        y_cut_faces.append(face)
    if abs(bb.zmin - ZMIN) < GEOM_TOL and abs(bb.zmax - ZMIN) < GEOM_TOL:
        z_cut_faces.append(face)

check(checks, "horn_y180_cut_face_count", len(y_cut_faces), 1)
check(checks, "barrel_z850_cut_face_count", len(z_cut_faces), 1)

# Ensure the cropped head still does not intersect the preserved non-head bodies.
for body_name in expected_body_names[1:]:
    iv = head_local.intersect(parent_named[body_name]["shape"]).Volume()
    check(checks, f"intersection_local_head__{body_name}", iv, 0.0, "mm^3", 1e-6)

# -----------------------------------------------------------------------------
# Export assembly: local cropped head + unchanged compact journal hardware.
# -----------------------------------------------------------------------------
assembly = cq.Assembly(name="B14B11D_R8_ROOT_LOCAL_SUBMODEL")
assembly.add(head_local, name="HEAD_BARREL_7075_R8_LOCAL")
for body_name in expected_body_names[1:]:
    assembly.add(parent_named[body_name]["shape"], name=body_name)
assembly.save(str(OUT_STEP))

# Also provide a head-only STEP for users who choose displacement-only component
# submodeling rather than retaining local contact hardware.
head_assembly = cq.Assembly(name="B14B11D_R8_ROOT_LOCAL_HEAD_ONLY")
head_assembly.add(head_local, name="HEAD_BARREL_7075_R8_LOCAL")
head_assembly.save(str(OUT_HEAD_ONLY_STEP))

# Reimport validation.
reimp = cq.importers.importStep(str(OUT_STEP))
re_solids = reimp.solids().vals()
check(checks, "assembly_reimported_solid_count", len(re_solids), 6)
step_text = OUT_STEP.read_text(encoding="utf-8", errors="replace")
for label in ["HEAD_BARREL_7075_R8_LOCAL", *expected_body_names[1:]]:
    check_bool(checks, f"step_label_{label}", label in step_text)

# Geometry record.
geom = [
    {"parameter":"r8_root_fillet_radius_mm", "value":R8_MM, "units":"mm", "note":"preserved exactly from B14B-11C R8"},
    {"parameter":"crop_xmin_mm", "value":XMIN, "units":"mm", "note":"box exceeds physical head xmin; no artificial x cut"},
    {"parameter":"crop_xmax_mm", "value":XMAX, "units":"mm", "note":"box exceeds physical head xmax; no artificial x cut"},
    {"parameter":"crop_ymin_mm", "value":YMIN, "units":"mm", "note":"box exceeds physical head ymin"},
    {"parameter":"crop_ymax_mm", "value":YMAX, "units":"mm", "note":"artificial horn/taper cut plane"},
    {"parameter":"crop_zmin_mm", "value":ZMIN, "units":"mm", "note":"artificial barrel cut plane"},
    {"parameter":"crop_zmax_mm", "value":ZMAX, "units":"mm", "note":"box exceeds physical head zmax"},
    {"parameter":"hotspot_x_mm", "value":HOTSPOT[0], "units":"mm", "note":"latest refined full-model R8 head hotspot"},
    {"parameter":"hotspot_y_mm", "value":HOTSPOT[1], "units":"mm", "note":"latest refined full-model R8 head hotspot"},
    {"parameter":"hotspot_z_mm", "value":HOTSPOT[2], "units":"mm", "note":"latest refined full-model R8 head hotspot"},
    {"parameter":"hotspot_min_distance_to_artificial_cut_mm", "value":min_hotspot_distance_to_artificial_cut(HOTSPOT), "units":"mm", "note":"min of horn-cut and barrel-cut distance"},
    {"parameter":"full_r8_head_volume_mm3", "value":head_r8.Volume(), "units":"mm^3", "note":"before submodel crop"},
    {"parameter":"local_r8_head_volume_mm3", "value":head_local.Volume(), "units":"mm^3", "note":"after crop"},
    {"parameter":"local_volume_fraction", "value":head_local.Volume()/head_r8.Volume(), "units":"-", "note":"local/full 7075 head volume"},
    {"parameter":"horn_y180_cut_area_mm2", "value":sum(f.Area() for f in y_cut_faces), "units":"mm^2", "note":"Imported Displacement candidate cut boundary"},
    {"parameter":"barrel_z850_cut_area_mm2", "value":sum(f.Area() for f in z_cut_faces), "units":"mm^2", "note":"Imported Displacement candidate cut boundary"},
]

write_rows(OUT_GEOM, geom)
write_rows(OUT_VAL, checks)

fails = [r for r in checks if r["status"] != "PASS"]
status = "PASS" if not fails else "FAIL"

summary = f"""PHASE 2E3-B14B-11D — R8 ROOT LOCAL SUBMODEL CAD V0.1

SOURCE
------
Exact B14B-9 source-connected geometry rebuilt from project artifacts.
R8 root fillet: {R8_MM:.3f} mm, reproduced using the B14B-11C construction method.

LOCAL ENVELOPE
--------------
7075 local head crop:
  x = [{XMIN:.1f}, {XMAX:.1f}] mm (no physical x cut)
  y = [{YMIN:.1f}, {YMAX:.1f}] mm (artificial cut at y={YMAX:.1f})
  z = [{ZMIN:.1f}, {ZMAX:.1f}] mm (artificial cut at z={ZMIN:.1f})

Latest R8 hotspot:
  ({HOTSPOT[0]:.6f}, {HOTSPOT[1]:.6f}, {HOTSPOT[2]:.6f}) mm
Minimum hotspot distance to an artificial cut:
  {min_hotspot_distance_to_artificial_cut(HOTSPOT):.6f} mm

BODY CONTENTS
-------------
- HEAD_BARREL_7075_R8_LOCAL: cropped local 7075 head/horn, R8 preserved
- SHAFT_300M_CONTINUOUS: unchanged
- BUSHING_LEFT_AMS4640: unchanged
- BUSHING_RIGHT_AMS4640: unchanged
- THRUST_COLLAR_LEFT_300M: unchanged
- THRUST_COLLAR_RIGHT_300M: unchanged

Artificial 7075 cut faces:
  horn/taper boundary y={YMAX:.1f}: count={len(y_cut_faces)}, area={sum(f.Area() for f in y_cut_faces):.3f} mm^2
  barrel boundary z={ZMIN:.1f}: count={len(z_cut_faces)}, area={sum(f.Area() for f in z_cut_faces):.3f} mm^2

VOLUME
------
Full R8 7075 head:  {head_r8.Volume():.3f} mm^3
Local R8 7075 head: {head_local.Volume():.3f} mm^3
Local/full fraction: {head_local.Volume()/head_r8.Volume():.6f}

EXPORTS
-------
Main six-body local assembly:
  {OUT_STEP.name}
Optional head-only local body:
  {OUT_HEAD_ONLY_STEP.name}

VALIDATION
----------
Checks: {len(checks)}
Failures: {len(fails)}
Gate: {status}_B14B11D_R8_LOCAL_SUBMODEL_GEOMETRY

ANSYS INTENT
------------
Use this as a local submodel geometry. The two planar 7075 artificial cut faces at
z={ZMIN:.1f} mm and y={YMAX:.1f} mm are the intended parent-to-submodel displacement
mapping boundaries. Preserve the physical journal contacts/support architecture if the
six-body assembly is used. Do not reapply the parent remote force/moment or brace spring
on portions removed by the crop; their effect should enter through imported parent
boundary displacements. Retain physical loads that act on surfaces still inside the
local domain only if they were present in the parent analysis.

STATUS
------
WORKING LOCAL-FEA SUBMODEL GEOMETRY — NOT DETAIL-DESIGN FREEZE.
"""
OUT_SUMMARY.write_text(summary, encoding="utf-8")

print(summary)
if fails:
    for r in fails:
        print("FAIL:", r)
    raise RuntimeError(f"B14B11D geometry validation failed with {len(fails)} failed checks")
