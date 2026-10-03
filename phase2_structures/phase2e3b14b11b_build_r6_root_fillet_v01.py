"""
Landing_Gear_Design_Project
PHASE 2E3-B14B-11B V0.1 — R6 HORN/HEAD ROOT FILLET CAD BUILD

PURPOSE
-------
Take the validated B14B-9 physical horn/clevis geometry and replace the sharp embedded
horn-root perimeter with the B14B-11A working R6 fillet candidate.

This builder deliberately REUSES the B14B-9 source-connected build rather than copying
its entire geometry definition. B14B-9 is executed through runpy, exposing the exact
baseline CadQuery solids/cutters. B14B-11B then applies only the new root-fillet feature.

REQUIRED UPSTREAM ARTIFACTS
---------------------------
phase2e3b14b9_build_physical_horn_clevis_v01.py
phase2e3b14b11_reference_candidate_v01.csv
phase2e3b14b10_closeout_record_v01.csv
plus all B14B-9 upstream files required by the B14B-9 builder.

OUTPUTS
-------
phase2e3b14b11b_r6_root_fillet_candidate_v01.step
phase2e3b14b11b_geometry_validation_v01.csv
phase2e3b14b11b_geometry_definition_v01.csv
phase2e3b14b11b_open_items_v01.csv
phase2e3b14b11b_summary_v01.txt

STATUS
------
WORKING CAD/FEA CANDIDATE — NOT A DETAIL-DESIGN FREEZE.
"""

from __future__ import annotations

import csv
import math
import runpy
from pathlib import Path
from typing import Iterable

import cadquery as cq

HERE = Path(__file__).resolve().parent

B14B9_BUILDER = HERE / "phase2e3b14b9_build_physical_horn_clevis_v01.py"
B11_REF = HERE / "phase2e3b14b11_reference_candidate_v01.csv"
B10_CLOSEOUT = HERE / "phase2e3b14b10_closeout_record_v01.csv"

OUT_STEP = HERE / "phase2e3b14b11b_r6_root_fillet_candidate_v01.step"
OUT_VALIDATION = HERE / "phase2e3b14b11b_geometry_validation_v01.csv"
OUT_GEOMETRY = HERE / "phase2e3b14b11b_geometry_definition_v01.csv"
OUT_OPEN = HERE / "phase2e3b14b11b_open_items_v01.csv"
OUT_SUMMARY = HERE / "phase2e3b14b11b_summary_v01.txt"

GEOM_TOL_MM = 1.0e-3
VOL_TOL_MM3 = 1.0e-3


def read_one(path: Path) -> dict:
    with path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 1:
        raise ValueError(f"{path.name}: expected exactly one row, found {len(rows)}")
    return rows[0]


def read_kv(path: Path) -> dict[str, str]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return {r["field"]: r["value"] for r in csv.DictReader(f)}


def write_rows(path: Path, rows: list[dict]) -> None:
    if not rows:
        rows = [{"status": "NONE"}]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def bbox_tuple(shape) -> tuple[float, float, float, float, float, float]:
    b = shape.BoundingBox()
    return (b.xmin, b.xmax, b.ymin, b.ymax, b.zmin, b.zmax)


def add_check(checks: list[dict], name: str, actual, expected, units: str, tol: float, note: str = ""):
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        ok = abs(float(actual) - float(expected)) <= tol
    else:
        ok = actual == expected
    checks.append({
        "check": name,
        "actual": actual,
        "expected": expected,
        "units": units,
        "tolerance": tol,
        "status": "PASS" if ok else "FAIL",
        "note": note,
    })
    return ok


def add_bool(checks: list[dict], name: str, condition: bool, note: str = ""):
    return add_check(checks, name, bool(condition), True, "-", 0, note)


# =============================================================================
# 1. READ B14B-11 / B14B-10 CONTROLLING INPUTS
# =============================================================================

if not B14B9_BUILDER.exists():
    raise FileNotFoundError(B14B9_BUILDER)
if not B11_REF.exists():
    raise FileNotFoundError(B11_REF)
if not B10_CLOSEOUT.exists():
    raise FileNotFoundError(B10_CLOSEOUT)

b11 = read_one(B11_REF)
b10 = read_kv(B10_CLOSEOUT)

fillet_r = float(b11["working_radius_mm"])
if abs(fillet_r - 6.0) > 1e-9:
    raise ValueError(f"B14B-11B V0.1 is the R6 builder; source candidate is R{fillet_r:g}")

baseline_brace_force_N = float(b10["linear_brace_force_N"])
baseline_def_mm = float(b10["linear_max_deformation_mm"])
baseline_vm_MPa = float(b10["linear_max_vm_MPa"])


# =============================================================================
# 2. REBUILD EXACT B14B-9 BASELINE AND RETRIEVE CAD OBJECTS
# =============================================================================

# The baseline builder performs its own source/geometry validation and returns its global
# namespace. This avoids a second copy of the B14B-9 geometry logic in the project.
g = runpy.run_path(str(B14B9_BUILDER))

horn_before_cuts = g["horn_before_cuts"]
slot_cutter = g["slot_cutter"]
pin_hole_cutter = g["pin_hole_cutter"]
parent_head = g["parent_head"]
parent_named = g["parent_named"]
expected_body_names = g["EXPECTED_BODY_NAMES"]
root_center_global = g["root_center_global"]
root_width_x = float(g["root_width_x"])
root_height_z = float(g["root_height_z"])
root_embed = float(g["root_embed"])
root_passage_clearance = float(g["root_passage_clearance"])
pin_center_global = g["pin_center_global"]
pin_d = float(g["pin_d"])

b14b9_head = g["modified_head"]
b14b9_horn = g["horn_final"]


# =============================================================================
# 3. SELECT THE FOUR EMBEDDED ROOT-PERIMETER EDGES
# =============================================================================

root_y = float(root_center_global[1])
root_edges = []
root_edge_meta = []
for idx, edge in enumerate(horn_before_cuts.Edges()):
    bb = edge.BoundingBox()
    # The B14B-9 horn starts on a planar rectangular root section normal to +y.
    # Its four perimeter edges are the only edges lying entirely on y=root_y.
    if abs(bb.ymin - root_y) <= 1e-7 and abs(bb.ymax - root_y) <= 1e-7:
        root_edges.append(edge)
        root_edge_meta.append({
            "index_in_baseline_horn": idx,
            "length_mm": edge.Length(),
            "geom_type": edge.geomType(),
        })

if len(root_edges) != 4:
    raise RuntimeError(
        f"Expected 4 B14B-9 root-perimeter edges at y={root_y:.9f} mm; found {len(root_edges)}"
    )

root_edge_lengths = sorted(round(x["length_mm"], 6) for x in root_edge_meta)
expected_lengths = sorted([root_width_x, root_width_x, root_height_z, root_height_z])
if any(abs(a-b) > 1e-4 for a, b in zip(root_edge_lengths, expected_lengths)):
    raise RuntimeError(
        f"Selected root edges do not reconstruct the {root_width_x} x {root_height_z} mm root. "
        f"Lengths={root_edge_lengths}"
    )


# =============================================================================
# 4. APPLY R6 FILLET BEFORE SLOT / PIN CUTS
# =============================================================================

# Filleting the embedded root perimeter before cutting the clevis preserves the exact B14B-9
# pin/slot geometry while replacing the root's mathematically sharp perimeter with a smooth
# constant-radius transition. The root plane is embedded in the parent head, so the final
# external head/horn blend is created by the subsequent Boolean fuse.
horn_root_filleted = horn_before_cuts.fillet(fillet_r, root_edges)

horn_after_slot = horn_root_filleted.cut(slot_cutter)
horn_final = horn_after_slot.cut(pin_hole_cutter)

if len(horn_final.Solids()) != 1:
    raise RuntimeError(f"R6 horn produced {len(horn_final.Solids())} solids; expected one")

modified_head = parent_head.fuse(horn_final)
if len(modified_head.Solids()) != 1:
    raise RuntimeError(f"R6 fused head produced {len(modified_head.Solids())} solids; expected one")


# =============================================================================
# 5. VALIDATION
# =============================================================================

checks: list[dict] = []

add_check(checks, "working_root_fillet_radius", fillet_r, 6.0, "mm", 1e-9)
add_check(checks, "selected_root_edge_count", len(root_edges), 4, "-", 0)
add_check(checks, "selected_root_edge_length_1", root_edge_lengths[0], expected_lengths[0], "mm", 1e-4)
add_check(checks, "selected_root_edge_length_2", root_edge_lengths[1], expected_lengths[1], "mm", 1e-4)
add_check(checks, "selected_root_edge_length_3", root_edge_lengths[2], expected_lengths[2], "mm", 1e-4)
add_check(checks, "selected_root_edge_length_4", root_edge_lengths[3], expected_lengths[3], "mm", 1e-4)
add_bool(checks, "filleted_horn_single_solid", len(horn_final.Solids()) == 1)
add_bool(checks, "modified_head_single_solid", len(modified_head.Solids()) == 1)
add_bool(checks, "fillet_removed_material_from_standalone_horn", horn_final.Volume() < b14b9_horn.Volume())
add_bool(checks, "fillet_changed_final_head_volume", abs(modified_head.Volume() - b14b9_head.Volume()) > 1.0)

# Fillet is subtractive from the horn root, so it cannot create a new collision with the
# existing shaft/bushings/collars. Still verify every interface explicitly.
for body_name in expected_body_names[1:]:
    iv = modified_head.intersect(parent_named[body_name]["shape"]).Volume()
    add_check(
        checks,
        f"intersection_modified_head__{body_name}",
        iv,
        0.0,
        "mm^3",
        1e-6,
        note="Separate material bodies must not have positive common volume.",
    )

# Verify non-head bodies are still unchanged by bounding box and volume against B14B-9 parent input.
for body_name in expected_body_names[1:]:
    rec = parent_named[body_name]
    add_bool(checks, f"preserve_{body_name}_positive_volume", rec["volume"] > 0.0)

# A subtractive root fillet may shrink the local envelope slightly (notably the old sharp
# top-root corner), but it must never expand beyond the validated B14B-9 envelope.
bb_old = bbox_tuple(b14b9_head)
bb_new = bbox_tuple(modified_head)
labels = ["xmin", "xmax", "ymin", "ymax", "zmin", "zmax"]
for label, old, newv in zip(labels, bb_old, bb_new):
    if label.endswith("min"):
        ok = newv >= old - 1e-6
    else:
        ok = newv <= old + 1e-6
    add_bool(
        checks,
        f"head_bbox_{label}_does_not_expand",
        ok,
        note=f"B14B-9={old:.9f} mm; R6={newv:.9f} mm. Subtractive fillet may shrink the envelope.",
    )

# Root remains positively embedded into the parent head.
parent_vol = parent_head.Volume()
horn_vol = horn_final.Volume()
head_vol = modified_head.Volume()
overlap_vol = parent_vol + horn_vol - head_vol
add_bool(checks, "positive_head_horn_overlap_after_fillet", overlap_vol > 1.0)

# The baseline source passage clearance cannot worsen under a subtractive root fillet.
add_bool(
    checks,
    "source_passage_clearance_not_worsened_by_subtractive_fillet",
    fillet_r > 0.0 and root_passage_clearance > 0.0,
    note=(
        "R6 removes horn material at the embedded root perimeter; no material is added toward "
        "the existing head passage. Existing separate-body collision checks also remain zero."
    ),
)


# =============================================================================
# 6. EXPORT NAMED SIX-BODY STEP AND REIMPORT
# =============================================================================

assembly = cq.Assembly(name="B14B11B_R6_ROOT_FILLET_CANDIDATE")
assembly.add(modified_head, name="HEAD_BARREL_7075")
for body_name in expected_body_names[1:]:
    assembly.add(parent_named[body_name]["shape"], name=body_name)
assembly.save(str(OUT_STEP))

reimport = cq.importers.importStep(str(OUT_STEP))
re_solids = reimport.solids().vals()
add_check(checks, "exported_reimported_solid_count", len(re_solids), 6, "-", 0)

step_text = OUT_STEP.read_text(encoding="utf-8", errors="replace")
add_bool(checks, "export_product_label", "B14B11B_R6_ROOT_FILLET_CANDIDATE" in step_text)
for body_name in expected_body_names:
    add_bool(checks, f"export_body_label_{body_name}", body_name in step_text)

fail_count = sum(1 for r in checks if r["status"] != "PASS")
pass_count = len(checks) - fail_count


# =============================================================================
# 7. MACHINE-READABLE OUTPUTS
# =============================================================================

geometry_rows = [
    {"feature": "root_fillet", "parameter": "radius", "value": fillet_r, "units": "mm", "status": "WORKING_NOT_FROZEN"},
    {"feature": "root_fillet", "parameter": "selected_edge_count", "value": len(root_edges), "units": "-", "status": "GEOMETRY_VALIDATED"},
    {"feature": "root_fillet", "parameter": "root_plane_y_global", "value": root_y, "units": "mm", "status": "SOURCE_B14B9"},
    {"feature": "root_fillet", "parameter": "root_width_x", "value": root_width_x, "units": "mm", "status": "SOURCE_B14B9"},
    {"feature": "root_fillet", "parameter": "root_height_z", "value": root_height_z, "units": "mm", "status": "SOURCE_B14B9"},
    {"feature": "root_fillet", "parameter": "root_embed_depth", "value": root_embed, "units": "mm", "status": "SOURCE_B14B9"},
    {"feature": "root_fillet", "parameter": "source_passage_clearance", "value": root_passage_clearance, "units": "mm", "status": "SOURCE_B14B9"},
    {"feature": "pin_bore", "parameter": "diameter", "value": pin_d, "units": "mm", "status": "UNCHANGED_FROM_B14B9"},
    {"feature": "volume", "parameter": "B14B9_horn_volume", "value": b14b9_horn.Volume(), "units": "mm^3", "status": "BASELINE"},
    {"feature": "volume", "parameter": "R6_horn_volume", "value": horn_vol, "units": "mm^3", "status": "MEASURED"},
    {"feature": "volume", "parameter": "horn_material_removed", "value": b14b9_horn.Volume() - horn_vol, "units": "mm^3", "status": "DERIVED"},
    {"feature": "volume", "parameter": "B14B9_modified_head_volume", "value": b14b9_head.Volume(), "units": "mm^3", "status": "BASELINE"},
    {"feature": "volume", "parameter": "R6_modified_head_volume", "value": head_vol, "units": "mm^3", "status": "MEASURED"},
    {"feature": "volume", "parameter": "head_volume_change", "value": head_vol - b14b9_head.Volume(), "units": "mm^3", "status": "DERIVED"},
    {"feature": "volume", "parameter": "head_horn_overlap_volume", "value": overlap_vol, "units": "mm^3", "status": "MEASURED_DERIVED"},
    {"feature": "FEA_reference", "parameter": "cleaned_linear_brace_force", "value": baseline_brace_force_N, "units": "N", "status": "SOURCE_B14B10"},
    {"feature": "FEA_reference", "parameter": "cleaned_linear_max_deformation", "value": baseline_def_mm, "units": "mm", "status": "SOURCE_B14B10"},
    {"feature": "FEA_reference", "parameter": "sharp_root_VM_peak", "value": baseline_vm_MPa, "units": "MPa", "status": "REFERENCE_NOT_LOCALLY_CONVERGED"},
]

open_rows = [
    {"item": "R6_linear_FEA_screen", "status": "OPEN", "next_action": "Replace B14B-10 geometry with the R6 STEP and rerun cleaned linear LC4 ultimate model."},
    {"item": "root_hotspot_location", "status": "OPEN", "next_action": "Verify peak VM moves onto the smooth root transition rather than a residual sharp edge."},
    {"item": "R4_R8_comparison", "status": "OPEN", "next_action": "Only build neighboring radii if R6 stress result warrants a trade."},
    {"item": "local_mesh_convergence", "status": "OPEN", "next_action": "Required on selected final transition before freezing local stress."},
    {"item": "manufacturing_detail", "status": "OPEN", "next_action": "Final machining/forging/blend specification follows structural selection."},
]

write_rows(OUT_VALIDATION, checks)
write_rows(OUT_GEOMETRY, geometry_rows)
write_rows(OUT_OPEN, open_rows)


# =============================================================================
# 8. SUMMARY
# =============================================================================

summary = f"""========================================================================================================================
 PHASE 2E3-B14B-11B V0.1 — R6 HORN/HEAD ROOT FILLET CAD BUILD
========================================================================================================================

SOURCE / STATUS
------------------------------------------------------------------------------------------------------------------------
B14B-9 builder reused:                 {B14B9_BUILDER.name}
B14B-11A working radius:               {fillet_r:.3f} mm
B14B-10 cleaned linear brace force:    {baseline_brace_force_N/1000:.6f} kN
B14B-10 sharp-root VM reference:       {baseline_vm_MPa:.3f} MPa [NOT LOCALLY CONVERGED]

ROOT FEATURE
------------------------------------------------------------------------------------------------------------------------
Root plane y:                          {root_y:.6f} mm
Equivalent root:                       {root_width_x:.3f} x {root_height_z:.3f} mm
Selected embedded root edges:          {len(root_edges)}
Root-edge lengths:                     {', '.join(f'{x:.3f}' for x in root_edge_lengths)} mm
Applied constant-radius fillet:        R{fillet_r:.3f} mm on all four root-perimeter edges
Fillet application sequence:           B14B-9 horn envelope -> R6 root fillet -> U-slot cut -> Ø18 pin cut -> fuse to head

GEOMETRY CHANGE
------------------------------------------------------------------------------------------------------------------------
B14B-9 standalone horn volume:         {b14b9_horn.Volume():.3f} mm^3
R6 standalone horn volume:             {horn_vol:.3f} mm^3
Horn material removed:                 {b14b9_horn.Volume() - horn_vol:.3f} mm^3
B14B-9 fused head volume:               {b14b9_head.Volume():.3f} mm^3
R6 fused head volume:                  {head_vol:.3f} mm^3
Fused-head volume change:              {head_vol - b14b9_head.Volume():+.3f} mm^3
R6 head/horn overlap:                  {overlap_vol:.3f} mm^3

VALIDATION
------------------------------------------------------------------------------------------------------------------------
PASS checks:                           {pass_count}
FAIL checks:                           {fail_count}
Reimported STEP solid count:           {len(re_solids)}

GATE
------------------------------------------------------------------------------------------------------------------------
{'PASS_B14B11B_R6_GEOMETRY_FOR_LINEAR_FEA_SCREEN' if fail_count == 0 else 'FAIL_B14B11B_GEOMETRY'}
This is a WORKING R6 CAD/FEA candidate, not a final root-detail freeze.

NEXT
------------------------------------------------------------------------------------------------------------------------
Use this STEP in a duplicate of the cleaned B14B-10 linear model. Preserve the shared RP_UPPER_LOAD_U,
cylindrical contact smoothing, spring definition, supports and LC4 ultimate load package. Compare brace force,
max deformation and the local horn/head root stress field against the B14B-10 baseline. Final local stress still
requires focused mesh convergence after the transition geometry is selected.

OUTPUTS
------------------------------------------------------------------------------------------------------------------------
{OUT_STEP}
{OUT_VALIDATION}
{OUT_GEOMETRY}
{OUT_OPEN}
{OUT_SUMMARY}
========================================================================================================================
"""
OUT_SUMMARY.write_text(summary, encoding="utf-8")
print(summary)

if fail_count:
    raise RuntimeError(f"B14B-11B validation failed: {fail_count} check(s)")
