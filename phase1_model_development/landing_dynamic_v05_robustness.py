import numpy as np
import matplotlib.pyplot as plt

from scipy.integrate import solve_ivp


# ============================================================
# LANDING GEAR DESIGN PROJECT
# PHASE 1 — DYNAMIC LANDING MODEL V0.5
#
# ROBUSTNESS / SENSITIVITY STUDY
#
# Frozen physics:
# - V0.3 oleo gas model
# - V0.3 smooth hydraulic metering
# - V0.4 2-DOF sprung / unsprung model
# - V0.4 nonlinear tire model
#
# Variables investigated:
# - unsprung mass
# - touchdown sink speed
# - tire stiffness
# - retained aerodynamic lift
# ============================================================


# ============================================================
# 1. LOCKED BASELINE
# ============================================================

g = 9.80665

m_aircraft = 1700.0

m_eq = m_aircraft / 2.0

V_sink_design = 3.048

lift_fraction_nominal = 2.0 / 3.0

m_unsprung_nominal = 30.0

F_limit = 25.02e3

F_ultimate = 37.53e3

x_hand = 0.205

x_available = 0.230


# ============================================================
# 2. FROZEN OLEO GAS MODEL — V0.3
# ============================================================

D_piston = 0.058

A_piston = (
    np.pi * D_piston**2 / 4.0
)

L_gas_0 = 0.350

P_atm = 101325.0

P_gas_0_abs = 2.336e6

n_poly = 1.30


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
            L_gas_0
            / gas_length
        )**n_poly
    )


def gas_force(x):

    return (
        gas_pressure(x)
        - P_atm
    ) * A_piston


F_gas_preload = gas_force(
    0.0
)


# ============================================================
# 3. FROZEN HYDRAULIC METERING — V0.3
# ============================================================

rho_oil = 850.0

C_d = 0.70

d_orifice_start = 0.010301

d_orifice_end = 0.009742


def orifice_diameter(x):

    x_clamped = min(
        max(x, 0.0),
        x_hand
    )

    fraction = (
        x_clamped / x_hand
    )

    return (
        d_orifice_start
        + (
            d_orifice_end
            - d_orifice_start
        )
        * fraction
    )


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


def hydraulic_force(
    x,
    x_dot
):

    return (
        hydraulic_coefficient(x)
        * x_dot
        * abs(x_dot)
    )


def oleo_force(
    x,
    x_dot
):

    return (
        gas_force(x)
        + hydraulic_force(
            x,
            x_dot
        )
    )


# ============================================================
# 4. FROZEN TIRE MODEL — V0.4
# ============================================================

delta_tire_design = 0.047

eta_tire = 0.47


tire_exponent = (
    1.0 / eta_tire
    - 1.0
)


k_tire_nominal = (
    F_limit
    / delta_tire_design**tire_exponent
)


# ============================================================
# 5. GENERAL 2-DOF SIMULATION
# ============================================================

def run_landing_simulation(
    m_unsprung,
    V_sink,
    lift_fraction,
    tire_stiffness_factor
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
    # Aerodynamic lift
    # --------------------------------------------------------

    L_main = (
        lift_fraction
        * m_eq
        * g
    )


    # --------------------------------------------------------
    # Tire coefficient for this case
    # --------------------------------------------------------

    k_tire = (
        k_tire_nominal
        * tire_stiffness_factor
    )


    def tire_force(delta):

        if delta <= 0.0:

            return 0.0

        return (
            k_tire
            * delta**tire_exponent
        )


    # ========================================================
    # PHASE A — EXTENSION STOP ENGAGED
    # ========================================================

    def phase_a_ode(
        t,
        y
    ):

        z = y[0]

        v = y[1]

        F_t = tire_force(
            z
        )

        a = (
            m_eq * g
            - L_main
            - F_t
        ) / m_eq

        return [
            v,
            a
        ]


    def constrained_strut_force(
        z
    ):

        F_t = tire_force(
            z
        )

        a = (
            m_eq * g
            - L_main
            - F_t
        ) / m_eq

        F_required = (
            m_s * g
            - L_main
            - m_s * a
        )

        return F_required


    def extension_stop_release_event(
        t,
        y
    ):

        return (
            constrained_strut_force(
                y[0]
            )
            - F_gas_preload
        )


    extension_stop_release_event.terminal = True

    extension_stop_release_event.direction = 1


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


    # Safety check

    if (
        len(
            phase_a.t_events[0]
        )
        == 0
    ):

        raise RuntimeError(
            "Extension stop never released."
        )


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
    # PHASE B — FULL 2-DOF DYNAMICS
    # ========================================================

    def phase_b_ode(
        t,
        y
    ):

        z_s = y[0]

        v_s = y[1]

        z_u = y[2]

        v_u = y[3]


        x = (
            z_s
            - z_u
        )

        x_force = max(
            x,
            0.0
        )

        x_dot = (
            v_s
            - v_u
        )


        F_o = oleo_force(
            x_force,
            x_dot
        )

        F_t = tire_force(
            z_u
        )


        a_s = (
            m_s * g
            - L_main
            - F_o
        ) / m_s


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
    # First maximum oleo compression
    # --------------------------------------------------------

    def peak_oleo_event(
        t,
        y
    ):

        x = (
            y[0]
            - y[2]
        )

        # Avoid immediate triggering at release

        if x < 1.0e-6:

            return 1.0

        return (
            y[1]
            - y[3]
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


    phase_b = solve_ivp(
        phase_b_ode,
        t_span=(
            t_release,
            0.50
        ),
        y0=[
            z_release,
            v_release,
            z_release,
            v_release
        ],
        events=[
            peak_oleo_event,
            bottoming_event
        ],
        max_step=0.00002,
        rtol=1e-9,
        atol=1e-11
    )


    # ========================================================
    # COMBINE BOTH PHASES
    # ========================================================

    t = np.concatenate([
        phase_a.t,
        phase_b.t[1:]
    ])


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


    F_strut = np.zeros_like(
        t
    )


    n_phase_a = len(
        phase_a.t
    )


    # Phase A

    for i in range(
        n_phase_a
    ):

        F_strut[i] = (
            constrained_strut_force(
                delta_tire[i]
            )
        )


    # Phase B

    for i in range(
        n_phase_a,
        len(t)
    ):

        x_force = max(
            x_oleo[i],
            0.0
        )

        F_strut[i] = oleo_force(
            x_force,
            x_dot[i]
        )


    # ========================================================
    # PEAK RESULTS
    # ========================================================

    peak_oleo = np.max(
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
    # STATUS
    # ========================================================

    stroke_pass = (
        not bottomed
        and peak_oleo
        <= x_available
    )


    ground_limit_pass = (
        peak_tire_force
        <= F_limit
    )


    strut_limit_pass = (
        peak_strut_force
        <= F_limit
    )


    ultimate_pass = (
        peak_tire_force
        <= F_ultimate
        and peak_strut_force
        <= F_ultimate
    )


    return {

        "m_unsprung":
            m_unsprung,

        "V_sink":
            V_sink,

        "sink_factor":
            V_sink
            / V_sink_design,

        "lift_fraction":
            lift_fraction,

        "tire_factor":
            tire_stiffness_factor,

        "t_release":
            t_release,

        "peak_oleo":
            peak_oleo,

        "stroke_margin":
            x_available
            - peak_oleo,

        "peak_tire_deflection":
            peak_tire_deflection,

        "peak_tire_force":
            peak_tire_force,

        "peak_strut_force":
            peak_strut_force,

        "bottomed":
            bottomed,

        "peak_event_reached":
            peak_event_reached,

        "stroke_pass":
            stroke_pass,

        "ground_limit_pass":
            ground_limit_pass,

        "strut_limit_pass":
            strut_limit_pass,

        "ultimate_pass":
            ultimate_pass
    }


# ============================================================
# 6. REPORT FUNCTION
# ============================================================

def print_case(
    name,
    result
):

    status = "PASS"

    if not (
        result["stroke_pass"]
        and result["ground_limit_pass"]
        and result["strut_limit_pass"]
        and result["ultimate_pass"]
    ):

        status = "FLAG"


    print(
        f"{name:<22}"
        f"{result['peak_oleo'] * 1000:10.2f}"
        f"{result['peak_tire_deflection'] * 1000:12.2f}"
        f"{result['peak_tire_force'] / 1000:13.2f}"
        f"{result['peak_strut_force'] / 1000:14.2f}"
        f"{status:>9}"
    )


# ============================================================
# 7. NOMINAL CASE
# ============================================================

nominal = run_landing_simulation(
    m_unsprung=
    m_unsprung_nominal,

    V_sink=
    V_sink_design,

    lift_fraction=
    lift_fraction_nominal,

    tire_stiffness_factor=
    1.0
)


print()

print("=" * 82)

print(
    " PHASE 1 — DYNAMIC LANDING ROBUSTNESS STUDY V0.5"
)

print("=" * 82)


print()

print(
    "Frozen oleo: V0.3"
)

print(
    "Frozen 2-DOF architecture: V0.4"
)

print(
    "Nominal unsprung mass: 30 kg/main"
)

print(
    "Nominal sink speed: 3.048 m/s"
)

print(
    "Nominal retained lift: L/W = 2/3"
)

print()


print(
    f"Nominal peak oleo stroke:        "
    f"{nominal['peak_oleo'] * 1000:.3f} mm"
)

print(
    f"Nominal stroke margin:           "
    f"{nominal['stroke_margin'] * 1000:.3f} mm"
)

print(
    f"Nominal peak tire reaction:      "
    f"{nominal['peak_tire_force'] / 1000:.3f} kN"
)

print(
    f"Nominal peak strut force:        "
    f"{nominal['peak_strut_force'] / 1000:.3f} kN"
)


# ============================================================
# 8. UNSPRUNG-MASS SWEEP
# ============================================================

mass_values = [
    20.0,
    30.0,
    40.0
]


mass_results = []


for value in mass_values:

    result = run_landing_simulation(
        m_unsprung=value,
        V_sink=V_sink_design,
        lift_fraction=lift_fraction_nominal,
        tire_stiffness_factor=1.0
    )

    mass_results.append(
        result
    )


print()
print("-" * 82)

print(
    "UNSPRUNG-MASS SWEEP"
)

print(
    "Case                  Oleo(mm)   Tire(mm)   Tire F(kN)   Strut F(kN)   Status"
)

print("-" * 82)


for value, result in zip(
    mass_values,
    mass_results
):

    print_case(
        f"{value:.0f} kg",
        result
    )


# ============================================================
# 9. SINK-SPEED SWEEP
# ============================================================

sink_factors = [
    0.90,
    1.00,
    1.10
]


sink_results = []


for factor in sink_factors:

    result = run_landing_simulation(
        m_unsprung=
        m_unsprung_nominal,

        V_sink=
        V_sink_design
        * factor,

        lift_fraction=
        lift_fraction_nominal,

        tire_stiffness_factor=
        1.0
    )

    sink_results.append(
        result
    )


print()
print("-" * 82)

print(
    "SINK-SPEED SWEEP"
)

print(
    "Case                  Oleo(mm)   Tire(mm)   Tire F(kN)   Strut F(kN)   Status"
)

print("-" * 82)


for factor, result in zip(
    sink_factors,
    sink_results
):

    print_case(
        f"{factor:.2f} Vd",
        result
    )


# ============================================================
# 10. TIRE-STIFFNESS SWEEP
# ============================================================

tire_factors = [
    0.85,
    1.00,
    1.15
]


tire_results = []


for factor in tire_factors:

    result = run_landing_simulation(
        m_unsprung=
        m_unsprung_nominal,

        V_sink=
        V_sink_design,

        lift_fraction=
        lift_fraction_nominal,

        tire_stiffness_factor=
        factor
    )

    tire_results.append(
        result
    )


print()
print("-" * 82)

print(
    "TIRE-STIFFNESS SWEEP"
)

print(
    "Case                  Oleo(mm)   Tire(mm)   Tire F(kN)   Strut F(kN)   Status"
)

print("-" * 82)


for factor, result in zip(
    tire_factors,
    tire_results
):

    print_case(
        f"{factor:.2f} kt",
        result
    )


# ============================================================
# 11. LIFT-FRACTION SWEEP
# ============================================================

lift_values = [
    0.0,
    1.0 / 3.0,
    2.0 / 3.0
]


lift_results = []


for value in lift_values:

    result = run_landing_simulation(
        m_unsprung=
        m_unsprung_nominal,

        V_sink=
        V_sink_design,

        lift_fraction=
        value,

        tire_stiffness_factor=
        1.0
    )

    lift_results.append(
        result
    )


print()
print("-" * 82)

print(
    "RETAINED-LIFT SWEEP"
)

print(
    "Case                  Oleo(mm)   Tire(mm)   Tire F(kN)   Strut F(kN)   Status"
)

print("-" * 82)


lift_labels = [
    "L/W = 0",
    "L/W = 1/3",
    "L/W = 2/3"
]


for label, result in zip(
    lift_labels,
    lift_results
):

    print_case(
        label,
        result
    )


# ============================================================
# 12. SELECTED ROBUSTNESS CORNERS
# ============================================================

corner_cases = [

    (
        "High sink",
        30.0,
        1.10,
        1.00,
        2.0 / 3.0
    ),

    (
        "High sink + hard tire",
        40.0,
        1.10,
        1.15,
        2.0 / 3.0
    ),

    (
        "Zero retained lift",
        30.0,
        1.00,
        1.00,
        0.0
    ),

    (
        "High sink + zero lift",
        30.0,
        1.10,
        1.00,
        0.0
    )
]


corner_results = []


print()
print("-" * 82)

print(
    "SELECTED ROBUSTNESS CORNERS"
)

print(
    "Case                  Oleo(mm)   Tire(mm)   Tire F(kN)   Strut F(kN)   Status"
)

print("-" * 82)


for (
    name,
    mass,
    sink_factor,
    tire_factor,
    lift_fraction
) in corner_cases:

    result = run_landing_simulation(
        m_unsprung=
        mass,

        V_sink=
        V_sink_design
        * sink_factor,

        lift_fraction=
        lift_fraction,

        tire_stiffness_factor=
        tire_factor
    )

    corner_results.append(
        result
    )

    print_case(
        name,
        result
    )


print()
print("=" * 82)


# ============================================================
# 13. PLOT — UNSPRUNG MASS VS STROKE
# ============================================================

plt.figure(
    figsize=(8, 5)
)

plt.plot(
    mass_values,
    [
        r["peak_oleo"] * 1000
        for r in mass_results
    ],
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


# ============================================================
# 14. PLOT — UNSPRUNG MASS VS GROUND REACTION
# ============================================================

plt.figure(
    figsize=(8, 5)
)

plt.plot(
    mass_values,
    [
        r["peak_tire_force"] / 1000
        for r in mass_results
    ],
    marker="o"
)

plt.axhline(
    F_limit / 1000,
    linestyle="--",
    label="LC1 limit"
)

plt.xlabel(
    "Unsprung Mass per Main (kg)"
)

plt.ylabel(
    "Peak Tire / Runway Reaction (kN)"
)

plt.title(
    "Unsprung-Mass Load Sensitivity"
)

plt.legend()

plt.grid(True)

plt.tight_layout()


# ============================================================
# 15. PLOT — SINK SPEED VS STROKE
# ============================================================

plt.figure(
    figsize=(8, 5)
)

plt.plot(
    sink_factors,
    [
        r["peak_oleo"] * 1000
        for r in sink_results
    ],
    marker="o"
)

plt.axhline(
    x_available * 1000,
    linestyle="--",
    label="Available stroke"
)

plt.xlabel(
    "Sink-Speed Factor, V / Vd"
)

plt.ylabel(
    "Peak Oleo Compression (mm)"
)

plt.title(
    "Sink-Speed Stroke Sensitivity"
)

plt.legend()

plt.grid(True)

plt.tight_layout()


# ============================================================
# 16. PLOT — SINK SPEED VS LOAD
# ============================================================

plt.figure(
    figsize=(8, 5)
)

plt.plot(
    sink_factors,
    [
        r["peak_tire_force"] / 1000
        for r in sink_results
    ],
    marker="o",
    label="Ground reaction"
)

plt.plot(
    sink_factors,
    [
        r["peak_strut_force"] / 1000
        for r in sink_results
    ],
    marker="o",
    label="Strut force"
)

plt.axhline(
    F_limit / 1000,
    linestyle="--",
    label="LC1 limit"
)

plt.xlabel(
    "Sink-Speed Factor, V / Vd"
)

plt.ylabel(
    "Peak Force (kN)"
)

plt.title(
    "Sink-Speed Load Sensitivity"
)

plt.legend()

plt.grid(True)

plt.tight_layout()


# ============================================================
# 17. PLOT — TIRE STIFFNESS VS LOAD
# ============================================================

plt.figure(
    figsize=(8, 5)
)

plt.plot(
    tire_factors,
    [
        r["peak_tire_force"] / 1000
        for r in tire_results
    ],
    marker="o",
    label="Ground reaction"
)

plt.plot(
    tire_factors,
    [
        r["peak_strut_force"] / 1000
        for r in tire_results
    ],
    marker="o",
    label="Strut force"
)

plt.axhline(
    F_limit / 1000,
    linestyle="--",
    label="LC1 limit"
)

plt.xlabel(
    "Tire-Stiffness Factor"
)

plt.ylabel(
    "Peak Force (kN)"
)

plt.title(
    "Tire-Stiffness Load Sensitivity"
)

plt.legend()

plt.grid(True)

plt.tight_layout()


# ============================================================
# 18. PLOT — RETAINED LIFT VS STROKE
# ============================================================

plt.figure(
    figsize=(8, 5)
)

plt.plot(
    lift_values,
    [
        r["peak_oleo"] * 1000
        for r in lift_results
    ],
    marker="o"
)

plt.axhline(
    x_available * 1000,
    linestyle="--",
    label="Available stroke"
)

plt.xlabel(
    "Retained Lift Fraction, L/W"
)

plt.ylabel(
    "Peak Oleo Compression (mm)"
)

plt.title(
    "Retained-Lift Stroke Sensitivity"
)

plt.legend()

plt.grid(True)

plt.tight_layout()


# ============================================================
# 19. PLOT — RETAINED LIFT VS LOAD
# ============================================================

plt.figure(
    figsize=(8, 5)
)

plt.plot(
    lift_values,
    [
        r["peak_tire_force"] / 1000
        for r in lift_results
    ],
    marker="o",
    label="Ground reaction"
)

plt.plot(
    lift_values,
    [
        r["peak_strut_force"] / 1000
        for r in lift_results
    ],
    marker="o",
    label="Strut force"
)

plt.axhline(
    F_limit / 1000,
    linestyle="--",
    label="LC1 limit"
)

plt.xlabel(
    "Retained Lift Fraction, L/W"
)

plt.ylabel(
    "Peak Force (kN)"
)

plt.title(
    "Retained-Lift Load Sensitivity"
)

plt.legend()

plt.grid(True)

plt.tight_layout()


plt.show()