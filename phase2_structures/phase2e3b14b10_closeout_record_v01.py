from pathlib import Path
import csv

OUTDIR = Path(".")

linear = {
    "brace_force_N": -67231.0,
    "brace_elongation_mm": -0.56743,
    "left_total_N": 40355.0,
    "right_total_N": 47301.0,
    "max_deformation_mm": 5.122,
    "max_vm_MPa": 415.55,
}
large_def = {
    "brace_force_N": -67212.0,
    "brace_elongation_mm": -0.56727,
    "left_total_N": 41478.0,
    "right_total_N": 47338.0,
    "max_deformation_mm": 5.1296,
    "max_vm_MPa": 415.61,
}
ansys = {
    "run_completed": True,
    "error_count": 0,
    "warning_count": 5,
    "end_time": 1.0,
    "nodes": 38327,
    "elements_total": 105318,
    "dof": 112461,
    "solve_time_s": 284.6265271,
    "elapsed_time_s": 311.635,
}

def magnitude_change_pct(new, old):
    return 100.0 * (abs(new) - abs(old)) / abs(old)

record = {
    "phase": "PHASE2E3-B14B-10",
    "status": "CLOSED_FOR_GLOBAL_LOAD_PATH_AND_LARGE_DEFLECTION_SENSITIVITY",
    "ansys_run_completed": ansys["run_completed"],
    "ansys_error_count": ansys["error_count"],
    "ansys_warning_count": ansys["warning_count"],
    "ansys_end_time": ansys["end_time"],
    "nodes": ansys["nodes"],
    "elements_total": ansys["elements_total"],
    "dof": ansys["dof"],
    "solve_time_s": ansys["solve_time_s"],
    "elapsed_time_s": ansys["elapsed_time_s"],
    "linear_brace_force_N": linear["brace_force_N"],
    "large_def_brace_force_N": large_def["brace_force_N"],
    "linear_brace_elongation_mm": linear["brace_elongation_mm"],
    "large_def_brace_elongation_mm": large_def["brace_elongation_mm"],
    "linear_left_total_N": linear["left_total_N"],
    "large_def_left_total_N": large_def["left_total_N"],
    "linear_right_total_N": linear["right_total_N"],
    "large_def_right_total_N": large_def["right_total_N"],
    "linear_max_deformation_mm": linear["max_deformation_mm"],
    "large_def_max_deformation_mm": large_def["max_deformation_mm"],
    "linear_max_vm_MPa": linear["max_vm_MPa"],
    "large_def_max_vm_MPa": large_def["max_vm_MPa"],
    "brace_force_mag_change_pct": magnitude_change_pct(large_def["brace_force_N"], linear["brace_force_N"]),
    "brace_elong_mag_change_pct": magnitude_change_pct(large_def["brace_elongation_mm"], linear["brace_elongation_mm"]),
    "left_total_mag_change_pct": magnitude_change_pct(large_def["left_total_N"], linear["left_total_N"]),
    "right_total_mag_change_pct": magnitude_change_pct(large_def["right_total_N"], linear["right_total_N"]),
    "max_deformation_change_pct": magnitude_change_pct(large_def["max_deformation_mm"], linear["max_deformation_mm"]),
    "max_vm_change_pct": magnitude_change_pct(large_def["max_vm_MPa"], linear["max_vm_MPa"]),
    "local_stress_convergence_closed": False,
}

with (OUTDIR / "phase2e3b14b10_closeout_record_v01.csv").open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["field", "value"])
    for k, v in record.items():
        w.writerow([k, v])

lines = [
    "PHASE 2E3-B14B-10 — PHYSICAL BRACE FEA CLOSEOUT SUMMARY V0.1",
    "",
    "ANSYS RUN COMPLETION",
    "--------------------",
    f"Run completed:                 {record['ansys_run_completed']}",
    f"Errors:                        {record['ansys_error_count']}",
    f"Warnings:                      {record['ansys_warning_count']}",
    f"End time reached:              {record['ansys_end_time']:.6f}",
    f"Nodes:                         {record['nodes']}",
    f"Total elements:                {record['elements_total']}",
    f"DOF:                           {record['dof']}",
    f"MAPDL solve time:              {record['solve_time_s']:.3f} s",
    f"MAPDL elapsed time:            {record['elapsed_time_s']:.3f} s",
    "",
    "CLEANED LINEAR -> LARGE-DEFLECTION SENSITIVITY",
    "----------------------------------------------",
    f"Brace force magnitude change:      {record['brace_force_mag_change_pct']:+.6f} %",
    f"Brace elongation magnitude change: {record['brace_elong_mag_change_pct']:+.6f} %",
    f"Left journal total change:          {record['left_total_mag_change_pct']:+.6f} %",
    f"Right journal total change:         {record['right_total_mag_change_pct']:+.6f} %",
    f"Max deformation change:             {record['max_deformation_change_pct']:+.6f} %",
    f"Max von-Mises change:               {record['max_vm_change_pct']:+.6f} %",
    "",
    "DISPOSITION",
    "-----------",
    "B14B-10 is CLOSED for global physical-brace load-path validation and large-deflection sensitivity.",
    "",
    "This closeout is NOT a final local-stress convergence approval:",
    "- linear tetrahedral mesh warning remains,",
    "- rigid-body/support caution remains,",
    "- contact/BC overlap information remains,",
    "- the sharp horn/head root remains the governing local hotspot and still requires",
    "  physical fillet/transition refinement and local convergence work.",
    "",
    "Next phase: B14B-11 horn-root fillet / transition refinement.",
]
(OUTDIR / "phase2e3b14b10_closeout_summary_v01.txt").write_text("\n".join(lines), encoding="utf-8")

print("B14B-10 closeout artifacts written.")
