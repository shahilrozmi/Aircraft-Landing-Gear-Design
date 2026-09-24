import numpy as np
import matplotlib.pyplot as plt

from scipy.integrate import solve_ivp, trapezoid


# ============================================================
# LANDING GEAR DESIGN PROJECT
# PHASE 1 — DYNAMIC OLEO MODEL V0.3
#
# 1-DOF energy-equivalent landing model
# One main landing gear
# Smooth stroke-dependent hydraulic metering
# ============================================================


# ============================================================
# 1. LOCKED AIRCRAFT / LC1 BASELINE
# ============================================================

g = 9.80665                       # gravitational acceleration [m/s^2]

m_aircraft = 1700.0              # aircraft mass [kg]

# Symmetric landing:
# half-aircraft equivalent mass assigned to one main gear
m_eq = m_aircraft / 2.0          # [kg]

V_sink = 3.048                   # 10 ft/s design sink speed [m/s]

lift_fraction = 2.0 / 3.0        # residual aerodynamic lift fraction

F_limit = 25.02e3                # LC1 limit load per main [N]
F_ultimate = 37.53e3             # LC1 ultimate load per main [N]

x_hand = 0.205                   # hand-analysis required stroke [m]
x_available = 0.230              # available physical stroke [m]

s_tire = 0.047                   # tire deflection proxy [m]
eta_tire = 0.47                  # tire energy efficiency


# ============================================================
# 2. LOCKED OLEO GAS PARAMETERS
# ============================================================

D_piston = 0.058                 # piston diameter [m]

A_piston = (
    np.pi * D_piston**2 / 4.0
)

L_gas_0 = 0.350                  # initial gas-column length [m]

P_atm = 101325.0                 # atmospheric pressure [Pa]

P_gas_0_abs = 2.336e6            # initial gas pressure, absolute [Pa]

n_poly = 1.30                    # polytropic exponent


# ============================================================
# 3. SMOOTH HYDRAULIC METERING V0.3
# ============================================================

rho_oil = 850.0                  # hydraulic oil density [kg/m^3]

C_d = 0.70                       # discharge coefficient


# Smooth equivalent orifice schedule
#
# At x = 0:
#     d_o = 10.301 mm
#
# At x = 205 mm:
#     d_o = 9.742 mm

d_orifice_start = 0.010301       # [m]

d_orifice_end = 0.009742         # [m]


def orifice_diameter(x):
    """
    Smooth linear equivalent-orifice schedule.

    The effective orifice diameter decreases continuously
    from d_orifice_start at zero compression to
    d_orifice_end at the design stroke x_hand.

    Outside the design interval, the diameter is clamped
    to the corresponding endpoint.
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


# ============================================================
# 4. STROKE-DEPENDENT HYDRAULIC COEFFICIENT
# ============================================================

def orifice_area(x):
    """
    Equivalent hydraulic flow area at compression x.
    """

    diameter = orifice_diameter(x)

    area = (
        np.pi
        * diameter**2
        / 4.0
    )

    return area


def hydraulic_coefficient(x):
    """
    Quadratic hydraulic coefficient:

        F_h = C_h(x) * v * |v|

    where

        C_h = rho * A_p^3 / (2 Cd^2 Ao^2)
    """

    A_o = orifice_area(x)

    C_h_local = (
        rho_oil
        * A_piston**3
        / (
            2.0
            * C_d**2
            * A_o**2
        )
    )

    return C_h_local


# ============================================================
# 5. LANDING ENERGY BEFORE OLEO COMPRESSION
# ============================================================

# Initial touchdown kinetic energy carried by ONE main

E_kin_touchdown = (
    0.5
    * m_eq
    * V_sink**2
)


# Net downward force after residual lift:
#
# F_effective = mg - L

F_effective = (
    m_eq
    * g
    * (1.0 - lift_fraction)
)


# Tire energy absorbed before the equivalent oleo event

E_tire = (
    eta_tire
    * F_limit
    * s_tire
)


# Gravity-minus-lift work while the tire deflects

E_gravity_tire = (
    F_effective
    * s_tire
)


# Remaining kinetic energy at start of oleo compression

E_kin_oleo_start = (
    E_kin_touchdown
    + E_gravity_tire
    - E_tire
)


# Equivalent oleo-entry velocity

V_oleo_0 = np.sqrt(
    2.0
    * E_kin_oleo_start
    / m_eq
)


# ============================================================
# 6. GAS SPRING MODEL
# ============================================================

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

    pressure = (
        P_gas_0_abs
        * (
            L_gas_0
            / gas_length
        )**n_poly
    )

    return pressure


def gas_force(x):
    """
    Pneumatic gas-spring force.

    Atmospheric pressure is removed because
    P_gas_0_abs is an absolute pressure.
    """

    pressure_abs = gas_pressure(x)

    pressure_gauge = (
        pressure_abs
        - P_atm
    )

    force = (
        pressure_gauge
        * A_piston
    )

    return force


# ============================================================
# 7. HYDRAULIC DAMPING MODEL
# ============================================================

def hydraulic_force(x, v):
    """
    Stroke-dependent quadratic hydraulic force.

    Positive velocity = compression.

        F_h = C_h(x) * v * |v|
    """

    C_h_local = hydraulic_coefficient(x)

    force = (
        C_h_local
        * v
        * abs(v)
    )

    return force


# ============================================================
# 8. TOTAL OLEO FORCE
# ============================================================

def oleo_force(x, v):
    """
    Total axial oleo force.
    """

    F_g = gas_force(x)

    F_h = hydraulic_force(
        x,
        v
    )

    F_total = (
        F_g
        + F_h
    )

    return F_total


# ============================================================
# 9. GOVERNING EQUATION OF MOTION
# ============================================================

def landing_ode(t, y):
    """
    State vector:

        y[0] = x  : oleo compression [m]
        y[1] = v  : compression velocity [m/s]

    Downward direction is positive.
    """

    x = y[0]
    v = y[1]

    F_oleo = oleo_force(
        x,
        v
    )

    # Newton's second law:
    #
    # m*a = F_effective - F_oleo

    a = (
        F_effective
        - F_oleo
    ) / m_eq

    return [
        v,
        a
    ]


# ============================================================
# 10. EVENTS
# ============================================================

def peak_compression_event(t, y):
    """
    Maximum compression occurs when compression velocity
    decreases through zero.
    """

    return y[1]


peak_compression_event.terminal = True
peak_compression_event.direction = -1


def bottoming_event(t, y):
    """
    Detect physical stroke exhaustion.
    """

    return (
        x_available
        - y[0]
    )


bottoming_event.terminal = True
bottoming_event.direction = -1


# ============================================================
# 11. INITIAL CONDITIONS
# ============================================================

x0 = 0.0

v0 = V_oleo_0

y0 = [
    x0,
    v0
]


# ============================================================
# 12. NUMERICAL INTEGRATION
# ============================================================

solution = solve_ivp(
    landing_ode,
    t_span=(0.0, 1.0),
    y0=y0,
    events=[
        peak_compression_event,
        bottoming_event
    ],
    max_step=0.00025,
    rtol=1e-9,
    atol=1e-11
)


# ============================================================
# 13. EXTRACT SIMULATION RESULTS
# ============================================================

t = solution.t

x = solution.y[0]

v = solution.y[1]


F_g = np.array([
    gas_force(xi)
    for xi in x
])


F_h = np.array([
    hydraulic_force(xi, vi)
    for xi, vi in zip(x, v)
])


F_total = (
    F_g
    + F_h
)


acceleration = (
    F_effective
    - F_total
) / m_eq


d_orifice_history = np.array([
    orifice_diameter(xi)
    for xi in x
])


C_h_history = np.array([
    hydraulic_coefficient(xi)
    for xi in x
])


# ============================================================
# 14. ENERGY CALCULATIONS
# ============================================================

# Gas work

E_gas = trapezoid(
    F_g,
    x
)


# Hydraulic energy dissipation

E_hydraulic = trapezoid(
    F_h,
    x
)


# Gravity-minus-lift work during oleo compression

E_external = (
    F_effective
    * x[-1]
)


# Final kinetic energy

E_kin_final = (
    0.5
    * m_eq
    * v[-1]**2
)


# Energy balance:
#
# initial KE + external work
# =
# gas work + hydraulic dissipation + final KE

energy_residual = (
    E_kin_oleo_start
    + E_external
    - E_gas
    - E_hydraulic
    - E_kin_final
)


# ============================================================
# 15. HAND-ANALYSIS ENERGY TARGETS
# ============================================================

E_oleo_hand = (
    E_kin_oleo_start
    + F_effective
    * x_hand
)


x_hand_array = np.linspace(
    0.0,
    x_hand,
    1000
)


F_g_hand_array = np.array([
    gas_force(xi)
    for xi in x_hand_array
])


E_gas_hand = trapezoid(
    F_g_hand_array,
    x_hand_array
)


E_hydraulic_hand = (
    E_oleo_hand
    - E_gas_hand
)


# ============================================================
# 16. ENGINEERING RESULTS
# ============================================================

x_peak = np.max(x)

t_peak = t[
    np.argmax(x)
]


F_g_peak = np.max(F_g)

F_h_peak = np.max(F_h)

F_total_peak = np.max(F_total)


stroke_margin = (
    x_available
    - x_peak
)


# Maximum upward acceleration
#
# Downward-positive convention:
# most-negative acceleration = strongest upward acceleration.

a_min = np.min(
    acceleration
)

upward_accel_g = (
    -a_min / g
)


# Total main-gear reaction / aircraft weight

W_aircraft = (
    m_aircraft
    * g
)

gear_reaction_ratio = (
    2.0
    * F_total_peak
    / W_aircraft
)


# Hydraulic endpoint values

A_orifice_start = (
    np.pi
    * d_orifice_start**2
    / 4.0
)

A_orifice_end = (
    np.pi
    * d_orifice_end**2
    / 4.0
)


C_h_start = hydraulic_coefficient(
    0.0
)

C_h_end = hydraulic_coefficient(
    x_hand
)


# ============================================================
# 17. TERMINATION STATUS
# ============================================================

peak_event_occurred = (
    len(solution.t_events[0]) > 0
)

bottom_event_occurred = (
    len(solution.t_events[1]) > 0
)


# ============================================================
# 18. PRINT REPORT
# ============================================================

print()

print("=" * 68)

print(
    " PHASE 1 — DYNAMIC LANDING / OLEO MODEL V0.3"
)

print("=" * 68)


print()
print("--- LOCKED AIRCRAFT BASELINE ---")

print(
    f"Aircraft mass:                     "
    f"{m_aircraft:.1f} kg"
)

print(
    f"Equivalent mass per main:          "
    f"{m_eq:.1f} kg"
)

print(
    f"Design touchdown sink speed:       "
    f"{V_sink:.4f} m/s"
)

print(
    f"Residual lift fraction:            "
    f"{lift_fraction:.4f}"
)


print()
print("--- TIRE ENERGY TRANSFER ---")

print(
    f"Touchdown KE / main:               "
    f"{E_kin_touchdown / 1000:.3f} kJ"
)

print(
    f"Tire energy absorbed / main:       "
    f"{E_tire / 1000:.3f} kJ"
)

print(
    f"Gravity/lift work over tire:       "
    f"{E_gravity_tire / 1000:.3f} kJ"
)

print(
    f"KE entering oleo:                  "
    f"{E_kin_oleo_start / 1000:.3f} kJ"
)

print(
    f"Equivalent oleo velocity:          "
    f"{V_oleo_0:.4f} m/s"
)


print()
print("--- OLEO GAS SYSTEM ---")

print(
    f"Piston diameter:                   "
    f"{D_piston * 1000:.2f} mm"
)

print(
    f"Piston area:                       "
    f"{A_piston:.7f} m^2"
)

print(
    f"Initial gas length:                "
    f"{L_gas_0 * 1000:.1f} mm"
)

print(
    f"Gas precharge, absolute:           "
    f"{P_gas_0_abs / 1e6:.3f} MPa"
)

print(
    f"Gas precharge, gauge:              "
    f"{(P_gas_0_abs - P_atm) / 1e6:.3f} MPa"
)

print(
    f"Polytropic exponent:               "
    f"{n_poly:.2f}"
)


print()
print("--- SMOOTH HYDRAULIC SYSTEM V0.3 ---")

print(
    f"Oil density:                       "
    f"{rho_oil:.1f} kg/m^3"
)

print(
    f"Discharge coefficient:             "
    f"{C_d:.3f}"
)

print(
    f"Initial equivalent orifice dia.:   "
    f"{d_orifice_start * 1000:.3f} mm"
)

print(
    f"Final equivalent orifice dia.:     "
    f"{d_orifice_end * 1000:.3f} mm"
)

print(
    f"Initial orifice area:              "
    f"{A_orifice_start * 1e6:.2f} mm^2"
)

print(
    f"Final orifice area:                "
    f"{A_orifice_end * 1e6:.2f} mm^2"
)

print(
    f"Initial damping coefficient:       "
    f"{C_h_start:.2f} N/(m/s)^2"
)

print(
    f"Final damping coefficient:         "
    f"{C_h_end:.2f} N/(m/s)^2"
)


print()
print("--- HAND-ANALYSIS TARGETS ---")

print(
    f"Required oleo stroke:              "
    f"{x_hand * 1000:.2f} mm"
)

print(
    f"Available physical stroke:         "
    f"{x_available * 1000:.2f} mm"
)

print(
    f"LC1 limit load:                    "
    f"{F_limit / 1000:.2f} kN"
)

print(
    f"LC1 ultimate load:                 "
    f"{F_ultimate / 1000:.2f} kN"
)

print(
    f"Target oleo energy:                "
    f"{E_oleo_hand / 1000:.3f} kJ"
)

print(
    f"Target gas work:                   "
    f"{E_gas_hand / 1000:.3f} kJ"
)

print(
    f"Target hydraulic work:             "
    f"{E_hydraulic_hand / 1000:.3f} kJ"
)


print()
print("--- DYNAMIC SIMULATION ---")

print(
    f"Peak oleo compression:             "
    f"{x_peak * 1000:.3f} mm"
)

print(
    f"Stroke margin:                     "
    f"{stroke_margin * 1000:.3f} mm"
)

print(
    f"Time to peak compression:          "
    f"{t_peak:.5f} s"
)

print(
    f"Peak gas force:                    "
    f"{F_g_peak / 1000:.3f} kN"
)

print(
    f"Peak hydraulic force:              "
    f"{F_h_peak / 1000:.3f} kN"
)

print(
    f"Peak total oleo force:             "
    f"{F_total_peak / 1000:.3f} kN"
)

print(
    f"Peak upward acceleration:          "
    f"{upward_accel_g:.3f} g"
)

print(
    f"Gear reaction / aircraft W:        "
    f"{gear_reaction_ratio:.3f}"
)


print()
print("--- DYNAMIC ENERGY RESULTS ---")

print(
    f"Gas work:                          "
    f"{E_gas / 1000:.3f} kJ"
)

print(
    f"Hydraulic energy dissipated:       "
    f"{E_hydraulic / 1000:.3f} kJ"
)

print(
    f"Gravity/lift work over oleo:       "
    f"{E_external / 1000:.3f} kJ"
)

print(
    f"Energy balance residual:           "
    f"{energy_residual:.6f} J"
)


print()
print("--- CHECKS ---")


if bottom_event_occurred:

    print(
        "Stroke / bottoming:                "
        "FAIL — STRUT BOTTOMED"
    )

elif x_peak <= x_available:

    print(
        "Stroke / bottoming:                "
        "PASS"
    )

else:

    print(
        "Stroke / bottoming:                "
        "FAIL"
    )


if F_total_peak <= F_limit:

    print(
        "LC1 limit-load check:              "
        "PASS"
    )

else:

    print(
        "LC1 limit-load check:              "
        "FAIL"
    )


if F_total_peak <= F_ultimate:

    print(
        "LC1 ultimate-load check:           "
        "PASS"
    )

else:

    print(
        "LC1 ultimate-load check:           "
        "FAIL"
    )


stroke_difference = (
    x_peak
    - x_hand
)

print(
    f"Dynamic vs hand stroke:            "
    f"{stroke_difference * 1000:+.3f} mm"
)


hydraulic_difference = (
    E_hydraulic
    - E_hydraulic_hand
)

print(
    f"Dynamic vs hand hydraulic E:       "
    f"{hydraulic_difference:+.2f} J"
)


print()

print("=" * 68)


# ============================================================
# 19. PLOTS
# ============================================================


# ------------------------------------------------------------
# Figure 1 — Oleo compression
# ------------------------------------------------------------

plt.figure(
    figsize=(8, 5)
)

plt.plot(
    t,
    x * 1000
)

plt.axhline(
    x_hand * 1000,
    linestyle="--",
    label="Hand-analysis stroke"
)

plt.axhline(
    x_available * 1000,
    linestyle=":",
    label="Available stroke"
)

plt.xlabel(
    "Time (s)"
)

plt.ylabel(
    "Oleo Compression (mm)"
)

plt.title(
    "Oleo Compression vs Time"
)

plt.legend()

plt.grid(True)

plt.tight_layout()


# ------------------------------------------------------------
# Figure 2 — Compression velocity
# ------------------------------------------------------------

plt.figure(
    figsize=(8, 5)
)

plt.plot(
    t,
    v
)

plt.xlabel(
    "Time (s)"
)

plt.ylabel(
    "Compression Velocity (m/s)"
)

plt.title(
    "Oleo Compression Velocity"
)

plt.grid(True)

plt.tight_layout()


# ------------------------------------------------------------
# Figure 3 — Force history
# ------------------------------------------------------------

plt.figure(
    figsize=(8, 5)
)

plt.plot(
    t,
    F_g / 1000,
    label="Gas force"
)

plt.plot(
    t,
    F_h / 1000,
    label="Hydraulic force"
)

plt.plot(
    t,
    F_total / 1000,
    label="Total oleo force"
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
    "Oleo Force History"
)

plt.legend()

plt.grid(True)

plt.tight_layout()


# ------------------------------------------------------------
# Figure 4 — Force vs stroke
# ------------------------------------------------------------

plt.figure(
    figsize=(8, 5)
)

plt.plot(
    x * 1000,
    F_g / 1000,
    label="Gas"
)

plt.plot(
    x * 1000,
    F_h / 1000,
    label="Hydraulic"
)

plt.plot(
    x * 1000,
    F_total / 1000,
    label="Total"
)

plt.axhline(
    F_limit / 1000,
    linestyle="--",
    label="LC1 limit"
)

plt.xlabel(
    "Oleo Compression (mm)"
)

plt.ylabel(
    "Force (kN)"
)

plt.title(
    "Oleo Force vs Stroke"
)

plt.legend()

plt.grid(True)

plt.tight_layout()


# ------------------------------------------------------------
# Figure 5 — Vertical acceleration
# ------------------------------------------------------------

plt.figure(
    figsize=(8, 5)
)

plt.plot(
    t,
    acceleration / g
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
    "Equivalent Sprung-Mass Vertical Acceleration"
)

plt.grid(True)

plt.tight_layout()


# ------------------------------------------------------------
# Figure 6 — Smooth metering schedule
# ------------------------------------------------------------

plt.figure(
    figsize=(8, 5)
)

plt.plot(
    x * 1000,
    d_orifice_history * 1000
)

plt.xlabel(
    "Oleo Compression (mm)"
)

plt.ylabel(
    "Equivalent Orifice Diameter (mm)"
)

plt.title(
    "Smooth Hydraulic Metering Schedule"
)

plt.grid(True)

plt.tight_layout()


# ------------------------------------------------------------
# Figure 7 — Hydraulic coefficient vs stroke
# ------------------------------------------------------------

plt.figure(
    figsize=(8, 5)
)

plt.plot(
    x * 1000,
    C_h_history
)

plt.xlabel(
    "Oleo Compression (mm)"
)

plt.ylabel(
    "Hydraulic Coefficient [N/(m/s)^2]"
)

plt.title(
    "Hydraulic Damping Coefficient vs Stroke"
)

plt.grid(True)

plt.tight_layout()


plt.show()