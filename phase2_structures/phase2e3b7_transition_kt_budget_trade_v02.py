from pathlib import Path
import io
import math
import runpy
from contextlib import redirect_stdout

import numpy as np
import pandas as pd


# =============================================================================
# LANDING GEAR DESIGN PROJECT
# PHASE 2E3-B7 — UPPER-BARREL -> SOLID-HEAD TRANSITION / Kt-BUDGET TRADE V0.2
#
# PURPOSE
#   Develop a practical preliminary external reinforcement profile after:
#
#       B5A: historical 74/64 barrel PASS was found to use 300M allowables,
#       B5B: corrected 7075-T6 upper-barrel / solid-head requirements were mapped,
#       B6:  150 mm / 34 mm / 25 mm trunnion family was selected as working,
#       B6A: 10 mm lower ligament passed the corrected local-head screen.
#
#   The internal 64 mm bore and E2 pressure-cavity geometry remain unchanged.
#   Only the EXTERNAL structural envelope is varied.
#
# PROFILE MODEL
#   The retained smooth barrel is 74 mm OD / 64 mm ID.
#
#   Candidate upper annular ODs:
#       90, 96, 102 mm
#
#   Candidate smooth-taper start stations:
#       300, 350, 400 mm above axle datum A
#
#   The taper ends at the E2 pressure-closure outer face.
#
#   A cubic smoothstep is used:
#
#       D(s) = D0 + (D1-D0) * (3s^2 - 2s^3)
#
#   so dD/dz = 0 at both ends. This is a packaging shape only, NOT a
#   validated stress-concentration solution.
#
# Kt SENSITIVITY MODEL
#   Since no source-backed fillet/taper Kt correlation has yet been frozen,
#   this script DOES NOT pretend to predict the actual Kt from geometry.
#
#   Instead it applies a transparent sensitivity envelope:
#
#       Kt(s) = 1 + (Kt_peak - 1) * 4s(1-s)
#
#   so:
#       Kt = 1 at the tangent ends,
#       Kt = Kt_peak at mid-transition.
#
#   Peak sensitivity values:
#       1.25, 1.50, 2.00
#
#   The final CAD/FEA task will have to demonstrate that the real transition
#   stays within the allowable Kt budget.
#
# ADDITIONAL CHECKS
#   For each upper OD the script also calculates:
#
#       - annular pressure-side margin immediately below the closure at Kt=3,
#       - solid-neck margin above the closure at Kt=3,
#       - geometric reserve inside the 115 mm B6 root-to-root head width,
#       - added annular 7075 mass relative to a 74/64 baseline.
#
# WORKING-PROFILE ELIGIBILITY
#   A candidate is "ELIGIBLE_WITHIN_SENSITIVITY_MODEL" only if:
#
#       - the full profile passes limit + ultimate for the stated Kt_peak,
#       - the upper annulus at the closure passes a separate Kt=3 screen,
#       - the solid neck at the shaft-hole bottom passes Kt=3,
#       - the selected OD fits inside the 115 mm root-to-root head envelope.
#
#   This is NOT final FEA validation.
#
# OUTPUTS
#   phase2e3b7_transition_trade.csv
#   phase2e3b7_profile_station_details.csv
#   phase2e3b7_upper_OD_boundary_checks.csv
#   phase2e3b7_working_profile_candidate.csv
#   phase2e3b7_summary.txt
# =============================================================================


HERE = Path(__file__).resolve().parent

B5B_PY = HERE / "phase2e3b5b_upper_barrel_reinforcement_profile_v01.py"
B6_WORKING = HERE / "phase2e3b6_working_candidate_record.csv"

OUTPUT_TRADE = HERE / "phase2e3b7_transition_trade.csv"
OUTPUT_DETAILS = HERE / "phase2e3b7_profile_station_details.csv"
OUTPUT_BOUNDARY = HERE / "phase2e3b7_upper_OD_boundary_checks.csv"
OUTPUT_WORKING = HERE / "phase2e3b7_working_profile_candidate.csv"
OUTPUT_SUMMARY = HERE / "phase2e3b7_summary.txt"


# =============================================================================
# CANDIDATE / SENSITIVITY SETS
# =============================================================================

UPPER_OD_VALUES_MM = [
    90.0,
    96.0,
    102.0,
]

TAPER_START_VALUES_A_MM = [
    300.0,
    350.0,
    400.0,
]

KT_PEAK_VALUES = [
    1.25,
    1.50,
    2.00,
]

PROFILE_STEP_MM = 10.0

RHO_7075_KG_M3 = 2810.0


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
    s = min(
        1.0,
        max(
            0.0,
            float(s),
        ),
    )

    return (
        3.0 * s**2
        - 2.0 * s**3
    )


def smoothstep_derivative(s):
    s = min(
        1.0,
        max(
            0.0,
            float(s),
        ),
    )

    return (
        6.0 * s
        - 6.0 * s**2
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
            1.0 - s
        )
    )


def annulus_area_mm2(
    OD_mm,
    ID_mm,
):
    return (
        math.pi
        / 4.0
        * (
            OD_mm**2
            - ID_mm**2
        )
    )


def added_annular_mass_kg(
    start_A_mm,
    end_A_mm,
    lower_OD_mm,
    upper_OD_mm,
    ID_mm,
    step_mm=2.0,
):
    z = np.arange(
        start_A_mm,
        end_A_mm
        + step_mm,
        step_mm,
    )

    if z[-1] > end_A_mm:
        z[-1] = (
            end_A_mm
        )

    areas_added_m2 = []

    A_baseline_mm2 = (
        annulus_area_mm2(
            lower_OD_mm,
            ID_mm,
        )
    )

    for zi in z:
        OD = profile_OD_mm(
            zi,
            start_A_mm,
            end_A_mm,
            lower_OD_mm,
            upper_OD_mm,
        )

        A_added_mm2 = (
            annulus_area_mm2(
                OD,
                ID_mm,
            )
            - A_baseline_mm2
        )

        areas_added_m2.append(
            A_added_mm2
            * 1e-6
        )

    z_m = (
        z
        * 1e-3
    )

    # NumPy 2.x removed np.trapz; use np.trapezoid instead.
    volume_added_m3 = np.trapezoid(
        np.array(
            areas_added_m2
        ),
        z_m,
    )

    return (
        RHO_7075_KG_M3
        * volume_added_m3
    )


# =============================================================================
# LOAD B5B MECHANICS WITHOUT REPRINTING ITS REPORT
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
        run_name="phase2e3b5b_reuse_for_b7",
    )


required = [
    "governing_annular",
    "governing_solid",
    "barrel_OD_mm",
    "barrel_ID_mm",
    "preferred_hL_mm",
    "h_UA_static_m",
    "e2_boundary_above_U_mm",
    "WORKING_LOWER_LIGAMENT_MM",
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

PROFILE_START_SCAN_A_MM = float(
    b5b[
        "preferred_hL_mm"
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

SHAFT_HOLE_BOTTOM_A_MM = (
    E2_BOUNDARY_A_MM
    + WORKING_LOWER_LIGAMENT_MM
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
# B6 HEAD WIDTH
# =============================================================================

b6_working = read_csv(
    B6_WORKING
)

if b6_working.empty:
    raise ValueError(
        "B6 working candidate record is empty."
    )

b6 = b6_working.iloc[
    0
]

HEAD_ROOT_TO_ROOT_WIDTH_MM = float(
    b6[
        "root_to_root_head_width_mm"
    ]
)


# =============================================================================
# BOUNDARY / SOLID-NECK CHECKS FOR EACH UPPER OD
# =============================================================================

boundary_rows = []

for upper_OD_mm in UPPER_OD_VALUES_MM:

    ann_limit = governing_annular(
        E2_BOUNDARY_A_MM,
        upper_OD_mm,
        3.0,
        "limit",
    )

    ann_ult = governing_annular(
        E2_BOUNDARY_A_MM,
        upper_OD_mm,
        3.0,
        "ultimate",
    )

    solid_limit = governing_solid(
        SHAFT_HOLE_BOTTOM_A_MM,
        upper_OD_mm,
        3.0,
        "limit",
    )

    solid_ult = governing_solid(
        SHAFT_HOLE_BOTTOM_A_MM,
        upper_OD_mm,
        3.0,
        "ultimate",
    )

    fit_reserve_total_mm = (
        HEAD_ROOT_TO_ROOT_WIDTH_MM
        - upper_OD_mm
    )

    boundary_rows.append({
        "upper_OD_mm":
            upper_OD_mm,

        "annular_closure_limit_case":
            ann_limit[
                "case"
            ],
        "annular_closure_limit_vm_MPa":
            ann_limit[
                "vm_MPa"
            ],
        "annular_closure_MS_limit":
            ann_limit[
                "MS"
            ],

        "annular_closure_ultimate_case":
            ann_ult[
                "case"
            ],
        "annular_closure_ultimate_vm_MPa":
            ann_ult[
                "vm_MPa"
            ],
        "annular_closure_MS_ultimate":
            ann_ult[
                "MS"
            ],

        "annular_closure_Kt3_PASS":
            (
                ann_limit[
                    "MS"
                ] >= 0.0
                and ann_ult[
                    "MS"
                ] >= 0.0
            ),

        "solid_neck_limit_case":
            solid_limit[
                "case"
            ],
        "solid_neck_limit_vm_MPa":
            solid_limit[
                "vm_MPa"
            ],
        "solid_neck_MS_limit":
            solid_limit[
                "MS"
            ],

        "solid_neck_ultimate_case":
            solid_ult[
                "case"
            ],
        "solid_neck_ultimate_vm_MPa":
            solid_ult[
                "vm_MPa"
            ],
        "solid_neck_MS_ultimate":
            solid_ult[
                "MS"
            ],

        "solid_neck_Kt3_PASS":
            (
                solid_limit[
                    "MS"
                ] >= 0.0
                and solid_ult[
                    "MS"
                ] >= 0.0
            ),

        "head_root_to_root_width_mm":
            HEAD_ROOT_TO_ROOT_WIDTH_MM,
        "head_width_total_reserve_mm":
            fit_reserve_total_mm,
        "head_width_reserve_each_side_mm":
            fit_reserve_total_mm
            / 2.0,
        "head_width_fit_PASS":
            fit_reserve_total_mm
            >= 0.0,
    })


boundary_df = pd.DataFrame(
    boundary_rows
)

boundary_df.to_csv(
    OUTPUT_BOUNDARY,
    index=False,
)


# =============================================================================
# PROFILE SWEEP
# =============================================================================

trade_rows = []
detail_rows = []

for upper_OD_mm in UPPER_OD_VALUES_MM:

    boundary = boundary_df.loc[
        np.isclose(
            boundary_df[
                "upper_OD_mm"
            ],
            upper_OD_mm,
        )
    ].iloc[
        0
    ]

    for start_A_mm in TAPER_START_VALUES_A_MM:

        if start_A_mm >= E2_BOUNDARY_A_MM:
            continue

        transition_length_mm = (
            E2_BOUNDARY_A_MM
            - start_A_mm
        )

        delta_D_mm = (
            upper_OD_mm
            - LOWER_OD_MM
        )

        # Maximum smoothstep derivative occurs at s=0.5 and equals 1.5.
        max_dD_dz = (
            1.5
            * delta_D_mm
            / transition_length_mm
        )

        max_half_angle_deg = math.degrees(
            math.atan(
                0.5
                * max_dD_dz
            )
        )

        added_mass_kg = added_annular_mass_kg(
            start_A_mm,
            E2_BOUNDARY_A_MM,
            LOWER_OD_MM,
            upper_OD_mm,
            BARREL_ID_MM,
        )

        for Kt_peak in KT_PEAK_VALUES:

            stations = np.arange(
                PROFILE_START_SCAN_A_MM,
                E2_BOUNDARY_A_MM,
                PROFILE_STEP_MM,
            ).tolist()

            if (
                not stations
                or abs(
                    stations[
                        -1
                    ]
                    - E2_BOUNDARY_A_MM
                ) > 1e-9
            ):
                stations.append(
                    E2_BOUNDARY_A_MM
                )

            min_limit_MS = np.inf
            min_ultimate_MS = np.inf

            gov_limit_station = None
            gov_ultimate_station = None

            profile_pass = True

            for zA_mm in stations:

                OD_mm = profile_OD_mm(
                    zA_mm,
                    start_A_mm,
                    E2_BOUNDARY_A_MM,
                    LOWER_OD_MM,
                    upper_OD_mm,
                )

                local_Kt = profile_Kt(
                    zA_mm,
                    start_A_mm,
                    E2_BOUNDARY_A_MM,
                    Kt_peak,
                )

                lim = governing_annular(
                    zA_mm,
                    OD_mm,
                    local_Kt,
                    "limit",
                )

                ult = governing_annular(
                    zA_mm,
                    OD_mm,
                    local_Kt,
                    "ultimate",
                )

                if lim[
                    "MS"
                ] < min_limit_MS:
                    min_limit_MS = (
                        lim[
                            "MS"
                        ]
                    )

                    gov_limit_station = {
                        "station_A_mm":
                            zA_mm,
                        "station_U_mm":
                            zA_mm
                            - h_UA_static_m
                            * 1000.0,
                        "OD_mm":
                            OD_mm,
                        "Kt":
                            local_Kt,
                        "case":
                            lim[
                                "case"
                            ],
                        "vm_MPa":
                            lim[
                                "vm_MPa"
                            ],
                    }

                if ult[
                    "MS"
                ] < min_ultimate_MS:
                    min_ultimate_MS = (
                        ult[
                            "MS"
                        ]
                    )

                    gov_ultimate_station = {
                        "station_A_mm":
                            zA_mm,
                        "station_U_mm":
                            zA_mm
                            - h_UA_static_m
                            * 1000.0,
                        "OD_mm":
                            OD_mm,
                        "Kt":
                            local_Kt,
                        "case":
                            ult[
                                "case"
                            ],
                        "vm_MPa":
                            ult[
                                "vm_MPa"
                            ],
                    }

                if (
                    lim[
                        "MS"
                    ] < 0.0
                    or ult[
                        "MS"
                    ] < 0.0
                ):
                    profile_pass = False

                detail_rows.append({
                    "upper_OD_mm":
                        upper_OD_mm,
                    "taper_start_A_mm":
                        start_A_mm,
                    "Kt_peak_sensitivity":
                        Kt_peak,
                    "station_A_mm":
                        zA_mm,
                    "station_U_mm":
                        zA_mm
                        - h_UA_static_m
                        * 1000.0,
                    "profile_OD_mm":
                        OD_mm,
                    "local_Kt_sensitivity":
                        local_Kt,

                    "limit_case":
                        lim[
                            "case"
                        ],
                    "limit_vm_MPa":
                        lim[
                            "vm_MPa"
                        ],
                    "MS_limit":
                        lim[
                            "MS"
                        ],

                    "ultimate_case":
                        ult[
                            "case"
                        ],
                    "ultimate_vm_MPa":
                        ult[
                            "vm_MPa"
                        ],
                    "MS_ultimate":
                        ult[
                            "MS"
                        ],

                    "station_PASS":
                        (
                            lim[
                                "MS"
                            ] >= 0.0
                            and ult[
                                "MS"
                            ] >= 0.0
                        ),
                })

            boundary_pass = bool(
                boundary[
                    "annular_closure_Kt3_PASS"
                ]
            )

            solid_pass = bool(
                boundary[
                    "solid_neck_Kt3_PASS"
                ]
            )

            fit_pass = bool(
                boundary[
                    "head_width_fit_PASS"
                ]
            )

            eligible = (
                profile_pass
                and boundary_pass
                and solid_pass
                and fit_pass
            )

            trade_rows.append({
                "upper_OD_mm":
                    upper_OD_mm,
                "taper_start_A_mm":
                    start_A_mm,
                "taper_end_A_mm":
                    E2_BOUNDARY_A_MM,
                "transition_length_mm":
                    transition_length_mm,
                "maximum_geometric_half_angle_deg":
                    max_half_angle_deg,
                "Kt_peak_sensitivity":
                    Kt_peak,

                "minimum_profile_MS_limit":
                    min_limit_MS,
                "governing_limit_station_A_mm":
                    gov_limit_station[
                        "station_A_mm"
                    ],
                "governing_limit_station_U_mm":
                    gov_limit_station[
                        "station_U_mm"
                    ],
                "governing_limit_OD_mm":
                    gov_limit_station[
                        "OD_mm"
                    ],
                "governing_limit_local_Kt":
                    gov_limit_station[
                        "Kt"
                    ],
                "governing_limit_case":
                    gov_limit_station[
                        "case"
                    ],
                "governing_limit_vm_MPa":
                    gov_limit_station[
                        "vm_MPa"
                    ],

                "minimum_profile_MS_ultimate":
                    min_ultimate_MS,
                "governing_ultimate_station_A_mm":
                    gov_ultimate_station[
                        "station_A_mm"
                    ],
                "governing_ultimate_station_U_mm":
                    gov_ultimate_station[
                        "station_U_mm"
                    ],
                "governing_ultimate_OD_mm":
                    gov_ultimate_station[
                        "OD_mm"
                    ],
                "governing_ultimate_local_Kt":
                    gov_ultimate_station[
                        "Kt"
                    ],
                "governing_ultimate_case":
                    gov_ultimate_station[
                        "case"
                    ],
                "governing_ultimate_vm_MPa":
                    gov_ultimate_station[
                        "vm_MPa"
                    ],

                "annular_closure_Kt3_MS_ultimate":
                    boundary[
                        "annular_closure_MS_ultimate"
                    ],
                "annular_closure_Kt3_PASS":
                    boundary_pass,

                "solid_neck_Kt3_MS_ultimate":
                    boundary[
                        "solid_neck_MS_ultimate"
                    ],
                "solid_neck_Kt3_PASS":
                    solid_pass,

                "head_width_reserve_each_side_mm":
                    boundary[
                        "head_width_reserve_each_side_mm"
                    ],
                "head_width_fit_PASS":
                    fit_pass,

                "added_annular_mass_kg_vs_74mm":
                    added_mass_kg,

                "PROFILE_PASS":
                    profile_pass,
                "ELIGIBLE_WITHIN_SENSITIVITY_MODEL":
                    eligible,
            })


trade_df = pd.DataFrame(
    trade_rows
)

details_df = pd.DataFrame(
    detail_rows
)

trade_df.to_csv(
    OUTPUT_TRADE,
    index=False,
)

details_df.to_csv(
    OUTPUT_DETAILS,
    index=False,
)


# =============================================================================
# WORKING PROFILE SELECTION
#
# We do not collapse unlike Kt sensitivities into a hidden numeric score.
#
# Selection rule:
#   1. Require eligibility at Kt_peak = 1.50.
#   2. Prefer candidates that ALSO survive Kt_peak = 2.00 for same geometry.
#   3. Among those, choose minimum added annular mass.
#   4. Break ties using the latest taper start.
#
# The result is only a working profile for detailed transition CAD/FEA.
# =============================================================================

geometry_group = [
    "upper_OD_mm",
    "taper_start_A_mm",
]

candidate_rows = []

for (
    upper_OD_mm,
    start_A_mm,
), group in trade_df.groupby(
    geometry_group,
    sort=True,
):

    row_15 = group.loc[
        np.isclose(
            group[
                "Kt_peak_sensitivity"
            ],
            1.50,
        )
    ]

    row_20 = group.loc[
        np.isclose(
            group[
                "Kt_peak_sensitivity"
            ],
            2.00,
        )
    ]

    pass_15 = (
        len(
            row_15
        ) == 1
        and bool(
            row_15.iloc[
                0
            ][
                "ELIGIBLE_WITHIN_SENSITIVITY_MODEL"
            ]
        )
    )

    pass_20 = (
        len(
            row_20
        ) == 1
        and bool(
            row_20.iloc[
                0
            ][
                "ELIGIBLE_WITHIN_SENSITIVITY_MODEL"
            ]
        )
    )

    reference = (
        row_20.iloc[
            0
        ]
        if len(
            row_20
        ) == 1
        else group.iloc[
            0
        ]
    )

    candidate_rows.append({
        "upper_OD_mm":
            upper_OD_mm,
        "taper_start_A_mm":
            start_A_mm,
        "passes_Kt_peak_1p5":
            pass_15,
        "passes_Kt_peak_2p0":
            pass_20,
        "added_annular_mass_kg_vs_74mm":
            reference[
                "added_annular_mass_kg_vs_74mm"
            ],
        "head_width_reserve_each_side_mm":
            reference[
                "head_width_reserve_each_side_mm"
            ],
        "annular_closure_Kt3_MS_ultimate":
            reference[
                "annular_closure_Kt3_MS_ultimate"
            ],
        "solid_neck_Kt3_MS_ultimate":
            reference[
                "solid_neck_Kt3_MS_ultimate"
            ],
    })


candidate_df = pd.DataFrame(
    candidate_rows
)

preferred_pool = candidate_df.loc[
    candidate_df[
        "passes_Kt_peak_1p5"
    ]
    &
    candidate_df[
        "passes_Kt_peak_2p0"
    ]
].copy()

if preferred_pool.empty:
    preferred_pool = candidate_df.loc[
        candidate_df[
            "passes_Kt_peak_1p5"
        ]
    ].copy()

working_rows = []

if not preferred_pool.empty:

    preferred_pool = preferred_pool.sort_values(
        [
            "added_annular_mass_kg_vs_74mm",
            "taper_start_A_mm",
        ],
        ascending=[
            True,
            False,
        ],
    )

    chosen = preferred_pool.iloc[
        0
    ]

    working_rows.append({
        "status":
            "WORKING_PROFILE_NOT_FROZEN",
        "upper_OD_mm":
            chosen[
                "upper_OD_mm"
            ],
        "taper_start_A_mm":
            chosen[
                "taper_start_A_mm"
            ],
        "taper_end_A_mm":
            E2_BOUNDARY_A_MM,
        "lower_barrel_OD_mm":
            LOWER_OD_MM,
        "retained_internal_ID_mm":
            BARREL_ID_MM,
        "head_root_to_root_width_mm":
            HEAD_ROOT_TO_ROOT_WIDTH_MM,
        "head_reserve_each_side_mm":
            chosen[
                "head_width_reserve_each_side_mm"
            ],
        "added_annular_mass_kg_vs_74mm":
            chosen[
                "added_annular_mass_kg_vs_74mm"
            ],
        "passes_Kt_peak_1p5":
            chosen[
                "passes_Kt_peak_1p5"
            ],
        "passes_Kt_peak_2p0":
            chosen[
                "passes_Kt_peak_2p0"
            ],
        "annular_closure_Kt3_MS_ultimate":
            chosen[
                "annular_closure_Kt3_MS_ultimate"
            ],
        "solid_neck_Kt3_MS_ultimate":
            chosen[
                "solid_neck_Kt3_MS_ultimate"
            ],
        "interpretation":
            (
                "Selected only within the smoothstep / Kt-sensitivity model. "
                "Actual transition Kt must be verified by detailed geometry/FEA."
            ),
    })


working_df = pd.DataFrame(
    working_rows
)

working_df.to_csv(
    OUTPUT_WORKING,
    index=False,
)


# =============================================================================
# CONSOLE REPORT
# =============================================================================

print("=" * 124)
print(
    " PHASE 2E3-B7 — UPPER-BARREL -> SOLID-HEAD TRANSITION / Kt-BUDGET TRADE V0.2"
)
print("=" * 124)

print("\nFROZEN / WORKING GEOMETRY CONNECTION")
print("-" * 124)
print(
    f"Retained lower barrel:            {LOWER_OD_MM:.1f} OD / {BARREL_ID_MM:.1f} ID mm"
)
print(
    f"E2 closure outer face:            {E2_BOUNDARY_A_MM:.6f} mm above A"
)
print(
    f"Working shaft-hole bottom:        {SHAFT_HOLE_BOTTOM_A_MM:.6f} mm above A"
)
print(
    f"B6 root-to-root head width:       {HEAD_ROOT_TO_ROOT_WIDTH_MM:.1f} mm"
)
print(
    f"Working lower ligament:           {WORKING_LOWER_LIGAMENT_MM:.1f} mm"
)

print("\nKt SENSITIVITY MODEL")
print("-" * 124)
print(
    "Kt(s) = 1 + (Kt_peak - 1)*4*s*(1-s)"
)
print(
    "This is a transparent sensitivity envelope, NOT a geometry-derived stress concentration."
)
print(
    f"Peak values checked:              "
    f"{', '.join(f'{x:.2f}' for x in KT_PEAK_VALUES)}"
)

print("\nUPPER-OD BOUNDARY CHECKS — SEPARATE Kt=3 SCREEN")
print("-" * 124)
print(
    f"{'OD':>8}"
    f"{'Ann MSu':>12}"
    f"{'Ann PASS':>12}"
    f"{'Solid MSu':>12}"
    f"{'Solid PASS':>12}"
    f"{'Head res/side':>16}"
)
print("-" * 76)

for _, row in boundary_df.iterrows():
    print(
        f"{row['upper_OD_mm']:>8.0f}"
        f"{row['annular_closure_MS_ultimate']:>12.3f}"
        f"{str(bool(row['annular_closure_Kt3_PASS'])):>12}"
        f"{row['solid_neck_MS_ultimate']:>12.3f}"
        f"{str(bool(row['solid_neck_Kt3_PASS'])):>12}"
        f"{row['head_width_reserve_each_side_mm']:>16.1f}"
    )

print("\nTRANSITION PROFILE TRADE")
print("-" * 124)
print(
    f"{'ODtop':>7}"
    f"{'StartA':>8}"
    f"{'Ktpk':>7}"
    f"{'Len':>9}"
    f"{'ang':>8}"
    f"{'MSlim':>10}"
    f"{'MSult':>10}"
    f"{'Mass+':>10}"
    f"{'Prof':>8}"
    f"{'Elig':>8}"
)
print("-" * 90)

for _, row in trade_df.sort_values(
    [
        "upper_OD_mm",
        "taper_start_A_mm",
        "Kt_peak_sensitivity",
    ]
).iterrows():

    print(
        f"{row['upper_OD_mm']:>7.0f}"
        f"{row['taper_start_A_mm']:>8.0f}"
        f"{row['Kt_peak_sensitivity']:>7.2f}"
        f"{row['transition_length_mm']:>9.1f}"
        f"{row['maximum_geometric_half_angle_deg']:>8.3f}"
        f"{row['minimum_profile_MS_limit']:>10.3f}"
        f"{row['minimum_profile_MS_ultimate']:>10.3f}"
        f"{row['added_annular_mass_kg_vs_74mm']:>10.3f}"
        f"{str(bool(row['PROFILE_PASS'])):>8}"
        f"{str(bool(row['ELIGIBLE_WITHIN_SENSITIVITY_MODEL'])):>8}"
    )

print("\nB7 DISPOSITION")
print("-" * 124)

if working_df.empty:
    print(
        "No candidate satisfied the working profile selection rule."
    )
    print(
        "The upper OD set or taper-start set must be expanded before freezing transition geometry."
    )
else:
    w = working_df.iloc[
        0
    ]

    print(
        "WORKING PROFILE — NOT FROZEN:"
    )
    print(
        f"  74/{BARREL_ID_MM:.0f} mm lower barrel -> "
        f"{w['upper_OD_mm']:.0f}/{BARREL_ID_MM:.0f} mm upper annulus"
    )
    print(
        f"  smoothstep taper start:         {w['taper_start_A_mm']:.1f} mm above A"
    )
    print(
        f"  taper end / closure:            {w['taper_end_A_mm']:.3f} mm above A"
    )
    print(
        f"  head-width reserve per side:    {w['head_reserve_each_side_mm']:.1f} mm"
    )
    print(
        f"  added annular 7075 mass:        {w['added_annular_mass_kg_vs_74mm']:.3f} kg"
    )
    print(
        f"  survives Kt_peak=1.5 envelope:  {bool(w['passes_Kt_peak_1p5'])}"
    )
    print(
        f"  survives Kt_peak=2.0 envelope:  {bool(w['passes_Kt_peak_2p0'])}"
    )
    print(
        f"  closure annulus Kt=3 MSu:       {w['annular_closure_Kt3_MS_ultimate']:+.3f}"
    )
    print(
        f"  solid neck Kt=3 MSu:            {w['solid_neck_Kt3_MS_ultimate']:+.3f}"
    )

print()
print(
    "Do NOT interpret the Kt sensitivity curve as a geometry correlation."
)
print(
    "Next: turn the working external profile into explicit CAD dimensions/fillets "
    "and verify the true local Kt with a dedicated transition analysis / 3D FEA."
)

print("\nOUTPUT FILES")
print("-" * 124)
print(
    f"Transition trade:                 {OUTPUT_TRADE}"
)
print(
    f"Station details:                  {OUTPUT_DETAILS}"
)
print(
    f"Upper-OD boundary checks:         {OUTPUT_BOUNDARY}"
)
print(
    f"Working profile candidate:        {OUTPUT_WORKING}"
)
print(
    f"Summary:                          {OUTPUT_SUMMARY}"
)


summary_lines = [
    "=" * 124,
    " PHASE 2E3-B7 — UPPER-BARREL -> SOLID-HEAD TRANSITION / Kt-BUDGET TRADE V0.2",
    "=" * 124,
    "",
    f"Lower barrel: {LOWER_OD_MM:.1f}/{BARREL_ID_MM:.1f} mm",
    f"Closure outer face: {E2_BOUNDARY_A_MM:.6f} mm above A",
    f"Head width: {HEAD_ROOT_TO_ROOT_WIDTH_MM:.1f} mm",
    "",
]

if working_df.empty:
    summary_lines.append(
        "No working profile selected."
    )
else:
    w = working_df.iloc[
        0
    ]

    summary_lines.extend([
        "Working profile — NOT FROZEN:",
        f"  upper OD = {w['upper_OD_mm']:.1f} mm",
        f"  taper start = {w['taper_start_A_mm']:.1f} mm above A",
        f"  taper end = {w['taper_end_A_mm']:.6f} mm above A",
        f"  added mass = {w['added_annular_mass_kg_vs_74mm']:.6f} kg",
        f"  head reserve/side = {w['head_reserve_each_side_mm']:.6f} mm",
        f"  closure Kt3 MSu = {w['annular_closure_Kt3_MS_ultimate']:+.6f}",
        f"  solid-neck Kt3 MSu = {w['solid_neck_Kt3_MS_ultimate']:+.6f}",
    ])

summary_lines.extend([
    "",
    "Actual geometry-derived Kt remains OPEN and must be verified later.",
    "=" * 124,
])

OUTPUT_SUMMARY.write_text(
    "\n".join(
        summary_lines
    ),
    encoding="utf-8",
)

print("=" * 124)


if __name__ == "__main__":
    pass
