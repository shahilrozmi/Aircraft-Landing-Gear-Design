from pathlib import Path
import ast
import math

import numpy as np
import pandas as pd


# =============================================================================
# LANDING GEAR DESIGN PROJECT
# PHASE 2E3-B5B — 7075 UPPER-BARREL / SOLID-HEAD REINFORCEMENT PROFILE V0.1
#
# PURPOSE
#   Correct the material-basis issue confirmed in Phase 2E3-B5A and determine
#   where the retained 74/64 mm 7075-T6 barrel must be locally reinforced.
#
#   B5A established:
#       - historical 74/64 barrel margins used 300M allowables,
#       - 74/64 mm 7075 is NOT adequate at the E2/E3 boundary,
#       - local upper-head reinforcement is therefore required.
#
#   This script maps the CURRENT load envelope along the barrel axis and screens
#   a 7075-T6 annular barrel including conservative internal-pressure stresses.
#
#   It also screens the solid neck immediately above the E2 pressure closure.
#
#   IMPORTANT:
#   - no redesign is frozen here,
#   - Kt is a bending sensitivity only,
#   - pressure and mechanical load peaks are conservatively treated as
#     simultaneous,
#   - 7075 values remain preliminary project material screens, not
#     certification allowables,
#   - no local boss hole / fillet / shaft-fit 3D stress is solved here.
#
# OUTPUTS
#   phase2e3b5b_annular_profile.csv
#   phase2e3b5b_profile_summary.csv
#   phase2e3b5b_solid_neck_screen.csv
#   phase2e3b5b_summary.txt
# =============================================================================


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.resolve()

LOAD_CSV = (
    PROJECT_ROOT
    / "phase1_loads"
    / "phase1_load_envelope.csv"
)

D9_PY = HERE / "phase2_upper_trunnion_sizing.py"
D5_PY = HERE / "phase2_bushing_material_gland.py"
E2_BASELINE = HERE / "phase2e2_v1_baseline.csv"

OUTPUT_PROFILE = HERE / "phase2e3b5b_annular_profile.csv"
OUTPUT_PROFILE_SUMMARY = HERE / "phase2e3b5b_profile_summary.csv"
OUTPUT_SOLID = HERE / "phase2e3b5b_solid_neck_screen.csv"
OUTPUT_SUMMARY = HERE / "phase2e3b5b_summary.txt"


# =============================================================================
# PRELIMINARY PROJECT MATERIAL / PRESSURE SCREENS
# =============================================================================

SY_7075_MPa = 503.0
SU_7075_MPa = 572.0

# Frozen Phase 2E2 pressure screen at maximum physical stroke:
#   physical differential pressure ~= 9.292 MPa
#   ultimate pressure screen = 1.5 x physical ~= 13.938 MPa
#
# These are not invented values. They are retained Phase 2E2 project values.
P_LIMIT_DIFF_MPa = 9.292
P_ULT_DIFF_MPa = 13.938

KT_VALUES = [
    1.0,
    1.5,
    2.0,
    2.5,
    3.0,
]

# Working E3-B5 head geometry candidate.
WORKING_JOURNAL_D_MM = 36.0
WORKING_LOWER_LIGAMENT_MM = 10.0

# OD search grid for reinforced annular barrel / solid neck.
OD_MIN_MM = 74.0
OD_MAX_MM = 140.0
OD_STEP_MM = 0.5

# Axial profile resolution.
STATION_STEP_MM = 10.0


# =============================================================================
# UTILITIES
# =============================================================================

def normalize(text):
    return "".join(
        ch
        for ch in str(text).lower()
        if ch.isalnum()
    )


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


def find_column(df, aliases):
    norm = {
        normalize(col): col
        for col in df.columns
    }

    for alias in aliases:
        key = normalize(alias)

        if key in norm:
            return norm[key]

    return None


def find_parameter(df, aliases):
    pcol = find_column(
        df,
        ["parameter"],
    )

    vcol = find_column(
        df,
        ["value"],
    )

    if pcol is None or vcol is None:
        return None

    pnorm = (
        df[pcol]
        .astype(str)
        .map(normalize)
    )

    for alias in aliases:
        rows = df.loc[
            pnorm == normalize(alias)
        ]

        if not rows.empty:
            return rows.iloc[0][vcol]

    return None


def literal_assignments(path):
    if not path.exists():
        raise FileNotFoundError(
            f"Required source not found:\n{path}"
        )

    source = path.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    tree = ast.parse(
        source,
        filename=str(path),
    )

    out = {}

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue

        try:
            value = ast.literal_eval(node.value)
        except Exception:
            continue

        for target in node.targets:
            if isinstance(target, ast.Name):
                out[target.id] = value

    return out


def force_columns(df, level):
    result = {}

    for comp in ["Fx", "Fy", "Fz"]:
        col = find_column(
            df,
            [
                f"{comp} {level} (kN)",
                f"{comp}_{level}_kN",
                f"{comp}_{level}",
            ],
        )

        if col is None:
            raise KeyError(
                f"Could not resolve {comp} {level}. "
                f"Columns: {list(df.columns)}"
            )

        result[comp] = col

    return result


def vm_3d(
    sigma_z,
    sigma_theta,
    sigma_r,
    tau_ztheta,
):
    return math.sqrt(
        0.5
        * (
            (sigma_z - sigma_theta)**2
            + (sigma_theta - sigma_r)**2
            + (sigma_r - sigma_z)**2
        )
        + 3.0
        * tau_ztheta**2
    )


# =============================================================================
# SOURCE GEOMETRY
# =============================================================================

loads = read_csv(
    LOAD_CSV
)

e2 = read_csv(
    E2_BASELINE
)

d9 = literal_assignments(
    D9_PY
)

d5 = literal_assignments(
    D5_PY
)

e_m = float(
    d9["e_m"]
)

rt_m = float(
    d9["rt_m"]
)

h_UA_static_m = float(
    d9["h_UA_static_m"]
)

preferred_hL_mm = float(
    d5.get(
        "preferred_hL_mm",
        250.0,
    )
)

preferred_hU_mm = float(
    d5.get(
        "preferred_hU_mm",
        400.0,
    )
)

barrel_OD_mm = float(
    find_parameter(
        e2,
        [
            "barrel_OD",
            "barrel_OD_mm",
        ],
    )
)

barrel_ID_mm = float(
    find_parameter(
        e2,
        [
            "barrel_ID",
            "barrel_ID_mm",
        ],
    )
)

e2_boundary_above_U_mm = float(
    find_parameter(
        e2,
        [
            "preliminary_E3_interface_outer_face_above_U",
        ],
    )
)

# Working 10-mm lower ligament puts the bottom of the transverse 36-mm shaft
# exactly 10 mm above the E2 boundary.
shaft_bottom_above_U_mm = (
    e2_boundary_above_U_mm
    + WORKING_LOWER_LIGAMENT_MM
)

shaft_center_above_U_mm = (
    shaft_bottom_above_U_mm
    + WORKING_JOURNAL_D_MM / 2.0
)


case_col = find_column(
    loads,
    [
        "Load Case",
        "case",
        "load_case",
    ],
)

if case_col is None:
    raise KeyError(
        "Could not resolve load-case column."
    )

limit_cols = force_columns(
    loads,
    "Limit",
)

ultimate_cols = force_columns(
    loads,
    "Ultimate",
)


# =============================================================================
# SECTION RESULTANTS
# =============================================================================

def resultants_at_h(
    Fx_kN,
    Fy_kN,
    Fz_kN,
    h_from_A_mm,
):
    h_m = (
        h_from_A_mm
        / 1000.0
    )

    arm_m = (
        rt_m
        + h_m
    )

    Mx_kNm = (
        e_m
        * Fz_kN
        + arm_m
        * Fy_kN
    )

    My_kNm = (
        -arm_m
        * Fx_kN
    )

    Mz_kNm = (
        -e_m
        * Fx_kN
    )

    return {
        "Fx_kN":
            Fx_kN,
        "Fy_kN":
            Fy_kN,
        "Fz_kN":
            Fz_kN,
        "Mx_kNm":
            Mx_kNm,
        "My_kNm":
            My_kNm,
        "Mz_kNm":
            Mz_kNm,
        "Mb_kNm":
            math.hypot(
                Mx_kNm,
                My_kNm,
            ),
    }


# =============================================================================
# COMBINED MECHANICAL + INTERNAL PRESSURE STRESS
# =============================================================================

def annular_properties(
    OD_mm,
    ID_mm,
):
    ro = (
        OD_mm
        / 2000.0
    )

    ri = (
        ID_mm
        / 2000.0
    )

    if (
        ro <= 0.0
        or ri < 0.0
        or ri >= ro
    ):
        raise ValueError(
            f"Invalid annulus OD={OD_mm}, ID={ID_mm}"
        )

    A = (
        math.pi
        * (
            ro**2
            - ri**2
        )
    )

    I = (
        math.pi
        / 4.0
        * (
            ro**4
            - ri**4
        )
    )

    J = (
        math.pi
        / 2.0
        * (
            ro**4
            - ri**4
        )
    )

    return {
        "ro_m":
            ro,
        "ri_m":
            ri,
        "A_m2":
            A,
        "I_m4":
            I,
        "J_m4":
            J,
    }


def annular_combined_vm_MPa(
    resultant,
    OD_mm,
    ID_mm,
    pressure_diff_MPa,
    Kt_bending,
):
    """
    Conservative envelope over:
      - inner and outer cylinder surface,
      - +/- structural axial sign,
      - +/- bending sign.

    Pressure is thick-wall Lame stress with closed-end axial pressure stress.
    Kt is applied to bending only.
    """

    props = annular_properties(
        OD_mm,
        ID_mm,
    )

    ro = props["ro_m"]
    ri = props["ri_m"]
    A = props["A_m2"]
    I = props["I_m4"]
    J = props["J_m4"]

    p = (
        pressure_diff_MPa
        * 1e6
    )

    N = (
        abs(
            resultant["Fz_kN"]
        )
        * 1000.0
    )

    Mb = (
        abs(
            resultant["Mb_kNm"]
        )
        * 1000.0
    )

    T = (
        abs(
            resultant["Mz_kNm"]
        )
        * 1000.0
    )

    sigma_ax_mag = (
        N / A
    )

    denom = (
        ro**2
        - ri**2
    )

    # Closed-end axial pressure stress is constant through wall.
    sigma_z_pressure = (
        p
        * ri**2
        / denom
    )

    surface_rows = []

    for surface, r in [
        ("INNER", ri),
        ("OUTER", ro),
    ]:

        sigma_b_mag = (
            Kt_bending
            * Mb
            * r
            / I
        )

        tau_t = (
            T
            * r
            / J
        )

        if surface == "INNER":
            sigma_r = (
                -p
            )

            sigma_theta = (
                p
                * (
                    ro**2
                    + ri**2
                )
                / denom
            )

        else:
            sigma_r = 0.0

            sigma_theta = (
                2.0
                * p
                * ri**2
                / denom
            )

        # Sign-envelope structural axial and bending contributions because the
        # preliminary project convention does not yet freeze local material
        # fiber orientation / signed stress at a specific circumferential point.
        for axial_sign in [
            -1.0,
            +1.0,
        ]:
            for bend_sign in [
                -1.0,
                +1.0,
            ]:

                sigma_z = (
                    sigma_z_pressure
                    + axial_sign
                    * sigma_ax_mag
                    + bend_sign
                    * sigma_b_mag
                )

                vm = vm_3d(
                    sigma_z,
                    sigma_theta,
                    sigma_r,
                    tau_t,
                )

                surface_rows.append({
                    "surface":
                        surface,
                    "sigma_z_MPa":
                        sigma_z / 1e6,
                    "sigma_theta_MPa":
                        sigma_theta / 1e6,
                    "sigma_r_MPa":
                        sigma_r / 1e6,
                    "tau_torsion_MPa":
                        tau_t / 1e6,
                    "vm_MPa":
                        vm / 1e6,
                })

    gov = max(
        surface_rows,
        key=lambda x:
            x["vm_MPa"],
    )

    return gov


def solid_combined_vm_MPa(
    resultant,
    OD_mm,
    Kt_bending,
):
    """
    Solid circular global neck section. No internal pressure acts above the
    pressure closure.
    """

    d = (
        OD_mm
        / 1000.0
    )

    A = (
        math.pi
        / 4.0
        * d**2
    )

    I = (
        math.pi
        / 64.0
        * d**4
    )

    J = (
        math.pi
        / 32.0
        * d**4
    )

    c = (
        d / 2.0
    )

    N = (
        abs(
            resultant["Fz_kN"]
        )
        * 1000.0
    )

    Mb = (
        abs(
            resultant["Mb_kNm"]
        )
        * 1000.0
    )

    T = (
        abs(
            resultant["Mz_kNm"]
        )
        * 1000.0
    )

    sigma_ax_mag = (
        N / A
    )

    sigma_b_mag = (
        Kt_bending
        * Mb
        * c
        / I
    )

    tau_t = (
        T
        * c
        / J
    )

    vm_candidates = []

    for axial_sign in [
        -1.0,
        +1.0,
    ]:
        for bend_sign in [
            -1.0,
            +1.0,
        ]:
            sigma = (
                axial_sign
                * sigma_ax_mag
                + bend_sign
                * sigma_b_mag
            )

            vm = math.sqrt(
                sigma**2
                + 3.0
                * tau_t**2
            )

            vm_candidates.append(
                vm / 1e6
            )

    return max(
        vm_candidates
    )


# =============================================================================
# GOVERNING STRESS AT ONE STATION / ONE OD
# =============================================================================

def governing_annular(
    h_from_A_mm,
    OD_mm,
    Kt,
    level,
):
    if level == "limit":
        cols = limit_cols
        pressure_MPa = (
            P_LIMIT_DIFF_MPa
        )
        allowable_MPa = (
            SY_7075_MPa
        )

    elif level == "ultimate":
        cols = ultimate_cols
        pressure_MPa = (
            P_ULT_DIFF_MPa
        )
        allowable_MPa = (
            SU_7075_MPa
        )

    else:
        raise ValueError(
            f"Unknown level: {level}"
        )

    rows = []

    for _, load in loads.iterrows():

        res = resultants_at_h(
            float(
                load[
                    cols["Fx"]
                ]
            ),
            float(
                load[
                    cols["Fy"]
                ]
            ),
            float(
                load[
                    cols["Fz"]
                ]
            ),
            h_from_A_mm,
        )

        stress = annular_combined_vm_MPa(
            res,
            OD_mm,
            barrel_ID_mm,
            pressure_MPa,
            Kt,
        )

        rows.append({
            "case":
                str(
                    load[
                        case_col
                    ]
                ),
            **stress,
        })

    df = pd.DataFrame(
        rows
    )

    idx = df[
        "vm_MPa"
    ].idxmax()

    gov = df.loc[
        idx
    ]

    return {
        "case":
            gov["case"],
        "surface":
            gov["surface"],
        "vm_MPa":
            float(
                gov[
                    "vm_MPa"
                ]
            ),
        "allowable_MPa":
            allowable_MPa,
        "MS":
            (
                allowable_MPa
                / float(
                    gov[
                        "vm_MPa"
                    ]
                )
                - 1.0
            ),
    }


def governing_solid(
    h_from_A_mm,
    OD_mm,
    Kt,
    level,
):
    if level == "limit":
        cols = limit_cols
        allowable_MPa = SY_7075_MPa

    elif level == "ultimate":
        cols = ultimate_cols
        allowable_MPa = SU_7075_MPa

    else:
        raise ValueError(
            f"Unknown level: {level}"
        )

    rows = []

    for _, load in loads.iterrows():

        res = resultants_at_h(
            float(
                load[
                    cols["Fx"]
                ]
            ),
            float(
                load[
                    cols["Fy"]
                ]
            ),
            float(
                load[
                    cols["Fz"]
                ]
            ),
            h_from_A_mm,
        )

        vm = solid_combined_vm_MPa(
            res,
            OD_mm,
            Kt,
        )

        rows.append({
            "case":
                str(
                    load[
                        case_col
                    ]
                ),
            "vm_MPa":
                vm,
        })

    df = pd.DataFrame(
        rows
    )

    idx = df[
        "vm_MPa"
    ].idxmax()

    gov = df.loc[
        idx
    ]

    return {
        "case":
            gov[
                "case"
            ],
        "vm_MPa":
            float(
                gov[
                    "vm_MPa"
                ]
            ),
        "allowable_MPa":
            allowable_MPa,
        "MS":
            (
                allowable_MPa
                / float(
                    gov[
                        "vm_MPa"
                    ]
                )
                - 1.0
            ),
    }


# =============================================================================
# ANNULAR BARREL PROFILE
# =============================================================================

# Scan from the preferred lower-guide region to the pressure-closure outer face.
start_h_from_A_mm = (
    preferred_hL_mm
)

end_h_from_A_mm = (
    h_UA_static_m
    * 1000.0
    + e2_boundary_above_U_mm
)

stations_mm = list(
    np.arange(
        start_h_from_A_mm,
        end_h_from_A_mm,
        STATION_STEP_MM,
    )
)

if (
    not stations_mm
    or abs(
        stations_mm[-1]
        - end_h_from_A_mm
    ) > 1e-9
):
    stations_mm.append(
        end_h_from_A_mm
    )


profile_rows = []

for Kt in KT_VALUES:

    for h_from_A_mm in stations_mm:

        first_passing_OD = None
        first_limit = None
        first_ultimate = None

        frozen_limit = governing_annular(
            h_from_A_mm,
            barrel_OD_mm,
            Kt,
            "limit",
        )

        frozen_ultimate = governing_annular(
            h_from_A_mm,
            barrel_OD_mm,
            Kt,
            "ultimate",
        )

        for OD_mm in np.arange(
            max(
                OD_MIN_MM,
                barrel_ID_mm
                + OD_STEP_MM,
            ),
            OD_MAX_MM
            + 1e-9,
            OD_STEP_MM,
        ):

            lim = governing_annular(
                h_from_A_mm,
                OD_mm,
                Kt,
                "limit",
            )

            ult = governing_annular(
                h_from_A_mm,
                OD_mm,
                Kt,
                "ultimate",
            )

            if (
                lim["MS"] >= 0.0
                and ult["MS"] >= 0.0
            ):
                first_passing_OD = (
                    OD_mm
                )
                first_limit = lim
                first_ultimate = ult
                break

        profile_rows.append({
            "Kt_bending":
                Kt,
            "station_above_A_mm":
                h_from_A_mm,
            "station_above_U_mm":
                h_from_A_mm
                - h_UA_static_m
                * 1000.0,

            "frozen_74_limit_case":
                frozen_limit[
                    "case"
                ],
            "frozen_74_limit_surface":
                frozen_limit[
                    "surface"
                ],
            "frozen_74_limit_vm_MPa":
                frozen_limit[
                    "vm_MPa"
                ],
            "frozen_74_limit_MS":
                frozen_limit[
                    "MS"
                ],

            "frozen_74_ultimate_case":
                frozen_ultimate[
                    "case"
                ],
            "frozen_74_ultimate_surface":
                frozen_ultimate[
                    "surface"
                ],
            "frozen_74_ultimate_vm_MPa":
                frozen_ultimate[
                    "vm_MPa"
                ],
            "frozen_74_ultimate_MS":
                frozen_ultimate[
                    "MS"
                ],

            "frozen_74_PASS":
                (
                    frozen_limit[
                        "MS"
                    ] >= 0.0
                    and frozen_ultimate[
                        "MS"
                    ] >= 0.0
                ),

            "minimum_passing_OD_mm":
                first_passing_OD,

            "minimum_OD_limit_case":
                (
                    first_limit[
                        "case"
                    ]
                    if first_limit
                    else ""
                ),
            "minimum_OD_limit_vm_MPa":
                (
                    first_limit[
                        "vm_MPa"
                    ]
                    if first_limit
                    else np.nan
                ),
            "minimum_OD_limit_MS":
                (
                    first_limit[
                        "MS"
                    ]
                    if first_limit
                    else np.nan
                ),

            "minimum_OD_ultimate_case":
                (
                    first_ultimate[
                        "case"
                    ]
                    if first_ultimate
                    else ""
                ),
            "minimum_OD_ultimate_vm_MPa":
                (
                    first_ultimate[
                        "vm_MPa"
                    ]
                    if first_ultimate
                    else np.nan
                ),
            "minimum_OD_ultimate_MS":
                (
                    first_ultimate[
                        "MS"
                    ]
                    if first_ultimate
                    else np.nan
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
# PROFILE SUMMARY
# =============================================================================

summary_rows = []

for Kt in KT_VALUES:

    sub = profile_df.loc[
        np.isclose(
            profile_df[
                "Kt_bending"
            ],
            Kt,
        )
    ].sort_values(
        "station_above_A_mm"
    )

    failed74 = sub.loc[
        ~sub[
            "frozen_74_PASS"
        ]
    ]

    first_fail_A_mm = (
        float(
            failed74[
                "station_above_A_mm"
            ].min()
        )
        if not failed74.empty
        else np.nan
    )

    first_fail_U_mm = (
        first_fail_A_mm
        - h_UA_static_m
        * 1000.0
        if np.isfinite(
            first_fail_A_mm
        )
        else np.nan
    )

    max_required_OD = float(
        pd.to_numeric(
            sub[
                "minimum_passing_OD_mm"
            ],
            errors="coerce",
        ).max()
    )

    boundary_row = sub.iloc[
        -1
    ]

    # Values nearest upper guide and U.
    idx_hU = (
        sub[
            "station_above_A_mm"
        ]
        .sub(
            preferred_hU_mm
        )
        .abs()
        .idxmin()
    )

    idx_U = (
        sub[
            "station_above_A_mm"
        ]
        .sub(
            h_UA_static_m
            * 1000.0
        )
        .abs()
        .idxmin()
    )

    row_hU = sub.loc[
        idx_hU
    ]

    row_U = sub.loc[
        idx_U
    ]

    summary_rows.append({
        "Kt_bending":
            Kt,
        "first_station_74mm_fails_above_A_mm":
            first_fail_A_mm,
        "first_station_74mm_fails_above_U_mm":
            first_fail_U_mm,
        "required_OD_near_upper_guide_mm":
            row_hU[
                "minimum_passing_OD_mm"
            ],
        "upper_guide_station_above_A_mm":
            row_hU[
                "station_above_A_mm"
            ],
        "required_OD_near_U_mm":
            row_U[
                "minimum_passing_OD_mm"
            ],
        "U_sample_station_above_A_mm":
            row_U[
                "station_above_A_mm"
            ],
        "required_OD_at_E2_boundary_mm":
            boundary_row[
                "minimum_passing_OD_mm"
            ],
        "maximum_required_OD_over_profile_mm":
            max_required_OD,
    })


profile_summary_df = pd.DataFrame(
    summary_rows
)

profile_summary_df.to_csv(
    OUTPUT_PROFILE_SUMMARY,
    index=False,
)


# =============================================================================
# SOLID HEAD-NECK SCREEN
# =============================================================================

# Global circular-equivalent neck screen from closure outer face up to the
# bottom of the transverse shaft hole. The actual boss becomes 3D/noncircular
# near the shaft and will require local FEA later.
solid_station_above_U_mm = [
    e2_boundary_above_U_mm,
    e2_boundary_above_U_mm
    + WORKING_LOWER_LIGAMENT_MM / 2.0,
    shaft_bottom_above_U_mm,
]

solid_rows = []

for Kt in KT_VALUES:

    for zU_mm in solid_station_above_U_mm:

        hA_mm = (
            h_UA_static_m
            * 1000.0
            + zU_mm
        )

        for test_OD_mm in [
            74.0,
            80.0,
            85.0,
            90.0,
            96.0,
        ]:

            lim = governing_solid(
                hA_mm,
                test_OD_mm,
                Kt,
                "limit",
            )

            ult = governing_solid(
                hA_mm,
                test_OD_mm,
                Kt,
                "ultimate",
            )

            solid_rows.append({
                "Kt_bending":
                    Kt,
                "station_above_U_mm":
                    zU_mm,
                "station_above_A_mm":
                    hA_mm,
                "OD_mm":
                    test_OD_mm,
                "limit_case":
                    lim[
                        "case"
                    ],
                "limit_vm_MPa":
                    lim[
                        "vm_MPa"
                    ],
                "MS_limit_7075":
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
                "MS_ultimate_7075":
                    ult[
                        "MS"
                    ],
                "PASS":
                    (
                        lim[
                            "MS"
                        ] >= 0.0
                        and ult[
                            "MS"
                        ] >= 0.0
                    ),
            })


solid_df = pd.DataFrame(
    solid_rows
)

solid_df.to_csv(
    OUTPUT_SOLID,
    index=False,
)


# =============================================================================
# CONSOLE REPORT
# =============================================================================

print("=" * 124)
print(
    " PHASE 2E3-B5B — 7075 UPPER-BARREL / SOLID-HEAD REINFORCEMENT PROFILE V0.1"
)
print("=" * 124)

print("\nMATERIAL / PRESSURE BASIS")
print("-" * 124)
print(
    f"7075-T6 yield / ultimate screen:  "
    f"{SY_7075_MPa:.1f} / {SU_7075_MPa:.1f} MPa"
)
print(
    f"Limit pressure differential:      {P_LIMIT_DIFF_MPa:.3f} MPa"
)
print(
    f"Ultimate pressure differential:   {P_ULT_DIFF_MPa:.3f} MPa"
)
print(
    "Mechanical and maximum-pressure screens are conservatively treated as simultaneous."
)

print("\nAXIAL GEOMETRY")
print("-" * 124)
print(
    f"Preferred lower guide hL:         {preferred_hL_mm:.1f} mm above A"
)
print(
    f"Preferred upper guide hU:         {preferred_hU_mm:.1f} mm above A"
)
print(
    f"Equivalent datum U:               {h_UA_static_m*1000.0:.1f} mm above A"
)
print(
    f"E2 closure outer face:            {e2_boundary_above_U_mm:.6f} mm above U"
)
print(
    f"Closure outer face above A:       {end_h_from_A_mm:.6f} mm"
)
print(
    f"Working shaft-hole bottom:        {shaft_bottom_above_U_mm:.6f} mm above U"
)
print(
    f"Working shaft centerline:         {shaft_center_above_U_mm:.6f} mm above U"
)

print("\nANNULAR 64-mm-ID BARREL — REQUIRED OD PROFILE SUMMARY")
print("-" * 124)
print(
    f"{'Kt':>6}"
    f"{'74 fails @A':>14}"
    f"{'74 fails @U':>14}"
    f"{'OD@hU':>10}"
    f"{'OD@U':>10}"
    f"{'OD@E2':>10}"
    f"{'Max OD':>10}"
)
print("-" * 74)

for _, row in profile_summary_df.iterrows():

    fail_A = (
        f"{row['first_station_74mm_fails_above_A_mm']:.0f}"
        if np.isfinite(
            row[
                "first_station_74mm_fails_above_A_mm"
            ]
        )
        else "NEVER"
    )

    fail_U = (
        f"{row['first_station_74mm_fails_above_U_mm']:+.0f}"
        if np.isfinite(
            row[
                "first_station_74mm_fails_above_U_mm"
            ]
        )
        else "NEVER"
    )

    print(
        f"{row['Kt_bending']:>6.1f}"
        f"{fail_A:>14}"
        f"{fail_U:>14}"
        f"{row['required_OD_near_upper_guide_mm']:>10.1f}"
        f"{row['required_OD_near_U_mm']:>10.1f}"
        f"{row['required_OD_at_E2_boundary_mm']:>10.1f}"
        f"{row['maximum_required_OD_over_profile_mm']:>10.1f}"
    )

print("\nSOLID HEAD-NECK SCREEN — 10 mm BELOW SHAFT HOLE")
print("-" * 124)
print(
    f"{'Kt':>6}"
    f"{'Station>U':>12}"
    f"{'OD':>8}"
    f"{'VMlim':>10}"
    f"{'MSlim':>10}"
    f"{'VMult':>10}"
    f"{'MSult':>10}"
    f"{'PASS':>8}"
)
print("-" * 80)

# Print only the bottom-of-hole station for compactness.
bottom_rows = solid_df.loc[
    np.isclose(
        solid_df[
            "station_above_U_mm"
        ],
        shaft_bottom_above_U_mm,
    )
]

for _, row in bottom_rows.iterrows():
    print(
        f"{row['Kt_bending']:>6.1f}"
        f"{row['station_above_U_mm']:>12.1f}"
        f"{row['OD_mm']:>8.0f}"
        f"{row['limit_vm_MPa']:>10.1f}"
        f"{row['MS_limit_7075']:>10.3f}"
        f"{row['ultimate_vm_MPa']:>10.1f}"
        f"{row['MS_ultimate_7075']:>10.3f}"
        f"{str(bool(row['PASS'])):>8}"
    )

print("\nB5B DISPOSITION")
print("-" * 124)
print(
    "The old 74/64 barrel may remain only where the corrected 7075 + pressure screen passes."
)
print(
    "Above the first failing station, carry a locally reinforced external OD while retaining the 64 mm internal bore."
)
print(
    "Retaining the 64 mm ID preserves the frozen E2 gas/oil cavity geometry; only the external structural envelope changes."
)
print(
    "Do NOT freeze a taper or shoulder yet. The next step is to select a practical reinforced OD profile and "
    "screen its transition Kt / fillet sensitivity before updating the E2/E3 geometry baseline."
)

print("\nOUTPUT FILES")
print("-" * 124)
print(
    f"Full annular profile:             {OUTPUT_PROFILE}"
)
print(
    f"Profile summary:                  {OUTPUT_PROFILE_SUMMARY}"
)
print(
    f"Solid head-neck screen:           {OUTPUT_SOLID}"
)
print(
    f"Summary:                          {OUTPUT_SUMMARY}"
)


# =============================================================================
# SUMMARY FILE
# =============================================================================

summary_lines = [
    "=" * 124,
    " PHASE 2E3-B5B — 7075 UPPER-BARREL / SOLID-HEAD REINFORCEMENT PROFILE V0.1",
    "=" * 124,
    "",
    f"7075 screen: {SY_7075_MPa:.1f} / {SU_7075_MPa:.1f} MPa",
    f"Pressure screen: {P_LIMIT_DIFF_MPa:.3f} / {P_ULT_DIFF_MPa:.3f} MPa",
    f"Frozen internal bore retained: {barrel_ID_mm:.1f} mm",
    "",
    "Profile summary:",
]

for _, row in profile_summary_df.iterrows():
    summary_lines.append(
        f"  Kt={row['Kt_bending']:.1f}: "
        f"first 74-mm fail A={row['first_station_74mm_fails_above_A_mm']}, "
        f"required OD at E2={row['required_OD_at_E2_boundary_mm']:.1f} mm"
    )

summary_lines.extend([
    "",
    "No taper / shoulder / fillet is frozen by this script.",
    "Next: practical reinforcement-profile selection + transition Kt screening.",
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
