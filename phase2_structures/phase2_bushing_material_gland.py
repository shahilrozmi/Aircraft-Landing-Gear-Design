"""
Landing_Gear_Design_Project
Phase 2D5 — Bushing Material Screen + Lower Gland / Barrel-End Load Requirements

Purpose
-------
1) Select a realistic preliminary guide-bushing material basis.
2) Compare the CALCULATED Phase 2D3 projected bearing pressure against that basis.
3) Convert the preferred Phase 2D4 layout into local lower-gland / barrel-end load
   requirements for later detailed geometry design.

IMPORTANT
---------
This script does NOT paste stress/reaction answers from chat.

It reads:
    phase2_bushing_load_transfer.csv

and extracts the preferred working layout:
    h_L = 250 mm
    spacing = 150 mm
    h_U = 400 mm
    bushing length = 30 mm

All reaction loads and projected pressures therefore come from the Python statics
model developed in Phase 2D3.

Preliminary bushing material
----------------------------
Primary baseline:
    Nickel-aluminum bronze, C63000 / AMS 4640

Why:
    - established aircraft landing-gear bushing/bearing material
    - good bearing / galling resistance against steel
    - corrosion resistance
    - direct landing-gear precedent

Preliminary static bearing-capacity screen:
    60 ksi = 413.685 MPa

This value is treated ONLY as a preliminary maximum static bearing-capacity screen,
not a wear-life or certification allowable.

A separate PTFE-composite comparison is also reported using SKF catalog values:
    permissible specific static bearing load  = 250 MPa
    permissible specific dynamic bearing load = 80 MPa

These PTFE values are included only as a technology comparison. A real PTFE-lined
selection would still require p-v, temperature, surface-finish, clearance, and life
checks.

Working interface geometry
--------------------------
Piston OD              = 58 mm
Outer-barrel bore / bushing OD = 64 mm
Bushing radial wall    = (64 - 58)/2 = 3 mm
Bushing axial length   = 30 mm

Lower gland / barrel-end requirements
-------------------------------------
The lower bushing reaction is converted into:
    - average piston-side projected bearing pressure
    - average housing-side projected bearing pressure
    - radial line load into the barrel over the bushing length

The script also calculates pressure thrust from the frozen Phase 1 gas law:
    - thrust on the 58 mm effective piston area
    - thrust on the 64 mm barrel-bore area

These are LOAD REQUIREMENTS only.

A detailed gland-retainer / groove / thread stress check is intentionally deferred
until its actual geometry is defined. We do NOT invent a groove diameter, thread
form, shoulder thickness, fillet radius, or retainer architecture.
"""

import csv
import math
from pathlib import Path


# =============================================================================
# 1. SOURCE-BASED PRELIMINARY MATERIAL DATA
# =============================================================================

# C63000 / AMS 4640 nickel-aluminum bronze
bronze_static_capacity_MPa = 60.0 * 6.894757293168361  # 60 ksi -> MPa

# SKF PTFE-composite plain-bearing catalog comparison values
ptfe_static_limit_MPa = 250.0
ptfe_dynamic_limit_MPa = 80.0


# =============================================================================
# 2. WORKING INTERFACE GEOMETRY
# =============================================================================

piston_OD_mm = 58.0
bushing_OD_mm = 64.0
bushing_length_mm = 30.0

bushing_radial_wall_mm = (
    bushing_OD_mm - piston_OD_mm
) / 2.0


# =============================================================================
# 3. PREFERRED PHASE 2D4 LAYOUT
# =============================================================================

preferred_hL_mm = 250.0
preferred_spacing_mm = 150.0
preferred_hU_mm = 400.0
preferred_bushing_length_mm = 30.0


# =============================================================================
# 4. FROZEN PHASE 1 PRESSURE MODEL
# =============================================================================

P_atm_Pa = 101_325.0
P0_abs_Pa = 2.336e6
L0_gas_m = 0.350
n_gas = 1.30

x_physical_m = 0.230000
x_virtual_m = 0.240779

D_effective_piston_m = 0.058
D_barrel_bore_m = 0.064


def gas_pressure_gauge_Pa(x_m):
    if x_m >= L0_gas_m:
        raise ValueError(
            "Compression exceeds initial gas-column length."
        )

    P_abs = (
        P0_abs_Pa
        * (
            L0_gas_m
            / (L0_gas_m - x_m)
        )**n_gas
    )

    return P_abs - P_atm_Pa


p_physical_Pa = gas_pressure_gauge_Pa(
    x_physical_m
)

p_virtual_Pa = gas_pressure_gauge_Pa(
    x_virtual_m
)


# =============================================================================
# 5. READ PHASE 2D3 RESULTS
# =============================================================================

here = Path(__file__).resolve().parent

candidate_paths = [
    here / "phase2_bushing_load_transfer.csv",
    here.parent / "phase2_structures" / "phase2_bushing_load_transfer.csv",
]

d3_csv = None

for path in candidate_paths:
    if path.exists():
        d3_csv = path
        break

if d3_csv is None:
    raise FileNotFoundError(
        "Could not find phase2_bushing_load_transfer.csv. "
        "Run phase2_bushing_load_transfer.py first."
    )


def find_preferred_layout(path):
    matches = []

    with path.open(
        "r",
        newline="",
        encoding="utf-8",
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:
            hL = float(row["hL_mm"])
            spacing = float(row["spacing_mm"])
            hU = float(row["hU_mm"])
            Lb = float(row["bushing_length_mm"])

            if (
                abs(hL - preferred_hL_mm) < 1e-12
                and abs(spacing - preferred_spacing_mm) < 1e-12
                and abs(hU - preferred_hU_mm) < 1e-12
                and abs(Lb - preferred_bushing_length_mm) < 1e-12
            ):
                matches.append(row)

    if len(matches) != 1:
        raise RuntimeError(
            "Expected exactly one preferred-layout row in the D3 CSV; "
            f"found {len(matches)}."
        )

    row = matches[0]

    return {
        "limit_lower_case": row["limit_lower_case"],
        "limit_lower_R_kN": float(row["limit_lower_R_kN"]),
        "limit_lower_p_MPa": float(row["limit_lower_p_MPa"]),

        "limit_upper_case": row["limit_upper_case"],
        "limit_upper_R_kN": float(row["limit_upper_R_kN"]),
        "limit_upper_p_MPa": float(row["limit_upper_p_MPa"]),

        "ultimate_lower_case": row["ultimate_lower_case"],
        "ultimate_lower_R_kN": float(row["ultimate_lower_R_kN"]),
        "ultimate_lower_p_MPa": float(row["ultimate_lower_p_MPa"]),

        "ultimate_upper_case": row["ultimate_upper_case"],
        "ultimate_upper_R_kN": float(row["ultimate_upper_R_kN"]),
        "ultimate_upper_p_MPa": float(row["ultimate_upper_p_MPa"]),
    }


layout = find_preferred_layout(
    d3_csv
)


# =============================================================================
# 6. BUSHING STATIC-CAPACITY / TECHNOLOGY COMPARISON
# =============================================================================

limit_pressure_MPa = layout[
    "limit_lower_p_MPa"
]

ultimate_pressure_MPa = layout[
    "ultimate_lower_p_MPa"
]


def margin(
    allowable,
    demand,
):
    return allowable / demand - 1.0


bronze_limit_MS = margin(
    bronze_static_capacity_MPa,
    limit_pressure_MPa,
)

bronze_ultimate_MS = margin(
    bronze_static_capacity_MPa,
    ultimate_pressure_MPa,
)

ptfe_static_limit_MS = margin(
    ptfe_static_limit_MPa,
    limit_pressure_MPa,
)

ptfe_static_ultimate_MS = margin(
    ptfe_static_limit_MPa,
    ultimate_pressure_MPa,
)

ptfe_dynamic_limit_MS = margin(
    ptfe_dynamic_limit_MPa,
    limit_pressure_MPa,
)

ptfe_dynamic_ultimate_MS = margin(
    ptfe_dynamic_limit_MPa,
    ultimate_pressure_MPa,
)


# =============================================================================
# 7. MINIMUM LENGTH IMPLIED BY STATIC CAPACITY
# =============================================================================

def required_length_mm(
    reaction_kN,
    diameter_mm,
    capacity_MPa,
):
    """
    p = F / (D L)
    -> L = F / (D p)

    Units:
        F [N]
        D [mm]
        p [N/mm^2]
        L [mm]
    """

    F_N = reaction_kN * 1000.0

    return (
        F_N
        / (
            diameter_mm
            * capacity_MPa
        )
    )


bronze_required_length_ultimate_mm = required_length_mm(
    layout["ultimate_lower_R_kN"],
    piston_OD_mm,
    bronze_static_capacity_MPa,
)

ptfe_dynamic_required_length_ultimate_mm = required_length_mm(
    layout["ultimate_lower_R_kN"],
    piston_OD_mm,
    ptfe_dynamic_limit_MPa,
)


# =============================================================================
# 8. LOWER GLAND / BARREL-END RADIAL LOAD REQUIREMENTS
# =============================================================================

# Average housing-side projected bearing pressure:
# use bushing OD x axial bushing length.
housing_limit_pressure_MPa = (
    layout["limit_lower_R_kN"] * 1000.0
    / (
        bushing_OD_mm
        * bushing_length_mm
    )
)

housing_ultimate_pressure_MPa = (
    layout["ultimate_lower_R_kN"] * 1000.0
    / (
        bushing_OD_mm
        * bushing_length_mm
    )
)

# Radial line load into the barrel across bushing axial length.
radial_line_load_limit_N_per_mm = (
    layout["limit_lower_R_kN"]
    * 1000.0
    / bushing_length_mm
)

radial_line_load_ultimate_N_per_mm = (
    layout["ultimate_lower_R_kN"]
    * 1000.0
    / bushing_length_mm
)


# =============================================================================
# 9. PRESSURE-THRUST REQUIREMENTS FOR FUTURE GLAND / CLOSURE DESIGN
# =============================================================================

def circular_area_m2(
    diameter_m,
):
    return (
        math.pi
        * diameter_m**2
        / 4.0
    )


A_effective_piston_m2 = circular_area_m2(
    D_effective_piston_m
)

A_barrel_bore_m2 = circular_area_m2(
    D_barrel_bore_m
)

physical_piston_thrust_N = (
    p_physical_Pa
    * A_effective_piston_m2
)

virtual_piston_thrust_N = (
    p_virtual_Pa
    * A_effective_piston_m2
)

physical_full_bore_thrust_N = (
    p_physical_Pa
    * A_barrel_bore_m2
)

virtual_full_bore_thrust_N = (
    p_virtual_Pa
    * A_barrel_bore_m2
)


# =============================================================================
# 10. PROCESS / CONSISTENCY CHECKS
# =============================================================================

# Check that D3 projected pressure really equals R/(D*L).
reconstructed_limit_p_MPa = (
    layout["limit_lower_R_kN"] * 1000.0
    / (
        piston_OD_mm
        * bushing_length_mm
    )
)

reconstructed_ultimate_p_MPa = (
    layout["ultimate_lower_R_kN"] * 1000.0
    / (
        piston_OD_mm
        * bushing_length_mm
    )
)

assert abs(
    reconstructed_limit_p_MPa
    - limit_pressure_MPa
) < 1e-9

assert abs(
    reconstructed_ultimate_p_MPa
    - ultimate_pressure_MPa
) < 1e-9

# Check expected Phase 1 force consistency:
# virtual piston thrust should reproduce the frozen V0.5b gas-force magnitude
# to normal numerical precision.
assert abs(
    virtual_piston_thrust_N / 1000.0
    - 27.781
) < 0.01


# =============================================================================
# 11. WRITE SUMMARY CSV
# =============================================================================

output_csv = (
    here
    / "phase2_bushing_material_gland_requirements.csv"
)

summary_row = {
    "hL_mm": preferred_hL_mm,
    "spacing_mm": preferred_spacing_mm,
    "hU_mm": preferred_hU_mm,
    "bushing_length_mm": preferred_bushing_length_mm,

    "piston_OD_mm": piston_OD_mm,
    "bushing_OD_mm": bushing_OD_mm,
    "bushing_radial_wall_mm": bushing_radial_wall_mm,

    "limit_lower_R_kN": layout["limit_lower_R_kN"],
    "ultimate_lower_R_kN": layout["ultimate_lower_R_kN"],

    "limit_piston_side_pressure_MPa": limit_pressure_MPa,
    "ultimate_piston_side_pressure_MPa": ultimate_pressure_MPa,

    "AMS4640_static_capacity_MPa": bronze_static_capacity_MPa,
    "AMS4640_limit_MS": bronze_limit_MS,
    "AMS4640_ultimate_MS": bronze_ultimate_MS,

    "PTFE_static_limit_MPa": ptfe_static_limit_MPa,
    "PTFE_dynamic_limit_MPa": ptfe_dynamic_limit_MPa,
    "PTFE_dynamic_ultimate_MS": ptfe_dynamic_ultimate_MS,

    "AMS4640_required_length_ultimate_mm":
        bronze_required_length_ultimate_mm,

    "PTFE_dynamic_required_length_ultimate_mm":
        ptfe_dynamic_required_length_ultimate_mm,

    "housing_limit_pressure_MPa":
        housing_limit_pressure_MPa,

    "housing_ultimate_pressure_MPa":
        housing_ultimate_pressure_MPa,

    "radial_line_load_limit_N_per_mm":
        radial_line_load_limit_N_per_mm,

    "radial_line_load_ultimate_N_per_mm":
        radial_line_load_ultimate_N_per_mm,

    "physical_pressure_MPa":
        p_physical_Pa / 1e6,

    "virtual_pressure_MPa":
        p_virtual_Pa / 1e6,

    "physical_piston_thrust_kN":
        physical_piston_thrust_N / 1000.0,

    "virtual_piston_thrust_kN":
        virtual_piston_thrust_N / 1000.0,

    "physical_full_bore_thrust_kN":
        physical_full_bore_thrust_N / 1000.0,

    "virtual_full_bore_thrust_kN":
        virtual_full_bore_thrust_N / 1000.0,
}


with output_csv.open(
    "w",
    newline="",
    encoding="utf-8",
) as file:

    writer = csv.DictWriter(
        file,
        fieldnames=list(
            summary_row.keys()
        ),
    )

    writer.writeheader()
    writer.writerow(
        summary_row
    )


# =============================================================================
# 12. CONSOLE REPORT
# =============================================================================

print()
print("=" * 102)
print(
    " PHASE 2D5 — BUSHING MATERIAL SCREEN + "
    "LOWER GLAND / BARREL-END LOAD REQUIREMENTS"
)
print("=" * 102)

print()
print("--- INPUT CONNECTION ---")
print(
    f"Phase 2D3 result file:            "
    f"{d3_csv}"
)

print()
print("--- PREFERRED WORKING LAYOUT ---")
print(
    f"h_L / spacing / h_U:              "
    f"{preferred_hL_mm:.0f} / "
    f"{preferred_spacing_mm:.0f} / "
    f"{preferred_hU_mm:.0f} mm"
)
print(
    f"Bushing axial length:             "
    f"{bushing_length_mm:.1f} mm"
)
print(
    f"Piston OD:                        "
    f"{piston_OD_mm:.1f} mm"
)
print(
    f"Bushing OD / barrel bore:         "
    f"{bushing_OD_mm:.1f} mm"
)
print(
    f"Bronze radial wall:               "
    f"{bushing_radial_wall_mm:.1f} mm"
)

print()
print("--- CALCULATED D3 LOWER-BUSHING DEMAND ---")
print(
    f"Limit governing case:             "
    f"{layout['limit_lower_case']}"
)
print(
    f"Limit radial reaction:            "
    f"{layout['limit_lower_R_kN']:.3f} kN"
)
print(
    f"Limit projected pressure:         "
    f"{limit_pressure_MPa:.3f} MPa"
)
print()
print(
    f"Ultimate governing case:          "
    f"{layout['ultimate_lower_case']}"
)
print(
    f"Ultimate radial reaction:         "
    f"{layout['ultimate_lower_R_kN']:.3f} kN"
)
print(
    f"Ultimate projected pressure:      "
    f"{ultimate_pressure_MPa:.3f} MPa"
)

print()
print("--- PRIMARY MATERIAL: C63000 / AMS 4640 Ni-Al BRONZE ---")
print(
    f"Preliminary static capacity:      "
    f"{bronze_static_capacity_MPa:.1f} MPa"
)
print(
    f"Margin at limit demand:           "
    f"{bronze_limit_MS:+.3f}"
)
print(
    f"Margin at ultimate demand:        "
    f"{bronze_ultimate_MS:+.3f}"
)
print(
    f"Length required by static-capacity "
    f"screen at ultimate: {bronze_required_length_ultimate_mm:.2f} mm"
)
print(
    "Interpretation: static bearing capacity is NOT the driver of the 30 mm length."
)

print()
print("--- PTFE-COMPOSITE TECHNOLOGY COMPARISON ---")
print(
    f"Catalog static specific load:     "
    f"{ptfe_static_limit_MPa:.1f} MPa"
)
print(
    f"Catalog dynamic specific load:    "
    f"{ptfe_dynamic_limit_MPa:.1f} MPa"
)
print(
    f"Ultimate margin vs static value:  "
    f"{ptfe_static_ultimate_MS:+.3f}"
)
print(
    f"Ultimate margin vs dynamic value: "
    f"{ptfe_dynamic_ultimate_MS:+.3f}"
)
print(
    f"Length required vs dynamic value: "
    f"{ptfe_dynamic_required_length_ultimate_mm:.2f} mm"
)
print(
    "PTFE option still requires p-v / life / temperature / surface-finish checks."
)

print()
print("--- LOWER GLAND / BARREL-END RADIAL REQUIREMENTS ---")
print(
    f"Housing-side average pressure, limit:    "
    f"{housing_limit_pressure_MPa:.3f} MPa"
)
print(
    f"Housing-side average pressure, ultimate: "
    f"{housing_ultimate_pressure_MPa:.3f} MPa"
)
print(
    f"Radial line load into barrel, limit:     "
    f"{radial_line_load_limit_N_per_mm:.1f} N/mm"
)
print(
    f"Radial line load into barrel, ultimate:  "
    f"{radial_line_load_ultimate_N_per_mm:.1f} N/mm"
)

print()
print("--- PRESSURE-THRUST REQUIREMENTS ---")
print(
    f"Physical-stroke gas pressure:     "
    f"{p_physical_Pa/1e6:.3f} MPa"
)
print(
    f"58 mm effective-piston thrust:    "
    f"{physical_piston_thrust_N/1000:.3f} kN"
)
print(
    f"64 mm full-bore closure thrust:   "
    f"{physical_full_bore_thrust_N/1000:.3f} kN"
)
print()
print(
    f"V0.5b virtual gas pressure:       "
    f"{p_virtual_Pa/1e6:.3f} MPa"
)
print(
    f"58 mm effective-piston thrust:    "
    f"{virtual_piston_thrust_N/1000:.3f} kN"
)
print(
    f"64 mm full-bore closure thrust:   "
    f"{virtual_full_bore_thrust_N/1000:.3f} kN"
)

print()
print("--- PHASE 2D5 INTERPRETATION ---")
print(
    "AMS 4640 nickel-aluminum bronze is retained as the primary preliminary "
    "guide-bushing material."
)
print(
    "The 30 mm bushing length is NOT strength-driven by static projected pressure; "
    "it is being retained for load distribution, wear, stiffness, and packaging."
)
print(
    "The gland/barrel-end region must later carry BOTH the calculated radial "
    "bushing load and an axial pressure-thrust requirement."
)
print(
    "A groove / thread / shoulder stress calculation is NOT performed yet because "
    "the actual retainer geometry has not been defined."
)

print()
print("Consistency checks:               PASS")
print(
    f"CSV written to:                   "
    f"{output_csv.name}"
)
print("=" * 102)
