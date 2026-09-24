from pathlib import Path
import ast
import math

import numpy as np
import pandas as pd


# =============================================================================
# LANDING GEAR DESIGN PROJECT
# PHASE 2E3-A2 — UPPER ATTACHMENT FBD TRANSPORT / STATION SENSITIVITY V0.1
#
# PURPOSE
#   Reconcile the valid Phase 2D9/2D10 upper-attachment ARCHITECTURE with the
#   Phase 2E2 physical upper-head packaging.
#
#   Key point:
#       The old D9/D10 calculations were performed at equivalent upper datum U.
#       E2 later established that the real attachment must lie in solid head
#       material ABOVE the live pressure cavity.
#
#   Therefore:
#       - retain the trunnion + brace conceptual load path,
#       - DO NOT retain D9/D10 numerical loads without transporting the
#         six-component resultant to the new physical attachment station.
#
#   This script does NOT choose a final trunnion station or hardware dimensions.
#   It:
#       1. reads the current Phase 1 load envelope,
#       2. reads D9/D10 source geometry/sweep values,
#       3. reads the E2 minimum solid-head boundary above U,
#       4. transports the upper resultants from U to candidate stations,
#       5. checks direct-vs-transport equations,
#       6. updates trunnion reaction sensitivities for the OLD D9 span sweep,
#       7. updates brace-force sensitivities for the OLD D9/D10 arm sweep.
#
#   Sensitivity stations:
#       E2 boundary + [0, 25, 50, 75, 100] mm.
#
#   These offsets are a NON-FROZEN sensitivity grid only.
#
# OUTPUTS
#   phase2e3a2_station_resultants.csv
#   phase2e3a2_trunnion_reaction_sensitivity.csv
#   phase2e3a2_brace_force_sensitivity.csv
#   phase2e3a2_fbd_definition.csv
#   phase2e3a2_summary.txt
# =============================================================================


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.resolve()

LOAD_CSV = (
    PROJECT_ROOT
    / "phase1_loads"
    / "phase1_load_envelope.csv"
)

D9_PY = HERE / "phase2_upper_trunnion_sizing.py"
D10_PY = HERE / "phase2_upper_brace_sizing.py"
E2_BASELINE = HERE / "phase2e2_v1_baseline.csv"

OUTPUT_RESULTANTS = (
    HERE
    / "phase2e3a2_station_resultants.csv"
)

OUTPUT_TRUNNION = (
    HERE
    / "phase2e3a2_trunnion_reaction_sensitivity.csv"
)

OUTPUT_BRACE = (
    HERE
    / "phase2e3a2_brace_force_sensitivity.csv"
)

OUTPUT_FBD = (
    HERE
    / "phase2e3a2_fbd_definition.csv"
)

OUTPUT_SUMMARY = (
    HERE
    / "phase2e3a2_summary.txt"
)


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
        str(col)
        .replace(
            "\ufeff",
            "",
        )
        .strip()
        for col in df.columns
    ]

    return df


def find_column(df, aliases):
    norm = {
        normalize(col): col
        for col in df.columns
    }

    for alias in aliases:
        key = normalize(
            alias
        )

        if key in norm:
            return norm[
                key
            ]

    return None


def parameter_lookup(df, aliases):
    pcol = find_column(
        df,
        [
            "parameter",
        ],
    )

    vcol = find_column(
        df,
        [
            "value",
        ],
    )

    if (
        pcol is None
        or vcol is None
    ):
        return None

    pnorm = (
        df[pcol]
        .astype(str)
        .map(normalize)
    )

    for alias in aliases:
        mask = (
            pnorm
            == normalize(
                alias
            )
        )

        rows = df.loc[
            mask
        ]

        if not rows.empty:
            return rows.iloc[0][
                vcol
            ]

    return None


def safe_float(value):
    try:
        return float(
            value
        )
    except Exception:
        return np.nan


def ast_literal_assignments(path):
    """
    Recover simple literal scalar/list assignments from source code.
    """

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
        filename=str(
            path
        ),
    )

    values = {}

    for node in tree.body:
        if isinstance(
            node,
            ast.Assign,
        ):
            names = [
                target.id
                for target in node.targets
                if isinstance(
                    target,
                    ast.Name,
                )
            ]

            if not names:
                continue

            try:
                value = ast.literal_eval(
                    node.value
                )
            except Exception:
                continue

            for name in names:
                values[
                    name
                ] = value

    return values


def force_columns(df, level):
    cols = {}

    for comp in [
        "Fx",
        "Fy",
        "Fz",
    ]:
        aliases = [
            f"{comp} {level} (kN)",
            f"{comp}_{level}_kN",
            f"{comp}_{level}",
        ]

        col = find_column(
            df,
            aliases,
        )

        if col is None:
            raise KeyError(
                f"Could not find {comp} {level} column. "
                f"Columns: {list(df.columns)}"
            )

        cols[
            comp
        ] = col

    return cols


# =============================================================================
# SOURCE INPUTS
# =============================================================================

d9 = ast_literal_assignments(
    D9_PY
)

d10 = ast_literal_assignments(
    D10_PY
)

e_m = float(
    d9[
        "e_m"
    ]
)

rt_m = float(
    d9[
        "rt_m"
    ]
)

h_UA_static_m = float(
    d9[
        "h_UA_static_m"
    ]
)

support_spans_mm = [
    float(x)
    for x in d9[
        "support_span_values_mm"
    ]
]

# Prefer the D9 brace-arm sweep if present, otherwise D10.
if (
    "brace_arm_values_mm"
    in d9
):
    brace_arms_mm = [
        float(x)
        for x in d9[
            "brace_arm_values_mm"
        ]
    ]
else:
    brace_arms_mm = [
        float(x)
        for x in d10[
            "effective_arm_values_mm"
        ]
    ]

loads_df = read_csv(
    LOAD_CSV
)

e2_df = read_csv(
    E2_BASELINE
)

e2_boundary_mm = safe_float(
    parameter_lookup(
        e2_df,
        [
            "preliminary_E3_interface_outer_face_above_U",
        ],
    )
)

if not np.isfinite(
    e2_boundary_mm
):
    raise ValueError(
        "Could not resolve "
        "preliminary_E3_interface_outer_face_above_U "
        "from phase2e2_v1_baseline.csv."
    )

case_col = find_column(
    loads_df,
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
    loads_df,
    "Limit",
)

ultimate_cols = force_columns(
    loads_df,
    "Ultimate",
)


# =============================================================================
# RESULTANT EQUATIONS
# =============================================================================

def upper_resultants_at_station(
    Fx_kN,
    Fy_kN,
    Fz_kN,
    delta_from_U_m,
):
    """
    Resultants at a vertical strut section delta_from_U_m above datum U.

    Frozen Phase 2 convention:
        Mx = e*Fz + (rt+h)*Fy
        My = -(rt+h)*Fx
        Mz = -e*Fx

    where:
        h = h_UA_static + delta_from_U
    """

    h_from_A_m = (
        h_UA_static_m
        + delta_from_U_m
    )

    arm_m = (
        rt_m
        + h_from_A_m
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
        "h_from_A_m":
            h_from_A_m,
        "arm_contact_to_section_m":
            arm_m,
    }


def transported_from_U(
    Fx_kN,
    Fy_kN,
    Fz_kN,
    delta_from_U_m,
):
    """
    Transport the six-component resultant from datum U to a station directly
    above U by delta_from_U.

    Because the station shift is purely +z:
        Mx_T = Mx_U + delta*Fy
        My_T = My_U - delta*Fx
        Mz_T = Mz_U
    """

    U = upper_resultants_at_station(
        Fx_kN,
        Fy_kN,
        Fz_kN,
        0.0,
    )

    return {
        "Mx_kNm":
            U["Mx_kNm"]
            + delta_from_U_m
            * Fy_kN,
        "My_kNm":
            U["My_kNm"]
            - delta_from_U_m
            * Fx_kN,
        "Mz_kNm":
            U["Mz_kNm"],
    }


# =============================================================================
# TRUNNION / BRACE LOAD SPLIT
# =============================================================================

def trunnion_reactions(
    Fy_kN,
    Fz_kN,
    My_kNm,
    Mz_kNm,
    span_mm,
):
    """
    Two support planes at x = +/- s/2.

    Equilibrium:
        RLy + RRy + Fy = 0
        RLz + RRz + Fz = 0

        RLy = (-Fy + 2*Mz/s)/2
        RRy = (-Fy - 2*Mz/s)/2

        RLz = (-Fz - 2*My/s)/2
        RRz = (-Fz + 2*My/s)/2
    """

    s_m = (
        span_mm
        / 1000.0
    )

    if s_m <= 0.0:
        raise ValueError(
            "Trunnion support span must be positive."
        )

    RLy = (
        -Fy_kN
        + 2.0
        * Mz_kNm
        / s_m
    ) / 2.0

    RRy = (
        -Fy_kN
        - 2.0
        * Mz_kNm
        / s_m
    ) / 2.0

    RLz = (
        -Fz_kN
        - 2.0
        * My_kNm
        / s_m
    ) / 2.0

    RRz = (
        -Fz_kN
        + 2.0
        * My_kNm
        / s_m
    ) / 2.0

    RL = math.hypot(
        RLy,
        RLz,
    )

    RR = math.hypot(
        RRy,
        RRz,
    )

    force_y_residual = (
        RLy
        + RRy
        + Fy_kN
    )

    force_z_residual = (
        RLz
        + RRz
        + Fz_kN
    )

    moment_y_residual = (
        (s_m / 2.0)
        * (
            RLz
            - RRz
        )
        + My_kNm
    )

    moment_z_residual = (
        (s_m / 2.0)
        * (
            RRy
            - RLy
        )
        + Mz_kNm
    )

    return {
        "RLy_kN":
            RLy,
        "RRy_kN":
            RRy,
        "RLz_kN":
            RLz,
        "RRz_kN":
            RRz,
        "RL_kN":
            RL,
        "RR_kN":
            RR,
        "Rmax_kN":
            max(
                RL,
                RR,
            ),
        "force_y_residual_kN":
            force_y_residual,
        "force_z_residual_kN":
            force_z_residual,
        "moment_y_residual_kNm":
            moment_y_residual,
        "moment_z_residual_kNm":
            moment_z_residual,
    }


def brace_force_kN(
    Mx_kNm,
    arm_mm,
):
    arm_m = (
        arm_mm
        / 1000.0
    )

    if arm_m <= 0.0:
        raise ValueError(
            "Brace arm must be positive."
        )

    return abs(
        Mx_kNm
    ) / arm_m


# =============================================================================
# STATION GRID
# =============================================================================

# Non-frozen geometric sensitivity only.
station_extra_offsets_mm = [
    0.0,
    25.0,
    50.0,
    75.0,
    100.0,
]

station_rows = []
trunnion_rows = []
brace_rows = []

for extra_mm in station_extra_offsets_mm:

    delta_from_U_mm = (
        e2_boundary_mm
        + extra_mm
    )

    delta_from_U_m = (
        delta_from_U_mm
        / 1000.0
    )

    station_label = (
        "E2_BOUNDARY"
        if abs(
            extra_mm
        ) < 1e-12
        else f"E2_BOUNDARY_PLUS_{extra_mm:.0f}MM"
    )

    for level, cols in [
        (
            "limit",
            limit_cols,
        ),
        (
            "ultimate",
            ultimate_cols,
        ),
    ]:

        for _, row in loads_df.iterrows():

            case = str(
                row[
                    case_col
                ]
            )

            Fx = float(
                row[
                    cols["Fx"]
                ]
            )

            Fy = float(
                row[
                    cols["Fy"]
                ]
            )

            Fz = float(
                row[
                    cols["Fz"]
                ]
            )

            direct = upper_resultants_at_station(
                Fx,
                Fy,
                Fz,
                delta_from_U_m,
            )

            transport = transported_from_U(
                Fx,
                Fy,
                Fz,
                delta_from_U_m,
            )

            residual_Mx = (
                direct[
                    "Mx_kNm"
                ]
                - transport[
                    "Mx_kNm"
                ]
            )

            residual_My = (
                direct[
                    "My_kNm"
                ]
                - transport[
                    "My_kNm"
                ]
            )

            residual_Mz = (
                direct[
                    "Mz_kNm"
                ]
                - transport[
                    "Mz_kNm"
                ]
            )

            if max(
                abs(
                    residual_Mx
                ),
                abs(
                    residual_My
                ),
                abs(
                    residual_Mz
                ),
            ) > 1e-10:
                raise AssertionError(
                    "Resultant transport identity failed."
                )

            station_rows.append({
                "station_label":
                    station_label,
                "extra_above_E2_boundary_mm":
                    extra_mm,
                "station_above_U_mm":
                    delta_from_U_mm,
                "station_above_A_static_mm":
                    (
                        h_UA_static_m
                        * 1000.0
                        + delta_from_U_mm
                    ),
                "level":
                    level,
                "case":
                    case,
                "Fx_kN":
                    direct["Fx_kN"],
                "Fy_kN":
                    direct["Fy_kN"],
                "Fz_kN":
                    direct["Fz_kN"],
                "Mx_kNm":
                    direct["Mx_kNm"],
                "My_kNm":
                    direct["My_kNm"],
                "Mz_kNm":
                    direct["Mz_kNm"],
                "resultant_moment_kNm":
                    math.sqrt(
                        direct["Mx_kNm"]**2
                        + direct["My_kNm"]**2
                        + direct["Mz_kNm"]**2
                    ),
                "transport_residual_Mx_kNm":
                    residual_Mx,
                "transport_residual_My_kNm":
                    residual_My,
                "transport_residual_Mz_kNm":
                    residual_Mz,
            })

            # Old D9 span sweep retained only as a reaction-sensitivity basis.
            for span_mm in support_spans_mm:

                reactions = trunnion_reactions(
                    direct[
                        "Fy_kN"
                    ],
                    direct[
                        "Fz_kN"
                    ],
                    direct[
                        "My_kNm"
                    ],
                    direct[
                        "Mz_kNm"
                    ],
                    span_mm,
                )

                residuals = [
                    abs(
                        reactions[
                            "force_y_residual_kN"
                        ]
                    ),
                    abs(
                        reactions[
                            "force_z_residual_kN"
                        ]
                    ),
                    abs(
                        reactions[
                            "moment_y_residual_kNm"
                        ]
                    ),
                    abs(
                        reactions[
                            "moment_z_residual_kNm"
                        ]
                    ),
                ]

                if max(
                    residuals
                ) > 1e-10:
                    raise AssertionError(
                        "Trunnion reaction equilibrium check failed."
                    )

                trunnion_rows.append({
                    "station_label":
                        station_label,
                    "extra_above_E2_boundary_mm":
                        extra_mm,
                    "station_above_U_mm":
                        delta_from_U_mm,
                    "level":
                        level,
                    "case":
                        case,
                    "support_span_mm":
                        span_mm,
                    "Fx_thrust_requirement_kN":
                        abs(
                            direct[
                                "Fx_kN"
                            ]
                        ),
                    "Fy_external_kN":
                        direct[
                            "Fy_kN"
                        ],
                    "Fz_external_kN":
                        direct[
                            "Fz_kN"
                        ],
                    "My_external_kNm":
                        direct[
                            "My_kNm"
                        ],
                    "Mz_external_kNm":
                        direct[
                            "Mz_kNm"
                        ],
                    **reactions,
                })

            # Old D9/D10 arm sweep retained only as brace-load sensitivity.
            for arm_mm in brace_arms_mm:

                brace_rows.append({
                    "station_label":
                        station_label,
                    "extra_above_E2_boundary_mm":
                        extra_mm,
                    "station_above_U_mm":
                        delta_from_U_mm,
                    "level":
                        level,
                    "case":
                        case,
                    "Mx_external_kNm":
                        direct[
                            "Mx_kNm"
                        ],
                    "brace_effective_arm_mm":
                        arm_mm,
                    "brace_force_abs_kN":
                        brace_force_kN(
                            direct[
                                "Mx_kNm"
                            ],
                            arm_mm,
                        ),
                })


station_df = pd.DataFrame(
    station_rows
)

trunnion_df = pd.DataFrame(
    trunnion_rows
)

brace_df = pd.DataFrame(
    brace_rows
)

station_df.to_csv(
    OUTPUT_RESULTANTS,
    index=False,
)

trunnion_df.to_csv(
    OUTPUT_TRUNNION,
    index=False,
)

brace_df.to_csv(
    OUTPUT_BRACE,
    index=False,
)


# =============================================================================
# FBD DEFINITION / TRACEABILITY
# =============================================================================

fbd_rows = [
    {
        "component":
            "Upper trunnion pair",
        "reaction_or_load":
            "Fx",
        "role":
            "Axial/thrust load through locating journal / thrust face",
        "status":
            "ARCHITECTURE_RETAINED",
        "note":
            "Full |Fx| remains a conservative thrust requirement until detailed locating/floating bearing arrangement is defined.",
    },
    {
        "component":
            "Upper trunnion pair",
        "reaction_or_load":
            "Fy, Fz",
        "role":
            "Radial bearing reactions",
        "status":
            "ARCHITECTURE_RETAINED",
        "note":
            "Distributed between left/right support planes by force and moment equilibrium.",
    },
    {
        "component":
            "Upper trunnion pair",
        "reaction_or_load":
            "My, Mz",
        "role":
            "Differential radial reaction couples across support span",
        "status":
            "ARCHITECTURE_RETAINED",
        "note":
            "Numerical reaction magnitudes must be recomputed at the physical E3 station.",
    },
    {
        "component":
            "Brace / anti-rotation link",
        "reaction_or_load":
            "Mx",
        "role":
            "Separate two-force path reacting moment about trunnion axis",
        "status":
            "ARCHITECTURE_RETAINED",
        "note":
            "Exact brace endpoints, angle, airframe fitting and retraction kinematics remain open.",
    },
    {
        "component":
            "Guide bushings",
        "reaction_or_load":
            "Internal RL/RU",
        "role":
            "Internal piston-to-barrel radial load transfer",
        "status":
            "NOT_EXTERNAL_ATTACHMENT_REACTION",
        "note":
            "Do not substitute guide-bushing reaction directly for trunnion/airframe reaction.",
    },
    {
        "component":
            "E2 solid-head boundary",
        "reaction_or_load":
            "geometry only",
        "role":
            "Minimum preliminary location outside live pressure cavity",
        "status":
            "PACKAGING_BOUNDARY",
        "note":
            "Not a trunnion centerline. E3 station remains to be selected.",
    },
]

fbd_df = pd.DataFrame(
    fbd_rows
)

fbd_df.to_csv(
    OUTPUT_FBD,
    index=False,
)


# =============================================================================
# GOVERNING SUMMARIES
# =============================================================================

def governing_abs(
    df,
    column,
    level,
    station_label,
):
    subset = df.loc[
        (
            df[
                "level"
            ]
            == level
        )
        &
        (
            df[
                "station_label"
            ]
            == station_label
        )
    ].copy()

    idx = (
        subset[
            column
        ]
        .abs()
        .idxmax()
    )

    return subset.loc[
        idx
    ]


def governing_max(
    df,
    column,
    level,
    station_label,
    extra_filter=None,
):
    mask = (
        (
            df[
                "level"
            ]
            == level
        )
        &
        (
            df[
                "station_label"
            ]
            == station_label
        )
    )

    if extra_filter is not None:
        mask &= extra_filter(
            df
        )

    subset = df.loc[
        mask
    ].copy()

    idx = subset[
        column
    ].idxmax()

    return subset.loc[
        idx
    ]


boundary_label = (
    "E2_BOUNDARY"
)

top_label = (
    "E2_BOUNDARY_PLUS_100MM"
)

# Datum-U reference generated directly.
reference_U_rows = []

for level, cols in [
    (
        "limit",
        limit_cols,
    ),
    (
        "ultimate",
        ultimate_cols,
    ),
]:

    for _, row in loads_df.iterrows():
        case = str(
            row[
                case_col
            ]
        )

        ref = upper_resultants_at_station(
            float(
                row[
                    cols["Fx"]
                ]
            ),
            float(
                row[
                    cols["Fy"]
                ]
            ),
            float(
                row[
                    cols["Fz"]
                ]
            ),
            0.0,
        )

        reference_U_rows.append({
            "level":
                level,
            "case":
                case,
            **ref,
        })

reference_U_df = pd.DataFrame(
    reference_U_rows
)

# Governing U vs E2-boundary moments.
summary_lines = []

summary_lines.append(
    "=" * 124
)
summary_lines.append(
    " PHASE 2E3-A2 — UPPER ATTACHMENT FBD TRANSPORT / STATION SENSITIVITY V0.1"
)
summary_lines.append(
    "=" * 124
)
summary_lines.append("")
summary_lines.append(
    "SOURCE GEOMETRY"
)
summary_lines.append(
    f"e = {e_m*1000.0:.3f} mm"
)
summary_lines.append(
    f"r_t = {rt_m*1000.0:.3f} mm"
)
summary_lines.append(
    f"U above A in static reference = {h_UA_static_m*1000.0:.3f} mm"
)
summary_lines.append(
    f"E2 minimum solid-head boundary = {e2_boundary_mm:.6f} mm above U"
)
summary_lines.append("")
summary_lines.append(
    "ARCHITECTURE DISPOSITION"
)
summary_lines.append(
    "Retain +x transverse trunnion pair for Fx/Fy/Fz/My/Mz."
)
summary_lines.append(
    "Retain separate brace / anti-rotation two-force path for Mx."
)
summary_lines.append(
    "Do NOT retain the old D9/D10 numerical sizing without station transport."
)
summary_lines.append(
    "Guide-bushing reactions remain internal and are not trunnion reactions."
)
summary_lines.append("")

for level in [
    "limit",
    "ultimate",
]:

    summary_lines.append(
        f"{level.upper()} MOMENT TRANSPORT — DATUM U VS E2 BOUNDARY"
    )

    for component in [
        "Mx_kNm",
        "My_kNm",
        "Mz_kNm",
    ]:

        U_subset = reference_U_df.loc[
            reference_U_df[
                "level"
            ]
            == level
        ]

        idx_U = (
            U_subset[
                component
            ]
            .abs()
            .idxmax()
        )

        U_row = U_subset.loc[
            idx_U
        ]

        B_row = governing_abs(
            station_df,
            component,
            level,
            boundary_label,
        )

        denom = abs(
            float(
                U_row[
                    component
                ]
            )
        )

        if denom > 1e-12:
            pct = (
                (
                    abs(
                        float(
                            B_row[
                                component
                            ]
                        )
                    )
                    / denom
                    - 1.0
                )
                * 100.0
            )
        else:
            pct = np.nan

        summary_lines.append(
            f"  {component}: U gov {U_row['case']} "
            f"{U_row[component]:+.6f} kN*m ; "
            f"E2-boundary gov {B_row['case']} "
            f"{B_row[component]:+.6f} kN*m ; "
            f"change in governing |value| = "
            f"{pct:+.3f}%"
        )

    summary_lines.append("")

# Trunnion reaction governing values for each old span at boundary and +100 mm.
for station_label in [
    boundary_label,
    top_label,
]:
    summary_lines.append(
        f"ULTIMATE TRUNNION REACTION SENSITIVITY — {station_label}"
    )

    for span_mm in support_spans_mm:
        row = governing_max(
            trunnion_df,
            "Rmax_kN",
            "ultimate",
            station_label,
            extra_filter=lambda df, s=span_mm:
                np.isclose(
                    df[
                        "support_span_mm"
                    ],
                    s,
                ),
        )

        summary_lines.append(
            f"  span {span_mm:.0f} mm: "
            f"Rmax = {row['Rmax_kN']:.6f} kN "
            f"({row['case']})"
        )

    summary_lines.append("")

# Brace force governing values for each old arm at boundary and +100 mm.
for station_label in [
    boundary_label,
    top_label,
]:
    summary_lines.append(
        f"ULTIMATE BRACE FORCE SENSITIVITY — {station_label}"
    )

    for arm_mm in brace_arms_mm:
        row = governing_max(
            brace_df,
            "brace_force_abs_kN",
            "ultimate",
            station_label,
            extra_filter=lambda df, a=arm_mm:
                np.isclose(
                    df[
                        "brace_effective_arm_mm"
                    ],
                    a,
                ),
        )

        summary_lines.append(
            f"  arm {arm_mm:.0f} mm: "
            f"|Fbrace| = {row['brace_force_abs_kN']:.6f} kN "
            f"({row['case']})"
        )

    summary_lines.append("")

summary_lines.append(
    "E3-A2 DISPOSITION"
)
summary_lines.append(
    "PASS — the old D9/D10 load-path architecture is mechanically compatible "
    "with E2, but its numerical sizing at datum U is superseded for E3."
)
summary_lines.append(
    "Next step: select a physically realizable trunnion-centerline station in "
    "the solid upper head, then re-size journals/brace/lugs from the transported "
    "loads at that frozen station."
)
summary_lines.append(
    "=" * 124
)

OUTPUT_SUMMARY.write_text(
    "\n".join(
        summary_lines
    ),
    encoding="utf-8",
)


# =============================================================================
# CONSOLE OUTPUT
# =============================================================================

print("=" * 124)
print(
    " PHASE 2E3-A2 — UPPER ATTACHMENT FBD TRANSPORT / STATION SENSITIVITY V0.1"
)
print("=" * 124)

print("\nSOURCE CONNECTION")
print("-" * 124)
print(
    f"Current Phase 1 loads:            {LOAD_CSV}"
)
print(
    f"Phase 2D9 trunnion source:        {D9_PY}"
)
print(
    f"Phase 2D10 brace source:          {D10_PY}"
)
print(
    f"Phase 2E2 frozen baseline:        {E2_BASELINE}"
)

print("\nSOURCE GEOMETRY")
print("-" * 124)
print(
    f"Wheel/strut offset e:             {e_m*1000.0:.3f} mm"
)
print(
    f"Loaded tire radius r_t:           {rt_m*1000.0:.3f} mm"
)
print(
    f"Equivalent datum U above A:       {h_UA_static_m*1000.0:.3f} mm"
)
print(
    f"E2 minimum solid-head boundary:   {e2_boundary_mm:.6f} mm above U"
)
print(
    f"Boundary above A (static ref):    "
    f"{h_UA_static_m*1000.0 + e2_boundary_mm:.6f} mm"
)

print("\nFROZEN CONCEPTUAL LOAD PATH")
print("-" * 124)
print(
    "Trunnion pair (+x axis):          Fx thrust; Fy/Fz radial; My/Mz via differential reactions."
)
print(
    "Separate brace / anti-rotation:   Mx."
)
print(
    "Guide bushings:                   internal piston-to-barrel reactions only."
)
print(
    "E2 +498.780... mm boundary:       packaging minimum only, not a trunnion centerline."
)

print("\nIMPORTANT RECONCILIATION")
print("-" * 124)
print(
    "Phase 2D9/D10 calculated loads at datum U."
)
print(
    "Phase 2E2 moved the physical attachment region hundreds of millimetres above U."
)
print(
    "Therefore D9/D10 architecture can be retained, but their numerical sizing must be updated."
)

for level in [
    "limit",
    "ultimate",
]:

    print(
        f"\n{level.upper()} GOVERNING MOMENTS — U VS E2 MINIMUM BOUNDARY"
    )
    print("-" * 124)

    for component in [
        "Mx_kNm",
        "My_kNm",
        "Mz_kNm",
    ]:

        U_subset = reference_U_df.loc[
            reference_U_df[
                "level"
            ]
            == level
        ]

        idx_U = (
            U_subset[
                component
            ]
            .abs()
            .idxmax()
        )

        U_row = U_subset.loc[
            idx_U
        ]

        B_row = governing_abs(
            station_df,
            component,
            level,
            boundary_label,
        )

        print(
            f"{component:<8}  U: "
            f"{U_row[component]:>+12.6f} kN*m "
            f"({U_row['case']:<5})   "
            f"E2 boundary: "
            f"{B_row[component]:>+12.6f} kN*m "
            f"({B_row['case']})"
        )

print("\nULTIMATE TRUNNION REACTION — E2 BOUNDARY")
print("-" * 124)

for span_mm in support_spans_mm:
    row = governing_max(
        trunnion_df,
        "Rmax_kN",
        "ultimate",
        boundary_label,
        extra_filter=lambda df, s=span_mm:
            np.isclose(
                df[
                    "support_span_mm"
                ],
                s,
            ),
    )

    print(
        f"Old D9 span sensitivity {span_mm:>6.0f} mm: "
        f"Rmax = {row['Rmax_kN']:>10.4f} kN "
        f"({row['case']})"
    )

print("\nULTIMATE BRACE FORCE — E2 BOUNDARY")
print("-" * 124)

for arm_mm in brace_arms_mm:
    row = governing_max(
        brace_df,
        "brace_force_abs_kN",
        "ultimate",
        boundary_label,
        extra_filter=lambda df, a=arm_mm:
            np.isclose(
                df[
                    "brace_effective_arm_mm"
                ],
                a,
            ),
    )

    print(
        f"Old D9/D10 arm sensitivity {arm_mm:>6.0f} mm: "
        f"|F| = {row['brace_force_abs_kN']:>10.4f} kN "
        f"({row['case']})"
    )

print("\nE3-A2 DISPOSITION")
print("-" * 124)
print(
    "PASS — retain the D9/D10 conceptual trunnion + brace load path."
)
print(
    "SUPERSEDE the old numerical sizing performed at equivalent datum U."
)
print(
    "Next: choose a physically realizable trunnion centerline in the solid head, "
    "then re-size journals, brace, lugs and airframe fittings at that station."
)

print("\nOUTPUT FILES")
print("-" * 124)
print(
    f"Station resultants:               {OUTPUT_RESULTANTS}"
)
print(
    f"Trunnion reaction sensitivity:    {OUTPUT_TRUNNION}"
)
print(
    f"Brace-force sensitivity:          {OUTPUT_BRACE}"
)
print(
    f"FBD definition:                   {OUTPUT_FBD}"
)
print(
    f"Summary:                          {OUTPUT_SUMMARY}"
)
print("=" * 124)
