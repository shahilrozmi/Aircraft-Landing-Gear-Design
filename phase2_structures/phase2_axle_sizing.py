"""
Landing_Gear_Design_Project
Phase 2D8 — Axle / Spindle Preliminary Structural Sizing

Purpose
-------
Preliminarily size the smooth ROOT section of the main-wheel axle/spindle using
the frozen Phase 2C limit and ultimate load cases.

This script reads phase2_internal_loads.csv directly. It reconstructs the axle
resultants from Fx, Fy, Fz and the frozen Phase 2B geometry rather than pasting
moments or stresses from chat.

Architecture / scope
--------------------
- Axle axis: +y
- Root at the lower-strut / axle intersection A
- Wheel center located e = 120 mm outboard of A
- Tire loaded radius r_t = 175 mm
- Hollow circular 300M-steel root section is used for preliminary screening
- Bearing seats, brake flange, shoulders, threads/nut, fillets, and wheel-bearing
  spacing are NOT yet defined

Axle resultants at A
--------------------
    N_y = F_y
    V_x = F_x
    V_z = F_z

    M_x = e*F_z + r_t*F_y
    M_z = -e*F_x

    M_b = sqrt(M_x^2 + M_z^2)

The contact-patch geometric moment about the axle axis is

    T_y,geom = -r_t*F_x

Important torsion rule
----------------------
LC5 braking:
    T_y,geom is treated as CONFIRMED structural brake torque because the brake
    system transfers wheel torque into the axle/strut.

LC2A / LC2B spin-up:
    T_y,geom is reported, but is NOT automatically applied as shaft structural
    torsion in the baseline stress calculation. During wheel spin-up, this moment
    participates in wheel angular acceleration and requires a wheel/bearing
    rotational FBD before it can be assigned as axle torsion.

A separate LC2 torsion-sensitivity result is reported for the working axle so
that the design consequence is visible without silently changing the load case.

Stress screen
-------------
For a hollow circular section:

    A = pi/4  * (Do^2 - Di^2)
    I = pi/64 * (Do^4 - Di^4)
    J = pi/32 * (Do^4 - Di^4)

Surface normal stress:
    sigma = N/A +/- M_b*c/I

Torsional shear:
    tau_T = T*c/J

Surface von Mises:
    sigma_VM = sqrt(sigma^2 + 3*tau_T^2)

A separate conservative transverse-shear screen is retained:

    tau_V,screen = 2*V/A

This shear screen is NOT simply added to the outer-surface bending/torsion
von-Mises state because the peak transverse-shear distribution is not coincident
with the circular-section outer-surface bending maximum.

Stiffness screen
----------------
For the WORKING candidate only, the axle is idealized as a uniform cantilever of
length e. Wheel-center deflection is calculated from the actual wheel-center force
and contact-patch tip couple:

    delta_x = F_x*e^3/(3EI)

    delta_z = F_z*e^3/(3EI)
              + (r_t*F_y)*e^2/(2EI)

LC5 torsional twist:
    theta_y = T*e/(GJ)

No wheel-alignment allowable is imposed yet.
"""

import csv
import math
from pathlib import Path


# =============================================================================
# 1. PRELIMINARY MATERIAL — 300M STEEL
# =============================================================================

E_Pa = 205e9
G_Pa = 80e9
rho_kg_m3 = 7870.0

Sy_Pa = 1517e6
Su_Pa = 1862e6

tau_y_Pa = Sy_Pa / math.sqrt(3.0)
tau_u_Pa = Su_Pa / math.sqrt(3.0)


# =============================================================================
# 2. FROZEN PHASE 2B AXLE GEOMETRY
# =============================================================================

e_m = 0.120
rt_m = 0.175


# =============================================================================
# 3. SECTION SWEEP
# =============================================================================

OD_values_mm = [
    40.0,
    45.0,
    50.0,
    55.0,
    60.0,
]

wall_min_mm = 1.50
wall_max_mm = 10.00
wall_step_mm = 0.25

# Preliminary working ROOT section only.
working_OD_mm = 50.0
working_wall_mm = 8.0


# =============================================================================
# 4. READ PHASE 2C LOAD FILE
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


def read_force_cases(path):
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
                "Fx_kN": float(row["Fx_kN"]),
                "Fy_kN": float(row["Fy_kN"]),
                "Fz_kN": float(row["Fz_kN"]),
            }

    return data


loads = read_force_cases(
    phase2_csv
)


# =============================================================================
# 5. AXLE RESULTANTS
# =============================================================================

def axle_resultants(
    force,
    case_name,
    force_spinup_torsion=False,
):
    Fx = force["Fx_kN"]
    Fy = force["Fy_kN"]
    Fz = force["Fz_kN"]

    Ny_kN = Fy
    Vx_kN = Fx
    Vz_kN = Fz

    Mx_kNm = (
        e_m * Fz
        + rt_m * Fy
    )

    Mz_kNm = (
        -e_m * Fx
    )

    Mb_kNm = math.hypot(
        Mx_kNm,
        Mz_kNm,
    )

    Ty_geom_kNm = (
        -rt_m * Fx
    )

    if case_name == "LC5":
        Ty_structural_kNm = Ty_geom_kNm

    elif (
        force_spinup_torsion
        and case_name in (
            "LC2A",
            "LC2B",
        )
    ):
        Ty_structural_kNm = Ty_geom_kNm

    else:
        Ty_structural_kNm = 0.0

    V_kN = math.hypot(
        Vx_kN,
        Vz_kN,
    )

    return {
        "Ny_kN": Ny_kN,
        "Vx_kN": Vx_kN,
        "Vz_kN": Vz_kN,
        "V_kN": V_kN,

        "Mx_kNm": Mx_kNm,
        "Mz_kNm": Mz_kNm,
        "Mb_kNm": Mb_kNm,

        "Ty_geom_kNm": Ty_geom_kNm,
        "Ty_structural_kNm":
            Ty_structural_kNm,
    }


# =============================================================================
# 6. SECTION PROPERTIES
# =============================================================================

def section_properties(
    OD_mm,
    wall_mm,
):
    ID_mm = (
        OD_mm
        - 2.0 * wall_mm
    )

    if ID_mm <= 0.0:
        raise ValueError(
            "Axle ID must remain positive."
        )

    Do = OD_mm / 1000.0
    Di = ID_mm / 1000.0

    A = (
        math.pi
        / 4.0
        * (
            Do**2
            - Di**2
        )
    )

    I = (
        math.pi
        / 64.0
        * (
            Do**4
            - Di**4
        )
    )

    J = (
        math.pi
        / 32.0
        * (
            Do**4
            - Di**4
        )
    )

    c = Do / 2.0

    return {
        "OD_mm": OD_mm,
        "ID_mm": ID_mm,
        "wall_mm": wall_mm,
        "A_m2": A,
        "I_m4": I,
        "J_m4": J,
        "c_m": c,
        "mass_per_m_kg":
            rho_kg_m3 * A,
    }


# =============================================================================
# 7. STRESS EVALUATION
# =============================================================================

def evaluate_stress(
    section,
    resultants,
):
    A = section["A_m2"]
    I = section["I_m4"]
    J = section["J_m4"]
    c = section["c_m"]

    N_N = (
        resultants["Ny_kN"]
        * 1000.0
    )

    V_N = (
        resultants["V_kN"]
        * 1000.0
    )

    M_Nm = (
        resultants["Mb_kNm"]
        * 1000.0
    )

    T_Nm = (
        resultants[
            "Ty_structural_kNm"
        ]
        * 1000.0
    )

    sigma_axial = (
        N_N / A
    )

    sigma_bending = (
        M_Nm * c / I
    )

    tau_torsion = (
        T_Nm * c / J
    )

    normal_candidates = [
        sigma_axial
        + sigma_bending,
        sigma_axial
        - sigma_bending,
    ]

    sigma_worst = max(
        normal_candidates,
        key=lambda x: abs(x),
    )

    vm = math.sqrt(
        sigma_worst**2
        + 3.0 * tau_torsion**2
    )

    tau_transverse_screen = (
        2.0 * V_N / A
    )

    return {
        "sigma_axial_MPa":
            sigma_axial / 1e6,

        "sigma_bending_MPa":
            sigma_bending / 1e6,

        "tau_torsion_MPa":
            tau_torsion / 1e6,

        "vm_MPa":
            vm / 1e6,

        "tau_transverse_screen_MPa":
            tau_transverse_screen / 1e6,
    }


# =============================================================================
# 8. DESIGN EVALUATION
# =============================================================================

def evaluate_design(
    OD_mm,
    wall_mm,
):
    section = section_properties(
        OD_mm,
        wall_mm,
    )

    rows = []

    for level in (
        "limit",
        "ultimate",
    ):

        for case_name, force in loads[level].items():

            resultants = axle_resultants(
                force,
                case_name,
                force_spinup_torsion=False,
            )

            stress = evaluate_stress(
                section,
                resultants,
            )

            rows.append({
                "level": level,
                "case": case_name,
                **resultants,
                **stress,
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

    gov_limit_vm = max(
        limit_rows,
        key=lambda row: row["vm_MPa"],
    )

    gov_ultimate_vm = max(
        ultimate_rows,
        key=lambda row: row["vm_MPa"],
    )

    gov_limit_shear = max(
        limit_rows,
        key=lambda row:
            row[
                "tau_transverse_screen_MPa"
            ],
    )

    gov_ultimate_shear = max(
        ultimate_rows,
        key=lambda row:
            row[
                "tau_transverse_screen_MPa"
            ],
    )

    MS_limit_yield = (
        Sy_Pa / 1e6
        / gov_limit_vm["vm_MPa"]
        - 1.0
    )

    MS_ultimate = (
        Su_Pa / 1e6
        / gov_ultimate_vm["vm_MPa"]
        - 1.0
    )

    MS_limit_shear = (
        tau_y_Pa / 1e6
        / gov_limit_shear[
            "tau_transverse_screen_MPa"
        ]
        - 1.0
    )

    MS_ultimate_shear = (
        tau_u_Pa / 1e6
        / gov_ultimate_shear[
            "tau_transverse_screen_MPa"
        ]
        - 1.0
    )

    passes = all([
        MS_limit_yield >= 0.0,
        MS_ultimate >= 0.0,
        MS_limit_shear >= 0.0,
        MS_ultimate_shear >= 0.0,
    ])

    return {
        **section,

        "limit_governing_case":
            gov_limit_vm["case"],
        "limit_vm_MPa":
            gov_limit_vm["vm_MPa"],
        "MS_limit_yield":
            MS_limit_yield,

        "ultimate_governing_case":
            gov_ultimate_vm["case"],
        "ultimate_vm_MPa":
            gov_ultimate_vm["vm_MPa"],
        "MS_ultimate":
            MS_ultimate,

        "limit_shear_governing_case":
            gov_limit_shear["case"],
        "limit_tau_screen_MPa":
            gov_limit_shear[
                "tau_transverse_screen_MPa"
            ],
        "MS_limit_shear":
            MS_limit_shear,

        "ultimate_shear_governing_case":
            gov_ultimate_shear["case"],
        "ultimate_tau_screen_MPa":
            gov_ultimate_shear[
                "tau_transverse_screen_MPa"
            ],
        "MS_ultimate_shear":
            MS_ultimate_shear,

        "PASS": passes,
    }


# =============================================================================
# 9. SWEEP
# =============================================================================

n_steps = int(
    round(
        (
            wall_max_mm
            - wall_min_mm
        )
        / wall_step_mm
    )
) + 1

wall_values_mm = [
    wall_min_mm
    + i * wall_step_mm
    for i in range(n_steps)
]

designs = []

for OD_mm in OD_values_mm:

    for wall_mm in wall_values_mm:

        if (
            OD_mm
            - 2.0 * wall_mm
            <= 0.0
        ):
            continue

        designs.append(
            evaluate_design(
                OD_mm,
                wall_mm,
            )
        )


# =============================================================================
# 10. WORKING CANDIDATE DETAILS
# =============================================================================

def get_design(
    OD_mm,
    wall_mm,
):
    for row in designs:
        if (
            abs(
                row["OD_mm"]
                - OD_mm
            ) < 1e-12
            and abs(
                row["wall_mm"]
                - wall_mm
            ) < 1e-12
        ):
            return row

    raise KeyError(
        "Requested axle design not found."
    )


working = get_design(
    working_OD_mm,
    working_wall_mm,
)


def working_case_rows(
    level,
    force_spinup_torsion=False,
):
    section = section_properties(
        working_OD_mm,
        working_wall_mm,
    )

    rows = []

    for case_name, force in loads[level].items():

        resultants = axle_resultants(
            force,
            case_name,
            force_spinup_torsion=
                force_spinup_torsion,
        )

        stress = evaluate_stress(
            section,
            resultants,
        )

        rows.append({
            "case": case_name,
            **resultants,
            **stress,
        })

    return rows


working_limit_cases = working_case_rows(
    "limit"
)

working_ultimate_cases = working_case_rows(
    "ultimate"
)

working_ultimate_spinup_sensitivity = (
    working_case_rows(
        "ultimate",
        force_spinup_torsion=True,
    )
)


# =============================================================================
# 11. WORKING-CANDIDATE STIFFNESS
# =============================================================================

def stiffness_response(
    force,
    case_name,
):
    section = section_properties(
        working_OD_mm,
        working_wall_mm,
    )

    I = section["I_m4"]
    J = section["J_m4"]

    Fx_N = (
        force["Fx_kN"]
        * 1000.0
    )

    Fy_N = (
        force["Fy_kN"]
        * 1000.0
    )

    Fz_N = (
        force["Fz_kN"]
        * 1000.0
    )

    # Contact-patch tip couple at wheel center.
    Mx_tip_Nm = (
        rt_m * Fy_N
    )

    dx_m = (
        Fx_N * e_m**3
        / (
            3.0 * E_Pa * I
        )
    )

    dz_m = (
        Fz_N * e_m**3
        / (
            3.0 * E_Pa * I
        )
        + Mx_tip_Nm * e_m**2
        / (
            2.0 * E_Pa * I
        )
    )

    d_resultant_m = math.hypot(
        dx_m,
        dz_m,
    )

    resultants = axle_resultants(
        force,
        case_name,
        force_spinup_torsion=False,
    )

    T_Nm = (
        resultants[
            "Ty_structural_kNm"
        ]
        * 1000.0
    )

    theta_rad = (
        T_Nm * e_m
        / (
            G_Pa * J
        )
    )

    return {
        "dx_mm": dx_m * 1000.0,
        "dz_mm": dz_m * 1000.0,
        "d_resultant_mm":
            d_resultant_m * 1000.0,
        "theta_deg":
            math.degrees(theta_rad),
    }


stiffness_rows = []

for level in (
    "limit",
    "ultimate",
):

    for case_name, force in loads[level].items():

        response = stiffness_response(
            force,
            case_name,
        )

        stiffness_rows.append({
            "level": level,
            "case": case_name,
            **response,
        })


gov_deflection = max(
    stiffness_rows,
    key=lambda row:
        row["d_resultant_mm"],
)

gov_twist = max(
    stiffness_rows,
    key=lambda row:
        abs(row["theta_deg"]),
)


# =============================================================================
# 12. PROCESS / IDENTITY CHECKS
# =============================================================================

section_check = section_properties(
    working_OD_mm,
    working_wall_mm,
)

assert abs(
    section_check["J_m4"]
    - 2.0
    * section_check["I_m4"]
) < 1e-20

# Confirm Phase 2C geometry identity at LC5:
# brake torque = r_t * |Fx|.
lc5_limit = axle_resultants(
    loads["limit"]["LC5"],
    "LC5",
)

assert abs(
    abs(
        lc5_limit[
            "Ty_structural_kNm"
        ]
    )
    - rt_m
    * abs(
        loads["limit"][
            "LC5"
        ]["Fx_kN"]
    )
) < 1e-12

# Confirm LC2 torsion is excluded in the baseline model.
lc2_baseline = axle_resultants(
    loads["limit"]["LC2A"],
    "LC2A",
    force_spinup_torsion=False,
)

assert abs(
    lc2_baseline[
        "Ty_structural_kNm"
    ]
) < 1e-15


# =============================================================================
# 13. CSV OUTPUT
# =============================================================================

output_csv = (
    here
    / "phase2_axle_sizing.csv"
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
# 14. CONSOLE REPORT
# =============================================================================

print()
print("=" * 106)
print(
    " PHASE 2D8 — AXLE / SPINDLE "
    "PRELIMINARY STRUCTURAL SIZING"
)
print("=" * 106)

print()
print("--- INPUT CONNECTION ---")
print(
    f"Phase 2C result file:             "
    f"{phase2_csv}"
)

print()
print("--- MATERIAL BASELINE: 300M STEEL ---")
print(
    f"E:                               "
    f"{E_Pa/1e9:.1f} GPa"
)
print(
    f"G:                               "
    f"{G_Pa/1e9:.1f} GPa"
)
print(
    f"Yield screening strength:         "
    f"{Sy_Pa/1e6:.0f} MPa"
)
print(
    f"Ultimate screening strength:      "
    f"{Su_Pa/1e6:.0f} MPa"
)

print()
print("--- FROZEN AXLE GEOMETRY ---")
print(
    f"Root-to-wheel-center offset e:    "
    f"{e_m*1000:.1f} mm"
)
print(
    f"Loaded tire radius r_t:           "
    f"{rt_m*1000:.1f} mm"
)
print(
    "LC5 geometric tire torque is treated as confirmed axle brake torque."
)
print(
    "LC2A/B geometric spin-up torque is reported but excluded from baseline shaft torsion."
)

print()
print("--- HOLLOW ROOT-SECTION SWEEP ---")
print(
    f"OD values:                        "
    f"{', '.join(f'{x:.0f}' for x in OD_values_mm)} mm"
)
print(
    f"Wall sweep:                       "
    f"{wall_min_mm:.2f} to "
    f"{wall_max_mm:.2f} mm"
)

print()
print("--- MINIMUM MATHEMATICAL PASSING WALL BY OD ---")
print(
    f"{'OD mm':>8}"
    f"{'t_min mm':>12}"
    f"{'ID mm':>10}"
    f"{'Limit VM':>12}"
    f"{'Ult VM':>12}"
    f"{'Gov LC':>10}"
)
print("-" * 68)

for OD_mm in OD_values_mm:

    subset = [
        row
        for row in designs
        if (
            abs(
                row["OD_mm"]
                - OD_mm
            ) < 1e-12
            and row["PASS"]
        )
    ]

    if subset:
        first = min(
            subset,
            key=lambda row:
                row["wall_mm"],
        )

        print(
            f"{first['OD_mm']:>8.0f}"
            f"{first['wall_mm']:>12.2f}"
            f"{first['ID_mm']:>10.1f}"
            f"{first['limit_vm_MPa']:>12.1f}"
            f"{first['ultimate_vm_MPa']:>12.1f}"
            f"{first['ultimate_governing_case']:>10}"
        )
    else:
        print(
            f"{OD_mm:>8.0f}"
            f"{'NO PASS':>12}"
        )

print()
print(
    "--- WORKING ROOT CANDIDATE: "
    f"{working_OD_mm:.0f} mm OD x "
    f"{working_wall_mm:.0f} mm WALL ---"
)
print(
    f"Inner diameter:                   "
    f"{working['ID_mm']:.1f} mm"
)
print(
    f"Area:                             "
    f"{working['A_m2']*1e6:.1f} mm^2"
)
print(
    f"I:                                "
    f"{working['I_m4']*1e12:.0f} mm^4"
)
print(
    f"J:                                "
    f"{working['J_m4']*1e12:.0f} mm^4"
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
    f"Ultimate VM stress:               "
    f"{working['ultimate_vm_MPa']:.1f} MPa"
)
print(
    f"Ultimate strength margin:         "
    f"{working['MS_ultimate']:+.3f}"
)

print()
print(
    f"Ultimate transverse shear screen: "
    f"{working['ultimate_tau_screen_MPa']:.1f} MPa"
)
print(
    f"Shear-screen governing case:      "
    f"{working['ultimate_shear_governing_case']}"
)

print()
print("--- WORKING CANDIDATE: ULTIMATE LOAD-CASE DETAILS ---")
print(
    f"{'Case':>8}"
    f"{'Mb kNm':>10}"
    f"{'Tstruct':>10}"
    f"{'Tgeom':>10}"
    f"{'VM MPa':>10}"
)
print("-" * 52)

for row in working_ultimate_cases:
    print(
        f"{row['case']:>8}"
        f"{row['Mb_kNm']:>10.3f}"
        f"{row['Ty_structural_kNm']:>10.3f}"
        f"{row['Ty_geom_kNm']:>10.3f}"
        f"{row['vm_MPa']:>10.1f}"
    )

print()
print("--- LC2 SPIN-UP TORSION SENSITIVITY ---")

baseline_lc2 = max(
    [
        row
        for row in working_ultimate_cases
        if row["case"] in (
            "LC2A",
            "LC2B",
        )
    ],
    key=lambda row:
        row["vm_MPa"],
)

sensitivity_lc2 = max(
    [
        row
        for row
        in working_ultimate_spinup_sensitivity
        if row["case"] in (
            "LC2A",
            "LC2B",
        )
    ],
    key=lambda row:
        row["vm_MPa"],
)

print(
    f"LC2 baseline VM, spin-up torsion excluded: "
    f"{baseline_lc2['vm_MPa']:.1f} MPa"
)
print(
    f"LC2 sensitivity VM, if Tgeom were imposed: "
    f"{sensitivity_lc2['vm_MPa']:.1f} MPa"
)
print(
    f"LC2 geometric spin-up moment magnitude:     "
    f"{abs(sensitivity_lc2['Ty_geom_kNm']):.3f} kN*m"
)
print(
    "Sensitivity only — NOT promoted to a structural torsion load case."
)

print()
print("--- WORKING-CANDIDATE STIFFNESS SCREEN ---")
print(
    f"Governing transverse-deflection case: "
    f"{gov_deflection['level']} "
    f"{gov_deflection['case']}"
)
print(
    f"Wheel-center resultant deflection:     "
    f"{gov_deflection['d_resultant_mm']:.3f} mm"
)
print(
    f"  x component:                         "
    f"{gov_deflection['dx_mm']:.3f} mm"
)
print(
    f"  z component:                         "
    f"{gov_deflection['dz_mm']:.3f} mm"
)
print(
    f"Governing confirmed torsional twist:   "
    f"{gov_twist['level']} "
    f"{gov_twist['case']}"
)
print(
    f"Axle torsional twist over 120 mm:       "
    f"{gov_twist['theta_deg']:.4f} deg"
)
print(
    "No wheel-alignment stiffness allowable is imposed yet."
)

print()
print("--- INTERPRETATION ---")
print(
    "The calculated minimum walls are mathematical strength minima only; "
    "they are not suitable final axle dimensions."
)
print(
    "Bearing seats, brake flange, root fillet, wheel nut/thread, fatigue, "
    "fretting, contact stresses, and manufacturing will control the final spindle detail."
)
print(
    f"The {working_OD_mm:.0f} x {working_wall_mm:.0f} mm section is a "
    "WORKING ROOT candidate only."
)

print()
print("Identity / consistency checks:    PASS")
print(
    f"CSV written to:                   "
    f"{output_csv.name}"
)
print("=" * 106)
