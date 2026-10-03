import math

baseline = {'name': 'B14B11E_R8_0p75', 'vm_peak_mpa': 732.45, 'vm_avg_mpa': 91.817, 'u_max_mm': 0.73252, 'x_mm': 39.934226, 'y_mm': 40.941526, 'z_mm': 994.342929}
f2 = {'name': 'B14B11F_F2_BALANCED_1p0', 'nodes': 24801, 'elements': 14487, 'vm_global_peak_mpa': 2144.2, 'vm_fillet_peak_mpa': 1995.7, 'vm_fillet_avg_mpa': 77.072, 'vm_fillet_min_mpa': 1.0072, 'u_max_mm': 0.73252, 'x_mm': 40.752712, 'y_mm': 37.333527, 'z_mm': 994.065585, 'node_id': 580}

peak_change_pct = 100*(f2["vm_fillet_peak_mpa"]-baseline["vm_peak_mpa"])/baseline["vm_peak_mpa"]
avg_change_pct = 100*(f2["vm_fillet_avg_mpa"]-baseline["vm_avg_mpa"])/baseline["vm_avg_mpa"]
u_change_pct = 100*(f2["u_max_mm"]-baseline["u_max_mm"])/baseline["u_max_mm"]
hotspot_shift_mm = math.dist(
    (baseline["x_mm"],baseline["y_mm"],baseline["z_mm"]),
    (f2["x_mm"],f2["y_mm"],f2["z_mm"])
)
peak_to_avg = f2["vm_fillet_peak_mpa"]/f2["vm_fillet_avg_mpa"]

print(f"F2 peak change vs R8: {peak_change_pct:+.2f} %")
print(f"F2 average change vs R8: {avg_change_pct:+.2f} %")
print(f"Hotspot shift: {hotspot_shift_mm:.3f} mm")
print(f"Peak/average ratio: {peak_to_avg:.2f}")
print(f"Max-deformation change: {u_change_pct:+.6f} %")
