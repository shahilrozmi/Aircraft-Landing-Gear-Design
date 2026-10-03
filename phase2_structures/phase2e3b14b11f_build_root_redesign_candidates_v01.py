"""
Landing_Gear_Design_Project
PHASE 2E3-B14B-11F V0.1 — R8 ROOT REDESIGN CAD CANDIDATES

Build two source-connected redesign candidates from the validated B14B-9 horn/head:
  F2_BALANCED : root 95 x 115 mm, R12 mm
  F3_ROBUST   : root 100 x 115 mm, R15 mm

For each candidate export:
  1) Full six-body STEP for eventual parent-model confirmation.
  2) One-body local STEP using the exact B14B11E crop for displacement-driven screening.

Status: WORKING CAD/FEA CANDIDATES — NOT FROZEN.
"""
from __future__ import annotations
import csv, math, runpy, zipfile
from pathlib import Path
import cadquery as cq

HERE = Path(__file__).resolve().parent
BASE = HERE / "phase2e3b14b9_build_physical_horn_clevis_v01.py"
OUT_GEOM = HERE / "phase2e3b14b11f_candidate_geometry_v01.csv"
OUT_VAL = HERE / "phase2e3b14b11f_candidate_validation_v01.csv"
OUT_SUM = HERE / "phase2e3b14b11f_candidate_summary_v01.txt"
OUT_ZIP = HERE / "phase2e3b14b11f_R8_ROOT_REDESIGN_CANDIDATES_v01.zip"

CANDIDATES = [
    dict(name="F2_BALANCED", root_width=95.0, root_height=115.0, fillet_r=12.0),
    dict(name="F3_ROBUST", root_width=100.0, root_height=115.0, fillet_r=15.0),
]

# Same crop as the validated B14B11E single-body submodel.
XMIN, XMAX = -60.0, 60.0
YMIN, YMAX = 25.0, 120.0
ZMIN, ZMAX = 920.0, 992.0
TOL = 1e-4
RHO_7075_KG_PER_MM3 = 2810.0e-9


def write_rows(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)


def cut_faces(shape, axis, value):
    faces=[]
    for f in shape.Faces():
        bb=f.BoundingBox()
        if axis=="y" and abs(bb.ymin-value)<TOL and abs(bb.ymax-value)<TOL: faces.append(f)
        if axis=="z" and abs(bb.zmin-value)<TOL and abs(bb.zmax-value)<TOL: faces.append(f)
    return faces


def add_check(rows, cand, check, actual, expected, tol=0.0, note=""):
    if isinstance(actual,(int,float)) and isinstance(expected,(int,float)):
        ok=abs(float(actual)-float(expected))<=tol
    else:
        ok=actual==expected
    rows.append(dict(candidate=cand,check=check,actual=actual,expected=expected,tolerance=tol,status="PASS" if ok else "FAIL",note=note))
    return ok

# Exact source-connected baseline.
g = runpy.run_path(str(BASE))
root_plane = g["root_plane"]
throat_wire = g["throat_wire"]
fork_outer = g["fork_outer"]
slot_cutter = g["slot_cutter"]
pin_hole_cutter = g["pin_hole_cutter"]
parent_head = g["parent_head"]
parent_named = g["parent_named"]
root_y = float(g["root_center_global"][1])

# Rebuild exact current R8 head for delta-volume/mass reference.
base_horn_before = g["horn_before_cuts"]
base_root_edges=[]
for e in base_horn_before.Edges():
    bb=e.BoundingBox()
    if abs(bb.ymin-root_y)<=1e-7 and abs(bb.ymax-root_y)<=1e-7:
        base_root_edges.append(e)
if len(base_root_edges)!=4:
    raise RuntimeError(f"Expected 4 baseline root edges, got {len(base_root_edges)}")
base_r8_horn = base_horn_before.fillet(8.0, base_root_edges).cut(slot_cutter).cut(pin_hole_cutter)
base_r8_head = parent_head.fuse(base_r8_horn)
V_R8 = base_r8_head.Volume()

box=(cq.Workplane("XY").box(XMAX-XMIN,YMAX-YMIN,ZMAX-ZMIN,centered=(False,False,False)).translate((XMIN,YMIN,ZMIN)).val())

geom=[]; checks=[]; generated=[]

for c in CANDIDATES:
    name=c["name"]; b=c["root_width"]; h=c["root_height"]; r=c["fillet_r"]
    root_wire=cq.Workplane(root_plane).rect(b,h).val()
    taper=cq.Solid.makeLoft([root_wire,throat_wire],ruled=True)
    horn_before=taper.fuse(fork_outer)

    root_edges=[]
    for e in horn_before.Edges():
        bb=e.BoundingBox()
        if abs(bb.ymin-root_y)<=1e-7 and abs(bb.ymax-root_y)<=1e-7:
            root_edges.append(e)
    add_check(checks,name,"root_edge_count",len(root_edges),4)

    horn=horn_before.fillet(r,root_edges).cut(slot_cutter).cut(pin_hole_cutter)
    head=parent_head.fuse(horn)
    add_check(checks,name,"modified_head_single_solid",len(head.Solids()),1)

    # Hardware interference screen.
    for body_name,rec in parent_named.items():
        if body_name=="HEAD_BARREL_7075":
            continue
        iv=head.intersect(rec["shape"]).Volume()
        add_check(checks,name,f"no_intersection__{body_name}",iv,0.0,1e-6)

    local=head.intersect(box)
    add_check(checks,name,"local_single_solid",len(local.Solids()),1)
    yf0=cut_faces(local,"y",YMIN); yf1=cut_faces(local,"y",YMAX)
    zf0=cut_faces(local,"z",ZMIN); zf1=cut_faces(local,"z",ZMAX)
    add_check(checks,name,"cut_y25_face_count",len(yf0),1)
    add_check(checks,name,"cut_y120_face_count",len(yf1),1)
    add_check(checks,name,"cut_z920_face_count",len(zf0),1)
    add_check(checks,name,"cut_z992_face_count",len(zf1),1)

    # Export full six-body assembly.
    full_step=HERE/f"phase2e3b14b11f_{name.lower()}_full_sixbody_v01.step"
    a=cq.Assembly(name=f"B14B11F_{name}_FULL")
    a.add(head,name="HEAD_BARREL_7075")
    for body_name,rec in parent_named.items():
        if body_name=="HEAD_BARREL_7075": continue
        a.add(rec["shape"],name=body_name)
    a.save(str(full_step))
    re_full=cq.importers.importStep(str(full_step))
    add_check(checks,name,"full_step_reimport_solid_count",len(re_full.solids().vals()),6)

    local_step=HERE/f"phase2e3b14b11f_{name.lower()}_local_submodel_v01.step"
    al=cq.Assembly(name=f"B14B11F_{name}_LOCAL")
    al.add(local,name="HEAD_7075_ROOT_LOCAL")
    al.save(str(local_step))
    re_local=cq.importers.importStep(str(local_step))
    add_check(checks,name,"local_step_reimport_solid_count",len(re_local.solids().vals()),1)

    dv=head.Volume()-V_R8
    geom.append(dict(
        candidate=name, root_width_mm=b, root_height_mm=h, fillet_radius_mm=r,
        root_plane_y_mm=root_y, full_head_volume_mm3=head.Volume(),
        delta_volume_vs_R8_mm3=dv, delta_mass_vs_R8_kg=dv*RHO_7075_KG_PER_MM3,
        local_volume_mm3=local.Volume(),
        cut_y25_area_mm2=sum(f.Area() for f in yf0),
        cut_y120_area_mm2=sum(f.Area() for f in yf1),
        cut_z920_area_mm2=sum(f.Area() for f in zf0),
        cut_z992_area_mm2=sum(f.Area() for f in zf1),
        status="WORKING_CAD_FEA_CANDIDATE_NOT_FROZEN"
    ))
    generated += [full_step,local_step]

write_rows(OUT_GEOM,geom)
write_rows(OUT_VAL,checks)

fails=[r for r in checks if r["status"]!="PASS"]
summary=[]
summary.append("PHASE 2E3-B14B-11F — R8 ROOT REDESIGN CAD CANDIDATES V0.1")
summary.append("")
summary.append(f"Baseline retained R8 full-head volume: {V_R8:.3f} mm^3")
summary.append("Local crop: x[-60,60], y[25,120], z[920,992] mm — identical to B14B11E.")
summary.append("")
for row in geom:
    summary.append(f"{row['candidate']}")
    summary.append(f"  root section: {row['root_width_mm']:.1f} x {row['root_height_mm']:.1f} mm")
    summary.append(f"  fillet radius: R{row['fillet_radius_mm']:.1f} mm")
    summary.append(f"  full-head volume: {row['full_head_volume_mm3']:.3f} mm^3")
    summary.append(f"  added mass vs R8: {row['delta_mass_vs_R8_kg']:.3f} kg")
    summary.append(f"  local volume: {row['local_volume_mm3']:.3f} mm^3")
    summary.append(f"  artificial cut areas y25/y120/z920/z992: {row['cut_y25_area_mm2']:.3f}, {row['cut_y120_area_mm2']:.3f}, {row['cut_z920_area_mm2']:.3f}, {row['cut_z992_area_mm2']:.3f} mm^2")
    summary.append("")
summary.append(f"Validation PASS: {sum(r['status']=='PASS' for r in checks)}")
summary.append(f"Validation FAIL: {len(fails)}")
summary.append("Gate: " + ("PASS_B14B11F_CANDIDATES_READY_FOR_LOCAL_FEA_SCREEN" if not fails else "FAIL_B14B11F_CANDIDATE_GEOMETRY"))
summary.append("")
summary.append("FEA SCREEN PLAN")
summary.append("  Use the existing solved R8 parent displacement field for screening only.")
summary.append("  Replace local geometry with each candidate local STEP; map the same four cut faces.")
summary.append("  Use quadratic elements and 1.0 mm local root/fillet sizing for both candidates.")
summary.append("  Pick the lower-stress practical candidate; run only that winner at 0.75 mm.")
summary.append("  Then replace the full six-body parent geometry with the winning full STEP and perform one confirmation solve.")
summary.append("")
summary.append("STATUS: WORKING CANDIDATES — NOT FROZEN.")
OUT_SUM.write_text("\n".join(summary),encoding="utf-8")

# Package only B14B11F outputs + candidate STEPs.
package=[Path(__file__),OUT_GEOM,OUT_VAL,OUT_SUM]+generated
with zipfile.ZipFile(OUT_ZIP,"w",zipfile.ZIP_DEFLATED) as z:
    for p in package:
        z.write(p,arcname=p.name)

print("\n".join(summary))
print(f"\nPackage: {OUT_ZIP}")
if fails:
    raise SystemExit("Candidate validation failed: "+", ".join(f"{r['candidate']}::{r['check']}" for r in fails))
