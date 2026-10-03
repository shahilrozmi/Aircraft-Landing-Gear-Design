from pathlib import Path
import csv

baseline = {
    "brace_force_N": -67231.0,
    "brace_elongation_mm": -0.56743,
    "max_deformation_mm": 5.1220,
    "max_vm_MPa": 415.55,
}
r6 = {
    "brace_force_N": -67348.0,
    "brace_elongation_mm": -0.56842,
    "max_deformation_mm": 5.1384,
    "max_vm_MPa": 433.41,
}

rows = []
for k in baseline:
    b = baseline[k]
    c = r6[k]
    rows.append({
        "metric": k,
        "baseline": b,
        "r6": c,
        "difference": c-b,
        "percent_change_magnitude": 100*(abs(c)-abs(b))/abs(b),
    })

with Path("phase2e3b14b11_r6_first_screen_compare_v01.csv").open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
