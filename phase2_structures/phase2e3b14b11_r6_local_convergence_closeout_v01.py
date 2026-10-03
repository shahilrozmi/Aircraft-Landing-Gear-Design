from math import sqrt

sharp = {'mesh_mm': None, 'stress_MPa': 415.55, 'brace_force_N': -67231.0, 'max_deformation_mm': 5.122}
r3 = {'mesh_mm': 3.0, 'stress_MPa': 411.23, 'x_mm': -5.02568, 'y_mm': 53.19141, 'z_mm': 965.185037, 'brace_force_N': -67348.0, 'elongation_mm': -0.56842, 'max_deformation_mm': 5.1354}
r25 = {'mesh_mm': 2.5, 'stress_MPa': 408.46, 'x_mm': 14.380477, 'y_mm': 51.449116, 'z_mm': 965.189499, 'brace_force_N': -67348.0, 'elongation_mm': -0.56842, 'max_deformation_mm': 5.1459}
r2 = {'mesh_mm': 2.0, 'stress_MPa': 407.52, 'x_mm': 4.756123, 'y_mm': 53.219397, 'z_mm': 965.195576, 'brace_force_N': -67348.0, 'elongation_mm': -0.56842, 'max_deformation_mm': 5.1478}

def pct(new, old):
    return 100.0*(new-old)/old

def dist(a,b):
    return sqrt((a["x_mm"]-b["x_mm"])**2 +
                (a["y_mm"]-b["y_mm"])**2 +
                (a["z_mm"]-b["z_mm"])**2)

print("3.0 -> 2.5 mm stress change [%]:", pct(r25["stress_MPa"], r3["stress_MPa"]))
print("2.5 -> 2.0 mm stress change [%]:", pct(r2["stress_MPa"], r25["stress_MPa"]))
print("R6 2.0 mm vs sharp baseline [%]:", pct(r2["stress_MPa"], sharp["stress_MPa"]))
print("2.5 -> 2.0 mm hotspot shift [mm]:", dist(r2, r25))
