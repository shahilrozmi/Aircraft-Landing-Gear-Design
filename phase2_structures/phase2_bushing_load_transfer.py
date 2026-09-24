"""
Landing_Gear_Design_Project
Phase 2D3 — Bushing / Gland Radial Load-Transfer Model

Purpose
-------
Resolve the lower-piston bending/shear resultants into two radial guide/bushing
reactions and estimate projected bearing pressure.

This script reads the frozen Phase 2C force envelope. It DOES NOT copy reaction
forces from chat.

Idealization
------------
At a selected lower-bushing plane P_L, located h_L above axle station A:

    Vx = Fx
    Vy = Fy

    Mx = e*Fz + (r_t + h_L)*Fy
    My = -(r_t + h_L)*Fx

The lower and upper radial bushings are separated by distance b.

Using a local coordinate with the lower bushing at z = 0 and the upper bushing
at z = b:

Force equilibrium:
    R_Lx + R_Ux + Vx = 0
    R_Ly + R_Uy + Vy = 0

Moment equilibrium about the lower bushing:
    My + b*R_Ux = 0
    Mx - b*R_Uy = 0

Therefore:
    R_Ux = -My/b
    R_Uy =  Mx/b

    R_Lx = -Vx - R_Ux
    R_Ly = -Vy - R_Uy

Resultant radial loads:
    R_U = sqrt(R_Ux^2 + R_Uy^2)
    R_L = sqrt(R_Lx^2 + R_Ly^2)

Projected bearing pressure:
    p_b = R / (D_p * L_b)

where D_p is the working piston OD and L_b is the axial bushing length.

Important limitations
---------------------
- This is a rigid-support statics model.
- It does not yet model elastic load sharing, edge loading, diametral clearance,
  lubrication, contact stress distribution, or bushing material allowables.
- The lower-bushing reaction is treated as the radial load entering the gland /
  lower-barrel-end region.
- Axial gland-retention loads from detailed seal/retainer geometry are deferred
  until the gland hardware is defined.
"""

import csv
import math
from pathlib import Path


# =============================================================================
# 1. LOCKED / WORKING GEOMETRY
# =============================================================================

# Frozen Phase 2B geometry
e_m = 0.120
rt_m = 0.175
L_UA_static_m = 0.475

# Working Phase 2D piston OD
piston_OD_m = 0.058

# Geometry sweeps — deliberately not frozen yet
lower_bushing_h_cases_m = [
    0.200,
    0.250,
    0.300,
    0.350,
]

bushing_spacing_cases_m = [
    0.075,
    0.100,
    0.125,
    0.150,
]

bushing_length_cases_m = [
    0.020,
    0.030,
    0.040,
]

# Provisional working layout for detailed reporting only
working_hL_m = 0.300
working_spacing_m = 0.125
working_bushing_length_m = 0.030


# =============================================================================
# 2. FIND / READ PHASE 2C RESULT FILE
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
    cases = {
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

            cases[level][case] = {
                "Fx_kN": float(row["Fx_kN"]),
                "Fy_kN": float(row["Fy_kN"]),
                "Fz_kN": float(row["Fz_kN"]),
            }

    return cases


loads = read_force_cases(
    phase2_csv
)


# =============================================================================
# 3. LOAD TRANSFER
# =============================================================================

def section_resultants_at_lower_bushing(
    force,
    hL_m,
):
    Fx = force["Fx_kN"]
    Fy = force["Fy_kN"]
    Fz = force["Fz_kN"]

    arm_m = (
        rt_m
        + hL_m
    )

    Mx_kNm = (
        e_m * Fz
        + arm_m * Fy
    )

    My_kNm = (
        -arm_m * Fx
    )

    return {
        "Vx_kN": Fx,
        "Vy_kN": Fy,
        "Mx_kNm": Mx_kNm,
        "My_kNm": My_kNm,
    }


def bushing_reactions(
    resultants,
    spacing_m,
):
    if spacing_m <= 0.0:
        raise ValueError(
            "Bushing spacing must be positive."
        )

    Vx = resultants["Vx_kN"]
    Vy = resultants["Vy_kN"]
    Mx = resultants["Mx_kNm"]
    My = resultants["My_kNm"]

    # Moment equilibrium about lower bushing.
    RUx = -My / spacing_m
    RUy = +Mx / spacing_m

    # Force equilibrium.
    RLx = -Vx - RUx
    RLy = -Vy - RUy

    RU = math.hypot(
        RUx,
        RUy,
    )

    RL = math.hypot(
        RLx,
        RLy,
    )

    # Equilibrium residuals.
    force_residual_x = (
        RLx + RUx + Vx
    )

    force_residual_y = (
        RLy + RUy + Vy
    )

    # About lower bushing:
    #   My + b*RUx = 0
    #   Mx - b*RUy = 0
    moment_residual_y = (
        My + spacing_m * RUx
    )

    moment_residual_x = (
        Mx - spacing_m * RUy
    )

    return {
        "RLx_kN": RLx,
        "RLy_kN": RLy,
        "RL_kN": RL,

        "RUx_kN": RUx,
        "RUy_kN": RUy,
        "RU_kN": RU,

        "force_residual_x_kN": force_residual_x,
        "force_residual_y_kN": force_residual_y,
        "moment_residual_x_kNm": moment_residual_x,
        "moment_residual_y_kNm": moment_residual_y,
    }


def bearing_pressure_MPa(
    reaction_kN,
    bushing_length_m,
):
    projected_area_m2 = (
        piston_OD_m
        * bushing_length_m
    )

    pressure_Pa = (
        reaction_kN
        * 1000.0
        / projected_area_m2
    )

    return pressure_Pa / 1e6


# =============================================================================
# 4. SINGLE LAYOUT EVALUATION
# =============================================================================

def evaluate_layout(
    hL_m,
    spacing_m,
    bushing_length_m,
):
    hU_m = (
        hL_m
        + spacing_m
    )

    # Keep both radial supports inside the static U-A envelope.
    if hU_m > L_UA_static_m:
        return None

    rows = []

    for level in (
        "limit",
        "ultimate",
    ):

        for case_name, force in loads[level].items():

            section = section_resultants_at_lower_bushing(
                force,
                hL_m,
            )

            reactions = bushing_reactions(
                section,
                spacing_m,
            )

            p_lower = bearing_pressure_MPa(
                reactions["RL_kN"],
                bushing_length_m,
            )

            p_upper = bearing_pressure_MPa(
                reactions["RU_kN"],
                bushing_length_m,
            )

            # Self-check equilibrium. These are process checks, not copied outputs.
            assert abs(
                reactions["force_residual_x_kN"]
            ) < 1e-10

            assert abs(
                reactions["force_residual_y_kN"]
            ) < 1e-10

            assert abs(
                reactions["moment_residual_x_kNm"]
            ) < 1e-10

            assert abs(
                reactions["moment_residual_y_kNm"]
            ) < 1e-10

            rows.append({
                "level": level,
                "case": case_name,

                "Vx_kN": section["Vx_kN"],
                "Vy_kN": section["Vy_kN"],
                "Mx_kNm": section["Mx_kNm"],
                "My_kNm": section["My_kNm"],

                "RLx_kN": reactions["RLx_kN"],
                "RLy_kN": reactions["RLy_kN"],
                "RL_kN": reactions["RL_kN"],

                "RUx_kN": reactions["RUx_kN"],
                "RUy_kN": reactions["RUy_kN"],
                "RU_kN": reactions["RU_kN"],

                "p_lower_MPa": p_lower,
                "p_upper_MPa": p_upper,
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

    gov_limit_lower = max(
        limit_rows,
        key=lambda row: row["RL_kN"],
    )

    gov_limit_upper = max(
        limit_rows,
        key=lambda row: row["RU_kN"],
    )

    gov_ult_lower = max(
        ultimate_rows,
        key=lambda row: row["RL_kN"],
    )

    gov_ult_upper = max(
        ultimate_rows,
        key=lambda row: row["RU_kN"],
    )

    max_ultimate_reaction = max(
        gov_ult_lower["RL_kN"],
        gov_ult_upper["RU_kN"],
    )

    max_ultimate_pressure = max(
        gov_ult_lower["p_lower_MPa"],
        gov_ult_upper["p_upper_MPa"],
    )

    return {
        "hL_mm": hL_m * 1000.0,
        "spacing_mm": spacing_m * 1000.0,
        "hU_mm": hU_m * 1000.0,
        "bushing_length_mm": bushing_length_m * 1000.0,

        "limit_lower_case": gov_limit_lower["case"],
        "limit_lower_R_kN": gov_limit_lower["RL_kN"],
        "limit_lower_p_MPa": gov_limit_lower["p_lower_MPa"],

        "limit_upper_case": gov_limit_upper["case"],
        "limit_upper_R_kN": gov_limit_upper["RU_kN"],
        "limit_upper_p_MPa": gov_limit_upper["p_upper_MPa"],

        "ultimate_lower_case": gov_ult_lower["case"],
        "ultimate_lower_R_kN": gov_ult_lower["RL_kN"],
        "ultimate_lower_p_MPa": gov_ult_lower["p_lower_MPa"],

        "ultimate_upper_case": gov_ult_upper["case"],
        "ultimate_upper_R_kN": gov_ult_upper["RU_kN"],
        "ultimate_upper_p_MPa": gov_ult_upper["p_upper_MPa"],

        "max_ultimate_reaction_kN": max_ultimate_reaction,
        "max_ultimate_pressure_MPa": max_ultimate_pressure,
    }


# =============================================================================
# 5. SWEEP
# =============================================================================

layouts = []

for hL_m in lower_bushing_h_cases_m:

    for spacing_m in bushing_spacing_cases_m:

        for bushing_length_m in bushing_length_cases_m:

            result = evaluate_layout(
                hL_m,
                spacing_m,
                bushing_length_m,
            )

            if result is not None:
                layouts.append(
                    result
                )


# =============================================================================
# 6. WORKING LAYOUT
# =============================================================================

working = evaluate_layout(
    working_hL_m,
    working_spacing_m,
    working_bushing_length_m,
)

if working is None:
    raise RuntimeError(
        "Working bushing layout does not fit inside "
        "the static U-A envelope."
    )


# =============================================================================
# 7. OUTPUT CSV
# =============================================================================

output_csv = (
    here
    / "phase2_bushing_load_transfer.csv"
)

with output_csv.open(
    "w",
    newline="",
    encoding="utf-8",
) as file:

    writer = csv.DictWriter(
        file,
        fieldnames=list(
            layouts[0].keys()
        ),
    )

    writer.writeheader()
    writer.writerows(
        layouts
    )


# =============================================================================
# 8. CONSOLE REPORT
# =============================================================================

print()
print("=" * 96)
print(
    " PHASE 2D3 — BUSHING / GLAND "
    "RADIAL LOAD-TRANSFER MODEL"
)
print("=" * 96)

print()
print("--- INPUT CONNECTION ---")
print(
    f"Phase 2C result file:             "
    f"{phase2_csv}"
)

print()
print("--- WORKING INTERFACE GEOMETRY ---")
print(
    f"Piston OD / bearing diameter:     "
    f"{piston_OD_m*1000:.1f} mm"
)
print(
    f"Static U->A envelope:             "
    f"{L_UA_static_m*1000:.1f} mm"
)
print(
    f"Lower-bushing h sweep:            "
    f"{', '.join(f'{x*1000:.0f}' for x in lower_bushing_h_cases_m)} mm"
)
print(
    f"Bushing spacing sweep:            "
    f"{', '.join(f'{x*1000:.0f}' for x in bushing_spacing_cases_m)} mm"
)
print(
    f"Bushing length sweep:             "
    f"{', '.join(f'{x*1000:.0f}' for x in bushing_length_cases_m)} mm"
)

print()
print("--- WORKING LAYOUT ---")
print(
    f"Lower bushing station h_L:        "
    f"{working['hL_mm']:.0f} mm"
)
print(
    f"Bushing spacing b:                "
    f"{working['spacing_mm']:.0f} mm"
)
print(
    f"Upper bushing station h_U:        "
    f"{working['hU_mm']:.0f} mm"
)
print(
    f"Each bushing axial length:        "
    f"{working['bushing_length_mm']:.0f} mm"
)

print()
print("--- WORKING LAYOUT: LIMIT LOADS ---")
print(
    f"Lower/gland governing case:       "
    f"{working['limit_lower_case']}"
)
print(
    f"Lower/gland radial reaction:      "
    f"{working['limit_lower_R_kN']:.3f} kN"
)
print(
    f"Lower projected bearing pressure: "
    f"{working['limit_lower_p_MPa']:.3f} MPa"
)

print()
print(
    f"Upper governing case:             "
    f"{working['limit_upper_case']}"
)
print(
    f"Upper radial reaction:            "
    f"{working['limit_upper_R_kN']:.3f} kN"
)
print(
    f"Upper projected bearing pressure: "
    f"{working['limit_upper_p_MPa']:.3f} MPa"
)

print()
print("--- WORKING LAYOUT: ULTIMATE LOADS ---")
print(
    f"Lower/gland governing case:       "
    f"{working['ultimate_lower_case']}"
)
print(
    f"Lower/gland radial reaction:      "
    f"{working['ultimate_lower_R_kN']:.3f} kN"
)
print(
    f"Lower projected bearing pressure: "
    f"{working['ultimate_lower_p_MPa']:.3f} MPa"
)

print()
print(
    f"Upper governing case:             "
    f"{working['ultimate_upper_case']}"
)
print(
    f"Upper radial reaction:            "
    f"{working['ultimate_upper_R_kN']:.3f} kN"
)
print(
    f"Upper projected bearing pressure: "
    f"{working['ultimate_upper_p_MPa']:.3f} MPa"
)

print()
print("--- SPACING EFFECT, 30 mm BUSHINGS ---")
print(
    f"{'hL mm':>8}"
    f"{'b mm':>8}"
    f"{'hU mm':>8}"
    f"{'R_L,ult kN':>14}"
    f"{'R_U,ult kN':>14}"
    f"{'p_max MPa':>12}"
    f"{'Gov lower':>12}"
)
print("-" * 80)

spacing_rows = [
    row
    for row in layouts
    if abs(
        row["bushing_length_mm"]
        - 30.0
    ) < 1e-12
]

for row in spacing_rows:
    print(
        f"{row['hL_mm']:>8.0f}"
        f"{row['spacing_mm']:>8.0f}"
        f"{row['hU_mm']:>8.0f}"
        f"{row['ultimate_lower_R_kN']:>14.2f}"
        f"{row['ultimate_upper_R_kN']:>14.2f}"
        f"{row['max_ultimate_pressure_MPa']:>12.2f}"
        f"{row['ultimate_lower_case']:>12}"
    )

print()
print(
    "Equilibrium self-checks:          PASS"
)
print(
    "No bushing material allowable has been imposed yet."
)
print(
    "The lower reaction is the radial load delivered into "
    "the gland/lower-barrel-end region."
)
print(
    "Axial gland-retention and groove stresses are deferred "
    "until the actual gland/retainer geometry is selected."
)

print()
print(
    f"CSV written to:                   "
    f"{output_csv.name}"
)
print("=" * 96)
