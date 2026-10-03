from pathlib import Path
import csv

sharp_baseline = {
    "brace_force_N": -67231.0,
    "max_deformation_mm": 5.1220,
    "max_vm_MPa": 415.55,
}
r6_coarse = {
    "brace_force_N": -67348.0,
    "max_deformation_mm": 5.1384,
    "max_vm_MPa": 433.41,
}
r6_root3 = {
    "brace_force_N": -67348.0,
    "max_deformation_mm": 5.1354,
    "max_vm_MPa": 411.23,
}

def pct(new, old):
    return 100.0*(new-old)/old

rows = []
for metric in sharp_baseline:
    rows.append({
        "metric": metric,
        "sharp_baseline": sharp_baseline[metric],
        "r6_coarse": r6_coarse[metric],
        "r6_root3mm": r6_root3[metric],
        "r6_coarse_vs_sharp_pct": pct(r6_coarse[metric], sharp_baseline[metric]),
        "r6_root3_vs_sharp_pct": pct(r6_root3[metric], sharp_baseline[metric]),
        "r6_root3_vs_r6_coarse_pct": pct(r6_root3[metric], r6_coarse[metric]),
    })

with Path("phase2e3b14b11_r6_root3mm_compare_v01.csv").open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

for r in rows:
    print(r)
