from pathlib import Path
import ast
import math
import numpy as np
import pandas as pd


# =============================================================================
# LANDING GEAR DESIGN PROJECT
# PHASE 2E2 — UPPER BARREL / INTERNAL CAVITY PACKAGING V0.3
#
# PURPOSE
#   Convert the locked Phase 1 effective oleo model + locked Phase 2 packaging
#   into a physically plausible first-order internal architecture and axial
#   cavity envelope.
#
#   Architecture screened here:
#
#       upper closure / fixed metering element
#                    │
#            nitrogen gas region
#                    │
#             direct gas/oil interface
#                    │
#              upper oil region
#                    │
#       piston-top metering head / orifice
#                    │
#          hollow 58 x 4 mm piston
#          (lower oil reservoir)
#                    │
#        E1 blind-ended lower piston bore
#
#   No separator piston is introduced in V0.1.
#
# DATA RULE
#   - Phase 2D kinematic/packaging quantities are READ from
#     phase2_packaging_overlap.csv.
#   - Phase 2E1 lower-end geometry is READ from
#     phase2e1_lower_end_geometry.csv.
#   - Phase 1 gas-model primitive inputs are extracted from the existing Phase 1
#     Python source by AST when available. The source is NOT executed.
#   - If the Phase 1 source cannot be found, only the LOCKED primitive input
#     values are used as a fallback. No calculated Phase 1 result is copied.
#   - All gas volumes, pressures, state positions, reservoir volumes and closure
#     envelope results are calculated here.
#
# IMPORTANT
#   This is a packaging / architecture audit, NOT a final hydraulic-detail
#   design. The actual oil fill, gas/oil interface location, metering-pin shape,
#   closure geometry and local 3D stresses remain later design work.
# =============================================================================


# =============================================================================
# 1. PATHS
# =============================================================================

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.resolve()

PACKAGING_PREFERRED = (
    HERE / "phase2_packaging_overlap.csv"
).resolve()

E1_GEOMETRY_PREFERRED = (
    HERE / "phase2e1_lower_end_geometry.csv"
).resolve()

PHASE1_LOADS_PREFERRED = (
    PROJECT_ROOT / "phase1_loads" / "phase1_load_envelope.csv"
).resolve()

OUTPUT_STATES_CSV = (
    HERE / "phase2e2_stroke_cavity_states.csv"
).resolve()

OUTPUT_CLOSURE_SWEEP_CSV = (
    HERE / "phase2e2_closure_reserve_sweep.csv"
).resolve()

OUTPUT_GEOMETRY_CHECKS_CSV = (
    HERE / "phase2e2_geometry_checks.csv"
).resolve()

OUTPUT_ARCHITECTURE_INPUTS_CSV = (
    HERE / "phase2e2_architecture_inputs.csv"
).resolve()

OUTPUT_VOLUME_BOUNDS_CSV = (
    HERE / "phase2e2_volume_bounds.csv"
).resolve()

OUTPUT_STATIC_DIAGNOSTIC_CSV = (
    HERE / "phase2e2_static_equilibrium_diagnostic.csv"
).resolve()

OUTPUT_DESIGN_ENVELOPE_CSV = (
    HERE / "phase2e2_design_envelope.csv"
).resolve()


# =============================================================================
# 2. LOCKED PHASE 2 PRELIMINARY BASELINE INPUTS
# =============================================================================
#
# These are primitive locked design dimensions, not calculated results.
# Calculated packaging quantities continue to come from the upstream CSVs.

D_barrel_i = 0.064               # smooth barrel ID [m]
D_barrel_o = 0.074               # smooth barrel OD [m]
D_lower_boss = 0.084             # lower gland/boss envelope [m]

preferred_hL_mm = 250.0
preferred_spacing_mm = 150.0
preferred_hU_mm = 400.0

# Extra axial envelope sweep ABOVE the moving piston top, in addition to the
# equivalent gas height. This is intentionally NOT locked.
#
# It provides a transparent sensitivity allowance for:
#   - upper oil region,
#   - piston-top metering-head thickness,
#   - fixed metering element / pin root,
#   - closure dead clearance.
#
# It is NOT an oil-fill calculation.
non_gas_reserve_sweep_mm = [
    0.0,
    25.0,
    50.0,
    75.0,
    100.0,
]

# Numerical tolerances
position_consistency_tol_mm = 0.50
diameter_consistency_tol_mm = 0.10


# =============================================================================
# 3. PHASE 1 LOCKED INPUT FALLBACK
# =============================================================================
#
# Used ONLY if the existing Phase 1 source cannot be located / parsed.
# These are locked primitive inputs from the Phase 1 model, not derived outputs.

PHASE1_FALLBACK = {
    "D_piston": 0.058,            # [m]
    "L_gas_0": 0.350,             # [m]
    "P_atm": 101325.0,            # [Pa]
    "P_gas_0_abs": 2.336e6,       # [Pa]
    "n_poly": 1.30,               # [-]
    "x_available": 0.230,         # [m]
}


# =============================================================================
# 4. UTILITIES
# =============================================================================

def normalize_column_name(name):
    """Lowercase alphanumeric-only name for tolerant matching."""
    return "".join(
        ch for ch in str(name).lower()
        if ch.isalnum()
    )


def read_csv_flexible(path):
    """Read comma / semicolon / tab CSV and clean headers."""
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


def candidate_source_paths(filename, preferred_path=None):
    """
    Return matching files in priority order:
      1. preferred path,
      2. current phase2_structures folder,
      3. anywhere below Landing_Gear_Project.
    """
    candidates = []

    def add(path):
        path = Path(path).resolve()

        if (
            path.exists()
            and path.is_file()
            and path not in candidates
        ):
            candidates.append(path)

    if preferred_path is not None:
        add(preferred_path)

    add(HERE / filename)

    for path in PROJECT_ROOT.rglob(filename):
        add(path)

    return candidates


def resolve_columns(df, alias_map):
    """Resolve canonical fields from tolerant aliases."""
    normalized_to_actual = {
        normalize_column_name(col): col
        for col in df.columns
    }

    resolved = {}
    missing = []

    for canonical, aliases in alias_map.items():

        found = None

        for alias in aliases:
            key = normalize_column_name(alias)

            if key in normalized_to_actual:
                found = normalized_to_actual[key]
                break

        if found is None:
            missing.append(canonical)
        else:
            resolved[canonical] = found

    return resolved, missing


def to_float(value, label):
    """Convert one CSV value to finite float."""
    result = float(
        pd.to_numeric(
            pd.Series([value]),
            errors="raise",
        ).iloc[0]
    )

    if not np.isfinite(result):
        raise ValueError(
            f"{label} is not finite."
        )

    return result


def circular_area(D):
    return math.pi * D**2 / 4.0


# =============================================================================
# 5. PHASE 1 SOURCE DISCOVERY / AST EXTRACTION
# =============================================================================

def numeric_literal(node):
    """
    Safely evaluate a simple numeric AST expression without executing code.

    Supports literals and straightforward arithmetic such as:
        2.336e6
        58 / 1000
        0.230
    """

    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        return None

    if isinstance(node, ast.UnaryOp):
        value = numeric_literal(node.operand)

        if value is None:
            return None

        if isinstance(node.op, ast.USub):
            return -value

        if isinstance(node.op, ast.UAdd):
            return value

        return None

    if isinstance(node, ast.BinOp):

        left = numeric_literal(node.left)
        right = numeric_literal(node.right)

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


def extract_assignments_from_python(path, wanted_names):
    """Extract simple numeric assignments from a Python source file."""
    try:
        source = path.read_text(
            encoding="utf-8",
            errors="ignore",
        )

        tree = ast.parse(
            source,
            filename=str(path),
        )

    except Exception:
        return {}

    found = {}

    for node in ast.walk(tree):

        if isinstance(node, ast.Assign):

            value = numeric_literal(node.value)

            if value is None:
                continue

            for target in node.targets:

                if (
                    isinstance(target, ast.Name)
                    and target.id in wanted_names
                ):
                    found[target.id] = value

        elif isinstance(node, ast.AnnAssign):

            if not isinstance(node.target, ast.Name):
                continue

            if node.target.id not in wanted_names:
                continue

            value = numeric_literal(node.value)

            if value is not None:
                found[node.target.id] = value

    return found


def resolve_phase1_oleo_inputs():
    """
    Search existing project Python sources for the Phase 1 oleo primitives.

    We never import / execute the source because the Phase 1 script performs a
    simulation and creates plots at module level.
    """

    required = [
        "D_piston",
        "L_gas_0",
        "P_atm",
        "P_gas_0_abs",
        "n_poly",
        "x_available",
    ]

    wanted = set(required)

    candidates = []

    for path in PROJECT_ROOT.rglob("*.py"):

        if path.resolve() == Path(__file__).resolve():
            continue

        values = extract_assignments_from_python(
            path,
            wanted,
        )

        score = sum(
            name in values
            for name in required
        )

        if score > 0:
            candidates.append(
                (score, path, values)
            )

    candidates.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    for score, path, values in candidates:

        if score == len(required):

            # Sanity screen to prevent selecting an unrelated script that just
            # happens to reuse similar variable names.
            if not (0.040 <= values["D_piston"] <= 0.080):
                continue

            if not (0.20 <= values["L_gas_0"] <= 0.60):
                continue

            if not (0.15 <= values["x_available"] <= 0.35):
                continue

            print("\nPHASE 1 OLEO INPUT SOURCE RESOLVED")
            print("-" * 110)
            print(f"File: {path}")

            return values, path, False

    print("\nPHASE 1 OLEO INPUT SOURCE")
    print("-" * 110)
    print(
        "No complete Phase 1 source file could be parsed automatically."
    )
    print(
        "Using locked primitive Phase 1 inputs as fallback; "
        "all E2 results are still recalculated."
    )

    return PHASE1_FALLBACK.copy(), None, True


# =============================================================================
# 6. PHASE 2D PACKAGING SOURCE
# =============================================================================

def read_preferred_packaging_row():

    candidates = candidate_source_paths(
        "phase2_packaging_overlap.csv",
        PACKAGING_PREFERRED,
    )

    if not candidates:
        raise FileNotFoundError(
            "Could not find phase2_packaging_overlap.csv below:\n"
            f"{PROJECT_ROOT}"
        )

    aliases = {
        "hL_mm": [
            "hL_mm",
            "hL",
        ],
        "spacing_mm": [
            "spacing_mm",
            "spacing",
            "b_mm",
            "b",
        ],
        "hU_mm": [
            "hU_mm",
            "hU",
        ],
        "bushing_length_mm": [
            "bushing_length_mm",
            "guide_length_mm",
            "bushinglengthmm",
        ],
        "required_piston_guide_length_mm": [
            "required_piston_guide_length_mm",
            "required_piston_length_mm",
            "requiredguidelengthmm",
        ],
        "nominal_top_intrusion_mm": [
            "nominal_top_intrusion_above_U_mm",
            "nominal_top_intrusion_mm",
        ],
        "physical_top_intrusion_mm": [
            "physical_top_intrusion_above_U_mm",
            "physical_top_intrusion_mm",
        ],
        "virtual_top_intrusion_mm": [
            "virtual_top_intrusion_above_U_mm",
            "virtual_top_intrusion_mm",
        ],
        "physical_lower_surface_reserve_mm": [
            "physical_lower_surface_reserve_mm",
            "physical_reserve_mm",
            "PhysRes",
        ],
        "virtual_lower_surface_reserve_mm": [
            "virtual_lower_surface_reserve_mm",
            "virtual_reserve_mm",
            "VirtRes",
        ],
        "full_extension_hL_mm": [
            "full_extension_hL_mm",
            "full_extension_hL",
        ],
        "full_extension_hU_mm": [
            "full_extension_hU_mm",
            "full_extension_hU",
        ],
        "nominal_hL_mm": [
            "nominal_hL_mm",
            "nominal_hL",
        ],
        "nominal_hU_mm": [
            "nominal_hU_mm",
            "nominal_hU",
        ],
        "physical_hL_mm": [
            "physical_hL_mm",
            "physical_hL",
        ],
        "physical_hU_mm": [
            "physical_hU_mm",
            "physical_hU",
        ],
        "virtual_hL_mm": [
            "virtual_hL_mm",
            "virtual_hL",
        ],
        "virtual_hU_mm": [
            "virtual_hU_mm",
            "virtual_hU",
        ],
    }

    required_fields = [
        "hL_mm",
        "spacing_mm",
        "hU_mm",
        "bushing_length_mm",
        "required_piston_guide_length_mm",
        "nominal_top_intrusion_mm",
        "physical_top_intrusion_mm",
        "virtual_top_intrusion_mm",
        "physical_lower_surface_reserve_mm",
    ]

    diagnostics = []

    for path in candidates:

        try:
            df = read_csv_flexible(path)
        except Exception as exc:
            diagnostics.append(
                f"{path} -> read error: {exc}"
            )
            continue

        resolved, _ = resolve_columns(
            df,
            aliases,
        )

        missing = [
            field for field in required_fields
            if field not in resolved
        ]

        if missing:
            diagnostics.append(
                f"{path} -> missing: {missing}"
            )
            continue

        hL = pd.to_numeric(
            df[resolved["hL_mm"]],
            errors="coerce",
        )

        spacing = pd.to_numeric(
            df[resolved["spacing_mm"]],
            errors="coerce",
        )

        hU = pd.to_numeric(
            df[resolved["hU_mm"]],
            errors="coerce",
        )

        mask = (
            np.isclose(hL, preferred_hL_mm)
            & np.isclose(spacing, preferred_spacing_mm)
            & np.isclose(hU, preferred_hU_mm)
        )

        selected = df.loc[mask]

        if selected.empty:
            diagnostics.append(
                f"{path} -> compatible schema, but preferred "
                f"{preferred_hL_mm:.0f}/"
                f"{preferred_spacing_mm:.0f}/"
                f"{preferred_hU_mm:.0f} mm row not found."
            )
            continue

        row = selected.iloc[0]

        print("\nPHASE 2D PACKAGING SOURCE RESOLVED")
        print("-" * 110)
        print(f"File: {path}")
        print(
            f"Preferred row: hL={preferred_hL_mm:.0f} mm, "
            f"spacing={preferred_spacing_mm:.0f} mm, "
            f"hU={preferred_hU_mm:.0f} mm"
        )

        return row, resolved, path

    raise ValueError(
        "No compatible Phase 2D packaging source was found.\n"
        + "\n".join(diagnostics)
    )


# =============================================================================
# 7. PHASE 1 STATIC LOAD SOURCE
# =============================================================================

def read_phase1_load_envelope():
    """
    Read the existing Phase 1 load-envelope CSV.

    Used in E2 only to compare the Phase 2D 'nominal' compression state with
    the pneumatic static-equilibrium compression implied by the locked Phase 1
    gas spring at the LC0 vertical load.
    """

    candidates = candidate_source_paths(
        "phase1_load_envelope.csv",
        PHASE1_LOADS_PREFERRED,
    )

    if not candidates:
        return None, None

    aliases = {
        "Case": [
            "Case",
            "LoadCase",
            "load_case",
        ],
        "Fz_lim": [
            "Fz_lim",
            "Fz_limit",
            "FzLimit",
            "limit_Fz",
            "Fz_limit_kN",
        ],
    }

    for path in candidates:

        try:
            df = read_csv_flexible(path)
        except Exception:
            continue

        resolved, missing = resolve_columns(
            df,
            aliases,
        )

        if missing:
            continue

        df = df.rename(
            columns={
                resolved["Case"]: "Case",
                resolved["Fz_lim"]: "Fz_lim",
            }
        )

        df["Fz_lim"] = pd.to_numeric(
            df["Fz_lim"],
            errors="coerce",
        )

        if df["Fz_lim"].isna().all():
            continue

        print("\nPHASE 1 LOAD ENVELOPE SOURCE RESOLVED")
        print("-" * 110)
        print(f"File: {path}")

        return df, path

    return None, None


# =============================================================================
# 8. PHASE 2E1 GEOMETRY SOURCE
# =============================================================================

def read_e1_geometry():

    candidates = candidate_source_paths(
        "phase2e1_lower_end_geometry.csv",
        E1_GEOMETRY_PREFERRED,
    )

    if not candidates:
        raise FileNotFoundError(
            "Could not find phase2e1_lower_end_geometry.csv below:\n"
            f"{PROJECT_ROOT}"
        )

    required_parameters = [
        "piston_OD",
        "piston_ID",
        "piston_bore_blind_end",
    ]

    diagnostics = []

    for path in candidates:

        try:
            df = read_csv_flexible(path)
        except Exception as exc:
            diagnostics.append(
                f"{path} -> read error: {exc}"
            )
            continue

        normalized = {
            normalize_column_name(col): col
            for col in df.columns
        }

        if (
            "parameter" not in normalized
            or "value" not in normalized
        ):
            diagnostics.append(
                f"{path} -> expected parameter/value table."
            )
            continue

        col_parameter = normalized["parameter"]
        col_value = normalized["value"]

        values = {}

        for parameter in required_parameters:

            mask = (
                df[col_parameter]
                .astype(str)
                .map(normalize_column_name)
                == normalize_column_name(parameter)
            )

            selected = df.loc[mask]

            if selected.empty:
                continue

            values[parameter] = to_float(
                selected.iloc[0][col_value],
                parameter,
            )

        missing = [
            parameter
            for parameter in required_parameters
            if parameter not in values
        ]

        if missing:
            diagnostics.append(
                f"{path} -> missing parameters: {missing}"
            )
            continue

        print("\nPHASE 2E1 GEOMETRY SOURCE RESOLVED")
        print("-" * 110)
        print(f"File: {path}")

        return values, path

    raise ValueError(
        "No compatible Phase 2E1 geometry source was found.\n"
        + "\n".join(diagnostics)
    )


# =============================================================================
# 9. GAS MODEL
# =============================================================================

def gas_state(
    x,
    D_effective,
    L0,
    P0_abs,
    P_atm,
    n_poly,
):
    """
    Recalculate Phase 1 polytropic gas state.

    Phase 1 model:
        V0 = A_eff * L0
        V  = A_eff * (L0 - x)
        P  = P0 * (V0/V)^n
    """

    A_eff = circular_area(
        D_effective
    )

    L = L0 - x

    if L <= 0.0:
        raise ValueError(
            f"Gas-model length became non-positive at x={x:.6f} m."
        )

    V0 = A_eff * L0
    V = A_eff * L

    P_abs = (
        P0_abs
        * (V0 / V)**n_poly
    )

    P_gauge = P_abs - P_atm

    F_gas = (
        P_gauge
        * A_eff
    )

    return {
        "gas_length_m": L,
        "gas_volume_m3": V,
        "gas_pressure_abs_Pa": P_abs,
        "gas_pressure_gauge_Pa": P_gauge,
        "gas_force_N": F_gas,
    }


def compression_for_gas_force(
    target_force_N,
    D_effective,
    L0,
    P0_abs,
    P_atm,
    n_poly,
):
    """
    Analytically invert the locked Phase 1 gas law for compression x such that
    the pneumatic force equals target_force_N at zero velocity.
    """

    if target_force_N < 0.0:
        target_force_N = abs(target_force_N)

    A_eff = circular_area(
        D_effective
    )

    required_pressure_abs = (
        P_atm
        + target_force_N / A_eff
    )

    if required_pressure_abs <= 0.0:
        return math.nan

    ratio = (
        required_pressure_abs
        / P0_abs
    )

    if ratio <= 0.0:
        return math.nan

    gas_length = (
        L0
        / ratio**(1.0 / n_poly)
    )

    x = L0 - gas_length

    return x


# =============================================================================
# 10. MAIN ANALYSIS
# =============================================================================

def main():

    # -------------------------------------------------------------------------
    # Read upstream project sources
    # -------------------------------------------------------------------------

    phase1, phase1_path, phase1_fallback = (
        resolve_phase1_oleo_inputs()
    )

    packaging_row, packaging_cols, packaging_path = (
        read_preferred_packaging_row()
    )

    e1, e1_path = read_e1_geometry()

    phase1_loads, phase1_loads_path = (
        read_phase1_load_envelope()
    )

    # -------------------------------------------------------------------------
    # Upstream primitive data
    # -------------------------------------------------------------------------

    D_piston_phase1 = phase1["D_piston"]
    L_gas_0 = phase1["L_gas_0"]
    P_atm = phase1["P_atm"]
    P_gas_0_abs = phase1["P_gas_0_abs"]
    n_poly = phase1["n_poly"]
    x_physical = phase1["x_available"]

    # E1 CSV stores dimensions in mm.
    D_piston_e1 = e1["piston_OD"] / 1000.0
    D_piston_i = e1["piston_ID"] / 1000.0
    z_piston_bore_end_from_A = (
        e1["piston_bore_blind_end"]
        / 1000.0
    )

    # -------------------------------------------------------------------------
    # Cross-phase consistency checks
    # -------------------------------------------------------------------------

    piston_diameter_difference_mm = (
        D_piston_phase1
        - D_piston_e1
    ) * 1000.0

    if (
        abs(piston_diameter_difference_mm)
        > diameter_consistency_tol_mm
    ):
        raise ValueError(
            "Phase 1 effective piston diameter does not match the "
            "Phase 2E1 piston OD.\n"
            f"Phase 1: {D_piston_phase1*1000:.3f} mm\n"
            f"Phase 2E1: {D_piston_e1*1000:.3f} mm"
        )

    # Use the E1 geometry value after confirming agreement.
    D_piston = D_piston_e1

    # -------------------------------------------------------------------------
    # Read preferred-row packaging values
    # -------------------------------------------------------------------------

    def pkg(field):
        return to_float(
            packaging_row[
                packaging_cols[field]
            ],
            field,
        )

    bushing_length_mm = pkg(
        "bushing_length_mm"
    )

    required_piston_guide_length_mm = pkg(
        "required_piston_guide_length_mm"
    )

    nominal_intrusion_mm = pkg(
        "nominal_top_intrusion_mm"
    )

    physical_intrusion_mm = pkg(
        "physical_top_intrusion_mm"
    )

    virtual_intrusion_mm = pkg(
        "virtual_top_intrusion_mm"
    )

    physical_lower_reserve_mm = pkg(
        "physical_lower_surface_reserve_mm"
    )

    virtual_lower_reserve_mm = np.nan

    if (
        "virtual_lower_surface_reserve_mm"
        in packaging_cols
    ):
        virtual_lower_reserve_mm = pkg(
            "virtual_lower_surface_reserve_mm"
        )

    # -------------------------------------------------------------------------
    # Reconstruct stroke states from the CSV rather than copying positions
    # -------------------------------------------------------------------------
    #
    # Physical top intrusion is an upstream calculated Phase 2D quantity.
    # The Phase 1 locked physical stroke is a primitive input.
    #
    # Therefore:
    #   full-extension intrusion
    #       = physical intrusion - physical stroke
    #
    # Then nominal and virtual compression follow from their CSV intrusions.

    x_physical_mm = (
        x_physical * 1000.0
    )

    full_extension_intrusion_mm = (
        physical_intrusion_mm
        - x_physical_mm
    )

    x_nominal_mm = (
        nominal_intrusion_mm
        - full_extension_intrusion_mm
    )

    x_virtual_mm = (
        virtual_intrusion_mm
        - full_extension_intrusion_mm
    )

    # Independent full-extension reconstruction using virtual/nominal states.
    full_ext_from_virtual_mm = (
        virtual_intrusion_mm
        - x_virtual_mm
    )

    full_ext_from_nominal_mm = (
        nominal_intrusion_mm
        - x_nominal_mm
    )

    # These are algebraically exact here; retained as explicit audit fields.
    full_extension_spread_mm = max(
        abs(
            full_ext_from_virtual_mm
            - full_extension_intrusion_mm
        ),
        abs(
            full_ext_from_nominal_mm
            - full_extension_intrusion_mm
        ),
    )

    # -------------------------------------------------------------------------
    # Piston internal oil-reservoir geometry
    # -------------------------------------------------------------------------
    #
    # Phase 2D required_piston_guide_length is the A -> piston-top length used
    # by the locked packaging model.
    #
    # E1 blind-bore end is z above A.
    #
    # Therefore the available straight internal bore length below the piston
    # top is:
    #
    #   L_internal = L_A_to_top - z_blind_end

    L_A_to_piston_top_m = (
        required_piston_guide_length_mm
        / 1000.0
    )

    L_internal_piston_bore_m = (
        L_A_to_piston_top_m
        - z_piston_bore_end_from_A
    )

    if L_internal_piston_bore_m <= 0.0:
        raise ValueError(
            "Calculated internal piston-bore length is non-positive."
        )

    A_piston_internal = circular_area(
        D_piston_i
    )

    V_piston_internal = (
        A_piston_internal
        * L_internal_piston_bore_m
    )

    # -------------------------------------------------------------------------
    # Barrel / piston areas
    # -------------------------------------------------------------------------

    A_barrel = circular_area(
        D_barrel_i
    )

    A_effective = circular_area(
        D_piston
    )

    A_barrel_annulus = (
        A_barrel
        - A_effective
    )

    radial_running_clearance = (
        D_barrel_i
        - D_piston
    ) / 2.0

    # -------------------------------------------------------------------------
    # State table
    # -------------------------------------------------------------------------

    state_definitions = [
        {
            "state": "FULL_EXTENSION",
            "x_mm": 0.0,
            "top_intrusion_mm": full_extension_intrusion_mm,
            "design_class": "PHYSICAL_DESIGN",
        },
        {
            "state": "PHASE2D_NOMINAL_REFERENCE",
            "x_mm": x_nominal_mm,
            "top_intrusion_mm": nominal_intrusion_mm,
            "design_class": "PACKAGING_REFERENCE_ONLY",
        },
        {
            "state": "FULL_PHYSICAL_STROKE",
            "x_mm": x_physical_mm,
            "top_intrusion_mm": physical_intrusion_mm,
            "design_class": "PHYSICAL_DESIGN",
        },
        {
            "state": "VIRTUAL_DIAGNOSTIC",
            "x_mm": x_virtual_mm,
            "top_intrusion_mm": virtual_intrusion_mm,
            "design_class": "DIAGNOSTIC_ONLY",
        },
    ]

    # -------------------------------------------------------------------------
    # Static-equilibrium diagnostic
    # -------------------------------------------------------------------------
    #
    # "NOMINAL_STATIC" is the Phase 2D label. Before treating it as a true
    # aircraft static-sag state, compare it with the compression at which the
    # locked Phase 1 gas spring alone supports the Phase 1 LC0 vertical load.
    #
    # At zero velocity the hydraulic damping force is zero in the Phase 1 model,
    # so the gas force is the appropriate equilibrium comparison.

    static_diagnostic_rows = []

    x_static_equilibrium_mm = np.nan
    Fz_LC0_kN = np.nan
    static_difference_mm = np.nan
    nominal_stroke_utilization_pct = (
        x_nominal_mm
        / x_physical_mm
        * 100.0
    )
    nominal_remaining_stroke_mm = (
        x_physical_mm
        - x_nominal_mm
    )

    if phase1_loads is not None:

        case_norm = (
            phase1_loads["Case"]
            .astype(str)
            .map(normalize_column_name)
        )

        lc0_rows = phase1_loads.loc[
            case_norm == normalize_column_name("LC0")
        ]

        if not lc0_rows.empty:

            Fz_LC0_kN = abs(
                float(
                    lc0_rows.iloc[0]["Fz_lim"]
                )
            )

            Fz_LC0_N = (
                Fz_LC0_kN
                * 1e3
            )

            x_static_equilibrium_m = (
                compression_for_gas_force(
                    target_force_N=Fz_LC0_N,
                    D_effective=D_piston,
                    L0=L_gas_0,
                    P0_abs=P_gas_0_abs,
                    P_atm=P_atm,
                    n_poly=n_poly,
                )
            )

            x_static_equilibrium_mm = (
                x_static_equilibrium_m
                * 1000.0
            )

            static_difference_mm = (
                x_nominal_mm
                - x_static_equilibrium_mm
            )

    static_diagnostic_rows.extend([
        {
            "quantity": "phase2d_nominal_compression",
            "value": x_nominal_mm,
            "units": "mm",
            "classification": "SOURCE_RECONSTRUCTION",
        },
        {
            "quantity": "physical_stroke",
            "value": x_physical_mm,
            "units": "mm",
            "classification": "SOURCE_PHASE1",
        },
        {
            "quantity": "nominal_remaining_stroke",
            "value": nominal_remaining_stroke_mm,
            "units": "mm",
            "classification": "DERIVED",
        },
        {
            "quantity": "nominal_stroke_utilization",
            "value": nominal_stroke_utilization_pct,
            "units": "percent",
            "classification": "DERIVED",
        },
        {
            "quantity": "LC0_vertical_load",
            "value": Fz_LC0_kN,
            "units": "kN",
            "classification": (
                "SOURCE_PHASE1_LOAD_CSV"
                if np.isfinite(Fz_LC0_kN)
                else "UNAVAILABLE"
            ),
        },
        {
            "quantity": "gas_only_static_equilibrium_compression",
            "value": x_static_equilibrium_mm,
            "units": "mm",
            "classification": (
                "DERIVED_FROM_PHASE1_GAS_AND_LC0"
                if np.isfinite(x_static_equilibrium_mm)
                else "UNAVAILABLE"
            ),
        },
        {
            "quantity": "phase2d_nominal_minus_gas_static",
            "value": static_difference_mm,
            "units": "mm",
            "classification": (
                "DIAGNOSTIC"
                if np.isfinite(static_difference_mm)
                else "UNAVAILABLE"
            ),
        },
    ])

    static_diagnostic = pd.DataFrame(
        static_diagnostic_rows
    )

    static_diagnostic.to_csv(
        OUTPUT_STATIC_DIAGNOSTIC_CSV,
        index=False,
    )

    # Add the physically meaningful zero-velocity static state when LC0 was
    # successfully resolved. The Phase 2D "nominal" position is retained as a
    # packaging reference only and is NOT treated as aircraft static sag.
    if np.isfinite(x_static_equilibrium_mm):

        lc0_static_intrusion_mm = (
            full_extension_intrusion_mm
            + x_static_equilibrium_mm
        )

        state_definitions.insert(
            1,
            {
                "state": "LC0_STATIC_EQUILIBRIUM",
                "x_mm": x_static_equilibrium_mm,
                "top_intrusion_mm": lc0_static_intrusion_mm,
                "design_class": "PHYSICAL_DESIGN",
            },
        )

    state_records = []

    for item in state_definitions:

        x_m = item["x_mm"] / 1000.0

        gas = gas_state(
            x=x_m,
            D_effective=D_piston,
            L0=L_gas_0,
            P0_abs=P_gas_0_abs,
            P_atm=P_atm,
            n_poly=n_poly,
        )

        # Equivalent axial height if the entire Phase 1 gas volume is mapped
        # into the 64 mm ID upper-barrel cross section.
        equivalent_gas_height_m = (
            gas["gas_volume_m3"]
            / A_barrel
        )

        # First-order MINIMUM closure plane assuming gas volume begins
        # immediately above the piston top. Real hardware needs additional
        # non-gas axial reserve, swept parametrically later.
        gas_only_closure_above_U_m = (
            item["top_intrusion_mm"]
            / 1000.0
            + equivalent_gas_height_m
        )

        # Reconstruct axle A and E1 blind-bore-end locations relative to U.
        z_A_above_U_m = (
            item["top_intrusion_mm"]
            / 1000.0
            - L_A_to_piston_top_m
        )

        z_blind_end_above_U_m = (
            z_A_above_U_m
            + z_piston_bore_end_from_A
        )

        state_records.append({
            "state": item["state"],
            "design_class": item["design_class"],
            "compression_mm": item["x_mm"],
            "piston_top_intrusion_above_U_mm": (
                item["top_intrusion_mm"]
            ),
            "axle_A_above_U_mm": (
                z_A_above_U_m * 1000.0
            ),
            "piston_bore_blind_end_above_U_mm": (
                z_blind_end_above_U_m * 1000.0
            ),
            "gas_model_length_mm": (
                gas["gas_length_m"] * 1000.0
            ),
            "gas_volume_cm3": (
                gas["gas_volume_m3"] * 1e6
            ),
            "gas_equivalent_height_in_64mm_barrel_mm": (
                equivalent_gas_height_m * 1000.0
            ),
            "gas_pressure_abs_MPa": (
                gas["gas_pressure_abs_Pa"] / 1e6
            ),
            "gas_pressure_gauge_MPa": (
                gas["gas_pressure_gauge_Pa"] / 1e6
            ),
            "gas_force_kN": (
                gas["gas_force_N"] / 1e3
            ),
            "gas_only_min_closure_above_U_mm": (
                gas_only_closure_above_U_m * 1000.0
            ),
        })

    states = pd.DataFrame(
        state_records
    )

    states.to_csv(
        OUTPUT_STATES_CSV,
        index=False,
    )

    # -------------------------------------------------------------------------
    # PHYSICAL VOLUME-BOUND AUDIT
    # -------------------------------------------------------------------------
    #
    # The V0.1 gas-only closure is a LOWER BOUND because it ignores hydraulic
    # fluid and hardware in the upper working chamber.
    #
    # Until the detailed metering topology is frozen, create a deliberately
    # conservative UPPER BOUND by assuming that the full Phase 1 equivalent
    # swept volume A_eff*x must also be accommodated above the moving piston.
    #
    # This does NOT assert that real fluid transfer equals A_eff*x. It brackets
    # the axial packaging problem using only quantities already defined by the
    # locked effective model.
    #
    # Lower bound:
    #     V_upper = V_gas
    #
    # Conservative upper bound:
    #     V_upper = V_gas + A_eff*x
    #
    # Because the Phase 1 gas law uses
    #     V_gas = V_gas0 - A_eff*x
    # this conservative upper-bound fluid+gas volume is V_gas0 at every state.

    A_effective_phase1 = circular_area(
        D_piston
    )

    V_gas0 = (
        A_effective_phase1
        * L_gas_0
    )

    volume_bound_records = []

    for _, state_row in states.iterrows():

        x_m = (
            float(
                state_row["compression_mm"]
            )
            / 1000.0
        )

        top_intrusion_m = (
            float(
                state_row[
                    "piston_top_intrusion_above_U_mm"
                ]
            )
            / 1000.0
        )

        V_gas = (
            float(
                state_row["gas_volume_cm3"]
            )
            / 1e6
        )

        V_equiv_transfer = (
            A_effective_phase1
            * x_m
        )

        V_lower_reservoir_remaining = (
            V_piston_internal
            - V_equiv_transfer
        )

        lower_bound_height_m = (
            V_gas
            / A_barrel
        )

        upper_bound_volume = (
            V_gas
            + V_equiv_transfer
        )

        upper_bound_height_m = (
            upper_bound_volume
            / A_barrel
        )

        lower_bound_closure_m = (
            top_intrusion_m
            + lower_bound_height_m
        )

        upper_bound_closure_m = (
            top_intrusion_m
            + upper_bound_height_m
        )

        volume_bound_records.append({
            "state": state_row["state"],
            "design_class": state_row["design_class"],
            "compression_mm": (
                state_row["compression_mm"]
            ),
            "phase1_equivalent_swept_volume_cm3": (
                V_equiv_transfer * 1e6
            ),
            "piston_internal_reservoir_capacity_cm3": (
                V_piston_internal * 1e6
            ),
            "conservative_reservoir_remaining_cm3": (
                V_lower_reservoir_remaining * 1e6
            ),
            "conservative_reservoir_capacity_status": (
                "PASS_CAPACITY"
                if V_lower_reservoir_remaining >= 0.0
                else "FAIL_CAPACITY"
            ),
            "gas_only_lower_bound_closure_above_U_mm": (
                lower_bound_closure_m * 1000.0
            ),
            "gas_plus_equiv_transfer_upper_bound_closure_above_U_mm": (
                upper_bound_closure_m * 1000.0
            ),
            "closure_bound_width_mm": (
                (
                    upper_bound_closure_m
                    - lower_bound_closure_m
                )
                * 1000.0
            ),
        })

    volume_bounds = pd.DataFrame(
        volume_bound_records
    )

    volume_bounds.to_csv(
        OUTPUT_VOLUME_BOUNDS_CSV,
        index=False,
    )

    # -------------------------------------------------------------------------
    # PHASE 2E2 CONSERVATIVE INTERNAL AXIAL ENVELOPE
    # -------------------------------------------------------------------------
    #
    # Use only physical-design states:
    #   - full extension
    #   - LC0 gas-only static equilibrium
    #   - full physical stroke
    #
    # Exclude:
    #   - Phase 2D nominal packaging reference
    #   - virtual diagnostic stroke
    #
    # The result is a calculated MINIMUM VOLUMETRIC ENVELOPE before adding
    # final closure thickness, metering hardware, manufacturing clearances or
    # E3 trunnion-specific geometry.

    physical_volume_bounds = volume_bounds[
        volume_bounds["design_class"]
        == "PHYSICAL_DESIGN"
    ].copy()

    governing_lower_index = (
        physical_volume_bounds[
            "gas_only_lower_bound_closure_above_U_mm"
        ]
        .idxmax()
    )

    governing_upper_index = (
        physical_volume_bounds[
            "gas_plus_equiv_transfer_upper_bound_closure_above_U_mm"
        ]
        .idxmax()
    )

    governing_lower_row = volume_bounds.loc[
        governing_lower_index
    ]

    governing_upper_row = volume_bounds.loc[
        governing_upper_index
    ]

    design_envelope = pd.DataFrame([
        {
            "quantity": "gas_only_minimum_internal_envelope_above_U",
            "value_mm": float(
                governing_lower_row[
                    "gas_only_lower_bound_closure_above_U_mm"
                ]
            ),
            "governing_state": governing_lower_row["state"],
            "classification": "LOWER_BOUND_NOT_FINAL_CLOSURE",
        },
        {
            "quantity": "conservative_volume_internal_envelope_above_U",
            "value_mm": float(
                governing_upper_row[
                    "gas_plus_equiv_transfer_upper_bound_closure_above_U_mm"
                ]
            ),
            "governing_state": governing_upper_row["state"],
            "classification": "PHASE2E2_WORKING_ENVELOPE",
        },
    ])

    design_envelope.to_csv(
        OUTPUT_DESIGN_ENVELOPE_CSV,
        index=False,
    )

    # -------------------------------------------------------------------------
    # Axial closure reserve sweep
    # -------------------------------------------------------------------------

    closure_records = []

    physical_states = states[
        states["design_class"]
        == "PHYSICAL_DESIGN"
    ].copy()

    virtual_state = states[
        states["state"]
        == "VIRTUAL_DIAGNOSTIC"
    ].iloc[0]

    for reserve_mm in non_gas_reserve_sweep_mm:

        physical_required = (
            physical_states[
                "gas_only_min_closure_above_U_mm"
            ]
            + reserve_mm
        )

        idx = physical_required.idxmax()

        governing_row = states.loc[idx]

        physical_closure_mm = float(
            physical_required.loc[idx]
        )

        virtual_closure_mm = float(
            virtual_state[
                "gas_only_min_closure_above_U_mm"
            ]
            + reserve_mm
        )

        closure_records.append({
            "non_gas_axial_reserve_mm": reserve_mm,
            "governing_physical_state": (
                governing_row["state"]
            ),
            "required_physical_closure_above_U_mm": (
                physical_closure_mm
            ),
            "required_virtual_closure_above_U_mm": (
                virtual_closure_mm
            ),
            "virtual_minus_physical_mm": (
                virtual_closure_mm
                - physical_closure_mm
            ),
            "classification": (
                "WORKING_ENVELOPE_SWEEP_NOT_LOCKED"
            ),
        })

    closure_sweep = pd.DataFrame(
        closure_records
    )

    closure_sweep.to_csv(
        OUTPUT_CLOSURE_SWEEP_CSV,
        index=False,
    )

    # -------------------------------------------------------------------------
    # Geometry / consistency checks
    # -------------------------------------------------------------------------

    gas_length_physical_mm = float(
        states.loc[
            states["state"]
            == "FULL_PHYSICAL_STROKE",
            "gas_model_length_mm",
        ].iloc[0]
    )

    gas_length_virtual_mm = float(
        states.loc[
            states["state"]
            == "VIRTUAL_DIAGNOSTIC",
            "gas_model_length_mm",
        ].iloc[0]
    )

    geometry_checks = pd.DataFrame([
        {
            "check": "PHASE1_VS_E1_PISTON_DIAMETER",
            "value": piston_diameter_difference_mm,
            "units": "mm difference",
            "criterion": (
                f"|difference| <= "
                f"{diameter_consistency_tol_mm:.2f} mm"
            ),
            "status": (
                "PASS"
                if abs(piston_diameter_difference_mm)
                <= diameter_consistency_tol_mm
                else "FAIL"
            ),
        },
        {
            "check": "BARREL_TO_PISTON_RADIAL_RUNNING_CLEARANCE",
            "value": radial_running_clearance * 1000.0,
            "units": "mm per side",
            "criterion": "> 0 mm",
            "status": (
                "PASS"
                if radial_running_clearance > 0.0
                else "FAIL"
            ),
        },
        {
            "check": "PISTON_INTERNAL_BORE_LENGTH",
            "value": L_internal_piston_bore_m * 1000.0,
            "units": "mm",
            "criterion": "> 0 mm",
            "status": (
                "PASS"
                if L_internal_piston_bore_m > 0.0
                else "FAIL"
            ),
        },
        {
            "check": "PHYSICAL_GAS_LENGTH_REMAINING",
            "value": gas_length_physical_mm,
            "units": "mm",
            "criterion": "> 0 mm",
            "status": (
                "PASS"
                if gas_length_physical_mm > 0.0
                else "FAIL"
            ),
        },
        {
            "check": "VIRTUAL_GAS_LENGTH_REMAINING",
            "value": gas_length_virtual_mm,
            "units": "mm",
            "criterion": "> 0 mm diagnostic",
            "status": (
                "PASS_DIAGNOSTIC"
                if gas_length_virtual_mm > 0.0
                else "FAIL_DIAGNOSTIC"
            ),
        },
        {
            "check": "PHYSICAL_LOWER_GUIDE_SURFACE_RESERVE",
            "value": physical_lower_reserve_mm,
            "units": "mm",
            "criterion": "> 0 mm",
            "status": (
                "PASS"
                if physical_lower_reserve_mm > 0.0
                else "FAIL"
            ),
        },
        {
            "check": "FULL_EXTENSION_RECONSTRUCTION",
            "value": full_extension_spread_mm,
            "units": "mm spread",
            "criterion": (
                f"<= {position_consistency_tol_mm:.2f} mm"
            ),
            "status": (
                "PASS"
                if full_extension_spread_mm
                <= position_consistency_tol_mm
                else "FAIL"
            ),
        },
    ])

    geometry_checks.to_csv(
        OUTPUT_GEOMETRY_CHECKS_CSV,
        index=False,
    )

    # -------------------------------------------------------------------------
    # Architecture / input record
    # -------------------------------------------------------------------------

    architecture_inputs = pd.DataFrame([
        {
            "parameter": "architecture",
            "value": (
                "two-chamber metering-pin oleo; lower hydraulic chamber; "
                "upper gas/oil chamber; relative metering pin/orifice motion; "
                "no separator piston in V0.3"
            ),
            "units": "-",
            "classification": "PHASE2E2_WORKING",
        },
        {
            "parameter": "barrel_ID",
            "value": D_barrel_i * 1000.0,
            "units": "mm",
            "classification": "LOCKED_BASELINE",
        },
        {
            "parameter": "barrel_OD",
            "value": D_barrel_o * 1000.0,
            "units": "mm",
            "classification": "LOCKED_BASELINE",
        },
        {
            "parameter": "lower_boss_envelope",
            "value": D_lower_boss * 1000.0,
            "units": "mm",
            "classification": "LOCKED_BASELINE",
        },
        {
            "parameter": "bushing_length",
            "value": bushing_length_mm,
            "units": "mm",
            "classification": "SOURCE_PHASE2D_CSV",
        },
        {
            "parameter": "required_A_to_piston_top_length",
            "value": required_piston_guide_length_mm,
            "units": "mm",
            "classification": "SOURCE_PHASE2D_CSV",
        },
        {
            "parameter": "piston_OD",
            "value": D_piston * 1000.0,
            "units": "mm",
            "classification": "SOURCE_PHASE2E1_CSV",
        },
        {
            "parameter": "piston_ID",
            "value": D_piston_i * 1000.0,
            "units": "mm",
            "classification": "SOURCE_PHASE2E1_CSV",
        },
        {
            "parameter": "piston_bore_blind_end_from_A",
            "value": z_piston_bore_end_from_A * 1000.0,
            "units": "mm above A",
            "classification": "SOURCE_PHASE2E1_CSV",
        },
        {
            "parameter": "piston_internal_bore_length",
            "value": L_internal_piston_bore_m * 1000.0,
            "units": "mm",
            "classification": "DERIVED_PHASE2E2",
        },
        {
            "parameter": "piston_internal_bore_volume",
            "value": V_piston_internal * 1e6,
            "units": "cm^3",
            "classification": "DERIVED_PHASE2E2",
        },
        {
            "parameter": "barrel_piston_radial_clearance",
            "value": radial_running_clearance * 1000.0,
            "units": "mm per side",
            "classification": "DERIVED_PHASE2E2",
        },
        {
            "parameter": "barrel_minus_piston_annulus_area",
            "value": A_barrel_annulus * 1e6,
            "units": "mm^2",
            "classification": "DERIVED_PHASE2E2",
        },
        {
            "parameter": "phase1_effective_piston_area",
            "value": A_effective_phase1 * 1e6,
            "units": "mm^2",
            "classification": "DERIVED_FROM_PHASE1_PISTON_DIAMETER",
        },
        {
            "parameter": "physical_barrel_area",
            "value": A_barrel * 1e6,
            "units": "mm^2",
            "classification": "DERIVED_LOCKED_BASELINE",
        },
        {
            "parameter": "phase1_effective_area_to_barrel_area_ratio",
            "value": A_effective_phase1 / A_barrel,
            "units": "-",
            "classification": "PHASE2E2_MODEL_MAPPING",
        },
        {
            "parameter": "phase1_initial_gas_volume",
            "value": V_gas0 * 1e6,
            "units": "cm^3",
            "classification": "DERIVED_PHASE2E2",
        },
        {
            "parameter": "phase1_initial_gas_length",
            "value": L_gas_0 * 1000.0,
            "units": "mm",
            "classification": (
                "SOURCE_PHASE1_PY"
                if not phase1_fallback
                else "LOCKED_PHASE1_INPUT_FALLBACK"
            ),
        },
        {
            "parameter": "phase1_precharge_abs",
            "value": P_gas_0_abs / 1e6,
            "units": "MPa",
            "classification": (
                "SOURCE_PHASE1_PY"
                if not phase1_fallback
                else "LOCKED_PHASE1_INPUT_FALLBACK"
            ),
        },
        {
            "parameter": "phase1_polytropic_exponent",
            "value": n_poly,
            "units": "-",
            "classification": (
                "SOURCE_PHASE1_PY"
                if not phase1_fallback
                else "LOCKED_PHASE1_INPUT_FALLBACK"
            ),
        },
    ])

    architecture_inputs.to_csv(
        OUTPUT_ARCHITECTURE_INPUTS_CSV,
        index=False,
    )

    # -------------------------------------------------------------------------
    # Console report
    # -------------------------------------------------------------------------

    print("=" * 110)
    print(" PHASE 2E2 — UPPER BARREL / INTERNAL CAVITY PACKAGING V0.3")
    print("=" * 110)

    print("\nSOURCE CONNECTION")
    print("-" * 110)

    if phase1_path is not None:
        print(f"Phase 1 oleo source:        {phase1_path}")
    else:
        print(
            "Phase 1 oleo source:        "
            "locked primitive fallback inputs"
        )

    print(f"Phase 2D packaging CSV:     {packaging_path}")
    print(f"Phase 2E1 geometry CSV:     {e1_path}")

    print("\nWORKING PHYSICAL ARCHITECTURE")
    print("-" * 110)
    print(
        "Gas system:                  upper nitrogen/oil chamber; "
        "lower hydraulic chamber (no separator piston in V0.3)"
    )
    print(
        "Moving member:               hollow 58 x 4 mm piston tube"
    )
    print(
        "Metering concept:            relative metering-pin/orifice motion "
        "between telescoping members"
    )
    print(
        "Lower piston cavity:         hydraulic chamber / reservoir; "
        "E1 blind lower end retained"
    )
    print(
        "Outer working cavity:        64 mm ID upper barrel"
    )

    print("\nLOCKED / SOURCE GEOMETRY")
    print("-" * 110)
    print(
        f"Smooth barrel:               "
        f"{D_barrel_i*1000:.1f} mm ID / "
        f"{D_barrel_o*1000:.1f} mm OD"
    )
    print(
        f"Piston:                      "
        f"{D_piston*1000:.1f} mm OD / "
        f"{D_piston_i*1000:.1f} mm ID"
    )
    print(
        f"Radial running clearance:    "
        f"{radial_running_clearance*1000:.3f} mm / side"
    )
    print(
        f"Bronze guide length:         "
        f"{bushing_length_mm:.1f} mm"
    )
    print(
        f"A -> piston top length:      "
        f"{required_piston_guide_length_mm:.3f} mm"
    )
    print(
        f"E1 bore blind end:           "
        f"{z_piston_bore_end_from_A*1000:.3f} mm above A"
    )
    print(
        f"Usable internal bore length: "
        f"{L_internal_piston_bore_m*1000:.3f} mm"
    )
    print(
        f"Internal piston volume:      "
        f"{V_piston_internal*1e6:.1f} cm^3"
    )

    print("\nRECONSTRUCTED STROKE STATES")
    print("-" * 110)

    state_display = states[
        [
            "state",
            "compression_mm",
            "piston_top_intrusion_above_U_mm",
            "axle_A_above_U_mm",
            "piston_bore_blind_end_above_U_mm",
            "gas_model_length_mm",
            "gas_volume_cm3",
            "gas_equivalent_height_in_64mm_barrel_mm",
            "gas_pressure_abs_MPa",
            "gas_only_min_closure_above_U_mm",
        ]
    ]

    print(
        state_display.to_string(
            index=False,
            formatters={
                "compression_mm": lambda x: f"{x:.3f}",
                "piston_top_intrusion_above_U_mm": lambda x: f"{x:.3f}",
                "axle_A_above_U_mm": lambda x: f"{x:.3f}",
                "piston_bore_blind_end_above_U_mm": lambda x: f"{x:.3f}",
                "gas_model_length_mm": lambda x: f"{x:.3f}",
                "gas_volume_cm3": lambda x: f"{x:.1f}",
                "gas_equivalent_height_in_64mm_barrel_mm": lambda x: f"{x:.3f}",
                "gas_pressure_abs_MPa": lambda x: f"{x:.3f}",
                "gas_only_min_closure_above_U_mm": lambda x: f"{x:.3f}",
            },
        )
    )

    print("\nGEOMETRY / MODEL CONSISTENCY CHECKS")
    print("-" * 110)

    print(
        geometry_checks.to_string(
            index=False,
            formatters={
                "value": lambda x: f"{x:.3f}",
            },
        )
    )

    print("\nSTATIC-POSITION DIAGNOSTIC")
    print("-" * 110)
    print(
        f"Phase 2D nominal compression:         "
        f"{x_nominal_mm:.3f} mm"
    )
    print(
        f"Physical stroke:                      "
        f"{x_physical_mm:.3f} mm"
    )
    print(
        f"Remaining stroke at Phase 2D nominal: "
        f"{nominal_remaining_stroke_mm:.3f} mm"
    )
    print(
        f"Nominal stroke utilization:           "
        f"{nominal_stroke_utilization_pct:.2f}%"
    )

    if np.isfinite(x_static_equilibrium_mm):
        print(
            f"LC0 vertical load from Phase 1 CSV:   "
            f"{Fz_LC0_kN:.3f} kN"
        )
        print(
            f"Gas-only static equilibrium stroke:   "
            f"{x_static_equilibrium_mm:.3f} mm"
        )
        print(
            f"Phase2D nominal - gas static:          "
            f"{static_difference_mm:+.3f} mm"
        )
        print(
            "Disposition:                          Phase 2D nominal is retained as a "
            "PACKAGING REFERENCE ONLY; LC0 gas equilibrium is used as the "
            "physical zero-velocity static state in E2."
        )
    else:
        print(
            "LC0/static-equilibrium comparison:     "
            "UNAVAILABLE — LC0 row was not resolved."
        )

    print("\nPHYSICAL VOLUME-BOUND AUDIT")
    print("-" * 110)
    print(
        "Gas-only closure = lower bound. Gas + full Phase-1-equivalent "
        "swept-volume closure = conservative upper packaging bound."
    )

    volume_display = volume_bounds[
        [
            "state",
            "phase1_equivalent_swept_volume_cm3",
            "conservative_reservoir_remaining_cm3",
            "conservative_reservoir_capacity_status",
            "gas_only_lower_bound_closure_above_U_mm",
            "gas_plus_equiv_transfer_upper_bound_closure_above_U_mm",
        ]
    ]

    print(
        volume_display.to_string(
            index=False,
            formatters={
                "phase1_equivalent_swept_volume_cm3": lambda x: f"{x:.1f}",
                "conservative_reservoir_remaining_cm3": lambda x: f"{x:.1f}",
                "gas_only_lower_bound_closure_above_U_mm": lambda x: f"{x:.1f}",
                "gas_plus_equiv_transfer_upper_bound_closure_above_U_mm": lambda x: f"{x:.1f}",
            },
        )
    )

    print("\nPHASE 2E2 CONSERVATIVE INTERNAL AXIAL ENVELOPE")
    print("-" * 110)

    print(
        design_envelope.to_string(
            index=False,
            formatters={
                "value_mm": lambda x: f"{x:.3f}",
            },
        )
    )

    print(
        "\nNOTE: the conservative envelope is NOT yet the final upper-closure "
        "station. It is the minimum axial volume envelope before closure "
        "thickness, detailed metering hardware, manufacturing clearance and "
        "E3 trunnion packaging are added."
    )

    print("\nUPPER-CLOSURE ENVELOPE SWEEP")
    print("-" * 110)
    print(
        "The reserve below is NOT a locked oil height. It is a transparent "
        "axial allowance added above the gas-only minimum for oil, metering "
        "hardware and closure clearance."
    )

    print(
        closure_sweep.to_string(
            index=False,
            formatters={
                "non_gas_axial_reserve_mm": lambda x: f"{x:.1f}",
                "required_physical_closure_above_U_mm": lambda x: f"{x:.1f}",
                "required_virtual_closure_above_U_mm": lambda x: f"{x:.1f}",
                "virtual_minus_physical_mm": lambda x: f"{x:+.1f}",
            },
        )
    )

    print("\nOUTPUT FILES")
    print("-" * 110)
    print(f"Stroke / cavity states:     {OUTPUT_STATES_CSV}")
    print(f"Closure reserve sweep:      {OUTPUT_CLOSURE_SWEEP_CSV}")
    print(f"Geometry checks:            {OUTPUT_GEOMETRY_CHECKS_CSV}")
    print(f"Architecture inputs:        {OUTPUT_ARCHITECTURE_INPUTS_CSV}")
    print(f"Physical volume bounds:     {OUTPUT_VOLUME_BOUNDS_CSV}")
    print(f"Static equilibrium diag.:   {OUTPUT_STATIC_DIAGNOSTIC_CSV}")
    print(f"E2 design envelope:         {OUTPUT_DESIGN_ENVELOPE_CSV}")

    print("\nINTERPRETATION BOUNDARY")
    print("-" * 110)
    print(
        "V0.3 resolves the Phase 2D nominal-state ambiguity: it remains a "
        "packaging reference only, while LC0 gas-only equilibrium is the E2 "
        "zero-velocity static state. The Phase 1 gas model remains an EFFECTIVE "
        "pneumatic model. The gas-only result is a lower axial bound and the "
        "gas-plus-equivalent-transfer result is a conservative upper bound. "
        "The conservative physical envelope may now be carried forward as an "
        "E2 working requirement, but the final closure station still requires "
        "closure thickness, detailed metering hardware, manufacturing clearance "
        "and E3 trunnion packaging."
    )

    print("=" * 110)


if __name__ == "__main__":
    main()
