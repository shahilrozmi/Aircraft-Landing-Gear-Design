from math import sqrt

old = {'stress_MPa': 415.49, 'x_mm': -5.025296, 'y_mm': 53.190953, 'z_mm': 965.183876}
new = {'stress_MPa': 433.41, 'x_mm': -9.542205, 'y_mm': 52.53084, 'z_mm': 967.788613}
dx = new["x_mm"] - old["x_mm"]
dy = new["y_mm"] - old["y_mm"]
dz = new["z_mm"] - old["z_mm"]
distance = sqrt(dx*dx + dy*dy + dz*dz)
stress_change = 100*(new["stress_MPa"]-old["stress_MPa"])/old["stress_MPa"]

print("3-D hotspot shift [mm]:", distance)
print("Stress change [%]:", stress_change)
