from pathlib import Path
import io
import math
import runpy
from contextlib import redirect_stdout

import numpy as np
import pandas as pd


# =============================================================================
# LANDING GEAR DESIGN PROJECT
# PHASE 2E3-B8 — LOCAL TRANSITION FEA LOAD-CASE / SUBMODEL PACKAGE V0.1
#
# PURPOSE
#   Convert the B7B primary transition geometry into a solver-ready engineering
#   load package for the first geometry-specific local stress analysis.
#
#   PRIMARY GEOMETRY FROM B7B:
#
#       74/64 mm lower barrel
#       -> 106/64 mm upper annulus
#       smoothstep taper start = 275 mm above A
#       taper end / E2 closure = 973.780357 mm above A
#
#   B7B showed the artificial Kt-sensitivity capacity is ~1.64, but this is NOT
#   a geometry-derived stress concentration. The next useful result must come
#   from the explicit geometry.
#
# SUBMODEL STRATEGY
#   The transition's previous governing region is near A = 375 mm.
#
#   To keep solver size reasonable while keeping remote boundaries several
#   diameters from the governing transition region, this package defines:
#
#       model bottom = floor(gov_z - 3*D_top, 10 mm)
#       model top    = ceil (gov_z + 3*D_top, 10 mm)
#
#   then clips those bounds to:
#
#       bottom >= 0 mm
#       top <= E2 pressure-closure outer face
#
#   For the present geometry this should place the boundary conditions well away
#   from the expected local peak.
#
# LOAD APPLICATION CONCEPT
#   The local model is a full 3D hollow body.
#
#   At the TOP cut face:
#       - use a remote/pilot point at the section center,
#       - distribute the six STRUCTURAL section resultants:
#             Fx, Fy, Fz, Mx, My, Mz
#       - add CLOSED-END pressure thrust:
#             Fp = p * (pi/4) * ID^2
#         in +z at the same remote point.
#
#   On the internal 64 mm bore:
#       - apply the differential pressure p radially.
#
#   At the BOTTOM cut face:
#       - use a fixed support for the first local run.
#
#   The fixed and remote faces are intentionally far from the target region.
#   If the peak moves to either boundary, the model must be extended.
#
# IMPORTANT INTERPRETATION
#   For combined loading, the ratio:
#
#       peak_FEA_von_Mises / nominal_von_Mises
#
#   is best called a LOCAL VM AMPLIFICATION FACTOR, not a classical elastic Kt.
#   Classical Kt is load/stress-component specific.
#
# OUTPUTS
#   phase2e3b8_fea_load_cards.csv
#   phase2e3b8_case_ranking.csv
#   phase2e3b8_submodel_profile.csv
#   phase2e3b8_nominal_reference.csv
#   phase2e3b8_ansys_setup.txt
#   phase2e3b8_summary.txt
# =============================================================================


HERE = Path(__file__).resolve().parent

B5B_PY = HERE / "phase2e3b5b_upper_barrel_reinforcement_profile_v01.py"
B7B_CANDIDATES = HERE / "phase2e3b7b_candidate_summary.csv"
B7B_GOV = HERE / "phase2e3b7b_profile_governing_points.csv"
B6_WORKING = HERE / "phase2e3b6_working_candidate_record.csv"

OUTPUT_LOADS = HERE / "phase2e3b8_fea_load_cards.csv"
OUTPUT_RANKING = HERE / "phase2e3b8_case_ranking.csv"
OUTPUT_PROFILE = HERE / "phase2e3b8_submodel_profile.csv"
OUTPUT_NOMINAL = HERE / "phase2e3b8_nominal_reference.csv"
OUTPUT_SETUP = HERE / "phase2e3b8_ansys_setup.txt"
OUTPUT_SUMMARY = HERE / "phase2e3b8_summary.txt"


# =============================================================================
# SETTINGS
# =============================================================================

PRIMARY_CANDIDATE_NAME = "PRIMARY_106"

PROFILE_EXPORT_STEP_MM = 5.0

BOUNDARY_DISTANCE_DIAMETERS = 3.0

# Suggested initial mesh targets only.
# These are mesh-study starting values, NOT frozen validation settings.
LOCAL_MESH_INITIAL_MM = 2.0
LOCAL_MESH_REFINED_MM = 1.0
REMOTE_MESH_MM = 6.0


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


def smoothstep(s):
    s = max(
        0.0,
        min(
            1.0,
            float(s),
        ),
    )

    return (
        3.0 * s**2
        - 2.0 * s**3
    )


def profile_OD_mm(
    zA_mm,
    start_A_mm,
    end_A_mm,
    lower_OD_mm,
    upper_OD_mm,
):
    if zA_mm <= start_A_mm:
        return lower_OD_mm

    if zA_mm >= end_A_mm:
        return upper_OD_mm

    s = (
        zA_mm
        - start_A_mm
    ) / (
        end_A_mm
        - start_A_mm
    )

    return (
        lower_OD_mm
        + (
            upper_OD_mm
            - lower_OD_mm
        )
        * smoothstep(
            s
        )
    )


def round_down(
    value,
    increment,
):
    return (
        math.floor(
            value / increment
        )
        * increment
    )


def round_up(
    value,
    increment,
):
    return (
        math.ceil(
            value / increment
        )
        * increment
    )


def annulus_area_m2(
    OD_mm,
    ID_mm,
):
    Do = OD_mm / 1000.0
    Di = ID_mm / 1000.0

    return (
        math.pi
        / 4.0
        * (
            Do**2
            - Di**2
        )
    )


def annulus_I_m4(
    OD_mm,
    ID_mm,
):
    Do = OD_mm / 1000.0
    Di = ID_mm / 1000.0

    return (
        math.pi
        / 64.0
        * (
            Do**4
            - Di**4
        )
    )


def annulus_J_m4(
    OD_mm,
    ID_mm,
):
    return (
        2.0
        * annulus_I_m4(
            OD_mm,
            ID_mm,
        )
    )


def pressure_thrust_kN(
    pressure_MPa,
    ID_mm,
):
    area_m2 = (
        math.pi
        / 4.0
        * (
            ID_mm
            / 1000.0
        )**2
    )

    return (
        pressure_MPa
        * 1e6
        * area_m2
        / 1000.0
    )


# =============================================================================
# LOAD AUTHORITATIVE B5B MECHANICS / SOURCES
# =============================================================================

if not B5B_PY.exists():
    raise FileNotFoundError(
        f"Required B5B source not found:\n{B5B_PY}"
    )

with redirect_stdout(
    io.StringIO()
):
    b5b = runpy.run_path(
        str(B5B_PY),
        run_name="phase2e3b5b_reuse_for_b8",
    )


required = [
    "resultants_at_h",
    "annular_combined_vm_MPa",
    "loads",
    "case_col",
    "limit_cols",
    "ultimate_cols",
    "barrel_ID_mm",
    "h_UA_static_m",
    "P_LIMIT_DIFF_MPa",
    "P_ULT_DIFF_MPa",
    "SY_7075_MPa",
    "SU_7075_MPa",
]

missing = [
    name
    for name in required
    if name not in b5b
]

if missing:
    raise KeyError(
        "B5B source did not expose required items: "
        + ", ".join(
            missing
        )
    )


resultants_at_h = b5b[
    "resultants_at_h"
]

annular_combined_vm_MPa = b5b[
    "annular_combined_vm_MPa"
]

loads = b5b[
    "loads"
]

case_col = b5b[
    "case_col"
]

limit_cols = b5b[
    "limit_cols"
]

ultimate_cols = b5b[
    "ultimate_cols"
]

BARREL_ID_MM = float(
    b5b[
        "barrel_ID_mm"
    ]
)

h_UA_static_m = float(
    b5b[
        "h_UA_static_m"
    ]
)

P_LIMIT_DIFF_MPa = float(
    b5b[
        "P_LIMIT_DIFF_MPa"
    ]
)

P_ULT_DIFF_MPa = float(
    b5b[
        "P_ULT_DIFF_MPa"
    ]
)

SY_7075_MPa = float(
    b5b[
        "SY_7075_MPa"
    ]
)

SU_7075_MPa = float(
    b5b[
        "SU_7075_MPa"
    ]
)


# =============================================================================
# PRIMARY GEOMETRY
# =============================================================================

candidate_df = read_csv(
    B7B_CANDIDATES
)

primary_rows = candidate_df.loc[
    candidate_df[
        "candidate"
    ].astype(str)
    == PRIMARY_CANDIDATE_NAME
]

if len(
    primary_rows
) != 1:
    raise ValueError(
        f"Expected one {PRIMARY_CANDIDATE_NAME} row; found {len(primary_rows)}."
    )

primary = primary_rows.iloc[
    0
]

LOWER_OD_MM = float(
    primary[
        "lower_OD_mm"
    ]
)

UPPER_OD_MM = float(
    primary[
        "upper_OD_mm"
    ]
)

TAPER_START_A_MM = float(
    primary[
        "taper_start_A_mm"
    ]
)

TAPER_END_A_MM = float(
    primary[
        "taper_end_A_mm"
    ]
)

B7A_KT_CAPACITY = float(
    primary[
        "B7A_Kt_peak_capacity"
    ]
)


b6 = read_csv(
    B6_WORKING
)

if b6.empty:
    raise ValueError(
        "B6 working candidate record is empty."
    )

TRUNNION_D_MM = float(
    b6.iloc[
        0
    ][
        "journal_diameter_mm"
    ]
)


# =============================================================================
# PREVIOUS GOVERNING STATION -> SUBMODEL BOUNDS
# =============================================================================

gov_df = read_csv(
    B7B_GOV
)

gov_row = gov_df.loc[
    (
        gov_df[
            "candidate"
        ].astype(str)
        == PRIMARY_CANDIDATE_NAME
    )
    &
    (
        gov_df[
            "Kt_case"
        ].astype(str)
        == "AT_B7A_KT_CAPACITY"
    )
    &
    (
        gov_df[
            "level"
        ].astype(str)
        == "ultimate"
    )
]

if len(
    gov_row
) != 1:
    raise ValueError(
        "Could not uniquely identify B7B primary ultimate capacity-governing point."
    )

gov_row = gov_row.iloc[
    0
]

TARGET_STATION_A_MM = float(
    gov_row[
        "station_A_mm"
    ]
)

TARGET_OD_MM = float(
    gov_row[
        "local_OD_mm"
    ]
)


boundary_distance_mm = (
    BOUNDARY_DISTANCE_DIAMETERS
    * UPPER_OD_MM
)

MODEL_BOTTOM_A_MM = max(
    0.0,
    round_down(
        TARGET_STATION_A_MM
        - boundary_distance_mm,
        10.0,
    ),
)

MODEL_TOP_A_MM = min(
    TAPER_END_A_MM,
    round_up(
        TARGET_STATION_A_MM
        + boundary_distance_mm,
        10.0,
    ),
)

distance_target_to_bottom_mm = (
    TARGET_STATION_A_MM
    - MODEL_BOTTOM_A_MM
)

distance_target_to_top_mm = (
    MODEL_TOP_A_MM
    - TARGET_STATION_A_MM
)


# =============================================================================
# SUBMODEL PROFILE EXPORT
# =============================================================================

z_profile = np.arange(
    MODEL_BOTTOM_A_MM,
    MODEL_TOP_A_MM,
    PROFILE_EXPORT_STEP_MM,
).tolist()

if (
    not z_profile
    or abs(
        z_profile[
            -1
        ]
        - MODEL_TOP_A_MM
    ) > 1e-12
):
    z_profile.append(
        MODEL_TOP_A_MM
    )


profile_rows = []

for zA_mm in z_profile:

    OD_mm = profile_OD_mm(
        zA_mm,
        TAPER_START_A_MM,
        TAPER_END_A_MM,
        LOWER_OD_MM,
        UPPER_OD_MM,
    )

    profile_rows.append({
        "station_A_mm":
            zA_mm,
        "station_U_mm":
            zA_mm
            - h_UA_static_m
            * 1000.0,
        "outer_diameter_mm":
            OD_mm,
        "outer_radius_mm":
            OD_mm
            / 2.0,
        "inner_diameter_mm":
            BARREL_ID_MM,
        "inner_radius_mm":
            BARREL_ID_MM
            / 2.0,
        "is_below_taper":
            zA_mm
            <= TAPER_START_A_MM,
        "is_in_taper":
            (
                zA_mm
                > TAPER_START_A_MM
                and zA_mm
                < TAPER_END_A_MM
            ),
    })


profile_df = pd.DataFrame(
    profile_rows
)

profile_df.to_csv(
    OUTPUT_PROFILE,
    index=False,
)


# =============================================================================
# LOAD CARDS AT SUBMODEL TOP
# =============================================================================

load_card_rows = []

for (
    level,
    cols,
    pressure_MPa,
    allowable_MPa,
) in [
    (
        "limit",
        limit_cols,
        P_LIMIT_DIFF_MPa,
        SY_7075_MPa,
    ),
    (
        "ultimate",
        ultimate_cols,
        P_ULT_DIFF_MPa,
        SU_7075_MPa,
    ),
]:

    F_pressure_kN = pressure_thrust_kN(
        pressure_MPa,
        BARREL_ID_MM,
    )

    for _, load in loads.iterrows():

        res = resultants_at_h(
            float(
                load[
                    cols[
                        "Fx"
                    ]
                ]
            ),
            float(
                load[
                    cols[
                        "Fy"
                    ]
                ]
            ),
            float(
                load[
                    cols[
                        "Fz"
                    ]
                ]
            ),
            MODEL_TOP_A_MM,
        )

        load_card_rows.append({
            "level":
                level,
            "case":
                str(
                    load[
                        case_col
                    ]
                ),
            "application_station_A_mm":
                MODEL_TOP_A_MM,
            "application_outer_OD_mm":
                profile_OD_mm(
                    MODEL_TOP_A_MM,
                    TAPER_START_A_MM,
                    TAPER_END_A_MM,
                    LOWER_OD_MM,
                    UPPER_OD_MM,
                ),
            "application_inner_ID_mm":
                BARREL_ID_MM,

            "structural_Fx_kN":
                res[
                    "Fx_kN"
                ],
            "structural_Fy_kN":
                res[
                    "Fy_kN"
                ],
            "structural_Fz_kN":
                res[
                    "Fz_kN"
                ],

            "Mx_kNm":
                res[
                    "Mx_kNm"
                ],
            "My_kNm":
                res[
                    "My_kNm"
                ],
            "Mz_kNm":
                res[
                    "Mz_kNm"
                ],

            "internal_pressure_MPa":
                pressure_MPa,
            "closed_end_pressure_thrust_kN_plus_z":
                F_pressure_kN,

            "remote_total_Fz_kN_if_pressure_thrust_added":
                res[
                    "Fz_kN"
                ]
                + F_pressure_kN,

            "material_screen_allowable_MPa":
                allowable_MPa,
        })


load_cards_df = pd.DataFrame(
    load_card_rows
)

load_cards_df.to_csv(
    OUTPUT_LOADS,
    index=False,
)


# =============================================================================
# NOMINAL REFERENCE / CASE RANKING AT TARGET STATION
# =============================================================================

nominal_rows = []

target_OD_mm = profile_OD_mm(
    TARGET_STATION_A_MM,
    TAPER_START_A_MM,
    TAPER_END_A_MM,
    LOWER_OD_MM,
    UPPER_OD_MM,
)

for (
    level,
    cols,
    pressure_MPa,
    allowable_MPa,
) in [
    (
        "limit",
        limit_cols,
        P_LIMIT_DIFF_MPa,
        SY_7075_MPa,
    ),
    (
        "ultimate",
        ultimate_cols,
        P_ULT_DIFF_MPa,
        SU_7075_MPa,
    ),
]:

    for _, load in loads.iterrows():

        res = resultants_at_h(
            float(
                load[
                    cols[
                        "Fx"
                    ]
                ]
            ),
            float(
                load[
                    cols[
                        "Fy"
                    ]
                ]
            ),
            float(
                load[
                    cols[
                        "Fz"
                    ]
                ]
            ),
            TARGET_STATION_A_MM,
        )

        stress = annular_combined_vm_MPa(
            res,
            target_OD_mm,
            BARREL_ID_MM,
            pressure_MPa,
            1.0,
        )

        nominal_rows.append({
            "level":
                level,
            "case":
                str(
                    load[
                        case_col
                    ]
                ),
            "reference_station_A_mm":
                TARGET_STATION_A_MM,
            "reference_OD_mm":
                target_OD_mm,
            "reference_ID_mm":
                BARREL_ID_MM,
            "pressure_MPa":
                pressure_MPa,

            "Fx_kN":
                res[
                    "Fx_kN"
                ],
            "Fy_kN":
                res[
                    "Fy_kN"
                ],
            "Fz_kN":
                res[
                    "Fz_kN"
                ],
            "Mx_kNm":
                res[
                    "Mx_kNm"
                ],
            "My_kNm":
                res[
                    "My_kNm"
                ],
            "Mz_kNm":
                res[
                    "Mz_kNm"
                ],
            "Mb_kNm":
                res[
                    "Mb_kNm"
                ],

            "nominal_Kt1_surface":
                stress[
                    "surface"
                ],
            "nominal_Kt1_sigma_z_MPa":
                stress[
                    "sigma_z_MPa"
                ],
            "nominal_Kt1_sigma_theta_MPa":
                stress[
                    "sigma_theta_MPa"
                ],
            "nominal_Kt1_sigma_r_MPa":
                stress[
                    "sigma_r_MPa"
                ],
            "nominal_Kt1_tau_torsion_MPa":
                stress[
                    "tau_torsion_MPa"
                ],
            "nominal_Kt1_VM_MPa":
                stress[
                    "vm_MPa"
                ],

            "allowable_MPa":
                allowable_MPa,
            "nominal_Kt1_MS":
                (
                    allowable_MPa
                    / stress[
                        "vm_MPa"
                    ]
                    - 1.0
                ),
        })


nominal_df = pd.DataFrame(
    nominal_rows
)

nominal_df.to_csv(
    OUTPUT_NOMINAL,
    index=False,
)


ranking_rows = []

for level in [
    "limit",
    "ultimate",
]:

    sub = nominal_df.loc[
        nominal_df[
            "level"
        ]
        == level
    ].sort_values(
        "nominal_Kt1_VM_MPa",
        ascending=False,
    ).reset_index(
        drop=True
    )

    for i, row in sub.iterrows():
        ranking_rows.append({
            "level":
                level,
            "rank":
                i + 1,
            "case":
                row[
                    "case"
                ],
            "nominal_Kt1_VM_MPa":
                row[
                    "nominal_Kt1_VM_MPa"
                ],
            "nominal_Kt1_MS":
                row[
                    "nominal_Kt1_MS"
                ],
            "Mb_kNm":
                row[
                    "Mb_kNm"
                ],
            "Mz_kNm":
                row[
                    "Mz_kNm"
                ],
        })


ranking_df = pd.DataFrame(
    ranking_rows
)

ranking_df.to_csv(
    OUTPUT_RANKING,
    index=False,
)


# =============================================================================
# ANSYS SETUP NOTE
# =============================================================================

top_OD_mm = profile_OD_mm(
    MODEL_TOP_A_MM,
    TAPER_START_A_MM,
    TAPER_END_A_MM,
    LOWER_OD_MM,
    UPPER_OD_MM,
)

wall_at_target_mm = (
    target_OD_mm
    - BARREL_ID_MM
) / 2.0

wall_at_top_mm = (
    top_OD_mm
    - BARREL_ID_MM
) / 2.0

ultimate_rank = ranking_df.loc[
    ranking_df[
        "level"
    ]
    == "ultimate"
].sort_values(
    "rank"
)

top_three_ultimate = ultimate_rank.head(
    3
)


setup_lines = [
    "=" * 124,
    " PHASE 2E3-B8 — ANSYS LOCAL TRANSITION SUBMODEL SETUP V0.1",
    "=" * 124,
    "",
    "MODEL GEOMETRY",
    "-" * 124,
    f"Primary profile:                 74/{BARREL_ID_MM:.0f} -> {UPPER_OD_MM:.0f}/{BARREL_ID_MM:.0f} mm",
    f"Full taper start:                {TAPER_START_A_MM:.3f} mm above A",
    f"Full taper end / E2 closure:     {TAPER_END_A_MM:.6f} mm above A",
    f"Local model bottom:              {MODEL_BOTTOM_A_MM:.3f} mm above A",
    f"Local model top:                 {MODEL_TOP_A_MM:.3f} mm above A",
    f"Target/reference station:        {TARGET_STATION_A_MM:.3f} mm above A",
    f"Target OD / wall:                {target_OD_mm:.3f} mm / {wall_at_target_mm:.3f} mm",
    f"Top OD / wall:                   {top_OD_mm:.3f} mm / {wall_at_top_mm:.3f} mm",
    f"Distance target -> bottom:       {distance_target_to_bottom_mm:.3f} mm",
    f"Distance target -> top:          {distance_target_to_top_mm:.3f} mm",
    "",
    "COORDINATE SYSTEM",
    "-" * 124,
    "+x forward",
    "+y inboard",
    "+z upward along the strut/barrel axis",
    "",
    "MATERIAL",
    "-" * 124,
    "7075-T6 project elastic baseline:",
    "  E  = 71.7 GPa",
    "  nu = 0.33",
    f"Preliminary yield / ultimate screens = {SY_7075_MPa:.1f} / {SU_7075_MPa:.1f} MPa",
    "Use linear elastic material for this local Kt/amplification study.",
    "",
    "BOUNDARY CONDITIONS",
    "-" * 124,
    "Bottom cut face:",
    "  Fixed Support for the first local run.",
    "",
    "Top cut face:",
    "  Remote point at section center.",
    "  Use deformable/distributed coupling if available; avoid a locally rigid face if possible.",
    "  Apply the six structural section resultants from phase2e3b8_fea_load_cards.csv.",
    "  Add the listed closed-end pressure thrust to +Fz at the remote point.",
    "",
    "Inner 64-mm bore:",
    "  Apply the corresponding differential pressure over the complete internal bore of the local model.",
    "",
    "Pressure caution:",
    "  Do NOT both model an explicit pressurized end-cap and also add the equivalent pressure thrust.",
    "  The B8 load card assumes NO explicit end-cap in the local cut model.",
    "",
    "INITIAL MESH PLAN",
    "-" * 124,
    f"Remote/coarse body sizing target: about {REMOTE_MESH_MM:.1f} mm.",
    f"Local transition sizing first run: about {LOCAL_MESH_INITIAL_MM:.1f} mm.",
    f"Refined comparison run:           about {LOCAL_MESH_REFINED_MM:.1f} mm.",
    (
        "At the thin-wall governing region (~"
        f"{wall_at_target_mm:.2f} mm wall), aim for multiple quadratic-element "
        "layers through thickness."
    ),
    "Use quadratic solid elements if available.",
    "",
    "MESH-CONVERGENCE RULE",
    "-" * 124,
    "At minimum compare three successively refined local meshes.",
    "Track:",
    "  1. peak von Mises stress in the smooth transition region,",
    "  2. nominal von Mises stress away from the local peak,",
    "  3. peak location,",
    "  4. total deformation / reaction equilibrium.",
    (
        "Treat a moving/diverging peak at a constraint, remote coupling edge, "
        "or geometric singularity as a modelling artifact until resolved."
    ),
    "",
    "POST-PROCESSING TERMINOLOGY",
    "-" * 124,
    (
        "For combined loading, report peak von Mises directly against the "
        "preliminary material screen."
    ),
    (
        "If you calculate peak_VM / nominal_VM, call it K_VM or local VM "
        "amplification, not classical Kt."
    ),
    (
        "For a classical Kt, compare a specific stress component under a "
        "specific load mode to its corresponding nominal component."
    ),
    "",
    "FIRST FEA CASES TO RUN",
    "-" * 124,
]

for _, row in top_three_ultimate.iterrows():
    setup_lines.append(
        f"  Ultimate rank {int(row['rank'])}: {row['case']}  "
        f"nominal VM={row['nominal_Kt1_VM_MPa']:.3f} MPa, "
        f"Mb={row['Mb_kNm']:.3f} kN*m, Mz={row['Mz_kNm']:.3f} kN*m"
    )

setup_lines.extend([
    "",
    "ACCEPTANCE FOR THIS LOCAL STUDY",
    "-" * 124,
    (
        "No certification claim is made. For the preliminary static screen, "
        "compare LIMIT peak elastic VM to the 503 MPa project yield screen and "
        "ULTIMATE peak elastic VM to the 572 MPa project ultimate screen."
    ),
    (
        "If the real primary geometry does not provide adequate margin, revise "
        "the profile/radius/head envelope and rerun. Do not force-fit the old "
        "arbitrary Kt>=2 sensitivity gate."
    ),
    "",
    "OPEN ITEMS NOT SOLVED BY THIS SUBMODEL",
    "-" * 124,
    "Pressure-closure plate/retainer local stress",
    "Trunnion transverse hole and positive shaft-lock detail",
    "Steel/aluminum fretting/contact",
    "Fatigue / spectrum / crack initiation",
    "Corrosion / surface treatment",
    "Fits / tolerances",
    "Final certification allowables and fitting factors",
    "=" * 124,
])

OUTPUT_SETUP.write_text(
    "\n".join(
        setup_lines
    ),
    encoding="utf-8",
)


# =============================================================================
# CONSOLE REPORT
# =============================================================================

print("=" * 124)
print(
    " PHASE 2E3-B8 — LOCAL TRANSITION FEA LOAD-CASE / SUBMODEL PACKAGE V0.1"
)
print("=" * 124)

print("\nPRIMARY GEOMETRY")
print("-" * 124)
print(
    f"Barrel transition:                {LOWER_OD_MM:.1f}/{BARREL_ID_MM:.1f}"
    f" -> {UPPER_OD_MM:.1f}/{BARREL_ID_MM:.1f} mm"
)
print(
    f"Full taper start / end:           {TAPER_START_A_MM:.1f} / "
    f"{TAPER_END_A_MM:.3f} mm above A"
)
print(
    f"B7A sensitivity Kt capacity:      {B7A_KT_CAPACITY:.3f} "
    f"(NOT geometry-derived)"
)

print("\nLOCAL SUBMODEL")
print("-" * 124)
print(
    f"Previous target station:          {TARGET_STATION_A_MM:.1f} mm above A"
)
print(
    f"Local model bottom / top:         {MODEL_BOTTOM_A_MM:.1f} / "
    f"{MODEL_TOP_A_MM:.1f} mm above A"
)
print(
    f"Target distance to boundaries:    {distance_target_to_bottom_mm:.1f} / "
    f"{distance_target_to_top_mm:.1f} mm"
)
print(
    f"Target OD / wall:                 {target_OD_mm:.2f} / "
    f"{wall_at_target_mm:.2f} mm"
)
print(
    f"Top cut OD / wall:                {top_OD_mm:.2f} / "
    f"{wall_at_top_mm:.2f} mm"
)

print("\nPRESSURE LOADS")
print("-" * 124)
print(
    f"Limit differential pressure:      {P_LIMIT_DIFF_MPa:.3f} MPa"
)
print(
    f"Limit closed-end thrust:          "
    f"{pressure_thrust_kN(P_LIMIT_DIFF_MPa, BARREL_ID_MM):.3f} kN"
)
print(
    f"Ultimate differential pressure:   {P_ULT_DIFF_MPa:.3f} MPa"
)
print(
    f"Ultimate closed-end thrust:       "
    f"{pressure_thrust_kN(P_ULT_DIFF_MPa, BARREL_ID_MM):.3f} kN"
)

print("\nNOMINAL CASE RANKING AT TARGET STATION")
print("-" * 124)
print(
    f"{'Lvl':>9}"
    f"{'Rank':>7}"
    f"{'Case':>10}"
    f"{'VM Kt1':>12}"
    f"{'MS':>10}"
    f"{'Mb':>10}"
    f"{'Mz':>10}"
)
print("-" * 72)

for _, row in ranking_df.loc[
    ranking_df[
        "rank"
    ] <= 4
].iterrows():

    print(
        f"{row['level']:>9}"
        f"{int(row['rank']):>7}"
        f"{str(row['case']):>10}"
        f"{row['nominal_Kt1_VM_MPa']:>12.1f}"
        f"{row['nominal_Kt1_MS']:>10.3f}"
        f"{row['Mb_kNm']:>10.3f}"
        f"{row['Mz_kNm']:>10.3f}"
    )

print("\nB8 DISPOSITION")
print("-" * 124)
print(
    "The primary 106/64 profile is now packaged for geometry-specific local FEA."
)
print(
    "Run LC4+ ultimate first, then the next ranked ultimate cases, followed by the corresponding limit cases."
)
print(
    "Use the explicit pressure thrust in the load card only when the local model does NOT include a pressurized end-cap."
)
print(
    "The result we need next is the mesh-converged local peak stress and its location — not another assumed Kt."
)

print("\nOUTPUT FILES")
print("-" * 124)
print(
    f"FEA load cards:                   {OUTPUT_LOADS}"
)
print(
    f"Case ranking:                     {OUTPUT_RANKING}"
)
print(
    f"Submodel profile:                 {OUTPUT_PROFILE}"
)
print(
    f"Nominal reference:                {OUTPUT_NOMINAL}"
)
print(
    f"ANSYS setup note:                 {OUTPUT_SETUP}"
)
print(
    f"Summary:                          {OUTPUT_SUMMARY}"
)


summary_lines = [
    "=" * 124,
    " PHASE 2E3-B8 — LOCAL TRANSITION FEA LOAD-CASE / SUBMODEL PACKAGE V0.1",
    "=" * 124,
    "",
    f"Primary profile: {LOWER_OD_MM:.1f}/{BARREL_ID_MM:.1f} -> "
    f"{UPPER_OD_MM:.1f}/{BARREL_ID_MM:.1f} mm",
    f"Submodel: A={MODEL_BOTTOM_A_MM:.1f} to {MODEL_TOP_A_MM:.1f} mm",
    f"Target station: A={TARGET_STATION_A_MM:.1f} mm",
    f"Target OD/wall: {target_OD_mm:.6f}/{wall_at_target_mm:.6f} mm",
    "",
    f"Limit pressure thrust: "
    f"{pressure_thrust_kN(P_LIMIT_DIFF_MPa, BARREL_ID_MM):.6f} kN",
    f"Ultimate pressure thrust: "
    f"{pressure_thrust_kN(P_ULT_DIFF_MPa, BARREL_ID_MM):.6f} kN",
    "",
    "Next evidence required: mesh-converged local transition FEA.",
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
