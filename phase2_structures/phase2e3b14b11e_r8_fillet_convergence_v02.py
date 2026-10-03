import math

runs = [{'root_size_mm': 1.5, 'nodes': 12090, 'elements': 6796, 'vm_max_mpa': 442.62, 'vm_avg_mpa': 95.227, 'vm_min_mpa': 6.9896, 'x_mm': 39.974671, 'y_mm': 41.798669, 'z_mm': 994.421519, 'node_id': 575, 'u_max_mm': 0.73252}, {'root_size_mm': 1.0, 'nodes': 15362, 'elements': 8784, 'vm_max_mpa': 697.48, 'vm_avg_mpa': 90.99, 'vm_min_mpa': 6.0169, 'x_mm': 38.9793, 'y_mm': 37.892137, 'z_mm': 994.198461, 'node_id': 595, 'u_max_mm': 0.73252}]
coarse, fine = runs

stress_change_pct = 100.0 * (fine["vm_max_mpa"] - coarse["vm_max_mpa"]) / coarse["vm_max_mpa"]
stress_ratio = fine["vm_max_mpa"] / coarse["vm_max_mpa"]
u_change_pct = 100.0 * (fine["u_max_mm"] - coarse["u_max_mm"]) / coarse["u_max_mm"]
hotspot_shift_mm = math.dist(
    (coarse["x_mm"], coarse["y_mm"], coarse["z_mm"]),
    (fine["x_mm"], fine["y_mm"], fine["z_mm"])
)

sy = 505.0
su = 572.0
fine_ms_y = sy / fine["vm_max_mpa"] - 1.0
fine_ms_u = su / fine["vm_max_mpa"] - 1.0

print(f"Stress change 1.5 -> 1.0 mm: {stress_change_pct:+.3f} %")
print(f"Stress ratio: {stress_ratio:.5f}")
print(f"Hotspot shift: {hotspot_shift_mm:.3f} mm")
print(f"Max-deformation change: {u_change_pct:+.6f} %")
print(f"1.0 mm preliminary yield MS: {fine_ms_y:+.4f}")
print(f"1.0 mm preliminary ultimate MS: {fine_ms_u:+.4f}")
print("Disposition: NOT CONVERGED. Run the planned 0.75 mm R8-local refinement with all other settings frozen.")
