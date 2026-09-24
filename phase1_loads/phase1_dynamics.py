"""
Landing_Gear_Design_Project
Phase 1B–1E — Frozen 2-DOF Oleo / Tire Landing Dynamics

Purpose
-------
Document and reproduce the final validated Phase 1 dynamic model.

This script is a BACKFILL of the frozen Phase 1 model. It must not be used to
silently retune Phase 1 parameters.

Model
-----
Downward-positive 2-DOF vertical model for ONE main gear:

    m_s z_s_ddot = m_s g - L - F_o
    m_u z_u_ddot = m_u g + F_o - F_t

where

    x      = z_s - z_u        oleo compression
    x_dot  = v_s - v_u

and

    F_o = F_g + F_h

The tire is unilateral:

    F_t = k_t * max(delta_t, 0)^p

with delta_t = z_u after first ground contact.

The landing starts with the oleo on its extension stop (x = 0). The sprung and
unsprung masses move together until the extension-stop reaction falls to zero.
The release point is solved analytically from force compatibility and energy.

Validated frozen outputs include:
- Nominal V0.4:
    peak oleo stroke      206.338 mm
    peak tire deflection   44.961 mm
    peak ground reaction   23.800 kN
    peak internal strut    23.038 kN
- V0.5b zero-lift virtual-stroke diagnostic:
    demanded stroke       240.779 mm
    peak tire deflection   52.399 mm
    peak ground reaction   28.284 kN
    peak internal strut    27.781 kN
"""

import csv
import math
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp


# =============================================================================
# 1. FROZEN CONSTANTS
# =============================================================================

g = 9.80665                         # [m/s^2]

# One-main equivalent vertical mass model
m_eq = 850.0                        # [kg]
m_u_nominal = 30.0                  # [kg]
m_s_nominal = m_eq - m_u_nominal    # [kg]

# Design touchdown sink speed
Vd = 3.048                          # [m/s] = 10 ft/s

# Retained lift baseline
lift_fraction_nominal = 2.0 / 3.0   # L / (m_eq*g)

# Frozen structural/load reference
F_limit = 25.02e3                   # [N]
F_ultimate = 37.53e3                # [N]

# Oleo stroke
stroke_design = 0.205               # [m] target/design stroke
stroke_physical = 0.230             # [m] real physical stroke
stroke_virtual = 0.300              # [m] V0.5b diagnostic only

# Piston / gas spring
D_piston = 0.058                    # [m]
A_piston = math.pi * D_piston**2 / 4.0

L_gas_0 = 0.350                     # [m]
n_gas = 1.30                        # polytropic exponent

P_atm = 101_325.0                   # [Pa]
P0_abs = 2.336e6                    # [Pa] absolute
P0_gauge = P0_abs - P_atm           # [Pa]

# Static oleo sag used in the original gas-precharge sizing
x_static = 0.050                    # [m]

# Hydraulic fluid / metering
rho_oil = 850.0                     # [kg/m^3]
C_d = 0.70

d_orifice_start = 0.010301          # [m]
d_orifice_end = 0.009742            # [m]
x_metering = stroke_design          # [m]

# Tire calibration
delta_tire_design = 0.047           # [m]
eta_tire = 0.47

# From:
#   E_t = F_max*delta_max/(p+1)
# and
#   eta_t = E_t/(F_max*delta_max)
#
# therefore:
#   p = 1/eta_t - 1
p_tire = 1.0 / eta_tire - 1.0

# Calibrate F_t = k_t delta^p at the frozen reference:
# F_t = 25.02 kN at delta = 47 mm.
k_tire = F_limit / delta_tire_design**p_tire


# =============================================================================
# 2. CONSTITUTIVE MODELS
# =============================================================================

def gas_force(x):
    """
    Gas-spring force, positive in the compression-resisting direction.

    F_g = A_p * [ P0_abs * (L0/(L0-x))^n - P_atm ]

    x = 0 is full oleo extension.
    """

    if x >= L_gas_0:
        raise ValueError(
            "Oleo compression reached the initial gas-column length."
        )

    pressure_abs = P0_abs * (
        L_gas_0 / (L_gas_0 - x)
    )**n_gas

    return A_piston * (pressure_abs - P_atm)


def orifice_diameter(x):
    """
    Frozen V0.3 smooth linear metering schedule.

    10.301 mm at x = 0
      ->
     9.742 mm at x = 205 mm

    The schedule is clamped at its endpoint beyond the design stroke.
    """

    x_clamped = min(
        max(x, 0.0),
        x_metering
    )

    fraction = x_clamped / x_metering

    return (
        d_orifice_start
        + (d_orifice_end - d_orifice_start) * fraction
    )


def hydraulic_coefficient(x):
    """
    Quadratic hydraulic damping coefficient:

        C_h = rho * A_p^3 / (2 C_d^2 A_o^2)
    """

    d_o = orifice_diameter(x)
    A_o = math.pi * d_o**2 / 4.0

    return (
        rho_oil * A_piston**3
        / (2.0 * C_d**2 * A_o**2)
    )


def hydraulic_force(x, x_dot):
    """
    Signed hydraulic force:

        F_h = C_h(x) * x_dot * |x_dot|

    Positive x_dot = compression.
    Negative x_dot = extension.

    The sign therefore reverses automatically with oleo motion.
    """

    return (
        hydraulic_coefficient(x)
        * x_dot
        * abs(x_dot)
    )


def oleo_force(x, x_dot):
    """
    Total internal oleo force:

        F_o = F_g + F_h
    """

    return (
        gas_force(x)
        + hydraulic_force(x, x_dot)
    )


def tire_force(delta):
    """
    Unilateral nonlinear tire law:

        F_t = k_t * delta^p,   delta > 0
        F_t = 0,               delta <= 0
    """

    if delta <= 0.0:
        return 0.0

    return k_tire * delta**p_tire


def tire_energy(delta):
    """
    Stored tire energy:

        U_t = integral(F_t d delta)
            = k_t * delta^(p+1)/(p+1)
    """

    if delta <= 0.0:
        return 0.0

    return (
        k_tire
        * delta**(p_tire + 1.0)
        / (p_tire + 1.0)
    )


# =============================================================================
# 3. EXTENSION-STOP RELEASE
# =============================================================================

def extension_stop_release(
    sink_speed,
    lift_fraction,
    m_u
):
    """
    Determine when the oleo leaves its full-extension stop.

    Before release:
        x = 0
        z_s = z_u = delta_t
        v_s = v_u

    The two masses therefore translate together.

    Release occurs when the stop reaction becomes zero.
    Equating the unconstrained sprung- and unsprung-mass accelerations gives:

        F_t,release
            = F_g(0)
            + m_u * [L + F_g(0)] / m_s

    The corresponding tire deflection follows from the nonlinear tire law.

    The common velocity at release comes from energy conservation during the
    extension-stop phase:

        1/2 m_eq v_r^2
          = 1/2 m_eq V_sink^2
            + (m_eq*g - L) delta_r
            - U_t(delta_r)
    """

    m_s = m_eq - m_u

    if m_s <= 0.0:
        raise ValueError("Sprung mass must be positive.")

    lift = (
        lift_fraction
        * m_eq
        * g
    )

    F_g0 = gas_force(0.0)

    F_t_release = (
        F_g0
        + m_u * (lift + F_g0) / m_s
    )

    delta_release = (
        F_t_release / k_tire
    )**(1.0 / p_tire)

    U_t_release = tire_energy(
        delta_release
    )

    v_release_sq = (
        sink_speed**2
        + 2.0
        * (
            (m_eq * g - lift)
            * delta_release
            - U_t_release
        )
        / m_eq
    )

    if v_release_sq < 0.0:
        raise ValueError(
            "Computed negative release-velocity squared."
        )

    v_release = math.sqrt(
        v_release_sq
    )

    return {
        "m_s": m_s,
        "m_u": m_u,
        "lift_N": lift,
        "F_t_release_N": F_t_release,
        "delta_release_m": delta_release,
        "v_release_mps": v_release,
    }


# =============================================================================
# 4. TWO-DEGREE-OF-FREEDOM LANDING MODEL
# =============================================================================

def simulate_landing(
    sink_speed=Vd,
    lift_fraction=lift_fraction_nominal,
    m_u=m_u_nominal,
    stroke_limit=stroke_physical,
    max_time=1.0,
):
    """
    Run one landing case.

    Coordinates are downward-positive.

    States:
        z_s : sprung-mass downward displacement [m]
        z_u : unsprung-mass / tire deflection coordinate [m]
        v_s : sprung-mass downward velocity [m/s]
        v_u : unsprung-mass downward velocity [m/s]

    Oleo:
        x     = z_s - z_u
        x_dot = v_s - v_u

    Equations:
        m_s z_s_ddot = m_s g - L - F_o

        m_u z_u_ddot = m_u g + F_o - F_t

    The integration terminates at whichever happens first:
        1) first maximum oleo compression (x_dot crosses + -> -), or
        2) the requested stroke limit.
    """

    release = extension_stop_release(
        sink_speed=sink_speed,
        lift_fraction=lift_fraction,
        m_u=m_u,
    )

    m_s = release["m_s"]
    lift = release["lift_N"]

    delta_release = release[
        "delta_release_m"
    ]

    v_release = release[
        "v_release_mps"
    ]

    # At release the two masses are still coincident in displacement
    # and velocity, so x = 0 and x_dot = 0.
    y0 = np.array([
        delta_release,   # z_s
        delta_release,   # z_u
        v_release,       # v_s
        v_release,       # v_u
    ], dtype=float)

    def rhs(t, y):

        z_s, z_u, v_s, v_u = y

        x = z_s - z_u
        x_dot = v_s - v_u

        F_o = oleo_force(
            x,
            x_dot
        )

        F_t = tire_force(
            z_u
        )

        a_s = (
            m_s * g
            - lift
            - F_o
        ) / m_s

        a_u = (
            m_u * g
            + F_o
            - F_t
        ) / m_u

        return [
            v_s,
            v_u,
            a_s,
            a_u,
        ]

    def first_maximum_event(t, y):
        # x_dot = v_s - v_u
        return y[2] - y[3]

    first_maximum_event.direction = -1
    first_maximum_event.terminal = True

    def stroke_limit_event(t, y):
        x = y[0] - y[1]
        return stroke_limit - x

    stroke_limit_event.direction = -1
    stroke_limit_event.terminal = True

    solution = solve_ivp(
        rhs,
        t_span=(0.0, max_time),
        y0=y0,
        events=[
            first_maximum_event,
            stroke_limit_event,
        ],
        rtol=1.0e-10,
        atol=1.0e-12,
        max_step=1.0e-4,
    )

    z_s = solution.y[0]
    z_u = solution.y[1]
    v_s = solution.y[2]
    v_u = solution.y[3]

    x = z_s - z_u
    x_dot = v_s - v_u

    F_t = np.array([
        tire_force(delta)
        for delta in z_u
    ])

    F_g = np.array([
        gas_force(x_i)
        for x_i in x
    ])

    F_h = np.array([
        hydraulic_force(x_i, v_i)
        for x_i, v_i in zip(
            x,
            x_dot
        )
    ])

    F_o = F_g + F_h

    hit_peak = (
        len(solution.t_events[0]) > 0
    )

    hit_stroke_limit = (
        len(solution.t_events[1]) > 0
    )

    termination = (
        "FIRST_MAXIMUM"
        if hit_peak
        else "STROKE_LIMIT"
        if hit_stroke_limit
        else "TIME_LIMIT"
    )

    result = {
        "sink_speed_mps": sink_speed,
        "lift_fraction": lift_fraction,
        "m_u_kg": m_u,
        "m_s_kg": m_s,
        "release_delta_m": release[
            "delta_release_m"
        ],
        "release_velocity_mps": release[
            "v_release_mps"
        ],
        "termination": termination,
        "peak_stroke_m": float(
            np.max(x)
        ),
        "peak_tire_deflection_m": float(
            np.max(z_u)
        ),
        "peak_ground_reaction_N": float(
            np.max(F_t)
        ),
        "peak_strut_force_N": float(
            np.max(F_o)
        ),
        "peak_gas_force_N": float(
            np.max(F_g)
        ),
        "peak_hydraulic_force_N": float(
            np.max(F_h)
        ),
        "solution": solution,
        "x": x,
        "x_dot": x_dot,
        "F_t": F_t,
        "F_g": F_g,
        "F_h": F_h,
        "F_o": F_o,
    }

    return result


# =============================================================================
# 5. ENERGY AUDIT
# =============================================================================

def gas_work(x):
    """
    Exact numerical integral of gas force from x=0 to the supplied x.

    We use a dense deterministic trapezoidal grid here because this is a
    documentation/audit calculation, not the dynamic integrator itself.
    """

    if x <= 0.0:
        return 0.0

    grid = np.linspace(
        0.0,
        x,
        20_001
    )

    force = np.array([
        gas_force(x_i)
        for x_i in grid
    ])

    return float(
        np.trapezoid(
            force,
            grid
        )
    )


def energy_audit(result):
    """
    Energy balance from first tire contact to the simulation endpoint.

    Input energy/work:
        initial kinetic energy
        + gravity work

    Removed/stored:
        lift work
        final kinetic energy
        gas work
        tire strain energy
        hydraulic dissipation

    Residual should be numerically ~0.
    """

    solution = result["solution"]

    m_u = result["m_u_kg"]
    m_s = result["m_s_kg"]

    lift = (
        result["lift_fraction"]
        * m_eq
        * g
    )

    z_s_final = solution.y[0, -1]
    z_u_final = solution.y[1, -1]

    v_s_final = solution.y[2, -1]
    v_u_final = solution.y[3, -1]

    x_final = (
        z_s_final
        - z_u_final
    )

    KE_initial = (
        0.5
        * m_eq
        * result["sink_speed_mps"]**2
    )

    KE_final = (
        0.5 * m_s * v_s_final**2
        + 0.5 * m_u * v_u_final**2
    )

    gravity_work = (
        m_s * g * z_s_final
        + m_u * g * z_u_final
    )

    lift_work = (
        lift
        * z_s_final
    )

    gas_energy = gas_work(
        x_final
    )

    tire_energy_final = tire_energy(
        z_u_final
    )

    # Hydraulic dissipated energy:
    #
    # power = F_h * x_dot
    #
    # Since F_h and x_dot have the same sign in the signed constitutive law,
    # the product is positive for both compression and rebound damping.
    hydraulic_power = (
        result["F_h"]
        * result["x_dot"]
    )

    hydraulic_energy = float(
        np.trapezoid(
            hydraulic_power,
            solution.t
        )
    )

    residual = (
        KE_initial
        + gravity_work
        - lift_work
        - KE_final
        - gas_energy
        - tire_energy_final
        - hydraulic_energy
    )

    return {
        "KE_initial_J": KE_initial,
        "KE_final_J": KE_final,
        "gravity_work_J": gravity_work,
        "lift_work_J": lift_work,
        "gas_work_J": gas_energy,
        "tire_energy_J": tire_energy_final,
        "hydraulic_energy_J": hydraulic_energy,
        "residual_J": residual,
    }


# =============================================================================
# 6. PASS / FLAG LOGIC FOR V0.5 SCREENING
# =============================================================================

def screening_status(result):
    """
    Frozen Phase 1 screening logic.

    FLAG if:
    - physical stroke is exhausted, OR
    - peak ground reaction exceeds the 25.02 kN limit reference, OR
    - peak internal strut force exceeds the 25.02 kN limit reference.

    The 205 mm design stroke is a target, not a hard bottoming limit.
    """

    if result["termination"] == "STROKE_LIMIT":
        return "FLAG"

    if (
        result["peak_ground_reaction_N"]
        > F_limit
    ):
        return "FLAG"

    if (
        result["peak_strut_force_N"]
        > F_limit
    ):
        return "FLAG"

    return "PASS"


# =============================================================================
# 7. V0.4 NOMINAL VALIDATION
# =============================================================================

nominal = simulate_landing()

nominal_energy = energy_audit(
    nominal
)


# =============================================================================
# 8. V0.5 ROBUSTNESS SWEEPS
# =============================================================================

unsprung_mass_cases = []

for m_u in (
    20.0,
    30.0,
    40.0,
):
    result = simulate_landing(
        m_u=m_u
    )

    unsprung_mass_cases.append(
        (
            m_u,
            result,
            screening_status(result),
        )
    )


sink_speed_cases = []

for multiplier in (
    0.90,
    1.00,
    1.10,
):
    result = simulate_landing(
        sink_speed=multiplier * Vd
    )

    sink_speed_cases.append(
        (
            multiplier,
            result,
            screening_status(result),
        )
    )


lift_cases = []

for lift_fraction in (
    0.0,
    1.0 / 3.0,
    2.0 / 3.0,
):
    result = simulate_landing(
        lift_fraction=lift_fraction
    )

    lift_cases.append(
        (
            lift_fraction,
            result,
            screening_status(result),
        )
    )


# =============================================================================
# 9. V0.5b ZERO-LIFT VIRTUAL-STROKE DIAGNOSTIC
# =============================================================================

zero_lift_virtual = simulate_landing(
    sink_speed=Vd,
    lift_fraction=0.0,
    m_u=m_u_nominal,
    stroke_limit=stroke_virtual,
)

zero_lift_virtual_energy = energy_audit(
    zero_lift_virtual
)


# =============================================================================
# 10. REGRESSION CHECKS
# =============================================================================

def assert_close(
    name,
    calculated,
    reference,
    tolerance,
):
    error = abs(
        calculated - reference
    )

    assert error <= tolerance, (
        f"{name} regression failed: "
        f"calculated={calculated}, "
        f"reference={reference}, "
        f"error={error}"
    )


# Nominal V0.4
assert_close(
    "Nominal peak stroke [m]",
    nominal["peak_stroke_m"],
    0.206338,
    2.0e-6,
)

assert_close(
    "Nominal peak tire deflection [m]",
    nominal["peak_tire_deflection_m"],
    0.044961,
    2.0e-6,
)

assert_close(
    "Nominal peak ground reaction [N]",
    nominal["peak_ground_reaction_N"],
    23.800e3,
    5.0,
)

assert_close(
    "Nominal peak strut force [N]",
    nominal["peak_strut_force_N"],
    23.038e3,
    5.0,
)

assert_close(
    "Nominal extension-stop release [m]",
    nominal["release_delta_m"],
    0.013880,
    2.0e-6,
)

# V0.5b
assert_close(
    "Zero-lift virtual peak stroke [m]",
    zero_lift_virtual["peak_stroke_m"],
    0.240779,
    2.0e-6,
)

assert_close(
    "Zero-lift virtual peak tire deflection [m]",
    zero_lift_virtual[
        "peak_tire_deflection_m"
    ],
    0.052399,
    2.0e-6,
)

assert_close(
    "Zero-lift virtual peak ground reaction [N]",
    zero_lift_virtual[
        "peak_ground_reaction_N"
    ],
    28.284e3,
    5.0,
)

assert_close(
    "Zero-lift virtual peak strut force [N]",
    zero_lift_virtual[
        "peak_strut_force_N"
    ],
    27.781e3,
    5.0,
)


# =============================================================================
# 11. CSV OUTPUT
# =============================================================================

output_dir = Path(
    __file__
).resolve().parent


def write_robustness_csv():

    path = (
        output_dir
        / "phase1_dynamic_robustness.csv"
    )

    rows = []

    for parameter, result, status in unsprung_mass_cases:
        rows.append([
            "Unsprung mass sweep",
            f"{parameter:.3f} kg",
            result["peak_stroke_m"] * 1000.0,
            result["peak_tire_deflection_m"] * 1000.0,
            result["peak_ground_reaction_N"] / 1000.0,
            result["peak_strut_force_N"] / 1000.0,
            result["termination"],
            status,
        ])

    for parameter, result, status in sink_speed_cases:
        rows.append([
            "Sink-speed sweep",
            f"{parameter:.2f} Vd",
            result["peak_stroke_m"] * 1000.0,
            result["peak_tire_deflection_m"] * 1000.0,
            result["peak_ground_reaction_N"] / 1000.0,
            result["peak_strut_force_N"] / 1000.0,
            result["termination"],
            status,
        ])

    for parameter, result, status in lift_cases:
        rows.append([
            "Retained-lift sweep",
            f"L/W = {parameter:.6f}",
            result["peak_stroke_m"] * 1000.0,
            result["peak_tire_deflection_m"] * 1000.0,
            result["peak_ground_reaction_N"] / 1000.0,
            result["peak_strut_force_N"] / 1000.0,
            result["termination"],
            status,
        ])

    rows.append([
        "V0.5b virtual diagnostic",
        "Vd, L/W = 0",
        zero_lift_virtual[
            "peak_stroke_m"
        ] * 1000.0,
        zero_lift_virtual[
            "peak_tire_deflection_m"
        ] * 1000.0,
        zero_lift_virtual[
            "peak_ground_reaction_N"
        ] / 1000.0,
        zero_lift_virtual[
            "peak_strut_force_N"
        ] / 1000.0,
        zero_lift_virtual[
            "termination"
        ],
        "DIAGNOSTIC",
    ])

    with path.open(
        "w",
        newline=""
    ) as file:

        writer = csv.writer(file)

        writer.writerow([
            "Study",
            "Case",
            "Peak Oleo Stroke (mm)",
            "Peak Tire Deflection (mm)",
            "Peak Ground Reaction (kN)",
            "Peak Strut Force (kN)",
            "Termination",
            "Status",
        ])

        writer.writerows(rows)

    return path


csv_path = write_robustness_csv()


# =============================================================================
# 12. CONSOLE REPORT
# =============================================================================

def print_case(
    label,
    result,
    status=None,
):

    status_text = (
        ""
        if status is None
        else f"  {status}"
    )

    print(
        f"{label:<18}"
        f"{result['peak_stroke_m']*1000:>10.2f}"
        f"{result['peak_tire_deflection_m']*1000:>12.2f}"
        f"{result['peak_ground_reaction_N']/1000:>12.2f}"
        f"{result['peak_strut_force_N']/1000:>12.2f}"
        f"{status_text}"
    )


print()
print("=" * 82)
print(
    " PHASE 1B–1E — FROZEN 2-DOF "
    "OLEO / TIRE DYNAMIC MODEL"
)
print("=" * 82)

print()
print("--- MODEL CONSTANTS ---")
print(
    f"Equivalent mass:                  "
    f"{m_eq:.1f} kg"
)
print(
    f"Nominal sprung / unsprung:        "
    f"{m_s_nominal:.1f} / "
    f"{m_u_nominal:.1f} kg"
)
print(
    f"Design sink speed:                "
    f"{Vd:.4f} m/s"
)
print(
    f"Nominal retained lift:            "
    f"L/W = {lift_fraction_nominal:.6f}"
)
print(
    f"Piston diameter:                  "
    f"{D_piston*1000:.2f} mm"
)
print(
    f"Piston area:                      "
    f"{A_piston:.8f} m^2"
)
print(
    f"Initial gas length:               "
    f"{L_gas_0*1000:.1f} mm"
)
print(
    f"Gas exponent:                     "
    f"{n_gas:.3f}"
)
print(
    f"Initial gas pressure absolute:    "
    f"{P0_abs/1e6:.3f} MPa"
)
print(
    f"Initial gas pressure gauge:       "
    f"{P0_gauge/1e6:.3f} MPa"
)
print(
    f"Design / physical stroke:         "
    f"{stroke_design*1000:.1f} / "
    f"{stroke_physical*1000:.1f} mm"
)
print(
    f"Orifice schedule:                 "
    f"{d_orifice_start*1000:.3f} -> "
    f"{d_orifice_end*1000:.3f} mm"
)
print(
    f"Tire exponent p:                  "
    f"{p_tire:.6f}"
)
print(
    f"Tire stiffness k:                 "
    f"{k_tire:.2f} N/m^p"
)

print()
print("--- NOMINAL V0.4 VALIDATION ---")
print(
    f"Extension-stop release:           "
    f"{nominal['release_delta_m']*1000:.3f} mm"
)
print(
    f"Release velocity:                 "
    f"{nominal['release_velocity_mps']:.6f} m/s"
)
print(
    f"Peak oleo stroke:                 "
    f"{nominal['peak_stroke_m']*1000:.3f} mm"
)
print(
    f"Peak tire deflection:             "
    f"{nominal['peak_tire_deflection_m']*1000:.3f} mm"
)
print(
    f"Peak ground reaction:             "
    f"{nominal['peak_ground_reaction_N']/1000:.3f} kN"
)
print(
    f"Peak internal strut force:        "
    f"{nominal['peak_strut_force_N']/1000:.3f} kN"
)
print(
    f"Peak gas force:                   "
    f"{nominal['peak_gas_force_N']/1000:.3f} kN"
)
print(
    f"Peak hydraulic force:             "
    f"{nominal['peak_hydraulic_force_N']/1000:.3f} kN"
)
print(
    f"Gas work to first max:            "
    f"{nominal_energy['gas_work_J']/1000:.3f} kJ"
)
print(
    f"Hydraulic energy dissipated:      "
    f"{nominal_energy['hydraulic_energy_J']/1000:.3f} kJ"
)
print(
    f"Energy residual:                  "
    f"{nominal_energy['residual_J']:+.6f} J"
)
print(
    f"Termination:                      "
    f"{nominal['termination']}"
)

print()
print("--- V0.5 ROBUSTNESS MATRIX ---")
print(
    f"{'Case':<18}"
    f"{'Stroke mm':>10}"
    f"{'Tire mm':>12}"
    f"{'Ground kN':>12}"
    f"{'Strut kN':>12}"
    f"  Status"
)
print("-" * 78)

for m_u, result, status in unsprung_mass_cases:
    print_case(
        f"m_u={m_u:.0f} kg",
        result,
        status,
    )

for multiplier, result, status in sink_speed_cases:
    print_case(
        f"V={multiplier:.2f} Vd",
        result,
        status,
    )

for lift_fraction, result, status in lift_cases:
    print_case(
        f"L/W={lift_fraction:.3f}",
        result,
        status,
    )

print()
print("--- V0.5b ZERO-LIFT VIRTUAL-STROKE DIAGNOSTIC ---")
print(
    f"REAL physical oleo stroke:        "
    f"{stroke_physical*1000:.1f} mm"
)
print(
    f"Temporary virtual stroke limit:   "
    f"{stroke_virtual*1000:.1f} mm"
)
print(
    f"Nominal unsprung mass:            "
    f"{m_u_nominal:.1f} kg/main"
)
print(
    f"Retained lift:                    "
    f"L/W = 0"
)
print()
print(
    f"Peak demanded oleo stroke:        "
    f"{zero_lift_virtual['peak_stroke_m']*1000:.3f} mm"
)
print(
    f"Stroke beyond physical design:    "
    f"{(zero_lift_virtual['peak_stroke_m']-stroke_physical)*1000:+.3f} mm"
)
print(
    f"Peak tire deflection:             "
    f"{zero_lift_virtual['peak_tire_deflection_m']*1000:.3f} mm"
)
print(
    f"Peak ground reaction:             "
    f"{zero_lift_virtual['peak_ground_reaction_N']/1000:.3f} kN"
)
print(
    f"Peak internal strut force:        "
    f"{zero_lift_virtual['peak_strut_force_N']/1000:.3f} kN"
)
print(
    f"Peak gas force:                   "
    f"{zero_lift_virtual['peak_gas_force_N']/1000:.3f} kN"
)
print(
    f"Peak hydraulic force:             "
    f"{zero_lift_virtual['peak_hydraulic_force_N']/1000:.3f} kN"
)
print(
    f"Gas work:                         "
    f"{zero_lift_virtual_energy['gas_work_J']/1000:.3f} kJ"
)
print(
    f"Hydraulic energy dissipated:      "
    f"{zero_lift_virtual_energy['hydraulic_energy_J']/1000:.3f} kJ"
)
print(
    f"Energy residual:                  "
    f"{zero_lift_virtual_energy['residual_J']:+.6f} J"
)
print(
    f"First maximum termination:        "
    f"{zero_lift_virtual['termination']}"
)

print()
print("Regression checks:                PASS")
print(
    f"CSV written to:                   "
    f"{csv_path.name}"
)
print("=" * 82)
