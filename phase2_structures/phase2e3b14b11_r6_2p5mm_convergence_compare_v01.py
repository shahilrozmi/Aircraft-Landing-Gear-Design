from math import sqrt

r3 = {'stress_MPa': 411.23, 'x_mm': -5.02568, 'y_mm': 53.19141, 'z_mm': 965.185037, 'brace_force_N': -67348.0, 'elongation_mm': -0.56842, 'max_deformation_mm': 5.1354}
r25 = {'stress_MPa': 408.46, 'x_mm': 14.380477, 'y_mm': 51.449116, 'z_mm': 965.189499, 'brace_force_N': -67348.0, 'elongation_mm': -0.56842, 'max_deformation_mm': 5.1459}

def pct(new, old):
    return 100.0*(new-old)/old

dx = r25["x_mm"] - r3["x_mm"]
dy = r25["y_mm"] - r3["y_mm"]
dz = r25["z_mm"] - r3["z_mm"]
shift = sqrt(dx*dx + dy*dy + dz*dz)

print("Stress change [%]:", pct(r25["stress_MPa"], r3["stress_MPa"]))
print("Deformation change [%]:", pct(r25["max_deformation_mm"], r3["max_deformation_mm"]))
print("Hotspot shift [mm]:", shift)
