
"""
Landing_Gear_Design_Project
PHASE 2E3-B14B-11E V0.1 — R8 SINGLE-BODY ROOT SUBMODEL CAD

Purpose
-------
Create a true displacement-driven local submodel containing ONLY the 7075 root
material around the R8 hotspot. All shaft/bushing/collar/contact hardware is
removed. Every non-physical truncation surface is an artificial cut boundary
that is to receive imported displacement from the solved full R8 parent model.

Source connection
-----------------
Rebuilds the exact source-connected B14B-9 head/horn and applies the exact
R8 = 8 mm root fillet used by B14B-11C/B14B-11D. No geometry dimensions are
copied from chat.

Status
------
WORKING LOCAL-FEA SUBMODEL GEOMETRY — NOT DETAIL-DESIGN FREEZE.
"""
from __future__ import annotations
import csv, math, runpy
from pathlib import Path
import cadquery as cq

HERE = Path(__file__).resolve().parent
BASE_BUILDER = HERE / "phase2e3b14b9_build_physical_horn_clevis_v01.py"

OUT_STEP = HERE / "phase2e3b14b11e_r8_root_local_solid_v01.step"
OUT_GEOM = HERE / "phase2e3b14b11e_r8_root_local_solid_geometry_v01.csv"
OUT_VAL = HERE / "phase2e3b14b11e_r8_root_local_solid_validation_v01.csv"
OUT_SUMMARY = HERE / "phase2e3b14b11e_r8_root_local_solid_summary_v01.txt"

R8_MM = 8.0
HOTSPOT = (18.702387, 49.818011, 964.937219)
O_Y = 0.0
O_Z = 1012.780
MAX_PASSAGE_RADIUS_MM = 25.0

XMIN, XMAX = -60.0, 60.0
YMIN, YMAX = 25.0, 120.0
ZMIN, ZMAX = 920.0, 992.0

GEOM_TOL = 1e-4

def write_rows(path: Path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

def add_check(rows, name, actual, expected, units="-", tol=0.0, note=""):
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        ok = abs(float(actual) - float(expected)) <= tol
    else:
        ok = actual == expected
    rows.append({
        "check": name, "actual": actual, "expected": expected, "units": units,
        "tolerance": tol, "status": "PASS" if ok else "FAIL", "note": note
    })
    return ok

def cut_faces(shape, axis, value):
    out = []
    for f in shape.Faces():
        bb = f.BoundingBox()
        if axis == "y" and abs(bb.ymin-value) < GEOM_TOL and abs(bb.ymax-value) < GEOM_TOL:
            out.append(f)
        if axis == "z" and abs(bb.zmin-value) < GEOM_TOL and abs(bb.zmax-value) < GEOM_TOL:
            out.append(f)
    return out

# Rebuild exact B14B-9 source geometry.
g = runpy.run_path(str(BASE_BUILDER))
horn_before_cuts = g["horn_before_cuts"]
slot_cutter = g["slot_cutter"]
pin_hole_cutter = g["pin_hole_cutter"]
parent_head = g["parent_head"]
parent_named = g["parent_named"]
root_y = float(g["root_center_global"][1])

root_edges = []
for edge in horn_before_cuts.Edges():
    bb = edge.BoundingBox()
    if abs(bb.ymin-root_y) <= 1e-7 and abs(bb.ymax-root_y) <= 1e-7:
        root_edges.append(edge)
if len(root_edges) != 4:
    raise RuntimeError(f"Expected 4 B14B root edges, found {len(root_edges)}")

horn_r8 = horn_before_cuts.fillet(R8_MM, root_edges).cut(slot_cutter).cut(pin_hole_cutter)
head_r8 = parent_head.fuse(horn_r8)

box = (
    cq.Workplane("XY")
    .box(XMAX-XMIN, YMAX-YMIN, ZMAX-ZMIN, centered=(False, False, False))
    .translate((XMIN, YMIN, ZMIN))
    .val()
)
local = head_r8.intersect(box)

ymin_faces = cut_faces(local, "y", YMIN)
ymax_faces = cut_faces(local, "y", YMAX)
zmin_faces = cut_faces(local, "z", ZMIN)
zmax_faces = cut_faces(local, "z", ZMAX)

min_rect_radius = math.hypot(YMIN-O_Y, ZMAX-O_Z)
passage_margin = min_rect_radius - MAX_PASSAGE_RADIUS_MM

hx, hy, hz = HOTSPOT
cut_distances = {
    "ymin": hy-YMIN,
    "ymax": YMAX-hy,
    "zmin": hz-ZMIN,
    "zmax": ZMAX-hz,
}
min_hotspot_cut_distance = min(cut_distances.values())

checks = []
add_check(checks, "r8_root_edge_count", len(root_edges), 4)
add_check(checks, "full_r8_head_single_solid", len(head_r8.Solids()), 1)
add_check(checks, "local_single_solid", len(local.Solids()), 1)
add_check(
    checks, "hotspot_inside_local_box",
    XMIN < hx < XMAX and YMIN < hy < YMAX and ZMIN < hz < ZMAX, True
)
add_check(
    checks, "hotspot_min_cut_distance_gt_3R",
    min_hotspot_cut_distance > 3*R8_MM, True,
    note=f"min={min_hotspot_cut_distance:.6f} mm; 3R={3*R8_MM:.3f} mm"
)
add_check(
    checks, "passage_clearance_positive", passage_margin > 0, True,
    note=f"nearest yz radius={min_rect_radius:.6f} mm; passage R={MAX_PASSAGE_RADIUS_MM:.3f} mm; margin={passage_margin:.6f} mm"
)
add_check(checks, "cut_face_ymin_count", len(ymin_faces), 1)
add_check(checks, "cut_face_ymax_count", len(ymax_faces), 1)
add_check(checks, "cut_face_zmin_count", len(zmin_faces), 1)
add_check(checks, "cut_face_zmax_count", len(zmax_faces), 1)

bb = local.BoundingBox()
add_check(
    checks, "no_artificial_xmin_cut", abs(bb.xmin-XMIN) > 1.0, True,
    note=f"local xmin={bb.xmin:.6f} mm vs box xmin={XMIN:.3f}"
)
add_check(
    checks, "no_artificial_xmax_cut", abs(bb.xmax-XMAX) > 1.0, True,
    note=f"local xmax={bb.xmax:.6f} mm vs box xmax={XMAX:.3f}"
)

for name, data in parent_named.items():
    if name == "HEAD_BARREL_7075":
        continue
    iv = local.intersect(data["shape"]).Volume()
    add_check(checks, f"no_intersection__{name}", iv, 0.0, "mm^3", 1e-6)

assy = cq.Assembly(name="B14B11E_R8_ROOT_LOCAL_SOLID")
assy.add(local, name="HEAD_7075_R8_ROOT_LOCAL_SOLID")
assy.save(str(OUT_STEP))

re = cq.importers.importStep(str(OUT_STEP))
add_check(checks, "step_reimport_solid_count", len(re.solids().vals()), 1)
step_text = OUT_STEP.read_text(encoding="utf-8", errors="replace")
add_check(checks, "step_label_present", "HEAD_7075_R8_ROOT_LOCAL_SOLID" in step_text, True)

geom = [
    {"parameter":"r8_root_fillet_radius_mm","value":R8_MM,"units":"mm","note":"exact R8 construction retained"},
    {"parameter":"crop_xmin_mm","value":XMIN,"units":"mm","note":"outside local physical width; no x cut"},
    {"parameter":"crop_xmax_mm","value":XMAX,"units":"mm","note":"outside local physical width; no x cut"},
    {"parameter":"crop_ymin_mm","value":YMIN,"units":"mm","note":"artificial cut boundary"},
    {"parameter":"crop_ymax_mm","value":YMAX,"units":"mm","note":"artificial cut boundary"},
    {"parameter":"crop_zmin_mm","value":ZMIN,"units":"mm","note":"artificial cut boundary"},
    {"parameter":"crop_zmax_mm","value":ZMAX,"units":"mm","note":"artificial cut boundary"},
    {"parameter":"hotspot_x_mm","value":hx,"units":"mm","note":"full-model R8 reference hotspot"},
    {"parameter":"hotspot_y_mm","value":hy,"units":"mm","note":"full-model R8 reference hotspot"},
    {"parameter":"hotspot_z_mm","value":hz,"units":"mm","note":"full-model R8 reference hotspot"},
    {"parameter":"hotspot_min_distance_to_cut_mm","value":min_hotspot_cut_distance,"units":"mm","note":"minimum of four artificial-cut distances"},
    {"parameter":"nearest_crop_radius_from_trunnion_center_mm","value":min_rect_radius,"units":"mm","note":"yz-plane minimum"},
    {"parameter":"governing_passage_radius_mm","value":MAX_PASSAGE_RADIUS_MM,"units":"mm","note":"Ø50 source passage"},
    {"parameter":"passage_clearance_margin_mm","value":passage_margin,"units":"mm","note":"local crop avoids passage/contact surfaces"},
    {"parameter":"local_volume_mm3","value":local.Volume(),"units":"mm^3","note":"single 7075 local body"},
    {"parameter":"cut_ymin_area_mm2","value":sum(f.Area() for f in ymin_faces),"units":"mm^2","note":"map parent displacement"},
    {"parameter":"cut_ymax_area_mm2","value":sum(f.Area() for f in ymax_faces),"units":"mm^2","note":"map parent displacement"},
    {"parameter":"cut_zmin_area_mm2","value":sum(f.Area() for f in zmin_faces),"units":"mm^2","note":"map parent displacement"},
    {"parameter":"cut_zmax_area_mm2","value":sum(f.Area() for f in zmax_faces),"units":"mm^2","note":"map parent displacement"},
]
write_rows(OUT_GEOM, geom)
write_rows(OUT_VAL, checks)

fails = [r for r in checks if r["status"] != "PASS"]
gate = "PASS_B14B11E_R8_SINGLE_BODY_SUBMODEL_GEOMETRY" if not fails else "FAIL_B14B11E_R8_SINGLE_BODY_SUBMODEL_GEOMETRY"

summary = f"""PHASE 2E3-B14B-11E — R8 SINGLE-BODY ROOT SUBMODEL CAD V0.1

PURPOSE
-------
Final clean R8 local-stress path: one 7075 solid only; no shaft, bushings,
collars, contacts, journal supports, brace spring, remote force/moment, or
internal-pressure loads in the local model. Their effect is inherited through
parent-model displacement mapping on every artificial cut face.

SOURCE
------
Exact source-connected B14B-9 head/horn rebuilt in Python.
R8 fillet = {R8_MM:.3f} mm using the same construction as B14B-11C/B14B-11D.

LOCAL ENVELOPE
--------------
x box = [{XMIN:.1f}, {XMAX:.1f}] mm; no artificial x cut occurs.
y cuts = {YMIN:.1f}, {YMAX:.1f} mm.
z cuts = {ZMIN:.1f}, {ZMAX:.1f} mm.

Reference R8 hotspot = ({hx:.6f}, {hy:.6f}, {hz:.6f}) mm.
Minimum hotspot-to-cut distance = {min_hotspot_cut_distance:.6f} mm = {min_hotspot_cut_distance/R8_MM:.3f} R.
Nearest crop point to trunnion passage center = {min_rect_radius:.6f} mm.
Governing passage radius = {MAX_PASSAGE_RADIUS_MM:.3f} mm.
Passage/contact-surface clearance margin = {passage_margin:.6f} mm.

ARTIFICIAL CUT BOUNDARIES — CREATE FOUR NAMED SELECTIONS IN ANSYS
-----------------------------------------------------------------
1) NS_B14B11E_CUT_YMIN_25  : y = {YMIN:.1f} mm, area {sum(f.Area() for f in ymin_faces):.3f} mm^2
2) NS_B14B11E_CUT_YMAX_120 : y = {YMAX:.1f} mm, area {sum(f.Area() for f in ymax_faces):.3f} mm^2
3) NS_B14B11E_CUT_ZMIN_920 : z = {ZMIN:.1f} mm, area {sum(f.Area() for f in zmin_faces):.3f} mm^2
4) NS_B14B11E_CUT_ZMAX_992 : z = {ZMAX:.1f} mm, area {sum(f.Area() for f in zmax_faces):.3f} mm^2

All four get Imported Displacement from the solved full-R8 parent at End Time.
No other structural BC/load/contact is to be applied to this one-body submodel.
Physical exterior surfaces remain free, exactly as they are in the parent.

VALIDATION
----------
PASS checks: {sum(r['status']=='PASS' for r in checks)}
FAIL checks: {len(fails)}
Gate: {gate}

OUTPUT
------
{OUT_STEP.name}
{OUT_GEOM.name}
{OUT_VAL.name}
{OUT_SUMMARY.name}

STATUS
------
Working local-FEA geometry only. R8 design is not frozen until the quadratic
submodel stress converges through the planned short refinement sequence.
"""
OUT_SUMMARY.write_text(summary, encoding="utf-8")
print(summary)
if fails:
    raise SystemExit("Validation failed: " + ", ".join(r["check"] for r in fails))
