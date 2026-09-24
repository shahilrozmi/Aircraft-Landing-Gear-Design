from pathlib import Path
import io
import math
import runpy
from contextlib import redirect_stdout

import numpy as np
import pandas as pd


# =============================================================================
# LANDING GEAR DESIGN PROJECT
# PHASE 2E3-B7B — TRANSITION GEOMETRY / LOCAL-FEA HANDOFF V0.1
#
# PURPOSE
#   Stop expanding the arbitrary Kt sensitivity trade and convert the surviving
#   150-mm-span architecture into explicit geometry and analysis inputs for the
#   next geometry-specific stress-concentration study.
#
# WHY
#   B7A showed that even the largest circular upper annulus inside the current
#   115 mm root-to-root head envelope does not reach the self-imposed
#   Kt_peak >= 2.0 transition-sensitivity gate.
#
#   That does NOT prove the architecture fails, because the B7/B7A Kt(s) curve
#   was explicitly a sensitivity envelope rather than a geometry-derived Kt.
#
#   Therefore this script:
#
#       1. carries TWO concrete transition geometries into local analysis:
#
#          PRIMARY:
#              74/64 -> 106/64 mm
#              taper start = 275 mm above A
#
#          MASS-LEAN COMPARATOR:
#              74/64 -> 104/64 mm
#              taper start = 275 mm above A
#
#       2. reads their B7A Kt capacities and local robustness margins,
#       3. generates explicit smoothstep OD coordinates for CAD / meshing,
#       4. reconstructs the current Phase 1 section resultants at:
#              - taper start,
#              - E2 pressure-closure outer face,
#              - shaft-hole bottom,
#       5. exports all limit/ultimate load cases and pressure states,
#       6. identifies the governing profile station at nominal Kt=1,
#          Kt_peak=1.5, and at the computed Kt capacity,
#       7. writes a local-FEA handoff note.
#
# IMPORTANT
#   - No claim is made that Kt=1.5 or the calculated Kt capacity is the actual
#     transition Kt.
#   - The next analysis must determine the real local concentration produced by
#     the explicit geometry.
#   - The 106 mm profile is a PRIMARY ANALYSIS CANDIDATE, not a frozen design.
#   - The 104 mm profile is retained as a mass/packaging comparator.
#
# OUTPUTS
#   phase2e3b7b_candidate_summary.csv
#   phase2e3b7b_profile_coordinates.csv
#   phase2e3b7b_section_resultants.csv
#   phase2e3b7b_profile_governing_points.csv
#   phase2e3b7b_fea_handoff.txt
# =============================================================================


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.resolve()

B7A_CAPACITY = HERE / "phase2e3b7a_kt_capacity.csv"
B5B_PY = HERE / "phase2e3b5b_upper_barrel_reinforcement_profile_v01.py"
B6_WORKING = HERE / "phase2e3b6_working_candidate_record.csv"

OUTPUT_SUMMARY = HERE / "phase2e3b7b_candidate_summary.csv"
OUTPUT_PROFILE = HERE / "phase2e3b7b_profile_coordinates.csv"
OUTPUT_RESULTANTS = HERE / "phase2e3b7b_section_resultants.csv"
OUTPUT_GOV = HERE / "phase2e3b7b_profile_governing_points.csv"
OUTPUT_HANDOFF = HERE / "phase2e3b7b_fea_handoff.txt"


# =============================================================================
# ANALYSIS CANDIDATES
# =============================================================================

CANDIDATES = [
    {
        "candidate":
            "PRIMARY_106",
        "role":
            "PRIMARY_ANALYSIS_CANDIDATE_NOT_FROZEN",
        "upper_OD_mm":
            106.0,
        "taper_start_A_mm":
            275.0,
    },
    {
        "candidate":
            "COMPARATOR_104",
        "role":
            "MASS_LEAN_COMPARATOR",
        "upper_OD_mm":
            104.0,
        "taper_start_A_mm":
            275.0,
    },
]

PROFILE_COORD_STEP_MM = 10.0

PROFILE_KT_CASES = [
    ("NOMINAL_KT1", 1.0),
    ("SENSITIVITY_KT1p5", 1.5),
    ("AT_B7A_KT_CAPACITY", None),
]


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


def profile_Kt(
    zA_mm,
    start_A_mm,
    end_A_mm,
    Kt_peak,
):
    if (
        zA_mm <= start_A_mm
        or zA_mm >= end_A_mm
    ):
        return 1.0

    s = (
        zA_mm
        - start_A_mm
    ) / (
        end_A_mm
        - start_A_mm
    )

    return (
        1.0
        + (
            Kt_peak
            - 1.0
        )
        * 4.0
        * s
        * (
            1.0
            - s
        )
    )


def station_grid(
    start_mm,
    end_mm,
    step_mm,
):
    values = np.arange(
        start_mm,
        end_mm,
        step_mm,
    ).tolist()

    if (
        not values
        or abs(
            values[-1]
            - end_mm
        ) > 1e-12
    ):
        values.append(
            end_mm
        )

    return [
        float(x)
        for x in values
    ]


# =============================================================================
# LOAD B5B MECHANICS
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
        run_name="phase2e3b5b_reuse_for_b7b",
    )


required = [
    "governing_annular",
    "governing_solid",
    "resultants_at_h",
    "loads",
    "case_col",
    "limit_cols",
    "ultimate_cols",
    "barrel_OD_mm",
    "barrel_ID_mm",
    "h_UA_static_m",
    "e2_boundary_above_U_mm",
    "WORKING_LOWER_LIGAMENT_MM",
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


governing_annular = b5b[
    "governing_annular"
]

governing_solid = b5b[
    "governing_solid"
]

resultants_at_h = b5b[
    "resultants_at_h"
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

LOWER_OD_MM = float(
    b5b[
        "barrel_OD_mm"
    ]
)

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

E2_BOUNDARY_ABOVE_U_MM = float(
    b5b[
        "e2_boundary_above_U_mm"
    ]
)

E2_BOUNDARY_A_MM = (
    h_UA_static_m
    * 1000.0
    + E2_BOUNDARY_ABOVE_U_MM
)

WORKING_LOWER_LIGAMENT_MM = float(
    b5b[
        "WORKING_LOWER_LIGAMENT_MM"
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
# B6 WORKING TRUNNION GEOMETRY
# =============================================================================

b6 = read_csv(
    B6_WORKING
)

if b6.empty:
    raise ValueError(
        "B6 working candidate record is empty."
    )

b6row = b6.iloc[
    0
]

TRUNNION_D_MM = float(
    b6row[
        "journal_diameter_mm"
    ]
)

HEAD_ROOT_TO_ROOT_WIDTH_MM = float(
    b6row[
        "root_to_root_head_width_mm"
    ]
)

SHAFT_HOLE_BOTTOM_A_MM = (
    E2_BOUNDARY_A_MM
    + WORKING_LOWER_LIGAMENT_MM
)

SHAFT_CENTER_A_MM = (
    SHAFT_HOLE_BOTTOM_A_MM
    + TRUNNION_D_MM
    / 2.0
)


# =============================================================================
# READ B7A CAPACITY RESULTS
# =============================================================================

capacity_df = read_csv(
    B7A_CAPACITY
)

candidate_summary_rows = []

for cand in CANDIDATES:

    rows = capacity_df.loc[
        near(
            capacity_df[
                "upper_OD_mm"
            ],
            cand[
                "upper_OD_mm"
            ],
        )
        &
        near(
            capacity_df[
                "taper_start_A_mm"
            ],
            cand[
                "taper_start_A_mm"
            ],
        )
    ]

    if len(
        rows
    ) != 1:
        raise ValueError(
            f"Expected one B7A capacity row for {cand['candidate']}; "
            f"found {len(rows)}."
        )

    src = rows.iloc[
        0
    ]

    candidate_summary_rows.append({
        "candidate":
            cand[
                "candidate"
            ],
        "role":
            cand[
                "role"
            ],
        "lower_OD_mm":
            LOWER_OD_MM,
        "retained_ID_mm":
            BARREL_ID_MM,
        "upper_OD_mm":
            cand[
                "upper_OD_mm"
            ],
        "taper_start_A_mm":
            cand[
                "taper_start_A_mm"
            ],
        "taper_end_A_mm":
            E2_BOUNDARY_A_MM,
        "transition_length_mm":
            src[
                "transition_length_mm"
            ],
        "maximum_geometric_half_angle_deg":
            src[
                "maximum_geometric_half_angle_deg"
            ],
        "B7A_Kt_peak_capacity":
            src[
                "Kt_peak_capacity"
            ],
        "closure_annulus_MS_ultimate_Kt3":
            src[
                "annular_closure_MS_ultimate_Kt3"
            ],
        "solid_neck_MS_ultimate_Kt3":
            src[
                "solid_neck_MS_ultimate_Kt3"
            ],
        "head_width_reserve_each_side_mm":
            src[
                "head_width_reserve_each_side_mm"
            ],
        "added_annular_mass_kg_vs_74mm":
            src[
                "added_annular_mass_kg_vs_74mm"
            ],
        "status":
            (
                "READY_FOR_GEOMETRY_SPECIFIC_LOCAL_ANALYSIS"
            ),
    })


candidate_summary_df = pd.DataFrame(
    candidate_summary_rows
)

candidate_summary_df.to_csv(
    OUTPUT_SUMMARY,
    index=False,
)


# =============================================================================
# PROFILE COORDINATES
# =============================================================================

profile_rows = []

for cand in CANDIDATES:

    z_values = station_grid(
        cand[
            "taper_start_A_mm"
        ],
        E2_BOUNDARY_A_MM,
        PROFILE_COORD_STEP_MM,
    )

    for zA_mm in z_values:

        OD_mm = profile_OD_mm(
            zA_mm,
            cand[
                "taper_start_A_mm"
            ],
            E2_BOUNDARY_A_MM,
            LOWER_OD_MM,
            cand[
                "upper_OD_mm"
            ],
        )

        s = (
            (
                zA_mm
                - cand[
                    "taper_start_A_mm"
                ]
            )
            / (
                E2_BOUNDARY_A_MM
                - cand[
                    "taper_start_A_mm"
                ]
            )
        )

        s = max(
            0.0,
            min(
                1.0,
                s,
            ),
        )

        profile_rows.append({
            "candidate":
                cand[
                    "candidate"
                ],
            "station_A_mm":
                zA_mm,
            "station_U_mm":
                zA_mm
                - h_UA_static_m
                * 1000.0,
            "normalized_s":
                s,
            "outer_diameter_mm":
                OD_mm,
            "outer_radius_mm":
                OD_mm / 2.0,
            "inner_diameter_mm":
                BARREL_ID_MM,
            "inner_radius_mm":
                BARREL_ID_MM / 2.0,
        })


profile_df = pd.DataFrame(
    profile_rows
)

profile_df.to_csv(
    OUTPUT_PROFILE,
    index=False,
)


# =============================================================================
# SECTION RESULTANTS FOR LOCAL MODEL HANDOFF
# =============================================================================

key_stations = []

for cand in CANDIDATES:
    key_stations.append(
        (
            cand[
                "candidate"
            ],
            "TAPER_START",
            cand[
                "taper_start_A_mm"
            ],
        )
    )

# Shared upper stations.
for cand in CANDIDATES:
    key_stations.extend([
        (
            cand[
                "candidate"
            ],
            "E2_CLOSURE_OUTER_FACE",
            E2_BOUNDARY_A_MM,
        ),
        (
            cand[
                "candidate"
            ],
            "SHAFT_HOLE_BOTTOM",
            SHAFT_HOLE_BOTTOM_A_MM,
        ),
        (
            cand[
                "candidate"
            ],
            "TRUNNION_CENTERLINE",
            SHAFT_CENTER_A_MM,
        ),
    ])


resultant_rows = []

for (
    candidate_name,
    station_name,
    zA_mm,
) in key_stations:

    for (
        level,
        cols,
        pressure_MPa,
    ) in [
        (
            "limit",
            limit_cols,
            P_LIMIT_DIFF_MPa,
        ),
        (
            "ultimate",
            ultimate_cols,
            P_ULT_DIFF_MPa,
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
                zA_mm,
            )

            resultant_rows.append({
                "candidate":
                    candidate_name,
                "station":
                    station_name,
                "station_A_mm":
                    zA_mm,
                "station_U_mm":
                    zA_mm
                    - h_UA_static_m
                    * 1000.0,
                "level":
                    level,
                "case":
                    str(
                        load[
                            case_col
                        ]
                    ),
                "pressure_diff_MPa_if_inside_live_pressure_region":
                    (
                        pressure_MPa
                        if zA_mm
                        <= E2_BOUNDARY_A_MM
                        + 1e-9
                        else 0.0
                    ),
                **res,
            })


resultants_df = pd.DataFrame(
    resultant_rows
)

resultants_df.to_csv(
    OUTPUT_RESULTANTS,
    index=False,
)


# =============================================================================
# GOVERNING PROFILE POINTS
# =============================================================================

gov_rows = []

for cand in CANDIDATES:

    cap_row = candidate_summary_df.loc[
        candidate_summary_df[
            "candidate"
        ]
        == cand[
            "candidate"
        ]
    ].iloc[
        0
    ]

    for (
        kt_case_name,
        Kt_peak_raw,
    ) in PROFILE_KT_CASES:

        Kt_peak = (
            float(
                cap_row[
                    "B7A_Kt_peak_capacity"
                ]
            )
            if Kt_peak_raw
            is None
            else float(
                Kt_peak_raw
            )
        )

        stations = station_grid(
            cand[
                "taper_start_A_mm"
            ],
            E2_BOUNDARY_A_MM,
            PROFILE_COORD_STEP_MM,
        )

        for level in [
            "limit",
            "ultimate",
        ]:

            best = None

            for zA_mm in stations:

                OD_mm = profile_OD_mm(
                    zA_mm,
                    cand[
                        "taper_start_A_mm"
                    ],
                    E2_BOUNDARY_A_MM,
                    LOWER_OD_MM,
                    cand[
                        "upper_OD_mm"
                    ],
                )

                local_Kt = profile_Kt(
                    zA_mm,
                    cand[
                        "taper_start_A_mm"
                    ],
                    E2_BOUNDARY_A_MM,
                    Kt_peak,
                )

                gov = governing_annular(
                    zA_mm,
                    OD_mm,
                    local_Kt,
                    level,
                )

                row = {
                    "candidate":
                        cand[
                            "candidate"
                        ],
                    "Kt_case":
                        kt_case_name,
                    "Kt_peak":
                        Kt_peak,
                    "level":
                        level,
                    "station_A_mm":
                        zA_mm,
                    "station_U_mm":
                        zA_mm
                        - h_UA_static_m
                        * 1000.0,
                    "local_OD_mm":
                        OD_mm,
                    "local_Kt":
                        local_Kt,
                    "governing_load_case":
                        gov[
                            "case"
                        ],
                    "vm_MPa":
                        gov[
                            "vm_MPa"
                        ],
                    "MS":
                        gov[
                            "MS"
                        ],
                }

                if (
                    best is None
                    or row[
                        "MS"
                    ]
                    < best[
                        "MS"
                    ]
                ):
                    best = row

            gov_rows.append(
                best
            )


gov_df = pd.DataFrame(
    gov_rows
)

gov_df.to_csv(
    OUTPUT_GOV,
    index=False,
)


# =============================================================================
# FEA HANDOFF NOTE
# =============================================================================

primary = candidate_summary_df.loc[
    candidate_summary_df[
        "candidate"
    ]
    == "PRIMARY_106"
].iloc[
    0
]

comparator = candidate_summary_df.loc[
    candidate_summary_df[
        "candidate"
    ]
    == "COMPARATOR_104"
].iloc[
    0
]

primary_gov = gov_df.loc[
    (
        gov_df[
            "candidate"
        ]
        == "PRIMARY_106"
    )
    &
    (
        gov_df[
            "Kt_case"
        ]
        == "AT_B7A_KT_CAPACITY"
    )
    &
    (
        gov_df[
            "level"
        ]
        == "ultimate"
    )
].iloc[
    0
]


handoff_lines = [
    "=" * 124,
    " PHASE 2E3-B7B — TRANSITION GEOMETRY / LOCAL-FEA HANDOFF V0.1",
    "=" * 124,
    "",
    "PURPOSE",
    "-" * 124,
    (
        "Replace the artificial Kt>=2 screening gate with a geometry-specific "
        "local analysis of an explicit transition."
    ),
    "",
    "PRIMARY ANALYSIS CANDIDATE — NOT FROZEN",
    "-" * 124,
    f"Lower barrel:                    {LOWER_OD_MM:.1f} OD / {BARREL_ID_MM:.1f} ID mm",
    f"Upper annulus:                   {primary['upper_OD_mm']:.1f} OD / {BARREL_ID_MM:.1f} ID mm",
    f"Taper start:                     {primary['taper_start_A_mm']:.1f} mm above A",
    f"Taper end / closure outer face: {primary['taper_end_A_mm']:.6f} mm above A",
    f"Transition length:               {primary['transition_length_mm']:.3f} mm",
    f"Maximum geometric half-angle:    {primary['maximum_geometric_half_angle_deg']:.3f} deg",
    f"B7A Kt_peak capacity:            {primary['B7A_Kt_peak_capacity']:.3f}",
    f"Closure annulus Kt=3 MSu:        {primary['closure_annulus_MS_ultimate_Kt3']:+.3f}",
    f"Solid neck Kt=3 MSu:             {primary['solid_neck_MS_ultimate_Kt3']:+.3f}",
    f"Head reserve each side:          {primary['head_width_reserve_each_side_mm']:.1f} mm",
    f"Added annular 7075 mass:         {primary['added_annular_mass_kg_vs_74mm']:.3f} kg",
    "",
    "MASS-LEAN COMPARATOR",
    "-" * 124,
    f"Upper annulus:                   {comparator['upper_OD_mm']:.1f} OD / {BARREL_ID_MM:.1f} ID mm",
    f"B7A Kt_peak capacity:            {comparator['B7A_Kt_peak_capacity']:.3f}",
    f"Closure annulus Kt=3 MSu:        {comparator['closure_annulus_MS_ultimate_Kt3']:+.3f}",
    f"Head reserve each side:          {comparator['head_width_reserve_each_side_mm']:.1f} mm",
    f"Added annular 7075 mass:         {comparator['added_annular_mass_kg_vs_74mm']:.3f} kg",
    "",
    "CURRENT HEAD / TRUNNION GEOMETRY",
    "-" * 124,
    f"Root-to-root head width:         {HEAD_ROOT_TO_ROOT_WIDTH_MM:.1f} mm",
    f"300M trunnion journal diameter:  {TRUNNION_D_MM:.1f} mm",
    f"Lower ligament:                  {WORKING_LOWER_LIGAMENT_MM:.1f} mm",
    f"Shaft-hole bottom:               {SHAFT_HOLE_BOTTOM_A_MM:.6f} mm above A",
    f"Trunnion centerline:             {SHAFT_CENTER_A_MM:.6f} mm above A",
    "",
    "PRIMARY CAPACITY-GOVERNING POINT",
    "-" * 124,
    f"Ultimate governing station:      {primary_gov['station_A_mm']:.3f} mm above A",
    f"Local OD:                        {primary_gov['local_OD_mm']:.3f} mm",
    f"Local sensitivity Kt:            {primary_gov['local_Kt']:.6f}",
    f"Governing load case:             {primary_gov['governing_load_case']}",
    f"VM stress at capacity:           {primary_gov['vm_MPa']:.3f} MPa",
    f"Margin at capacity:              {primary_gov['MS']:+.6f}",
    "",
    "PRESSURE STATES",
    "-" * 124,
    f"Limit differential pressure:     {P_LIMIT_DIFF_MPa:.3f} MPa",
    f"Ultimate differential pressure:  {P_ULT_DIFF_MPa:.3f} MPa",
    (
        "Pressure applies to the live 64 mm bore only up to the E2 pressure "
        "closure; the solid head above the closure is not internally pressurized."
    ),
    "",
    "LOCAL-ANALYSIS REQUIREMENTS",
    "-" * 124,
    (
        "1. Use the profile coordinate CSV as the exact preliminary outer "
        "generatrix for the primary/comparator geometry."
    ),
    (
        "2. Include the 64 mm internal bore and the pressure closure / solid "
        "head transition."
    ),
    (
        "3. Evaluate at least LC4+, LC5, and any additional cases identified "
        "from the exported section-resultant table."
    ),
    (
        "4. Run both limit and ultimate load levels with their corresponding "
        "pressure state."
    ),
    (
        "5. Report nominal section stress away from the transition and peak "
        "local stress at the transition, then calculate Kt_local = "
        "sigma_peak / sigma_nominal on a consistent stress basis."
    ),
    (
        "6. Mesh-converge the local peak. Do not accept a single-element "
        "singularity or sharp-corner stress."
    ),
    (
        "7. If primary 106 mm geometry produces a real local Kt below its "
        "B7A capacity, retain it for further detail; otherwise compare 104 mm "
        "only as a mass reference and revise geometry/profile."
    ),
    "",
    "OPEN ITEMS",
    "-" * 124,
    (
        "Actual fillet/tangent radii, pressure-closure retainer geometry, "
        "transverse trunnion hole, shaft/head capture, fretting/contact, "
        "fatigue, tolerances and corrosion remain open."
    ),
    "=" * 124,
]

OUTPUT_HANDOFF.write_text(
    "\n".join(
        handoff_lines
    ),
    encoding="utf-8",
)


# =============================================================================
# CONSOLE REPORT
# =============================================================================

print("=" * 124)
print(
    " PHASE 2E3-B7B — TRANSITION GEOMETRY / LOCAL-FEA HANDOFF V0.1"
)
print("=" * 124)

print("\nWHY B7A STOPS THE PARAMETRIC Kt EXPANSION")
print("-" * 124)
print(
    "B7A did not produce Kt_peak >= 2.0 inside the current 115-mm head envelope."
)
print(
    "Because that Kt curve is a sensitivity assumption rather than a geometry-derived correlation, "
    "further OD inflation alone would not constitute validation."
)

print("\nANALYSIS CANDIDATES")
print("-" * 124)
print(
    f"{'Candidate':<18}"
    f"{'ODtop':>8}"
    f"{'StartA':>10}"
    f"{'Kt cap':>10}"
    f"{'Clos MSu':>11}"
    f"{'Neck MSu':>11}"
    f"{'Res/side':>11}"
    f"{'Mass+':>10}"
)
print("-" * 92)

for _, row in candidate_summary_df.iterrows():
    print(
        f"{row['candidate']:<18}"
        f"{row['upper_OD_mm']:>8.0f}"
        f"{row['taper_start_A_mm']:>10.0f}"
        f"{row['B7A_Kt_peak_capacity']:>10.3f}"
        f"{row['closure_annulus_MS_ultimate_Kt3']:>11.3f}"
        f"{row['solid_neck_MS_ultimate_Kt3']:>11.3f}"
        f"{row['head_width_reserve_each_side_mm']:>11.1f}"
        f"{row['added_annular_mass_kg_vs_74mm']:>10.3f}"
    )

print("\nPRIMARY GEOMETRY")
print("-" * 124)
print(
    f"74/{BARREL_ID_MM:.0f} mm lower barrel -> "
    f"{primary['upper_OD_mm']:.0f}/{BARREL_ID_MM:.0f} mm upper annulus"
)
print(
    f"Taper start / end:                "
    f"{primary['taper_start_A_mm']:.1f} / {primary['taper_end_A_mm']:.3f} mm above A"
)
print(
    f"Transition length:                {primary['transition_length_mm']:.3f} mm"
)
print(
    f"Maximum geometric half-angle:     {primary['maximum_geometric_half_angle_deg']:.3f} deg"
)
print(
    f"Trunnion centerline:              {SHAFT_CENTER_A_MM:.3f} mm above A"
)

print("\nPRIMARY — PROFILE GOVERNING POINTS")
print("-" * 124)
print(
    f"{'Kt case':<24}"
    f"{'Level':>10}"
    f"{'A station':>12}"
    f"{'OD':>10}"
    f"{'Kt local':>10}"
    f"{'Case':>10}"
    f"{'VM':>10}"
    f"{'MS':>10}"
)
print("-" * 98)

primary_rows = gov_df.loc[
    gov_df[
        "candidate"
    ]
    == "PRIMARY_106"
]

for _, row in primary_rows.iterrows():
    print(
        f"{row['Kt_case']:<24}"
        f"{row['level']:>10}"
        f"{row['station_A_mm']:>12.1f}"
        f"{row['local_OD_mm']:>10.2f}"
        f"{row['local_Kt']:>10.3f}"
        f"{str(row['governing_load_case']):>10}"
        f"{row['vm_MPa']:>10.1f}"
        f"{row['MS']:>10.3f}"
    )

print("\nB7B DISPOSITION")
print("-" * 124)
print(
    "PRIMARY geometry for geometry-specific analysis: 106/64 mm upper annulus, taper start 275 mm above A."
)
print(
    "104/64 mm is retained only as a mass-lean comparator."
)
print(
    "No transition Kt is frozen. The next meaningful result must come from the explicit geometry "
    "rather than another arbitrary Kt sensitivity expansion."
)
print(
    "The exported resultants/profile coordinates are ready to use as the basis for the local CAD/ANSYS model."
)

print("\nOUTPUT FILES")
print("-" * 124)
print(
    f"Candidate summary:                {OUTPUT_SUMMARY}"
)
print(
    f"Profile coordinates:              {OUTPUT_PROFILE}"
)
print(
    f"Section resultants:               {OUTPUT_RESULTANTS}"
)
print(
    f"Profile governing points:         {OUTPUT_GOV}"
)
print(
    f"FEA handoff note:                 {OUTPUT_HANDOFF}"
)
print("=" * 124)


if __name__ == "__main__":
    pass
