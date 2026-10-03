import math

nodes = 12090
elements = 6796
vm_max_mpa = 1847.5
vm_loc = (45.532908, 26.964134, 993.636235)
total_deformation_max_mm = 0.73252

cuts = {'Y25': 25.0, 'Y120': 120.0, 'Z920': 920.0, 'Z992': 992.0}
r8_hotspot = (18.702387, 49.818011, 964.937219)

dist_to_r8_ref = math.dist(vm_loc, r8_hotspot)
distances = {
    "Y25": abs(vm_loc[1] - cuts["Y25"]),
    "Y120": abs(vm_loc[1] - cuts["Y120"]),
    "Z920": abs(vm_loc[2] - cuts["Z920"]),
    "Z992": abs(vm_loc[2] - cuts["Z992"]),
}
nearest_cut = min(distances, key=distances.get)

print("B14B11E single-body baseline diagnostic")
print(f"Nodes / elements: {nodes} / {elements}")
print(f"Global VM max: {vm_max_mpa:.1f} MPa at {vm_loc} mm")
print(f"Total deformation max: {total_deformation_max_mm:.5f} mm")
print(f"Distance to R8 reference hotspot: {dist_to_r8_ref:.3f} mm")
print(f"Nearest artificial cut by reported coordinate: {nearest_cut} = {distances[nearest_cut]:.3f} mm")
print("Disposition: global VM maximum is boundary-dominated; fix overlapping imported-displacement BCs before convergence.")
