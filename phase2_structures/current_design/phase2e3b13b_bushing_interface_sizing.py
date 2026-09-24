"""
Landing_Gear_Design_Project
Phase 2E3-B13B — Shaft / Head Bushing Interface Preliminary Sizing V0.1

PURPOSE
-------
Screen a replaceable AMS 4640 nickel-aluminum-bronze bushing concept for the
removable Ø38 mm 300M upper cross-pin.

Architecture:
    7075-T6 head -> bronze bushing -> removable 300M shaft -> airframe bearings

This V0.1 is deliberately a PRELIMINARY bearing/geometry screen.

It DOES:
    - retain the current Ø38 mm shaft as the working pin diameter
    - sweep bushing length and OD
    - compute shaft-side projected bearing pressure
    - compute preliminary AMS 4640 static bearing margin
    - compute housing-side projected pressure as a descriptive quantity
    - report bronze wall thickness, head radial ligament, and central unbushed gap
    - identify a practical working candidate rather than the mathematical minimum

It DOES NOT yet:
    - size the bronze-to-7075 interference fit
    - define final running clearance between shaft and bushing
    - validate 7075 local bearing/net-section/shear-out stress
    - calculate fretting, wear, lubrication life, fatigue, or fracture mechanics
    - replace B13C nonlinear contact FEA

SOURCE / PROJECT BASIS
----------------------
1) Phase 2E3-B2 output:
       AMS 4640 preliminary static bearing screen = 413.685 MPa.
   B2 explicitly treats this as a preliminary static-capacity screen only.

2) Current B12 reaction result:
       left support resultant ~= 166.16 kN.
   B13B V0.1 intentionally uses this as a CONSERVATIVE per-bushing design envelope.
   It is NOT asserted to be the exact physical bushing reaction. B13C contact FEA
   will resolve the actual interface load distribution.

3) Current working geometry:
       shaft nominal diameter = 38 mm
       head OD = 106 mm
   The head OD is a current-CAD working input, not a material allowable.

4) Historical B2 reference:
       150 mm span / 25 mm bearing / Ø32 journal:
       p_ult = 140.8 MPa
   Therefore recovered support reaction:
       R = p*d*L = 140.8*32*25 = 112.64 kN

WORKING SELECTION PHILOSOPHY
----------------------------
Requirement -> equation/constraint -> candidate sweep -> selected value -> reason.

The practical-selection filter in this script is explicitly a packaging/design-judgment
filter, NOT a certification rule:
    - bronze static bearing screen must pass
    - bushing length >= 25 mm
    - bronze radial wall >= 5 mm
    - remaining head radial ligament >= 25 mm

Those geometry thresholds are used only to avoid choosing a mathematical minimum.
"""

from pathlib import Path
import pandas as pd

# =============================================================================
# 1. FROZEN / WORKING INPUTS
# =============================================================================

SHAFT_D_MM = 38.0
HEAD_OD_MM = 106.0  # current CAD working geometry input

# Material / preliminary screen
AMS4640_STATIC_BEARING_MPA = 413.685

# Load basis
B12_CONSERVATIVE_PER_BUSHING_KN = 166.16
B2_REFERENCE_REACTION_KN = 140.8 * 32.0 * 25.0 / 1000.0  # = 112.64 kN

# Candidate geometry
BUSH_LENGTHS_MM = [15, 20, 25, 30, 35]
BUSH_ODS_MM = [44, 46, 48, 50, 52, 54, 56]

# Practical, NON-CERTIFICATION packaging filters
PRACTICAL_MIN_LENGTH_MM = 25.0
PRACTICAL_MIN_WALL_MM = 5.0
PRACTICAL_MIN_HEAD_LIGAMENT_MM = 25.0

# Working candidate chosen for next fit/contact step
WORKING_LENGTH_MM = 30.0
WORKING_OD_MM = 50.0


# =============================================================================
# 2. BASIC FUNCTIONS
# =============================================================================

def projected_bearing_pressure_mpa(force_kN: float, diameter_mm: float, length_mm: float) -> float:
    """
    Average projected bearing pressure:
        p = F / (d L)

    N / mm^2 = MPa
    """
    return force_kN * 1000.0 / (diameter_mm * length_mm)


def margin_of_safety(allowable_mpa: float, demand_mpa: float) -> float:
    return allowable_mpa / demand_mpa - 1.0


def required_length_mm(force_kN: float, diameter_mm: float, capacity_mpa: float) -> float:
    """
    Minimum length from the preliminary projected-bearing-capacity screen only:
        L_req = F / (d p_allow)
    """
    return force_kN * 1000.0 / (diameter_mm * capacity_mpa)


# =============================================================================
# 3. CANDIDATE SWEEP
# =============================================================================

rows = []

for L_mm in BUSH_LENGTHS_MM:
    for OD_mm in BUSH_ODS_MM:
        if OD_mm <= SHAFT_D_MM:
            continue

        wall_mm = 0.5 * (OD_mm - SHAFT_D_MM)
        head_radial_ligament_mm = 0.5 * (HEAD_OD_MM - OD_mm)

        # With two equal bushings inserted from opposite sides.
        central_unbushed_gap_mm = HEAD_OD_MM - 2.0 * L_mm

        p_id_design_mpa = projected_bearing_pressure_mpa(
            B12_CONSERVATIVE_PER_BUSHING_KN,
            SHAFT_D_MM,
            L_mm,
        )
        p_id_ref_mpa = projected_bearing_pressure_mpa(
            B2_REFERENCE_REACTION_KN,
            SHAFT_D_MM,
            L_mm,
        )

        # Descriptive pressure on the bushing OD / 7075 housing interface.
        # Do NOT compare this directly with a 7075 tensile yield value.
        p_od_design_mpa = projected_bearing_pressure_mpa(
            B12_CONSERVATIVE_PER_BUSHING_KN,
            OD_mm,
            L_mm,
        )

        ms_bronze_design = margin_of_safety(
            AMS4640_STATIC_BEARING_MPA,
            p_id_design_mpa,
        )

        static_bearing_pass = ms_bronze_design >= 0.0

        practical_geometry_pass = all([
            L_mm >= PRACTICAL_MIN_LENGTH_MM,
            wall_mm >= PRACTICAL_MIN_WALL_MM,
            head_radial_ligament_mm >= PRACTICAL_MIN_HEAD_LIGAMENT_MM,
            central_unbushed_gap_mm >= 0.0,
        ])

        practical_shortlist = static_bearing_pass and practical_geometry_pass

        rows.append({
            "shaft_d_mm": SHAFT_D_MM,
            "bushing_ID_nominal_mm": SHAFT_D_MM,
            "bushing_OD_mm": OD_mm,
            "bushing_length_each_mm": L_mm,
            "total_bronze_engagement_mm": 2.0 * L_mm,
            "central_unbushed_gap_mm": central_unbushed_gap_mm,
            "bushing_radial_wall_mm": wall_mm,
            "head_radial_ligament_mm": head_radial_ligament_mm,
            "design_load_per_bushing_kN": B12_CONSERVATIVE_PER_BUSHING_KN,
            "B2_reference_reaction_kN": B2_REFERENCE_REACTION_KN,
            "shaft_side_p_design_MPa": p_id_design_mpa,
            "shaft_side_p_B2ref_MPa": p_id_ref_mpa,
            "housing_side_projected_p_design_MPa": p_od_design_mpa,
            "AMS4640_static_screen_MPa": AMS4640_STATIC_BEARING_MPA,
            "MS_AMS4640_static_design": ms_bronze_design,
            "static_bearing_pass": static_bearing_pass,
            "practical_geometry_pass": practical_geometry_pass,
            "practical_shortlist": practical_shortlist,
        })

df = pd.DataFrame(rows)


# =============================================================================
# 4. REQUIRED LENGTHS
# =============================================================================

L_req_design_mm = required_length_mm(
    B12_CONSERVATIVE_PER_BUSHING_KN,
    SHAFT_D_MM,
    AMS4640_STATIC_BEARING_MPA,
)

L_req_B2ref_mm = required_length_mm(
    B2_REFERENCE_REACTION_KN,
    SHAFT_D_MM,
    AMS4640_STATIC_BEARING_MPA,
)


# =============================================================================
# 5. WORKING CANDIDATE
# =============================================================================

working = df[
    (df["bushing_length_each_mm"] == WORKING_LENGTH_MM)
    & (df["bushing_OD_mm"] == WORKING_OD_MM)
].iloc[0]


# =============================================================================
# 6. OUTPUT
# =============================================================================

here = Path(__file__).resolve().parent
csv_path = here / "phase2e3b13b_bushing_trade.csv"
summary_path = here / "phase2e3b13b_summary.txt"

df.to_csv(csv_path, index=False)

lines = []

def emit(s=""):
    print(s)
    lines.append(s)

emit("=" * 108)
emit(" PHASE 2E3-B13B — SHAFT / HEAD BUSHING INTERFACE PRELIMINARY SIZING V0.1")
emit("=" * 108)

emit("\n--- INPUT / ARCHITECTURE BASIS ---")
emit(f"300M shaft nominal diameter:              {SHAFT_D_MM:8.3f} mm")
emit(f"7075 head OD, working CAD input:          {HEAD_OD_MM:8.3f} mm")
emit(f"AMS 4640 static bearing screen:           {AMS4640_STATIC_BEARING_MPA:8.3f} MPa")
emit(f"B2 recovered reference reaction:          {B2_REFERENCE_REACTION_KN:8.3f} kN")
emit(f"B12 conservative per-bushing envelope:    {B12_CONSERVATIVE_PER_BUSHING_KN:8.3f} kN")
emit("Load note: B12 reaction is intentionally used as a conservative per-bushing screen;")
emit("           B13C contact FEA will resolve the actual bushing load distribution.")

emit("\n--- STATIC-BEARING MINIMUM LENGTHS ---")
emit(f"Length required at B2 reference reaction: {L_req_B2ref_mm:8.3f} mm")
emit(f"Length required at B12 envelope:          {L_req_design_mm:8.3f} mm")
emit("Interpretation: static projected bearing capacity alone does NOT control a 25–30 mm bushing length.")

emit("\n--- PRACTICAL SHORTLIST FILTERS (NON-CERTIFICATION / PACKAGING ONLY) ---")
emit(f"Minimum candidate length retained:        {PRACTICAL_MIN_LENGTH_MM:8.3f} mm")
emit(f"Minimum bronze radial wall retained:      {PRACTICAL_MIN_WALL_MM:8.3f} mm")
emit(f"Minimum head radial ligament retained:    {PRACTICAL_MIN_HEAD_LIGAMENT_MM:8.3f} mm")

short = df[df["practical_shortlist"]].copy()
emit("\n--- PRACTICAL SHORTLIST ---")
emit(
    f"{'L':>5} {'OD':>5} {'wall':>7} {'head lig':>9} {'gap':>8} "
    f"{'p_ID':>9} {'MS_brg':>9} {'p_OD':>9}"
)
emit("-" * 76)
for _, r in short.iterrows():
    emit(
        f"{r['bushing_length_each_mm']:5.0f} "
        f"{r['bushing_OD_mm']:5.0f} "
        f"{r['bushing_radial_wall_mm']:7.2f} "
        f"{r['head_radial_ligament_mm']:9.2f} "
        f"{r['central_unbushed_gap_mm']:8.2f} "
        f"{r['shaft_side_p_design_MPa']:9.1f} "
        f"{r['MS_AMS4640_static_design']:9.3f} "
        f"{r['housing_side_projected_p_design_MPa']:9.1f}"
    )

emit("\n--- WORKING CANDIDATE FOR B13B/B13C DEVELOPMENT ---")
emit(f"Nominal shaft / bushing ID:               {SHAFT_D_MM:8.3f} mm")
emit(f"Bushing OD:                               {WORKING_OD_MM:8.3f} mm")
emit(f"Bushing length, each side:                {WORKING_LENGTH_MM:8.3f} mm")
emit(f"Bronze radial wall:                       {working['bushing_radial_wall_mm']:8.3f} mm")
emit(f"Remaining head radial ligament:           {working['head_radial_ligament_mm']:8.3f} mm")
emit(f"Central unbushed gap:                     {working['central_unbushed_gap_mm']:8.3f} mm")
emit(f"Shaft-side projected p @ B12 envelope:    {working['shaft_side_p_design_MPa']:8.3f} MPa")
emit(f"AMS 4640 static bearing MS:               {working['MS_AMS4640_static_design']:+8.3f}")
emit(f"Housing-side projected p, descriptive:    {working['housing_side_projected_p_design_MPa']:8.3f} MPa")

emit("\nSELECTION REASON")
emit("- Ø50 x 30 mm gives a 6 mm bronze wall and 28 mm current-CAD head radial ligament.")
emit("- Its 30 mm length is far above the static-capacity mathematical minimum.")
emit("- It preserves a practical, round geometry for the next interference-fit/contact study.")
emit("- This is a WORKING candidate, not a final certified bushing dimension.")

emit("\n--- OPEN ITEMS BEFORE GEOMETRY FREEZE ---")
emit("1. Bronze-to-7075 interference/retention fit: DEFERRED to B13B V0.2.")
emit("2. Shaft-to-bushing running clearance:       TBD from fit/lubrication/wear basis.")
emit("3. 7075 bearing/net-section/shear-out:        requires local head mechanics / FEA.")
emit("4. Fretting, wear, lubrication, fatigue:      OPEN.")
emit("5. Actual bushing reaction split:             resolve in B13C nonlinear contact FEA.")

emit("\nOUTPUT FILES")
emit(f"Full candidate sweep: {csv_path}")
emit(f"Summary:              {summary_path}")
emit("=" * 108)

summary_path.write_text("\n".join(lines), encoding="utf-8")
