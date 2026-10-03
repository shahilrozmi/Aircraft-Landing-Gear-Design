from pathlib import Path
import csv, math

linear = {
    "brace_force_N": -67231.0,
    "brace_elongation_mm": -0.56743,
    "left_Rx_N": 18466.0,
    "left_Ry_N": 35836.0,
    "left_Rz_N": 1811.7,
    "left_total_N": 40355.0,
    "right_Rx_N": 2.5487e-12,
    "right_Ry_N": -47256.0,
    "right_Rz_N": 2047.2,
    "right_total_N": 47301.0,
    "max_deformation_mm": 5.122,
    "max_vm_MPa": 415.55,
}
large_def = {
    "brace_force_N": -67212.0,
    "brace_elongation_mm": -0.56727,
    "left_Rx_N": 18752.0,
    "left_Ry_N": 36907.0,
    "left_Rz_N": 2587.7,
    "left_total_N": 41478.0,
    "right_Rx_N": 2.6566e-12,
    "right_Ry_N": -47324.0,
    "right_Rz_N": 1155.3,
    "right_total_N": 47338.0,
    "max_deformation_mm": 5.1296,
    "max_vm_MPa": 415.61,
}

rows = []
for k in linear:
    b = linear[k]
    c = large_def[k]
    rows.append({
        "metric": k,
        "linear_baseline": b,
        "large_deflection": c,
        "difference": c-b,
        "percent_change_signed": (100*(c-b)/b) if abs(b)>1e-9 else float("nan"),
        "percent_change_magnitude": (100*(abs(c)-abs(b))/abs(b)) if abs(b)>1e-9 else float("nan"),
    })

with Path("phase2e3b14b10_large_deflection_sensitivity_v01.csv").open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
