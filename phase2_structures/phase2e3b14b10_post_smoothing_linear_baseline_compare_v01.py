from pathlib import Path
import csv, math

baseline = {
    "brace_force_N": -67229.0,
    "brace_elongation_mm": -0.56741,
    "left_Rx_N": 18466.0,
    "left_Ry_N": 35839.0,
    "left_Rz_N": 1811.2,
    "left_total_N": 40357.0,
    "right_Rx_N": 2.5492e-12,
    "right_Ry_N": -47259.0,
    "right_Rz_N": 2045.5,
    "right_total_N": 47304.0,
    "max_deformation_mm": 5.1211,
    "max_vm_MPa": 415.49,
}
current = {
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

rows=[]
for k in baseline:
    b=baseline[k]; c=current[k]
    rows.append({
        "metric":k,
        "baseline":b,
        "current":c,
        "difference":c-b,
        "percent_change_signed": (100*(c-b)/b) if abs(b)>1e-9 else float("nan"),
        "percent_change_magnitude": (100*(abs(c)-abs(b))/abs(b)) if abs(b)>1e-9 else float("nan"),
    })

with Path("phase2e3b14b10_post_smoothing_linear_baseline_compare_v01.csv").open("w", newline="") as f:
    w=csv.DictWriter(f, fieldnames=rows[0].keys())
    w.writeheader()
    w.writerows(rows)
