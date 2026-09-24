import numpy as np
import matplotlib.pyplot as plt

from scipy.integrate import solve_ivp, trapezoid


# ============================================================
# LANDING GEAR DESIGN PROJECT
# PHASE 1 — DYNAMIC LANDING MODEL V0.5b
#
# ZERO-LIFT / VIRTUAL-STROKE DIAGNOSTIC
#
# IMPORTANT:
# The physical oleo stroke remains 230 mm.
#
# The virtual 300 mm limit exists ONLY to determine how much
# stroke the zero-lift cases would demand if the physical
# bottoming stop were temporarily removed.
# ============================================================


# ============================================================
# 1. LOCKED BASELINE
# ============================================================

g = 9.80665

m_aircraft = 1700.0

m_eq = m_aircraft / 2.0

m_unsprung = 30.0

m_sprung = (
    m_eq - m_unsprung
)

V_design = 3.048

F_limit = 25.02e3

F_ultimate = 37.53e3

x_hand = 0.205

# REAL physical stroke
x_physical = 0.230

# VIRTUAL numerical stroke used only for diagnosis
x_virtual = 0.300


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
    """
    Absolute gas pressure as a function of oleo compression.
    """

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
    """
    Pneumatic gas force.
    """

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
    """
    Frozen V0.3 metering law.

    The V0.3 design schedule ends at the 205 mm design stroke.

    For diagnostic compression beyond 205 mm, the effective
    diameter remains fixed at its final V0.3 value.
    """

    x_clamped = np.clip(
        x,
        0.0,
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
        np.pi * d**2 / 4.0
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
# 4. FROZEN NONLINEAR TIRE MODEL — V0.4
# ============================================================

delta_tire_design = 0.047

eta_tire = 0.47


tire_exponent = (
    1.0 / eta_tire
    - 1.0
)


k_tire = (
    F_limit
    / delta_tire_design**tire_exponent
)


def tire_force(delta):

    if delta <= 0.0:

        return 0.0

    return (
        k_tire
        * delta**tire_exponent
    )


def tire_energy(delta):

    if delta <= 0.0:

        return 0.0

    return (
        k_tire
        / (
            tire_exponent + 1.0
        )
        * delta**(
            tire_exponent + 1.0
        )
    )


# ============================================================
# 5. GENERAL ZERO-LIFT SIMULATION
# ============================================================

def run_case(
    name,
    V_sink
):

    # Zero retained lift
    lift_fraction = 0.0

    L_main = (
        lift_fraction
        * m_eq
        * g
    )


    # ========================================================
    # PHASE A
    # Tire compresses while oleo remains at extension stop
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


    def constrained_strut_force(z):

        F_t = tire_force(
            z
        )

        a = (
            m_eq * g
            - L_main
            - F_t
        ) / m_eq

        F_required = (
            m_sprung * g
            - L_main
            - m_sprung * a
        )

        return F_required


    def extension_release_event(
        t,
        y
    ):

        return (
            constrained_strut_force(
                y[0]
            )
            - F_gas_preload
        )


    extension_release_event.terminal = True

    extension_release_event.direction = 1


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
        extension_release_event,
        max_step=0.00002,
        rtol=1e-9,
        atol=1e-11
    )


    if (
        len(
            phase_a.t_events[0]
        )
        == 0
    ):

        raise RuntimeError(
            f"{name}: extension stop never released."
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
    # PHASE B
    # Full 2-DOF model
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
            z_s - z_u
        )

        x_force = max(
            x,
            0.0
        )

        x_dot = (
            v_s - v_u
        )


        F_o = oleo_force(
            x_force,
            x_dot
        )

        F_t = tire_force(
            z_u
        )


        a_s = (
            m_sprung * g
            - L_main
            - F_o
        ) / m_sprung


        a_u = (
            m_unsprung * g
            + F_o
            - F_t
        ) / m_unsprung


        return [
            v_s,
            a_s,
            v_u,
            a_u
        ]


    # --------------------------------------------------------
    # First maximum oleo compression
    # --------------------------------------------------------

    def peak_compression_event(
        t,
        y
    ):

        x = (
            y[0]
            - y[2]
        )

        if x < 1.0e-6:

            return 1.0

        return (
            y[1]
            - y[3]
        )


    peak_compression_event.terminal = True

    peak_compression_event.direction = -1


    # --------------------------------------------------------
    # Virtual numerical stroke limit
    # --------------------------------------------------------

    def virtual_stroke_event(
        t,
        y
    ):

        x = (
            y[0]
            - y[2]
        )

        return (
            x_virtual
            - x
        )


    virtual_stroke_event.terminal = True

    virtual_stroke_event.direction = -1


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
            peak_compression_event,
            virtual_stroke_event
        ],
        max_step=0.00002,
        rtol=1e-9,
        atol=1e-11
    )


    # ========================================================
    # COMBINE PHASES
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


    x = (
        z_s - z_u
    )

    x_dot = (
        v_s - v_u
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

    F_hyd = np.zeros_like(
        t
    )

    F_strut = np.zeros_like(
        t
    )


    n_phase_a = len(
        phase_a.t
    )


    # Phase A force reconstruction

    for i in range(
        n_phase_a
    ):

        F_gas[i] = (
            F_gas_preload
        )

        F_hyd[i] = (
            0.0
        )

        F_strut[i] = (
            constrained_strut_force(
                delta_tire[i]
            )
        )


    # Phase B force reconstruction

    for i in range(
        n_phase_a,
        len(t)
    ):

        x_force = max(
            x[i],
            0.0
        )

        F_gas[i] = gas_force(
            x_force
        )

        F_hyd[i] = hydraulic_force(
            x_force,
            x_dot[i]
        )

        F_strut[i] = (
            F_gas[i]
            + F_hyd[i]
        )


    # ========================================================
    # ENERGY ACCOUNTING
    # ========================================================

    E_initial = (
        0.5
        * m_eq
        * V_sink**2
    )


    E_gas = trapezoid(
        F_gas,
        x
    )


    E_hyd = trapezoid(
        F_hyd
        * x_dot,
        t
    )


    E_tire_final = tire_energy(
        delta_tire[-1]
    )


    E_final_KE = (
        0.5
        * m_sprung
        * v_s[-1]**2
        +
        0.5
        * m_unsprung
        * v_u[-1]**2
    )


    E_external = (
        (
            m_sprung * g
            - L_main
        )
        * z_s[-1]
        +
        m_unsprung
        * g
        * z_u[-1]
    )


    energy_residual = (
        E_initial
        + E_external
        - E_gas
        - E_hyd
        - E_tire_final
        - E_final_KE
    )


    # ========================================================
    # PEAK OUTPUTS
    # ========================================================

    x_peak = np.max(
        x
    )

    tire_peak = np.max(
        delta_tire
    )

    F_tire_peak = np.max(
        F_tire
    )

    F_strut_peak = np.max(
        F_strut
    )

    F_gas_peak = np.max(
        F_gas
    )

    F_hyd_peak = np.max(
        F_hyd
    )


    physical_excess = (
        x_peak
        - x_physical
    )


    peak_reached = (
        len(
            phase_b.t_events[0]
        )
        > 0
    )


    virtual_limit_hit = (
        len(
            phase_b.t_events[1]
        )
        > 0
    )


    return {

        "name":
            name,

        "V_sink":
            V_sink,

        "t":
            t,

        "x":
            x,

        "delta_tire":
            delta_tire,

        "F_tire":
            F_tire,

        "F_gas":
            F_gas,

        "F_hyd":
            F_hyd,

        "F_strut":
            F_strut,

        "x_peak":
            x_peak,

        "physical_excess":
            physical_excess,

        "tire_peak":
            tire_peak,

        "F_tire_peak":
            F_tire_peak,

        "F_strut_peak":
            F_strut_peak,

        "F_gas_peak":
            F_gas_peak,

        "F_hyd_peak":
            F_hyd_peak,

        "E_gas":
            E_gas,

        "E_hyd":
            E_hyd,

        "energy_residual":
            energy_residual,

        "peak_reached":
            peak_reached,

        "virtual_limit_hit":
            virtual_limit_hit,

        "t_release":
            t_release,

        "delta_release":
            z_release
    }


# ============================================================
# 6. RUN THE TWO DIAGNOSTIC CASES
# ============================================================

cases = [

    (
        "Design sink, zero lift",
        V_design
    ),

    (
        "1.10 Vd, zero lift",
        1.10 * V_design
    )

]


results = []


for (
    name,
    velocity
) in cases:

    results.append(
        run_case(
            name,
            velocity
        )
    )


# ============================================================
# 7. PRINT REPORT
# ============================================================

print()

print("=" * 78)

print(
    " PHASE 1 — V0.5b ZERO-LIFT VIRTUAL-STROKE DIAGNOSTIC"
)

print("=" * 78)


print()

print(
    f"REAL physical oleo stroke:         "
    f"{x_physical * 1000:.1f} mm"
)

print(
    f"Temporary virtual stroke limit:    "
    f"{x_virtual * 1000:.1f} mm"
)

print(
    f"Nominal unsprung mass:             "
    f"{m_unsprung:.1f} kg/main"
)

print(
    f"Retained lift for both cases:      "
    f"L/W = 0"
)


for result in results:

    print()
    print("-" * 78)

    print(
        result["name"]
    )

    print("-" * 78)

    print(
        f"Sink speed:                        "
        f"{result['V_sink']:.4f} m/s"
    )

    print(
        f"Peak demanded oleo stroke:         "
        f"{result['x_peak'] * 1000:.3f} mm"
    )

    print(
        f"Physical stroke available:         "
        f"{x_physical * 1000:.3f} mm"
    )

    print(
        f"Stroke beyond physical design:     "
        f"{result['physical_excess'] * 1000:+.3f} mm"
    )

    print(
        f"Peak tire deflection:              "
        f"{result['tire_peak'] * 1000:.3f} mm"
    )

    print(
        f"Peak ground reaction:              "
        f"{result['F_tire_peak'] / 1000:.3f} kN"
    )

    print(
        f"Peak internal strut force:         "
        f"{result['F_strut_peak'] / 1000:.3f} kN"
    )

    print(
        f"Peak gas force:                    "
        f"{result['F_gas_peak'] / 1000:.3f} kN"
    )

    print(
        f"Peak hydraulic force:              "
        f"{result['F_hyd_peak'] / 1000:.3f} kN"
    )

    print(
        f"Gas work:                          "
        f"{result['E_gas'] / 1000:.3f} kJ"
    )

    print(
        f"Hydraulic energy dissipated:       "
        f"{result['E_hyd'] / 1000:.3f} kJ"
    )

    print(
        f"Energy residual:                   "
        f"{result['energy_residual']:.6f} J"
    )


    if result["peak_reached"]:

        print(
            "First maximum compression:         "
            "REACHED"
        )

    else:

        print(
            "First maximum compression:         "
            "NOT REACHED"
        )


    if result["virtual_limit_hit"]:

        print(
            "300 mm virtual limit:              "
            "HIT"
        )

    else:

        print(
            "300 mm virtual limit:              "
            "NOT HIT"
        )


    if (
        result["x_peak"]
        <= x_physical
    ):

        print(
            "230 mm physical-stroke check:      "
            "PASS"
        )

    else:

        print(
            "230 mm physical-stroke check:      "
            "EXCEEDED"
        )


    if (
        result["F_tire_peak"]
        <= F_limit
    ):

        print(
            "LC1 ground-reaction limit:         "
            "PASS"
        )

    else:

        print(
            "LC1 ground-reaction limit:         "
            "EXCEEDED"
        )


    if (
        result["F_strut_peak"]
        <= F_limit
    ):

        print(
            "LC1 strut-force limit:             "
            "PASS"
        )

    else:

        print(
            "LC1 strut-force limit:             "
            "EXCEEDED"
        )


    if (
        result["F_tire_peak"]
        <= F_ultimate
        and
        result["F_strut_peak"]
        <= F_ultimate
    ):

        print(
            "Ultimate reference check:          "
            "PASS"
        )

    else:

        print(
            "Ultimate reference check:          "
            "EXCEEDED"
        )


print()

print("=" * 78)


# ============================================================
# 8. PLOT 1 — OLEO STROKE
# ============================================================

plt.figure(
    figsize=(8, 5)
)


for result in results:

    plt.plot(
        result["t"],
        result["x"] * 1000,
        label=result["name"]
    )


plt.axhline(
    x_physical * 1000,
    linestyle="--",
    label="Real 230 mm stroke"
)


plt.axhline(
    x_virtual * 1000,
    linestyle=":",
    label="Virtual 300 mm limit"
)


plt.xlabel(
    "Time (s)"
)

plt.ylabel(
    "Oleo Compression (mm)"
)

plt.title(
    "Zero-Lift Virtual-Stroke Demand"
)

plt.legend()

plt.grid(True)

plt.tight_layout()


# ============================================================
# 9. PLOT 2 — GROUND REACTION
# ============================================================

plt.figure(
    figsize=(8, 5)
)


for result in results:

    plt.plot(
        result["t"],
        result["F_tire"] / 1000,
        label=result["name"]
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
    "Tire / Runway Reaction (kN)"
)

plt.title(
    "Zero-Lift Ground-Reaction History"
)

plt.legend()

plt.grid(True)

plt.tight_layout()


# ============================================================
# 10. PLOT 3 — INTERNAL STRUT FORCE
# ============================================================

plt.figure(
    figsize=(8, 5)
)


for result in results:

    plt.plot(
        result["t"],
        result["F_strut"] / 1000,
        label=result["name"]
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
    "Internal Strut Force (kN)"
)

plt.title(
    "Zero-Lift Strut-Force History"
)

plt.legend()

plt.grid(True)

plt.tight_layout()


# ============================================================
# 11. PLOT 4 — FORCE VS STROKE
# ============================================================

plt.figure(
    figsize=(8, 5)
)


for result in results:

    plt.plot(
        result["x"] * 1000,
        result["F_strut"] / 1000,
        label=result["name"]
    )


plt.axvline(
    x_physical * 1000,
    linestyle="--",
    label="Real stroke limit"
)


plt.axhline(
    F_limit / 1000,
    linestyle=":",
    label="LC1 limit"
)


plt.xlabel(
    "Oleo Compression (mm)"
)

plt.ylabel(
    "Internal Strut Force (kN)"
)

plt.title(
    "Zero-Lift Strut Force vs Stroke"
)

plt.legend()

plt.grid(True)

plt.tight_layout()


plt.show()