root_size_mm = 1.5
mesh_nodes = 12090
mesh_elements = 6796
vm_fillet_max_mpa = 442.62
vm_fillet_avg_mpa = 95.227
vm_fillet_min_mpa = 6.9896
vm_location_mm = (39.974671, 41.798669, 994.421519)
vm_node_id = 575
total_deformation_max_mm = 0.73252

sy_mpa = 505.0
su_mpa = 572.0
ms_yield = sy_mpa / vm_fillet_max_mpa - 1.0
ms_ultimate = su_mpa / vm_fillet_max_mpa - 1.0

print("B14B11E R8 fillet convergence baseline")
print(f"Root local size: {root_size_mm:.3f} mm")
print(f"Mesh: {mesh_nodes} nodes / {mesh_elements} elements")
print(f"Fillet VM max: {vm_fillet_max_mpa:.2f} MPa at node {vm_node_id}")
print(f"Location: X={vm_location_mm[0]:.6f}, Y={vm_location_mm[1]:.6f}, Z={vm_location_mm[2]:.6f} mm")
print(f"Total deformation max: {total_deformation_max_mm:.5f} mm")
print(f"Preliminary yield MS: {ms_yield:+.4f}")
print(f"Preliminary ultimate MS: {ms_ultimate:+.4f}")
print("Status: BASELINE ONLY — do not freeze until 1.0 mm and, if needed, 0.75 mm refinement are reviewed.")
