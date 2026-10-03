from math import sqrt
r6={"stress_MPa":407.52,"x_mm":4.756123,"y_mm":53.219397,"z_mm":965.195576,"brace_force_N":-67348.0,"max_deformation_mm":5.1478}
r4={"stress_MPa":430.71,"x_mm":-0.136580,"y_mm":53.429862,"z_mm":965.192475,"brace_force_N":-67310.0,"max_deformation_mm":5.1343}
pct=lambda new,old:100.0*(new-old)/old
dx=r4["x_mm"]-r6["x_mm"]; dy=r4["y_mm"]-r6["y_mm"]; dz=r4["z_mm"]-r6["z_mm"]
print("Stress change [%]:",pct(r4["stress_MPa"],r6["stress_MPa"]))
print("Brace force magnitude change [%]:",pct(abs(r4["brace_force_N"]),abs(r6["brace_force_N"])))
print("Deformation change [%]:",pct(r4["max_deformation_mm"],r6["max_deformation_mm"]))
print("Hotspot shift [mm]:",sqrt(dx*dx+dy*dy+dz*dz))
