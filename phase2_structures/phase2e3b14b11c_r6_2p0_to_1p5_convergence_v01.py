def pct(new, old):
    return 100.0 * (new - old) / old

r6_2 = {
    "stress_MPa": 412.24,
    "max_deformation_mm": 5.1439,
    "brace_force_N": -67348.0,
    "nodes": 38424,
    "elements": 87564,
}

r6_15 = {
    "stress_MPa": 428.84,
    "max_deformation_mm": 5.1578,
    "brace_force_N": -67348.0,
    "nodes": 39467,
    "elements": 92160,
}

print("Stress change [%]:",
      pct(r6_15["stress_MPa"], r6_2["stress_MPa"]))

print("Deformation change [%]:",
      pct(r6_15["max_deformation_mm"], r6_2["max_deformation_mm"]))

print("Brace force magnitude change [%]:",
      pct(abs(r6_15["brace_force_N"]), abs(r6_2["brace_force_N"])))

print("Node change [%]:",
      pct(r6_15["nodes"], r6_2["nodes"]))

print("Element change [%]:",
      pct(r6_15["elements"], r6_2["elements"]))
