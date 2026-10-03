def pct(new, old):
    return 100.0*(new-old)/old

prev = {
    "head_vm_MPa": 294.96,
    "max_def_mm": 3.5022,
    "brace_force_N": -67391.0,
    "nodes": 40815,
    "elements": 97824,
}
edge = {
    "head_vm_MPa": 305.8,
    "max_def_mm": 3.5179,
    "brace_force_N": -67391.0,
    "nodes": 42862,
    "elements": 105894,
}

print("Head VM change [%]:", pct(edge["head_vm_MPa"], prev["head_vm_MPa"]))
print("Max deformation change [%]:", pct(edge["max_def_mm"], prev["max_def_mm"]))
print("Brace force magnitude change [%]:", pct(abs(edge["brace_force_N"]), abs(prev["brace_force_N"])))
print("Node change [%]:", pct(edge["nodes"], prev["nodes"]))
print("Element change [%]:", pct(edge["elements"], prev["elements"]))
