"""
Landing_Gear_Design_Project
Phase 2D2 — Outer Oleo Barrel Preliminary Structural + Pressure Sizing

Purpose
-------
Preliminary sizing of the outer oleo barrel using:
1) the frozen Phase 2C upper-interface structural resultants, and
2) internal oleo pressure from the frozen Phase 1 gas model.

This is a screening analysis only. It does not yet include:
- gland-thread / snap-ring / retaining-groove local stresses,
- bushing bearing pressure,
- trunnion/lug local geometry,
- fatigue,
- fracture mechanics,
- corrosion / plating effects,
- detailed FEA.

Material baseline
-----------------
300M steel screening properties:
    E   = 205 GPa
    nu  = 0.28
    rho = 7870 kg/m^3
    Sy  = 1517 MPa
    Su  = 1862 MPa

Pressure model
--------------
Frozen Phase 1 gas law:

    P_abs(x) = P0_abs * [ L0 / (L0 - x) ]^n

Gauge pressure:
    p_g = P_abs - P_atm

Two pressure levels are reported:
- Physical-stroke service screen at x = 230 mm
- V0.5b virtual-stroke diagnostic at x = 240.779 mm

The physical-stroke pressure is conservatively combined with every Phase 2C
structural load case. This is intentionally conservative because the side/braking
loads and maximum oleo pressure are not guaranteed to occur simultaneously.

The V0.5b virtual pressure is checked separately with the corresponding vertical
strut force only, so we do not manufacture a nonphysical combined load case.

Thick-cylinder stress
---------------------
Because the wall may not be "thin" relative to the barrel radius, Lamé stresses
are used rather than a thin-wall approximation.

For inner radius a and outer radius b, with gauge internal pressure p and zero
external pressure:

    A_L = p*a^2 / (b^2 - a^2)
    B_L = p*a^2*b^2 / (b^2 - a^2)

    sigma_r     = A_L - B_L/r^2
    sigma_theta = A_L + B_L/r^2

Closed-end pressure axial stress:

    sigma_z,p = A_L

The global strut loads add:
    axial compression  -N/A
    bending            +/- M*r/I
    torsion            T*r/J

3-D von Mises:

    vm = sqrt(
        0.5 * [
            (st-sr)^2 + (sr-sz)^2 + (sz-st)^2
        ]
        + 3*tau^2
    )
"""

import csv
import math
from pathlib import Path


# =============================================================================
# 1. MATERIAL
# =============================================================================

E = 205e9
nu = 0.28
rho = 7870.0

Sy = 1517e6
Su = 1862e6

tau_y_allow = Sy / math.sqrt(3.0)
tau_u_allow = Su / math.sqrt(3.0)


# =============================================================================
# 2. FROZEN PHASE 1 GAS MODEL
# =============================================================================

P_atm = 101_325.0
P0_abs = 2.336e6
L0_gas = 0.350
n_gas = 1.30

x_physical = 0.230
x_virtual = 0.240779

D_effective_piston = 0.058
A_effective_piston = (
    math.pi
    * D_effective_piston**2
    / 4.0
)


def gas_pressure_gauge(x):
    if x >= L0_gas:
        raise ValueError(
            "Compression exceeds initial gas length."
        )

    P_abs = (
        P0_abs
        * (
            L0_gas
            / (L0_gas - x)
        )**n_gas
    )

    return P_abs - P_atm


p_physical = gas_pressure_gauge(
    x_physical
)

p_virtual = gas_pressure_gauge(
    x_virtual
)

F_virtual_strut = (
    p_virtual
    * A_effective_piston
)


# =============================================================================
# 3. BARREL GEOMETRY SWEEP
# =============================================================================

# IMPORTANT:
# Barrel ID is not yet frozen. The 58 mm Phase 1 piston diameter is an effective
# hydraulic diameter, not a guaranteed finished structural OD.
#
# Therefore we sweep several provisional barrel IDs rather than inventing one.
barrel_ID_values_mm = [
    62.0,
    64.0,
    66.0,
    68.0,
    70.0,
]

wall_min_mm = 2.0
wall_max_mm = 8.0
wall_step_mm = 0.25

# Working packaging candidate used only for detailed reporting.
working_ID_mm = 64.0
working_wall_mm = 5.0


# =============================================================================
# 4. READ PHASE 2C RESULTANTS
# =============================================================================

here = Path(__file__).resolve().parent

candidate_paths = [
    here / "phase2_internal_loads.csv",
    here.parent / "phase2_structures" / "phase2_internal_loads.csv",
]

phase2_csv = None

for path in candidate_paths:
    if path.exists():
        phase2_csv = path
        break

if phase2_csv is None:
    raise FileNotFoundError(
        "Could not find phase2_internal_loads.csv. "
        "Run phase2_internal_loads.py first."
    )


def read_upper_resultants(path):
    data = {
        "limit": {},
        "ultimate": {},
    }

    with path.open(
        "r",
        newline="",
        encoding="utf-8",
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:
            level = row["level"]
            case = row["case"]

            data[level][case] = {
                "Nc_kN": float(row["U_Nc_kN"]),
                "Vx_kN": float(row["U_Vx_kN"]),
                "Vy_kN": float(row["U_Vy_kN"]),
                "Mb_kNm": float(row["U_Mb_kNm"]),
                "Tz_kNm": float(row["U_Tz_kNm"]),
            }

    return data


upper_loads = read_upper_resultants(
    phase2_csv
)


# =============================================================================
# 5. SECTION PROPERTIES
# =============================================================================

def section_properties(
    ID_m,
    wall_m,
):
    a = ID_m / 2.0
    b = a + wall_m

    Do = 2.0 * b

    A = math.pi * (
        b**2 - a**2
    )

    I = math.pi / 4.0 * (
        b**4 - a**4
    )

    J = math.pi / 2.0 * (
        b**4 - a**4
    )

    mass_per_m = (
        rho * A
    )

    return {
        "a_m": a,
        "b_m": b,
        "OD_m": Do,
        "A_m2": A,
        "I_m4": I,
        "J_m4": J,
        "mass_per_m_kg": mass_per_m,
    }


# =============================================================================
# 6. THICK-CYLINDER + GLOBAL LOAD STRESS
# =============================================================================

def lame_constants(
    p,
    a,
    b,
):
    denom = (
        b**2 - a**2
    )

    A_L = (
        p * a**2 / denom
    )

    B_L = (
        p * a**2 * b**2
        / denom
    )

    return A_L, B_L


def vm_3d(
    sigma_r,
    sigma_theta,
    sigma_z,
    tau_ztheta,
):
    return math.sqrt(
        0.5
        * (
            (sigma_theta - sigma_r)**2
            + (sigma_r - sigma_z)**2
            + (sigma_z - sigma_theta)**2
        )
        + 3.0 * tau_ztheta**2
    )


def evaluate_load_case(
    section,
    load,
    p_internal,
):
    a = section["a_m"]
    b = section["b_m"]
    A = section["A_m2"]
    I = section["I_m4"]
    J = section["J_m4"]

    N = abs(
        load["Nc_kN"]
    ) * 1e3

    V = math.hypot(
        load["Vx_kN"],
        load["Vy_kN"],
    ) * 1e3

    M = abs(
        load["Mb_kNm"]
    ) * 1e3

    T = abs(
        load["Tz_kNm"]
    ) * 1e3

    A_L, B_L = lame_constants(
        p_internal,
        a,
        b,
    )

    sigma_z_pressure = A_L

    candidates = []

    for surface, r in (
        ("inner", a),
        ("outer", b),
    ):

        sigma_r = (
            A_L
            - B_L / r**2
        )

        sigma_theta = (
            A_L
            + B_L / r**2
        )

        tau_torsion = (
            T * r / J
        )

        for bending_side in (
            -1.0,
            +1.0,
        ):

            sigma_z = (
                sigma_z_pressure
                - N / A
                + bending_side
                * M * r / I
            )

            vm = vm_3d(
                sigma_r,
                sigma_theta,
                sigma_z,
                tau_torsion,
            )

            candidates.append({
                "surface": surface,
                "bending_side": bending_side,
                "sigma_r_Pa": sigma_r,
                "sigma_theta_Pa": sigma_theta,
                "sigma_z_Pa": sigma_z,
                "tau_torsion_Pa": tau_torsion,
                "vm_Pa": vm,
            })

    worst = max(
        candidates,
        key=lambda x: x["vm_Pa"],
    )

    # Separate conservative transverse-shear screen.
    tau_transverse_screen = (
        2.0 * V / A
    )

    return {
        **worst,
        "tau_transverse_screen_Pa": tau_transverse_screen,
    }


# =============================================================================
# 7. V0.5b PRESSURE DIAGNOSTIC
# =============================================================================

def evaluate_virtual_diagnostic(
    section,
):
    """
    V0.5b diagnostic:
        pressure = p_virtual
        axial compression = corresponding peak strut force
        no artificial side/braking moment is added.
    """

    load = {
        "Nc_kN": F_virtual_strut / 1000.0,
        "Vx_kN": 0.0,
        "Vy_kN": 0.0,
        "Mb_kNm": 0.0,
        "Tz_kNm": 0.0,
    }

    return evaluate_load_case(
        section,
        load,
        p_virtual,
    )


# =============================================================================
# 8. FULL DESIGN EVALUATION
# =============================================================================

def evaluate_design(
    ID_mm,
    wall_mm,
):
    section = section_properties(
        ID_mm / 1000.0,
        wall_mm / 1000.0,
    )

    rows = []

    for level in (
        "limit",
        "ultimate",
    ):

        for case_name, load in upper_loads[level].items():

            state = evaluate_load_case(
                section,
                load,
                p_physical,
            )

            rows.append({
                "level": level,
                "case": case_name,
                **state,
            })

    limit_rows = [
        row
        for row in rows
        if row["level"] == "limit"
    ]

    ultimate_rows = [
        row
        for row in rows
        if row["level"] == "ultimate"
    ]

    worst_limit = max(
        limit_rows,
        key=lambda row: row["vm_Pa"],
    )

    worst_ultimate = max(
        ultimate_rows,
        key=lambda row: row["vm_Pa"],
    )

    worst_limit_shear = max(
        limit_rows,
        key=lambda row: row[
            "tau_transverse_screen_Pa"
        ],
    )

    worst_ultimate_shear = max(
        ultimate_rows,
        key=lambda row: row[
            "tau_transverse_screen_Pa"
        ],
    )

    virtual_state = evaluate_virtual_diagnostic(
        section
    )

    MS_limit_yield = (
        Sy / worst_limit["vm_Pa"]
        - 1.0
    )

    MS_ultimate = (
        Su / worst_ultimate["vm_Pa"]
        - 1.0
    )

    MS_limit_shear = (
        tau_y_allow
        / worst_limit_shear[
            "tau_transverse_screen_Pa"
        ]
        - 1.0
    )

    MS_ultimate_shear = (
        tau_u_allow
        / worst_ultimate_shear[
            "tau_transverse_screen_Pa"
        ]
        - 1.0
    )

    MS_virtual_vs_yield = (
        Sy / virtual_state["vm_Pa"]
        - 1.0
    )

    passes = all([
        MS_limit_yield >= 0.0,
        MS_ultimate >= 0.0,
        MS_limit_shear >= 0.0,
        MS_ultimate_shear >= 0.0,
        MS_virtual_vs_yield >= 0.0,
    ])

    return {
        "ID_mm": ID_mm,
        "wall_mm": wall_mm,
        "OD_mm": (
            section["OD_m"]
            * 1000.0
        ),
        "A_mm2": (
            section["A_m2"]
            * 1e6
        ),
        "I_mm4": (
            section["I_m4"]
            * 1e12
        ),
        "J_mm4": (
            section["J_m4"]
            * 1e12
        ),
        "mass_per_m_kg": section["mass_per_m_kg"],

        "physical_pressure_MPa": (
            p_physical / 1e6
        ),
        "virtual_pressure_MPa": (
            p_virtual / 1e6
        ),

        "limit_governing_case": worst_limit["case"],
        "limit_governing_surface": worst_limit["surface"],
        "limit_vm_MPa": (
            worst_limit["vm_Pa"]
            / 1e6
        ),
        "MS_limit_yield": MS_limit_yield,

        "ultimate_governing_case": worst_ultimate["case"],
        "ultimate_governing_surface": worst_ultimate["surface"],
        "ultimate_vm_MPa": (
            worst_ultimate["vm_Pa"]
            / 1e6
        ),
        "MS_ultimate": MS_ultimate,

        "limit_tau_screen_MPa": (
            worst_limit_shear[
                "tau_transverse_screen_Pa"
            ]
            / 1e6
        ),
        "MS_limit_shear": MS_limit_shear,

        "ultimate_tau_screen_MPa": (
            worst_ultimate_shear[
                "tau_transverse_screen_Pa"
            ]
            / 1e6
        ),
        "MS_ultimate_shear": MS_ultimate_shear,

        "virtual_vm_MPa": (
            virtual_state["vm_Pa"]
            / 1e6
        ),
        "virtual_governing_surface": virtual_state["surface"],
        "MS_virtual_vs_yield": MS_virtual_vs_yield,

        "PASS": passes,
    }


# =============================================================================
# 9. SWEEP
# =============================================================================

n_wall_steps = int(
    round(
        (wall_max_mm - wall_min_mm)
        / wall_step_mm
    )
) + 1

wall_values_mm = [
    wall_min_mm
    + i * wall_step_mm
    for i in range(n_wall_steps)
]

designs = []

for ID_mm in barrel_ID_values_mm:

    for wall_mm in wall_values_mm:

        designs.append(
            evaluate_design(
                ID_mm,
                wall_mm,
            )
        )


# =============================================================================
# 10. WORKING CANDIDATE + REGRESSION
# =============================================================================

def get_design(
    ID_mm,
    wall_mm,
):
    for row in designs:
        if (
            abs(row["ID_mm"] - ID_mm) < 1e-12
            and abs(row["wall_mm"] - wall_mm) < 1e-12
        ):
            return row

    raise KeyError(
        "Requested barrel design not found."
    )


working = get_design(
    working_ID_mm,
    working_wall_mm,
)


def assert_close(
    label,
    calculated,
    reference,
    tolerance,
):
    error = abs(
        calculated - reference
    )

    assert error <= tolerance, (
        f"{label} regression failed: "
        f"calculated={calculated:.6f}, "
        f"reference={reference:.6f}, "
        f"error={error:.6f}"
    )


assert_close(
    "Physical-stroke pressure [MPa]",
    p_physical / 1e6,
    9.292136857,
    1e-6,
)

assert_close(
    "Virtual-stroke pressure [MPa]",
    p_virtual / 1e6,
    10.514733500,
    1e-6,
)

assert_close(
    "64x5 limit VM [MPa]",
    working["limit_vm_MPa"],
    398.397402,
    1e-3,
)

assert_close(
    "64x5 ultimate VM [MPa]",
    working["ultimate_vm_MPa"],
    595.204681,
    1e-3,
)


# =============================================================================
# 11. CSV OUTPUT
# =============================================================================

output_csv = (
    here
    / "phase2_barrel_sizing.csv"
)

with output_csv.open(
    "w",
    newline="",
    encoding="utf-8",
) as file:

    writer = csv.DictWriter(
        file,
        fieldnames=list(
            designs[0].keys()
        ),
    )

    writer.writeheader()
    writer.writerows(
        designs
    )


# =============================================================================
# 12. CONSOLE REPORT
# =============================================================================

print()
print("=" * 94)
print(
    " PHASE 2D2 — OUTER OLEO BARREL "
    "PRELIMINARY STRUCTURAL + PRESSURE SIZING"
)
print("=" * 94)

print()
print("--- INPUT CONNECTION ---")
print(
    f"Phase 2C result file:             "
    f"{phase2_csv}"
)

print()
print("--- PRESSURE BASIS ---")
print(
    f"Physical stroke:                  "
    f"{x_physical*1000:.3f} mm"
)
print(
    f"Gauge pressure at physical stroke:"
    f" {p_physical/1e6:.3f} MPa"
)
print(
    f"V0.5b virtual stroke:             "
    f"{x_virtual*1000:.3f} mm"
)
print(
    f"Gauge pressure at virtual stroke: "
    f"{p_virtual/1e6:.3f} MPa"
)
print(
    f"Corresponding virtual strut force:"
    f" {F_virtual_strut/1000:.3f} kN"
)

print()
print("--- BARREL DESIGN SWEEP ---")
print(
    f"ID values:                        "
    f"{', '.join(f'{x:.0f}' for x in barrel_ID_values_mm)} mm"
)
print(
    f"Wall sweep:                       "
    f"{wall_min_mm:.2f} to "
    f"{wall_max_mm:.2f} mm"
)
print(
    "Physical-stroke pressure is combined "
    "conservatively with every structural LC."
)

print()
print("--- MINIMUM PASSING WALL BY ID ---")
print(
    f"{'ID mm':>8}"
    f"{'wall mm':>10}"
    f"{'OD mm':>10}"
    f"{'Limit VM':>12}"
    f"{'Ult VM':>12}"
    f"{'Virt VM':>12}"
    f"{'Gov LC':>10}"
)
print("-" * 76)

for ID_mm in barrel_ID_values_mm:

    subset = [
        row
        for row in designs
        if (
            abs(
                row["ID_mm"] - ID_mm
            ) < 1e-12
            and row["PASS"]
        )
    ]

    if subset:

        first = min(
            subset,
            key=lambda row: row["wall_mm"],
        )

        print(
            f"{first['ID_mm']:>8.0f}"
            f"{first['wall_mm']:>10.2f}"
            f"{first['OD_mm']:>10.1f}"
            f"{first['limit_vm_MPa']:>12.1f}"
            f"{first['ultimate_vm_MPa']:>12.1f}"
            f"{first['virtual_vm_MPa']:>12.1f}"
            f"{first['ultimate_governing_case']:>10}"
        )

    else:
        print(
            f"{ID_mm:>8.0f}"
            f"{'NO PASS':>10}"
        )

print()
print(
    "--- WORKING CANDIDATE: "
    "64 mm ID x 5 mm WALL ---"
)
print(
    f"Outer diameter:                   "
    f"{working['OD_mm']:.1f} mm"
)
print(
    f"Metal area:                       "
    f"{working['A_mm2']:.1f} mm^2"
)
print(
    f"I:                                "
    f"{working['I_mm4']:.0f} mm^4"
)
print(
    f"J:                                "
    f"{working['J_mm4']:.0f} mm^4"
)
print(
    f"Mass per metre:                   "
    f"{working['mass_per_m_kg']:.3f} kg/m"
)

print()
print(
    f"Limit governing case:             "
    f"{working['limit_governing_case']}"
)
print(
    f"Limit governing surface:          "
    f"{working['limit_governing_surface']}"
)
print(
    f"Limit VM stress:                  "
    f"{working['limit_vm_MPa']:.1f} MPa"
)
print(
    f"Limit yield margin:               "
    f"{working['MS_limit_yield']:+.3f}"
)

print()
print(
    f"Ultimate governing case:          "
    f"{working['ultimate_governing_case']}"
)
print(
    f"Ultimate governing surface:       "
    f"{working['ultimate_governing_surface']}"
)
print(
    f"Ultimate VM screening stress:     "
    f"{working['ultimate_vm_MPa']:.1f} MPa"
)
print(
    f"Ultimate strength margin:         "
    f"{working['MS_ultimate']:+.3f}"
)

print()
print(
    f"Limit transverse shear screen:    "
    f"{working['limit_tau_screen_MPa']:.1f} MPa"
)
print(
    f"Ultimate transverse shear screen: "
    f"{working['ultimate_tau_screen_MPa']:.1f} MPa"
)

print()
print("--- V0.5b PRESSURE DIAGNOSTIC ---")
print(
    f"Virtual diagnostic VM stress:     "
    f"{working['virtual_vm_MPa']:.1f} MPa"
)
print(
    f"Virtual governing surface:        "
    f"{working['virtual_governing_surface']}"
)
print(
    f"Margin vs yield:                  "
    f"{working['MS_virtual_vs_yield']:+.3f}"
)

print()
print(
    f"Preliminary screen:               "
    f"{'PASS' if working['PASS'] else 'FAIL'}"
)
print()
print(
    "NOTE: The 64 mm barrel ID is a provisional packaging "
    "assumption, not a frozen interface dimension."
)
print(
    "Local gland/bushing/trunnion geometry is expected to "
    "be more critical than the smooth barrel wall."
)

print()
print("Regression checks:                PASS")
print(
    f"CSV written to:                   "
    f"{output_csv.name}"
)
print("=" * 94)
