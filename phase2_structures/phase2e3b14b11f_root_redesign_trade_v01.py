from pathlib import Path
import csv

HERE = Path(__file__).resolve().parent
with (HERE / "phase2e3b14b7_reference_candidate.csv").open(newline="", encoding="utf-8-sig") as f:
    src = next(csv.DictReader(f))

Mx_u_kNm = abs(float(src["Mx_root_ultimate_kNm"]))
Mz_u_kNm = abs(float(src["Mz_root_ultimate_kNm"]))
b0 = float(src["bx_mm"])
h0 = float(src["hz_mm"])

sigma_r8 = 732.45
Sy = 505.0
target_ms_y = 0.10
sigma_target = Sy / (1.0 + target_ms_y)
required_ratio = sigma_target / sigma_r8

Mx = Mx_u_kNm * 1e6
Mz = Mz_u_kNm * 1e6

def corner_bending_proxy(b, h):
    return 6.0*Mx/(b*h*h) + 6.0*Mz/(h*b*b)

sigma_nom0 = corner_bending_proxy(b0, h0)

candidates = [
    ("F2_BALANCED", 95.0, 115.0, 12.0),
    ("F3_ROBUST", 100.0, 115.0, 15.0),
]

print("B14B11F root redesign analytical trade")
print(f"Ultimate root moments: |Mx|={Mx_u_kNm:.6f} kN*m, |Mz|={Mz_u_kNm:.6f} kN*m")
print(f"Current retained R8 local peak: {sigma_r8:.2f} MPa")
print(f"Target stress for MS_y=+0.10: {sigma_target:.3f} MPa")
print(f"Required peak ratio: {required_ratio:.5f}")
print()
for name,b,h,r in candidates:
    s = corner_bending_proxy(b,h)
    ratio = s/sigma_nom0
    print(f"{name}: {b:.1f}x{h:.1f} mm, R{r:.1f}")
    print(f"  nominal corner-bending proxy = {s:.3f} MPa")
    print(f"  ratio vs 85x95 = {ratio:.5f}; reduction = {100*(1-ratio):.2f}%")
    print(f"  section-only target screen = {'PASS' if ratio <= required_ratio else 'FAIL'}")
