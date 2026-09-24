from pathlib import Path
import ast
import math
import re
import numpy as np
import pandas as pd


# =============================================================================
# LANDING GEAR DESIGN PROJECT
# PHASE 2E2 — METERING / UPPER-HEAD LAYOUT V0.4
#
# PURPOSE
#   Convert the Phase 2E2 V0.3 effective cavity envelope into a physically
#   plausible conventional metering-pin architecture:
#
#       solid upper head / future E3 attachment region
#                        │
#                 pressure closure
#                        │
#          upper nitrogen + hydraulic chamber
#                        │
#             fixed orifice/support plane
#                        │
#           tapered / stepped metering pin
#                  (moves with piston)
#                        │
#            hollow sliding piston tube
#            lower hydraulic chamber
#
#   The metering pin is attached to the moving inner piston and passes through
#   a fixed orifice plane carried by the outer cylinder / support structure.
#
#   This script does NOT lock final hardware dimensions. It:
#       1. Reads existing E2 V0.3 calculated outputs.
#       2. Extracts the Phase 1 smooth clamped-linear equivalent-orifice schedule directly
#          from the Phase 1 Python source.
#       3. Maps that continuously varying equivalent circular orifice area into candidate annular
#          pin/orifice geometries.
#       4. Sweeps physically useful piston-top/orifice-plane clearance and
#          initial upper-oil head.
#       5. Calculates the resulting pressure-closure inner-face station.
#       6. Reports the metering-pin length required for full physical stroke.
#
# DATA RULE
#   Results are calculated from existing project CSV/Python sources. Previously
#   calculated values from chat are not copied into this script.
#
# IMPORTANT
#   Phase 1 remains an EFFECTIVE gas/hydraulic model. This layout is a physical
#   mapping candidate. Once detailed CAD hardware volume is known, the Phase 1
#   gas model must be re-audited against the final internal geometry.
# =============================================================================


# =============================================================================
# 1. PATHS
# =============================================================================

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.resolve()

STATES_CSV = (
    HERE / "phase2e2_stroke_cavity_states.csv"
).resolve()

ARCH_INPUTS_CSV = (
    HERE / "phase2e2_architecture_inputs.csv"
).resolve()

DESIGN_ENVELOPE_CSV = (
    HERE / "phase2e2_design_envelope.csv"
).resolve()

OUTPUT_AXIAL_SWEEP_CSV = (
    HERE / "phase2e2_metering_axial_layout_sweep.csv"
).resolve()

OUTPUT_PIN_MAP_CSV = (
    HERE / "phase2e2_metering_pin_profile_map.csv"
).resolve()

OUTPUT_WORKING_CANDIDATE_CSV = (
    HERE / "phase2e2_metering_working_candidate.csv"
).resolve()

OUTPUT_INTERFACE_CSV = (
    HERE / "phase2e2_e3_upper_head_interface.csv"
).resolve()


# =============================================================================
# 2. PHASE 2E2 WORKING DESIGN VARIABLES — NOT LOCKED
# =============================================================================
#
# These are intentionally swept / labelled as working values. They are NOT
# silently promoted into the locked preliminary baseline.

# Minimum gap between the moving piston top and fixed orifice plane at full
# physical compression.
orifice_plane_clearance_sweep_mm = [
    10.0,
    15.0,
    20.0,
    25.0,
]

# Initial liquid depth above the fixed orifice plane at full extension.
# This keeps the metering region wetted and provides a first packaging allowance
# for an upper oil region. It is a design variable, not a sourced oil-fill spec.
initial_upper_oil_head_sweep_mm = [
    10.0,
    20.0,
    25.0,
    30.0,
    40.0,
    50.0,
]

# Candidate fixed central orifice bores. The Phase 1 equivalent flow areas are
# reproduced using an annular gap around the metering pin.
fixed_orifice_bore_sweep_mm = [
    12.0,
    14.0,
    16.0,
]

# Pin projection through / above the orifice plane at full extension so the pin
# remains positively engaged in the metering plane.
pin_tip_projection_sweep_mm = [
    10.0,
    15.0,
    20.0,
]

# One explicit working candidate used only to give the next CAD step a concrete
# starting point. It remains UNLOCKED until the whole E2 layout is accepted.
working_candidate = {
    "orifice_plane_clearance_mm": 15.0,
    "initial_upper_oil_head_mm": 25.0,
    "fixed_orifice_bore_mm": 14.0,
    "pin_tip_projection_mm": 15.0,
}

# Number of stations used to export the continuous metering-pin profile over
# the Phase 1 design metering stroke. The final physical-stroke station is
# appended separately if it lies beyond the design metering stroke.
pin_profile_sample_count = 21


# =============================================================================
# 3. UTILITIES
# =============================================================================

def normalize_column_name(name):
    return "".join(
        ch for ch in str(name).lower()
        if ch.isalnum()
    )


def read_csv_flexible(path):
    if not path.exists():
        raise FileNotFoundError(
            f"Required file not found:\n{path}"
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


def scalar_from_parameter_table(df, parameter):
    """
    Read one scalar from a table with columns:
        parameter, value, units, ...
    """

    norm = {
        normalize_column_name(col): col
        for col in df.columns
    }

    if "parameter" not in norm or "value" not in norm:
        raise ValueError(
            "Expected parameter/value table."
        )

    pcol = norm["parameter"]
    vcol = norm["value"]

    mask = (
        df[pcol]
        .astype(str)
        .map(normalize_column_name)
        == normalize_column_name(parameter)
    )

    selected = df.loc[mask]

    if selected.empty:
        raise KeyError(
            f"Parameter not found: {parameter}"
        )

    return float(
        pd.to_numeric(
            pd.Series(
                [selected.iloc[0][vcol]]
            ),
            errors="raise",
        ).iloc[0]
    )


def circular_area_from_diameter_mm(d_mm):
    return math.pi * d_mm**2 / 4.0


# =============================================================================
# 4. PHASE 1 SOURCE / METERING-SCHEDULE EXTRACTION
# =============================================================================

def numeric_literal(node, env=None):
    """
    Safely evaluate a simple numeric AST expression without executing project
    code.

    Supports:
      - numeric literals,
      - unary +/-,
      - +, -, *, /, **,
      - references to previously resolved module-level numeric constants.

    This is needed because later Phase 1 revisions may write, for example:

        x_orifice_switch = 0.050
        d_orifice_1 = 0.01030
        d_orifice_2 = 0.00997

        def orifice_diameter(x):
            if x < x_orifice_switch:
                return d_orifice_1
            return d_orifice_2
    """

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


def build_numeric_environment(tree):
    """
    Resolve simple module-level numeric assignments into a safe environment.

    Several passes are used so one constant can depend on an earlier constant.
    No project source is executed.
    """

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

        for names, value_node in assignments:

            value = numeric_literal(
                value_node,
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


def _find_env_value(env, candidate_names):
    """Find the first available numeric configuration value by exact name."""
    for name in candidate_names:
        if name in env:
            value = env[name]
            if isinstance(value, (int, float)):
                return float(value), name

    return None, None


def extract_orifice_schedule(path):
    """
    Extract the ACTUAL Phase 1 clamped-linear equivalent-orifice schedule.

    Current Phase 1 form:

        x_clamped = np.clip(x, 0.0, x_hand)
        fraction = x_clamped / x_hand
        diameter = (
            d_orifice_start
            + (d_orifice_end - d_orifice_start) * fraction
        )
        return diameter

    Some project revisions use min/max instead of np.clip or x_metering
    instead of x_hand. We read the numeric module configuration by AST and
    verify that the orifice_diameter() source references the expected start/end
    variables and a clamped design stroke.

    No Phase 1 project source is imported or executed.
    """

    source = path.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    tree = ast.parse(
        source,
        filename=str(path),
    )

    env = build_numeric_environment(
        tree
    )

    function = None

    for node in tree.body:
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == "orifice_diameter"
        ):
            function = node
            break

    if function is None:
        raise ValueError(
            "No orifice_diameter() function found."
        )

    segment = ast.get_source_segment(
        source,
        function,
    )

    if segment is None:
        segment = ""

    d_start_m, d_start_name = _find_env_value(
        env,
        [
            "d_orifice_start",
            "orifice_diameter_start",
            "d_metering_start",
        ],
    )

    d_end_m, d_end_name = _find_env_value(
        env,
        [
            "d_orifice_end",
            "orifice_diameter_end",
            "d_metering_end",
        ],
    )

    x_design_m, x_design_name = _find_env_value(
        env,
        [
            "x_metering",
            "x_hand",
            "x_design",
        ],
    )

    missing = []

    if d_start_m is None:
        missing.append("d_orifice_start")

    if d_end_m is None:
        missing.append("d_orifice_end")

    if x_design_m is None:
        missing.append("x_metering/x_hand")

    if missing:
        raise ValueError(
            "Smooth-linear orifice function found, but required module "
            "configuration could not be resolved: "
            + ", ".join(missing)
        )

    # Validate that these actual source variables participate in the function.
    referenced_names = {
        node.id
        for node in ast.walk(function)
        if isinstance(node, ast.Name)
    }

    if (
        d_start_name not in referenced_names
        or d_end_name not in referenced_names
        or x_design_name not in referenced_names
    ):
        raise ValueError(
            "Resolved metering constants exist, but orifice_diameter() does "
            "not reference all of them. Refusing to infer a schedule."
        )

    if x_design_m <= 0.0:
        raise ValueError(
            "Phase 1 metering design stroke must be positive."
        )

    if d_start_m <= 0.0 or d_end_m <= 0.0:
        raise ValueError(
            "Equivalent orifice diameters must be positive."
        )

    return {
        "schedule_type": "CLAMPED_LINEAR",
        "x_design_m": x_design_m,
        "d_start_m": d_start_m,
        "d_end_m": d_end_m,
        "function_name": function.name,
        "method": "AST_MODULE_CONSTANTS_PLUS_FUNCTION_REFERENCE",
        "source_segment": " ".join(segment.split()),
    }


def resolve_phase1_source():
    """
    Find the current Phase 1 oleo model by successfully extracting its
    clamped-linear equivalent-orifice schedule.
    """

    candidates = []

    for path in PROJECT_ROOT.rglob("*.py"):

        if path.resolve() == Path(__file__).resolve():
            continue

        try:
            source = path.read_text(
                encoding="utf-8",
                errors="ignore",
            )
        except Exception:
            continue

        if "def orifice_diameter" not in source:
            continue

        priority = 0

        name_lower = path.name.lower()
        parent_lower = str(path.parent).lower()

        if "landing_dynamic_v04_2dof" in name_lower:
            priority += 30
        elif "landing_dynamic" in name_lower:
            priority += 20

        if "phase1_model_development" in parent_lower:
            priority += 10
        elif "phase1" in parent_lower:
            priority += 5

        candidates.append(
            (priority, path)
        )

    if not candidates:
        raise FileNotFoundError(
            "Could not locate a Phase 1 Python source containing "
            "orifice_diameter()."
        )

    candidates.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    diagnostics = []

    for priority, path in candidates:

        try:
            schedule = extract_orifice_schedule(
                path
            )

            print(
                "\nPHASE 1 METERING SOURCE RESOLVED"
            )
            print("-" * 112)
            print(f"File: {path}")
            print(
                f"Function: "
                f"{schedule['function_name']}"
            )
            print(
                f"Schedule type: "
                f"{schedule['schedule_type']}"
            )
            print(
                f"Extraction method: "
                f"{schedule['method']}"
            )

            return path, schedule

        except Exception as exc:

            diagnostics.append(
                f"{path.name}: {exc}"
            )

    raise ValueError(
        "Phase 1 orifice_diameter() functions were found, but no current "
        "clamped-linear schedule could be resolved safely.\n\n"
        "Candidates checked:\n  - "
        + "\n  - ".join(diagnostics)
    )


# =============================================================================
# 5. LOAD E2 V0.3 OUTPUTS
# =============================================================================

def load_state(states, name):

    mask = (
        states["state"]
        .astype(str)
        .map(normalize_column_name)
        == normalize_column_name(name)
    )

    selected = states.loc[mask]

    if selected.empty:
        raise KeyError(
            f"E2 state not found: {name}"
        )

    return selected.iloc[0]


def main():

    states = read_csv_flexible(
        STATES_CSV
    )

    architecture = read_csv_flexible(
        ARCH_INPUTS_CSV
    )

    design_envelope = read_csv_flexible(
        DESIGN_ENVELOPE_CSV
    )

    phase1_path, orifice_schedule = (
        resolve_phase1_source()
    )

    full_extension = load_state(
        states,
        "FULL_EXTENSION",
    )

    lc0_static = load_state(
        states,
        "LC0_STATIC_EQUILIBRIUM",
    )

    full_physical = load_state(
        states,
        "FULL_PHYSICAL_STROKE",
    )

    virtual_diag = load_state(
        states,
        "VIRTUAL_DIAGNOSTIC",
    )

    # -------------------------------------------------------------------------
    # Source / derived geometry
    # -------------------------------------------------------------------------

    D_barrel_i_mm = scalar_from_parameter_table(
        architecture,
        "barrel_ID",
    )

    D_barrel_o_mm = scalar_from_parameter_table(
        architecture,
        "barrel_OD",
    )

    D_piston_mm = scalar_from_parameter_table(
        architecture,
        "piston_OD",
    )

    initial_gas_length_mm = scalar_from_parameter_table(
        architecture,
        "phase1_initial_gas_length",
    )

    initial_gas_volume_cm3 = scalar_from_parameter_table(
        architecture,
        "phase1_initial_gas_volume",
    )

    piston_internal_volume_cm3 = scalar_from_parameter_table(
        architecture,
        "piston_internal_bore_volume",
    )

    A_barrel_mm2 = circular_area_from_diameter_mm(
        D_barrel_i_mm
    )

    A_effective_mm2 = circular_area_from_diameter_mm(
        D_piston_mm
    )

    gas_only_height_in_barrel_mm = (
        initial_gas_volume_cm3
        * 1000.0
        / A_barrel_mm2
    )

    physical_stroke_mm = float(
        full_physical["compression_mm"]
    )

    full_ext_top_mm = float(
        full_extension[
            "piston_top_intrusion_above_U_mm"
        ]
    )

    full_physical_top_mm = float(
        full_physical[
            "piston_top_intrusion_above_U_mm"
        ]
    )

    # Cross-check that piston-top motion equals physical compression.
    top_motion_mm = (
        full_physical_top_mm
        - full_ext_top_mm
    )

    if not np.isclose(
        top_motion_mm,
        physical_stroke_mm,
        atol=0.25,
    ):
        raise ValueError(
            "Piston-top motion does not match physical stroke. "
            f"Top motion={top_motion_mm:.3f} mm, "
            f"stroke={physical_stroke_mm:.3f} mm."
        )

    # -------------------------------------------------------------------------
    # Phase 1 smooth-linear metering schedule
    # -------------------------------------------------------------------------

    if (
        orifice_schedule.get("schedule_type")
        != "CLAMPED_LINEAR"
    ):
        raise ValueError(
            "This E2 version expects the current Phase 1 CLAMPED_LINEAR "
            "equivalent-orifice schedule."
        )

    x_metering_design_mm = (
        orifice_schedule["x_design_m"]
        * 1000.0
    )

    d_eq_start_mm = (
        orifice_schedule["d_start_m"]
        * 1000.0
    )

    d_eq_end_mm = (
        orifice_schedule["d_end_m"]
        * 1000.0
    )

    A_eq_start_mm2 = (
        circular_area_from_diameter_mm(
            d_eq_start_mm
        )
    )

    A_eq_end_mm2 = (
        circular_area_from_diameter_mm(
            d_eq_end_mm
        )
    )

    if x_metering_design_mm > physical_stroke_mm + 1e-9:
        raise ValueError(
            "Phase 1 metering design stroke exceeds the E2 physical stroke."
        )

    def phase1_equivalent_orifice_diameter_mm(x_mm):
        """
        Reproduce the locked Phase 1 smooth-linear / clamped schedule.
        """

        x_clamped_mm = min(
            max(
                float(x_mm),
                0.0,
            ),
            x_metering_design_mm,
        )

        fraction = (
            x_clamped_mm
            / x_metering_design_mm
        )

        return (
            d_eq_start_mm
            + (
                d_eq_end_mm
                - d_eq_start_mm
            )
            * fraction
        )

    # -------------------------------------------------------------------------
    # Map equivalent circular area -> continuous annular metering-pin profile
    #
    # At each compression x:
    #
    #   A_eq(x) = pi/4 * d_eq(x)^2
    #
    # For a fixed circular support/orifice bore D_o and a concentric pin:
    #
    #   A_eq(x) = pi/4 * (D_o^2 - D_pin(x)^2)
    #
    # therefore
    #
    #   D_pin(x) = sqrt(D_o^2 - d_eq(x)^2)
    #
    # The fixed orifice samples successive axial stations of the moving pin as
    # the piston compresses. Thus compression x is also the profile station
    # measured from the full-extension orifice intercept.
    # -------------------------------------------------------------------------

    profile_stations_mm = np.linspace(
        0.0,
        x_metering_design_mm,
        pin_profile_sample_count,
    )

    # The schedule is clamped beyond the Phase 1 design metering stroke.
    # Include the full physical-stroke station explicitly if required.
    if (
        physical_stroke_mm
        > x_metering_design_mm + 1e-9
    ):
        profile_stations_mm = np.append(
            profile_stations_mm,
            physical_stroke_mm,
        )

    pin_map_records = []

    for D_orifice_mm in fixed_orifice_bore_sweep_mm:

        for x_profile_mm in profile_stations_mm:

            d_eq_mm = (
                phase1_equivalent_orifice_diameter_mm(
                    x_profile_mm
                )
            )

            A_eq_mm2 = (
                circular_area_from_diameter_mm(
                    d_eq_mm
                )
            )

            radicand = (
                D_orifice_mm**2
                - d_eq_mm**2
            )

            if radicand <= 0.0:

                D_pin_mm = np.nan
                area_error_pct = np.nan
                status = "INVALID_ORIFICE_TOO_SMALL"

            else:

                D_pin_mm = math.sqrt(
                    radicand
                )

                A_annular_mm2 = (
                    math.pi
                    / 4.0
                    * (
                        D_orifice_mm**2
                        - D_pin_mm**2
                    )
                )

                area_error_pct = (
                    (
                        A_annular_mm2
                        - A_eq_mm2
                    )
                    / A_eq_mm2
                    * 100.0
                )

                status = (
                    "PASS_AREA_MAP"
                    if abs(area_error_pct) < 1e-9
                    else "FAIL_AREA_MAP"
                )

            pin_map_records.append({
                "fixed_orifice_bore_mm": (
                    D_orifice_mm
                ),
                "compression_mm": (
                    x_profile_mm
                ),
                "pin_profile_station_from_full_extension_intercept_mm": (
                    x_profile_mm
                ),
                "schedule_region": (
                    "LINEAR"
                    if x_profile_mm
                    <= x_metering_design_mm + 1e-9
                    else "CLAMPED_END"
                ),
                "phase1_equivalent_diameter_mm": (
                    d_eq_mm
                ),
                "phase1_equivalent_area_mm2": (
                    A_eq_mm2
                ),
                "required_pin_diameter_mm": (
                    D_pin_mm
                ),
                "area_error_pct": (
                    area_error_pct
                ),
                "area_map_status": (
                    status
                ),
            })

    pin_map = pd.DataFrame(
        pin_map_records
    )

    pin_map.to_csv(
        OUTPUT_PIN_MAP_CSV,
        index=False,
    )
    # -------------------------------------------------------------------------
    # Axial layout sweep
    #
    # The fixed orifice plane must remain above the moving piston top at full
    # physical compression.
    #
    # z_orifice =
    #     z_piston_top_full_physical + clearance
    #
    # At full extension, the moving metering pin must span:
    #
    #     physical_stroke + clearance
    #
    # to reach the fixed orifice plane.
    #
    # The upper pressure chamber is placed ABOVE the fixed orifice plane.
    #
    # At full extension:
    #     upper volume = initial gas volume + selected initial upper oil volume
    #
    # The selected oil head is explicitly a WORKING packaging input, not a
    # sourced servicing quantity.
    #
    # Hardware displacement from the metering pin is reported separately.
    # -------------------------------------------------------------------------

    axial_records = []

    # Use the largest candidate pin diameter for conservative hardware-volume
    # reporting in the axial sweep.
    valid_pin_diameters = (
        pin_map[
            pin_map["required_pin_diameter_mm"]
            .notna()
        ]["required_pin_diameter_mm"]
        .to_numpy()
    )

    conservative_pin_diameter_mm = float(
        np.max(valid_pin_diameters)
    )

    A_pin_conservative_mm2 = (
        circular_area_from_diameter_mm(
            conservative_pin_diameter_mm
        )
    )

    for clearance_mm in orifice_plane_clearance_sweep_mm:

        z_orifice_mm = (
            full_physical_top_mm
            + clearance_mm
        )

        for oil_head_mm in initial_upper_oil_head_sweep_mm:

            V_upper_oil_initial_mm3 = (
                A_barrel_mm2
                * oil_head_mm
            )

            V_upper_fluid_initial_mm3 = (
                initial_gas_volume_cm3
                * 1000.0
                + V_upper_oil_initial_mm3
            )

            H_upper_fluid_nominal_mm = (
                V_upper_fluid_initial_mm3
                / A_barrel_mm2
            )

            for tip_projection_mm in pin_tip_projection_sweep_mm:

                pin_min_length_mm = (
                    physical_stroke_mm
                    + clearance_mm
                    + tip_projection_mm
                )

                # Maximum pin length occupying the region above the orifice
                # plane occurs at full physical compression:
                pin_above_plane_full_stroke_mm = (
                    tip_projection_mm
                    + physical_stroke_mm
                )

                V_pin_displacement_max_mm3 = (
                    A_pin_conservative_mm2
                    * pin_above_plane_full_stroke_mm
                )

                H_pin_displacement_reserve_mm = (
                    V_pin_displacement_max_mm3
                    / A_barrel_mm2
                )

                H_upper_with_pin_reserve_mm = (
                    H_upper_fluid_nominal_mm
                    + H_pin_displacement_reserve_mm
                )

                z_closure_inner_face_mm = (
                    z_orifice_mm
                    + H_upper_with_pin_reserve_mm
                )

                axial_records.append({
                    "orifice_plane_clearance_at_full_stroke_mm": (
                        clearance_mm
                    ),
                    "initial_upper_oil_head_mm": (
                        oil_head_mm
                    ),
                    "pin_tip_projection_at_full_extension_mm": (
                        tip_projection_mm
                    ),
                    "orifice_plane_above_U_mm": (
                        z_orifice_mm
                    ),
                    "minimum_metering_pin_length_mm": (
                        pin_min_length_mm
                    ),
                    "gas_height_equivalent_in_barrel_mm": (
                        gas_only_height_in_barrel_mm
                    ),
                    "upper_fluid_height_before_pin_reserve_mm": (
                        H_upper_fluid_nominal_mm
                    ),
                    "conservative_pin_diameter_for_volume_mm": (
                        conservative_pin_diameter_mm
                    ),
                    "max_pin_displacement_volume_cm3": (
                        V_pin_displacement_max_mm3
                        / 1000.0
                    ),
                    "pin_hardware_height_reserve_mm": (
                        H_pin_displacement_reserve_mm
                    ),
                    "pressure_closure_inner_face_above_U_mm": (
                        z_closure_inner_face_mm
                    ),
                    "classification": (
                        "PHASE2E2_WORKING_SWEEP_NOT_LOCKED"
                    ),
                })

    axial_sweep = pd.DataFrame(
        axial_records
    )

    axial_sweep.to_csv(
        OUTPUT_AXIAL_SWEEP_CSV,
        index=False,
    )

    # -------------------------------------------------------------------------
    # Working candidate
    # -------------------------------------------------------------------------

    candidate_mask = (
        np.isclose(
            axial_sweep[
                "orifice_plane_clearance_at_full_stroke_mm"
            ],
            working_candidate[
                "orifice_plane_clearance_mm"
            ],
        )
        & np.isclose(
            axial_sweep[
                "initial_upper_oil_head_mm"
            ],
            working_candidate[
                "initial_upper_oil_head_mm"
            ],
        )
        & np.isclose(
            axial_sweep[
                "pin_tip_projection_at_full_extension_mm"
            ],
            working_candidate[
                "pin_tip_projection_mm"
            ],
        )
    )

    candidate_rows = axial_sweep.loc[
        candidate_mask
    ]

    if candidate_rows.empty:
        raise ValueError(
            "Working axial candidate is not represented in the sweep."
        )

    candidate_axial = candidate_rows.iloc[0]

    candidate_pin_rows = pin_map.loc[
        np.isclose(
            pin_map["fixed_orifice_bore_mm"],
            working_candidate[
                "fixed_orifice_bore_mm"
            ],
        )
    ].copy()

    if candidate_pin_rows.empty:
        raise ValueError(
            "Working candidate fixed-orifice bore was not represented "
            "in the continuous pin-profile map."
        )

    candidate_pin_rows = (
        candidate_pin_rows
        .sort_values(
            "compression_mm"
        )
        .reset_index(drop=True)
    )

    pin_start_mm = float(
        candidate_pin_rows.iloc[0][
            "required_pin_diameter_mm"
        ]
    )

    # Value at the Phase 1 design metering endpoint.
    end_rows = candidate_pin_rows.loc[
        np.isclose(
            candidate_pin_rows["compression_mm"],
            x_metering_design_mm,
            atol=1e-8,
        )
    ]

    if end_rows.empty:
        raise ValueError(
            "Could not resolve the pin diameter at the Phase 1 metering "
            "design-stroke endpoint."
        )

    pin_end_mm = float(
        end_rows.iloc[0][
            "required_pin_diameter_mm"
        ]
    )

    physical_rows = candidate_pin_rows.loc[
        np.isclose(
            candidate_pin_rows["compression_mm"],
            physical_stroke_mm,
            atol=1e-8,
        )
    ]

    if physical_rows.empty:
        # This only occurs if physical stroke exactly equals the metering design
        # stroke and the endpoint row already represents both.
        pin_physical_mm = pin_end_mm
    else:
        pin_physical_mm = float(
            physical_rows.iloc[-1][
                "required_pin_diameter_mm"
            ]
        )

    pin_diameter_change_mm = (
        pin_end_mm
        - pin_start_mm
    )

    candidate_pin_mean_mm = float(
        candidate_pin_rows[
            "required_pin_diameter_mm"
        ].mean()
    )

    candidate_slenderness = (
        float(
            candidate_axial[
                "minimum_metering_pin_length_mm"
            ]
        )
        / candidate_pin_mean_mm
    )

    working_output = pd.DataFrame([
        {
            "parameter": "architecture",
            "value": (
                "moving metering pin on inner piston; "
                "fixed orifice/support plane in outer barrel; "
                "upper nitrogen/oil chamber above orifice plane"
            ),
            "units": "-",
            "classification": "PHASE2E2_WORKING_NOT_LOCKED",
        },
        {
            "parameter": "orifice_plane_clearance_at_full_stroke",
            "value": working_candidate[
                "orifice_plane_clearance_mm"
            ],
            "units": "mm",
            "classification": "WORKING_SELECTION_NOT_LOCKED",
        },
        {
            "parameter": "orifice_plane_above_U",
            "value": float(
                candidate_axial[
                    "orifice_plane_above_U_mm"
                ]
            ),
            "units": "mm",
            "classification": "DERIVED_FROM_WORKING_SELECTION",
        },
        {
            "parameter": "initial_upper_oil_head",
            "value": working_candidate[
                "initial_upper_oil_head_mm"
            ],
            "units": "mm",
            "classification": "WORKING_SELECTION_NOT_LOCKED",
        },
        {
            "parameter": "fixed_orifice_bore",
            "value": working_candidate[
                "fixed_orifice_bore_mm"
            ],
            "units": "mm",
            "classification": "WORKING_SELECTION_NOT_LOCKED",
        },
        {
            "parameter": "phase1_metering_design_stroke",
            "value": x_metering_design_mm,
            "units": "mm compression",
            "classification": "SOURCE_PHASE1_PY",
        },
        {
            "parameter": "phase1_equivalent_orifice_start",
            "value": d_eq_start_mm,
            "units": "mm",
            "classification": "SOURCE_PHASE1_PY",
        },
        {
            "parameter": "phase1_equivalent_orifice_end",
            "value": d_eq_end_mm,
            "units": "mm",
            "classification": "SOURCE_PHASE1_PY",
        },
        {
            "parameter": "pin_diameter_at_zero_compression",
            "value": pin_start_mm,
            "units": "mm",
            "classification": "DERIVED_FROM_PHASE1_EQUIVALENT_AREA",
        },
        {
            "parameter": "pin_diameter_at_metering_design_stroke",
            "value": pin_end_mm,
            "units": "mm",
            "classification": "DERIVED_FROM_PHASE1_EQUIVALENT_AREA",
        },
        {
            "parameter": "pin_diameter_at_full_physical_stroke",
            "value": pin_physical_mm,
            "units": "mm",
            "classification": "DERIVED_FROM_CLAMPED_PHASE1_SCHEDULE",
        },
        {
            "parameter": "pin_diameter_change_over_metering_stroke",
            "value": pin_diameter_change_mm,
            "units": "mm",
            "classification": "DERIVED_FROM_PHASE1_EQUIVALENT_AREA",
        },
        {
            "parameter": "pin_tip_projection_at_full_extension",
            "value": working_candidate[
                "pin_tip_projection_mm"
            ],
            "units": "mm",
            "classification": "WORKING_SELECTION_NOT_LOCKED",
        },
        {
            "parameter": "minimum_metering_pin_length",
            "value": float(
                candidate_axial[
                    "minimum_metering_pin_length_mm"
                ]
            ),
            "units": "mm",
            "classification": "DERIVED_FROM_WORKING_SELECTION",
        },
        {
            "parameter": "approx_pin_length_to_mean_diameter",
            "value": candidate_slenderness,
            "units": "-",
            "classification": "REPORT_ONLY",
        },
        {
            "parameter": "pressure_closure_inner_face_above_U",
            "value": float(
                candidate_axial[
                    "pressure_closure_inner_face_above_U_mm"
                ]
            ),
            "units": "mm",
            "classification": "WORKING_SELECTION_NOT_LOCKED",
        },
        {
            "parameter": "max_pin_hardware_displacement_volume",
            "value": float(
                candidate_axial[
                    "max_pin_displacement_volume_cm3"
                ]
            ),
            "units": "cm^3",
            "classification": "CONSERVATIVE_PACKAGING_RESERVE",
        },
        {
            "parameter": "piston_internal_reservoir_capacity",
            "value": piston_internal_volume_cm3,
            "units": "cm^3",
            "classification": "SOURCE_PHASE2E2_V03",
        },
    ])

    working_output.to_csv(
        OUTPUT_WORKING_CANDIDATE_CSV,
        index=False,
    )

    # -------------------------------------------------------------------------
    # E3 interface record
    # -------------------------------------------------------------------------
    #
    # The pressure closure inner face marks the start of the upper solid-head
    # region. E3 should place its attachment / trunnion load path in solid
    # structure rather than drilling through the active pressure chamber unless
    # a dedicated pressure-compatible boss is deliberately designed.

    interface = pd.DataFrame([
        {
            "interface_requirement": (
                "minimum_pressure_closure_inner_face_above_U"
            ),
            "value": float(
                candidate_axial[
                    "pressure_closure_inner_face_above_U_mm"
                ]
            ),
            "units": "mm",
            "classification": "WORKING_E2_TO_E3_INTERFACE",
        },
        {
            "interface_requirement": (
                "E3_attachment_location_rule"
            ),
            "value": (
                "Place trunnion / upper attachment in solid head at or above "
                "the pressure closure, unless E3 deliberately designs and "
                "checks a pressure-penetrating boss."
            ),
            "units": "-",
            "classification": "ARCHITECTURE_RULE",
        },
        {
            "interface_requirement": (
                "solid_head_axial_length"
            ),
            "value": (
                "TBD by E3 from trunnion diameter, bearing, edge-distance, "
                "local stress and manufacturing requirements."
            ),
            "units": "-",
            "classification": "NOT_YET_SIZED",
        },
    ])

    interface.to_csv(
        OUTPUT_INTERFACE_CSV,
        index=False,
    )

    # -------------------------------------------------------------------------
    # Console report
    # -------------------------------------------------------------------------

    print("=" * 112)
    print(" PHASE 2E2 — METERING / UPPER-HEAD LAYOUT V0.4")
    print("=" * 112)

    print("\nSOURCE CONNECTION")
    print("-" * 112)
    print(f"E2 stroke states:           {STATES_CSV}")
    print(f"E2 architecture inputs:     {ARCH_INPUTS_CSV}")
    print(f"E2 design envelope:         {DESIGN_ENVELOPE_CSV}")
    print(f"Phase 1 metering source:    {phase1_path}")

    print("\nPHYSICAL ARCHITECTURE")
    print("-" * 112)
    print(
        "Moving inner member:         hollow 58 mm piston / lower hydraulic chamber"
    )
    print(
        "Metering element:            pin attached to moving piston"
    )
    print(
        "Flow restriction:            fixed central orifice/support plane in outer barrel"
    )
    print(
        "Upper chamber:               nitrogen + hydraulic fluid above fixed orifice plane"
    )
    print(
        "Upper structural strategy:   pressure closure first; E3 attachment in solid head above it"
    )

    print("\nPHASE 1 METERING SCHEDULE — SOURCE EXTRACTED")
    print("-" * 112)
    print(
        f"Schedule:                    smooth linear, clamped after design stroke"
    )
    print(
        f"Design metering stroke:      {x_metering_design_mm:.3f} mm"
    )
    print(
        f"Equivalent orifice start:    {d_eq_start_mm:.3f} mm "
        f"({A_eq_start_mm2:.3f} mm^2)"
    )
    print(
        f"Equivalent orifice end:      {d_eq_end_mm:.3f} mm "
        f"({A_eq_end_mm2:.3f} mm^2)"
    )
    print(
        f"Physical stroke beyond map:  "
        f"{max(0.0, physical_stroke_mm - x_metering_design_mm):.3f} mm "
        f"at clamped endpoint"
    )

    print("\nANNULAR METERING-PIN PROFILE MAP")
    print("-" * 112)

    # Print the working 14 mm candidate in detail; all swept bores are still
    # written to CSV.
    pin_display = pin_map.loc[
        np.isclose(
            pin_map["fixed_orifice_bore_mm"],
            working_candidate[
                "fixed_orifice_bore_mm"
            ],
        )
    ].copy()

    print(
        pin_display.to_string(
            index=False,
            formatters={
                "fixed_orifice_bore_mm": lambda x: f"{x:.1f}",
                "compression_mm": lambda x: f"{x:.3f}",
                "pin_profile_station_from_full_extension_intercept_mm": lambda x: f"{x:.3f}",
                "phase1_equivalent_diameter_mm": lambda x: f"{x:.4f}",
                "phase1_equivalent_area_mm2": lambda x: f"{x:.3f}",
                "required_pin_diameter_mm": (
                    lambda x: "nan"
                    if not np.isfinite(x)
                    else f"{x:.4f}"
                ),
                "area_error_pct": (
                    lambda x: "nan"
                    if not np.isfinite(x)
                    else f"{x:+.3e}"
                ),
            },
        )
    )

    print("\nAXIAL PACKAGING RANGE")
    print("-" * 112)

    axial_summary = (
        axial_sweep
        .groupby(
            "orifice_plane_clearance_at_full_stroke_mm",
            as_index=False,
        )
        .agg(
            min_closure_mm=(
                "pressure_closure_inner_face_above_U_mm",
                "min",
            ),
            max_closure_mm=(
                "pressure_closure_inner_face_above_U_mm",
                "max",
            ),
            min_pin_length_mm=(
                "minimum_metering_pin_length_mm",
                "min",
            ),
            max_pin_length_mm=(
                "minimum_metering_pin_length_mm",
                "max",
            ),
        )
    )

    print(
        axial_summary.to_string(
            index=False,
            formatters={
                "orifice_plane_clearance_at_full_stroke_mm": lambda x: f"{x:.1f}",
                "min_closure_mm": lambda x: f"{x:.1f}",
                "max_closure_mm": lambda x: f"{x:.1f}",
                "min_pin_length_mm": lambda x: f"{x:.1f}",
                "max_pin_length_mm": lambda x: f"{x:.1f}",
            },
        )
    )

    print("\nWORKING V0.4 CANDIDATE — NOT LOCKED")
    print("-" * 112)

    print(
        working_output.to_string(
            index=False,
            formatters={
                "value": lambda x: (
                    f"{x:.3f}"
                    if isinstance(x, (int, float, np.floating))
                    else str(x)
                )
            },
        )
    )

    print("\nE3 INTERFACE RULE")
    print("-" * 112)
    print(
        "Treat the calculated pressure-closure inner face as the start of a "
        "solid upper-head region. Do not place the future upper trunnion "
        "through the live pressure chamber unless a pressure-penetrating boss "
        "is deliberately designed and checked."
    )

    print("\nOUTPUT FILES")
    print("-" * 112)
    print(f"Axial layout sweep:          {OUTPUT_AXIAL_SWEEP_CSV}")
    print(f"Pin/orifice profile map:    {OUTPUT_PIN_MAP_CSV}")
    print(f"Working candidate:           {OUTPUT_WORKING_CANDIDATE_CSV}")
    print(f"E3 interface:                {OUTPUT_INTERFACE_CSV}")

    print("\nINTERPRETATION")
    print("-" * 112)
    print(
        "This step turns the effective Phase 1 hydraulic restriction into a "
        "candidate annular pin/orifice geometry while preserving the full "
        "230 mm physical stroke. The fixed-orifice bore, piston-top clearance, "
        "initial upper-oil head and pin projection remain working selections. "
        "The final CAD geometry must be fed back into the Phase 1 gas/hydraulic "
        "model because metering-pin/support hardware displaces nonzero volume."
    )

    print("=" * 112)


if __name__ == "__main__":
    main()
