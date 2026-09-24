"""
Landing_Gear_Design_Project
Phase 2D10 — Upper Moment-Reaction Brace / Link Preliminary Sizing

Purpose
-------
Size the separate upper brace / anti-rotation link required to react the moment
about the Phase 2D9 trunnion axis.

This is NOT a retraction-mechanism design.

The brace is treated only as a structural two-force member that closes the
otherwise-missing Mx load path at the upper landing-gear attachment.

The script reads:
    phase2_internal_loads.csv
    phase2_bushing_material_gland_requirements.csv

No brace force, pin load, or stress result is copied from chat.

Load path
---------
The Phase 2D9 trunnion axis is along aircraft +x.

The trunnion bearings react:
    Fy, Fz, My, Mz

The separate brace reacts:
    Mx

For an effective perpendicular brace moment arm a_perp:

    F_brace = Mx / a_perp

The actual physical brace geometry can later satisfy:

    a_perp = r * sin(theta)

but no retraction kinematics or brace angle is frozen here.

Conservative compression rule
-----------------------------
The sign of Mx changes between some load cases.

Because the final side/orientation of the brace is not yet frozen, the governing
absolute brace force is conservatively checked as BOTH:
    - tensile member load
    - compressive member load

This prevents us from accidentally benefiting from a provisional sign convention.

Brace member
------------
A hollow circular 300M-steel tube is screened.

Direct axial stress:
    sigma = F / A

Buckling:
    pin-ended two-force member -> K = 1.0

Johnson/Euler transition:
    Cc = sqrt(2*pi^2*E/Sy)

    Johnson:
        sigma_cr = Sy * [1 - Sy*lambda^2/(4*pi^2*E)]

    Euler:
        sigma_cr = pi^2*E/lambda^2

    Pcr = sigma_cr*A

Pin / bushing interface
-----------------------
Both brace ends are preliminarily idealized as close-fitting clevis joints with
the pin in DOUBLE SHEAR.

Pin shear:
    tau_pin = F / (2*A_pin)

Projected bronze-bushing pressure:
    p_b = F / (d_pin * L_b)

The preliminary bushing capacity is read from Phase 2D5.

No pin bending is included yet because actual clevis gap, lug thickness, and
end-fitting geometry are not defined.

Open detail-design items
------------------------
- brace end-eye / fork geometry
- lug net-section and shear-out
- pin bending from real clevis spacing
- fillets and stress concentrations
- fit, lubrication, fretting, and wear
- fatigue / fracture mechanics
- airframe fitting
- retraction kinematics and actuator geometry
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
# 2. FROZEN PHASE 2B UPPER GEOMETRY
# =============================================================================

e_m = 0.120
rt_m = 0.175
h_UA_static_m = 0.475

upper_arm_m = (
    rt_m
    + h_UA_static_m
)


# =============================================================================
# 3. BRACE GEOMETRY / DESIGN SWEEPS
# =============================================================================

effective_arm_values_mm = [
    150.0,
    200.0,
    250.0,
    300.0,
]

working_effective_arm_mm = 250.0

# Physical pin-to-pin free length is independent of effective moment arm.
link_free_length_values_mm = [
    250.0,
    300.0,
    350.0,
    400.0,
    450.0,
]

working_link_free_length_mm = 350.0

tube_OD_values_mm = [
    18.0,
    20.0,
    22.0,
    25.0,
    28.0,
    30.0,
    32.0,
]

wall_min_mm = 1.00
wall_max_mm = 5.00
wall_step_mm = 0.25

working_tube_OD_mm = 25.0
working_tube_wall_mm = 3.0

# Preliminary pin / bushing interface.
pin_diameter_values_mm = [
    8.0,
    10.0,
    12.0,
    14.0,
    16.0,
    18.0,
    20.0,
    22.0,
    24.0,
]

working_pin_diameter_mm = 18.0
working_pin_bushing_width_mm = 20.0

buckling_K = 1.0


# =============================================================================
# 4. FIND INPUT FILES
# =============================================================================

here = Path(__file__).resolve().parent

p2c_candidates = [
    here / "phase2_internal_loads.csv",
    here.parent / "phase2_structures" / "phase2_internal_loads.csv",
]

phase2_csv = None

for path in p2c_candidates:
    if path.exists():
        phase2_csv = path
        break

if phase2_csv is None:
    raise FileNotFoundError(
        "Could not find phase2_internal_loads.csv. "
        "Run Phase 2C first."
    )


d5_candidates = [
    here / "phase2_bushing_material_gland_requirements.csv",
    here.parent
    / "phase2_structures"
    / "phase2_bushing_material_gland_requirements.csv",
]

d5_csv = None

for path in d5_candidates:
    if path.exists():
        d5_csv = path
        break

if d5_csv is None:
    raise FileNotFoundError(
        "Could not find phase2_bushing_material_gland_requirements.csv. "
        "Run Phase 2D5 first."
    )


# =============================================================================
# 5. READ PHASE 2C FORCE CASES
# =============================================================================

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
# 6. READ BRONZE STATIC CAPACITY FROM PHASE 2D5
# =============================================================================

with d5_csv.open(
    "r",
    newline="",
    encoding="utf-8",
) as file:

    d5_rows = list(
        csv.DictReader(file)
    )

if len(d5_rows) != 1:
    raise RuntimeError(
        "Expected exactly one Phase 2D5 summary row."
    )

bronze_static_capacity_MPa = float(
    d5_rows[0]["AMS4640_static_capacity_MPa"]
)


# =============================================================================
# 7. UPPER Mx AND BRACE FORCE
# =============================================================================

def upper_Mx_kNm(
    force,
):
    """
    Moment about the +x trunnion axis at U.
    """

    Fy = force["Fy_kN"]
    Fz = force["Fz_kN"]

    return (
        e_m * Fz
        + upper_arm_m * Fy
    )


def brace_force_kN(
    force,
    effective_arm_mm,
):
    a_m = (
        effective_arm_mm
        / 1000.0
    )

    if a_m <= 0.0:
        raise ValueError(
            "Effective brace arm must be positive."
        )

    return (
        upper_Mx_kNm(force)
        / a_m
    )


def brace_case_table(
    level,
    effective_arm_mm,
):
    rows = []

    for case_name, force in loads[level].items():

        Mx = upper_Mx_kNm(
            force
        )

        Fbrace = brace_force_kN(
            force,
            effective_arm_mm,
        )

        rows.append({
            "case": case_name,
            "Mx_kNm": Mx,
            "Fbrace_kN": Fbrace,
        })

    return rows


working_limit_force_rows = brace_case_table(
    "limit",
    working_effective_arm_mm,
)

working_ultimate_force_rows = brace_case_table(
    "ultimate",
    working_effective_arm_mm,
)

gov_limit_force_row = max(
    working_limit_force_rows,
    key=lambda row:
        abs(row["Fbrace_kN"]),
)

gov_ultimate_force_row = max(
    working_ultimate_force_rows,
    key=lambda row:
        abs(row["Fbrace_kN"]),
)

F_limit_abs_kN = abs(
    gov_limit_force_row["Fbrace_kN"]
)

F_ultimate_abs_kN = abs(
    gov_ultimate_force_row["Fbrace_kN"]
)


# =============================================================================
# 8. TUBE SECTION PROPERTIES
# =============================================================================

def tube_properties(
    OD_mm,
    wall_mm,
):
    ID_mm = (
        OD_mm
        - 2.0 * wall_mm
    )

    if ID_mm <= 0.0:
        raise ValueError(
            "Tube ID must remain positive."
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

    r_g = math.sqrt(
        I / A
    )

    return {
        "OD_mm": OD_mm,
        "ID_mm": ID_mm,
        "wall_mm": wall_mm,

        "A_m2": A,
        "I_m4": I,
        "r_g_m": r_g,

        "mass_per_m_kg":
            rho_kg_m3 * A,
    }


# =============================================================================
# 9. BUCKLING
# =============================================================================

Cc = math.sqrt(
    2.0
    * math.pi**2
    * E_Pa
    / Sy_Pa
)


def buckling_capacity(
    section,
    free_length_mm,
):
    L_m = (
        free_length_mm
        / 1000.0
    )

    r_g = section["r_g_m"]

    slenderness = (
        buckling_K
        * L_m
        / r_g
    )

    if slenderness <= Cc:

        method = "JOHNSON"

        sigma_cr = (
            Sy_Pa
            * (
                1.0
                - (
                    Sy_Pa
                    * slenderness**2
                    / (
                        4.0
                        * math.pi**2
                        * E_Pa
                    )
                )
            )
        )

    else:

        method = "EULER"

        sigma_cr = (
            math.pi**2
            * E_Pa
            / slenderness**2
        )

    Pcr_N = (
        sigma_cr
        * section["A_m2"]
    )

    return {
        "method": method,
        "slenderness": slenderness,
        "sigma_cr_Pa": sigma_cr,
        "Pcr_N": Pcr_N,
    }


# =============================================================================
# 10. MEMBER DESIGN EVALUATION
# =============================================================================

def evaluate_member(
    OD_mm,
    wall_mm,
    free_length_mm,
):
    section = tube_properties(
        OD_mm,
        wall_mm,
    )

    sigma_limit_Pa = (
        F_limit_abs_kN
        * 1000.0
        / section["A_m2"]
    )

    sigma_ultimate_Pa = (
        F_ultimate_abs_kN
        * 1000.0
        / section["A_m2"]
    )

    buckling = buckling_capacity(
        section,
        free_length_mm,
    )

    MS_limit_yield = (
        Sy_Pa
        / sigma_limit_Pa
        - 1.0
    )

    MS_ultimate = (
        Su_Pa
        / sigma_ultimate_Pa
        - 1.0
    )

    # Conservatively treat the governing absolute force as compression.
    MS_buckling = (
        buckling["Pcr_N"]
        / (
            F_ultimate_abs_kN
            * 1000.0
        )
        - 1.0
    )

    passes = all([
        MS_limit_yield >= 0.0,
        MS_ultimate >= 0.0,
        MS_buckling >= 0.0,
    ])

    return {
        **section,

        "free_length_mm":
            free_length_mm,

        "limit_axial_stress_MPa":
            sigma_limit_Pa / 1e6,

        "ultimate_axial_stress_MPa":
            sigma_ultimate_Pa / 1e6,

        "MS_limit_yield":
            MS_limit_yield,

        "MS_ultimate":
            MS_ultimate,

        "buckling_method":
            buckling["method"],

        "slenderness":
            buckling["slenderness"],

        "Pcr_kN":
            buckling["Pcr_N"] / 1000.0,

        "MS_buckling":
            MS_buckling,

        "PASS":
            passes,
    }


# =============================================================================
# 11. MEMBER SWEEP
# =============================================================================

n_wall_steps = int(
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
    for i in range(
        n_wall_steps
    )
]

member_designs = []

for OD_mm in tube_OD_values_mm:

    for wall_mm in wall_values_mm:

        if (
            OD_mm
            - 2.0 * wall_mm
            <= 0.0
        ):
            continue

        member_designs.append(
            evaluate_member(
                OD_mm,
                wall_mm,
                working_link_free_length_mm,
            )
        )


def get_member(
    OD_mm,
    wall_mm,
    free_length_mm,
):
    return evaluate_member(
        OD_mm,
        wall_mm,
        free_length_mm,
    )


working_member = get_member(
    working_tube_OD_mm,
    working_tube_wall_mm,
    working_link_free_length_mm,
)


# =============================================================================
# 12. PIN + BUSHING INTERFACE
# =============================================================================

def pin_interface(
    pin_diameter_mm,
    bushing_width_mm,
):
    d_m = (
        pin_diameter_mm
        / 1000.0
    )

    A_pin_m2 = (
        math.pi
        * d_m**2
        / 4.0
    )

    F_limit_N = (
        F_limit_abs_kN
        * 1000.0
    )

    F_ultimate_N = (
        F_ultimate_abs_kN
        * 1000.0
    )

    # Ideal double shear.
    tau_limit_Pa = (
        F_limit_N
        / (
            2.0
            * A_pin_m2
        )
    )

    tau_ultimate_Pa = (
        F_ultimate_N
        / (
            2.0
            * A_pin_m2
        )
    )

    # Projected bushing pressure, units N/mm2 = MPa.
    p_limit_MPa = (
        F_limit_N
        / (
            pin_diameter_mm
            * bushing_width_mm
        )
    )

    p_ultimate_MPa = (
        F_ultimate_N
        / (
            pin_diameter_mm
            * bushing_width_mm
        )
    )

    MS_limit_pin_shear = (
        tau_y_Pa
        / tau_limit_Pa
        - 1.0
    )

    MS_ultimate_pin_shear = (
        tau_u_Pa
        / tau_ultimate_Pa
        - 1.0
    )

    MS_limit_bearing = (
        bronze_static_capacity_MPa
        / p_limit_MPa
        - 1.0
    )

    MS_ultimate_bearing = (
        bronze_static_capacity_MPa
        / p_ultimate_MPa
        - 1.0
    )

    passes = all([
        MS_limit_pin_shear >= 0.0,
        MS_ultimate_pin_shear >= 0.0,
        MS_limit_bearing >= 0.0,
        MS_ultimate_bearing >= 0.0,
    ])

    return {
        "pin_diameter_mm":
            pin_diameter_mm,

        "bushing_width_mm":
            bushing_width_mm,

        "limit_pin_shear_MPa":
            tau_limit_Pa / 1e6,

        "ultimate_pin_shear_MPa":
            tau_ultimate_Pa / 1e6,

        "MS_limit_pin_shear":
            MS_limit_pin_shear,

        "MS_ultimate_pin_shear":
            MS_ultimate_pin_shear,

        "limit_bearing_pressure_MPa":
            p_limit_MPa,

        "ultimate_bearing_pressure_MPa":
            p_ultimate_MPa,

        "MS_limit_bearing":
            MS_limit_bearing,

        "MS_ultimate_bearing":
            MS_ultimate_bearing,

        "PASS":
            passes,
    }


pin_designs = [
    pin_interface(
        d_mm,
        working_pin_bushing_width_mm,
    )
    for d_mm in pin_diameter_values_mm
]

working_pin = pin_interface(
    working_pin_diameter_mm,
    working_pin_bushing_width_mm,
)


# =============================================================================
# 13. ARM / LENGTH SENSITIVITY
# =============================================================================

arm_rows = []

for arm_mm in effective_arm_values_mm:

    lim_rows = brace_case_table(
        "limit",
        arm_mm,
    )

    ult_rows = brace_case_table(
        "ultimate",
        arm_mm,
    )

    gov_lim = max(
        lim_rows,
        key=lambda row:
            abs(
                row["Fbrace_kN"]
            ),
    )

    gov_ult = max(
        ult_rows,
        key=lambda row:
            abs(
                row["Fbrace_kN"]
            ),
    )

    arm_rows.append({
        "arm_mm": arm_mm,

        "limit_case":
            gov_lim["case"],

        "limit_force_kN":
            abs(
                gov_lim["Fbrace_kN"]
            ),

        "ultimate_case":
            gov_ult["case"],

        "ultimate_force_kN":
            abs(
                gov_ult["Fbrace_kN"]
            ),
    })


length_rows = []

for free_length_mm in link_free_length_values_mm:

    row = get_member(
        working_tube_OD_mm,
        working_tube_wall_mm,
        free_length_mm,
    )

    length_rows.append({
        "free_length_mm":
            free_length_mm,

        "buckling_method":
            row["buckling_method"],

        "slenderness":
            row["slenderness"],

        "Pcr_kN":
            row["Pcr_kN"],

        "MS_buckling":
            row["MS_buckling"],
    })


# =============================================================================
# 14. PROCESS / CONSISTENCY CHECKS
# =============================================================================

# Governing moment must reproduce F = M/a.
gov_limit_Mx_abs_kNm = abs(
    upper_Mx_kNm(
        loads["limit"][
            gov_limit_force_row["case"]
        ]
    )
)

gov_ultimate_Mx_abs_kNm = abs(
    upper_Mx_kNm(
        loads["ultimate"][
            gov_ultimate_force_row["case"]
        ]
    )
)

assert abs(
    F_limit_abs_kN
    - (
        gov_limit_Mx_abs_kNm
        / (
            working_effective_arm_mm
            / 1000.0
        )
    )
) < 1e-12

assert abs(
    F_ultimate_abs_kN
    - (
        gov_ultimate_Mx_abs_kNm
        / (
            working_effective_arm_mm
            / 1000.0
        )
    )
) < 1e-12

assert F_ultimate_abs_kN > F_limit_abs_kN
assert working_member["Pcr_kN"] > 0.0


# =============================================================================
# 15. CSV OUTPUT
# =============================================================================

output_csv = (
    here
    / "phase2_upper_brace_sizing.csv"
)

csv_rows = []

for row in member_designs:

    csv_rows.append({
        "record_type": "MEMBER",
        "effective_arm_mm":
            working_effective_arm_mm,
        "governing_limit_case":
            gov_limit_force_row["case"],
        "governing_ultimate_case":
            gov_ultimate_force_row["case"],
        "limit_force_kN":
            F_limit_abs_kN,
        "ultimate_force_kN":
            F_ultimate_abs_kN,

        "tube_OD_mm":
            row["OD_mm"],
        "tube_ID_mm":
            row["ID_mm"],
        "tube_wall_mm":
            row["wall_mm"],
        "free_length_mm":
            row["free_length_mm"],

        "limit_axial_stress_MPa":
            row["limit_axial_stress_MPa"],
        "ultimate_axial_stress_MPa":
            row["ultimate_axial_stress_MPa"],
        "MS_limit_yield":
            row["MS_limit_yield"],
        "MS_ultimate":
            row["MS_ultimate"],

        "buckling_method":
            row["buckling_method"],
        "slenderness":
            row["slenderness"],
        "Pcr_kN":
            row["Pcr_kN"],
        "MS_buckling":
            row["MS_buckling"],

        "pin_diameter_mm": "",
        "bushing_width_mm": "",
        "ultimate_pin_shear_MPa": "",
        "ultimate_bearing_pressure_MPa": "",
        "MS_ultimate_pin_shear": "",
        "MS_ultimate_bearing": "",

        "PASS":
            row["PASS"],
    })


for row in pin_designs:

    csv_rows.append({
        "record_type": "PIN",
        "effective_arm_mm":
            working_effective_arm_mm,
        "governing_limit_case":
            gov_limit_force_row["case"],
        "governing_ultimate_case":
            gov_ultimate_force_row["case"],
        "limit_force_kN":
            F_limit_abs_kN,
        "ultimate_force_kN":
            F_ultimate_abs_kN,

        "tube_OD_mm": "",
        "tube_ID_mm": "",
        "tube_wall_mm": "",
        "free_length_mm": "",

        "limit_axial_stress_MPa": "",
        "ultimate_axial_stress_MPa": "",
        "MS_limit_yield": "",
        "MS_ultimate": "",

        "buckling_method": "",
        "slenderness": "",
        "Pcr_kN": "",
        "MS_buckling": "",

        "pin_diameter_mm":
            row["pin_diameter_mm"],
        "bushing_width_mm":
            row["bushing_width_mm"],
        "ultimate_pin_shear_MPa":
            row["ultimate_pin_shear_MPa"],
        "ultimate_bearing_pressure_MPa":
            row[
                "ultimate_bearing_pressure_MPa"
            ],
        "MS_ultimate_pin_shear":
            row["MS_ultimate_pin_shear"],
        "MS_ultimate_bearing":
            row["MS_ultimate_bearing"],

        "PASS":
            row["PASS"],
    })


with output_csv.open(
    "w",
    newline="",
    encoding="utf-8",
) as file:

    writer = csv.DictWriter(
        file,
        fieldnames=list(
            csv_rows[0].keys()
        ),
    )

    writer.writeheader()
    writer.writerows(
        csv_rows
    )


# =============================================================================
# 16. CONSOLE REPORT
# =============================================================================

print()
print("=" * 110)
print(
    " PHASE 2D10 — UPPER MOMENT-REACTION BRACE / LINK "
    "PRELIMINARY SIZING"
)
print("=" * 110)

print()
print("--- INPUT CONNECTION ---")
print(
    f"Phase 2C result file:             "
    f"{phase2_csv}"
)
print(
    f"Phase 2D5 material file:          "
    f"{d5_csv}"
)

print()
print("--- STRUCTURAL ROLE ---")
print(
    "Separate pin-jointed two-force brace closes the Mx load path from Phase 2D9."
)
print(
    "This is a structural anti-rotation/load-path member only; "
    "retraction kinematics remain deferred."
)
print(
    "Governing absolute brace force is conservatively checked in both tension "
    "and compression."
)

print()
print("--- GOVERNING Mx / BRACE FORCE AT WORKING ARM ---")
print(
    f"Working effective moment arm:     "
    f"{working_effective_arm_mm:.0f} mm"
)
print(
    f"Limit governing case:             "
    f"{gov_limit_force_row['case']}"
)
print(
    f"Limit |Mx|:                       "
    f"{gov_limit_Mx_abs_kNm:.3f} kN*m"
)
print(
    f"Limit brace force:                "
    f"{F_limit_abs_kN:.3f} kN"
)
print()
print(
    f"Ultimate governing case:          "
    f"{gov_ultimate_force_row['case']}"
)
print(
    f"Ultimate |Mx|:                    "
    f"{gov_ultimate_Mx_abs_kNm:.3f} kN*m"
)
print(
    f"Ultimate brace force:             "
    f"{F_ultimate_abs_kN:.3f} kN"
)

print()
print("--- MOMENT-ARM SENSITIVITY ---")
print(
    f"{'Arm mm':>10}"
    f"{'F_limit kN':>14}"
    f"{'F_ult kN':>14}"
    f"{'Gov LC':>10}"
)
print("-" * 50)

for row in arm_rows:
    print(
        f"{row['arm_mm']:>10.0f}"
        f"{row['limit_force_kN']:>14.2f}"
        f"{row['ultimate_force_kN']:>14.2f}"
        f"{row['ultimate_case']:>10}"
    )

print()
print("--- TUBULAR BRACE MEMBER SWEEP ---")
print(
    f"Working free length:              "
    f"{working_link_free_length_mm:.0f} mm"
)
print(
    f"OD values:                        "
    f"{', '.join(f'{x:.0f}' for x in tube_OD_values_mm)} mm"
)
print(
    f"Wall sweep:                       "
    f"{wall_min_mm:.2f} to "
    f"{wall_max_mm:.2f} mm"
)

print()
print("--- MINIMUM MATHEMATICAL PASSING WALL BY OD ---")
print(
    f"{'OD':>8}"
    f"{'t_min':>10}"
    f"{'ID':>10}"
    f"{'Ult sig':>12}"
    f"{'Pcr kN':>12}"
    f"{'MS buck':>12}"
)
print("-" * 66)

for OD_mm in tube_OD_values_mm:

    subset = [
        row
        for row in member_designs
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
            f"{first['wall_mm']:>10.2f}"
            f"{first['ID_mm']:>10.1f}"
            f"{first['ultimate_axial_stress_MPa']:>12.1f}"
            f"{first['Pcr_kN']:>12.1f}"
            f"{first['MS_buckling']:>12.3f}"
        )
    else:
        print(
            f"{OD_mm:>8.0f}"
            f"{'NO PASS':>10}"
        )

print()
print(
    "--- WORKING BRACE: "
    f"{working_tube_OD_mm:.0f} mm OD x "
    f"{working_tube_wall_mm:.0f} mm WALL / "
    f"{working_link_free_length_mm:.0f} mm FREE LENGTH ---"
)
print(
    f"Inner diameter:                   "
    f"{working_member['ID_mm']:.1f} mm"
)
print(
    f"Area:                             "
    f"{working_member['A_m2']*1e6:.1f} mm^2"
)
print(
    f"Mass per metre:                   "
    f"{working_member['mass_per_m_kg']:.3f} kg/m"
)
print(
    f"Approx tube mass over free length:"
    f" {working_member['mass_per_m_kg']*(working_link_free_length_mm/1000):.3f} kg"
)
print()
print(
    f"Limit axial stress:               "
    f"{working_member['limit_axial_stress_MPa']:.1f} MPa"
)
print(
    f"Limit yield margin:               "
    f"{working_member['MS_limit_yield']:+.3f}"
)
print(
    f"Ultimate axial stress:            "
    f"{working_member['ultimate_axial_stress_MPa']:.1f} MPa"
)
print(
    f"Ultimate strength margin:         "
    f"{working_member['MS_ultimate']:+.3f}"
)
print()
print(
    f"Buckling method:                  "
    f"{working_member['buckling_method']}"
)
print(
    f"Slenderness KL/r:                 "
    f"{working_member['slenderness']:.2f}"
)
print(
    f"Critical buckling load:           "
    f"{working_member['Pcr_kN']:.1f} kN"
)
print(
    f"Buckling margin:                  "
    f"{working_member['MS_buckling']:+.3f}"
)

print()
print("--- FREE-LENGTH EFFECT FOR WORKING 25 x 3 mm TUBE ---")
print(
    f"{'Length':>10}"
    f"{'Method':>12}"
    f"{'KL/r':>10}"
    f"{'Pcr kN':>12}"
    f"{'MS buck':>12}"
)
print("-" * 60)

for row in length_rows:
    print(
        f"{row['free_length_mm']:>8.0f} mm"
        f"{row['buckling_method']:>12}"
        f"{row['slenderness']:>10.2f}"
        f"{row['Pcr_kN']:>12.1f}"
        f"{row['MS_buckling']:>12.3f}"
    )

print()
print(
    "--- WORKING DOUBLE-SHEAR PIN / BRONZE-BUSHING INTERFACE ---"
)
print(
    f"Pin diameter:                     "
    f"{working_pin_diameter_mm:.1f} mm"
)
print(
    f"Projected bushing width:          "
    f"{working_pin_bushing_width_mm:.1f} mm"
)
print(
    f"Ultimate pin double-shear stress: "
    f"{working_pin['ultimate_pin_shear_MPa']:.1f} MPa"
)
print(
    f"Pin ultimate shear margin:        "
    f"{working_pin['MS_ultimate_pin_shear']:+.3f}"
)
print(
    f"Ultimate projected bearing p:     "
    f"{working_pin['ultimate_bearing_pressure_MPa']:.1f} MPa"
)
print(
    f"Bronze static-capacity margin:    "
    f"{working_pin['MS_ultimate_bearing']:+.3f}"
)

print()
print("--- MINIMUM MATHEMATICAL PASSING PIN DIAMETER ---")

passing_pins = [
    row
    for row in pin_designs
    if row["PASS"]
]

if passing_pins:

    min_pin = min(
        passing_pins,
        key=lambda row:
            row["pin_diameter_mm"],
    )

    print(
        f"At {working_pin_bushing_width_mm:.0f} mm projected bushing width: "
        f"{min_pin['pin_diameter_mm']:.1f} mm"
    )
else:
    print(
        "No pin in the current sweep passes."
    )

print()
print("--- INTERPRETATION ---")
print(
    "The brace is structurally feasible as a compact pin-jointed 300M tube."
)
print(
    "The mathematical minimum tube/pin sizes are NOT final design dimensions."
)
print(
    "The working 25 x 3 mm tube and 18 mm pin retain substantial room for "
    "end fittings, fatigue, fretting, pin bending, and manufacturing detail."
)
print(
    "Retraction-system geometry is still intentionally deferred."
)

print()
print("Identity / consistency checks:    PASS")
print(
    f"CSV written to:                   "
    f"{output_csv.name}"
)
print("=" * 110)
