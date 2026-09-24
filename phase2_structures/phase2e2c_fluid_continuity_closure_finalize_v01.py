from pathlib import Path
import ast
import math

import numpy as np
import pandas as pd


# =============================================================================
# LANDING GEAR DESIGN PROJECT
# PHASE 2E2-C — FLUID-CONTINUITY / FINAL CLOSURE AUDIT V0.1
#
# PURPOSE
#   Replace the deliberately conservative Phase 2E2 upper-cavity packaging
#   estimate with a physically consistent fixed-volume continuity model for the
#   selected 14 mm annular metering-pin candidate.
#
#   The upper fixed cavity contains:
#       1. nitrogen gas,
#       2. upper-chamber oil,
#       3. the portion of the moving metering pin above the fixed orifice plane.
#
#   At every compression state:
#
#       V_cavity = V_gas(x) + V_upper_oil(x) + V_pin_above_orifice(x)
#
#   The cavity volume is set from the FULL-EXTENSION condition using the
#   working initial upper-oil head. Oil transfer is then solved from continuity,
#   rather than represented by the earlier conservative A_eff*x upper bound.
#
#   This script also:
#       - verifies the 64/74 mm barrel baseline,
#       - verifies the 14 mm pin profile against the E2 profile CSV,
#       - computes actual candidate-specific pin displacement,
#       - checks remaining lower-reservoir volume,
#       - recomputes the pressure-closure plate screen using the locked
#         7075-T6 Poisson ratio nu = 0.33,
#       - establishes the preliminary E2 -> E3 structural interface.
#
# IMPORTANT
#   The 6 mm closure thickness produced by this screen remains a structural
#   PRELIMINARY minimum. Seal glands, retainers/threads, ports, local geometry,
#   manufacturing allowance and detailed FEA remain outside this calculation.
# =============================================================================


# =============================================================================
# 1. PATHS
# =============================================================================

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.resolve()

ARCH_CSV = (
    HERE / "phase2e2_architecture_inputs.csv"
).resolve()

STATES_CSV = (
    HERE / "phase2e2_stroke_cavity_states.csv"
).resolve()

DESIGN_ENVELOPE_CSV = (
    HERE / "phase2e2_design_envelope.csv"
).resolve()

METERING_CANDIDATE_CSV = (
    HERE / "phase2e2_metering_working_candidate.csv"
).resolve()

PIN_PROFILE_CSV = (
    HERE / "phase2e2_metering_pin_profile_map.csv"
).resolve()

PHASE1_SOURCE = (
    PROJECT_ROOT
    / "phase1_model_development"
    / "landing_dynamic_v04_2dof.py"
).resolve()

OUTPUT_CONTINUITY_CSV = (
    HERE / "phase2e2c_fluid_continuity_states.csv"
).resolve()

OUTPUT_CHECKS_CSV = (
    HERE / "phase2e2c_continuity_checks.csv"
).resolve()

OUTPUT_CLOSURE_CSV = (
    HERE / "phase2e2c_closure_structural_screen.csv"
).resolve()

OUTPUT_INTERFACE_CSV = (
    HERE / "phase2e2c_e3_interface.csv"
).resolve()


# =============================================================================
# 2. LOCKED / RETAINED BASELINES
# =============================================================================

EXPECTED_BARREL_ID_MM = 64.0
EXPECTED_BARREL_OD_MM = 74.0
EXPECTED_PISTON_OD_MM = 58.0

# 7075-T6 project baseline.
E_7075_GPA = 71.7
NU_7075 = 0.33
SY_7075_MPA = 503.0
SU_7075_MPA = 572.0

ULTIMATE_FACTOR = 1.50

# Screening increment only.
CLOSURE_SWEEP_MM = np.arange(
    3.0,
    20.0 + 1e-12,
    0.5,
)

GEOMETRY_TOL_MM = 0.10
PROFILE_TOL_MM = 0.002
VOLUME_TOL_CM3 = 0.05


# =============================================================================
# 3. BASIC UTILITIES
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
        str(col).replace(
            "\ufeff",
            "",
        ).strip()
        for col in df.columns
    ]

    return df


def parameter_value(
    df,
    parameter,
):
    cols = {
        normalize(col): col
        for col in df.columns
    }

    if (
        "parameter" not in cols
        or "value" not in cols
    ):
        raise ValueError(
            "Expected parameter/value CSV table."
        )

    pcol = cols["parameter"]
    vcol = cols["value"]

    mask = (
        df[pcol]
        .astype(str)
        .map(normalize)
        == normalize(parameter)
    )

    rows = df.loc[
        mask
    ]

    if rows.empty:
        raise KeyError(
            f"Parameter not found: {parameter}"
        )

    return rows.iloc[0][
        vcol
    ]


def parameter_float(
    df,
    parameter,
):
    return float(
        pd.to_numeric(
            pd.Series([
                parameter_value(
                    df,
                    parameter,
                )
            ]),
            errors="raise",
        ).iloc[0]
    )


def circular_area_mm2(
    diameter_mm,
):
    return (
        math.pi
        * diameter_mm**2
        / 4.0
    )


def read_state(
    states,
    name,
):
    mask = (
        states["state"]
        .astype(str)
        .map(normalize)
        == normalize(name)
    )

    rows = states.loc[
        mask
    ]

    if rows.empty:
        raise KeyError(
            f"State not found: {name}"
        )

    return rows.iloc[0]


def design_envelope_value(
    df,
    quantity,
):
    qcol = None
    vcol = None

    for col in df.columns:
        key = normalize(col)

        if key == "quantity":
            qcol = col

        if key in {
            "valuemm",
            "value",
        }:
            vcol = col

    if qcol is None or vcol is None:
        raise ValueError(
            "Could not resolve design-envelope columns."
        )

    mask = (
        df[qcol]
        .astype(str)
        .map(normalize)
        == normalize(quantity)
    )

    rows = df.loc[
        mask
    ]

    if rows.empty:
        raise KeyError(
            f"Design-envelope quantity missing: {quantity}"
        )

    return float(
        rows.iloc[0][vcol]
    )


# =============================================================================
# 4. SAFE PHASE 1 NUMERIC SOURCE READER
# =============================================================================

def numeric_literal(
    node,
    env=None,
):
    if env is None:
        env = {}

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

        return None

    if isinstance(
        node,
        ast.Name,
    ):
        value = env.get(
            node.id
        )

        if isinstance(
            value,
            (int, float),
        ):
            return float(
                value
            )

        return None

    if isinstance(
        node,
        ast.UnaryOp,
    ):
        value = numeric_literal(
            node.operand,
            env,
        )

        if value is None:
            return None

        if isinstance(
            node.op,
            ast.USub,
        ):
            return -value

        if isinstance(
            node.op,
            ast.UAdd,
        ):
            return value

        return None

    if isinstance(
        node,
        ast.BinOp,
    ):
        left = numeric_literal(
            node.left,
            env,
        )

        right = numeric_literal(
            node.right,
            env,
        )

        if (
            left is None
            or right is None
        ):
            return None

        if isinstance(
            node.op,
            ast.Add,
        ):
            return left + right

        if isinstance(
            node.op,
            ast.Sub,
        ):
            return left - right

        if isinstance(
            node.op,
            ast.Mult,
        ):
            return left * right

        if isinstance(
            node.op,
            ast.Div,
        ):
            return left / right

        if isinstance(
            node.op,
            ast.Pow,
        ):
            return left**right

    return None


def numeric_environment(
    path,
):
    if not path.exists():
        raise FileNotFoundError(
            f"Phase 1 source not found:\n{path}"
        )

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

            if names:
                assignments.append(
                    (
                        names,
                        node.value,
                    )
                )

        elif isinstance(
            node,
            ast.AnnAssign,
        ):
            if isinstance(
                node.target,
                ast.Name,
            ):
                assignments.append(
                    (
                        [node.target.id],
                        node.value,
                    )
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
# 5. METERING-PIN GEOMETRY
# =============================================================================

def equivalent_orifice_diameter_mm(
    x_mm,
    d_start_mm,
    d_end_mm,
    x_design_mm,
):
    x_clamped = min(
        max(
            float(x_mm),
            0.0,
        ),
        x_design_mm,
    )

    fraction = (
        x_clamped
        / x_design_mm
    )

    return (
        d_start_mm
        + (
            d_end_mm
            - d_start_mm
        )
        * fraction
    )


def pin_diameter_mm(
    x_mm,
    fixed_bore_mm,
    d_start_mm,
    d_end_mm,
    x_design_mm,
):
    d_eq = (
        equivalent_orifice_diameter_mm(
            x_mm,
            d_start_mm,
            d_end_mm,
            x_design_mm,
        )
    )

    radicand = (
        fixed_bore_mm**2
        - d_eq**2
    )

    if radicand <= 0.0:
        raise ValueError(
            "Fixed orifice bore is too small for the required "
            "equivalent-orifice area."
        )

    return math.sqrt(
        radicand
    )


def pin_area_mm2(
    x_mm,
    fixed_bore_mm,
    d_start_mm,
    d_end_mm,
    x_design_mm,
):
    D_pin = pin_diameter_mm(
        x_mm,
        fixed_bore_mm,
        d_start_mm,
        d_end_mm,
        x_design_mm,
    )

    return circular_area_mm2(
        D_pin
    )


def pin_volume_above_orifice_cm3(
    compression_mm,
    tip_projection_mm,
    fixed_bore_mm,
    d_start_mm,
    d_end_mm,
    x_design_mm,
):
    """
    Pin volume inside the upper fixed cavity.

    At full extension, the pin tip projects 'tip_projection_mm' through the
    fixed orifice. As the piston compresses by x, a further x mm of the profiled
    pin moves through the orifice.

    The portion beyond the full-extension intercept is assigned the x=0 pin
    diameter. The profile from x=0 onward is integrated directly.
    """

    x = max(
        float(compression_mm),
        0.0,
    )

    A_tip = pin_area_mm2(
        0.0,
        fixed_bore_mm,
        d_start_mm,
        d_end_mm,
        x_design_mm,
    )

    V_tip_mm3 = (
        A_tip
        * tip_projection_mm
    )

    if x <= 0.0:
        V_profile_mm3 = 0.0

    else:
        # Fine deterministic integration grid. Add exact design-stroke
        # breakpoint when it lies inside the interval so the clamped tail is
        # represented exactly enough for the volume audit.
        points = list(
            np.linspace(
                0.0,
                x,
                4001,
            )
        )

        if (
            0.0
            < x_design_mm
            < x
        ):
            points.append(
                x_design_mm
            )

        xs = np.array(
            sorted(
                set(
                    float(v)
                    for v in points
                )
            ),
            dtype=float,
        )

        areas = np.array([
            pin_area_mm2(
                xi,
                fixed_bore_mm,
                d_start_mm,
                d_end_mm,
                x_design_mm,
            )
            for xi in xs
        ])

        V_profile_mm3 = float(
            np.trapezoid(
                areas,
                xs,
            )
        )

    return (
        V_tip_mm3
        + V_profile_mm3
    ) / 1000.0


# =============================================================================
# 6. STRUCTURAL CLOSURE SCREEN
# =============================================================================

def closure_sigma_ss_MPa(
    p_MPa,
    radius_mm,
    thickness_mm,
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
        K
        * p_MPa
        * radius_mm**2
        / thickness_mm**2
    )


def closure_required_t_mm(
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
# 7. MAIN
# =============================================================================

def main():

    print("=" * 122)
    print(
        " PHASE 2E2-C — FLUID-CONTINUITY / FINAL CLOSURE AUDIT V0.1"
    )
    print("=" * 122)

    arch = read_csv(
        ARCH_CSV
    )

    states = read_csv(
        STATES_CSV
    )

    design_envelope = read_csv(
        DESIGN_ENVELOPE_CSV
    )

    candidate = read_csv(
        METERING_CANDIDATE_CSV
    )

    profile = read_csv(
        PIN_PROFILE_CSV
    )

    phase1_env = numeric_environment(
        PHASE1_SOURCE
    )

    # -------------------------------------------------------------------------
    # Source geometry / model values
    # -------------------------------------------------------------------------

    barrel_ID_mm = parameter_float(
        arch,
        "barrel_ID",
    )

    barrel_OD_mm = parameter_float(
        arch,
        "barrel_OD",
    )

    piston_OD_mm = parameter_float(
        arch,
        "piston_OD",
    )

    A_eff_mm2 = parameter_float(
        arch,
        "phase1_effective_piston_area",
    )

    A_barrel_mm2 = parameter_float(
        arch,
        "physical_barrel_area",
    )

    V_gas0_cm3 = parameter_float(
        arch,
        "phase1_initial_gas_volume",
    )

    L_gas0_mm = parameter_float(
        arch,
        "phase1_initial_gas_length",
    )

    P0_abs_MPa = parameter_float(
        arch,
        "phase1_precharge_abs",
    )

    n_poly = parameter_float(
        arch,
        "phase1_polytropic_exponent",
    )

    reservoir_capacity_cm3 = parameter_float(
        candidate,
        "piston_internal_reservoir_capacity",
    )

    orifice_plane_mm = parameter_float(
        candidate,
        "orifice_plane_above_U",
    )

    initial_oil_head_mm = parameter_float(
        candidate,
        "initial_upper_oil_head",
    )

    fixed_bore_mm = parameter_float(
        candidate,
        "fixed_orifice_bore",
    )

    x_design_mm = parameter_float(
        candidate,
        "phase1_metering_design_stroke",
    )

    d_eq_start_mm = parameter_float(
        candidate,
        "phase1_equivalent_orifice_start",
    )

    d_eq_end_mm = parameter_float(
        candidate,
        "phase1_equivalent_orifice_end",
    )

    tip_projection_mm = parameter_float(
        candidate,
        "pin_tip_projection_at_full_extension",
    )

    old_working_closure_mm = parameter_float(
        candidate,
        "pressure_closure_inner_face_above_U",
    )

    old_conservative_pin_volume_cm3 = parameter_float(
        candidate,
        "max_pin_hardware_displacement_volume",
    )

    conservative_e2_envelope_mm = (
        design_envelope_value(
            design_envelope,
            "conservative_volume_internal_envelope_above_U",
        )
    )

    P_atm_MPa = (
        float(
            phase1_env[
                "P_atm"
            ]
        )
        / 1e6
    )

    # -------------------------------------------------------------------------
    # Geometry gates
    # -------------------------------------------------------------------------

    geometry_checks = {
        "barrel_ID": (
            abs(
                barrel_ID_mm
                - EXPECTED_BARREL_ID_MM
            )
            <= GEOMETRY_TOL_MM
        ),
        "barrel_OD": (
            abs(
                barrel_OD_mm
                - EXPECTED_BARREL_OD_MM
            )
            <= GEOMETRY_TOL_MM
        ),
        "piston_OD": (
            abs(
                piston_OD_mm
                - EXPECTED_PISTON_OD_MM
            )
            <= GEOMETRY_TOL_MM
        ),
        "area_consistency": (
            abs(
                A_barrel_mm2
                - circular_area_mm2(
                    barrel_ID_mm
                )
            )
            <= 0.1
        ),
    }

    if not all(
        geometry_checks.values()
    ):
        raise ValueError(
            "E2 source geometry failed the continuity-audit hard gate:\n"
            + "\n".join(
                f"  {name}: {status}"
                for name, status
                in geometry_checks.items()
            )
        )

    # -------------------------------------------------------------------------
    # Verify continuous 14 mm pin profile CSV
    # -------------------------------------------------------------------------

    candidate_profile = profile.loc[
        np.isclose(
            pd.to_numeric(
                profile[
                    "fixed_orifice_bore_mm"
                ],
                errors="coerce",
            ),
            fixed_bore_mm,
        )
    ].copy()

    if candidate_profile.empty:
        raise ValueError(
            "No pin-profile rows found for the working fixed-orifice bore."
        )

    profile_errors = []

    for _, row in candidate_profile.iterrows():

        x = float(
            row[
                "compression_mm"
            ]
        )

        D_csv = float(
            row[
                "required_pin_diameter_mm"
            ]
        )

        D_calc = pin_diameter_mm(
            x,
            fixed_bore_mm,
            d_eq_start_mm,
            d_eq_end_mm,
            x_design_mm,
        )

        profile_errors.append(
            abs(
                D_csv
                - D_calc
            )
        )

    max_profile_error_mm = max(
        profile_errors
    )

    if (
        max_profile_error_mm
        > PROFILE_TOL_MM
    ):
        raise ValueError(
            "Metering-pin profile CSV does not match the current "
            "equivalent-area law."
        )

    # -------------------------------------------------------------------------
    # Full-extension fixed-cavity definition
    # -------------------------------------------------------------------------

    V_upper_oil0_cm3 = (
        A_barrel_mm2
        * initial_oil_head_mm
        / 1000.0
    )

    V_pin0_cm3 = (
        pin_volume_above_orifice_cm3(
            0.0,
            tip_projection_mm,
            fixed_bore_mm,
            d_eq_start_mm,
            d_eq_end_mm,
            x_design_mm,
        )
    )

    V_fixed_cavity_cm3 = (
        V_gas0_cm3
        + V_upper_oil0_cm3
        + V_pin0_cm3
    )

    H_fixed_cavity_mm = (
        V_fixed_cavity_cm3
        * 1000.0
        / A_barrel_mm2
    )

    closure_inner_face_mm = (
        orifice_plane_mm
        + H_fixed_cavity_mm
    )

    # -------------------------------------------------------------------------
    # State-by-state fluid continuity
    # -------------------------------------------------------------------------

    continuity_rows = []

    for _, row in states.iterrows():

        state_name = str(
            row["state"]
        )

        x_mm = float(
            row[
                "compression_mm"
            ]
        )

        # Effective Phase 1 gas volume:
        # V(x) = V0 - A_eff*x
        V_gas_cm3 = (
            V_gas0_cm3
            - (
                A_eff_mm2
                * x_mm
                / 1000.0
            )
        )

        if V_gas_cm3 <= 0.0:
            raise ValueError(
                f"Non-positive gas volume at state {state_name}."
            )

        P_abs_MPa = (
            P0_abs_MPa
            * (
                V_gas0_cm3
                / V_gas_cm3
            )**n_poly
        )

        V_pin_cm3 = (
            pin_volume_above_orifice_cm3(
                x_mm,
                tip_projection_mm,
                fixed_bore_mm,
                d_eq_start_mm,
                d_eq_end_mm,
                x_design_mm,
            )
        )

        V_upper_oil_cm3 = (
            V_fixed_cavity_cm3
            - V_gas_cm3
            - V_pin_cm3
        )

        oil_transfer_cm3 = (
            V_upper_oil_cm3
            - V_upper_oil0_cm3
        )

        conservative_phase1_swept_cm3 = (
            A_eff_mm2
            * x_mm
            / 1000.0
        )

        pin_increment_cm3 = (
            V_pin_cm3
            - V_pin0_cm3
        )

        identity_residual_cm3 = (
            conservative_phase1_swept_cm3
            - oil_transfer_cm3
            - pin_increment_cm3
        )

        reservoir_remaining_cm3 = (
            reservoir_capacity_cm3
            - oil_transfer_cm3
        )

        cavity_residual_cm3 = (
            V_fixed_cavity_cm3
            - (
                V_gas_cm3
                + V_upper_oil_cm3
                + V_pin_cm3
            )
        )

        continuity_rows.append({
            "state": state_name,
            "compression_mm": x_mm,
            "gas_volume_cm3": V_gas_cm3,
            "gas_pressure_abs_MPa": P_abs_MPa,
            "pin_volume_above_orifice_cm3": V_pin_cm3,
            "pin_volume_increment_from_extension_cm3": pin_increment_cm3,
            "upper_oil_volume_cm3": V_upper_oil_cm3,
            "oil_transfer_from_lower_to_upper_cm3": oil_transfer_cm3,
            "phase1_equivalent_swept_volume_cm3": conservative_phase1_swept_cm3,
            "swept_minus_transfer_minus_pin_increment_cm3": identity_residual_cm3,
            "lower_reservoir_remaining_cm3": reservoir_remaining_cm3,
            "fixed_cavity_volume_residual_cm3": cavity_residual_cm3,
            "upper_oil_positive": V_upper_oil_cm3 >= 0.0,
            "lower_reservoir_positive": reservoir_remaining_cm3 >= 0.0,
        })

    continuity = pd.DataFrame(
        continuity_rows
    )

    continuity.to_csv(
        OUTPUT_CONTINUITY_CSV,
        index=False,
    )

    # -------------------------------------------------------------------------
    # Structural closure screen using locked 7075-T6 nu = 0.33
    # -------------------------------------------------------------------------

    full_physical = continuity.loc[
        continuity["state"]
        .astype(str)
        .map(normalize)
        == normalize(
            "FULL_PHYSICAL_STROKE"
        )
    ]

    if full_physical.empty:
        raise KeyError(
            "FULL_PHYSICAL_STROKE state missing."
        )

    full_physical = (
        full_physical.iloc[0]
    )

    p_limit_MPa = (
        float(
            full_physical[
                "gas_pressure_abs_MPa"
            ]
        )
        - P_atm_MPa
    )

    p_ultimate_MPa = (
        ULTIMATE_FACTOR
        * p_limit_MPa
    )

    closure_radius_mm = (
        barrel_ID_mm
        / 2.0
    )

    t_req_limit_mm = (
        closure_required_t_mm(
            p_limit_MPa,
            closure_radius_mm,
            SY_7075_MPA,
            NU_7075,
        )
    )

    t_req_ultimate_mm = (
        closure_required_t_mm(
            p_ultimate_MPa,
            closure_radius_mm,
            SU_7075_MPA,
            NU_7075,
        )
    )

    t_theoretical_mm = max(
        t_req_limit_mm,
        t_req_ultimate_mm,
    )

    closure_rows = []

    for t_mm in CLOSURE_SWEEP_MM:

        sigma_limit = (
            closure_sigma_ss_MPa(
                p_limit_MPa,
                closure_radius_mm,
                t_mm,
                NU_7075,
            )
        )

        sigma_ultimate = (
            closure_sigma_ss_MPa(
                p_ultimate_MPa,
                closure_radius_mm,
                t_mm,
                NU_7075,
            )
        )

        MS_limit = (
            SY_7075_MPA
            / sigma_limit
            - 1.0
        )

        MS_ultimate = (
            SU_7075_MPA
            / sigma_ultimate
            - 1.0
        )

        closure_rows.append({
            "thickness_mm": t_mm,
            "sigma_limit_MPa": sigma_limit,
            "MS_limit_yield": MS_limit,
            "sigma_ultimate_MPa": sigma_ultimate,
            "MS_ultimate_tensile": MS_ultimate,
            "status": (
                "PASS_BOTH"
                if (
                    MS_limit >= 0.0
                    and MS_ultimate >= 0.0
                )
                else "FAIL"
            ),
        })

    closure_screen = pd.DataFrame(
        closure_rows
    )

    closure_screen.to_csv(
        OUTPUT_CLOSURE_CSV,
        index=False,
    )

    passing = closure_screen.loc[
        closure_screen[
            "status"
        ]
        == "PASS_BOTH"
    ]

    if passing.empty:
        raise ValueError(
            "No closure thickness in the screening sweep passes."
        )

    t_grid_pass_mm = float(
        passing.iloc[0][
            "thickness_mm"
        ]
    )

    structural_outer_face_theoretical_mm = (
        closure_inner_face_mm
        + t_theoretical_mm
    )

    structural_outer_face_grid_mm = (
        closure_inner_face_mm
        + t_grid_pass_mm
    )

    # -------------------------------------------------------------------------
    # Overall checks
    # -------------------------------------------------------------------------

    max_cavity_residual = float(
        continuity[
            "fixed_cavity_volume_residual_cm3"
        ]
        .abs()
        .max()
    )

    max_identity_residual = float(
        continuity[
            "swept_minus_transfer_minus_pin_increment_cm3"
        ]
        .abs()
        .max()
    )

    min_reservoir_remaining = float(
        continuity[
            "lower_reservoir_remaining_cm3"
        ]
        .min()
    )

    min_upper_oil = float(
        continuity[
            "upper_oil_volume_cm3"
        ]
        .min()
    )

    axial_reserve_over_conservative_mm = (
        closure_inner_face_mm
        - conservative_e2_envelope_mm
    )

    closure_shift_vs_old_mm = (
        closure_inner_face_mm
        - old_working_closure_mm
    )

    full_physical_pin_cm3 = float(
        full_physical[
            "pin_volume_above_orifice_cm3"
        ]
    )

    full_physical_oil_transfer_cm3 = float(
        full_physical[
            "oil_transfer_from_lower_to_upper_cm3"
        ]
    )

    full_physical_reservoir_remaining_cm3 = float(
        full_physical[
            "lower_reservoir_remaining_cm3"
        ]
    )

    checks = pd.DataFrame([
        {
            "check": "BARREL_ID_64_MM",
            "value": barrel_ID_mm,
            "criterion": (
                f"|value-{EXPECTED_BARREL_ID_MM}| <= "
                f"{GEOMETRY_TOL_MM} mm"
            ),
            "status": (
                "PASS"
                if geometry_checks[
                    "barrel_ID"
                ]
                else "FAIL"
            ),
        },
        {
            "check": "BARREL_OD_74_MM",
            "value": barrel_OD_mm,
            "criterion": (
                f"|value-{EXPECTED_BARREL_OD_MM}| <= "
                f"{GEOMETRY_TOL_MM} mm"
            ),
            "status": (
                "PASS"
                if geometry_checks[
                    "barrel_OD"
                ]
                else "FAIL"
            ),
        },
        {
            "check": "PIN_PROFILE_REPRODUCTION",
            "value": max_profile_error_mm,
            "criterion": (
                f"max error <= {PROFILE_TOL_MM} mm"
            ),
            "status": (
                "PASS"
                if max_profile_error_mm
                <= PROFILE_TOL_MM
                else "FAIL"
            ),
        },
        {
            "check": "FIXED_CAVITY_CONTINUITY",
            "value": max_cavity_residual,
            "criterion": (
                f"|residual| <= {VOLUME_TOL_CM3} cm^3"
            ),
            "status": (
                "PASS"
                if max_cavity_residual
                <= VOLUME_TOL_CM3
                else "FAIL"
            ),
        },
        {
            "check": "SWEPT_VOLUME_IDENTITY",
            "value": max_identity_residual,
            "criterion": (
                f"|swept-transfer-dVpin| <= "
                f"{VOLUME_TOL_CM3} cm^3"
            ),
            "status": (
                "PASS"
                if max_identity_residual
                <= VOLUME_TOL_CM3
                else "FAIL"
            ),
        },
        {
            "check": "UPPER_OIL_VOLUME_POSITIVE",
            "value": min_upper_oil,
            "criterion": "minimum >= 0 cm^3",
            "status": (
                "PASS"
                if min_upper_oil >= 0.0
                else "FAIL"
            ),
        },
        {
            "check": "LOWER_RESERVOIR_REMAINING_POSITIVE",
            "value": min_reservoir_remaining,
            "criterion": "minimum >= 0 cm^3",
            "status": (
                "PASS"
                if min_reservoir_remaining
                >= 0.0
                else "FAIL"
            ),
        },
        {
            "check": "CLOSURE_AXIAL_RESERVE_OVER_E2_ENVELOPE",
            "value": axial_reserve_over_conservative_mm,
            "criterion": ">= 0 mm",
            "status": (
                "PASS"
                if axial_reserve_over_conservative_mm
                >= 0.0
                else "FAIL"
            ),
        },
        {
            "check": "CLOSURE_6MM_LIMIT_AND_ULTIMATE",
            "value": t_grid_pass_mm,
            "criterion": "first 0.5-mm grid PASS <= 6.0 mm",
            "status": (
                "PASS"
                if t_grid_pass_mm
                <= 6.0 + 1e-12
                else "REVIEW"
            ),
        },
    ])

    checks.to_csv(
        OUTPUT_CHECKS_CSV,
        index=False,
    )

    interface = pd.DataFrame([
        {
            "quantity": "fixed_orifice_plane_above_U",
            "value": orifice_plane_mm,
            "units": "mm",
            "classification": "E2_WORKING_GEOMETRY",
        },
        {
            "quantity": "continuity_based_pressure_closure_inner_face_above_U",
            "value": closure_inner_face_mm,
            "units": "mm",
            "classification": (
                "E2_CONTINUITY_DERIVED_WORKING_CLOSURE"
            ),
        },
        {
            "quantity": "closure_theoretical_structural_minimum_thickness",
            "value": t_theoretical_mm,
            "units": "mm",
            "classification": (
                "PLATE_SCREEN_MINIMUM_NOT_FINAL_CAD"
            ),
        },
        {
            "quantity": "closure_first_0p5mm_grid_pass_thickness",
            "value": t_grid_pass_mm,
            "units": "mm",
            "classification": (
                "PRELIMINARY_STRUCTURAL_SCREEN"
            ),
        },
        {
            "quantity": "theoretical_minimum_outer_face_above_U",
            "value": structural_outer_face_theoretical_mm,
            "units": "mm",
            "classification": (
                "MINIMUM_BEFORE_SEALS_RETAINER_PORTS"
            ),
        },
        {
            "quantity": "six_mm_screen_outer_face_above_U",
            "value": structural_outer_face_grid_mm,
            "units": "mm",
            "classification": (
                "PRELIMINARY_E2_TO_E3_INTERFACE"
            ),
        },
        {
            "quantity": "E3_architecture_rule",
            "value": (
                "Place trunnion / airframe attachment load path in solid "
                "head at or above the final pressure-closure outer face; do "
                "not pass the attachment through the live pressure cavity "
                "unless a pressure-penetrating boss is deliberately designed."
            ),
            "units": "-",
            "classification": "ARCHITECTURE_RULE",
        },
    ])

    interface.to_csv(
        OUTPUT_INTERFACE_CSV,
        index=False,
    )

    # -------------------------------------------------------------------------
    # Console report
    # -------------------------------------------------------------------------

    print("\nSOURCE / GEOMETRY CONNECTION")
    print("-" * 122)
    print(
        f"Architecture inputs:           {ARCH_CSV}"
    )
    print(
        f"Stroke states:                 {STATES_CSV}"
    )
    print(
        f"Metering candidate:            {METERING_CANDIDATE_CSV}"
    )
    print(
        f"Pin profile:                   {PIN_PROFILE_CSV}"
    )
    print(
        f"Phase 1 source:                {PHASE1_SOURCE}"
    )
    print(
        f"Barrel:                        "
        f"{barrel_ID_mm:.3f} mm ID / "
        f"{barrel_OD_mm:.3f} mm OD"
    )
    print(
        f"Piston:                        {piston_OD_mm:.3f} mm OD"
    )

    print("\nMATERIAL SOURCE HYGIENE")
    print("-" * 122)
    print(
        f"7075-T6 E:                     {E_7075_GPA:.3f} GPa"
    )
    print(
        f"7075-T6 Poisson ratio used:    {NU_7075:.3f}"
    )
    print(
        "Disposition:                   use the project 7075-T6 material "
        "baseline for the closure plate; do not inherit a generic nu from "
        "the earlier barrel-sizing Python source."
    )

    print("\nMETERING-PIN PROFILE VERIFICATION")
    print("-" * 122)
    print(
        f"Fixed bore:                    {fixed_bore_mm:.3f} mm"
    )
    print(
        f"Equivalent orifice:            "
        f"{d_eq_start_mm:.4f} -> {d_eq_end_mm:.4f} mm"
    )
    print(
        f"Metering design stroke:        {x_design_mm:.3f} mm"
    )
    print(
        f"Tip projection at extension:   {tip_projection_mm:.3f} mm"
    )
    print(
        f"Max profile reproduction err.: {max_profile_error_mm:.6f} mm"
    )
    print(
        f"Pin volume at extension:       {V_pin0_cm3:.3f} cm^3"
    )
    print(
        f"Pin volume at physical stroke: {full_physical_pin_cm3:.3f} cm^3"
    )
    print(
        f"Old conservative pin reserve:  {old_conservative_pin_volume_cm3:.3f} cm^3"
    )

    print("\nFIXED UPPER-CAVITY DEFINITION — FULL EXTENSION")
    print("-" * 122)
    print(
        f"Initial gas volume:             {V_gas0_cm3:.3f} cm^3"
    )
    print(
        f"Initial upper-oil head:         {initial_oil_head_mm:.3f} mm"
    )
    print(
        f"Initial upper-oil volume:       {V_upper_oil0_cm3:.3f} cm^3"
    )
    print(
        f"Initial pin displacement:       {V_pin0_cm3:.3f} cm^3"
    )
    print(
        f"Required fixed cavity volume:   {V_fixed_cavity_cm3:.3f} cm^3"
    )
    print(
        f"Required cavity height:         {H_fixed_cavity_mm:.3f} mm"
    )
    print(
        f"Fixed orifice plane:            {orifice_plane_mm:.3f} mm above U"
    )
    print(
        f"Continuity closure inner face:  {closure_inner_face_mm:.3f} mm above U"
    )

    print("\nFLUID-CONTINUITY STATES")
    print("-" * 122)

    display = continuity[
        [
            "state",
            "compression_mm",
            "gas_volume_cm3",
            "pin_volume_above_orifice_cm3",
            "upper_oil_volume_cm3",
            "oil_transfer_from_lower_to_upper_cm3",
            "lower_reservoir_remaining_cm3",
            "gas_pressure_abs_MPa",
        ]
    ].copy()

    print(
        display.to_string(
            index=False,
            formatters={
                "compression_mm": (
                    lambda x: f"{x:.3f}"
                ),
                "gas_volume_cm3": (
                    lambda x: f"{x:.3f}"
                ),
                "pin_volume_above_orifice_cm3": (
                    lambda x: f"{x:.3f}"
                ),
                "upper_oil_volume_cm3": (
                    lambda x: f"{x:.3f}"
                ),
                "oil_transfer_from_lower_to_upper_cm3": (
                    lambda x: f"{x:.3f}"
                ),
                "lower_reservoir_remaining_cm3": (
                    lambda x: f"{x:.3f}"
                ),
                "gas_pressure_abs_MPa": (
                    lambda x: f"{x:.3f}"
                ),
            },
        )
    )

    print("\nPHYSICAL-STROKE CONTINUITY RESULT")
    print("-" * 122)
    print(
        f"Oil transferred to upper:      {full_physical_oil_transfer_cm3:.3f} cm^3"
    )
    print(
        f"Lower reservoir remaining:     {full_physical_reservoir_remaining_cm3:.3f} cm^3"
    )
    print(
        f"Minimum reservoir in states:   {min_reservoir_remaining:.3f} cm^3"
    )
    print(
        f"Max cavity residual:            {max_cavity_residual:.6e} cm^3"
    )
    print(
        f"Max swept-volume identity err.: {max_identity_residual:.6e} cm^3"
    )

    print("\nCLOSURE LOCATION RECONCILIATION")
    print("-" * 122)
    print(
        f"Old conservative working face: {old_working_closure_mm:.3f} mm above U"
    )
    print(
        f"Continuity-derived inner face:  {closure_inner_face_mm:.3f} mm above U"
    )
    print(
        f"Change vs old working face:     {closure_shift_vs_old_mm:+.3f} mm"
    )
    print(
        f"Old E2 conservative envelope:   {conservative_e2_envelope_mm:.3f} mm above U"
    )
    print(
        f"Reserve over old envelope:      {axial_reserve_over_conservative_mm:+.3f} mm"
    )

    print("\nUPDATED 7075-T6 PRESSURE-CLOSURE SCREEN")
    print("-" * 122)
    print(
        f"Full-stroke delta pressure:     {p_limit_MPa:.3f} MPa"
    )
    print(
        f"Ultimate delta pressure:        {p_ultimate_MPa:.3f} MPa"
    )
    print(
        f"Poisson ratio:                  {NU_7075:.3f}"
    )
    print(
        f"Required thickness — limit:     {t_req_limit_mm:.3f} mm"
    )
    print(
        f"Required thickness — ultimate:  {t_req_ultimate_mm:.3f} mm"
    )
    print(
        f"Governing theoretical minimum:  {t_theoretical_mm:.3f} mm"
    )
    print(
        f"First 0.5-mm grid PASS:         {t_grid_pass_mm:.3f} mm"
    )

    print("\nPRELIMINARY E2 -> E3 INTERFACE")
    print("-" * 122)
    print(
        f"Closure inner face:             {closure_inner_face_mm:.3f} mm above U"
    )
    print(
        f"Theoretical min outer face:     {structural_outer_face_theoretical_mm:.3f} mm above U"
    )
    print(
        f"6-mm screen outer face:         {structural_outer_face_grid_mm:.3f} mm above U"
    )
    print(
        "E3 rule:                        put the trunnion / airframe attachment "
        "in solid head at or above the FINAL closure outer face."
    )

    print("\nCHECK SUMMARY")
    print("-" * 122)
    print(
        checks.to_string(
            index=False,
        )
    )

    if not all(
        checks["status"].isin([
            "PASS",
        ])
    ):
        print(
            "\nDisposition: REVIEW — at least one E2-C check is not PASS."
        )
    else:
        print(
            "\nDisposition: PASS — the selected E2 fluid topology is volume-consistent "
            "through the physical stroke and the preliminary 6 mm closure screen "
            "passes limit and ultimate pressure loading."
        )

    print("\nLOCK BOUNDARY")
    print("-" * 122)
    print(
        "The continuity-based closure station supersedes the earlier conservative "
        "502 mm working face for this 14 mm candidate. The 6 mm closure remains "
        "a PRELIMINARY structural screen, not final detailed CAD thickness. "
        "Seal/retainer/port geometry and local stress concentrations remain to "
        "be developed with the upper solid head / E3 attachment."
    )

    print("\nOUTPUT FILES")
    print("-" * 122)
    print(
        f"Fluid continuity states:       {OUTPUT_CONTINUITY_CSV}"
    )
    print(
        f"Continuity checks:             {OUTPUT_CHECKS_CSV}"
    )
    print(
        f"Closure structural screen:     {OUTPUT_CLOSURE_CSV}"
    )
    print(
        f"E3 interface:                  {OUTPUT_INTERFACE_CSV}"
    )

    print("=" * 122)


if __name__ == "__main__":
    main()
