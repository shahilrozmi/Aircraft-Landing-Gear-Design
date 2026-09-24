from pathlib import Path
import ast
import math

import numpy as np
import pandas as pd


# =============================================================================
# LANDING GEAR DESIGN PROJECT
# PHASE 2E2-B — UPPER-HEAD / PRESSURE-CLOSURE AUDIT V0.3
#
# PURPOSE
#   Final pre-lock audit for Phase 2E2:
#
#   A. Read the ACTUAL Phase 2 barrel-sizing source and reconcile it against
#      the barrel dimensions currently carried by Phase 2E2.
#
#   B. If and only if the barrel source agrees with E2, check:
#        - thick-wall barrel pressure stress,
#        - preliminary circular pressure-closure thickness,
#        - pressure-closure axial packaging,
#        - E2 -> E3 solid-head interface.
#
# CRITICAL GATE
#   If the source barrel ID / OD does not agree with the dimensions used by E2,
#   this script STOPS the closure-sizing portion. The E2 gas/oil volumes and
#   axial closure position depend directly on barrel area and must be rebuilt
#   using the source-locked barrel geometry before Phase 2E2 can be frozen.
#
# STRUCTURAL SCREENING
#   Barrel:
#       Lamé thick-cylinder stresses at the inner wall, closed-end cylinder.
#
#   Closure:
#       conservative simply-supported circular flat-plate bending screen
#
#       sigma_b,max = [3(3+nu)/8] * p * a^2 / t^2
#
#   Limit check:
#       full-physical-stroke differential pressure -> yield allowable
#
#   Ultimate check:
#       1.5 * full-physical-stroke differential pressure -> tensile allowable
#
#   The plate screen is preliminary only. Detailed closure geometry, seals,
#   threads/retainers, ports and local stress concentration require later CAD /
#   detailed analysis / FEA.
# =============================================================================


# =============================================================================
# 1. PATHS
# =============================================================================

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.resolve()

BARREL_CSV = (
    HERE / "phase2_barrel_sizing.csv"
).resolve()

BARREL_PY = (
    HERE / "phase2_barrel_sizing.py"
).resolve()

E2_ARCH_CSV = (
    HERE / "phase2e2_architecture_inputs.csv"
).resolve()

E2_STATES_CSV = (
    HERE / "phase2e2_stroke_cavity_states.csv"
).resolve()

E2_DESIGN_ENVELOPE_CSV = (
    HERE / "phase2e2_design_envelope.csv"
).resolve()

E2_METERING_CANDIDATE_CSV = (
    HERE / "phase2e2_metering_working_candidate.csv"
).resolve()

PHASE1_PREFERRED = (
    PROJECT_ROOT
    / "phase1_model_development"
    / "landing_dynamic_v04_2dof.py"
).resolve()

OUTPUT_SOURCE_AUDIT_CSV = (
    HERE / "phase2e2b_barrel_source_audit.csv"
).resolve()

OUTPUT_PRESSURE_CHECK_CSV = (
    HERE / "phase2e2b_pressure_structure_checks.csv"
).resolve()

OUTPUT_CLOSURE_SWEEP_CSV = (
    HERE / "phase2e2b_closure_thickness_sweep.csv"
).resolve()

OUTPUT_E3_INTERFACE_CSV = (
    HERE / "phase2e2b_e3_interface.csv"
).resolve()


# =============================================================================
# 2. PROJECT MATERIAL BASELINE
# =============================================================================
#
# Used only if the barrel sizing CSV / Python source does not expose the
# properties explicitly. These are the already locked Phase 2 material values,
# not newly invented values.

MAT_7075 = {
    "E_GPa": 71.7,
    "nu": 0.33,
    "Sy_MPa": 503.0,
    "Su_MPa": 572.0,
}

ULTIMATE_FACTOR = 1.50

# =============================================================================
# 2A. PRIOR PHASE 2D WORKING BARREL BASELINE
# =============================================================================
#
# This is NOT inferred from the current CSV PASS column. Phase 2D previously
# retained this geometry as the WORKING packaging barrel candidate even though
# thinner sweep rows also passed the mathematical strength checks.
#
# Rationale carried from Phase 2D:
#   - 64 mm ID gives 3 mm radial clearance around the 58 mm piston.
#   - 5 mm wall / 74 mm OD was retained as a practical working barrel rather
#     than choosing the minimum mathematical wall.
#   - Smooth-barrel strength was not the sizing driver; side-load bending,
#     detail features, bushings/gland/seals/transitions and manufacturability
#     were intentionally left for later detail.
#
# This E2-B audit therefore verifies that the exact prior working candidate is
# present in the source sweep, then uses it for the closure audit. It remains a
# WORKING BASELINE until E2 is formally frozen.

PHASE2D_WORKING_BARREL_ID_MM = 64.0
PHASE2D_WORKING_BARREL_WALL_MM = 5.0
PHASE2D_WORKING_BARREL_OD_MM = 74.0

# Source geometry must agree with the E2-carried geometry this closely before
# the pressure-head calculation is allowed to proceed.
BARREL_GEOMETRY_TOL_MM = 0.10

# Screening sweep only; not an automatic manufacturing selection.
CLOSURE_THICKNESS_SWEEP_MM = np.arange(
    3.0,
    20.0 + 0.001,
    0.5,
)


# =============================================================================
# 3. BASIC UTILITIES
# =============================================================================

def normalize(text):
    return "".join(
        ch for ch in str(text).lower()
        if ch.isalnum()
    )


def read_csv_flexible(path):
    if not path.exists():
        raise FileNotFoundError(
            f"Required CSV not found:\n{path}"
        )

    df = pd.read_csv(
        path,
        sep=None,
        engine="python",
        encoding="utf-8-sig",
    )

    df.columns = [
        str(col).replace("\ufeff", "").strip()
        for col in df.columns
    ]

    return df


def numeric_series(series):
    return pd.to_numeric(
        series,
        errors="coerce",
    )


def circular_area_mm2(d_mm):
    return math.pi * d_mm**2 / 4.0


def parameter_value(df, parameter):
    norm_cols = {
        normalize(col): col
        for col in df.columns
    }

    if (
        "parameter" not in norm_cols
        or "value" not in norm_cols
    ):
        raise ValueError(
            "Expected a parameter/value table."
        )

    pcol = norm_cols["parameter"]
    vcol = norm_cols["value"]

    mask = (
        df[pcol]
        .astype(str)
        .map(normalize)
        == normalize(parameter)
    )

    rows = df.loc[mask]

    if rows.empty:
        raise KeyError(
            f"Parameter not found: {parameter}"
        )

    return rows.iloc[0][vcol]


def parameter_float(df, parameter):
    return float(
        pd.to_numeric(
            pd.Series(
                [parameter_value(df, parameter)]
            ),
            errors="raise",
        ).iloc[0]
    )


def first_existing_parameter(
    df,
    names,
):
    for name in names:
        try:
            return parameter_float(
                df,
                name,
            ), name
        except Exception:
            pass

    return None, None


# =============================================================================
# 4. SAFE PYTHON NUMERIC-SOURCE READER
# =============================================================================

def numeric_literal(node, env=None):
    if env is None:
        env = {}

    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        return None

    if isinstance(node, ast.Name):
        value = env.get(node.id)

        if isinstance(value, (int, float)):
            return float(value)

        return None

    if isinstance(node, ast.UnaryOp):
        value = numeric_literal(
            node.operand,
            env,
        )

        if value is None:
            return None

        if isinstance(node.op, ast.USub):
            return -value

        if isinstance(node.op, ast.UAdd):
            return value

        return None

    if isinstance(node, ast.BinOp):
        left = numeric_literal(
            node.left,
            env,
        )

        right = numeric_literal(
            node.right,
            env,
        )

        if left is None or right is None:
            return None

        if isinstance(node.op, ast.Add):
            return left + right

        if isinstance(node.op, ast.Sub):
            return left - right

        if isinstance(node.op, ast.Mult):
            return left * right

        if isinstance(node.op, ast.Div):
            return left / right

        if isinstance(node.op, ast.Pow):
            return left**right

    return None


def numeric_environment_from_py(path):
    if not path.exists():
        return {}

    source = path.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    tree = ast.parse(
        source,
        filename=str(path),
    )

    assignments = []

    for node in tree.body:

        if isinstance(node, ast.Assign):
            names = [
                target.id
                for target in node.targets
                if isinstance(target, ast.Name)
            ]

            if names:
                assignments.append(
                    (names, node.value)
                )

        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                assignments.append(
                    ([node.target.id], node.value)
                )

    env = {}

    for _ in range(
        max(
            1,
            len(assignments) + 1,
        )
    ):

        changed = False

        for names, expr in assignments:
            value = numeric_literal(
                expr,
                env,
            )

            if value is None:
                continue

            for name in names:
                if (
                    name not in env
                    or env[name] != value
                ):
                    env[name] = value
                    changed = True

        if not changed:
            break

    return env


# =============================================================================
# 5. BARREL SOURCE RESOLUTION
# =============================================================================

ID_ALIASES = [
    "barrel_ID_mm",
    "ID_mm",
    "id_mm",
    "Di_mm",
    "D_i_mm",
    "inner_diameter_mm",
    "inside_diameter_mm",
    "bore_mm",
]

OD_ALIASES = [
    "barrel_OD_mm",
    "OD_mm",
    "od_mm",
    "Do_mm",
    "D_o_mm",
    "outer_diameter_mm",
    "outside_diameter_mm",
]

WALL_ALIASES = [
    "barrel_wall_mm",
    "wall_mm",
    "wall_thickness_mm",
    "thickness_mm",
    "t_mm",
]

SELECTION_ALIASES = [
    "selected",
    "preferred",
    "locked",
    "chosen",
    "baseline",
    "selection",
    "status",
]


def resolve_column(
    df,
    aliases,
):
    normalized = {
        normalize(col): col
        for col in df.columns
    }

    for alias in aliases:
        key = normalize(alias)

        if key in normalized:
            return normalized[key]

    return None


def truthy_selection(value):
    s = str(value).strip().lower()

    return (
        s in {
            "1",
            "true",
            "yes",
            "y",
            "selected",
            "preferred",
            "locked",
            "chosen",
            "baseline",
            "pass_selected",
        }
        or "selected" in s
        or "preferred" in s
        or "locked" in s
        or "chosen" in s
    )


def resolve_barrel_from_parameter_table(
    df,
):
    id_value, id_name = first_existing_parameter(
        df,
        [
            "barrel_ID_mm",
            "barrel_ID",
            "ID_mm",
            "inner_diameter_mm",
        ],
    )

    od_value, od_name = first_existing_parameter(
        df,
        [
            "barrel_OD_mm",
            "barrel_OD",
            "OD_mm",
            "outer_diameter_mm",
        ],
    )

    wall_value, wall_name = first_existing_parameter(
        df,
        [
            "barrel_wall_mm",
            "barrel_wall",
            "wall_mm",
            "wall_thickness_mm",
        ],
    )

    # Unit heuristic for parameter/value sources:
    # E2 project geometry values in meters are normally < 1.
    if id_value is not None and id_value < 1.0:
        id_value *= 1000.0

    if od_value is not None and od_value < 1.0:
        od_value *= 1000.0

    if wall_value is not None and wall_value < 0.1:
        wall_value *= 1000.0

    if id_value is None and od_value is not None and wall_value is not None:
        id_value = (
            od_value
            - 2.0 * wall_value
        )

    if od_value is None and id_value is not None and wall_value is not None:
        od_value = (
            id_value
            + 2.0 * wall_value
        )

    if wall_value is None and id_value is not None and od_value is not None:
        wall_value = (
            od_value
            - id_value
        ) / 2.0

    if (
        id_value is None
        or od_value is None
        or wall_value is None
    ):
        return None

    return {
        "ID_mm": float(id_value),
        "OD_mm": float(od_value),
        "wall_mm": float(wall_value),
        "selection_method": (
            "PARAMETER_VALUE_TABLE"
        ),
    }


def resolve_barrel_from_wide_table(
    df,
):
    """
    Resolve a selected barrel geometry without guessing.

    Selection order:
      1. exactly one explicit selected/preferred/locked row,
      2. exactly one row whose status/result says PASS,
      3. exactly one usable geometry row,
      4. otherwise return AMBIGUOUS together with a diagnostic table.

    This deliberately does NOT choose "smallest", "lightest", or "first PASS"
    unless the Phase 2 source explicitly marks a single row. That prevents an
    invented geometry from being promoted into E2.
    """

    id_col = resolve_column(
        df,
        ID_ALIASES,
    )

    od_col = resolve_column(
        df,
        OD_ALIASES,
    )

    wall_col = resolve_column(
        df,
        WALL_ALIASES,
    )

    count = sum(
        col is not None
        for col in [
            id_col,
            od_col,
            wall_col,
        ]
    )

    if count < 2:
        return {
            "status": "UNRESOLVED",
            "reason": (
                "Fewer than two recognizable ID / OD / wall columns."
            ),
            "diagnostic_df": df.copy(),
            "recognized_columns": {
                "ID": id_col,
                "OD": od_col,
                "wall": wall_col,
            },
        }

    work = df.copy()

    for col in [
        id_col,
        od_col,
        wall_col,
    ]:
        if col is not None:
            work[col] = numeric_series(
                work[col]
            )

    geometry_cols = [
        col
        for col in [
            id_col,
            od_col,
            wall_col,
        ]
        if col is not None
    ]

    work = work.loc[
        work[
            geometry_cols
        ]
        .notna()
        .sum(axis=1)
        >= 2
    ].copy()

    if work.empty:
        return {
            "status": "UNRESOLVED",
            "reason": "No rows contain usable barrel geometry.",
            "diagnostic_df": df.copy(),
            "recognized_columns": {
                "ID": id_col,
                "OD": od_col,
                "wall": wall_col,
            },
        }

    # ------------------------------------------------------------------
    # 1. Explicit selection-like columns.
    # ------------------------------------------------------------------
    explicit_candidates = []

    for col in work.columns:
        key = normalize(col)

        if any(
            token in key
            for token in [
                "selected",
                "preferred",
                "locked",
                "chosen",
                "baseline",
                "selection",
            ]
        ):
            explicit_candidates.append(
                col
            )

    for selection_col in explicit_candidates:
        mask = work[
            selection_col
        ].map(
            truthy_selection
        )

        selected = work.loc[
            mask
        ]

        if len(selected) == 1:
            row = selected.iloc[0]

            return {
                "status": "RESOLVED",
                "row": row,
                "ID_col": id_col,
                "OD_col": od_col,
                "wall_col": wall_col,
                "selection_method": (
                    f"EXPLICIT_SELECTION_COLUMN:{selection_col}"
                ),
                "diagnostic_df": work,
            }

    # ------------------------------------------------------------------
    # 2. Exactly one explicit PASS row.
    #
    # We accept this only if exactly one row is clearly PASS. Multiple PASS
    # rows remain ambiguous because the source may represent a sizing sweep.
    # ------------------------------------------------------------------
    pass_like_columns = []

    for col in work.columns:
        key = normalize(col)

        if any(
            token in key
            for token in [
                "status",
                "result",
                "check",
                "passfail",
                "verdict",
            ]
        ):
            pass_like_columns.append(
                col
            )

    for status_col in pass_like_columns:

        def is_clear_pass(value):
            s = str(value).strip().lower()

            if "fail" in s:
                return False

            return (
                s == "pass"
                or s.startswith("pass_")
                or s.endswith("_pass")
                or s == "ok"
                or s == "acceptable"
            )

        mask = work[
            status_col
        ].map(
            is_clear_pass
        )

        passing = work.loc[
            mask
        ]

        if len(passing) == 1:
            row = passing.iloc[0]

            return {
                "status": "RESOLVED",
                "row": row,
                "ID_col": id_col,
                "OD_col": od_col,
                "wall_col": wall_col,
                "selection_method": (
                    f"UNIQUE_PASS_ROW:{status_col}"
                ),
                "diagnostic_df": work,
            }

    # ------------------------------------------------------------------
    # 3. Exactly one geometry row.
    # ------------------------------------------------------------------
    if len(work) == 1:
        return {
            "status": "RESOLVED",
            "row": work.iloc[0],
            "ID_col": id_col,
            "OD_col": od_col,
            "wall_col": wall_col,
            "selection_method": "ONLY_GEOMETRY_ROW",
            "diagnostic_df": work,
        }

    # ------------------------------------------------------------------
    # 4. Ambiguous. Do not guess.
    # ------------------------------------------------------------------
    return {
        "status": "AMBIGUOUS",
        "reason": (
            "Multiple candidate barrel rows remain and the source does not "
            "identify one unique selected / preferred / locked / PASS design."
        ),
        "diagnostic_df": work,
        "recognized_columns": {
            "ID": id_col,
            "OD": od_col,
            "wall": wall_col,
        },
        "explicit_selection_columns_checked": explicit_candidates,
        "pass_like_columns_checked": pass_like_columns,
    }


def finalize_barrel_geometry_from_result(
    result,
):
    """
    Convert a RESOLVED wide-table result into ID / OD / wall values.
    """

    row = result["row"]

    id_col = result["ID_col"]
    od_col = result["OD_col"]
    wall_col = result["wall_col"]

    id_value = (
        float(row[id_col])
        if id_col is not None
        else None
    )

    od_value = (
        float(row[od_col])
        if od_col is not None
        else None
    )

    wall_value = (
        float(row[wall_col])
        if wall_col is not None
        else None
    )

    if id_value is None:
        id_value = (
            od_value
            - 2.0 * wall_value
        )

    if od_value is None:
        od_value = (
            id_value
            + 2.0 * wall_value
        )

    if wall_value is None:
        wall_value = (
            od_value
            - id_value
        ) / 2.0

    return {
        "ID_mm": id_value,
        "OD_mm": od_value,
        "wall_mm": wall_value,
        "selection_method": result[
            "selection_method"
        ],
    }


def resolve_prior_phase2d_working_candidate(
    df,
):
    """
    Verify that the exact prior Phase 2D working barrel candidate exists in the
    current source sweep.

    This is intentionally an exact design-history match, not a new optimization
    rule such as "first PASS" or "minimum mass".
    """

    id_col = resolve_column(
        df,
        ID_ALIASES,
    )

    od_col = resolve_column(
        df,
        OD_ALIASES,
    )

    wall_col = resolve_column(
        df,
        WALL_ALIASES,
    )

    if (
        id_col is None
        or od_col is None
        or wall_col is None
    ):
        return None

    work = df.copy()

    for col in [
        id_col,
        od_col,
        wall_col,
    ]:
        work[col] = numeric_series(
            work[col]
        )

    mask = (
        np.isclose(
            work[id_col],
            PHASE2D_WORKING_BARREL_ID_MM,
            atol=1e-9,
        )
        & np.isclose(
            work[wall_col],
            PHASE2D_WORKING_BARREL_WALL_MM,
            atol=1e-9,
        )
        & np.isclose(
            work[od_col],
            PHASE2D_WORKING_BARREL_OD_MM,
            atol=1e-9,
        )
    )

    rows = work.loc[
        mask
    ]

    if len(rows) != 1:
        return None

    return {
        "status": "RESOLVED",
        "geometry": {
            "ID_mm": PHASE2D_WORKING_BARREL_ID_MM,
            "OD_mm": PHASE2D_WORKING_BARREL_OD_MM,
            "wall_mm": PHASE2D_WORKING_BARREL_WALL_MM,
            "selection_method": (
                "PRIOR_PHASE2D_WORKING_BASELINE_EXACT_MATCH"
            ),
        },
        "df": df,
        "diagnostic_df": work,
        "matched_row": rows.iloc[0],
    }


def resolve_barrel_geometry():
    df = read_csv_flexible(
        BARREL_CSV
    )

    norm_cols = {
        normalize(col)
        for col in df.columns
    }

    # -------------------------------------------------------------
    # 0. Project design-history exact match
    # -------------------------------------------------------------
    historical_match = (
        resolve_prior_phase2d_working_candidate(
            df
        )
    )

    if historical_match is not None:
        return historical_match

    # -------------------------------------------------------------
    # 1. Parameter/value table
    # -------------------------------------------------------------
    if (
        "parameter" in norm_cols
        and "value" in norm_cols
    ):
        result = (
            resolve_barrel_from_parameter_table(
                df
            )
        )

        if result is not None:
            return {
                "status": "RESOLVED",
                "geometry": result,
                "df": df,
                "diagnostic_df": df,
            }

    # -------------------------------------------------------------
    # Wide candidate table
    # -------------------------------------------------------------
    result = resolve_barrel_from_wide_table(
        df
    )

    if result["status"] == "RESOLVED":
        geometry = (
            finalize_barrel_geometry_from_result(
                result
            )
        )

        return {
            "status": "RESOLVED",
            "geometry": geometry,
            "df": df,
            "diagnostic_df": result[
                "diagnostic_df"
            ],
        }

    return {
        "status": result["status"],
        "reason": result.get(
            "reason",
            "Unknown barrel-source ambiguity.",
        ),
        "df": df,
        "diagnostic_df": result.get(
            "diagnostic_df",
            df,
        ),
        "recognized_columns": result.get(
            "recognized_columns",
            {},
        ),
        "explicit_selection_columns_checked": result.get(
            "explicit_selection_columns_checked",
            [],
        ),
        "pass_like_columns_checked": result.get(
            "pass_like_columns_checked",
            [],
        ),
    }


# =============================================================================
# 6. MATERIAL RESOLUTION
# =============================================================================

def find_numeric_column_value(
    df,
    aliases,
):
    col = resolve_column(
        df,
        aliases,
    )

    if col is None:
        return None

    values = numeric_series(
        df[col]
    ).dropna()

    if values.empty:
        return None

    unique = np.unique(
        values.to_numpy(
            dtype=float
        )
    )

    if len(unique) == 1:
        return float(unique[0])

    return None


def resolve_material_properties(
    barrel_df,
):
    material = dict(
        MAT_7075
    )

    sources = {
        key: "PROJECT_LOCKED_7075_T6_BASELINE"
        for key in material
    }

    # Wide-table CSV attempt.
    csv_candidates = {
        "E_GPa": [
            "E_GPa",
            "elastic_modulus_GPa",
        ],
        "nu": [
            "nu",
            "poisson",
            "poissons_ratio",
        ],
        "Sy_MPa": [
            "Sy_MPa",
            "yield_MPa",
            "yield_strength_MPa",
        ],
        "Su_MPa": [
            "Su_MPa",
            "ultimate_MPa",
            "ultimate_strength_MPa",
        ],
    }

    for key, aliases in csv_candidates.items():
        value = find_numeric_column_value(
            barrel_df,
            aliases,
        )

        if value is not None:
            material[key] = value
            sources[key] = (
                f"SOURCE_CSV:{BARREL_CSV.name}"
            )

    # Parameter/value CSV attempt.
    norm_cols = {
        normalize(col)
        for col in barrel_df.columns
    }

    if (
        "parameter" in norm_cols
        and "value" in norm_cols
    ):
        parameter_candidates = {
            "E_GPa": [
                "E_GPa",
                "E_7075_GPa",
            ],
            "nu": [
                "nu",
                "nu_7075",
            ],
            "Sy_MPa": [
                "Sy_MPa",
                "Sy_7075_MPa",
            ],
            "Su_MPa": [
                "Su_MPa",
                "Su_7075_MPa",
            ],
        }

        for key, names in parameter_candidates.items():
            value, used = first_existing_parameter(
                barrel_df,
                names,
            )

            if value is not None:
                material[key] = value
                sources[key] = (
                    f"SOURCE_CSV_PARAMETER:{used}"
                )

    # Python source attempt.
    env = numeric_environment_from_py(
        BARREL_PY
    )

    py_name_sets = {
        "E_GPa": [
            "E_7075_GPa",
            "E_GPa",
        ],
        "nu": [
            "nu_7075",
            "nu",
        ],
        "Sy_MPa": [
            "Sy_7075_MPa",
            "Sy_MPa",
            "sigma_y_7075_MPa",
        ],
        "Su_MPa": [
            "Su_7075_MPa",
            "Su_MPa",
            "sigma_u_7075_MPa",
        ],
    }

    for key, names in py_name_sets.items():
        for name in names:
            if name in env:
                value = float(
                    env[name]
                )

                # Common SI source forms.
                if key == "E_GPa" and value > 1e6:
                    value /= 1e9

                if key in {
                    "Sy_MPa",
                    "Su_MPa",
                } and value > 1e4:
                    value /= 1e6

                material[key] = value
                sources[key] = (
                    f"SOURCE_PY:{BARREL_PY.name}:{name}"
                )
                break

    return material, sources


# =============================================================================
# 7. PHASE 1 ATMOSPHERIC PRESSURE
# =============================================================================

def resolve_phase1_patm():
    if not PHASE1_PREFERRED.exists():
        matches = list(
            PROJECT_ROOT.rglob(
                "landing_dynamic_v04_2dof.py"
            )
        )

        if not matches:
            raise FileNotFoundError(
                "Current Phase 1 model not found."
            )

        path = matches[0]

    else:
        path = PHASE1_PREFERRED

    env = numeric_environment_from_py(
        path
    )

    if "P_atm" not in env:
        raise KeyError(
            f"P_atm not resolved from {path}"
        )

    return float(
        env["P_atm"]
    ), path


# =============================================================================
# 8. STRUCTURAL FORMULAE
# =============================================================================

def lame_inner_stresses_MPa(
    ID_mm,
    OD_mm,
    p_MPa,
):
    """
    Closed-end thick cylinder, external pressure approximately zero.

    At r = ri:
        sigma_r     = -p
        sigma_theta = p (ro^2 + ri^2)/(ro^2 - ri^2)
        sigma_z     = p ri^2/(ro^2 - ri^2)
    """

    ri = ID_mm / 2.0
    ro = OD_mm / 2.0

    denom = (
        ro**2
        - ri**2
    )

    if denom <= 0.0:
        raise ValueError(
            "Invalid barrel radii."
        )

    sigma_r = -p_MPa

    sigma_theta = (
        p_MPa
        * (
            ro**2
            + ri**2
        )
        / denom
    )

    sigma_z = (
        p_MPa
        * ri**2
        / denom
    )

    vm = math.sqrt(
        (
            (
                sigma_theta
                - sigma_r
            )**2
            + (
                sigma_r
                - sigma_z
            )**2
            + (
                sigma_z
                - sigma_theta
            )**2
        )
        / 2.0
    )

    return {
        "sigma_r_MPa": sigma_r,
        "sigma_theta_MPa": sigma_theta,
        "sigma_z_MPa": sigma_z,
        "von_mises_MPa": vm,
    }


def closure_sigma_simply_supported_MPa(
    p_MPa,
    radius_mm,
    thickness_mm,
    nu,
):
    """
    Conservative preliminary circular-plate screen.

        sigma = K p a^2 / t^2
        K = 3(3+nu)/8
    """

    K = (
        3.0
        * (
            3.0
            + nu
        )
        / 8.0
    )

    return (
        K
        * p_MPa
        * radius_mm**2
        / thickness_mm**2
    )


def closure_sigma_clamped_reference_MPa(
    p_MPa,
    radius_mm,
    thickness_mm,
):
    """
    Clamped-edge reference using the edge radial moment:

        sigma ~= 3 p a^2 / (4 t^2)

    Not used to select the preliminary minimum; included only to show the
    conservatism of the simply-supported screen.
    """

    return (
        3.0
        * p_MPa
        * radius_mm**2
        / (
            4.0
            * thickness_mm**2
        )
    )


def closure_required_thickness_mm(
    p_MPa,
    radius_mm,
    allowable_MPa,
    nu,
):
    K = (
        3.0
        * (
            3.0
            + nu
        )
        / 8.0
    )

    return (
        radius_mm
        * math.sqrt(
            K
            * p_MPa
            / allowable_MPa
        )
    )


# =============================================================================
# 9. E2 SOURCE LOADERS
# =============================================================================

def read_state(
    states,
    state_name,
):
    mask = (
        states["state"]
        .astype(str)
        .map(normalize)
        == normalize(state_name)
    )

    rows = states.loc[mask]

    if rows.empty:
        raise KeyError(
            f"E2 state not found: {state_name}"
        )

    return rows.iloc[0]


def read_design_envelope_value(
    df,
    quantity,
):
    qcol = resolve_column(
        df,
        ["quantity"]
    )

    vcol = resolve_column(
        df,
        [
            "value_mm",
            "value",
        ]
    )

    if qcol is None or vcol is None:
        raise ValueError(
            "E2 design-envelope columns not resolved."
        )

    mask = (
        df[qcol]
        .astype(str)
        .map(normalize)
        == normalize(quantity)
    )

    rows = df.loc[mask]

    if rows.empty:
        raise KeyError(
            f"E2 design-envelope quantity not found: {quantity}"
        )

    return float(
        pd.to_numeric(
            pd.Series(
                [rows.iloc[0][vcol]]
            ),
            errors="raise",
        ).iloc[0]
    )


# =============================================================================
# 10. MAIN
# =============================================================================

def main():

    print("=" * 118)
    print(
        " PHASE 2E2-B — UPPER-HEAD / PRESSURE-CLOSURE AUDIT V0.3"
    )
    print("=" * 118)

    # -------------------------------------------------------------------------
    # Read sources
    # -------------------------------------------------------------------------

    barrel_resolution = (
        resolve_barrel_geometry()
    )

    barrel_df = barrel_resolution[
        "df"
    ]

    # -------------------------------------------------------------------------
    # Source ambiguity diagnostic
    # -------------------------------------------------------------------------
    if (
        barrel_resolution["status"]
        != "RESOLVED"
    ):
        diagnostic_df = barrel_resolution[
            "diagnostic_df"
        ].copy()

        print("\nBARREL SOURCE RESOLUTION")
        print("-" * 118)
        print(
            f"Status:                       {barrel_resolution['status']}"
        )
        print(
            f"Reason:                       {barrel_resolution.get('reason', '')}"
        )
        print(
            f"CSV columns:                  {list(barrel_df.columns)}"
        )
        print(
            f"Recognized geometry columns:  "
            f"{barrel_resolution.get('recognized_columns', {})}"
        )
        print(
            f"Selection columns checked:    "
            f"{barrel_resolution.get('explicit_selection_columns_checked', [])}"
        )
        print(
            f"PASS/status columns checked:  "
            f"{barrel_resolution.get('pass_like_columns_checked', [])}"
        )

        print("\nCANDIDATE BARREL ROWS — SOURCE DATA")
        print("-" * 118)

        # Print all candidate rows because this is a source-resolution audit.
        with pd.option_context(
            "display.max_columns",
            None,
            "display.width",
            220,
            "display.max_colwidth",
            50,
        ):
            print(
                diagnostic_df.to_string(
                    index=True
                )
            )

        diagnostic_out = (
            HERE
            / "phase2e2b_barrel_candidate_diagnostic.csv"
        ).resolve()

        diagnostic_df.to_csv(
            diagnostic_out,
            index=True,
        )

        print("\n*** PHASE 2E2-B SOURCE GATE STOP ***")
        print("-" * 118)
        print(
            "The Phase 2 barrel CSV is a sizing sweep with multiple candidate "
            "rows, and no unique selected design can be proven from the CSV "
            "alone. No geometry has been guessed."
        )
        print(
            "Send the console table above. We can then identify the source's "
            "selection rule or read the Phase 2 barrel-sizing Python logic and "
            "lock the correct row before recalculating E2 volumes."
        )
        print(
            f"Candidate diagnostic CSV:     {diagnostic_out}"
        )
        print("=" * 118)
        return

    barrel = barrel_resolution[
        "geometry"
    ]

    matched_barrel_row = barrel_resolution.get(
        "matched_row",
        None,
    )

    material, material_sources = (
        resolve_material_properties(
            barrel_df
        )
    )

    e2_arch = read_csv_flexible(
        E2_ARCH_CSV
    )

    states = read_csv_flexible(
        E2_STATES_CSV
    )

    design_envelope = read_csv_flexible(
        E2_DESIGN_ENVELOPE_CSV
    )

    candidate = read_csv_flexible(
        E2_METERING_CANDIDATE_CSV
    )

    P_atm_Pa, phase1_path = (
        resolve_phase1_patm()
    )

    # -------------------------------------------------------------------------
    # Existing E2 geometry
    # -------------------------------------------------------------------------

    e2_barrel_ID_mm = parameter_float(
        e2_arch,
        "barrel_ID",
    )

    e2_barrel_OD_mm = parameter_float(
        e2_arch,
        "barrel_OD",
    )

    e2_piston_OD_mm = parameter_float(
        e2_arch,
        "piston_OD",
    )

    # E2 architecture-input values are already in mm.
    barrel_source_ID_mm = (
        barrel["ID_mm"]
    )

    barrel_source_OD_mm = (
        barrel["OD_mm"]
    )

    barrel_source_wall_mm = (
        barrel["wall_mm"]
    )

    id_difference_mm = (
        e2_barrel_ID_mm
        - barrel_source_ID_mm
    )

    od_difference_mm = (
        e2_barrel_OD_mm
        - barrel_source_OD_mm
    )

    id_match = (
        abs(id_difference_mm)
        <= BARREL_GEOMETRY_TOL_MM
    )

    od_match = (
        abs(od_difference_mm)
        <= BARREL_GEOMETRY_TOL_MM
    )

    geometry_gate_pass = (
        id_match
        and od_match
    )

    source_radial_clearance_mm = (
        barrel_source_ID_mm
        - e2_piston_OD_mm
    ) / 2.0

    audit = pd.DataFrame([
        {
            "quantity": "barrel_source_ID",
            "source_value_mm": barrel_source_ID_mm,
            "e2_carried_value_mm": e2_barrel_ID_mm,
            "difference_e2_minus_source_mm": id_difference_mm,
            "status": (
                "PASS"
                if id_match
                else "FAIL_RECONCILE"
            ),
            "source": str(
                BARREL_CSV
            ),
        },
        {
            "quantity": "barrel_source_OD",
            "source_value_mm": barrel_source_OD_mm,
            "e2_carried_value_mm": e2_barrel_OD_mm,
            "difference_e2_minus_source_mm": od_difference_mm,
            "status": (
                "PASS"
                if od_match
                else "FAIL_RECONCILE"
            ),
            "source": str(
                BARREL_CSV
            ),
        },
        {
            "quantity": "barrel_source_wall",
            "source_value_mm": barrel_source_wall_mm,
            "e2_carried_value_mm": (
                (
                    e2_barrel_OD_mm
                    - e2_barrel_ID_mm
                )
                / 2.0
            ),
            "difference_e2_minus_source_mm": (
                (
                    e2_barrel_OD_mm
                    - e2_barrel_ID_mm
                )
                / 2.0
                - barrel_source_wall_mm
            ),
            "status": (
                "PASS"
                if geometry_gate_pass
                else "REVIEW_AFTER_RECONCILIATION"
            ),
            "source": str(
                BARREL_CSV
            ),
        },
        {
            "quantity": "source_barrel_to_piston_radial_clearance",
            "source_value_mm": source_radial_clearance_mm,
            "e2_carried_value_mm": np.nan,
            "difference_e2_minus_source_mm": np.nan,
            "status": (
                "PASS"
                if source_radial_clearance_mm > 0.0
                else "FAIL_INTERFERENCE"
            ),
            "source": (
                "phase2_barrel_sizing.csv + "
                "phase2e2_architecture_inputs.csv"
            ),
        },
    ])

    audit.to_csv(
        OUTPUT_SOURCE_AUDIT_CSV,
        index=False,
    )

    print("\nSOURCE CONNECTION")
    print("-" * 118)
    print(
        f"Barrel sizing CSV:            {BARREL_CSV}"
    )
    print(
        f"Barrel sizing Python:         "
        f"{BARREL_PY if BARREL_PY.exists() else 'not present / not required'}"
    )
    print(
        f"E2 architecture inputs:       {E2_ARCH_CSV}"
    )
    print(
        f"E2 stroke states:             {E2_STATES_CSV}"
    )
    print(
        f"E2 design envelope:           {E2_DESIGN_ENVELOPE_CSV}"
    )
    print(
        f"E2 metering candidate:        {E2_METERING_CANDIDATE_CSV}"
    )
    print(
        f"Phase 1 pressure source:      {phase1_path}"
    )

    print("\nBARREL SOURCE RECONCILIATION — HARD GATE")
    print("-" * 118)
    print(
        f"Selection method:             {barrel['selection_method']}"
    )
    print(
        "Selection basis:              prior Phase 2D WORKING barrel baseline; "
        "not inferred from CSV PASS alone"
    )
    print(
        f"Phase 2 barrel source:        "
        f"{barrel_source_ID_mm:.3f} mm ID / "
        f"{barrel_source_OD_mm:.3f} mm OD / "
        f"{barrel_source_wall_mm:.3f} mm wall"
    )
    print(
        f"Current E2 carried geometry:  "
        f"{e2_barrel_ID_mm:.3f} mm ID / "
        f"{e2_barrel_OD_mm:.3f} mm OD / "
        f"{(e2_barrel_OD_mm-e2_barrel_ID_mm)/2.0:.3f} mm wall"
    )
    print(
        f"ID difference E2-source:      {id_difference_mm:+.3f} mm"
    )
    print(
        f"OD difference E2-source:      {od_difference_mm:+.3f} mm"
    )
    print(
        f"Source radial piston gap:     {source_radial_clearance_mm:.3f} mm / side"
    )

    if matched_barrel_row is not None:
        print("\nMATCHED PHASE 2D WORKING ROW")
        print("-" * 118)

        report_fields = [
            "ID_mm",
            "wall_mm",
            "OD_mm",
            "mass_per_m_kg",
            "limit_governing_case",
            "limit_governing_surface",
            "limit_vm_MPa",
            "MS_limit_yield",
            "ultimate_governing_case",
            "ultimate_governing_surface",
            "ultimate_vm_MPa",
            "MS_ultimate",
            "PASS",
        ]

        for field in report_fields:
            if field in matched_barrel_row.index:
                print(
                    f"{field:<32} {matched_barrel_row[field]}"
                )

    if not geometry_gate_pass:

        print("\n*** PHASE 2E2-B GATE STOP ***")
        print("-" * 118)
        print(
            "The actual Phase 2 barrel-sizing source does NOT match the barrel "
            "geometry currently carried by Phase 2E2."
        )
        print(
            "Do not size or freeze the pressure closure yet. Barrel cross-sectional "
            "area directly controls gas/oil axial volume, metering packaging and "
            "the closure station, so E2 must first be rebuilt with the source-locked "
            "barrel ID / OD."
        )
        print(
            f"\nSource audit written to:      {OUTPUT_SOURCE_AUDIT_CSV}"
        )
        print("=" * 118)
        return

    # -------------------------------------------------------------------------
    # Geometry gate passed: structural pressure checks may proceed.
    # -------------------------------------------------------------------------

    full_physical = read_state(
        states,
        "FULL_PHYSICAL_STROKE",
    )

    virtual_diag = read_state(
        states,
        "VIRTUAL_DIAGNOSTIC",
    )

    P_phys_abs_MPa = float(
        full_physical[
            "gas_pressure_abs_MPa"
        ]
    )

    P_virtual_abs_MPa = float(
        virtual_diag[
            "gas_pressure_abs_MPa"
        ]
    )

    P_atm_MPa = (
        P_atm_Pa
        / 1e6
    )

    p_limit_MPa = (
        P_phys_abs_MPa
        - P_atm_MPa
    )

    p_ultimate_MPa = (
        ULTIMATE_FACTOR
        * p_limit_MPa
    )

    p_virtual_MPa = (
        P_virtual_abs_MPa
        - P_atm_MPa
    )

    # -------------------------------------------------------------------------
    # Barrel pressure stress
    # -------------------------------------------------------------------------

    barrel_limit = lame_inner_stresses_MPa(
        barrel_source_ID_mm,
        barrel_source_OD_mm,
        p_limit_MPa,
    )

    barrel_ultimate = lame_inner_stresses_MPa(
        barrel_source_ID_mm,
        barrel_source_OD_mm,
        p_ultimate_MPa,
    )

    barrel_virtual = lame_inner_stresses_MPa(
        barrel_source_ID_mm,
        barrel_source_OD_mm,
        p_virtual_MPa,
    )

    barrel_MS_limit = (
        material["Sy_MPa"]
        / barrel_limit[
            "von_mises_MPa"
        ]
        - 1.0
    )

    barrel_MS_ultimate = (
        material["Su_MPa"]
        / barrel_ultimate[
            "von_mises_MPa"
        ]
        - 1.0
    )

    # -------------------------------------------------------------------------
    # Closure plate screen
    # -------------------------------------------------------------------------

    closure_radius_mm = (
        barrel_source_ID_mm
        / 2.0
    )

    t_req_limit_mm = (
        closure_required_thickness_mm(
            p_limit_MPa,
            closure_radius_mm,
            material["Sy_MPa"],
            material["nu"],
        )
    )

    t_req_ultimate_mm = (
        closure_required_thickness_mm(
            p_ultimate_MPa,
            closure_radius_mm,
            material["Su_MPa"],
            material["nu"],
        )
    )

    t_req_governing_mm = max(
        t_req_limit_mm,
        t_req_ultimate_mm,
    )

    closure_rows = []

    for thickness_mm in CLOSURE_THICKNESS_SWEEP_MM:

        sigma_lim = (
            closure_sigma_simply_supported_MPa(
                p_limit_MPa,
                closure_radius_mm,
                thickness_mm,
                material["nu"],
            )
        )

        sigma_ult = (
            closure_sigma_simply_supported_MPa(
                p_ultimate_MPa,
                closure_radius_mm,
                thickness_mm,
                material["nu"],
            )
        )

        sigma_clamped_ref = (
            closure_sigma_clamped_reference_MPa(
                p_limit_MPa,
                closure_radius_mm,
                thickness_mm,
            )
        )

        MS_lim = (
            material["Sy_MPa"]
            / sigma_lim
            - 1.0
        )

        MS_ult = (
            material["Su_MPa"]
            / sigma_ult
            - 1.0
        )

        closure_rows.append({
            "thickness_mm": thickness_mm,
            "sigma_limit_simply_supported_MPa": sigma_lim,
            "MS_limit_to_yield": MS_lim,
            "sigma_ultimate_simply_supported_MPa": sigma_ult,
            "MS_ultimate_to_tensile": MS_ult,
            "sigma_limit_clamped_reference_MPa": sigma_clamped_ref,
            "status": (
                "PASS_BOTH"
                if (
                    MS_lim >= 0.0
                    and MS_ult >= 0.0
                )
                else "FAIL"
            ),
        })

    closure_sweep = pd.DataFrame(
        closure_rows
    )

    closure_sweep.to_csv(
        OUTPUT_CLOSURE_SWEEP_CSV,
        index=False,
    )

    passing = closure_sweep.loc[
        closure_sweep["status"]
        == "PASS_BOTH"
    ]

    if passing.empty:
        t_sweep_first_pass_mm = np.nan
    else:
        t_sweep_first_pass_mm = float(
            passing.iloc[0][
                "thickness_mm"
            ]
        )

    # -------------------------------------------------------------------------
    # Axial packaging / E3 interface
    # -------------------------------------------------------------------------

    closure_inner_face_mm = parameter_float(
        candidate,
        "pressure_closure_inner_face_above_U",
    )

    orifice_plane_mm = parameter_float(
        candidate,
        "orifice_plane_above_U",
    )

    initial_upper_oil_head_mm = parameter_float(
        candidate,
        "initial_upper_oil_head",
    )

    max_pin_volume_cm3 = parameter_float(
        candidate,
        "max_pin_hardware_displacement_volume",
    )

    gas_initial_cm3 = parameter_float(
        e2_arch,
        "phase1_initial_gas_volume",
    )

    conservative_envelope_mm = (
        read_design_envelope_value(
            design_envelope,
            "conservative_volume_internal_envelope_above_U",
        )
    )

    axial_reserve_over_e2_envelope_mm = (
        closure_inner_face_mm
        - conservative_envelope_mm
    )

    A_barrel_mm2 = (
        circular_area_mm2(
            barrel_source_ID_mm
        )
    )

    upper_cavity_height_mm = (
        closure_inner_face_mm
        - orifice_plane_mm
    )

    upper_cavity_volume_cm3 = (
        A_barrel_mm2
        * upper_cavity_height_mm
        / 1000.0
    )

    initial_upper_oil_volume_cm3 = (
        A_barrel_mm2
        * initial_upper_oil_head_mm
        / 1000.0
    )

    reconstructed_required_volume_cm3 = (
        gas_initial_cm3
        + initial_upper_oil_volume_cm3
        + max_pin_volume_cm3
    )

    upper_volume_residual_cm3 = (
        upper_cavity_volume_cm3
        - reconstructed_required_volume_cm3
    )

    # Structural minimum only. This is NOT yet a seal/thread/retainer thickness.
    closure_outer_face_structural_min_mm = (
        closure_inner_face_mm
        + t_req_governing_mm
    )

    closure_outer_face_sweep_first_pass_mm = (
        closure_inner_face_mm
        + t_sweep_first_pass_mm
        if np.isfinite(
            t_sweep_first_pass_mm
        )
        else np.nan
    )

    pressure_force_limit_kN = (
        p_limit_MPa
        * A_barrel_mm2
        / 1000.0
    )

    pressure_force_ultimate_kN = (
        p_ultimate_MPa
        * A_barrel_mm2
        / 1000.0
    )

    checks = pd.DataFrame([
        {
            "check": "BARREL_PRESSURE_LIMIT",
            "value": barrel_limit[
                "von_mises_MPa"
            ],
            "units": "MPa von Mises",
            "allowable": material["Sy_MPa"],
            "margin": barrel_MS_limit,
            "status": (
                "PASS"
                if barrel_MS_limit >= 0.0
                else "FAIL"
            ),
        },
        {
            "check": "BARREL_PRESSURE_ULTIMATE",
            "value": barrel_ultimate[
                "von_mises_MPa"
            ],
            "units": "MPa von Mises",
            "allowable": material["Su_MPa"],
            "margin": barrel_MS_ultimate,
            "status": (
                "PASS"
                if barrel_MS_ultimate >= 0.0
                else "FAIL"
            ),
        },
        {
            "check": "BARREL_VIRTUAL_DIAGNOSTIC",
            "value": barrel_virtual[
                "von_mises_MPa"
            ],
            "units": "MPa von Mises",
            "allowable": material["Sy_MPa"],
            "margin": (
                material["Sy_MPa"]
                / barrel_virtual[
                    "von_mises_MPa"
                ]
                - 1.0
            ),
            "status": "DIAGNOSTIC_ONLY",
        },
        {
            "check": "CLOSURE_REQUIRED_LIMIT",
            "value": t_req_limit_mm,
            "units": "mm required thickness",
            "allowable": np.nan,
            "margin": np.nan,
            "status": "CALCULATED",
        },
        {
            "check": "CLOSURE_REQUIRED_ULTIMATE",
            "value": t_req_ultimate_mm,
            "units": "mm required thickness",
            "allowable": np.nan,
            "margin": np.nan,
            "status": "CALCULATED",
        },
        {
            "check": "AXIAL_RESERVE_OVER_E2_CONSERVATIVE_ENVELOPE",
            "value": axial_reserve_over_e2_envelope_mm,
            "units": "mm",
            "allowable": 0.0,
            "margin": np.nan,
            "status": (
                "PASS"
                if axial_reserve_over_e2_envelope_mm >= 0.0
                else "FAIL"
            ),
        },
        {
            "check": "UPPER_CAVITY_VOLUME_RECONSTRUCTION_RESIDUAL",
            "value": upper_volume_residual_cm3,
            "units": "cm^3",
            "allowable": 1.0,
            "margin": np.nan,
            "status": (
                "PASS"
                if abs(
                    upper_volume_residual_cm3
                ) <= 1.0
                else "REVIEW"
            ),
        },
    ])

    checks.to_csv(
        OUTPUT_PRESSURE_CHECK_CSV,
        index=False,
    )

    interface = pd.DataFrame([
        {
            "quantity": "pressure_closure_inner_face_above_U",
            "value": closure_inner_face_mm,
            "units": "mm",
            "classification": (
                "E2_WORKING_METERING_CANDIDATE"
            ),
        },
        {
            "quantity": "calculated_structural_minimum_closure_thickness",
            "value": t_req_governing_mm,
            "units": "mm",
            "classification": (
                "PLATE_SCREEN_MINIMUM_NOT_CAD_LOCK"
            ),
        },
        {
            "quantity": "first_0p5mm_sweep_thickness_passing_limit_and_ultimate",
            "value": t_sweep_first_pass_mm,
            "units": "mm",
            "classification": (
                "SCREENING_GRID_NOT_CAD_LOCK"
            ),
        },
        {
            "quantity": "structural_minimum_outer_face_above_U",
            "value": closure_outer_face_structural_min_mm,
            "units": "mm",
            "classification": (
                "MINIMUM_E2_TO_E3_INTERFACE_BEFORE_SEALS_RETAINER"
            ),
        },
        {
            "quantity": "sweep_first_pass_outer_face_above_U",
            "value": closure_outer_face_sweep_first_pass_mm,
            "units": "mm",
            "classification": (
                "WORKING_SCREENING_INTERFACE"
            ),
        },
        {
            "quantity": "E3_location_rule",
            "value": (
                "Place trunnion / upper attachment load path in solid head "
                "at or above the final pressure-closure outer face unless a "
                "pressure-penetrating boss is deliberately designed."
            ),
            "units": "-",
            "classification": "ARCHITECTURE_RULE",
        },
    ])

    interface.to_csv(
        OUTPUT_E3_INTERFACE_CSV,
        index=False,
    )

    # -------------------------------------------------------------------------
    # Console report
    # -------------------------------------------------------------------------

    print("\nBARREL GEOMETRY GATE")
    print("-" * 118)
    print("Status:                       PASS — source barrel and E2 geometry agree.")

    print("\nMATERIAL PROPERTIES")
    print("-" * 118)
    print(
        f"7075-T6 E:                    {material['E_GPa']:.3f} GPa "
        f"[{material_sources['E_GPa']}]"
    )
    print(
        f"7075-T6 nu:                   {material['nu']:.4f} "
        f"[{material_sources['nu']}]"
    )
    print(
        f"7075-T6 yield:                {material['Sy_MPa']:.1f} MPa "
        f"[{material_sources['Sy_MPa']}]"
    )
    print(
        f"7075-T6 ultimate:             {material['Su_MPa']:.1f} MPa "
        f"[{material_sources['Su_MPa']}]"
    )

    print("\nPRESSURE ENVELOPE")
    print("-" * 118)
    print(
        f"Atmospheric pressure:         {P_atm_MPa:.6f} MPa"
    )
    print(
        f"Full-stroke absolute gas P:   {P_phys_abs_MPa:.3f} MPa"
    )
    print(
        f"Limit differential pressure:  {p_limit_MPa:.3f} MPa"
    )
    print(
        f"Ultimate differential P:      {p_ultimate_MPa:.3f} MPa "
        f"(x{ULTIMATE_FACTOR:.2f})"
    )
    print(
        f"Virtual diagnostic delta P:   {p_virtual_MPa:.3f} MPa"
    )
    print(
        f"Closure pressure load limit:  {pressure_force_limit_kN:.3f} kN"
    )
    print(
        f"Closure pressure load ult.:   {pressure_force_ultimate_kN:.3f} kN"
    )

    print("\nBARREL THICK-WALL PRESSURE SCREEN")
    print("-" * 118)
    print(
        f"Limit inner hoop stress:      {barrel_limit['sigma_theta_MPa']:.3f} MPa"
    )
    print(
        f"Limit inner axial stress:     {barrel_limit['sigma_z_MPa']:.3f} MPa"
    )
    print(
        f"Limit von Mises:              {barrel_limit['von_mises_MPa']:.3f} MPa"
    )
    print(
        f"Limit margin to yield:        {barrel_MS_limit:+.3f}"
    )
    print(
        f"Ultimate von Mises:           {barrel_ultimate['von_mises_MPa']:.3f} MPa"
    )
    print(
        f"Ultimate margin to tensile:   {barrel_MS_ultimate:+.3f}"
    )

    print("\nPRESSURE-CLOSURE FLAT-PLATE SCREEN")
    print("-" * 118)
    print(
        f"Pressure radius:              {closure_radius_mm:.3f} mm"
    )
    print(
        f"Required thickness — limit:   {t_req_limit_mm:.3f} mm"
    )
    print(
        f"Required thickness — ult.:    {t_req_ultimate_mm:.3f} mm"
    )
    print(
        f"Governing theoretical min.:   {t_req_governing_mm:.3f} mm"
    )
    print(
        f"First 0.5-mm sweep PASS:      "
        f"{t_sweep_first_pass_mm:.3f} mm"
    )
    print(
        "Boundary model:               simply-supported circular plate "
        "(conservative preliminary screen)"
    )

    print("\nUPPER-CAVITY / AXIAL PACKAGING CHECK")
    print("-" * 118)
    print(
        f"Fixed orifice plane:          {orifice_plane_mm:.3f} mm above U"
    )
    print(
        f"Closure inner face:           {closure_inner_face_mm:.3f} mm above U"
    )
    print(
        f"E2 conservative envelope:     {conservative_envelope_mm:.3f} mm above U"
    )
    print(
        f"Axial reserve over envelope:  {axial_reserve_over_e2_envelope_mm:+.3f} mm"
    )
    print(
        f"Initial upper-oil head:        {initial_upper_oil_head_mm:.3f} mm"
    )
    print(
        f"Upper cavity volume:          {upper_cavity_volume_cm3:.3f} cm^3"
    )
    print(
        f"Reconstructed required vol.:  {reconstructed_required_volume_cm3:.3f} cm^3"
    )
    print(
        f"Volume residual:              {upper_volume_residual_cm3:+.6f} cm^3"
    )

    print("\nPRELIMINARY E2 -> E3 INTERFACE")
    print("-" * 118)
    print(
        f"Closure inner face:           {closure_inner_face_mm:.3f} mm above U"
    )
    print(
        f"Structural min. outer face:   {closure_outer_face_structural_min_mm:.3f} mm above U"
    )
    print(
        f"0.5-mm-grid PASS outer face:  {closure_outer_face_sweep_first_pass_mm:.3f} mm above U"
    )
    print(
        "E3 rule:                      future trunnion / upper attachment goes "
        "in solid head at or above the FINAL closure outer face."
    )

    print("\nLOCK BOUNDARY")
    print("-" * 118)
    print(
        "The pressure-vessel screening and axial-volume reconstruction may be "
        "used to establish the E2 structural minimum. The 64/5/74 mm barrel is "
        "the retained Phase 2D WORKING baseline, not a new minimum-mass selection. "
        "Do NOT yet interpret the theoretical plate thickness as the final CAD "
        "closure thickness: sealing grooves, retainer/thread geometry, ports, "
        "manufacturing allowance and local stress concentration still require "
        "explicit geometry."
    )

    print("\nOUTPUT FILES")
    print("-" * 118)
    print(
        f"Barrel source audit:          {OUTPUT_SOURCE_AUDIT_CSV}"
    )
    print(
        f"Pressure checks:              {OUTPUT_PRESSURE_CHECK_CSV}"
    )
    print(
        f"Closure thickness sweep:      {OUTPUT_CLOSURE_SWEEP_CSV}"
    )
    print(
        f"E3 interface:                 {OUTPUT_E3_INTERFACE_CSV}"
    )

    print("=" * 118)


if __name__ == "__main__":
    main()
