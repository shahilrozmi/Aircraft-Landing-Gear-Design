"""
Landing_Gear_Design_Project
PHASE 2E3-B14B-11C V0.1 — R4 / R8 ROOT-FILLET CAD TRADE VARIANTS

Purpose
-------
Build source-connected R4 and R8 horn/head root-fillet variants from the exact
validated B14B-9 physical horn/clevis baseline. Preserve all non-root geometry.

Outputs
-------
- phase2e3b14b11c_r4_root_fillet_candidate_v01.step
- phase2e3b14b11c_r8_root_fillet_candidate_v01.step
- per-variant validation / geometry / summary files
- phase2e3b14b11c_radius_trade_manifest_v01.csv
- phase2e3b14b11c_summary_v01.txt

Status
------
WORKING CAD/FEA TRADE VARIANTS — NOT DETAIL-DESIGN FREEZE.
"""
from __future__ import annotations

import csv
import runpy
from pathlib import Path
import traceback
import cadquery as cq

HERE = Path(__file__).resolve().parent
BASE_BUILDER = HERE / "phase2e3b14b9_build_physical_horn_clevis_v01.py"
TRADE = HERE / "phase2e3b14b11_root_transition_trade_v01.csv"
B10 = HERE / "phase2e3b14b10_closeout_record_v01.csv"

REQUESTED_RADII = [4.0, 8.0]


def read_rows(path):
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def read_kv(path):
    with path.open(newline="", encoding="utf-8-sig") as f:
        return {r["field"]: r["value"] for r in csv.DictReader(f)}


def write_rows(path, rows):
    if not rows:
        rows = [{"status": "NONE"}]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), extrasaction="ignore")
        w.writeheader(); w.writerows(rows)


def add_check(checks, name, actual, expected, units="-", tol=1e-6, note=""):
    if isinstance(actual, (int,float)) and isinstance(expected,(int,float)):
        ok = abs(float(actual)-float(expected)) <= tol
    else:
        ok = actual == expected
    checks.append({
        "check": name, "actual": actual, "expected": expected,
        "units": units, "tolerance": tol,
        "status": "PASS" if ok else "FAIL", "note": note,
    })
    return ok


def add_bool(checks, name, cond, note=""):
    return add_check(checks, name, bool(cond), True, "-", 0, note)


def bbox_tuple(shape):
    b = shape.BoundingBox()
    return (b.xmin,b.xmax,b.ymin,b.ymax,b.zmin,b.zmax)


trade_rows = read_rows(TRADE)
trade_by_r = {float(r["fillet_radius_mm"]): r for r in trade_rows}
b10 = read_kv(B10)

# Rebuild B14B-9 exactly once and reuse its in-memory geometry for both radii.
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
root_embed = float(g["root_embed"])
root_passage_clearance = float(g["root_passage_clearance"])
pin_d = float(g["pin_d"])
baseline_head = g["modified_head"]
baseline_horn = g["horn_final"]

root_y = float(root_center_global[1])
root_edges = []
for edge in horn_before_cuts.Edges():
    bb = edge.BoundingBox()
    if abs(bb.ymin-root_y) <= 1e-7 and abs(bb.ymax-root_y) <= 1e-7:
        root_edges.append(edge)
if len(root_edges) != 4:
    raise RuntimeError(f"Expected 4 root edges, found {len(root_edges)}")

root_edge_lengths = sorted(e.Length() for e in root_edges)
expected_lengths = sorted([root_width_x,root_width_x,root_height_z,root_height_z])

manifest = []
combined_summary = []

for radius in REQUESTED_RADII:
    tag = f"r{int(radius)}"
    row = trade_by_r[radius]
    out_step = HERE / f"phase2e3b14b11c_{tag}_root_fillet_candidate_v01.step"
    out_validation = HERE / f"phase2e3b14b11c_{tag}_geometry_validation_v01.csv"
    out_geometry = HERE / f"phase2e3b14b11c_{tag}_geometry_definition_v01.csv"
    out_summary = HERE / f"phase2e3b14b11c_{tag}_summary_v01.txt"
    checks = []
    geom = []
    status = "FAIL_BUILD"
    error_text = ""
    try:
        add_check(checks,"source_trade_packaging_screen",row["basic_packaging_screen"],"PASS")
        add_check(checks,"selected_root_edge_count",len(root_edges),4)
        for i,(a,b) in enumerate(zip(root_edge_lengths,expected_lengths),1):
            add_check(checks,f"root_edge_length_{i}",a,b,"mm",1e-4)

        horn_filleted = horn_before_cuts.fillet(radius, root_edges)
        horn_after_slot = horn_filleted.cut(slot_cutter)
        horn_final = horn_after_slot.cut(pin_hole_cutter)
        modified_head = parent_head.fuse(horn_final)

        add_bool(checks,"horn_single_solid",len(horn_final.Solids())==1)
        add_bool(checks,"head_single_solid",len(modified_head.Solids())==1)
        add_bool(checks,"fillet_subtractive_vs_B14B9",horn_final.Volume() < baseline_horn.Volume())

        for body_name in expected_body_names[1:]:
            iv = modified_head.intersect(parent_named[body_name]["shape"]).Volume()
            add_check(checks,f"intersection_head__{body_name}",iv,0.0,"mm^3",1e-6)

        bb0 = bbox_tuple(baseline_head); bb1 = bbox_tuple(modified_head)
        labels = ["xmin","xmax","ymin","ymax","zmin","zmax"]
        for label, old, new in zip(labels,bb0,bb1):
            ok = new >= old-1e-6 if label.endswith("min") else new <= old+1e-6
            add_bool(checks,f"head_bbox_{label}_does_not_expand",ok,
                     f"B14B9={old:.9f}; R{radius:g}={new:.9f}")

        overlap = parent_head.Volume() + horn_final.Volume() - modified_head.Volume()
        add_bool(checks,"positive_head_horn_overlap",overlap > 1.0)
        add_bool(checks,"source_passage_clearance_positive",root_passage_clearance > 0.0)

        assembly = cq.Assembly(name=f"B14B11C_R{int(radius)}_ROOT_FILLET_CANDIDATE")
        assembly.add(modified_head,name="HEAD_BARREL_7075")
        for body_name in expected_body_names[1:]:
            assembly.add(parent_named[body_name]["shape"],name=body_name)
        assembly.save(str(out_step))

        reimport = cq.importers.importStep(str(out_step))
        re_solids = reimport.solids().vals()
        add_check(checks,"exported_reimported_solid_count",len(re_solids),6)
        step_text = out_step.read_text(encoding="utf-8",errors="replace")
        for body_name in expected_body_names:
            add_bool(checks,f"export_body_label_{body_name}",body_name in step_text)

        fail_count = sum(c["status"]!="PASS" for c in checks)
        status = "PASS" if fail_count==0 else "FAIL_VALIDATION"

        geom = [
            {"parameter":"fillet_radius_mm","value":radius,"units":"mm"},
            {"parameter":"root_width_x_mm","value":root_width_x,"units":"mm"},
            {"parameter":"root_height_z_mm","value":root_height_z,"units":"mm"},
            {"parameter":"root_embed_depth_mm","value":root_embed,"units":"mm"},
            {"parameter":"source_passage_clearance_mm","value":root_passage_clearance,"units":"mm"},
            {"parameter":"nominal_radius_budget_reserve_mm","value":float(row["nominal_radius_budget_reserve_mm"]),"units":"mm"},
            {"parameter":"pin_diameter_mm","value":pin_d,"units":"mm"},
            {"parameter":"B14B9_horn_volume_mm3","value":baseline_horn.Volume(),"units":"mm^3"},
            {"parameter":f"R{int(radius)}_horn_volume_mm3","value":horn_final.Volume(),"units":"mm^3"},
            {"parameter":"horn_material_removed_mm3","value":baseline_horn.Volume()-horn_final.Volume(),"units":"mm^3"},
            {"parameter":"fused_head_volume_mm3","value":modified_head.Volume(),"units":"mm^3"},
            {"parameter":"head_horn_overlap_mm3","value":overlap,"units":"mm^3"},
        ]
        write_rows(out_geometry,geom)
        write_rows(out_validation,checks)

        summary = f"""PHASE 2E3-B14B-11C — R{int(radius)} ROOT-FILLET CAD VARIANT V0.1

Radius:                          R{radius:.3f} mm
Nominal radius-budget reserve:  {float(row['nominal_radius_budget_reserve_mm']):.3f} mm
Source passage clearance:       {root_passage_clearance:.6f} mm
Standalone horn volume:         {horn_final.Volume():.3f} mm^3
Horn material removed vs B14B9: {baseline_horn.Volume()-horn_final.Volume():.3f} mm^3
Fused head volume:              {modified_head.Volume():.3f} mm^3
Head/horn overlap:              {overlap:.3f} mm^3
Reimported STEP solids:         {len(re_solids)}
Validation:                     {status}

Disposition:
WORKING CAD/FEA TRADE VARIANT — NOT DETAIL-DESIGN FREEZE.
Use the same cleaned B14B-11 ANSYS load path and 2.0 mm root-local mesh method used for R6.
"""
        out_summary.write_text(summary,encoding="utf-8")
        combined_summary.append(summary)

        manifest.append({
            "radius_mm":radius,
            "nominal_radius_budget_reserve_mm":float(row["nominal_radius_budget_reserve_mm"]),
            "build_status":status,
            "validation_fail_count":fail_count,
            "step_file":out_step.name,
            "summary_file":out_summary.name,
            "horn_volume_mm3":horn_final.Volume(),
            "horn_material_removed_mm3":baseline_horn.Volume()-horn_final.Volume(),
            "fused_head_volume_mm3":modified_head.Volume(),
            "head_horn_overlap_mm3":overlap,
            "reimported_solid_count":len(re_solids),
            "error":"",
        })
    except Exception as exc:
        error_text = f"{type(exc).__name__}: {exc}"
        checks.append({"check":"build_exception","actual":error_text,"expected":"none","units":"-","tolerance":"-","status":"FAIL","note":traceback.format_exc()})
        write_rows(out_validation,checks)
        out_summary.write_text(
            f"PHASE 2E3-B14B-11C — R{int(radius)} ROOT-FILLET CAD VARIANT V0.1\n\nBUILD FAILED\n{error_text}\n",
            encoding="utf-8")
        manifest.append({
            "radius_mm":radius,
            "nominal_radius_budget_reserve_mm":float(row["nominal_radius_budget_reserve_mm"]),
            "build_status":"FAIL_BUILD",
            "validation_fail_count":1,
            "step_file":"",
            "summary_file":out_summary.name,
            "horn_volume_mm3":"",
            "horn_material_removed_mm3":"",
            "fused_head_volume_mm3":"",
            "head_horn_overlap_mm3":"",
            "reimported_solid_count":"",
            "error":error_text,
        })

manifest_path = HERE / "phase2e3b14b11c_radius_trade_manifest_v01.csv"
write_rows(manifest_path,manifest)

summary_path = HERE / "phase2e3b14b11c_summary_v01.txt"
summary_path.write_text(
    "PHASE 2E3-B14B-11C — R4/R8 CAD TRADE BUILD V0.1\n\n" +
    "\n".join(
        f"R{m['radius_mm']:.0f}: {m['build_status']} | reserve={m['nominal_radius_budget_reserve_mm']:.3f} mm | STEP={m['step_file'] or 'NONE'}"
        for m in manifest
    ) +
    "\n\nR6 remains the converged FEA reference. R4 and R8 are working variants for same-method ANSYS comparison.\n",
    encoding="utf-8"
)

print(summary_path.read_text(encoding="utf-8"))
if any(m["build_status"] != "PASS" for m in manifest):
    raise RuntimeError("One or more radius variants failed. See manifest/validation outputs.")
