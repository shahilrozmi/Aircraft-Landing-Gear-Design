from math import sqrt

def pct(new, old):
    return 100.0*(new-old)/old

r15 = {
    "head_vm_MPa": 254.42,
    "max_deformation_mm": 3.4977,
    "brace_force_N": -67391.0,
    "hotspot": (31.832506, 42.589256, 964.904460),
}

r125 = {
    "head_vm_MPa": 294.96,
    "max_deformation_mm": 3.5022,
    "brace_force_N": -67391.0,
    "hotspot": (23.502701, 47.727015, 964.925536),
}

dx = r125["hotspot"][0] - r15["hotspot"][0]
dy = r125["hotspot"][1] - r15["hotspot"][1]
dz = r125["hotspot"][2] - r15["hotspot"][2]

print("Head VM change [%]:", pct(r125["head_vm_MPa"], r15["head_vm_MPa"]))
print("Deformation change [%]:", pct(r125["max_deformation_mm"], r15["max_deformation_mm"]))
print("Brace force magnitude change [%]:", pct(abs(r125["brace_force_N"]), abs(r15["brace_force_N"])))
print("Hotspot shift [mm]:", sqrt(dx*dx + dy*dy + dz*dz))
