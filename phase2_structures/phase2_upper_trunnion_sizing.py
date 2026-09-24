"""
Landing_Gear_Design_Project
Phase 2D9 — Upper Trunnion / Attachment Preliminary Sizing

Purpose
-------
Create a mechanically consistent upper-attachment architecture for the frozen
Phase 2C six-component load set and preliminarily size the trunnion journals.

This script reads phase2_internal_loads.csv directly. It does NOT paste moments,
bearing reactions, or stresses from chat.

Selected preliminary architecture
---------------------------------
A transverse trunnion axis is taken along aircraft +x.

Two airframe-supported trunnion bearings are placed at:

    x = -s/2   (left/inboard support plane)
    x = +s/2   (right/outboard support plane)

This architecture separates the upper loads as follows:

    Fx  -> trunnion axial / thrust-face load
    Fy  -> radial trunnion-bearing load
    Fz  -> radial trunnion-bearing load

    My  -> differential Fz reactions across trunnion span
    Mz  -> differential Fy reactions across trunnion span

    Mx  -> NOT reacted by a freely rotating trunnion pair.
           It becomes the required brace / lock-link moment reaction.

This is important: a single trunnion pair cannot be credited with resisting the
moment about its own rotational axis without an additional brace/lock path.

Frozen Phase 2C upper resultants
--------------------------------
At upper datum U:

    arm_U = r_t + h_UA = 0.175 + 0.475 = 0.650 m

    Mx = e*Fz + arm_U*Fy
    My = -arm_U*Fx
    Mz = Tz = -e*Fx

Trunnion reactions
------------------
For left and right support reactions:

    RLy + RRy + Fy = 0
    RLz + RRz + Fz = 0

Moment equilibrium about U:

    My + (s/2)*(RLz - RRz) = 0
    Mz + (s/2)*(-RLy + RRy) = 0

which gives:

    RLy = (-Fy + 2*Mz/s)/2
    RRy = (-Fy - 2*Mz/s)/2

    RLz = (-Fz - 2*My/s)/2
    RRz = (-Fz + 2*My/s)/2

Each radial bearing load is:

    R = sqrt(Ry^2 + Rz^2)

Journal-root screen
-------------------
Each journal is treated as a solid 300M-steel cantilever root.

For bearing width L_b and root-to-bearing-edge clearance g:

    root lever arm = g + L_b/2
    M_root = R * (g + L_b/2)

Solid circular section:

    A = pi*d^2/4
    I = pi*d^4/64

A conservative axial-thrust screen applies the FULL |Fx| to the more highly
loaded journal root:

    sigma_axial = |Fx| / A
    sigma_bending = M_root*c/I

    sigma_normal,worst = sigma_axial + sigma_bending

Transverse shear is kept as a separate screen:

    tau_V,max = 4V/(3A)

for a solid circular section.

Shoulder stress concentration
-----------------------------
The actual trunnion shoulder fillet is not yet defined. Therefore:
- the design sweep uses nominal Kt = 1
- the working candidate is also reported at Kt = 1.5, 2.0, 2.5, 3.0
- Kt is applied to bending only
- no fake final fillet radius is invented

Bearing material
----------------
The preliminary trunnion bushing screen reuses the AMS 4640 nickel-aluminum
bronze static capacity already carried in Phase 2D5.

That is a STATIC preliminary capacity screen only. Final oscillatory wear,
fatigue, lubrication, fit, and life checks remain open.

Brace / lock-link requirement
-----------------------------
The moment about the trunnion axis Mx is converted into a force requirement:

    F_brace = |Mx| / l_brace

for several perpendicular moment arms. This is a load requirement only; the
brace member itself is NOT sized in this script.
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
# 2. FROZEN PHASE 2B GEOMETRY
# =============================================================================

e_m = 0.120
rt_m = 0.175
h_UA_static_m = 0.475

upper_arm_m = (
    rt_m
    + h_UA_static_m
)


# =============================================================================
# 3. TRUNNION DESIGN SWEEP
# =============================================================================

support_span_values_mm = [
    120.0,
    150.0,
    180.0,
]

bearing_width_values_mm = [
    20.0,
    25.0,
    30.0,
]

journal_diameter_values_mm = [
    22.0,
    24.0,
    26.0,
    28.0,
    30.0,
    32.0,
    34.0,
    36.0,
    38.0,
    40.0,
]

# Small packaging gap from head shoulder to bearing edge.
# Working assumption only.
root_clearance_mm = 5.0

working_span_mm = 120.0
working_bearing_width_mm = 25.0
working_journal_diameter_mm = 32.0

Kt_values = [
    1.0,
    1.5,
    2.0,
    2.5,
    3.0,
]

brace_arm_values_mm = [
    150.0,
    200.0,
    250.0,
    300.0,
]


# =============================================================================
# 4. FIND INPUT FILES
# =============================================================================

here = Path(__file__).resolve().parent

phase2_candidates = [
    here / "phase2_internal_loads.csv",
    here.parent / "phase2_structures" / "phase2_internal_loads.csv",
]

phase2_csv = None

for path in phase2_candidates:
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
# 6. READ PRELIMINARY BRONZE CAPACITY FROM D5
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
# 7. UPPER RESULTANTS
# =============================================================================

def upper_resultants(
    force,
):
    Fx = force["Fx_kN"]
    Fy = force["Fy_kN"]
    Fz = force["Fz_kN"]

    Mx_kNm = (
        e_m * Fz
        + upper_arm_m * Fy
    )

    My_kNm = (
        -upper_arm_m * Fx
    )

    Mz_kNm = (
        -e_m * Fx
    )

    return {
        "Fx_kN": Fx,
        "Fy_kN": Fy,
        "Fz_kN": Fz,
        "Mx_kNm": Mx_kNm,
        "My_kNm": My_kNm,
        "Mz_kNm": Mz_kNm,
    }


# =============================================================================
# 8. TWO-TRUNNION REACTIONS
# =============================================================================

def trunnion_reactions(
    upper,
    span_mm,
):
    s_m = span_mm / 1000.0

    if s_m <= 0.0:
        raise ValueError(
            "Trunnion support span must be positive."
        )

    Fy = upper["Fy_kN"]
    Fz = upper["Fz_kN"]
    My = upper["My_kNm"]
    Mz = upper["Mz_kNm"]

    RLy = (
        -Fy
        + 2.0 * Mz / s_m
    ) / 2.0

    RRy = (
        -Fy
        - 2.0 * Mz / s_m
    ) / 2.0

    RLz = (
        -Fz
        - 2.0 * My / s_m
    ) / 2.0

    RRz = (
        -Fz
        + 2.0 * My / s_m
    ) / 2.0

    RL = math.hypot(
        RLy,
        RLz,
    )

    RR = math.hypot(
        RRy,
        RRz,
    )

    # Equilibrium residuals.
    force_y_residual = (
        RLy + RRy + Fy
    )

    force_z_residual = (
        RLz + RRz + Fz
    )

    moment_y_residual = (
        My
        + (s_m / 2.0)
        * (
            RLz - RRz
        )
    )

    moment_z_residual = (
        Mz
        + (s_m / 2.0)
        * (
            -RLy + RRy
        )
    )

    return {
        "RLy_kN": RLy,
        "RLz_kN": RLz,
        "RL_kN": RL,

        "RRy_kN": RRy,
        "RRz_kN": RRz,
        "RR_kN": RR,

        "force_y_residual_kN":
            force_y_residual,
        "force_z_residual_kN":
            force_z_residual,
        "moment_y_residual_kNm":
            moment_y_residual,
        "moment_z_residual_kNm":
            moment_z_residual,
    }


# =============================================================================
# 9. JOURNAL SECTION
# =============================================================================

def journal_properties(
    diameter_mm,
):
    d_m = diameter_mm / 1000.0

    A_m2 = (
        math.pi
        * d_m**2
        / 4.0
    )

    I_m4 = (
        math.pi
        * d_m**4
        / 64.0
    )

    c_m = d_m / 2.0

    return {
        "d_m": d_m,
        "A_m2": A_m2,
        "I_m4": I_m4,
        "c_m": c_m,
    }


# =============================================================================
# 10. JOURNAL ROOT STRESS
# =============================================================================

def journal_root_stress(
    radial_reaction_kN,
    axial_thrust_kN,
    diameter_mm,
    bearing_width_mm,
    Kt_bending=1.0,
):
    section = journal_properties(
        diameter_mm
    )

    A = section["A_m2"]
    I = section["I_m4"]
    c = section["c_m"]

    root_lever_m = (
        root_clearance_mm
        + bearing_width_mm / 2.0
    ) / 1000.0

    R_N = (
        radial_reaction_kN
        * 1000.0
    )

    Fx_N = (
        abs(axial_thrust_kN)
        * 1000.0
    )

    M_Nm = (
        R_N
        * root_lever_m
    )

    sigma_axial = (
        Fx_N / A
    )

    sigma_bending = (
        Kt_bending
        * M_Nm
        * c / I
    )

    sigma_worst = (
        sigma_axial
        + sigma_bending
    )

    tau_transverse = (
        4.0
        * R_N
        / (
            3.0 * A
        )
    )

    return {
        "root_lever_mm":
            root_lever_m * 1000.0,

        "root_moment_kNm":
            M_Nm / 1000.0,

        "sigma_axial_MPa":
            sigma_axial / 1e6,

        "sigma_bending_MPa":
            sigma_bending / 1e6,

        "vm_MPa":
            sigma_worst / 1e6,

        "tau_transverse_MPa":
            tau_transverse / 1e6,
    }


# =============================================================================
# 11. SINGLE DESIGN EVALUATION
# =============================================================================

def evaluate_design(
    span_mm,
    bearing_width_mm,
    diameter_mm,
):
    case_rows = []

    for level in (
        "limit",
        "ultimate",
    ):

        for case_name, force in loads[level].items():

            upper = upper_resultants(
                force
            )

            reactions = trunnion_reactions(
                upper,
                span_mm,
            )

            # Equilibrium self-check.
            assert abs(
                reactions[
                    "force_y_residual_kN"
                ]
            ) < 1e-10

            assert abs(
                reactions[
                    "force_z_residual_kN"
                ]
            ) < 1e-10

            assert abs(
                reactions[
                    "moment_y_residual_kNm"
                ]
            ) < 1e-10

            assert abs(
                reactions[
                    "moment_z_residual_kNm"
                ]
            ) < 1e-10

            # Conservatively apply the full axial Fx to the journal that has
            # the larger radial reaction.
            if (
                reactions["RL_kN"]
                >= reactions["RR_kN"]
            ):
                governing_side = "LEFT"
                Rgov = reactions["RL_kN"]
            else:
                governing_side = "RIGHT"
                Rgov = reactions["RR_kN"]

            stress = journal_root_stress(
                Rgov,
                upper["Fx_kN"],
                diameter_mm,
                bearing_width_mm,
                Kt_bending=1.0,
            )

            p_bearing_MPa = (
                Rgov
                * 1000.0
                / (
                    diameter_mm
                    * bearing_width_mm
                )
            )

            case_rows.append({
                "level": level,
                "case": case_name,
                "governing_side":
                    governing_side,

                "Fx_kN": upper["Fx_kN"],
                "Fy_kN": upper["Fy_kN"],
                "Fz_kN": upper["Fz_kN"],

                "Mx_kNm": upper["Mx_kNm"],
                "My_kNm": upper["My_kNm"],
                "Mz_kNm": upper["Mz_kNm"],

                "RL_kN": reactions["RL_kN"],
                "RR_kN": reactions["RR_kN"],
                "Rgov_kN": Rgov,

                "bearing_pressure_MPa":
                    p_bearing_MPa,

                **stress,
            })

    limit_rows = [
        row
        for row in case_rows
        if row["level"] == "limit"
    ]

    ultimate_rows = [
        row
        for row in case_rows
        if row["level"] == "ultimate"
    ]

    gov_limit_vm = max(
        limit_rows,
        key=lambda row:
            row["vm_MPa"],
    )

    gov_ultimate_vm = max(
        ultimate_rows,
        key=lambda row:
            row["vm_MPa"],
    )

    gov_limit_bearing = max(
        limit_rows,
        key=lambda row:
            row["bearing_pressure_MPa"],
    )

    gov_ultimate_bearing = max(
        ultimate_rows,
        key=lambda row:
            row["bearing_pressure_MPa"],
    )

    gov_limit_shear = max(
        limit_rows,
        key=lambda row:
            row["tau_transverse_MPa"],
    )

    gov_ultimate_shear = max(
        ultimate_rows,
        key=lambda row:
            row["tau_transverse_MPa"],
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

    MS_limit_bearing = (
        bronze_static_capacity_MPa
        / gov_limit_bearing[
            "bearing_pressure_MPa"
        ]
        - 1.0
    )

    MS_ultimate_bearing = (
        bronze_static_capacity_MPa
        / gov_ultimate_bearing[
            "bearing_pressure_MPa"
        ]
        - 1.0
    )

    MS_limit_shear = (
        tau_y_Pa / 1e6
        / gov_limit_shear[
            "tau_transverse_MPa"
        ]
        - 1.0
    )

    MS_ultimate_shear = (
        tau_u_Pa / 1e6
        / gov_ultimate_shear[
            "tau_transverse_MPa"
        ]
        - 1.0
    )

    passes = all([
        MS_limit_yield >= 0.0,
        MS_ultimate >= 0.0,
        MS_limit_bearing >= 0.0,
        MS_ultimate_bearing >= 0.0,
        MS_limit_shear >= 0.0,
        MS_ultimate_shear >= 0.0,
    ])

    return {
        "span_mm": span_mm,
        "bearing_width_mm":
            bearing_width_mm,
        "journal_diameter_mm":
            diameter_mm,

        "limit_governing_case":
            gov_limit_vm["case"],
        "limit_governing_side":
            gov_limit_vm[
                "governing_side"
            ],
        "limit_radial_reaction_kN":
            gov_limit_vm["Rgov_kN"],
        "limit_vm_MPa":
            gov_limit_vm["vm_MPa"],
        "MS_limit_yield":
            MS_limit_yield,

        "ultimate_governing_case":
            gov_ultimate_vm["case"],
        "ultimate_governing_side":
            gov_ultimate_vm[
                "governing_side"
            ],
        "ultimate_radial_reaction_kN":
            gov_ultimate_vm["Rgov_kN"],
        "ultimate_vm_MPa":
            gov_ultimate_vm["vm_MPa"],
        "MS_ultimate":
            MS_ultimate,

        "ultimate_bearing_case":
            gov_ultimate_bearing["case"],
        "ultimate_bearing_pressure_MPa":
            gov_ultimate_bearing[
                "bearing_pressure_MPa"
            ],
        "MS_ultimate_bearing":
            MS_ultimate_bearing,

        "ultimate_tau_transverse_MPa":
            gov_ultimate_shear[
                "tau_transverse_MPa"
            ],
        "MS_ultimate_shear":
            MS_ultimate_shear,

        "root_lever_mm":
            gov_ultimate_vm[
                "root_lever_mm"
            ],

        "PASS": passes,
    }


# =============================================================================
# 12. DESIGN SWEEP
# =============================================================================

designs = []

for span_mm in support_span_values_mm:

    for bearing_width_mm in bearing_width_values_mm:

        for diameter_mm in journal_diameter_values_mm:

            designs.append(
                evaluate_design(
                    span_mm,
                    bearing_width_mm,
                    diameter_mm,
                )
            )


# =============================================================================
# 13. WORKING CANDIDATE + Kt SENSITIVITY
# =============================================================================

def get_design(
    span_mm,
    bearing_width_mm,
    diameter_mm,
):
    for row in designs:
        if (
            abs(
                row["span_mm"]
                - span_mm
            ) < 1e-12
            and abs(
                row[
                    "bearing_width_mm"
                ]
                - bearing_width_mm
            ) < 1e-12
            and abs(
                row[
                    "journal_diameter_mm"
                ]
                - diameter_mm
            ) < 1e-12
        ):
            return row

    raise KeyError(
        "Requested trunnion design not found."
    )


working = get_design(
    working_span_mm,
    working_bearing_width_mm,
    working_journal_diameter_mm,
)


def working_case_rows(
    level,
    Kt_bending,
):
    rows = []

    for case_name, force in loads[level].items():

        upper = upper_resultants(
            force
        )

        reactions = trunnion_reactions(
            upper,
            working_span_mm,
        )

        if (
            reactions["RL_kN"]
            >= reactions["RR_kN"]
        ):
            side = "LEFT"
            Rgov = reactions["RL_kN"]
        else:
            side = "RIGHT"
            Rgov = reactions["RR_kN"]

        stress = journal_root_stress(
            Rgov,
            upper["Fx_kN"],
            working_journal_diameter_mm,
            working_bearing_width_mm,
            Kt_bending,
        )

        p_bearing = (
            Rgov
            * 1000.0
            / (
                working_journal_diameter_mm
                * working_bearing_width_mm
            )
        )

        rows.append({
            "case": case_name,
            "side": side,
            "Rgov_kN": Rgov,
            "Mx_kNm": upper["Mx_kNm"],
            "Fx_kN": upper["Fx_kN"],
            "bearing_pressure_MPa":
                p_bearing,
            **stress,
        })

    return rows


kt_sensitivity = []

for Kt in Kt_values:

    lim_rows = working_case_rows(
        "limit",
        Kt,
    )

    ult_rows = working_case_rows(
        "ultimate",
        Kt,
    )

    gov_lim = max(
        lim_rows,
        key=lambda row:
            row["vm_MPa"],
    )

    gov_ult = max(
        ult_rows,
        key=lambda row:
            row["vm_MPa"],
    )

    kt_sensitivity.append({
        "Kt": Kt,

        "limit_case":
            gov_lim["case"],
        "limit_vm_MPa":
            gov_lim["vm_MPa"],
        "MS_limit_yield":
            Sy_Pa / 1e6
            / gov_lim["vm_MPa"]
            - 1.0,

        "ultimate_case":
            gov_ult["case"],
        "ultimate_vm_MPa":
            gov_ult["vm_MPa"],
        "MS_ultimate":
            Su_Pa / 1e6
            / gov_ult["vm_MPa"]
            - 1.0,
    })


# =============================================================================
# 14. BRACE / LOCK-LINK MOMENT REQUIREMENT
# =============================================================================

def governing_Mx(
    level,
):
    rows = []

    for case_name, force in loads[level].items():

        upper = upper_resultants(
            force
        )

        rows.append({
            "case": case_name,
            "Mx_kNm":
                abs(
                    upper["Mx_kNm"]
                ),
        })

    return max(
        rows,
        key=lambda row:
            row["Mx_kNm"],
    )


gov_Mx_limit = governing_Mx(
    "limit"
)

gov_Mx_ultimate = governing_Mx(
    "ultimate"
)

brace_rows = []

for arm_mm in brace_arm_values_mm:

    arm_m = arm_mm / 1000.0

    brace_rows.append({
        "arm_mm": arm_mm,

        "limit_case":
            gov_Mx_limit["case"],
        "limit_force_kN":
            gov_Mx_limit["Mx_kNm"]
            / arm_m,

        "ultimate_case":
            gov_Mx_ultimate["case"],
        "ultimate_force_kN":
            gov_Mx_ultimate["Mx_kNm"]
            / arm_m,
    })


# =============================================================================
# 15. CONSISTENCY CHECKS
# =============================================================================

# Every reaction calculation must satisfy exact statics.
for level in (
    "limit",
    "ultimate",
):
    for case_name, force in loads[level].items():

        upper = upper_resultants(
            force
        )

        reaction = trunnion_reactions(
            upper,
            working_span_mm,
        )

        assert abs(
            reaction[
                "force_y_residual_kN"
            ]
        ) < 1e-10

        assert abs(
            reaction[
                "force_z_residual_kN"
            ]
        ) < 1e-10

        assert abs(
            reaction[
                "moment_y_residual_kNm"
            ]
        ) < 1e-10

        assert abs(
            reaction[
                "moment_z_residual_kNm"
            ]
        ) < 1e-10


# =============================================================================
# 16. CSV OUTPUT
# =============================================================================

output_csv = (
    here
    / "phase2_upper_trunnion_sizing.csv"
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
# 17. CONSOLE REPORT
# =============================================================================

print()
print("=" * 110)
print(
    " PHASE 2D9 — UPPER TRUNNION / ATTACHMENT "
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
print("--- SELECTED UPPER-ATTACHMENT ARCHITECTURE ---")
print(
    "Trunnion axis: +x (aircraft longitudinal)."
)
print(
    "Two radial trunnion bearings react Fy, Fz, My, and Mz."
)
print(
    "Full |Fx| is conservatively treated as a thrust load on one locating journal."
)
print(
    "Mx about the trunnion axis is NOT assigned to the journals; "
    "it becomes a brace/lock-link moment requirement."
)

print()
print("--- FROZEN UPPER GEOMETRY ---")
print(
    f"Upper resultant arm r_t+h:        "
    f"{upper_arm_m*1000:.1f} mm"
)
print(
    f"Wheel/strut lateral offset e:     "
    f"{e_m*1000:.1f} mm"
)

print()
print("--- DESIGN SWEEP ---")
print(
    f"Trunnion support spans:           "
    f"{', '.join(f'{x:.0f}' for x in support_span_values_mm)} mm"
)
print(
    f"Bearing widths:                   "
    f"{', '.join(f'{x:.0f}' for x in bearing_width_values_mm)} mm"
)
print(
    f"Journal diameters:                "
    f"{journal_diameter_values_mm[0]:.0f} to "
    f"{journal_diameter_values_mm[-1]:.0f} mm"
)
print(
    f"Root-to-bearing-edge clearance:   "
    f"{root_clearance_mm:.1f} mm (working assumption)"
)

print()
print("--- MINIMUM NOMINAL PASSING DIAMETER ---")
print(
    f"{'Span':>8}"
    f"{'Lb':>8}"
    f"{'d_min':>10}"
    f"{'Ult R':>12}"
    f"{'Ult VM':>12}"
    f"{'p_brg':>12}"
    f"{'Gov LC':>10}"
)
print("-" * 76)

for span_mm in support_span_values_mm:

    for bearing_width_mm in bearing_width_values_mm:

        subset = [
            row
            for row in designs
            if (
                abs(
                    row["span_mm"]
                    - span_mm
                ) < 1e-12
                and abs(
                    row[
                        "bearing_width_mm"
                    ]
                    - bearing_width_mm
                ) < 1e-12
                and row["PASS"]
            )
        ]

        if subset:
            first = min(
                subset,
                key=lambda row:
                    row[
                        "journal_diameter_mm"
                    ],
            )

            print(
                f"{span_mm:>8.0f}"
                f"{bearing_width_mm:>8.0f}"
                f"{first['journal_diameter_mm']:>10.0f}"
                f"{first['ultimate_radial_reaction_kN']:>12.2f}"
                f"{first['ultimate_vm_MPa']:>12.1f}"
                f"{first['ultimate_bearing_pressure_MPa']:>12.1f}"
                f"{first['ultimate_governing_case']:>10}"
            )
        else:
            print(
                f"{span_mm:>8.0f}"
                f"{bearing_width_mm:>8.0f}"
                f"{'NO PASS':>10}"
            )

print()
print(
    "--- WORKING CANDIDATE: "
    f"{working_span_mm:.0f} mm SPAN / "
    f"{working_journal_diameter_mm:.0f} mm JOURNAL / "
    f"{working_bearing_width_mm:.0f} mm BEARING ---"
)
print(
    f"Journal-root lever arm:           "
    f"{working['root_lever_mm']:.1f} mm"
)
print(
    f"Ultimate governing case:          "
    f"{working['ultimate_governing_case']}"
)
print(
    f"Ultimate governing side:          "
    f"{working['ultimate_governing_side']}"
)
print(
    f"Ultimate radial reaction:         "
    f"{working['ultimate_radial_reaction_kN']:.3f} kN"
)
print(
    f"Nominal ultimate VM stress:       "
    f"{working['ultimate_vm_MPa']:.1f} MPa"
)
print(
    f"Nominal ultimate strength margin: "
    f"{working['MS_ultimate']:+.3f}"
)
print(
    f"Ultimate bearing pressure:        "
    f"{working['ultimate_bearing_pressure_MPa']:.1f} MPa"
)
print(
    f"Bronze static-capacity margin:    "
    f"{working['MS_ultimate_bearing']:+.3f}"
)
print(
    f"Ultimate transverse shear screen: "
    f"{working['ultimate_tau_transverse_MPa']:.1f} MPa"
)

print()
print("--- JOURNAL-SHOULDER Kt SENSITIVITY ---")
print(
    f"{'Kt':>6}"
    f"{'Limit VM':>14}"
    f"{'MS_yield':>12}"
    f"{'Ult VM':>14}"
    f"{'MS_ult':>12}"
    f"{'Gov LC':>10}"
)
print("-" * 70)

for row in kt_sensitivity:
    print(
        f"{row['Kt']:>6.1f}"
        f"{row['limit_vm_MPa']:>14.1f}"
        f"{row['MS_limit_yield']:>12.3f}"
        f"{row['ultimate_vm_MPa']:>14.1f}"
        f"{row['MS_ultimate']:>12.3f}"
        f"{row['ultimate_case']:>10}"
    )

print()
print("--- BRACE / LOCK-LINK REQUIREMENT FOR Mx ---")
print(
    f"Governing limit Mx:               "
    f"{gov_Mx_limit['Mx_kNm']:.3f} kN*m "
    f"({gov_Mx_limit['case']})"
)
print(
    f"Governing ultimate Mx:            "
    f"{gov_Mx_ultimate['Mx_kNm']:.3f} kN*m "
    f"({gov_Mx_ultimate['case']})"
)
print()
print(
    f"{'Moment arm':>12}"
    f"{'F_limit kN':>14}"
    f"{'F_ult kN':>14}"
)
print("-" * 42)

for row in brace_rows:
    print(
        f"{row['arm_mm']:>10.0f} mm"
        f"{row['limit_force_kN']:>14.2f}"
        f"{row['ultimate_force_kN']:>14.2f}"
    )

print()
print("--- INTERPRETATION ---")
print(
    "The trunnion pair reacts forces and the moments perpendicular to its axis."
)
print(
    "The Mx component requires an independent brace/lock path; omitting that path "
    "would make the upper attachment statically incomplete."
)
print(
    "The working 32 mm journal is a preliminary root/bearing diameter only."
)
print(
    "Final lugs, thrust faces, fillets, bearing fits, brace pins, fatigue, "
    "fretting, and airframe fitting geometry remain open."
)

print()
print("Equilibrium / consistency checks: PASS")
print(
    f"CSV written to:                   "
    f"{output_csv.name}"
)
print("=" * 110)
