from pathlib import Path
import ast
import math
import operator

import numpy as np
import pandas as pd


# =============================================================================
# LANDING GEAR DESIGN PROJECT
# PHASE 2E3-B5A — BARREL MATERIAL / UPPER-NECK STRUCTURAL AUDIT V0.1
#
# PURPOSE
#   Before sizing the E3 boss-to-barrel transition, verify that the inherited
#   74 mm OD / 64 mm ID barrel baseline was actually screened with the material
#   allowables we now intend to use.
#
#   This audit was triggered because the current E3 local-head work uses the
#   project 7075-T6 preliminary screen:
#
#       Sy = 503 MPa
#       Su = 572 MPa
#
#   while some historical barrel margin numbers may imply a different material
#   allowable convention.
#
#   This script therefore:
#
#       1. audits phase2_barrel_sizing.py for material / strength definitions,
#       2. reads the historical 74 x 5 mm working barrel row,
#       3. back-calculates the implied historical allowables from:
#
#              allowable = VM * (1 + MS)
#
#       4. transports the CURRENT Phase 1 loads to the E2/E3 solid-head boundary,
#       5. recomputes current section stress for:
#              - hollow 74/64 mm annulus
#              - solid 74 mm head neck
#       6. screens both against 7075-T6 503 / 572 MPa,
#       7. computes the minimum OD required at the E2 boundary for:
#              - a 64 mm-ID annular reinforced upper barrel,
#              - a solid circular upper-head neck,
#          over Kt = 1.0, 1.5, 2.0, 2.5, 3.0.
#
# IMPORTANT
#   - Kt is applied to bending only, consistent with the existing project
#     preliminary convention. Torsional/local notch concentration remains open.
#   - This is a global section screen, NOT local 3D boss/fillet validation.
#   - No barrel redesign is frozen by this script.
#
# OUTPUTS
#   phase2e3b5a_barrel_material_audit.csv
#   phase2e3b5a_current_upper_neck_screen.csv
#   phase2e3b5a_required_OD_sweep.csv
#   phase2e3b5a_source_snippets.txt
#   phase2e3b5a_summary.txt
# =============================================================================


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.resolve()

LOAD_CSV = (
    PROJECT_ROOT
    / "phase1_loads"
    / "phase1_load_envelope.csv"
)

BARREL_PY = HERE / "phase2_barrel_sizing.py"
BARREL_CSV = HERE / "phase2_barrel_sizing.csv"
D9_PY = HERE / "phase2_upper_trunnion_sizing.py"
E2_BASELINE = HERE / "phase2e2_v1_baseline.csv"

OUTPUT_AUDIT = HERE / "phase2e3b5a_barrel_material_audit.csv"
OUTPUT_SCREEN = HERE / "phase2e3b5a_current_upper_neck_screen.csv"
OUTPUT_SWEEP = HERE / "phase2e3b5a_required_OD_sweep.csv"
OUTPUT_SNIPPETS = HERE / "phase2e3b5a_source_snippets.txt"
OUTPUT_SUMMARY = HERE / "phase2e3b5a_summary.txt"


# =============================================================================
# PROJECT PRELIMINARY MATERIAL SCREENS
# =============================================================================

SY_7075_MPa = 503.0
SU_7075_MPa = 572.0

SY_300M_MPa = 1517.0
SU_300M_MPa = 1862.0


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
    cols = {
        normalize(col): col
        for col in df.columns
    }

    for alias in aliases:
        key = normalize(alias)

        if key in cols:
            return cols[key]

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
        rows = df.loc[
            pnorm
            == normalize(alias)
        ]

        if not rows.empty:
            return rows.iloc[0][
                vcol
            ]

    return None


def safe_numeric_ast(node):
    """
    Evaluate simple numeric literal expressions only.
    """

    if isinstance(
        node,
        ast.Constant,
    ):
        if isinstance(
            node.value,
            (int, float),
        ):
            return float(
                node.value
            )

        raise ValueError

    if isinstance(
        node,
        ast.UnaryOp,
    ):
        operand = safe_numeric_ast(
            node.operand
        )

        if isinstance(
            node.op,
            ast.UAdd,
        ):
            return operand

        if isinstance(
            node.op,
            ast.USub,
        ):
            return -operand

        raise ValueError

    if isinstance(
        node,
        ast.BinOp,
    ):
        left = safe_numeric_ast(
            node.left
        )

        right = safe_numeric_ast(
            node.right
        )

        ops = {
            ast.Add:
                operator.add,
            ast.Sub:
                operator.sub,
            ast.Mult:
                operator.mul,
            ast.Div:
                operator.truediv,
            ast.Pow:
                operator.pow,
        }

        for cls, fn in ops.items():
            if isinstance(
                node.op,
                cls,
            ):
                return fn(
                    left,
                    right,
                )

        raise ValueError

    raise ValueError


def numeric_assignments(path):
    if not path.exists():
        return {}

    tree = ast.parse(
        path.read_text(
            encoding="utf-8",
            errors="ignore",
        ),
        filename=str(
            path
        ),
    )

    values = {}

    for node in tree.body:
        if not isinstance(
            node,
            ast.Assign,
        ):
            continue

        try:
            value = safe_numeric_ast(
                node.value
            )
        except Exception:
            continue

        for target in node.targets:
            if isinstance(
                target,
                ast.Name,
            ):
                values[
                    target.id
                ] = value

    return values


def literal_assignments(path):
    if not path.exists():
        return {}

    tree = ast.parse(
        path.read_text(
            encoding="utf-8",
            errors="ignore",
        ),
        filename=str(
            path
        ),
    )

    values = {}

    for node in tree.body:
        if not isinstance(
            node,
            ast.Assign,
        ):
            continue

        try:
            value = ast.literal_eval(
                node.value
            )
        except Exception:
            continue

        for target in node.targets:
            if isinstance(
                target,
                ast.Name,
            ):
                values[
                    target.id
                ] = value

    return values


def source_keyword_snippets(
    path,
    keywords,
    radius=4,
):
    if not path.exists():
        return []

    lines = path.read_text(
        encoding="utf-8",
        errors="ignore",
    ).splitlines()

    hit_indices = []

    for i, line in enumerate(
        lines
    ):
        low = line.lower()

        if any(
            kw.lower() in low
            for kw in keywords
        ):
            hit_indices.append(
                i
            )

    ranges = []

    for i in hit_indices:
        start = max(
            0,
            i - radius,
        )

        stop = min(
            len(lines) - 1,
            i + radius,
        )

        if (
            ranges
            and start
            <= ranges[-1][1] + 1
        ):
            ranges[-1] = (
                ranges[-1][0],
                max(
                    ranges[-1][1],
                    stop,
                ),
            )
        else:
            ranges.append(
                (
                    start,
                    stop,
                )
            )

    blocks = []

    for start, stop in ranges:
        block = []

        for j in range(
            start,
            stop + 1,
        ):
            block.append(
                f"{j+1:5d}: "
                f"{lines[j]}"
            )

        blocks.append(
            "\n".join(
                block
            )
        )

    return blocks


def near(value, target, rel=0.02):
    if not np.isfinite(
        value
    ):
        return False

    return abs(
        value
        - target
    ) <= rel * target


def force_columns(df, level):
    result = {}

    for comp in [
        "Fx",
        "Fy",
        "Fz",
    ]:
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
                f"Could not find {comp} {level} column. "
                f"Columns: {list(df.columns)}"
            )

        result[
            comp
        ] = col

    return result


# =============================================================================
# SOURCE GEOMETRY / CURRENT LOADS
# =============================================================================

loads = read_csv(
    LOAD_CSV
)

e2 = read_csv(
    E2_BASELINE
)

d9_literals = literal_assignments(
    D9_PY
)

e_m = float(
    d9_literals[
        "e_m"
    ]
)

rt_m = float(
    d9_literals[
        "rt_m"
    ]
)

h_UA_static_m = float(
    d9_literals[
        "h_UA_static_m"
    ]
)

e2_boundary_mm = float(
    find_parameter(
        e2,
        [
            "preliminary_E3_interface_outer_face_above_U",
        ],
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
        "Could not identify load-case column."
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
# CURRENT RESULTANTS AT E2/E3 BOUNDARY
# =============================================================================

def section_resultants(
    Fx_kN,
    Fy_kN,
    Fz_kN,
    station_above_U_mm,
):
    h_from_A_m = (
        h_UA_static_m
        + station_above_U_mm
        / 1000.0
    )

    arm_m = (
        rt_m
        + h_from_A_m
    )

    Mx_kNm = (
        e_m * Fz_kN
        + arm_m * Fy_kN
    )

    My_kNm = (
        -arm_m * Fx_kN
    )

    Mz_kNm = (
        -e_m * Fx_kN
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


current_rows = []

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
    for _, row in loads.iterrows():

        current_rows.append({
            "level":
                level,
            "case":
                str(
                    row[
                        case_col
                    ]
                ),
            **section_resultants(
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
                e2_boundary_mm,
            ),
        })


current = pd.DataFrame(
    current_rows
)


# =============================================================================
# SECTION STRESS
# =============================================================================

def section_properties(
    OD_mm,
    ID_mm,
):
    Do = (
        OD_mm
        / 1000.0
    )

    Di = (
        ID_mm
        / 1000.0
    )

    if (
        Do <= 0.0
        or Di < 0.0
        or Di >= Do
    ):
        raise ValueError(
            f"Invalid section: OD={OD_mm}, ID={ID_mm}"
        )

    A = (
        math.pi
        / 4.0
        * (
            Do**2
            - Di**2
        )
    )

    I = (
        math.pi
        / 64.0
        * (
            Do**4
            - Di**4
        )
    )

    J = (
        math.pi
        / 32.0
        * (
            Do**4
            - Di**4
        )
    )

    return {
        "A_m2":
            A,
        "I_m4":
            I,
        "J_m4":
            J,
        "c_m":
            Do / 2.0,
    }


def stress_from_resultant(
    result,
    OD_mm,
    ID_mm,
    Kt_bending=1.0,
):
    props = section_properties(
        OD_mm,
        ID_mm,
    )

    N_N = (
        abs(
            result[
                "Fz_kN"
            ]
        )
        * 1000.0
    )

    Mb_Nm = (
        abs(
            result[
                "Mb_kNm"
            ]
        )
        * 1000.0
    )

    T_Nm = (
        abs(
            result[
                "Mz_kNm"
            ]
        )
        * 1000.0
    )

    sigma_ax_Pa = (
        N_N
        / props[
            "A_m2"
        ]
    )

    sigma_b_Pa = (
        Kt_bending
        * Mb_Nm
        * props[
            "c_m"
        ]
        / props[
            "I_m4"
        ]
    )

    tau_t_Pa = (
        T_Nm
        * props[
            "c_m"
        ]
        / props[
            "J_m4"
        ]
    )

    sigma_max_Pa = (
        sigma_ax_Pa
        + sigma_b_Pa
    )

    vm_Pa = math.sqrt(
        sigma_max_Pa**2
        + 3.0
        * tau_t_Pa**2
    )

    return {
        "sigma_ax_MPa":
            sigma_ax_Pa
            / 1e6,
        "sigma_bending_MPa":
            sigma_b_Pa
            / 1e6,
        "tau_torsion_MPa":
            tau_t_Pa
            / 1e6,
        "vm_MPa":
            vm_Pa
            / 1e6,
    }


def governing_stress(
    level,
    OD_mm,
    ID_mm,
    Kt_bending,
):
    subset = current.loc[
        current[
            "level"
        ]
        == level
    ]

    rows = []

    for _, row in subset.iterrows():

        stress = stress_from_resultant(
            row,
            OD_mm,
            ID_mm,
            Kt_bending,
        )

        rows.append({
            "case":
                row[
                    "case"
                ],
            **stress,
        })

    df = pd.DataFrame(
        rows
    )

    idx = df[
        "vm_MPa"
    ].idxmax()

    return df.loc[
        idx
    ]


# =============================================================================
# HISTORICAL BARREL SOURCE / CSV AUDIT
# =============================================================================

audit_rows = []

barrel_numeric = numeric_assignments(
    BARREL_PY
)

barrel_literals = literal_assignments(
    BARREL_PY
)

source_keywords = [
    "material",
    "7075",
    "300M",
    "yield",
    "ultimate",
    "Sy",
    "Su",
    "1517",
    "1862",
    "503",
    "572",
]

snippet_blocks = source_keyword_snippets(
    BARREL_PY,
    source_keywords,
    radius=4,
)

snippet_text = "\n\n".join(
    [
        "=" * 118,
        f"SOURCE: {BARREL_PY}",
        "=" * 118,
        *snippet_blocks,
    ]
)

OUTPUT_SNIPPETS.write_text(
    snippet_text,
    encoding="utf-8",
)


# Record strength-like numeric variables.
for name, value in sorted(
    barrel_numeric.items()
):
    key = name.lower()

    if any(
        token in key
        for token in [
            "yield",
            "ultimate",
            "sy",
            "su",
            "strength",
        ]
    ):
        value_MPa = (
            value
            / 1e6
            if abs(
                value
            ) > 1e6
            else value
        )

        audit_rows.append({
            "audit_type":
                "SOURCE_NUMERIC_ASSIGNMENT",
            "name":
                name,
            "value":
                value_MPa,
            "units":
                "MPa interpreted",
            "classification":
                "",
        })


# Record material-like literal strings.
for name, value in sorted(
    barrel_literals.items()
):
    if isinstance(
        value,
        str,
    ):
        text = (
            name
            + " "
            + value
        ).lower()

        if any(
            token in text
            for token in [
                "material",
                "7075",
                "300m",
                "steel",
                "aluminum",
                "aluminium",
            ]
        ):
            audit_rows.append({
                "audit_type":
                    "SOURCE_LITERAL_ASSIGNMENT",
                "name":
                    name,
                "value":
                    value,
                "units":
                    "",
                "classification":
                    "",
            })


historical_barrel = read_csv(
    BARREL_CSV
)

od_col = find_column(
    historical_barrel,
    [
        "OD_mm",
        "outer_diameter_mm",
    ],
)

id_col = find_column(
    historical_barrel,
    [
        "ID_mm",
        "inner_diameter_mm",
    ],
)

wall_col = find_column(
    historical_barrel,
    [
        "wall_mm",
        "wall_thickness_mm",
    ],
)

limit_vm_col = find_column(
    historical_barrel,
    [
        "limit_vm_MPa",
    ],
)

ult_vm_col = find_column(
    historical_barrel,
    [
        "ultimate_vm_MPa",
    ],
)

limit_ms_col = find_column(
    historical_barrel,
    [
        "MS_limit_yield",
        "MS_limit",
    ],
)

ult_ms_col = find_column(
    historical_barrel,
    [
        "MS_ultimate",
        "MS_ultimate_strength",
    ],
)


if (
    od_col is None
    or wall_col is None
):
    raise KeyError(
        "Could not resolve OD/wall columns in phase2_barrel_sizing.csv."
    )


mask = (
    np.isclose(
        pd.to_numeric(
            historical_barrel[
                od_col
            ],
            errors="coerce",
        ),
        barrel_OD_mm,
    )
    &
    np.isclose(
        pd.to_numeric(
            historical_barrel[
                wall_col
            ],
            errors="coerce",
        ),
        (
            barrel_OD_mm
            - barrel_ID_mm
        ) / 2.0,
    )
)

working_rows = historical_barrel.loc[
    mask
]

if working_rows.empty:
    raise ValueError(
        "Could not find frozen 74/64 working barrel row in "
        "phase2_barrel_sizing.csv."
    )

historic = working_rows.iloc[
    0
]


historic_limit_vm = (
    float(
        historic[
            limit_vm_col
        ]
    )
    if limit_vm_col is not None
    else np.nan
)

historic_ult_vm = (
    float(
        historic[
            ult_vm_col
        ]
    )
    if ult_vm_col is not None
    else np.nan
)

historic_limit_ms = (
    float(
        historic[
            limit_ms_col
        ]
    )
    if limit_ms_col is not None
    else np.nan
)

historic_ult_ms = (
    float(
        historic[
            ult_ms_col
        ]
    )
    if ult_ms_col is not None
    else np.nan
)

implied_limit_allowable = (
    historic_limit_vm
    * (
        1.0
        + historic_limit_ms
    )
    if np.isfinite(
        historic_limit_vm
    )
    and np.isfinite(
        historic_limit_ms
    )
    else np.nan
)

implied_ult_allowable = (
    historic_ult_vm
    * (
        1.0
        + historic_ult_ms
    )
    if np.isfinite(
        historic_ult_vm
    )
    and np.isfinite(
        historic_ult_ms
    )
    else np.nan
)


if (
    near(
        implied_limit_allowable,
        SY_300M_MPa,
    )
    and near(
        implied_ult_allowable,
        SU_300M_MPa,
    )
):
    implied_class = (
        "IMPLIED_300M_ALLOWABLES"
    )

elif (
    near(
        implied_limit_allowable,
        SY_7075_MPa,
    )
    and near(
        implied_ult_allowable,
        SU_7075_MPa,
    )
):
    implied_class = (
        "IMPLIED_7075_ALLOWABLES"
    )

else:
    implied_class = (
        "IMPLIED_ALLOWABLES_UNRESOLVED"
    )


audit_rows.append({
    "audit_type":
        "HISTORICAL_WORKING_ROW",
    "name":
        "74/64_barrel_limit_VM",
    "value":
        historic_limit_vm,
    "units":
        "MPa",
    "classification":
        implied_class,
})

audit_rows.append({
    "audit_type":
        "HISTORICAL_WORKING_ROW",
    "name":
        "74/64_barrel_limit_MS",
    "value":
        historic_limit_ms,
    "units":
        "-",
    "classification":
        implied_class,
})

audit_rows.append({
    "audit_type":
        "HISTORICAL_IMPLIED_ALLOWABLE",
    "name":
        "limit_allowable",
    "value":
        implied_limit_allowable,
    "units":
        "MPa",
    "classification":
        implied_class,
})

audit_rows.append({
    "audit_type":
        "HISTORICAL_WORKING_ROW",
    "name":
        "74/64_barrel_ultimate_VM",
    "value":
        historic_ult_vm,
    "units":
        "MPa",
    "classification":
        implied_class,
})

audit_rows.append({
    "audit_type":
        "HISTORICAL_WORKING_ROW",
    "name":
        "74/64_barrel_ultimate_MS",
    "value":
        historic_ult_ms,
    "units":
        "-",
    "classification":
        implied_class,
})

audit_rows.append({
    "audit_type":
        "HISTORICAL_IMPLIED_ALLOWABLE",
    "name":
        "ultimate_allowable",
    "value":
        implied_ult_allowable,
    "units":
        "MPa",
    "classification":
        implied_class,
})


audit_df = pd.DataFrame(
    audit_rows
)

audit_df.to_csv(
    OUTPUT_AUDIT,
    index=False,
)


# =============================================================================
# CURRENT 74-mm UPPER-NECK SCREEN
# =============================================================================

screen_rows = []

section_cases = [
    (
        "FROZEN_HOLLOW_BARREL",
        barrel_OD_mm,
        barrel_ID_mm,
    ),
    (
        "SOLID_74MM_HEAD_NECK",
        barrel_OD_mm,
        0.0,
    ),
]

for (
    section_name,
    OD_mm,
    ID_mm,
) in section_cases:

    for Kt in [
        1.0,
        1.5,
        2.0,
        2.5,
        3.0,
    ]:

        for level, allowable in [
            (
                "limit",
                SY_7075_MPa,
            ),
            (
                "ultimate",
                SU_7075_MPa,
            ),
        ]:

            gov = governing_stress(
                level,
                OD_mm,
                ID_mm,
                Kt,
            )

            MS = (
                allowable
                / float(
                    gov[
                        "vm_MPa"
                    ]
                )
                - 1.0
            )

            screen_rows.append({
                "section":
                    section_name,
                "OD_mm":
                    OD_mm,
                "ID_mm":
                    ID_mm,
                "Kt_bending":
                    Kt,
                "level":
                    level,
                "governing_case":
                    gov[
                        "case"
                    ],
                "sigma_ax_MPa":
                    gov[
                        "sigma_ax_MPa"
                    ],
                "sigma_bending_MPa":
                    gov[
                        "sigma_bending_MPa"
                    ],
                "tau_torsion_MPa":
                    gov[
                        "tau_torsion_MPa"
                    ],
                "vm_MPa":
                    gov[
                        "vm_MPa"
                    ],
                "7075_screen_allowable_MPa":
                    allowable,
                "MS":
                    MS,
                "PASS":
                    MS >= 0.0,
            })


screen_df = pd.DataFrame(
    screen_rows
)

screen_df.to_csv(
    OUTPUT_SCREEN,
    index=False,
)


# =============================================================================
# REQUIRED OD SWEEP AT CURRENT E2 BOUNDARY
# =============================================================================

sweep_rows = []

Kt_values = [
    1.0,
    1.5,
    2.0,
    2.5,
    3.0,
]

for section_type in [
    "ANNULAR_ID64",
    "SOLID",
]:

    for Kt in Kt_values:

        first_pass = None

        for OD_mm in np.arange(
            74.0,
            140.0 + 0.0001,
            0.5,
        ):

            ID_mm = (
                barrel_ID_mm
                if section_type
                == "ANNULAR_ID64"
                else 0.0
            )

            if ID_mm >= OD_mm:
                continue

            gov_limit = governing_stress(
                "limit",
                OD_mm,
                ID_mm,
                Kt,
            )

            gov_ultimate = governing_stress(
                "ultimate",
                OD_mm,
                ID_mm,
                Kt,
            )

            MS_limit = (
                SY_7075_MPa
                / float(
                    gov_limit[
                        "vm_MPa"
                    ]
                )
                - 1.0
            )

            MS_ultimate = (
                SU_7075_MPa
                / float(
                    gov_ultimate[
                        "vm_MPa"
                    ]
                )
                - 1.0
            )

            passes = (
                MS_limit >= 0.0
                and MS_ultimate >= 0.0
            )

            sweep_rows.append({
                "section_type":
                    section_type,
                "Kt_bending":
                    Kt,
                "OD_mm":
                    OD_mm,
                "ID_mm":
                    ID_mm,
                "limit_case":
                    gov_limit[
                        "case"
                    ],
                "limit_vm_MPa":
                    gov_limit[
                        "vm_MPa"
                    ],
                "MS_limit_7075":
                    MS_limit,
                "ultimate_case":
                    gov_ultimate[
                        "case"
                    ],
                "ultimate_vm_MPa":
                    gov_ultimate[
                        "vm_MPa"
                    ],
                "MS_ultimate_7075":
                    MS_ultimate,
                "PASS":
                    passes,
            })

            if (
                passes
                and first_pass is None
            ):
                first_pass = (
                    OD_mm
                )


sweep_df = pd.DataFrame(
    sweep_rows
)

sweep_df.to_csv(
    OUTPUT_SWEEP,
    index=False,
)


# =============================================================================
# CONSOLE REPORT
# =============================================================================

print("=" * 124)
print(
    " PHASE 2E3-B5A — BARREL MATERIAL / UPPER-NECK STRUCTURAL AUDIT V0.1"
)
print("=" * 124)

print("\nSOURCE CONNECTION")
print("-" * 124)
print(
    f"Barrel source:                    {BARREL_PY}"
)
print(
    f"Barrel historical results:        {BARREL_CSV}"
)
print(
    f"Current Phase 1 envelope:         {LOAD_CSV}"
)
print(
    f"Frozen E2 baseline:               {E2_BASELINE}"
)

print("\nHISTORICAL 74/64 BARREL ROW")
print("-" * 124)
print(
    f"Historical limit VM:              {historic_limit_vm:.3f} MPa"
)
print(
    f"Historical limit margin:          {historic_limit_ms:+.6f}"
)
print(
    f"Implied limit allowable:          {implied_limit_allowable:.3f} MPa"
)
print(
    f"Historical ultimate VM:           {historic_ult_vm:.3f} MPa"
)
print(
    f"Historical ultimate margin:       {historic_ult_ms:+.6f}"
)
print(
    f"Implied ultimate allowable:       {implied_ult_allowable:.3f} MPa"
)
print(
    f"Implied material convention:      {implied_class}"
)

print("\nCURRENT E3 BOUNDARY")
print("-" * 124)
print(
    f"E2/E3 boundary:                   {e2_boundary_mm:.6f} mm above U"
)
print(
    f"Frozen barrel section:            {barrel_OD_mm:.1f} OD / {barrel_ID_mm:.1f} ID mm"
)
print(
    f"7075 yield / ultimate screen:     {SY_7075_MPa:.1f} / {SU_7075_MPa:.1f} MPa"
)

print("\nCURRENT 74-mm SECTION SCREEN")
print("-" * 124)
print(
    f"{'Section':<24}"
    f"{'Kt':>6}"
    f"{'Level':>10}"
    f"{'Case':>8}"
    f"{'VM MPa':>12}"
    f"{'MS':>10}"
    f"{'PASS':>8}"
)
print("-" * 78)

for _, row in screen_df.iterrows():
    print(
        f"{row['section']:<24}"
        f"{row['Kt_bending']:>6.1f}"
        f"{row['level']:>10}"
        f"{str(row['governing_case']):>8}"
        f"{row['vm_MPa']:>12.1f}"
        f"{row['MS']:>10.3f}"
        f"{str(bool(row['PASS'])):>8}"
    )

print("\nMINIMUM OD REQUIRED AT CURRENT E2 BOUNDARY")
print("-" * 124)
print(
    f"{'Section':<18}"
    f"{'Kt':>8}"
    f"{'Min OD':>12}"
)
print("-" * 42)

minimum_rows = []

for section_type in [
    "ANNULAR_ID64",
    "SOLID",
]:
    for Kt in Kt_values:

        sub = sweep_df.loc[
            (
                sweep_df[
                    "section_type"
                ]
                == section_type
            )
            &
            np.isclose(
                sweep_df[
                    "Kt_bending"
                ],
                Kt,
            )
            &
            (
                sweep_df[
                    "PASS"
                ]
            )
        ]

        min_OD = (
            float(
                sub[
                    "OD_mm"
                ].min()
            )
            if not sub.empty
            else np.nan
        )

        minimum_rows.append(
            (
                section_type,
                Kt,
                min_OD,
            )
        )

        print(
            f"{section_type:<18}"
            f"{Kt:>8.1f}"
            f"{min_OD:>12.1f}"
            if np.isfinite(
                min_OD
            )
            else
            f"{section_type:<18}"
            f"{Kt:>8.1f}"
            f"{'NO PASS':>12}"
        )

print("\nB5A DISPOSITION")
print("-" * 124)

if implied_class == "IMPLIED_300M_ALLOWABLES":
    print(
        "HISTORICAL MATERIAL-BASIS MISMATCH CONFIRMED:"
    )
    print(
        "the old 74/64 barrel margins imply approximately 300M allowables, "
        "not the current 7075-T6 project baseline."
    )
    print(
        "Therefore the old barrel PASS must NOT be used as evidence that a "
        "74/64 7075 barrel is structurally adequate."
    )

elif implied_class == "IMPLIED_7075_ALLOWABLES":
    print(
        "Historical working-row margins are consistent with the 7075-T6 project screen."
    )

else:
    print(
        "Historical material basis could not be resolved solely from the CSV margin back-calculation."
    )
    print(
        "Review phase2e3b5a_source_snippets.txt before closing the material audit."
    )

print(
    "Use the CURRENT E3-boundary section screen above to decide whether the "
    "upper barrel/head region must be locally enlarged or re-architected."
)

print("\nOUTPUT FILES")
print("-" * 124)
print(
    f"Material audit:                   {OUTPUT_AUDIT}"
)
print(
    f"Current upper-neck screen:        {OUTPUT_SCREEN}"
)
print(
    f"Required OD sweep:                {OUTPUT_SWEEP}"
)
print(
    f"Barrel source snippets:           {OUTPUT_SNIPPETS}"
)
print(
    f"Summary:                          {OUTPUT_SUMMARY}"
)

# Summary
summary_lines = [
    "=" * 124,
    " PHASE 2E3-B5A — BARREL MATERIAL / UPPER-NECK STRUCTURAL AUDIT V0.1",
    "=" * 124,
    "",
    f"Historical 74/64 limit VM / MS: {historic_limit_vm:.6f} MPa / {historic_limit_ms:+.6f}",
    f"Historical implied limit allowable: {implied_limit_allowable:.6f} MPa",
    f"Historical 74/64 ultimate VM / MS: {historic_ult_vm:.6f} MPa / {historic_ult_ms:+.6f}",
    f"Historical implied ultimate allowable: {implied_ult_allowable:.6f} MPa",
    f"Historical implied material convention: {implied_class}",
    "",
    f"Current E2/E3 boundary: {e2_boundary_mm:.6f} mm above U",
    f"Frozen section: {barrel_OD_mm:.3f} OD / {barrel_ID_mm:.3f} ID mm",
    "",
    "No redesign is frozen by this audit.",
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
