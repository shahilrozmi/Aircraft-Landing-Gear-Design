from pathlib import Path
import csv

before = {"CT_BUSH_HEAD_L": 1.2895, "CT_BUSH_HEAD_R": 1.6130}
after = {"CT_BUSH_HEAD_L": 1.0414e-4, "CT_BUSH_HEAD_R": 2.0258e-4}

rows = []
for name in before:
    b = before[name]
    a = after[name]
    rows.append({
        "contact": name,
        "geometric_penetration_before_mm": b,
        "geometric_penetration_after_mm": a,
        "reduction_factor": b / a,
        "reduction_percent": (1 - a / b) * 100,
    })

with Path("phase2e3b14b10_contact_smoothing_diagnostic_v01.csv").open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
