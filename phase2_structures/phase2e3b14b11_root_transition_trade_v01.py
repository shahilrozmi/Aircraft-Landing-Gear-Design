from pathlib import Path
import csv

HERE = Path(__file__).resolve().parent

def find_one(name):
    direct = HERE / name
    if direct.exists():
        return direct
    hits = sorted(HERE.rglob(name))
    if len(hits) != 1:
        raise FileNotFoundError(f"Expected one {name}, found {len(hits)}")
    return hits[0]

def read_one_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 1:
        raise ValueError(f"{path.name}: expected one row")
    return rows[0]

def read_kv(path):
    with path.open(newline="", encoding="utf-8-sig") as f:
        return {r["field"]: r["value"] for r in csv.DictReader(f)}

b7 = read_one_csv(find_one("phase2e3b14b7_reference_candidate.csv"))
b8 = read_one_csv(find_one("phase2e3b14b8_reference_geometry.csv"))
b10 = read_kv(find_one("phase2e3b14b10_closeout_record_v01.csv"))

root_w = float(b7["bx_mm"])
root_h = float(b7["hz_mm"])
half_added = float(b7["symmetric_extension_each_side_mm"])
passage_clearance = float(b7["passage_clearance_from_root_plane_mm"])
root_to_pin = float(b7["root_to_pin_lever_mm"])
taper_len = float(b8["taper_length_from_saddle_root_mm"])

baseline_brace_force = float(b10["linear_brace_force_N"])
baseline_def = float(b10["linear_max_deformation_mm"])
baseline_vm = float(b10["linear_max_vm_MPa"])

candidate_radii = [2.0, 4.0, 6.0, 8.0]
rows = []
for r in candidate_radii:
    reserve = half_added - r
    rows.append({
        "fillet_radius_mm": r,
        "root_width_mm": root_w,
        "root_height_mm": root_h,
        "available_symmetric_extension_each_side_mm": half_added,
        "nominal_radius_budget_reserve_mm": reserve,
        "source_passage_clearance_mm": passage_clearance,
        "root_to_pin_lever_mm": root_to_pin,
        "taper_length_mm": taper_len,
        "basic_packaging_screen": "PASS" if reserve >= 0 else "FAIL",
        "first_build_eligible": "YES" if reserve >= 2.0 else "NO",
        "status": "WORKING_CAD_FEA_CANDIDATE_NOT_FROZEN",
    })

with (HERE / "phase2e3b14b11_root_transition_trade_v01.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

first = max((r for r in rows if r["first_build_eligible"] == "YES"),
            key=lambda x: x["fillet_radius_mm"])
print(f"First B14B-11 CAD/FEA candidate: R{first['fillet_radius_mm']:.0f} mm")
print(f"Nominal budget reserve: {first['nominal_radius_budget_reserve_mm']:.3f} mm")
print(f"B14B-10 linear brace force reference: {baseline_brace_force/1000:.6f} kN")
print(f"B14B-10 sharp-root VM reference: {baseline_vm:.6f} MPa (not locally converged)")
