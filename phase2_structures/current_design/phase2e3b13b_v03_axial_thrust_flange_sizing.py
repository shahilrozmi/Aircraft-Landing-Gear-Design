"""
Landing_Gear_Design_Project
PHASE 2E3-B13B V0.3 — FLANGED-BUSHING AXIAL THRUST-PATH PRELIMINARY SIZING

WHY THIS STEP EXISTS
--------------------
After B13B V0.2, the radial shaft/head load path is:

    7075 head -> bronze bushing -> Ø38 300M shaft -> airframe bearings

However, LC5 also contains an axial force along the trunnion axis (global X).
A plain sleeve bushing does not define a positive head-to-shaft axial load path.

Working architecture added here:
    - two flanged bronze bushings, one inserted from each side of the head
    - each flange seats on the outer 7075 head face
    - the shaft uses an outboard shoulder / thrust washer / positive retention system
    - one flange may conservatively carry the full |Fx| depending on load direction
    - Mx is STILL reacted by the independent brace; no Mx credit is taken here

This script sizes the flange face only at preliminary static level.
It does NOT freeze the final washer/shoulder, flange fillet, lubrication, wear or fatigue.

PROJECT LOAD
------------
LC5 ultimate |Fx| = 13.31064 kN
LC5 limit    |Fx| =  8.87376 kN

BUSHING BASELINE
----------------
Sleeve OD = 50 mm
Sleeve nominal ID = 38 mm
Sleeve length each side = 30 mm

AVAILABLE AXIAL PACKAGE
-----------------------
Current head-face to airframe-bearing inner-edge gap = 9.5 mm per side.

MATERIAL SCREEN
---------------
AMS 4640 preliminary static bearing-capacity screen = 413.685 MPa.
This is used only as a preliminary bronze thrust-face screen.

The 7075 head-face pressure is REPORTED but not compared to tensile yield as if it
were a bearing allowable. Local head-face contact is reserved for B13C/B13D FEA.
"""

from pathlib import Path
import math
import pandas as pd

# =============================================================================
# 1. INPUTS
# =============================================================================

FX_LIMIT_KN = 8.87376
FX_ULT_KN = 13.31064

SHAFT_D_MM = 38.0
SLEEVE_OD_MM = 50.0
SLEEVE_LENGTH_MM = 30.0

HEAD_FACE_TO_BEARING_EDGE_GAP_MM = 9.5

AMS4640_STATIC_BEARING_MPA = 413.685

# Flange candidates. OD must exceed 50 mm to form a positive seat on the head face.
FLANGE_ODS_MM = [52, 54, 56, 58, 60, 62, 64]
FLANGE_THICKNESSES_MM = [2.0, 3.0, 4.0, 5.0]

# NON-CERTIFICATION practical packaging filters.
MIN_HEAD_SEAT_RADIAL_WIDTH_MM = 4.0
MIN_REMAINING_EXTERNAL_GAP_MM = 4.0

# Working candidate for CAD/FEA development.
WORKING_FLANGE_OD_MM = 60.0
WORKING_FLANGE_T_MM = 3.0


# =============================================================================
# 2. FUNCTIONS
# =============================================================================

def annulus_area_mm2(Do_mm, Di_mm):
    return math.pi / 4.0 * (Do_mm**2 - Di_mm**2)


def pressure_mpa(force_kN, area_mm2):
    return force_kN * 1000.0 / area_mm2


def margin(allowable_mpa, demand_mpa):
    return allowable_mpa / demand_mpa - 1.0


# =============================================================================
# 3. SWEEP
# =============================================================================

rows = []

for Df in FLANGE_ODS_MM:
    if Df <= SLEEVE_OD_MM:
        continue

    # Shaft-side thrust contact can act over the bronze annulus surrounding the Ø38 shaft.
    bronze_thrust_area = annulus_area_mm2(Df, SHAFT_D_MM)

    # The 7075 head physically supports the flange only outside the Ø50 sleeve/bore.
    head_seat_area = annulus_area_mm2(Df, SLEEVE_OD_MM)

    radial_seat_width = 0.5 * (Df - SLEEVE_OD_MM)

    p_bronze_limit = pressure_mpa(FX_LIMIT_KN, bronze_thrust_area)
    p_bronze_ult = pressure_mpa(FX_ULT_KN, bronze_thrust_area)

    p_head_limit = pressure_mpa(FX_LIMIT_KN, head_seat_area)
    p_head_ult = pressure_mpa(FX_ULT_KN, head_seat_area)

    ms_bronze_ult = margin(AMS4640_STATIC_BEARING_MPA, p_bronze_ult)

    for tf in FLANGE_THICKNESSES_MM:
        remaining_external_gap = HEAD_FACE_TO_BEARING_EDGE_GAP_MM - tf

        practical_package_pass = all([
            radial_seat_width >= MIN_HEAD_SEAT_RADIAL_WIDTH_MM,
            remaining_external_gap >= MIN_REMAINING_EXTERNAL_GAP_MM,
        ])

        rows.append({
            "flange_OD_mm": Df,
            "flange_thickness_mm": tf,
            "radial_head_seat_width_mm": radial_seat_width,
            "bronze_thrust_area_mm2": bronze_thrust_area,
            "head_seat_area_mm2": head_seat_area,
            "bronze_thrust_p_limit_MPa": p_bronze_limit,
            "bronze_thrust_p_ult_MPa": p_bronze_ult,
            "MS_AMS4640_static_ult": ms_bronze_ult,
            "head_face_p_limit_MPa": p_head_limit,
            "head_face_p_ult_MPa": p_head_ult,
            "head_face_to_bearing_edge_gap_mm": HEAD_FACE_TO_BEARING_EDGE_GAP_MM,
            "remaining_gap_after_flange_mm": remaining_external_gap,
            "practical_package_pass": practical_package_pass,
        })

df = pd.DataFrame(rows)

working = df[
    (df["flange_OD_mm"] == WORKING_FLANGE_OD_MM)
    & (df["flange_thickness_mm"] == WORKING_FLANGE_T_MM)
].iloc[0]


# =============================================================================
# 4. OUTPUT
# =============================================================================

here = Path(__file__).resolve().parent
csv_path = here / "phase2e3b13b_v03_thrust_flange_trade.csv"
summary_path = here / "phase2e3b13b_v03_summary.txt"

df.to_csv(csv_path, index=False)

lines = []

def emit(s=""):
    print(s)
    lines.append(s)

emit("=" * 112)
emit(" PHASE 2E3-B13B V0.3 — FLANGED-BUSHING AXIAL THRUST-PATH PRELIMINARY SIZING")
emit("=" * 112)

emit("\n--- FROZEN / WORKING INPUTS ---")
emit(f"LC5 limit |Fx|:                         {FX_LIMIT_KN:9.5f} kN")
emit(f"LC5 ultimate |Fx|:                      {FX_ULT_KN:9.5f} kN")
emit(f"Shaft / bushing nominal ID:             {SHAFT_D_MM:9.3f} mm")
emit(f"Sleeve OD:                              {SLEEVE_OD_MM:9.3f} mm")
emit(f"Sleeve length each side:                {SLEEVE_LENGTH_MM:9.3f} mm")
emit(f"Head face -> bearing inner edge gap:    {HEAD_FACE_TO_BEARING_EDGE_GAP_MM:9.3f} mm")
emit(f"AMS 4640 preliminary static screen:     {AMS4640_STATIC_BEARING_MPA:9.3f} MPa")

emit("\n--- ARCHITECTURE RULE ---")
emit("One flanged bushing may conservatively carry the full axial |Fx| in either direction.")
emit("Mx remains on the independent brace path; flange/shaft retention is NOT credited for Mx.")

emit("\n--- CANDIDATE TRADE ---")
emit(
    f"{'Df':>5} {'tf':>5} {'seat_w':>8} {'pBr_ult':>10} {'MS_Br':>9} "
    f"{'pAl_ult':>10} {'gap_rem':>9} {'pkg':>6}"
)
emit("-" * 82)

for _, r in df.iterrows():
    emit(
        f"{r['flange_OD_mm']:5.0f} "
        f"{r['flange_thickness_mm']:5.1f} "
        f"{r['radial_head_seat_width_mm']:8.2f} "
        f"{r['bronze_thrust_p_ult_MPa']:10.2f} "
        f"{r['MS_AMS4640_static_ult']:9.3f} "
        f"{r['head_face_p_ult_MPa']:10.2f} "
        f"{r['remaining_gap_after_flange_mm']:9.2f} "
        f"{'PASS' if r['practical_package_pass'] else 'OPEN':>6}"
    )

emit("\n--- WORKING FLANGE FOR B13C CAD/FEA ---")
emit(f"Flange OD:                              {WORKING_FLANGE_OD_MM:9.3f} mm")
emit(f"Flange thickness:                       {WORKING_FLANGE_T_MM:9.3f} mm")
emit(f"Positive radial seat on 7075 face:      {working['radial_head_seat_width_mm']:9.3f} mm")
emit(f"Bronze thrust pressure, ultimate:       {working['bronze_thrust_p_ult_MPa']:9.3f} MPa")
emit(f"Bronze static-screen margin:            {working['MS_AMS4640_static_ult']:+9.3f}")
emit(f"7075 head-face avg pressure, ultimate:  {working['head_face_p_ult_MPa']:9.3f} MPa")
emit(f"Gap remaining before bearing inner edge:{working['remaining_gap_after_flange_mm']:9.3f} mm")

emit("\nSELECTION REASON")
emit("- Static axial thrust pressure is extremely low relative to the preliminary bronze screen.")
emit("- Ø60 gives a 5 mm radial positive seat outside the Ø50 sleeve bore.")
emit("- 3 mm flange thickness leaves 6.5 mm of the current 9.5 mm external gap.")
emit("- Thickness is a PROVISIONAL packaging/FEA starting value; static face pressure does not size it.")
emit("- Flange-root bending, local 7075 face stress, washer detail, wear and fatigue remain for FEA/detail design.")

emit("\n--- RESULTING B13C GEOMETRY INTENT ---")
emit("Per side bronze bushing: sleeve Ø50 OD x Ø38 nominal ID x 30 mm long")
emit("                         integral flange Ø60 OD x 3 mm thick")
emit("Two bushings are inserted from opposite sides of the head.")
emit("The flange is the positive axial seat; the shaft shoulder/thrust washer acts on the bronze flange.")
emit("The center of the head must NOT retain an exposed Ø38 aluminum land that can touch the shaft.")

emit("\n--- IMPORTANT OPEN ITEM FOR CAD ---")
emit("Central shaft clearance/relief diameter is NOT frozen in V0.3.")
emit("For B13C geometry, either keep the full head passage relieved to the Ø50 bushing OD,")
emit("or deliberately size a smaller central relief bore > Ø38 after a clearance/tolerance study.")
emit("Do NOT leave the old Ø38 7075 bore exposed between the two bushings.")

emit("\nOUTPUT FILES")
emit(f"Trade CSV: {csv_path}")
emit(f"Summary:   {summary_path}")
emit("=" * 112)

summary_path.write_text("\n".join(lines), encoding="utf-8")
