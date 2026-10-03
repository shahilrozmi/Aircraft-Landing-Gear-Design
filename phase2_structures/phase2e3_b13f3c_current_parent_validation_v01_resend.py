"""
Landing_Gear_Design_Project
PHASE 2E3 — B13F-3C CURRENT-PARENT GEOMETRY / TRACEABILITY VALIDATION V0.1

PURPOSE
-------
Validate the ACTUAL latest upper-attachment STEP before B14B-9 adds the physical
horn/clevis.

This supersedes use of the older four-body B13C model as the CAD parent.

EXPECTED CURRENT STEP PATTERN
-----------------------------
phase2e3_b13f_3c_d44_r1p5_t3p5_left_collar_partial_relief*.step

The script verifies from geometry, not chat:
    - six physical solids
    - 7075 head / barrel body
    - Ø38 x 175 mm 300M continuous shaft
    - two bronze bushings
    - two Ø58 x Ø38 x 3 mm 300M thrust collars
    - left bushing 3.5 mm flange
    - left bushing R1.5 inner-end toroidal relief/blend
    - current head central Ø44 passage segment
    - 4 mm Ø50-to-Ø44 conical transitions each side
    - left collar partial relief: Ø44 -> Ø46 cone over 0.12 mm axial depth
    - right collar full annulus
    - no solid-solid intersections
    - current shaft/head minimum central radial clearance
    - current trunnion centerline location in global CAD coordinates

It also scans the project directory for likely B13F source/summary files so the
geometry can be tied back to the later design work where available.

OUTPUTS
-------
phase2e3_b13f3c_current_parent_inventory.csv
phase2e3_b13f3c_current_parent_checks.csv
phase2e3_b13f3c_current_parent_source_scan.csv
phase2e3_b13f3c_current_parent_open_items.csv
phase2e3_b13f3c_current_parent_record.csv
phase2e3_b13f3c_current_parent_summary.txt
"""

from __future__ import annotations

import csv
import math
import re
from pathlib import Path

import cadquery as cq
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Cone, GeomAbs_Torus


HERE = Path(__file__).resolve().parent

STEP_PATTERNS = [
    "phase2e3_b13f_3c_d44_r1p5_t3p5_left_collar_partial_relief*.step",
    "*b13f*3c*d44*r1p5*t3p5*left*collar*partial*relief*.step",
]

OUT_INVENTORY = HERE / "phase2e3_b13f3c_current_parent_inventory.csv"
OUT_CHECKS = HERE / "phase2e3_b13f3c_current_parent_checks.csv"
OUT_SOURCE = HERE / "phase2e3_b13f3c_current_parent_source_scan.csv"
OUT_OPEN = HERE / "phase2e3_b13f3c_current_parent_open_items.csv"
OUT_RECORD = HERE / "phase2e3_b13f3c_current_parent_record.csv"
OUT_SUMMARY = HERE / "phase2e3_b13f3c_current_parent_summary.txt"

TOL_MM = 1e-3
TOL_VOL = 1e-3


# =============================================================================
# 1. HELPERS
# =============================================================================

def write_rows(path: Path, rows):
    if not rows:
        rows = [{"status": "NONE"}]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def find_step():
    for pat in STEP_PATTERNS:
        matches = sorted(HERE.rglob(pat))
        if matches:
            return matches[-1]
    raise FileNotFoundError(
        "Could not find the B13F-3C current-parent STEP under phase2_structures."
    )


def axis_tuple(direction):
    return (
        float(direction.X()),
        float(direction.Y()),
        float(direction.Z()),
    )


def axis_is(direction, axis, tol=1e-7):
    x, y, z = axis_tuple(direction)
    if axis == "x":
        return abs(abs(x) - 1.0) < tol and abs(y) < tol and abs(z) < tol
    if axis == "z":
        return abs(abs(z) - 1.0) < tol and abs(x) < tol and abs(y) < tol
    return False


def surfaces(shape):
    cyls = []
    cones = []
    tori = []

    for face in shape.Faces():
        ad = BRepAdaptor_Surface(face.wrapped)
        bb = face.BoundingBox()

        if ad.GetType() == GeomAbs_Cylinder:
            c = ad.Cylinder()
            cyls.append({
                "radius": float(c.Radius()),
                "axis": axis_tuple(c.Axis().Direction()),
                "xmin": bb.xmin, "xmax": bb.xmax,
                "ymin": bb.ymin, "ymax": bb.ymax,
                "zmin": bb.zmin, "zmax": bb.zmax,
            })

        elif ad.GetType() == GeomAbs_Cone:
            c = ad.Cone()
            cones.append({
                "ref_radius": float(c.RefRadius()),
                "semi_angle_rad": float(c.SemiAngle()),
                "axis": axis_tuple(c.Axis().Direction()),
                "xmin": bb.xmin, "xmax": bb.xmax,
                "ymin": bb.ymin, "ymax": bb.ymax,
                "zmin": bb.zmin, "zmax": bb.zmax,
            })

        elif ad.GetType() == GeomAbs_Torus:
            t = ad.Torus()
            tori.append({
                "major_radius": float(t.MajorRadius()),
                "minor_radius": float(t.MinorRadius()),
                "axis": axis_tuple(t.Axis().Direction()),
                "xmin": bb.xmin, "xmax": bb.xmax,
                "ymin": bb.ymin, "ymax": bb.ymax,
                "zmin": bb.zmin, "zmax": bb.zmax,
            })

    return cyls, cones, tori


def near(a, b, tol=TOL_MM):
    return abs(a - b) <= tol


def match_cyl(cyls, radius, axis, xmin=None, xmax=None, tol=TOL_MM):
    out = []
    for c in cyls:
        if not near(c["radius"], radius, tol):
            continue
        x, y, z = c["axis"]
        if axis == "x" and not (abs(abs(x)-1) < 1e-7 and abs(y)<1e-7 and abs(z)<1e-7):
            continue
        if axis == "z" and not (abs(abs(z)-1) < 1e-7 and abs(x)<1e-7 and abs(y)<1e-7):
            continue
        if xmin is not None and not near(c["xmin"], xmin, tol):
            continue
        if xmax is not None and not near(c["xmax"], xmax, tol):
            continue
        out.append(c)
    return out


def add_check(rows, name, actual, expected, units="-", note="", tol=None):
    if tol is None:
        tol = TOL_MM
    passed = abs(actual - expected) <= tol
    rows.append({
        "check": name,
        "actual": actual,
        "expected": expected,
        "units": units,
        "difference": actual - expected,
        "status": "PASS" if passed else "FAIL",
        "note": note,
    })


def product_names(step_text):
    names = re.findall(r"PRODUCT\('([^']+)'", step_text)
    return names


def classify_solids(solids):
    recs = []

    for i, s in enumerate(solids):
        bb = s.BoundingBox()
        recs.append({
            "index": i,
            "shape": s,
            "volume_mm3": s.Volume(),
            "xmin": bb.xmin, "xmax": bb.xmax,
            "ymin": bb.ymin, "ymax": bb.ymax,
            "zmin": bb.zmin, "zmax": bb.zmax,
            "xlen": bb.xlen, "ylen": bb.ylen, "zlen": bb.zlen,
            "xmid": 0.5*(bb.xmin + bb.xmax),
        })

    # Geometry-signature classification.
    head = max(recs, key=lambda r: r["volume_mm3"])

    shaft_candidates = [
        r for r in recs
        if r is not head
        and near(r["xlen"], 175.0, 0.02)
        and near(r["ylen"], 38.0, 0.02)
        and near(r["zlen"], 38.0, 0.02)
    ]
    if len(shaft_candidates) != 1:
        raise RuntimeError(f"Could not uniquely classify shaft: {len(shaft_candidates)} candidates")
    shaft = shaft_candidates[0]

    collars = [
        r for r in recs
        if r not in (head, shaft)
        and near(r["xlen"], 3.0, 0.02)
        and near(r["ylen"], 58.0, 0.02)
        and near(r["zlen"], 58.0, 0.02)
    ]
    if len(collars) != 2:
        raise RuntimeError(f"Could not classify two collars: {len(collars)} found")

    bushings = [
        r for r in recs
        if r not in (head, shaft)
        and r not in collars
    ]
    if len(bushings) != 2:
        raise RuntimeError(f"Could not classify two bushings: {len(bushings)} found")

    left_collar = min(collars, key=lambda r: r["xmid"])
    right_collar = max(collars, key=lambda r: r["xmid"])
    left_bushing = min(bushings, key=lambda r: r["xmid"])
    right_bushing = max(bushings, key=lambda r: r["xmid"])

    return {
        "HEAD_BARREL_7075": head,
        "SHAFT_300M_CONTINUOUS": shaft,
        "BUSHING_LEFT_AMS4640": left_bushing,
        "BUSHING_RIGHT_AMS4640": right_bushing,
        "THRUST_COLLAR_LEFT_300M": left_collar,
        "THRUST_COLLAR_RIGHT_300M": right_collar,
    }


# =============================================================================
# 2. IMPORT CURRENT STEP
# =============================================================================

step_path = find_step()
step_text = step_path.read_text(encoding="utf-8", errors="replace")
products = product_names(step_text)

assembly = cq.importers.importStep(str(step_path))
solids = assembly.solids().vals()
bodies = classify_solids(solids)

surf = {}
for name, rec in bodies.items():
    surf[name] = surfaces(rec["shape"])


# =============================================================================
# 3. GEOMETRY EXTRACTION
# =============================================================================

head = bodies["HEAD_BARREL_7075"]
shaft = bodies["SHAFT_300M_CONTINUOUS"]
lb = bodies["BUSHING_LEFT_AMS4640"]
rb = bodies["BUSHING_RIGHT_AMS4640"]
lc = bodies["THRUST_COLLAR_LEFT_300M"]
rc = bodies["THRUST_COLLAR_RIGHT_300M"]

head_cyl, head_cones, head_tori = surf["HEAD_BARREL_7075"]
lb_cyl, lb_cones, lb_tori = surf["BUSHING_LEFT_AMS4640"]
rb_cyl, rb_cones, rb_tori = surf["BUSHING_RIGHT_AMS4640"]
lc_cyl, lc_cones, lc_tori = surf["THRUST_COLLAR_LEFT_300M"]
rc_cyl, rc_cones, rc_tori = surf["THRUST_COLLAR_RIGHT_300M"]

# Shaft geometry from bbox.
shaft_d = 0.5*(shaft["ylen"] + shaft["zlen"])
shaft_L = shaft["xlen"]
trunnion_z = 0.5*(shaft["zmin"] + shaft["zmax"])
trunnion_y = 0.5*(shaft["ymin"] + shaft["ymax"])

# Head outer boss cylinder.
boss53 = [
    c for c in head_cyl
    if near(c["radius"], 53.0)
    and abs(abs(c["axis"][2]) - 1.0) < 1e-7
]
if not boss53:
    raise RuntimeError("Ø106 upper-head cylindrical boss was not found.")
boss_D = 2.0*boss53[0]["radius"]
boss_H = boss53[0]["zmax"] - boss53[0]["zmin"]

# Head X-axis passage surfaces.
head_r25 = sorted(
    [c for c in head_cyl if near(c["radius"], 25.0) and abs(abs(c["axis"][0])-1.0)<1e-7],
    key=lambda c: c["xmin"],
)
head_r22 = sorted(
    [c for c in head_cyl if near(c["radius"], 22.0) and abs(abs(c["axis"][0])-1.0)<1e-7],
    key=lambda c: c["xmin"],
)
head_r30 = sorted(
    [c for c in head_cyl if near(c["radius"], 30.0) and abs(abs(c["axis"][0])-1.0)<1e-7],
    key=lambda c: c["xmin"],
)

if len(head_r25) != 2:
    raise RuntimeError(f"Expected two Ø50 head passage cylinders, found {len(head_r25)}.")
if len(head_r22) != 1:
    raise RuntimeError(f"Expected one central Ø44 head passage cylinder, found {len(head_r22)}.")

central44 = head_r22[0]
central44_L = central44["xmax"] - central44["xmin"]
min_radial_clearance = 22.0 - shaft_d/2.0

# Ø50 -> Ø44 transition cones: identify X-axis cones near trunnion.
x_cones = [
    c for c in head_cones
    if abs(abs(c["axis"][0]) - 1.0) < 1e-7
    and c["zmin"] < trunnion_z < c["zmax"]
]
x_cones = sorted(x_cones, key=lambda c: c["xmin"])

# Right bushing surfaces.
rb_r25 = [
    c for c in rb_cyl
    if near(c["radius"], 25.0) and abs(abs(c["axis"][0])-1.0)<1e-7
]
rb_r30 = [
    c for c in rb_cyl
    if near(c["radius"], 30.0) and abs(abs(c["axis"][0])-1.0)<1e-7
]
rb_r19 = [
    c for c in rb_cyl
    if near(c["radius"], 19.0) and abs(abs(c["axis"][0])-1.0)<1e-7
]
if not (rb_r25 and rb_r30 and rb_r19):
    raise RuntimeError("Could not resolve right bushing Ø50/Ø60/Ø38 surfaces.")

rb_sleeve_L = max(c["xmax"]-c["xmin"] for c in rb_r25)
rb_flange_t = max(c["xmax"]-c["xmin"] for c in rb_r30)

# Left bushing: Ø60 flange and R1.5 toroidal inner-end blend.
lb_r30 = [
    c for c in lb_cyl
    if near(c["radius"], 30.0) and abs(abs(c["axis"][0])-1.0)<1e-7
]
lb_r19 = [
    c for c in lb_cyl
    if near(c["radius"], 19.0) and abs(abs(c["axis"][0])-1.0)<1e-7
]
if not (lb_r30 and lb_r19):
    raise RuntimeError("Could not resolve left bushing flange/bore surfaces.")

lb_flange_xmin = min(c["xmin"] for c in lb_r30)
lb_flange_xmax = max(c["xmax"] for c in lb_r30)
lb_flange_t = lb_flange_xmax - lb_flange_xmin

lb_r15_tori = [
    t for t in lb_tori
    if near(t["minor_radius"], 1.5)
]
if len(lb_r15_tori) != 1:
    raise RuntimeError(f"Expected one R1.5 torus on left bushing, found {len(lb_r15_tori)}.")
lb_blend = lb_r15_tori[0]

# Sleeve endpoint is the most-positive x of the left bushing cylindrical bore.
lb_inner_end_x = max(c["xmax"] for c in lb_r19)
lb_spotface_x = lb_flange_xmax
lb_sleeve_axial_to_inner_end = lb_inner_end_x - lb_spotface_x

# Collars.
rc_r29 = [c for c in rc_cyl if near(c["radius"], 29.0)]
rc_r19 = [c for c in rc_cyl if near(c["radius"], 19.0)]
lc_r29 = [c for c in lc_cyl if near(c["radius"], 29.0)]
lc_r19 = [c for c in lc_cyl if near(c["radius"], 19.0)]

if not (rc_r29 and rc_r19 and lc_r29 and lc_r19):
    raise RuntimeError("Could not resolve Ø58/Ø38 collar surfaces.")

rc_t = rc["xlen"]
lc_t = lc["xlen"]

# Left collar partial relief cone.
lc_relief_cones = [
    c for c in lc_cones
    if abs(abs(c["axis"][0])-1.0) < 1e-7
]
if len(lc_relief_cones) != 1:
    raise RuntimeError(f"Expected one left-collar relief cone, found {len(lc_relief_cones)}.")

relief_cone = lc_relief_cones[0]
relief_depth = relief_cone["xmax"] - relief_cone["xmin"]
# Bounding radius at inner and outer ends is recoverable from bbox.
relief_r_outer = 0.5*(relief_cone["ymax"] - relief_cone["ymin"])  # 23
relief_r_inner = relief_cone["ref_radius"]                        # 22

# Analytic collar volumes.
full_collar_volume = math.pi*(29.0**2 - 19.0**2)*3.0
relief_removed_volume = (
    math.pi*relief_depth/3.0
    * (relief_r_inner**2 + relief_r_inner*relief_r_outer + relief_r_outer**2)
    - math.pi*19.0**2*relief_depth
)
left_expected_volume = full_collar_volume - relief_removed_volume


# =============================================================================
# 4. CHECKS
# =============================================================================

checks = []

# Assembly/product structure.
expected_products = [
    "HEAD_BARREL_7075",
    "SHAFT_300M_CONTINUOUS",
    "BUSHING_LEFT_AMS4640",
    "BUSHING_RIGHT_AMS4640",
    "THRUST_COLLAR_LEFT_300M",
    "THRUST_COLLAR_RIGHT_300M",
]

for p in expected_products:
    checks.append({
        "check": f"STEP_product_{p}",
        "actual": 1 if p in products else 0,
        "expected": 1,
        "units": "-",
        "difference": 0 if p in products else -1,
        "status": "PASS" if p in products else "FAIL",
        "note": "Product label must exist in current-parent STEP.",
    })

add_check(checks, "solid_count", len(solids), 6, "-", tol=0)

# Core geometry.
add_check(checks, "upper_head_boss_diameter", boss_D, 106.0, "mm")
add_check(checks, "upper_head_boss_height", boss_H, 78.0, "mm")
add_check(checks, "shaft_diameter", shaft_d, 38.0, "mm")
add_check(checks, "shaft_length", shaft_L, 175.0, "mm")

# Right bushing baseline.
add_check(checks, "right_bushing_sleeve_OD", 2*25.0, 50.0, "mm")
add_check(checks, "right_bushing_bore_ID", 2*19.0, 38.0, "mm")
add_check(checks, "right_bushing_sleeve_length", rb_sleeve_L, 30.0, "mm")
add_check(checks, "right_bushing_flange_OD", 2*30.0, 60.0, "mm")
add_check(checks, "right_bushing_flange_thickness", rb_flange_t, 3.0, "mm")

# Left revised bushing.
add_check(checks, "left_bushing_flange_OD", 2*30.0, 60.0, "mm")
add_check(checks, "left_bushing_flange_thickness_T3p5", lb_flange_t, 3.5, "mm")
add_check(checks, "left_bushing_axial_spotface_to_inner_end", lb_sleeve_axial_to_inner_end, 30.0, "mm")
add_check(checks, "left_bushing_inner_blend_R1p5", lb_blend["minor_radius"], 1.5, "mm")
add_check(checks, "left_bushing_inner_blend_major_radius", lb_blend["major_radius"], 23.5, "mm")

# Current head passage — this deliberately supersedes old B13C Ø50-through geometry.
add_check(checks, "head_side_passage_diameter", 2*25.0, 50.0, "mm")
add_check(checks, "head_central_passage_diameter_D44", 2*22.0, 44.0, "mm")
add_check(checks, "head_central_D44_straight_length", central44_L, 17.3842090998, "mm", tol=2e-3)
add_check(checks, "shaft_to_head_min_radial_clearance_current", min_radial_clearance, 3.0, "mm")

if len(x_cones) >= 2:
    left_trans_L = x_cones[0]["xmax"] - x_cones[0]["xmin"]
    right_trans_L = x_cones[-1]["xmax"] - x_cones[-1]["xmin"]
    add_check(checks, "left_D50_to_D44_transition_length", left_trans_L, 4.0, "mm")
    add_check(checks, "right_D44_to_D50_transition_length", right_trans_L, 4.0, "mm")
else:
    checks.append({
        "check": "head_transition_cones",
        "actual": len(x_cones),
        "expected": 2,
        "units": "-",
        "difference": len(x_cones)-2,
        "status": "FAIL",
        "note": "Expected two X-axis passage transition cones.",
    })

# Collars.
add_check(checks, "right_collar_OD", rc["ylen"], 58.0, "mm")
add_check(checks, "right_collar_ID", 2*19.0, 38.0, "mm")
add_check(checks, "right_collar_thickness", rc_t, 3.0, "mm")
add_check(checks, "right_collar_volume_full_annulus", rc["volume_mm3"], full_collar_volume, "mm^3", tol=TOL_VOL)

add_check(checks, "left_collar_OD", lc["ylen"], 58.0, "mm")
add_check(checks, "left_collar_overall_thickness", lc_t, 3.0, "mm")
add_check(checks, "left_collar_relief_min_diameter_D44", 2*relief_r_inner, 44.0, "mm")
add_check(checks, "left_collar_relief_face_diameter_D46", 2*relief_r_outer, 46.0, "mm")
add_check(checks, "left_collar_relief_axial_depth", relief_depth, 0.12, "mm", tol=2e-3)
add_check(checks, "left_collar_volume_partial_relief", lc["volume_mm3"], left_expected_volume, "mm^3", tol=TOL_VOL)

# Trunnion centerline.
add_check(checks, "trunnion_centerline_y", trunnion_y, 0.0, "mm")
add_check(checks, "trunnion_centerline_z", trunnion_z, 1012.78, "mm", tol=2e-3)


# =============================================================================
# 5. INTERSECTION CHECKS
# =============================================================================

names = list(bodies)
intersection_rows = []

for i in range(len(names)):
    for j in range(i+1, len(names)):
        a = bodies[names[i]]["shape"]
        b = bodies[names[j]]["shape"]
        try:
            iv = a.intersect(b).Volume()
        except Exception:
            iv = float("nan")

        passed = math.isfinite(iv) and abs(iv) <= 1e-6

        intersection_rows.append({
            "check": f"intersection_{names[i]}__{names[j]}",
            "actual": iv,
            "expected": 0.0,
            "units": "mm^3",
            "difference": iv if math.isfinite(iv) else "",
            "status": "PASS" if passed else "FAIL",
            "note": "Separate physical bodies should not have positive common volume.",
        })

checks.extend(intersection_rows)


# =============================================================================
# 6. SOURCE SCAN
# =============================================================================

source_rows = []

tokens = [
    "b13f",
    "partial_collar_relief",
    "partial collar relief",
    "d44",
    "r1p5",
    "t3p5",
    "thrust_collar",
    "thrust collar",
]

for ext in ("*.py", "*.csv", "*.txt"):
    for p in HERE.rglob(ext):
        if p in {
            OUT_INVENTORY, OUT_CHECKS, OUT_SOURCE, OUT_OPEN, OUT_RECORD, OUT_SUMMARY
        }:
            continue

        try:
            txt = p.read_text(encoding="utf-8-sig", errors="ignore").lower()
        except Exception:
            continue

        hits = [t for t in tokens if t in txt or t in p.name.lower()]
        if hits:
            source_rows.append({
                "file": str(p.relative_to(HERE)),
                "hits": " | ".join(hits),
                "classification": (
                    "B13F_LIKELY_SOURCE"
                    if "b13f" in hits
                    else "RELATED_GEOMETRY_SOURCE"
                ),
            })

source_rows = sorted(source_rows, key=lambda r: r["file"].lower())


# =============================================================================
# 7. BODY INVENTORY
# =============================================================================

inventory = []

for name, rec in bodies.items():
    inventory.append({
        "body": name,
        "volume_mm3": rec["volume_mm3"],
        "xmin_mm": rec["xmin"],
        "xmax_mm": rec["xmax"],
        "ymin_mm": rec["ymin"],
        "ymax_mm": rec["ymax"],
        "zmin_mm": rec["zmin"],
        "zmax_mm": rec["zmax"],
        "x_length_mm": rec["xlen"],
        "y_length_mm": rec["ylen"],
        "z_length_mm": rec["zlen"],
    })


# =============================================================================
# 8. OPEN ITEMS / SUPERSESSION
# =============================================================================

open_items = [
    {
        "item": "OLD_B13C_GEOMETRY_AS_CURRENT_PARENT",
        "status": "SUPERSEDED",
        "reason": (
            "The latest B13F-3C geometry contains six bodies, two thrust collars, "
            "a revised left bushing and a central Ø44 passage segment. "
            "The old four-body B13C STEP must remain historical/reference only."
        ),
    },
    {
        "item": "COMPLETE_EXTERNAL_SHAFT_RETENTION",
        "status": "OPEN_NOT_FROZEN",
        "reason": (
            "Two thrust collars are now geometry-verified, but the complete external "
            "positive-retention hardware / airframe-side retention stack is not represented "
            "as separate bodies in this STEP."
        ),
    },
    {
        "item": "AIRFRAME_BEARING_BODIES",
        "status": "OPEN_NOT_FROZEN",
        "reason": (
            "The current parent contains head, shaft, two bushings and two collars only. "
            "Airframe bearing/fitting geometry remains external to this STEP."
        ),
    },
    {
        "item": "B13F_SOURCE_LINK",
        "status": "CHECK_SOURCE_SCAN",
        "reason": (
            "Use phase2e3_b13f3c_current_parent_source_scan.csv to confirm the exact "
            "later B13F Python/CSV/TXT source files that selected D44/R1.5/T3.5."
        ),
    },
]


# =============================================================================
# 9. GATE / RECORD
# =============================================================================

failures = [r for r in checks if r["status"] == "FAIL"]

if failures:
    gate = "FAIL_CURRENT_PARENT_GEOMETRY"
    approved_for_b14b9 = False
else:
    gate = "PASS_CURRENT_PARENT_VALIDATED_FOR_B14B9"
    approved_for_b14b9 = True

record = [{
    "current_parent_step": str(step_path),
    "step_product": "B13F_3C_PARTIAL_COLLAR_RELIEF",
    "solid_count": len(solids),
    "trunnion_center_x_mm": 0.0,
    "trunnion_center_y_mm": trunnion_y,
    "trunnion_center_z_mm": trunnion_z,
    "head_boss_diameter_mm": boss_D,
    "head_boss_height_mm": boss_H,
    "shaft_diameter_mm": shaft_d,
    "shaft_length_mm": shaft_L,
    "head_side_passage_diameter_mm": 50.0,
    "head_central_passage_diameter_mm": 44.0,
    "minimum_shaft_head_radial_clearance_mm": min_radial_clearance,
    "left_bushing_flange_thickness_mm": lb_flange_t,
    "left_bushing_inner_blend_radius_mm": lb_blend["minor_radius"],
    "right_bushing_flange_thickness_mm": rb_flange_t,
    "left_collar_OD_mm": lc["ylen"],
    "left_collar_thickness_mm": lc_t,
    "left_collar_relief_min_diameter_mm": 2*relief_r_inner,
    "left_collar_relief_face_diameter_mm": 2*relief_r_outer,
    "left_collar_relief_depth_mm": relief_depth,
    "right_collar_OD_mm": rc["ylen"],
    "right_collar_thickness_mm": rc_t,
    "geometry_gate": gate,
    "approved_as_B14B9_parent": approved_for_b14b9,
    "classification": "CURRENT_VALIDATED_PARENT_NOT_FINAL_ASSEMBLY_FREEZE",
}]


# =============================================================================
# 10. WRITE OUTPUTS
# =============================================================================

write_rows(OUT_INVENTORY, inventory)
write_rows(OUT_CHECKS, checks)
write_rows(OUT_SOURCE, source_rows)
write_rows(OUT_OPEN, open_items)
write_rows(OUT_RECORD, record)


# =============================================================================
# 11. SUMMARY
# =============================================================================

pass_count = sum(r["status"] == "PASS" for r in checks)
fail_count = sum(r["status"] == "FAIL" for r in checks)

lines = []
emit = lines.append

emit("=" * 140)
emit(" PHASE 2E3 — B13F-3C CURRENT-PARENT GEOMETRY / TRACEABILITY VALIDATION V0.1")
emit("=" * 140)
emit("")
emit("CURRENT PARENT")
emit("-" * 140)
emit(f"STEP:                 {step_path}")
emit(f"Top-level product:    {'B13F_3C_PARTIAL_COLLAR_RELIEF' if 'B13F_3C_PARTIAL_COLLAR_RELIEF' in products else 'NOT FOUND'}")
emit(f"Solid count:          {len(solids)}")
emit("")
emit("BODY INVENTORY")
emit("-" * 140)
for r in inventory:
    emit(
        f"{r['body']:30s} "
        f"V={r['volume_mm3']:12.3f} mm^3  "
        f"X[{r['xmin_mm']:9.3f},{r['xmax_mm']:9.3f}] "
        f"Y[{r['ymin_mm']:8.3f},{r['ymax_mm']:8.3f}] "
        f"Z[{r['zmin_mm']:9.3f},{r['zmax_mm']:9.3f}]"
    )
emit("")
emit("CURRENT TRUNNION / HEAD GEOMETRY")
emit("-" * 140)
emit(f"Trunnion center O_global:        [0.000, {trunnion_y:.3f}, {trunnion_z:.3f}] mm")
emit(f"Upper-head boss:                 Ø{boss_D:.3f} x {boss_H:.3f} mm high")
emit(f"Continuous shaft:                Ø{shaft_d:.3f} x {shaft_L:.3f} mm")
emit(f"Head side passage:               Ø50.000 mm")
emit(f"Head central passage:            Ø44.000 mm x {central44_L:.6f} mm straight")
emit(f"Current minimum shaft/head gap:  {min_radial_clearance:.3f} mm radial")
if len(x_cones) >= 2:
    emit(f"Left passage transition:         {x_cones[0]['xmax']-x_cones[0]['xmin']:.3f} mm axial")
    emit(f"Right passage transition:        {x_cones[-1]['xmax']-x_cones[-1]['xmin']:.3f} mm axial")
emit("")
emit("BUSHINGS")
emit("-" * 140)
emit(f"Right sleeve:                    Ø50/Ø38 x {rb_sleeve_L:.3f} mm")
emit(f"Right flange:                    Ø60/Ø38 x {rb_flange_t:.3f} mm")
emit(f"Left axial spotface->inner end:  {lb_sleeve_axial_to_inner_end:.3f} mm")
emit(f"Left flange:                     Ø60/Ø38 x {lb_flange_t:.3f} mm")
emit(f"Left inner-end torus:            major R={lb_blend['major_radius']:.3f} mm, minor R={lb_blend['minor_radius']:.3f} mm")
emit("")
emit("THRUST COLLARS")
emit("-" * 140)
emit(f"Right collar:                    Ø58/Ø38 x {rc_t:.3f} mm, full annulus")
emit(f"Left collar overall:             Ø58 x {lc_t:.3f} mm")
emit(f"Left collar partial relief:      Ø{2*relief_r_inner:.3f} -> Ø{2*relief_r_outer:.3f} over {relief_depth:.3f} mm axial")
emit(f"Right collar volume:             {rc['volume_mm3']:.6f} mm^3")
emit(f"Left collar volume:              {lc['volume_mm3']:.6f} mm^3")
emit("")
emit("CHECK RESULTS")
emit("-" * 140)
emit(f"PASS: {pass_count}")
emit(f"FAIL: {fail_count}")
if failures:
    for r in failures:
        emit(f"FAIL  {r['check']}: actual={r['actual']} expected={r['expected']} {r['units']}")
emit("")
emit("SUPERSESSION / TRACEABILITY")
emit("-" * 140)
emit("The old B13C four-body model is NOT the current CAD parent.")
emit("This B13F-3C six-body STEP is the current parent for B14B-9 if the gate passes.")
emit(f"Likely local B13F source/summary files found by scan: {len(source_rows)}")
emit("Use the source-scan CSV to identify the exact later calculation that selected D44/R1.5/T3.5.")
emit("")
emit("GATE")
emit("-" * 140)
emit(gate)
if approved_for_b14b9:
    emit("This STEP is approved as the geometry parent for the B14B-9 physical horn/clevis CAD build.")
    emit("This is NOT a final full-assembly freeze; external retention and airframe-side bearing/fitting details remain open.")
else:
    emit("Do not start B14B-9 until the failed current-parent geometry checks are resolved.")
emit("")
emit("OUTPUTS")
emit("-" * 140)
for p in [OUT_INVENTORY, OUT_CHECKS, OUT_SOURCE, OUT_OPEN, OUT_RECORD, OUT_SUMMARY]:
    emit(str(p))
emit("=" * 140)

report = "\n".join(lines)
OUT_SUMMARY.write_text(report, encoding="utf-8")
print(report)
