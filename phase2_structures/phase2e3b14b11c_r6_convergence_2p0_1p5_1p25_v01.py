from math import sqrt

def pct(new, old):
    return 100.0 * (new - old) / old

r15 = {
    "stress_MPa": 428.84,
    "max_deformation_mm": 5.1578,
    "brace_force_N": -67348.0,
    "hotspot": (4.756711, 53.219215, 965.196488),
}

r125 = {
    "stress_MPa": 427.81,
    "max_deformation_mm": 5.1624,
    "brace_force_N": -67348.0,
    "hotspot": (4.757493, 53.219731, 965.197498),
}

dx = r125["hotspot"][0] - r15["hotspot"][0]
dy = r125["hotspot"][1] - r15["hotspot"][1]
dz = r125["hotspot"][2] - r15["hotspot"][2]

print("Stress change 1.5 -> 1.25 mm [%]:",
      pct(r125["stress_MPa"], r15["stress_MPa"]))

print("Deformation change [%]:",
      pct(r125["max_deformation_mm"], r15["max_deformation_mm"]))

print("Brace force magnitude change [%]:",
      pct(abs(r125["brace_force_N"]), abs(r15["brace_force_N"])))

print("Hotspot shift [mm]:",
      sqrt(dx*dx + dy*dy + dz*dz))
