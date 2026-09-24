"""
Landing_Gear_Design_Project
PHASE 2E3-B13B V0.2R1 — INTERFERENCE-FIT MINIMUM-LIGAMENT CORRECTION

CORRECTION
----------
V0.2 treated the local 7075 head surrounding the Ø50 bushing as an axisymmetric
ring with outside diameter 106 mm. That 106 mm dimension is the lateral head width.

The current B11 head model also has a 78 mm vertical height. With the original
Ø38 bore this gave 20 mm upper/lower ligament and 34 mm side ligament.

Therefore, once the bushing seat is enlarged to Ø50:
    minimum vertical ligament = (78 - 50)/2 = 14 mm
    side ligament             = (106 - 50)/2 = 28 mm

To avoid overstating radial stiffness in the interference-fit hand model, this
revision reruns the Lamé compliance surrogate using the MINIMUM 78 mm outer
diameter. It is still only a local axisymmetric surrogate; the actual head is 3-D
and non-axisymmetric and must be checked in B13C/B13D FEA.

The correction does NOT invalidate the bushing concept. It corrects the geometric
interpretation and provides a less-optimistic fit-only elastic sensitivity.
"""

from pathlib import Path
import math
import pandas as pd

# Geometry [mm]
D_BUSH_ID = 38.0
D_BUSH_OD = 50.0
D_HEAD_MIN = 78.0     # vertical height governs minimum ligament
D_HEAD_LATERAL = 106.0

a = D_BUSH_ID / 2.0
b = D_BUSH_OD / 2.0
c = D_HEAD_MIN / 2.0

# Materials [MPa]
E_BRONZE = 125000.0
NU_BRONZE = 0.32
BRONZE_PROOF = 414.0

E_7075 = 71700.0
NU_7075 = 0.33
YIELD_7075 = 503.0

INTERFERENCE_MM = [
    0.005, 0.010, 0.015, 0.020, 0.025, 0.030,
    0.040, 0.050, 0.060, 0.080, 0.100, 0.150, 0.200
]

def vm2(sr, st):
    return math.sqrt(sr**2 - sr*st + st**2)

def bronze_compliance():
    return (
        b / E_BRONZE
        * (((1-NU_BRONZE)*b*b + (1+NU_BRONZE)*a*a)/(b*b-a*a))
    )

def head_compliance():
    return (
        b / E_7075
        * (((1-NU_7075)*b*b + (1+NU_7075)*c*c)/(c*c-b*b))
    )

CB = bronze_compliance()
CH = head_compliance()
CT = CB + CH

def pressure(delta_d):
    return (delta_d/2.0)/CT

def head_vm(p):
    A = p*b*b/(c*c-b*b)
    B = p*b*b*c*c/(c*c-b*b)
    sr = A - B/b**2
    st = A + B/b**2
    return sr, st, vm2(sr,st)

def bronze_vm(p):
    A = -p*b*b/(b*b-a*a)
    B = -p*a*a*b*b/(b*b-a*a)

    sr_i = A - B/a**2
    st_i = A + B/a**2
    vm_i = vm2(sr_i, st_i)

    sr_o = A - B/b**2
    st_o = A + B/b**2
    vm_o = vm2(sr_o, st_o)

    return max(vm_i, vm_o)

rows = []
for d in INTERFERENCE_MM:
    p = pressure(d)
    _, _, vh = head_vm(p)
    vb = bronze_vm(p)
    rows.append({
        "diametral_interference_mm": d,
        "fit_pressure_MPa": p,
        "head_VM_fit_only_MPa": vh,
        "MS_7075_yield_fit_only": YIELD_7075/vh - 1.0,
        "bronze_VM_fit_only_MPa": vb,
        "MS_bronze_proof_fit_only": BRONZE_PROOF/vb - 1.0,
    })

df = pd.DataFrame(rows)

p1 = pressure(1.0)
_,_,vh1 = head_vm(p1)
vb1 = bronze_vm(p1)
d_head = YIELD_7075/vh1
d_bronze = BRONZE_PROOF/vb1

here = Path(__file__).resolve().parent
csv_path = here / "phase2e3b13b_v02r1_interference_sweep.csv"
summary_path = here / "phase2e3b13b_v02r1_summary.txt"
df.to_csv(csv_path,index=False)

lines=[]
def emit(s=""):
    print(s); lines.append(s)

emit("="*106)
emit(" PHASE 2E3-B13B V0.2R1 — INTERFERENCE-FIT MINIMUM-LIGAMENT CORRECTION")
emit("="*106)
emit("\n--- CORRECTED GEOMETRY INTERPRETATION ---")
emit(f"Head lateral width:                    {D_HEAD_LATERAL:8.3f} mm")
emit(f"Head minimum vertical height:          {D_HEAD_MIN:8.3f} mm")
emit(f"Bushing seat diameter:                 {D_BUSH_OD:8.3f} mm")
emit(f"Minimum vertical ligament:             {(D_HEAD_MIN-D_BUSH_OD)/2:8.3f} mm")
emit(f"Side ligament:                         {(D_HEAD_LATERAL-D_BUSH_OD)/2:8.3f} mm")
emit("V0.2's 28 mm value was the SIDE ligament, not the minimum ligament.")

emit("\n--- CORRECTED FIT SENSITIVITY ---")
emit(f"{'delta_d':>9} {'p_fit':>9} {'VM7075':>10} {'MS7075':>10} {'VMbronze':>11} {'MSbronze':>11}")
emit("-"*70)
for _,r in df.iterrows():
    emit(
        f"{r['diametral_interference_mm']:9.3f} "
        f"{r['fit_pressure_MPa']:9.2f} "
        f"{r['head_VM_fit_only_MPa']:10.2f} "
        f"{r['MS_7075_yield_fit_only']:10.3f} "
        f"{r['bronze_VM_fit_only_MPa']:11.2f} "
        f"{r['MS_bronze_proof_fit_only']:11.3f}"
    )

emit("\n--- LINEAR ELASTIC FIRST SCREEN ---")
emit(f"7075 yield surrogate:                  {d_head:8.3f} mm diametral interference")
emit(f"Bronze proof surrogate:                {d_bronze:8.3f} mm diametral interference")
emit(f"First material screen:                 {min(d_head,d_bronze):8.3f} mm")
emit("Interpretation: the corrected minimum-ligament surrogate still leaves tens-of-micrometre")
emit("fit sensitivities comfortably elastic. This does NOT define the production fit.")

emit("\nOUTPUT FILES")
emit(f"CSV:     {csv_path}")
emit(f"Summary: {summary_path}")
emit("="*106)

summary_path.write_text("\n".join(lines),encoding="utf-8")
