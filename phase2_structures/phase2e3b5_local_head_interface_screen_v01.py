from pathlib import Path
import math

import numpy as np
import pandas as pd


# =============================================================================
# LANDING GEAR DESIGN PROJECT
# PHASE 2E3-B5 — 7075 SOLID-HEAD / 300M CROSS-TRUNNION LOCAL SCREEN V0.1
#
# PURPOSE
#   Perform the first explicit local structural screen of the selected
#   Architecture-A interface:
#
#       300M cross-trunnion / through-shaft
#       captured by a locally enlarged 7075-T6 solid upper head.
#
#   Working interface-study candidate from E3-B4:
#
#       support span          = 120 mm
#       300M journal diameter = 36 mm
#       airframe bearing width= 25 mm
#       root-to-root head width = 85 mm
#
#   THIS SCRIPT DOES NOT DEFINE A FINAL FIT OR RETENTION DETAIL.
#
#   It evaluates only source-supported / statically derived local requirements:
#
#   1) LINEAR PROJECTED SHAFT/HEAD CONTACT DISTRIBUTION
#
#      Each half of the head is treated as an engagement length L measured
#      inward from the journal-root face. The shaft enters the head carrying:
#
#          radial shear R
#          journal-root bending moment M_root
#
#      A first-order linear projected contact line load is used:
#
#          q(x) = a + b x      0 <= x <= L
#
#      with exact equilibrium:
#
#          integral(q dx)     = R
#          integral(x q dx)   = M_root
#
#      Hence:
#
#          a = 4R/L - 6M/L^2
#          b = 12M/L^3 - 6R/L^2
#
#      and projected pressure:
#
#          p(x) = q(x) / d
#
#      If either endpoint becomes negative, continuous full-length compressive
#      contact is physically impossible under this linear model and separation
#      / partial contact must be expected.
#
#      IMPORTANT:
#      Comparing peak projected pressure to 7075 yield / UTS is ONLY a material
#      stress proxy. It is NOT a certified bearing/contact allowable.
#
#   2) LOWER-LIGAMENT SHEAR-OUT SCREEN
#
#      The B1 ligament is the radial distance from the shaft surface down to the
#      frozen E2 pressure-closure boundary.
#
#      Each half-head is conservatively idealized as two shear-out planes:
#
#          A_so = 2 * ligament * L
#          tau  = R / A_so
#          sigma_VM,shear = sqrt(3) * tau
#
#      The full radial reaction R is conservatively used, independent of its
#      actual direction, so the lower pressure-boundary ligament is not helped
#      by a favorable provisional load direction.
#
#   3) TRANSVERSE SIDE-LIGAMENT SHEAR-OUT DIAGNOSTIC
#
#      The minimum 74 mm barrel OD is used as a conservative local transverse
#      head envelope:
#
#          side_ligament = (74 - d)/2
#
#      The same full radial R is imposed for a conservative geometric check.
#
#   4) AXIAL-THRUST SHOULDER AREA REQUIREMENT
#
#      The locating-journal thrust Fx must ultimately transfer into the head by
#      a positive feature. A minimum annular projected area is derived from:
#
#          A_req = Fx / allowable
#
#      and converted into the equivalent minimum shoulder OD around the
#      36 mm shaft. This is a requirement only; no shoulder geometry is frozen.
#
#   LIMITATIONS
#   -----------
#   - 7075-T6 project screening values 503 / 572 MPa are retained.
#   - No bearing-direction/orientation knockdowns are available yet.
#   - No fretting, Hertzian contact, interference-fit stress, notch Kt, fatigue,
#     corrosion, tolerance or 3D load redistribution is solved here.
#   - The separate Mx brace lug is NOT included in this local shaft/head screen.
#
# OUTPUTS
#   phase2e3b5_local_head_screen.csv
#   phase2e3b5_contact_distribution.csv
#   phase2e3b5_thrust_requirement.csv
#   phase2e3b5_summary.txt
# =============================================================================


HERE = Path(__file__).resolve().parent

B4_ENVELOPE = HERE / "phase2e3b4_interface_load_envelope.csv"
B4_FAMILY = HERE / "phase2e3b4_120mm_family_comparison.csv"
E2_BASELINE = HERE / "phase2e2_v1_baseline.csv"

OUTPUT_SCREEN = HERE / "phase2e3b5_local_head_screen.csv"
OUTPUT_CONTACT = HERE / "phase2e3b5_contact_distribution.csv"
OUTPUT_THRUST = HERE / "phase2e3b5_thrust_requirement.csv"
OUTPUT_SUMMARY = HERE / "phase2e3b5_summary.txt"


# =============================================================================
# PROJECT-LOCKED PRELIMINARY MATERIAL SCREEN
# =============================================================================

# Existing project baseline.
# These are NOT certification / MMPDS allowables and do not include direction,
# product form, temperature, corrosion, fatigue or fitting factors.
SY_7075_MPa = 503.0
SU_7075_MPa = 572.0


# =============================================================================
# WORKING E3-B4 CANDIDATE — NOT FINAL FREEZE
# =============================================================================

WORKING_SPAN_MM = 120.0
WORKING_JOURNAL_D_MM = 36.0
WORKING_BEARING_WIDTH_MM = 25.0

# Frozen smooth barrel outside diameter from Phase 2E2.
BARREL_OD_MM = 74.0


# =============================================================================
# UTILITIES
# =============================================================================

def read_csv(path):
    if not path.exists():
        raise FileNotFoundError(
            f"Required file not found:\n{path}"
        )

    df = pd.read_csv(
        path,
        encoding="utf-8-sig",
    )

    df.columns = [
        str(col).replace("\ufeff", "").strip()
        for col in df.columns
    ]

    return df


def near(series, value, atol=1e-9):
    return np.isclose(
        pd.to_numeric(
            series,
            errors="coerce",
        ),
        float(value),
        atol=atol,
        rtol=0.0,
    )


def margin(allowable, demand):
    if demand <= 0.0:
        return np.inf

    return (
        allowable
        / demand
        - 1.0
    )


def equivalent_shoulder_od_mm(
    shaft_diameter_mm,
    force_kN,
    allowable_MPa,
):
    """
    Minimum annular OD from uniform projected normal stress:
        A_req = F / sigma_allow
        A_ann = pi/4 (D^2 - d^2)
    """

    A_req_mm2 = (
        force_kN
        * 1000.0
        / allowable_MPa
    )

    D_req_mm = math.sqrt(
        shaft_diameter_mm**2
        + 4.0
        * A_req_mm2
        / math.pi
    )

    return (
        A_req_mm2,
        D_req_mm,
    )


# =============================================================================
# SOURCE DATA
# =============================================================================

envelope = read_csv(
    B4_ENVELOPE
)

family = read_csv(
    B4_FAMILY
)

e2 = read_csv(
    E2_BASELINE
)


required_cols = [
    "journal_diameter_mm",
    "support_span_mm",
    "bearing_width_mm",
    "head_root_to_root_width_mm",
    "half_head_engagement_mm",
    "ligament_mm",
    "station_above_U_mm",
    "level",
    "governing_radial_case",
    "per_journal_radial_reaction_kN",
    "governing_thrust_case",
    "full_locating_journal_thrust_kN",
    "journal_root_bending_moment_kNm",
]

for col in required_cols:
    if col not in envelope.columns:
        raise KeyError(
            f"B4 interface-envelope column missing: {col}"
        )


working = envelope.loc[
    near(
        envelope["journal_diameter_mm"],
        WORKING_JOURNAL_D_MM,
    )
    &
    near(
        envelope["support_span_mm"],
        WORKING_SPAN_MM,
    )
    &
    near(
        envelope["bearing_width_mm"],
        WORKING_BEARING_WIDTH_MM,
    )
].copy()


if working.empty:
    raise ValueError(
        "Could not find the B4 36 mm / 25 mm / 120 mm "
        "working interface-study candidate."
    )


# =============================================================================
# LOCAL SCREENS
# =============================================================================

screen_rows = []
contact_rows = []
thrust_rows = []

for _, row in working.iterrows():

    level = str(
        row["level"]
    ).strip().lower()

    ligament_mm = float(
        row["ligament_mm"]
    )

    diameter_mm = float(
        row["journal_diameter_mm"]
    )

    head_width_mm = float(
        row["head_root_to_root_width_mm"]
    )

    L_mm = float(
        row["half_head_engagement_mm"]
    )

    R_kN = float(
        row["per_journal_radial_reaction_kN"]
    )

    Fx_kN = abs(
        float(
            row["full_locating_journal_thrust_kN"]
        )
    )

    Mroot_kNm = abs(
        float(
            row["journal_root_bending_moment_kNm"]
        )
    )

    if L_mm <= 0.0:
        raise ValueError(
            "Non-positive shaft/head engagement length."
        )

    # -------------------------------------------------------------------------
    # Linear projected contact line load.
    # Work in N and mm so q is N/mm.
    # -------------------------------------------------------------------------

    R_N = (
        R_kN
        * 1000.0
    )

    Mroot_Nmm = (
        Mroot_kNm
        * 1.0e6
    )

    a_N_per_mm = (
        4.0
        * R_N
        / L_mm
        - 6.0
        * Mroot_Nmm
        / L_mm**2
    )

    b_N_per_mm2 = (
        12.0
        * Mroot_Nmm
        / L_mm**3
        - 6.0
        * R_N
        / L_mm**2
    )

    q_root_N_per_mm = (
        a_N_per_mm
    )

    q_inner_N_per_mm = (
        a_N_per_mm
        + b_N_per_mm2
        * L_mm
    )

    full_length_compressive = (
        q_root_N_per_mm >= 0.0
        and q_inner_N_per_mm >= 0.0
    )

    p_root_MPa = (
        q_root_N_per_mm
        / diameter_mm
    )

    p_inner_MPa = (
        q_inner_N_per_mm
        / diameter_mm
    )

    p_peak_MPa = max(
        p_root_MPa,
        p_inner_MPa,
    )

    # Equilibrium audit.
    R_reconstructed_N = (
        a_N_per_mm
        * L_mm
        + b_N_per_mm2
        * L_mm**2
        / 2.0
    )

    M_reconstructed_Nmm = (
        a_N_per_mm
        * L_mm**2
        / 2.0
        + b_N_per_mm2
        * L_mm**3
        / 3.0
    )

    force_residual_N = (
        R_reconstructed_N
        - R_N
    )

    moment_residual_Nmm = (
        M_reconstructed_Nmm
        - Mroot_Nmm
    )

    if max(
        abs(force_residual_N),
        abs(moment_residual_Nmm),
    ) > 1e-6:
        raise AssertionError(
            "Linear contact equilibrium reconstruction failed."
        )

    # -------------------------------------------------------------------------
    # Lower-ligament shear-out.
    # -------------------------------------------------------------------------

    A_lower_shear_mm2 = (
        2.0
        * ligament_mm
        * L_mm
    )

    tau_lower_MPa = (
        R_N
        / A_lower_shear_mm2
    )

    vm_lower_shear_MPa = (
        math.sqrt(3.0)
        * tau_lower_MPa
    )

    # -------------------------------------------------------------------------
    # Side-ligament conservative diagnostic using 74-mm local transverse
    # envelope and the FULL radial reaction.
    # -------------------------------------------------------------------------

    side_ligament_mm = (
        BARREL_OD_MM
        - diameter_mm
    ) / 2.0

    if side_ligament_mm <= 0.0:
        raise ValueError(
            "Journal does not fit inside 74-mm transverse envelope."
        )

    A_side_shear_mm2 = (
        2.0
        * side_ligament_mm
        * L_mm
    )

    tau_side_MPa = (
        R_N
        / A_side_shear_mm2
    )

    vm_side_shear_MPa = (
        math.sqrt(3.0)
        * tau_side_MPa
    )

    # -------------------------------------------------------------------------
    # Level-specific preliminary material screen.
    # -------------------------------------------------------------------------

    if level == "limit":
        allowable_MPa = (
            SY_7075_MPa
        )
        allowable_label = (
            "7075-T6 project yield screen"
        )

    elif level == "ultimate":
        allowable_MPa = (
            SU_7075_MPa
        )
        allowable_label = (
            "7075-T6 project UTS screen"
        )

    else:
        raise ValueError(
            f"Unexpected load level: {level}"
        )

    MS_contact_proxy = margin(
        allowable_MPa,
        p_peak_MPa,
    )

    MS_lower_shear = margin(
        allowable_MPa,
        vm_lower_shear_MPa,
    )

    MS_side_shear = margin(
        allowable_MPa,
        vm_side_shear_MPa,
    )

    # Zero-margin ligament required by the simple two-plane VM shear screen.
    required_ligament_mm = (
        math.sqrt(3.0)
        * R_N
        / (
            2.0
            * L_mm
            * allowable_MPa
        )
    )

    # -------------------------------------------------------------------------
    # Positive thrust-shoulder area requirement.
    # -------------------------------------------------------------------------

    A_thrust_req_mm2, D_thrust_req_mm = (
        equivalent_shoulder_od_mm(
            diameter_mm,
            Fx_kN,
            allowable_MPa,
        )
    )

    thrust_rows.append({
        "level":
            level,
        "ligament_mm":
            ligament_mm,
        "governing_thrust_case":
            row[
                "governing_thrust_case"
            ],
        "shaft_diameter_mm":
            diameter_mm,
        "axial_thrust_kN":
            Fx_kN,
        "screen_allowable_MPa":
            allowable_MPa,
        "minimum_annular_thrust_area_mm2":
            A_thrust_req_mm2,
        "equivalent_minimum_shoulder_OD_mm":
            D_thrust_req_mm,
        "interpretation":
            (
                "Zero-margin uniform projected normal-stress requirement only; "
                "actual thrust-face geometry, contact, Kt and retention remain open."
            ),
    })

    screen_rows.append({
        "level":
            level,
        "ligament_mm":
            ligament_mm,
        "station_above_U_mm":
            row[
                "station_above_U_mm"
            ],

        "governing_radial_case":
            row[
                "governing_radial_case"
            ],
        "radial_reaction_kN":
            R_kN,
        "journal_root_moment_kNm":
            Mroot_kNm,

        "journal_diameter_mm":
            diameter_mm,
        "head_root_to_root_width_mm":
            head_width_mm,
        "half_head_engagement_mm":
            L_mm,

        "contact_q_root_N_per_mm":
            q_root_N_per_mm,
        "contact_q_inner_N_per_mm":
            q_inner_N_per_mm,
        "contact_p_root_MPa":
            p_root_MPa,
        "contact_p_inner_MPa":
            p_inner_MPa,
        "contact_peak_projected_pressure_MPa":
            p_peak_MPa,
        "full_length_linear_contact_compressive":
            full_length_compressive,
        "contact_proxy_allowable_MPa":
            allowable_MPa,
        "contact_proxy_MS":
            MS_contact_proxy,

        "lower_shearout_area_mm2":
            A_lower_shear_mm2,
        "lower_shearout_tau_avg_MPa":
            tau_lower_MPa,
        "lower_shearout_VM_proxy_MPa":
            vm_lower_shear_MPa,
        "lower_shearout_MS":
            MS_lower_shear,
        "zero_margin_required_lower_ligament_mm":
            required_ligament_mm,

        "side_ligament_from_74mm_envelope_mm":
            side_ligament_mm,
        "side_shearout_area_mm2":
            A_side_shear_mm2,
        "side_shearout_tau_avg_MPa":
            tau_side_MPa,
        "side_shearout_VM_proxy_MPa":
            vm_side_shear_MPa,
        "side_shearout_MS":
            MS_side_shear,

        "material_screen_allowable_MPa":
            allowable_MPa,
        "material_screen_label":
            allowable_label,

        "simple_screen_PASS":
            bool(
                full_length_compressive
                and MS_contact_proxy >= 0.0
                and MS_lower_shear >= 0.0
                and MS_side_shear >= 0.0
            ),

        "limitations":
            (
                "Preliminary average/linear stress proxies only; no local Kt, "
                "true bearing allowable, fretting, fatigue, fit stress, "
                "partial-contact elasticity or 3D head redistribution."
            ),
    })

    # -------------------------------------------------------------------------
    # Normalized contact distribution for plotting / later FEA comparison.
    # -------------------------------------------------------------------------

    for xi in np.linspace(
        0.0,
        L_mm,
        51,
    ):
        q = (
            a_N_per_mm
            + b_N_per_mm2
            * xi
        )

        contact_rows.append({
            "level":
                level,
            "ligament_mm":
                ligament_mm,
            "x_from_journal_root_mm":
                xi,
            "q_N_per_mm":
                q,
            "projected_pressure_MPa":
                q / diameter_mm,
        })


screen_df = pd.DataFrame(
    screen_rows
)

contact_df = pd.DataFrame(
    contact_rows
)

thrust_df = pd.DataFrame(
    thrust_rows
)

screen_df.to_csv(
    OUTPUT_SCREEN,
    index=False,
)

contact_df.to_csv(
    OUTPUT_CONTACT,
    index=False,
)

thrust_df.to_csv(
    OUTPUT_THRUST,
    index=False,
)


# =============================================================================
# GOVERNING / DISCRETE LIGAMENT INTERPRETATION
# =============================================================================

def level_rows(level):
    return screen_df.loc[
        screen_df["level"] == level
    ].sort_values(
        "ligament_mm"
    )


limit_df = level_rows(
    "limit"
)

ultimate_df = level_rows(
    "ultimate"
)

passing_ligaments = []

for ligament_mm in sorted(
    screen_df[
        "ligament_mm"
    ].unique()
):
    lim = limit_df.loc[
        near(
            limit_df[
                "ligament_mm"
            ],
            ligament_mm,
        )
    ].iloc[0]

    ult = ultimate_df.loc[
        near(
            ultimate_df[
                "ligament_mm"
            ],
            ligament_mm,
        )
    ].iloc[0]

    if (
        bool(
            lim[
                "simple_screen_PASS"
            ]
        )
        and bool(
            ult[
                "simple_screen_PASS"
            ]
        )
    ):
        passing_ligaments.append(
            float(
                ligament_mm
            )
        )


first_discrete_pass_mm = (
    min(
        passing_ligaments
    )
    if passing_ligaments
    else np.nan
)


# =============================================================================
# CONSOLE REPORT
# =============================================================================

print("=" * 124)
print(
    " PHASE 2E3-B5 — 7075 SOLID-HEAD / 300M CROSS-TRUNNION LOCAL SCREEN V0.1"
)
print("=" * 124)

print("\nWORKING INTERFACE-STUDY CANDIDATE")
print("-" * 124)
print(
    f"Support span:                     {WORKING_SPAN_MM:.1f} mm"
)
print(
    f"300M journal diameter:            {WORKING_JOURNAL_D_MM:.1f} mm"
)
print(
    f"Airframe bearing width:           {WORKING_BEARING_WIDTH_MM:.1f} mm"
)
print(
    f"Head root-to-root width:          {float(working['head_root_to_root_width_mm'].iloc[0]):.1f} mm"
)
print(
    f"Half-head engagement length:      {float(working['half_head_engagement_mm'].iloc[0]):.1f} mm"
)
print(
    f"Minimum transverse envelope:      {BARREL_OD_MM:.1f} mm"
)

print("\n7075-T6 PROJECT SCREEN VALUES")
print("-" * 124)
print(
    f"Yield screen:                     {SY_7075_MPa:.1f} MPa"
)
print(
    f"Ultimate screen:                  {SU_7075_MPa:.1f} MPa"
)
print(
    "These remain preliminary project material screens, NOT certification/bearing allowables."
)

print("\nLOCAL HEAD SCREEN BY LOWER LIGAMENT")
print("-" * 124)
print(
    f"{'Lvl':>5}"
    f"{'Lig':>7}"
    f"{'R':>10}"
    f"{'Mroot':>10}"
    f"{'p_peak':>10}"
    f"{'MS_p*':>9}"
    f"{'VM_so':>10}"
    f"{'MS_so':>9}"
    f"{'lig_req':>10}"
    f"{'PASS':>8}"
)
print("-" * 96)

for _, row in screen_df.sort_values(
    [
        "level",
        "ligament_mm",
    ]
).iterrows():

    print(
        f"{row['level']:>5}"
        f"{row['ligament_mm']:>7.0f}"
        f"{row['radial_reaction_kN']:>10.2f}"
        f"{row['journal_root_moment_kNm']:>10.3f}"
        f"{row['contact_peak_projected_pressure_MPa']:>10.1f}"
        f"{row['contact_proxy_MS']:>9.3f}"
        f"{row['lower_shearout_VM_proxy_MPa']:>10.1f}"
        f"{row['lower_shearout_MS']:>9.3f}"
        f"{row['zero_margin_required_lower_ligament_mm']:>10.2f}"
        f"{str(bool(row['simple_screen_PASS'])):>8}"
    )

print(
    "\n*MS_p compares projected contact-pressure proxy to project yield/UTS. "
    "It is not a true bearing/contact allowable margin."
)

print("\nTRANSVERSE SIDE-LIGAMENT DIAGNOSTIC")
print("-" * 124)

for level in [
    "limit",
    "ultimate",
]:
    subset = screen_df.loc[
        screen_df[
            "level"
        ]
        == level
    ]

    gov = subset.loc[
        subset[
            "side_shearout_MS"
        ].idxmin()
    ]

    print(
        f"{level.capitalize():<10}"
        f" side ligament = {gov['side_ligament_from_74mm_envelope_mm']:.2f} mm, "
        f"VM shear-out proxy = {gov['side_shearout_VM_proxy_MPa']:.1f} MPa, "
        f"MS = {gov['side_shearout_MS']:+.3f}"
    )

print("\nAXIAL THRUST-SHOULDER REQUIREMENT")
print("-" * 124)

# Show highest-station row for each level; thrust itself is expected to be
# independent of ligament/station, but we keep the source envelope explicit.
for level in [
    "limit",
    "ultimate",
]:
    subset = thrust_df.loc[
        thrust_df[
            "level"
        ]
        == level
    ]

    row = subset.iloc[
        -1
    ]

    print(
        f"{level.capitalize():<10}"
        f" Fx = {row['axial_thrust_kN']:.3f} kN, "
        f"A_req = {row['minimum_annular_thrust_area_mm2']:.2f} mm^2, "
        f"equiv shoulder OD >= {row['equivalent_minimum_shoulder_OD_mm']:.3f} mm"
    )

print("\nB5 DISPOSITION")
print("-" * 124)

if np.isfinite(
    first_discrete_pass_mm
):
    print(
        f"First tested ligament passing ALL simple limit/ultimate local screens: "
        f"{first_discrete_pass_mm:.0f} mm"
    )
else:
    print(
        "No tested 5/10/15/20 mm ligament passes all simple screens."
    )

print(
    "Do NOT freeze that ligament yet. This is only a first-order local screen."
)
print(
    "If 5 mm fails or is near-zero-margin while 10+ mm passes, carry 10 mm as the "
    "next practical head-geometry candidate and retain 15/20 mm for FEA sensitivity."
)
print(
    "Next structural step: size the 7075 head/boss transition into the 74-mm barrel "
    "and then define the positive shaft-lock / retention detail."
)

print("\nOUTPUT FILES")
print("-" * 124)
print(
    f"Local head screen:                {OUTPUT_SCREEN}"
)
print(
    f"Contact distribution:             {OUTPUT_CONTACT}"
)
print(
    f"Thrust requirement:               {OUTPUT_THRUST}"
)
print(
    f"Summary:                          {OUTPUT_SUMMARY}"
)


# =============================================================================
# SUMMARY FILE
# =============================================================================

gov_ult = ultimate_df.loc[
    ultimate_df[
        "lower_shearout_MS"
    ].idxmin()
]

summary_lines = [
    "=" * 124,
    " PHASE 2E3-B5 — 7075 SOLID-HEAD / 300M CROSS-TRUNNION LOCAL SCREEN V0.1",
    "=" * 124,
    "",
    "Working candidate:",
    f"  span = {WORKING_SPAN_MM:.1f} mm",
    f"  journal = {WORKING_JOURNAL_D_MM:.1f} mm",
    f"  bearing width = {WORKING_BEARING_WIDTH_MM:.1f} mm",
    f"  half-head engagement = {float(working['half_head_engagement_mm'].iloc[0]):.1f} mm",
    "",
    f"First discrete simple-screen passing ligament = {first_discrete_pass_mm}",
    "",
    "Worst ultimate lower-ligament simple shear-out screen:",
    f"  ligament = {gov_ult['ligament_mm']:.1f} mm",
    f"  VM proxy = {gov_ult['lower_shearout_VM_proxy_MPa']:.6f} MPa",
    f"  MS vs project UTS = {gov_ult['lower_shearout_MS']:+.6f}",
    "",
    "No final 7075 local-head PASS is claimed.",
    "No fit/retention architecture is frozen.",
    "Next: boss-to-barrel transition + positive shaft-lock concept.",
    "=" * 124,
]

OUTPUT_SUMMARY.write_text(
    "\n".join(
        summary_lines
    ),
    encoding="utf-8",
)

print("=" * 124)


if __name__ == "__main__":
    pass
