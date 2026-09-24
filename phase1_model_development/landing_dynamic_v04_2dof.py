import numpy as np
import matplotlib.pyplot as plt

from scipy.integrate import solve_ivp, trapezoid


# ============================================================
# LANDING GEAR DESIGN PROJECT
# PHASE 1 — DYNAMIC LANDING MODEL V0.4
#
# 2-DOF vertical landing model
#
# Sprung mass
#     |
#   Oleo
#     |
# Unsprung mass
#     |
#   Tire
#     |
#   Runway
#
# Includes:
# - V0.3 nonlinear gas spring
# - V0.3 smooth hydraulic metering
# - explicit nonlinear tire
# - extension-stop touchdown phase
# - unsprung-mass sensitivity study
# ============================================================


# ============================================================
# 1. LOCKED AIRCRAFT / LC1 BASELINE
# ============================================================

g = 9.80665

m_aircraft = 1700.0

# Equivalent total mass assigned to one main gear
m_eq = m_aircraft / 2.0

V_sink = 3.048                   # m/s = 10 ft/s

lift_fraction = 2.0 / 3.0

F_limit = 25.02e3               # N per main
F_ultimate = 37.53e3            # N per main

x_hand = 0.205                  # m
x_available = 0.230             # m


# ============================================================
# 2. PROVISIONAL UNSPRUNG MASS
# ============================================================

# Nominal V0.4 assumption
m_unsprung_nominal = 30.0       # kg per main

# Sensitivity cases
unsprung_mass_cases = [
    20.0,
    30.0,
    40.0
]


# ============================================================
# 3. LOCKED OLEO GAS PARAMETERS — V0.3
# ============================================================

D_piston = 0.058

A_piston = (
    np.pi * D_piston**2 / 4.0
)

L_gas_0 = 0.350

P_atm = 101325.0

P_gas_0_abs = 2.336e6

n_poly = 1.30


# ============================================================
# 4. LOCKED SMOOTH HYDRAULIC METERING — V0.3
# ============================================================

rho_oil = 850.0

C_d = 0.70

d_orifice_start = 0.010301      # m

d_orifice_end = 0.009742        # m


def orifice_diameter(x):
    """
    Smooth linear equivalent-orifice schedule.
    """

    x_clamped = np.clip(
        x,
        0.0,
        x_hand
    )

    fraction = (
        x_clamped / x_hand
    )

    diameter = (
        d_orifice_start
        + (
            d_orifice_end
            - d_orifice_start
        )
        * fraction
    )

    return diameter


def orifice_area(x):

    d = orifice_diameter(x)

    return (
        np.pi
        * d**2
        / 4.0
    )


def hydraulic_coefficient(x):

    A_o = orifice_area(x)

    return (
        rho_oil
        * A_piston**3
        / (
            2.0
            * C_d**2
            * A_o**2
        )
    )


# ============================================================
# 5. GAS SPRING
# ============================================================

def gas_pressure(x):

    gas_length = (
        L_gas_0 - x
    )

    if gas_length <= 0.0:

        raise ValueError(
            "Gas column length became zero or negative."
        )

    return (
        P_gas_0_abs
        * (
            L_gas_0 / gas_length
        )**n_poly
    )


def gas_force(x):

    pressure_gauge = (
        gas_pressure(x)
        - P_atm
    )

    return (
        pressure_gauge
        * A_piston
    )


# Gas preload at full extension

F_gas_preload = gas_force(
    0.0
)


# ============================================================
# 6. HYDRAULIC FORCE
# ============================================================

def hydraulic_force(x, x_dot):

    C_h = hydraulic_coefficient(x)

    return (
        C_h
        * x_dot
        * abs(x_dot)
    )


def oleo_force(x, x_dot):

    return (
        gas_force(x)
        + hydraulic_force(
            x,
            x_dot
        )
    )


# ============================================================
# 7. NONLINEAR TIRE MODEL
# ============================================================

# Locked hand-analysis tire values

delta_tire_design = 0.047       # m

eta_tire = 0.47


# Power-law tire:
#
# F_t = k_t * delta^p
#
# Work:
#
# E = F_max * delta_max / (p + 1)
#
# Matching the hand-analysis efficiency:
#
# eta = 1 / (p + 1)

tire_exponent = (
    1.0 / eta_tire
    - 1.0
)


# Require:
#
# F_t(47 mm) = 25.02 kN

k_tire = (
    F_limit
    / delta_tire_design**tire_exponent
)


def tire_force(delta):
    """
    Nonlinear unilateral tire reaction.

    Tire can push upward but cannot pull the runway.
    """

    if delta <= 0.0:

        return 0.0

    return (
        k_tire
        * delta**tire_exponent
    )


def tire_strain_energy(delta):

    if delta <= 0.0:

        return 0.0

    return (
        k_tire
        / (
            tire_exponent
            + 1.0
        )
        * delta**(
            tire_exponent
            + 1.0
        )
    )


# ============================================================
# 8. SIMULATION FUNCTION
# ============================================================

def run_landing_simulation(
    m_unsprung
):

    # --------------------------------------------------------
    # Mass split
    # --------------------------------------------------------

    m_u = m_unsprung

    m_s = (
        m_eq
        - m_u
    )


    # --------------------------------------------------------
    # Aerodynamic lift assigned to this one-main model
    # --------------------------------------------------------

    L_main = (
        lift_fraction
        * m_eq
        * g
    )


    # ========================================================
    # PHASE A
    #
    # Initial touchdown with oleo held against its
    # extension stop.
    #
    # During this phase:
    #
    # z_s = z_u
    # v_s = v_u
    # x_oleo = 0
    #
    # The tire begins compressing first.
    # ========================================================

    def phase_a_ode(
        t,
        y
    ):

        z = y[0]

        v = y[1]

        F_t = tire_force(z)

        # Entire equivalent mass moves together

        a = (
            m_eq * g
            - L_main
            - F_t
        ) / m_eq

        return [
            v,
            a
        ]


    # --------------------------------------------------------
    # Required net strut force while constrained at x = 0
    # --------------------------------------------------------

    def constrained_strut_force(
        z
    ):

        F_t = tire_force(z)

        a = (
            m_eq * g
            - L_main
            - F_t
        ) / m_eq

        # Force transmitted upward into sprung mass

        F_required = (
            m_s * g
            - L_main
            - m_s * a
        )

        return F_required


    # --------------------------------------------------------
    # Extension stop releases when required transmitted
    # compressive force reaches the gas preload.
    # --------------------------------------------------------

    def extension_stop_release_event(
        t,
        y
    ):

        z = y[0]

        F_required = constrained_strut_force(
            z
        )

        return (
            F_required
            - F_gas_preload
        )


    extension_stop_release_event.terminal = True

    extension_stop_release_event.direction = 1


    # --------------------------------------------------------
    # Phase A integration
    # --------------------------------------------------------

    phase_a = solve_ivp(
        phase_a_ode,
        t_span=(
            0.0,
            0.20
        ),
        y0=[
            0.0,
            V_sink
        ],
        events=
        extension_stop_release_event,
        max_step=0.00002,
        rtol=1e-9,
        atol=1e-11
    )


    # --------------------------------------------------------
    # Release state
    # --------------------------------------------------------

    t_release = (
        phase_a.t[-1]
    )

    z_release = (
        phase_a.y[0, -1]
    )

    v_release = (
        phase_a.y[1, -1]
    )


    # ========================================================
    # PHASE B
    #
    # Full 2-DOF oleo + tire dynamics
    # ========================================================

    def phase_b_ode(
        t,
        y
    ):

        z_s = y[0]

        v_s = y[1]

        z_u = y[2]

        v_u = y[3]


        # Oleo compression

        x = (
            z_s - z_u
        )

        # Prevent tiny numerical negative values

        x_force = max(
            x,
            0.0
        )


        # Oleo compression velocity

        x_dot = (
            v_s - v_u
        )


        # Forces

        F_o = oleo_force(
            x_force,
            x_dot
        )

        F_t = tire_force(
            z_u
        )


        # Sprung mass

        a_s = (
            m_s * g
            - L_main
            - F_o
        ) / m_s


        # Unsprung mass

        a_u = (
            m_u * g
            + F_o
            - F_t
        ) / m_u


        return [
            v_s,
            a_s,
            v_u,
            a_u
        ]


    # --------------------------------------------------------
    # Peak oleo compression
    # --------------------------------------------------------

    def peak_oleo_event(
        t,
        y
    ):

        z_s = y[0]

        v_s = y[1]

        z_u = y[2]

        v_u = y[3]

        x = (
            z_s - z_u
        )

        # Prevent immediate event detection at release

        if x < 1.0e-6:

            return 1.0

        return (
            v_s - v_u
        )


    peak_oleo_event.terminal = True

    peak_oleo_event.direction = -1


    # --------------------------------------------------------
    # Physical bottoming
    # --------------------------------------------------------

    def bottoming_event(
        t,
        y
    ):

        x = (
            y[0]
            - y[2]
        )

        return (
            x_available
            - x
        )


    bottoming_event.terminal = True

    bottoming_event.direction = -1


    # --------------------------------------------------------
    # Phase B initial condition
    # --------------------------------------------------------

    y0_phase_b = [
        z_release,
        v_release,
        z_release,
        v_release
    ]


    # --------------------------------------------------------
    # Phase B integration
    # --------------------------------------------------------

    phase_b = solve_ivp(
        phase_b_ode,
        t_span=(
            t_release,
            0.50
        ),
        y0=y0_phase_b,
        events=[
            peak_oleo_event,
            bottoming_event
        ],
        max_step=0.00002,
        rtol=1e-9,
        atol=1e-11
    )


    # ========================================================
    # COMBINE PHASE A + PHASE B
    # ========================================================

    t = np.concatenate([
        phase_a.t,
        phase_b.t[1:]
    ])


    # During Phase A both masses move together

    z_s = np.concatenate([
        phase_a.y[0],
        phase_b.y[0, 1:]
    ])

    v_s = np.concatenate([
        phase_a.y[1],
        phase_b.y[1, 1:]
    ])

    z_u = np.concatenate([
        phase_a.y[0],
        phase_b.y[2, 1:]
    ])

    v_u = np.concatenate([
        phase_a.y[1],
        phase_b.y[3, 1:]
    ])


    # ========================================================
    # DERIVED KINEMATICS
    # ========================================================

    x_oleo = (
        z_s
        - z_u
    )

    x_dot = (
        v_s
        - v_u
    )

    delta_tire = np.maximum(
        z_u,
        0.0
    )


    # ========================================================
    # FORCE HISTORIES
    # ========================================================

    F_tire = np.array([
        tire_force(delta)
        for delta in delta_tire
    ])


    F_gas = np.zeros_like(
        t
    )

    F_hydraulic = np.zeros_like(
        t
    )

    F_strut = np.zeros_like(
        t
    )

    F_extension_stop = np.zeros_like(
        t
    )


    n_phase_a = len(
        phase_a.t
    )


    # --------------------------------------------------------
    # Phase A force reconstruction
    # --------------------------------------------------------

    for i in range(
        n_phase_a
    ):

        F_gas[i] = (
            F_gas_preload
        )

        F_hydraulic[i] = (
            0.0
        )

        F_required = constrained_strut_force(
            delta_tire[i]
        )

        F_strut[i] = (
            F_required
        )

        # Extension stop contribution.
        #
        # Negative here means that the stop is opposing
        # the gas preload to keep the oleo fully extended.

        F_extension_stop[i] = (
            F_required
            - F_gas_preload
        )


    # --------------------------------------------------------
    # Phase B force reconstruction
    # --------------------------------------------------------

    for i in range(
        n_phase_a,
        len(t)
    ):

        x_force = max(
            x_oleo[i],
            0.0
        )

        F_gas[i] = gas_force(
            x_force
        )

        F_hydraulic[i] = hydraulic_force(
            x_force,
            x_dot[i]
        )

        F_strut[i] = (
            F_gas[i]
            + F_hydraulic[i]
        )

        F_extension_stop[i] = (
            0.0
        )


    # ========================================================
    # ACCELERATION HISTORIES
    # ========================================================

    a_s = np.zeros_like(
        t
    )

    a_u = np.zeros_like(
        t
    )


    # Phase A:
    # both masses share the same acceleration

    for i in range(
        n_phase_a
    ):

        a_common = (
            m_eq * g
            - L_main
            - F_tire[i]
        ) / m_eq

        a_s[i] = (
            a_common
        )

        a_u[i] = (
            a_common
        )


    # Phase B

    for i in range(
        n_phase_a,
        len(t)
    ):

        a_s[i] = (
            m_s * g
            - L_main
            - F_strut[i]
        ) / m_s

        a_u[i] = (
            m_u * g
            + F_strut[i]
            - F_tire[i]
        ) / m_u


    # ========================================================
    # ENERGY ACCOUNTING
    # ========================================================

    E_initial_KE = (
        0.5
        * m_eq
        * V_sink**2
    )


    # Gas work

    E_gas = trapezoid(
        F_gas,
        x_oleo
    )


    # Hydraulic dissipation

    hydraulic_power = (
        F_hydraulic
        * x_dot
    )

    E_hydraulic = trapezoid(
        hydraulic_power,
        t
    )


    # Tire net strain energy

    E_tire = tire_strain_energy(
        delta_tire[-1]
    )


    # Maximum tire energy reached during the event

    E_tire_max = tire_strain_energy(
        np.max(delta_tire)
    )


    # Final kinetic energy

    E_final_KE = (
        0.5
        * m_s
        * v_s[-1]**2
        +
        0.5
        * m_u
        * v_u[-1]**2
    )


    # External gravity + aerodynamic work

    E_external = (
        (
            m_s * g
            - L_main
        )
        * z_s[-1]
        +
        (
            m_u * g
        )
        * z_u[-1]
    )


    # Full energy residual

    energy_residual = (
        E_initial_KE
        + E_external
        - E_gas
        - E_hydraulic
        - E_tire
        - E_final_KE
    )


    # ========================================================
    # DESIGN OUTPUTS
    # ========================================================

    peak_oleo_compression = np.max(
        x_oleo
    )

    peak_tire_deflection = np.max(
        delta_tire
    )

    peak_tire_force = np.max(
        F_tire
    )

    peak_strut_force = np.max(
        F_strut
    )

    peak_gas_force = np.max(
        F_gas
    )

    peak_hydraulic_force = np.max(
        F_hydraulic
    )

    peak_upward_sprung_accel_g = (
        -np.min(a_s)
        / g
    )


    stroke_margin = (
        x_available
        - peak_oleo_compression
    )


    bottomed = (
        len(
            phase_b.t_events[1]
        )
        > 0
    )


    peak_event_reached = (
        len(
            phase_b.t_events[0]
        )
        > 0
    )


    # ========================================================
    # RETURN EVERYTHING
    # ========================================================

    return {
        "m_u": m_u,
        "m_s": m_s,

        "t": t,

        "z_s": z_s,
        "v_s": v_s,
        "a_s": a_s,

        "z_u": z_u,
        "v_u": v_u,
        "a_u": a_u,

        "x_oleo": x_oleo,
        "x_dot": x_dot,

        "delta_tire": delta_tire,

        "F_tire": F_tire,

        "F_gas": F_gas,
        "F_hydraulic": F_hydraulic,
        "F_strut": F_strut,
        "F_extension_stop": F_extension_stop,

        "t_release": t_release,
        "z_release": z_release,
        "v_release": v_release,

        "peak_oleo_compression":
            peak_oleo_compression,

        "peak_tire_deflection":
            peak_tire_deflection,

        "peak_tire_force":
            peak_tire_force,

        "peak_strut_force":
            peak_strut_force,

        "peak_gas_force":
            peak_gas_force,

        "peak_hydraulic_force":
            peak_hydraulic_force,

        "peak_upward_sprung_accel_g":
            peak_upward_sprung_accel_g,

        "stroke_margin":
            stroke_margin,

        "E_initial_KE":
            E_initial_KE,

        "E_gas":
            E_gas,

        "E_hydraulic":
            E_hydraulic,

        "E_tire":
            E_tire,

        "E_tire_max":
            E_tire_max,

        "E_final_KE":
            E_final_KE,

        "E_external":
            E_external,

        "energy_residual":
            energy_residual,

        "bottomed":
            bottomed,

        "peak_event_reached":
            peak_event_reached
    }


# ============================================================
# 9. RUN NOMINAL CASE
# ============================================================

results = run_landing_simulation(
    m_unsprung_nominal
)


# ============================================================
# 10. NOMINAL REPORT
# ============================================================

print()

print("=" * 72)

print(
    " PHASE 1 — 2-DOF DYNAMIC LANDING MODEL V0.4"
)

print("=" * 72)


print()
print("--- MASS MODEL ---")

print(
    f"Equivalent mass per main:           "
    f"{m_eq:.2f} kg"
)

print(
    f"Sprung mass:                        "
    f"{results['m_s']:.2f} kg"
)

print(
    f"Unsprung mass:                      "
    f"{results['m_u']:.2f} kg"
)

print(
    f"Touchdown sink speed:               "
    f"{V_sink:.4f} m/s"
)


print()
print("--- NONLINEAR TIRE MODEL ---")

print(
    f"Design tire deflection:             "
    f"{delta_tire_design * 1000:.2f} mm"
)

print(
    f"Tire energy efficiency target:      "
    f"{eta_tire:.3f}"
)

print(
    f"Tire exponent p:                    "
    f"{tire_exponent:.4f}"
)

print(
    f"Tire coefficient k:                 "
    f"{k_tire:.2f} N/m^p"
)


print()
print("--- EXTENSION-STOP PHASE ---")

print(
    f"Gas preload at full extension:      "
    f"{F_gas_preload / 1000:.3f} kN"
)

print(
    f"Stop release time:                  "
    f"{results['t_release']:.6f} s"
)

print(
    f"Tire deflection at release:         "
    f"{results['z_release'] * 1000:.3f} mm"
)

print(
    f"Tire force at release:              "
    f"{tire_force(results['z_release']) / 1000:.3f} kN"
)

print(
    f"Vertical speed at release:          "
    f"{results['v_release']:.4f} m/s"
)


print()
print("--- PEAK DYNAMIC RESULTS ---")

print(
    f"Peak oleo compression:              "
    f"{results['peak_oleo_compression'] * 1000:.3f} mm"
)

print(
    f"Available oleo stroke:              "
    f"{x_available * 1000:.3f} mm"
)

print(
    f"Stroke margin:                      "
    f"{results['stroke_margin'] * 1000:.3f} mm"
)

print(
    f"Peak tire deflection:               "
    f"{results['peak_tire_deflection'] * 1000:.3f} mm"
)

print(
    f"Peak tire / runway reaction:        "
    f"{results['peak_tire_force'] / 1000:.3f} kN"
)

print(
    f"Peak internal strut force:          "
    f"{results['peak_strut_force'] / 1000:.3f} kN"
)

print(
    f"Peak gas force:                     "
    f"{results['peak_gas_force'] / 1000:.3f} kN"
)

print(
    f"Peak hydraulic force:               "
    f"{results['peak_hydraulic_force'] / 1000:.3f} kN"
)

print(
    f"Peak upward sprung acceleration:    "
    f"{results['peak_upward_sprung_accel_g']:.3f} g"
)


print()
print("--- ENERGY RESULTS ---")

print(
    f"Initial touchdown KE:               "
    f"{results['E_initial_KE'] / 1000:.3f} kJ"
)

print(
    f"Gas work:                           "
    f"{results['E_gas'] / 1000:.3f} kJ"
)

print(
    f"Hydraulic energy dissipated:        "
    f"{results['E_hydraulic'] / 1000:.3f} kJ"
)

print(
    f"Max tire strain energy:             "
    f"{results['E_tire_max'] / 1000:.3f} kJ"
)

print(
    f"Tire strain energy at final state:  "
    f"{results['E_tire'] / 1000:.3f} kJ"
)

print(
    f"External gravity/lift work:         "
    f"{results['E_external'] / 1000:.3f} kJ"
)

print(
    f"Final kinetic energy:               "
    f"{results['E_final_KE']:.4f} J"
)

print(
    f"Energy balance residual:            "
    f"{results['energy_residual']:.6f} J"
)


print()
print("--- CHECKS ---")


if results["bottomed"]:

    print(
        "Oleo bottoming:                      "
        "FAIL"
    )

else:

    print(
        "Oleo bottoming:                      "
        "PASS"
    )


if (
    results["peak_tire_force"]
    <= F_limit
):

    print(
        "LC1 ground-reaction limit:           "
        "PASS"
    )

else:

    print(
        "LC1 ground-reaction limit:           "
        "FAIL"
    )


if (
    results["peak_strut_force"]
    <= F_limit
):

    print(
        "LC1 internal-strut limit:            "
        "PASS"
    )

else:

    print(
        "LC1 internal-strut limit:            "
        "FAIL"
    )


if (
    results["peak_tire_force"]
    <= F_ultimate
):

    print(
        "LC1 ultimate ground reaction:        "
        "PASS"
    )

else:

    print(
        "LC1 ultimate ground reaction:        "
        "FAIL"
    )


print()
print("=" * 72)


# ============================================================
# 11. UNSPRUNG-MASS SENSITIVITY
# ============================================================

print()

print(
    "UNSPRUNG-MASS SENSITIVITY"
)

print(
    "-" * 72
)

print(
    " m_u    x_oleo,max    tire defl.    F_tire,max    F_strut,max"
)

print(
    " (kg)      (mm)          (mm)          (kN)           (kN)"
)

print(
    "-" * 72
)


sensitivity_results = []


for mass_case in unsprung_mass_cases:

    case = run_landing_simulation(
        mass_case
    )

    sensitivity_results.append(
        case
    )

    print(
        f"{mass_case:5.1f}"
        f"{case['peak_oleo_compression'] * 1000:13.3f}"
        f"{case['peak_tire_deflection'] * 1000:14.3f}"
        f"{case['peak_tire_force'] / 1000:14.3f}"
        f"{case['peak_strut_force'] / 1000:15.3f}"
    )


print(
    "-" * 72
)


# ============================================================
# 12. NOMINAL-CASE PLOTS
# ============================================================

t = results["t"]

z_s = results["z_s"]

z_u = results["z_u"]

v_s = results["v_s"]

v_u = results["v_u"]

x_oleo = results["x_oleo"]

delta_tire = results["delta_tire"]

F_tire = results["F_tire"]

F_gas = results["F_gas"]

F_hydraulic = results["F_hydraulic"]

F_strut = results["F_strut"]

a_s = results["a_s"]


# ------------------------------------------------------------
# Figure 1 — Oleo + tire compression
# ------------------------------------------------------------

plt.figure(
    figsize=(8, 5)
)

plt.plot(
    t,
    x_oleo * 1000,
    label="Oleo compression"
)

plt.plot(
    t,
    delta_tire * 1000,
    label="Tire compression"
)

plt.axhline(
    x_available * 1000,
    linestyle="--",
    label="Available oleo stroke"
)

plt.xlabel(
    "Time (s)"
)

plt.ylabel(
    "Compression (mm)"
)

plt.title(
    "Oleo and Tire Compression"
)

plt.legend()

plt.grid(True)

plt.tight_layout()


# ------------------------------------------------------------
# Figure 2 — Sprung / unsprung displacement
# ------------------------------------------------------------

plt.figure(
    figsize=(8, 5)
)

plt.plot(
    t,
    z_s * 1000,
    label="Sprung mass"
)

plt.plot(
    t,
    z_u * 1000,
    label="Unsprung mass"
)

plt.xlabel(
    "Time (s)"
)

plt.ylabel(
    "Downward Displacement (mm)"
)

plt.title(
    "Sprung and Unsprung Mass Motion"
)

plt.legend()

plt.grid(True)

plt.tight_layout()


# ------------------------------------------------------------
# Figure 3 — Velocities
# ------------------------------------------------------------

plt.figure(
    figsize=(8, 5)
)

plt.plot(
    t,
    v_s,
    label="Sprung velocity"
)

plt.plot(
    t,
    v_u,
    label="Unsprung velocity"
)

plt.xlabel(
    "Time (s)"
)

plt.ylabel(
    "Vertical Velocity (m/s)"
)

plt.title(
    "Sprung and Unsprung Vertical Velocity"
)

plt.legend()

plt.grid(True)

plt.tight_layout()


# ------------------------------------------------------------
# Figure 4 — Main landing forces
# ------------------------------------------------------------

plt.figure(
    figsize=(8, 5)
)

plt.plot(
    t,
    F_tire / 1000,
    label="Tire / runway reaction"
)

plt.plot(
    t,
    F_strut / 1000,
    label="Net strut force"
)

plt.axhline(
    F_limit / 1000,
    linestyle="--",
    label="LC1 limit"
)

plt.axhline(
    F_ultimate / 1000,
    linestyle=":",
    label="LC1 ultimate"
)

plt.xlabel(
    "Time (s)"
)

plt.ylabel(
    "Force (kN)"
)

plt.title(
    "Landing Gear Force History"
)

plt.legend()

plt.grid(True)

plt.tight_layout()


# ------------------------------------------------------------
# Figure 5 — Oleo force components
# ------------------------------------------------------------

plt.figure(
    figsize=(8, 5)
)

plt.plot(
    t,
    F_gas / 1000,
    label="Gas force"
)

plt.plot(
    t,
    F_hydraulic / 1000,
    label="Hydraulic force"
)

plt.plot(
    t,
    F_strut / 1000,
    label="Net strut force"
)

plt.xlabel(
    "Time (s)"
)

plt.ylabel(
    "Force (kN)"
)

plt.title(
    "Oleo Force Components"
)

plt.legend()

plt.grid(True)

plt.tight_layout()


# ------------------------------------------------------------
# Figure 6 — Force vs oleo stroke
# ------------------------------------------------------------

plt.figure(
    figsize=(8, 5)
)

plt.plot(
    x_oleo * 1000,
    F_strut / 1000
)

plt.axhline(
    F_limit / 1000,
    linestyle="--",
    label="LC1 limit"
)

plt.axvline(
    x_available * 1000,
    linestyle=":",
    label="Available stroke"
)

plt.xlabel(
    "Oleo Compression (mm)"
)

plt.ylabel(
    "Net Strut Force (kN)"
)

plt.title(
    "Strut Force vs Oleo Stroke"
)

plt.legend()

plt.grid(True)

plt.tight_layout()


# ------------------------------------------------------------
# Figure 7 — Sprung acceleration
# ------------------------------------------------------------

plt.figure(
    figsize=(8, 5)
)

plt.plot(
    t,
    a_s / g
)

plt.axhline(
    0.0,
    linestyle="--"
)

plt.xlabel(
    "Time (s)"
)

plt.ylabel(
    "Vertical Acceleration (g)"
)

plt.title(
    "Sprung-Mass Vertical Acceleration"
)

plt.grid(True)

plt.tight_layout()


# ------------------------------------------------------------
# Figure 8 — Unsprung-mass sensitivity
# ------------------------------------------------------------

masses = np.array([
    case["m_u"]
    for case in sensitivity_results
])

peak_strokes = np.array([
    case["peak_oleo_compression"]
    * 1000
    for case in sensitivity_results
])

plt.figure(
    figsize=(8, 5)
)

plt.plot(
    masses,
    peak_strokes,
    marker="o"
)

plt.axhline(
    x_available * 1000,
    linestyle="--",
    label="Available stroke"
)

plt.xlabel(
    "Unsprung Mass per Main (kg)"
)

plt.ylabel(
    "Peak Oleo Compression (mm)"
)

plt.title(
    "Unsprung-Mass Sensitivity"
)

plt.legend()

plt.grid(True)

plt.tight_layout()


plt.show()