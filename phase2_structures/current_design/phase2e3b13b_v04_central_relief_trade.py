"""
Landing_Gear_Design_Project
PHASE 2E3-B13B V0.4 — CENTRAL SHAFT RELIEF / HEAD-SECTION TRADE

PURPOSE
-------
Choose a working central relief-bore diameter between the two 30 mm bronze bushings
without allowing the Ø38 shaft to contact exposed 7075.

CURRENT HEAD CROSS-SECTION
--------------------------
Lateral width:  106 mm
Vertical height: 78 mm
Original bore:   38 mm

Candidate central relief diameters are compared using:
    - radial clearance to the Ø38 shaft
    - minimum vertical ligament
    - side ligament
    - net section area
    - section inertias of a centered rectangular head less a circular bore
    - change relative to the original Ø38-bore section

A rough nominal-ligament stress sensitivity is also reported by scaling the B11
53.641 MPa nominal value inversely with the upper/lower ligament:
    sigma_sens = 53.641 * 20 / ligament

This is ONLY a sensitivity bridge to B11, not a replacement for B13C FEA.

WORKING SELECTION
-----------------
Ø50 through relief is selected as the B13C working geometry because:
    - it exactly matches the bushing-seat diameter
    - it leaves no Ø38 aluminum land that can accidentally contact the shaft
    - it removes an internal bore shoulder/step between the two bushing seats
    - it provides 6 mm radial shaft-to-aluminum clearance
    - the gross section-property reduction is modest enough to take forward to FEA

This is a WORKING CAD/FEA selection, not a final certified head geometry.
"""

from pathlib import Path
import math
import pandas as pd

# Geometry [mm]
HEAD_W = 106.0
HEAD_H = 78.0
SHAFT_D = 38.0
BASE_BORE_D = 38.0

RELIEF_D = [40,42,44,46,48,50]

# B11 nominal reference sensitivity
B11_LIGAMENT_REF_MM = 20.0
B11_NOMINAL_STRESS_REF_MPA = 53.641
YIELD_7075_MPA = 503.0

WORKING_RELIEF_D = 50.0

def props(D):
    A = HEAD_W*HEAD_H - math.pi*D**2/4.0
    Iy = HEAD_W*HEAD_H**3/12.0 - math.pi*D**4/64.0
    Iz = HEAD_H*HEAD_W**3/12.0 - math.pi*D**4/64.0
    return A,Iy,Iz

A0,Iy0,Iz0 = props(BASE_BORE_D)

rows=[]
for D in RELIEF_D:
    A,Iy,Iz = props(D)
    vlig = (HEAD_H-D)/2.0
    slig = (HEAD_W-D)/2.0
    radial_clearance = (D-SHAFT_D)/2.0

    sigma_sens = B11_NOMINAL_STRESS_REF_MPA * B11_LIGAMENT_REF_MM/vlig
    ms_sens = YIELD_7075_MPA/sigma_sens - 1.0

    rows.append({
        "central_relief_d_mm":D,
        "shaft_to_aluminum_radial_clearance_mm":radial_clearance,
        "minimum_vertical_ligament_mm":vlig,
        "side_ligament_mm":slig,
        "net_area_mm2":A,
        "net_area_change_pct":100*(A/A0-1),
        "Iy_mm4":Iy,
        "Iy_change_pct":100*(Iy/Iy0-1),
        "Iz_mm4":Iz,
        "Iz_change_pct":100*(Iz/Iz0-1),
        "B11_scaled_nominal_stress_sensitivity_MPa":sigma_sens,
        "MS_7075_yield_on_scaled_sensitivity":ms_sens,
    })

df=pd.DataFrame(rows)
work=df[df["central_relief_d_mm"]==WORKING_RELIEF_D].iloc[0]

here=Path(__file__).resolve().parent
csv_path=here/"phase2e3b13b_v04_central_relief_trade.csv"
summary_path=here/"phase2e3b13b_v04_summary.txt"
df.to_csv(csv_path,index=False)

lines=[]
def emit(s=""):
    print(s); lines.append(s)

emit("="*112)
emit(" PHASE 2E3-B13B V0.4 — CENTRAL SHAFT RELIEF / HEAD-SECTION TRADE")
emit("="*112)

emit("\n--- BASELINE ---")
emit(f"Head cross-section:                    {HEAD_W:.1f} x {HEAD_H:.1f} mm")
emit(f"Original bore:                         Ø{BASE_BORE_D:.1f} mm")
emit(f"Original upper/lower ligament:         {(HEAD_H-BASE_BORE_D)/2:.1f} mm")
emit(f"Original side ligament:                {(HEAD_W-BASE_BORE_D)/2:.1f} mm")

emit("\n--- RELIEF TRADE ---")
emit(
    f"{'Drel':>6} {'clr_r':>7} {'v_lig':>7} {'s_lig':>7} "
    f"{'dA%':>8} {'dIy%':>8} {'dIz%':>8} {'sig_sens':>10} {'MSsens':>9}"
)
emit("-"*86)
for _,r in df.iterrows():
    emit(
        f"{r['central_relief_d_mm']:6.0f} "
        f"{r['shaft_to_aluminum_radial_clearance_mm']:7.2f} "
        f"{r['minimum_vertical_ligament_mm']:7.2f} "
        f"{r['side_ligament_mm']:7.2f} "
        f"{r['net_area_change_pct']:8.2f} "
        f"{r['Iy_change_pct']:8.2f} "
        f"{r['Iz_change_pct']:8.2f} "
        f"{r['B11_scaled_nominal_stress_sensitivity_MPa']:10.2f} "
        f"{r['MS_7075_yield_on_scaled_sensitivity']:9.3f}"
    )

emit("\n--- WORKING B13C CENTRAL RELIEF ---")
emit(f"Selected working relief:              Ø{WORKING_RELIEF_D:.1f} mm THROUGH")
emit(f"Shaft-to-aluminum radial clearance:    {work['shaft_to_aluminum_radial_clearance_mm']:.2f} mm")
emit(f"Minimum vertical ligament:             {work['minimum_vertical_ligament_mm']:.2f} mm")
emit(f"Side ligament:                         {work['side_ligament_mm']:.2f} mm")
emit(f"Net-area change vs Ø38 bore:           {work['net_area_change_pct']:.2f} %")
emit(f"Iy change vs Ø38 bore:                 {work['Iy_change_pct']:.2f} %")
emit(f"Iz change vs Ø38 bore:                 {work['Iz_change_pct']:.2f} %")
emit(f"B11 scaled nominal stress sensitivity: {work['B11_scaled_nominal_stress_sensitivity_MPa']:.2f} MPa")
emit(f"Yield margin on that sensitivity only: {work['MS_7075_yield_on_scaled_sensitivity']:+.3f}")

emit("\nSELECTION REASON")
emit("- Ø50 through-bore matches the bronze sleeve OD and eliminates exposed Ø38 aluminum.")
emit("- It avoids an internal bore shoulder at the bushing ends.")
emit("- It gives 6 mm radial clearance between the Ø38 shaft and 7075 center passage.")
emit("- Relative to the old Ø38 bore, the centered-section area falls about 11.6%,")
emit("  Iy about 5.0%, and Iz about 2.7%; these are acceptable to TAKE TO FEA, not final approval.")
emit("- The minimum vertical ligament becomes 14 mm, so B13C local head/contact FEA is mandatory.")

emit("\nB13C CAD INTENT")
emit("- Machine/model one Ø50 passage through the head.")
emit("- Install one 30 mm-long flanged bronze bushing from each side.")
emit("- Leave the center 46 mm of the Ø50 passage unoccupied.")
emit("- Shaft is Ø38 nominal; it contacts bronze ID surfaces only, never 7075.")
emit("- Keep the Ø60 x 3 mm flange working geometry from B13B V0.3.")
emit("- Do not add a central keeper hole/keyway through the Ø38 shaft.")
emit("- Mx remains on the independent brace path.")

emit("\nOUTPUT FILES")
emit(f"Trade CSV: {csv_path}")
emit(f"Summary:   {summary_path}")
emit("="*112)

summary_path.write_text("\n".join(lines),encoding="utf-8")
