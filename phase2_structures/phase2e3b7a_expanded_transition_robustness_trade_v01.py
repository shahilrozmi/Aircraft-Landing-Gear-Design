from pathlib import Path
import io
import math
import runpy
from contextlib import redirect_stdout

import numpy as np
import pandas as pd


# =============================================================================
# LANDING GEAR DESIGN PROJECT
# PHASE 2E3-B7A — EXPANDED TRANSITION ROBUSTNESS / Kt-CAPACITY TRADE V0.1
#
# PURPOSE
#   Expand the B7 transition study because the first 102/64 mm working profile
#   is structurally too marginal for a sensible preliminary freeze:
#
#       profile at Kt_peak = 1.50:   ultimate MS ≈ +0.002
#       profile at Kt_peak = 2.00:   FAIL
#       closure annulus at Kt = 3:   ultimate MS ≈ +0.019
#
#   Rather than carry that near-zero-margin geometry into CAD, this script
#   expands the external upper-barrel diameter trade and calculates an explicit
#   Kt_peak CAPACITY for each taper geometry.
#
# CANDIDATES
#   Upper annular OD:
#       102, 104, 106, 108, 110, 112 mm
#
#   Smoothstep taper start:
#       275, 300, 325, 350 mm above axle datum A
#
#   The internal bore remains frozen at 64 mm.
#   The taper still ends at the E2 pressure-closure outer face.
#
# STRESS MODEL
#   Reuses the corrected B5B mechanics:
#       - current Phase 1 mechanical load envelope,
#       - 7075-T6 project screening values 503 / 572 MPa,
#       - thick-wall pressure stresses,
#       - conservative simultaneous pressure + mechanical load,
#       - Kt applied to bending only.
#
# Kt CAPACITY
#   For each geometry, bisection finds the largest Kt_peak in:
#
#       1.0 <= Kt_peak <= 3.0
#
#   for which EVERY sampled profile station passes BOTH:
#
#       limit vs 7075 yield screen
#       ultimate vs 7075 UTS screen
#
#   The same sensitivity shape is retained:
#
#       Kt(s) = 1 + (Kt_peak - 1) * 4s(1-s)
#
#   This is still a sensitivity envelope, NOT a geometry-derived correlation.
#
# SEPARATE LOCAL ROBUSTNESS GATES
#   Every candidate also receives:
#
#       - annular closure section at Kt = 3,
#       - solid head neck at shaft-hole bottom at Kt = 3,
#       - head-width reserve inside the B6 115 mm root-to-root envelope.
#
# WORKING-CANDIDATE RULE
#   A geometry is eligible for the next CAD/detail step if:
#
#       1. profile passes Kt_peak = 2.0,
#       2. annular closure passes Kt = 3,
#       3. solid neck passes Kt = 3,
#       4. upper OD fits within the 115 mm root-to-root head width.
#
#   Selection among eligible geometries:
#
#       - smallest upper OD first,
#       - latest taper start second.
#
#   This is a transparent preliminary packaging/mass rule, NOT final
#   optimization.
#
# OUTPUTS
#   phase2e3b7a_expanded_trade.csv
#   phase2e3b7a_kt_capacity.csv
#   phase2e3b7a_station_details.csv
#   phase2e3b7a_working_profile.csv
#   phase2e3b7a_summary.txt
# =============================================================================


HERE = Path(__file__).resolve().parent

B5B_PY = HERE / "phase2e3b5b_upper_barrel_reinforcement_profile_v01.py"
B6_WORKING = HERE / "phase2e3b6_working_candidate_record.csv"

OUTPUT_TRADE = HERE / "phase2e3b7a_expanded_trade.csv"
OUTPUT_CAPACITY = HERE / "phase2e3b7a_kt_capacity.csv"
OUTPUT_DETAILS = HERE / "phase2e3b7a_station_details.csv"
OUTPUT_WORKING = HERE / "phase2e3b7a_working_profile.csv"
OUTPUT_SUMMARY = HERE / "phase2e3b7a_summary.txt"


# =============================================================================
# CANDIDATE SETS
# =============================================================================

UPPER_OD_VALUES_MM = [
    102.0,
    104.0,
    106.0,
    108.0,
    110.0,
    112.0,
]

TAPER_START_VALUES_A_MM = [
    275.0,
    300.0,
    325.0,
    350.0,
]

DISCRETE_KT_PEAK_VALUES = [
    1.50,
    1.75,
    2.00,
    2.25,
]

KT_CAPACITY_LOWER = 1.0
KT_CAPACITY_UPPER = 3.0
KT_CAPACITY_TOL = 1e-4

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
        end_A_mm,
        step_mm,
    ).tolist()

    if (
        not z
        or abs(
            z[-1]
            - end_A_mm
        ) > 1e-12
    ):
        z.append(
            end_A_mm
        )

    z = np.array(
        z,
        dtype=float,
    )

    baseline_area_mm2 = (
        annulus_area_mm2(
            lower_OD_mm,
            ID_mm,
        )
    )

    added_area_m2 = []

    for zi in z:

        OD = profile_OD_mm(
            zi,
            start_A_mm,
            end_A_mm,
            lower_OD_mm,
            upper_OD_mm,
        )

        added_area_m2.append(
            (
                annulus_area_mm2(
                    OD,
                    ID_mm,
                )
                - baseline_area_mm2
            )
            * 1e-6
        )

    volume_added_m3 = np.trapezoid(
        np.array(
            added_area_m2
        ),
        z
        * 1e-3,
    )

    return (
        RHO_7075_KG_M3
        * volume_added_m3
    )


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
        run_name="phase2e3b5b_reuse_for_b7a",
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

PROFILE_SCAN_START_A_MM = float(
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


# =============================================================================
# B6 HEAD WIDTH
# =============================================================================

b6 = read_csv(
    B6_WORKING
)

if b6.empty:
    raise ValueError(
        "B6 working candidate record is empty."
    )

HEAD_ROOT_TO_ROOT_WIDTH_MM = float(
    b6.iloc[
        0
    ][
        "root_to_root_head_width_mm"
    ]
)


# =============================================================================
# PROFILE EVALUATION
# =============================================================================

def station_grid(
    start_scan_A_mm,
    end_A_mm,
    step_mm,
):
    stations = np.arange(
        start_scan_A_mm,
        end_A_mm,
        step_mm,
    ).tolist()

    if (
        not stations
        or abs(
            stations[-1]
            - end_A_mm
        ) > 1e-12
    ):
        stations.append(
            end_A_mm
        )

    return stations


STATIONS_A_MM = station_grid(
    PROFILE_SCAN_START_A_MM,
    E2_BOUNDARY_A_MM,
    PROFILE_STEP_MM,
)


def evaluate_profile(
    upper_OD_mm,
    taper_start_A_mm,
    Kt_peak,
    collect_details=False,
):
    min_limit_MS = np.inf
    min_ultimate_MS = np.inf

    gov_limit = None
    gov_ultimate = None

    details = []

    profile_pass = True

    for zA_mm in STATIONS_A_MM:

        OD_mm = profile_OD_mm(
            zA_mm,
            taper_start_A_mm,
            E2_BOUNDARY_A_MM,
            LOWER_OD_MM,
            upper_OD_mm,
        )

        local_Kt = profile_Kt(
            zA_mm,
            taper_start_A_mm,
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

        if lim["MS"] < min_limit_MS:
            min_limit_MS = float(
                lim["MS"]
            )

            gov_limit = {
                "station_A_mm":
                    zA_mm,
                "station_U_mm":
                    zA_mm
                    - h_UA_static_m
                    * 1000.0,
                "OD_mm":
                    OD_mm,
                "local_Kt":
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

        if ult["MS"] < min_ultimate_MS:
            min_ultimate_MS = float(
                ult["MS"]
            )

            gov_ultimate = {
                "station_A_mm":
                    zA_mm,
                "station_U_mm":
                    zA_mm
                    - h_UA_static_m
                    * 1000.0,
                "OD_mm":
                    OD_mm,
                "local_Kt":
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

        station_pass = (
            lim["MS"] >= 0.0
            and ult["MS"] >= 0.0
        )

        if not station_pass:
            profile_pass = False

        if collect_details:
            details.append({
                "upper_OD_mm":
                    upper_OD_mm,
                "taper_start_A_mm":
                    taper_start_A_mm,
                "Kt_peak":
                    Kt_peak,
                "station_A_mm":
                    zA_mm,
                "station_U_mm":
                    zA_mm
                    - h_UA_static_m
                    * 1000.0,
                "profile_OD_mm":
                    OD_mm,
                "local_Kt":
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
                    station_pass,
            })

    return {
        "PROFILE_PASS":
            profile_pass,
        "minimum_profile_MS_limit":
            min_limit_MS,
        "minimum_profile_MS_ultimate":
            min_ultimate_MS,
        "governing_limit":
            gov_limit,
        "governing_ultimate":
            gov_ultimate,
        "details":
            details,
    }


def kt_peak_capacity(
    upper_OD_mm,
    taper_start_A_mm,
):
    """
    Largest Kt_peak in [1, 3] for which the full profile passes.
    """

    low = (
        KT_CAPACITY_LOWER
    )

    high = (
        KT_CAPACITY_UPPER
    )

    low_eval = evaluate_profile(
        upper_OD_mm,
        taper_start_A_mm,
        low,
        collect_details=False,
    )

    if not low_eval[
        "PROFILE_PASS"
    ]:
        return np.nan

    high_eval = evaluate_profile(
        upper_OD_mm,
        taper_start_A_mm,
        high,
        collect_details=False,
    )

    if high_eval[
        "PROFILE_PASS"
    ]:
        return high

    while (
        high - low
        > KT_CAPACITY_TOL
    ):

        mid = (
            low + high
        ) / 2.0

        mid_eval = evaluate_profile(
            upper_OD_mm,
            taper_start_A_mm,
            mid,
            collect_details=False,
        )

        if mid_eval[
            "PROFILE_PASS"
        ]:
            low = mid
        else:
            high = mid

    return low


# =============================================================================
# BOUNDARY CHECKS
# =============================================================================

boundary_rows = []

for upper_OD_mm in UPPER_OD_VALUES_MM:

    ann_lim = governing_annular(
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

    solid_lim = governing_solid(
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

    reserve_total_mm = (
        HEAD_ROOT_TO_ROOT_WIDTH_MM
        - upper_OD_mm
    )

    boundary_rows.append({
        "upper_OD_mm":
            upper_OD_mm,

        "annular_closure_MS_limit_Kt3":
            ann_lim[
                "MS"
            ],
        "annular_closure_MS_ultimate_Kt3":
            ann_ult[
                "MS"
            ],
        "annular_closure_PASS_Kt3":
            (
                ann_lim[
                    "MS"
                ] >= 0.0
                and ann_ult[
                    "MS"
                ] >= 0.0
            ),

        "solid_neck_MS_limit_Kt3":
            solid_lim[
                "MS"
            ],
        "solid_neck_MS_ultimate_Kt3":
            solid_ult[
                "MS"
            ],
        "solid_neck_PASS_Kt3":
            (
                solid_lim[
                    "MS"
                ] >= 0.0
                and solid_ult[
                    "MS"
                ] >= 0.0
            ),

        "head_width_total_reserve_mm":
            reserve_total_mm,
        "head_width_reserve_each_side_mm":
            reserve_total_mm
            / 2.0,
        "head_fit_PASS":
            reserve_total_mm
            >= 0.0,
    })


boundary_df = pd.DataFrame(
    boundary_rows
)


# =============================================================================
# DISCRETE TRADE + Kt CAPACITY
# =============================================================================

trade_rows = []
capacity_rows = []
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

        transition_length_mm = (
            E2_BOUNDARY_A_MM
            - start_A_mm
        )

        delta_D_mm = (
            upper_OD_mm
            - LOWER_OD_MM
        )

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

        capacity = kt_peak_capacity(
            upper_OD_mm,
            start_A_mm,
        )

        pass_Kt2 = (
            np.isfinite(
                capacity
            )
            and capacity
            >= 2.0
            - KT_CAPACITY_TOL
        )

        fully_eligible = (
            pass_Kt2
            and bool(
                boundary[
                    "annular_closure_PASS_Kt3"
                ]
            )
            and bool(
                boundary[
                    "solid_neck_PASS_Kt3"
                ]
            )
            and bool(
                boundary[
                    "head_fit_PASS"
                ]
            )
        )

        capacity_rows.append({
            "upper_OD_mm":
                upper_OD_mm,
            "taper_start_A_mm":
                start_A_mm,
            "transition_length_mm":
                transition_length_mm,
            "maximum_geometric_half_angle_deg":
                max_half_angle_deg,
            "Kt_peak_capacity":
                capacity,
            "passes_Kt_peak_2p0":
                pass_Kt2,

            "annular_closure_MS_ultimate_Kt3":
                boundary[
                    "annular_closure_MS_ultimate_Kt3"
                ],
            "annular_closure_PASS_Kt3":
                boundary[
                    "annular_closure_PASS_Kt3"
                ],

            "solid_neck_MS_ultimate_Kt3":
                boundary[
                    "solid_neck_MS_ultimate_Kt3"
                ],
            "solid_neck_PASS_Kt3":
                boundary[
                    "solid_neck_PASS_Kt3"
                ],

            "head_width_reserve_each_side_mm":
                boundary[
                    "head_width_reserve_each_side_mm"
                ],
            "head_fit_PASS":
                boundary[
                    "head_fit_PASS"
                ],

            "added_annular_mass_kg_vs_74mm":
                added_mass_kg,

            "ELIGIBLE_FOR_NEXT_DETAIL_STEP":
                fully_eligible,
        })

        for Kt_peak in DISCRETE_KT_PEAK_VALUES:

            result = evaluate_profile(
                upper_OD_mm,
                start_A_mm,
                Kt_peak,
                collect_details=True,
            )

            detail_rows.extend(
                result[
                    "details"
                ]
            )

            trade_rows.append({
                "upper_OD_mm":
                    upper_OD_mm,
                "taper_start_A_mm":
                    start_A_mm,
                "transition_length_mm":
                    transition_length_mm,
                "maximum_geometric_half_angle_deg":
                    max_half_angle_deg,
                "Kt_peak":
                    Kt_peak,

                "minimum_profile_MS_limit":
                    result[
                        "minimum_profile_MS_limit"
                    ],
                "minimum_profile_MS_ultimate":
                    result[
                        "minimum_profile_MS_ultimate"
                    ],

                "governing_ultimate_station_A_mm":
                    result[
                        "governing_ultimate"
                    ][
                        "station_A_mm"
                    ],
                "governing_ultimate_station_U_mm":
                    result[
                        "governing_ultimate"
                    ][
                        "station_U_mm"
                    ],
                "governing_ultimate_OD_mm":
                    result[
                        "governing_ultimate"
                    ][
                        "OD_mm"
                    ],
                "governing_ultimate_local_Kt":
                    result[
                        "governing_ultimate"
                    ][
                        "local_Kt"
                    ],
                "governing_ultimate_case":
                    result[
                        "governing_ultimate"
                    ][
                        "case"
                    ],
                "governing_ultimate_vm_MPa":
                    result[
                        "governing_ultimate"
                    ][
                        "vm_MPa"
                    ],

                "PROFILE_PASS":
                    result[
                        "PROFILE_PASS"
                    ],
                "added_annular_mass_kg_vs_74mm":
                    added_mass_kg,
            })


trade_df = pd.DataFrame(
    trade_rows
)

capacity_df = pd.DataFrame(
    capacity_rows
)

details_df = pd.DataFrame(
    detail_rows
)

trade_df.to_csv(
    OUTPUT_TRADE,
    index=False,
)

capacity_df.to_csv(
    OUTPUT_CAPACITY,
    index=False,
)

details_df.to_csv(
    OUTPUT_DETAILS,
    index=False,
)


# =============================================================================
# WORKING SELECTION
# =============================================================================

eligible = capacity_df.loc[
    capacity_df[
        "ELIGIBLE_FOR_NEXT_DETAIL_STEP"
    ]
].copy()

working_rows = []

if not eligible.empty:

    eligible = eligible.sort_values(
        [
            "upper_OD_mm",
            "taper_start_A_mm",
        ],
        ascending=[
            True,
            False,
        ],
    )

    chosen = eligible.iloc[
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
        "lower_OD_mm":
            LOWER_OD_MM,
        "retained_ID_mm":
            BARREL_ID_MM,

        "Kt_peak_capacity":
            chosen[
                "Kt_peak_capacity"
            ],

        "annular_closure_MS_ultimate_Kt3":
            chosen[
                "annular_closure_MS_ultimate_Kt3"
            ],

        "solid_neck_MS_ultimate_Kt3":
            chosen[
                "solid_neck_MS_ultimate_Kt3"
            ],

        "head_width_reserve_each_side_mm":
            chosen[
                "head_width_reserve_each_side_mm"
            ],

        "added_annular_mass_kg_vs_74mm":
            chosen[
                "added_annular_mass_kg_vs_74mm"
            ],

        "selection_rule":
            (
                "Smallest upper OD passing Kt_peak=2 profile + Kt=3 closure "
                "+ Kt=3 solid neck + head-fit; latest taper start breaks tie."
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

print("=" * 126)
print(
    " PHASE 2E3-B7A — EXPANDED TRANSITION ROBUSTNESS / Kt-CAPACITY TRADE V0.1"
)
print("=" * 126)

print("\nGEOMETRY CONNECTION")
print("-" * 126)
print(
    f"Lower barrel retained:            {LOWER_OD_MM:.1f} OD / {BARREL_ID_MM:.1f} ID mm"
)
print(
    f"E2 closure outer face:            {E2_BOUNDARY_A_MM:.6f} mm above A"
)
print(
    f"Shaft-hole bottom:                {SHAFT_HOLE_BOTTOM_A_MM:.6f} mm above A"
)
print(
    f"B6 root-to-root head width:       {HEAD_ROOT_TO_ROOT_WIDTH_MM:.1f} mm"
)

print("\nUPPER-OD LOCAL ROBUSTNESS — Kt=3")
print("-" * 126)
print(
    f"{'OD':>7}"
    f"{'Ann MSu':>12}"
    f"{'Ann PASS':>11}"
    f"{'Solid MSu':>12}"
    f"{'Solid PASS':>12}"
    f"{'Res/side':>12}"
)
print("-" * 70)

for _, row in boundary_df.iterrows():
    print(
        f"{row['upper_OD_mm']:>7.0f}"
        f"{row['annular_closure_MS_ultimate_Kt3']:>12.3f}"
        f"{str(bool(row['annular_closure_PASS_Kt3'])):>11}"
        f"{row['solid_neck_MS_ultimate_Kt3']:>12.3f}"
        f"{str(bool(row['solid_neck_PASS_Kt3'])):>12}"
        f"{row['head_width_reserve_each_side_mm']:>12.1f}"
    )

print("\nPROFILE Kt_PEAK CAPACITY")
print("-" * 126)
print(
    f"{'ODtop':>7}"
    f"{'StartA':>8}"
    f"{'Len':>9}"
    f"{'ang':>8}"
    f"{'Kt_cap':>10}"
    f"{'>=2?':>8}"
    f"{'Ann3':>8}"
    f"{'Sol3':>8}"
    f"{'Res/s':>9}"
    f"{'Mass+':>10}"
    f"{'Elig':>8}"
)
print("-" * 105)

for _, row in capacity_df.sort_values(
    [
        "upper_OD_mm",
        "taper_start_A_mm",
    ]
).iterrows():

    kt_text = (
        f"{row['Kt_peak_capacity']:.3f}"
        if np.isfinite(
            row[
                "Kt_peak_capacity"
            ]
        )
        else "FAIL@1"
    )

    print(
        f"{row['upper_OD_mm']:>7.0f}"
        f"{row['taper_start_A_mm']:>8.0f}"
        f"{row['transition_length_mm']:>9.1f}"
        f"{row['maximum_geometric_half_angle_deg']:>8.3f}"
        f"{kt_text:>10}"
        f"{str(bool(row['passes_Kt_peak_2p0'])):>8}"
        f"{str(bool(row['annular_closure_PASS_Kt3'])):>8}"
        f"{str(bool(row['solid_neck_PASS_Kt3'])):>8}"
        f"{row['head_width_reserve_each_side_mm']:>9.1f}"
        f"{row['added_annular_mass_kg_vs_74mm']:>10.3f}"
        f"{str(bool(row['ELIGIBLE_FOR_NEXT_DETAIL_STEP'])):>8}"
    )

print("\nB7A DISPOSITION")
print("-" * 126)

if working_df.empty:
    print(
        "No candidate meets the explicit Kt_peak>=2.0 + Kt=3 local robustness gates."
    )
    print(
        "Do not proceed to detailed CAD yet; architecture/profile expansion is required."
    )
else:
    w = working_df.iloc[
        0
    ]

    print(
        "WORKING PROFILE FOR NEXT DETAIL STEP — NOT FROZEN:"
    )
    print(
        f"  lower barrel:                   {w['lower_OD_mm']:.0f}/{w['retained_ID_mm']:.0f} mm"
    )
    print(
        f"  upper annulus:                  {w['upper_OD_mm']:.0f}/{w['retained_ID_mm']:.0f} mm"
    )
    print(
        f"  taper start:                    {w['taper_start_A_mm']:.1f} mm above A"
    )
    print(
        f"  taper end:                      {w['taper_end_A_mm']:.3f} mm above A"
    )
    print(
        f"  Kt_peak capacity:               {w['Kt_peak_capacity']:.3f}"
    )
    print(
        f"  closure annulus Kt=3 MSu:       {w['annular_closure_MS_ultimate_Kt3']:+.3f}"
    )
    print(
        f"  solid neck Kt=3 MSu:            {w['solid_neck_MS_ultimate_Kt3']:+.3f}"
    )
    print(
        f"  head reserve each side:         {w['head_width_reserve_each_side_mm']:.1f} mm"
    )
    print(
        f"  added annular 7075 mass:        {w['added_annular_mass_kg_vs_74mm']:.3f} kg"
    )

print()
print(
    "Actual geometry-derived transition Kt is still OPEN."
)
print(
    "Once a working geometry survives this trade, the next task is to define explicit CAD radii/tangent geometry "
    "and verify the real stress concentration with local analysis / 3D FEA."
)

print("\nOUTPUT FILES")
print("-" * 126)
print(
    f"Expanded trade:                   {OUTPUT_TRADE}"
)
print(
    f"Kt capacity summary:              {OUTPUT_CAPACITY}"
)
print(
    f"Station details:                  {OUTPUT_DETAILS}"
)
print(
    f"Working profile:                  {OUTPUT_WORKING}"
)
print(
    f"Summary:                          {OUTPUT_SUMMARY}"
)


# =============================================================================
# SUMMARY FILE
# =============================================================================

summary_lines = [
    "=" * 126,
    " PHASE 2E3-B7A — EXPANDED TRANSITION ROBUSTNESS / Kt-CAPACITY TRADE V0.1",
    "=" * 126,
    "",
    f"Lower barrel: {LOWER_OD_MM:.1f}/{BARREL_ID_MM:.1f} mm",
    f"Head width: {HEAD_ROOT_TO_ROOT_WIDTH_MM:.1f} mm",
    "",
]

if working_df.empty:
    summary_lines.append(
        "No working profile satisfied the robustness gates."
    )
else:
    w = working_df.iloc[
        0
    ]

    summary_lines.extend([
        "Working profile — NOT FROZEN:",
        f"  upper annulus = {w['upper_OD_mm']:.1f}/{w['retained_ID_mm']:.1f} mm",
        f"  taper start A = {w['taper_start_A_mm']:.1f} mm",
        f"  taper end A = {w['taper_end_A_mm']:.6f} mm",
        f"  Kt_peak capacity = {w['Kt_peak_capacity']:.6f}",
        f"  closure annulus Kt3 MSu = {w['annular_closure_MS_ultimate_Kt3']:+.6f}",
        f"  solid neck Kt3 MSu = {w['solid_neck_MS_ultimate_Kt3']:+.6f}",
        f"  reserve/side = {w['head_width_reserve_each_side_mm']:.6f} mm",
        f"  added mass = {w['added_annular_mass_kg_vs_74mm']:.6f} kg",
    ])

summary_lines.extend([
    "",
    "Actual geometry-derived Kt remains open pending CAD/local analysis.",
    "=" * 126,
])

OUTPUT_SUMMARY.write_text(
    "\n".join(
        summary_lines
    ),
    encoding="utf-8",
)

print("=" * 126)


if __name__ == "__main__":
    pass
