import math

runs = [{'root_size_mm': 1.5, 'nodes': 12090, 'elements': 6796, 'vm_max_mpa': 442.62, 'vm_avg_mpa': 95.227, 'vm_min_mpa': 6.9896, 'x_mm': 39.974671, 'y_mm': 41.798669, 'z_mm': 994.421519, 'node_id': 575, 'u_max_mm': 0.73252}, {'root_size_mm': 1.0, 'nodes': 15362, 'elements': 8784, 'vm_max_mpa': 697.48, 'vm_avg_mpa': 90.99, 'vm_min_mpa': 6.0169, 'x_mm': 38.9793, 'y_mm': 37.892137, 'z_mm': 994.198461, 'node_id': 595, 'u_max_mm': 0.73252}, {'root_size_mm': 0.75, 'nodes': 19081, 'elements': 11045, 'vm_max_mpa': 732.45, 'vm_avg_mpa': 91.817, 'vm_min_mpa': 5.8459, 'x_mm': 39.934226, 'y_mm': 40.941526, 'z_mm': 994.342929, 'node_id': 609, 'u_max_mm': 0.73252}]

def pct(new, old):
    return 100.0*(new-old)/old

d15_10 = pct(runs[1]["vm_max_mpa"], runs[0]["vm_max_mpa"])
d10_075 = pct(runs[2]["vm_max_mpa"], runs[1]["vm_max_mpa"])
davg_10_075 = pct(runs[2]["vm_avg_mpa"], runs[1]["vm_avg_mpa"])
du_10_075 = pct(runs[2]["u_max_mm"], runs[1]["u_max_mm"])
shift_10_075 = math.dist(
    (runs[1]["x_mm"], runs[1]["y_mm"], runs[1]["z_mm"]),
    (runs[2]["x_mm"], runs[2]["y_mm"], runs[2]["z_mm"])
)

sy = 505.0
su = 572.0
ms_y = sy / runs[2]["vm_max_mpa"] - 1.0
ms_u = su / runs[2]["vm_max_mpa"] - 1.0

print(f"VM max change 1.5 -> 1.0 mm: {d15_10:+.3f} %")
print(f"VM max change 1.0 -> 0.75 mm: {d10_075:+.3f} %")
print(f"VM average change 1.0 -> 0.75 mm: {davg_10_075:+.3f} %")
print(f"Hotspot shift 1.0 -> 0.75 mm: {shift_10_075:.3f} mm")
print(f"Max displacement change 1.0 -> 0.75 mm: {du_10_075:+.6f} %")
print(f"0.75 mm generic yield MS: {ms_y:+.4f}")
print(f"0.75 mm generic ultimate MS: {ms_u:+.4f}")
