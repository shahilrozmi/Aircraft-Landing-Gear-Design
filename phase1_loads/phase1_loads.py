"""
Landing_Gear_Design_Project
Phase 1A — Frozen Aircraft / Landing-Gear Load Envelope

Purpose
-------
Reproduce and document the frozen LC0–LC5 load envelope used by Phase 2.

Important:
- Phase 1 is FROZEN. This script documents the accepted baseline; it does not retune it.
- The original screening calculations used a rounded design weight W = 16.68 kN.
- The exact mass-based weight m*g is printed for reference, but the rounded design
  weight is retained so the code reproduces the locked 25.02, 8.34, 11.09, 8.87 kN values.
"""

import csv
from pathlib import Path


# ============================================================
# 1. LOCKED AIRCRAFT BASELINE
# ============================================================

g = 9.80665                         # [m/s^2]
m_aircraft = 1700.0                # [kg]

W_exact = m_aircraft * g            # [N]
W = 16.68e3                         # [N] frozen Phase 1 screening/design weight

wheelbase = 2.35                    # [m]
track = 3.20                        # [m]

x_cg_min = 0.25                    # [m] forward of main-gear line
x_cg_nom = 0.30                    # [m]
x_cg_max = 0.35                    # [m]

h_cg = 0.90                         # [m]

ultimate_factor = 1.50


# ============================================================
# 2. HELPER FUNCTIONS
# ============================================================

def static_reactions(x_cg):
    """
    Static vertical reactions for a tricycle aircraft.

    Coordinate convention:
    - main-gear line at x = 0
    - nose gear at x = +wheelbase
    - CG at x = +x_cg (forward of the mains)

    From vertical-force and pitch-moment equilibrium:

        R_N = W * x_cg / L

        R_M,total = W * (L - x_cg) / L

        R_main,each = R_M,total / 2
    """

    R_nose = W * x_cg / wheelbase

    R_mains_total = (
        W * (wheelbase - x_cg) / wheelbase
    )

    R_main_each = R_mains_total / 2.0

    return R_nose, R_mains_total, R_main_each


def multiply_case(case, factor):
    """Multiply all force components of one load case by factor."""

    return {
        "Fx_N": factor * case["Fx_N"],
        "Fy_N": factor * case["Fy_N"],
        "Fz_N": factor * case["Fz_N"],
    }


# ============================================================
# 3. LC0 — STATIC GROUND LOAD, WORST CG FOR MAIN GEAR
# ============================================================

# Main-gear reaction is greatest at the most aft CG in this coordinate definition,
# i.e. the smallest x_cg value (closest to the main-gear line).

R_nose_LC0, R_mains_total_LC0, R_main_each_LC0 = static_reactions(x_cg_min)

LC0 = {
    "Fx_N": 0.0,
    "Fy_N": 0.0,
    "Fz_N": R_main_each_LC0,
}


# ============================================================
# 4. LC1 — SYMMETRIC DESIGN LANDING
# ============================================================

# Frozen preliminary project target:
#
#   total main-gear reaction = lambda_g_limit * W
#
# with lambda_g_limit = 3.0.
#
# Symmetric landing => divide equally between two mains.

lambda_g_limit = 3.0

R_mains_total_LC1 = lambda_g_limit * W
R_main_each_LC1 = R_mains_total_LC1 / 2.0

LC1 = {
    "Fx_N": 0.0,
    "Fy_N": 0.0,
    "Fz_N": R_main_each_LC1,
}


# ============================================================
# 5. LC2A / LC2B — SPIN-UP / SPRING-BACK SCREENING
# ============================================================

# Frozen screening rule:
#
#   |Fx| = 0.25 * Fz
#
# LC2A: spin-up direction
# LC2B: spring-back direction
#
# This is retained as the accepted preliminary load envelope.
# A more detailed wheel rotational transient may be studied later,
# but it does not change the frozen Phase 1 envelope.

longitudinal_fraction = 0.25

Fx_LC2_mag = longitudinal_fraction * R_main_each_LC1

LC2A = {
    "Fx_N": -Fx_LC2_mag,
    "Fy_N": 0.0,
    "Fz_N": R_main_each_LC1,
}

LC2B = {
    "Fx_N": +Fx_LC2_mag,
    "Fy_N": 0.0,
    "Fz_N": R_main_each_LC1,
}


# ============================================================
# 6. LC3 — ONE-WHEEL LANDING
# ============================================================

# Frozen baseline:
# the contacting main gear carries the same 25.02 kN limit vertical
# load used for one main in LC1; the opposite main is unloaded.

LC3 = {
    "Fx_N": 0.0,
    "Fy_N": 0.0,
    "Fz_N": R_main_each_LC1,
}


# ============================================================
# 7. LC4 — SIDE-LOAD SCREENING
# ============================================================

# Frozen screening basis:
#
#   vertical load factor n_z = 1.33
#   per-main vertical reaction = 1.33 W / 2
#
# Legacy lateral split:
#   heavy/inboard main  = 0.50 W
#   opposite/outboard   = 0.33 W
#
# The structural detailed-gear envelope must check either lateral direction,
# so the critical 0.50 W magnitude is applied as +/- Fy.

nz_side = 1.33

Fz_LC4 = nz_side * W / 2.0

Fy_LC4_heavy = 0.50 * W
Fy_LC4_other = 0.33 * W       # retained for documentation only

LC4_plus = {
    "Fx_N": 0.0,
    "Fy_N": +Fy_LC4_heavy,
    "Fz_N": Fz_LC4,
}

LC4_minus = {
    "Fx_N": 0.0,
    "Fy_N": -Fy_LC4_heavy,
    "Fz_N": Fz_LC4,
}


# ============================================================
# 8. LC5 — BRAKED-ROLL SCREENING
# ============================================================

# Frozen LC5 nose-clear screening subcase:
#
#   n_z = 1.33
#   R_N = 0
#   R_M,total = n_z W
#
# Therefore:
#
#   Fz per main = n_z W / 2
#
# With mains-braked friction coefficient:
#
#   |Fx| = mu_b * Fz
#
# Braking direction is negative x.

nz_brake = 1.33
mu_brake = 0.80

R_nose_LC5 = 0.0
R_mains_total_LC5 = nz_brake * W
R_main_each_LC5 = R_mains_total_LC5 / 2.0

Fx_LC5 = -mu_brake * R_main_each_LC5

LC5 = {
    "Fx_N": Fx_LC5,
    "Fy_N": 0.0,
    "Fz_N": R_main_each_LC5,
}


# ============================================================
# 9. ASSEMBLE FROZEN LIMIT + ULTIMATE ENVELOPES
# ============================================================

limit_cases = {
    "LC0": LC0,
    "LC1": LC1,
    "LC2A": LC2A,
    "LC2B": LC2B,
    "LC3": LC3,
    "LC4+": LC4_plus,
    "LC4-": LC4_minus,
    "LC5": LC5,
}

ultimate_cases = {
    name: multiply_case(case, ultimate_factor)
    for name, case in limit_cases.items()
}


# ============================================================
# 10. REGRESSION CHECKS AGAINST FROZEN PHASE 1 VALUES
# ============================================================

frozen_reference_kN = {
    "LC0":  {"Fx": 0.00,  "Fy": 0.00,  "Fz": 7.45},
    "LC1":  {"Fx": 0.00,  "Fy": 0.00,  "Fz": 25.02},
    "LC2A": {"Fx": -6.25, "Fy": 0.00,  "Fz": 25.02},
    "LC2B": {"Fx": +6.25, "Fy": 0.00,  "Fz": 25.02},
    "LC3":  {"Fx": 0.00,  "Fy": 0.00,  "Fz": 25.02},
    "LC4+": {"Fx": 0.00,  "Fy": +8.34, "Fz": 11.09},
    "LC4-": {"Fx": 0.00,  "Fy": -8.34, "Fz": 11.09},
    "LC5":  {"Fx": -8.87, "Fy": 0.00,  "Fz": 11.09},
}

tolerance_kN = 0.015

for name, case in limit_cases.items():

    calculated = {
        "Fx": case["Fx_N"] / 1000.0,
        "Fy": case["Fy_N"] / 1000.0,
        "Fz": case["Fz_N"] / 1000.0,
    }

    reference = frozen_reference_kN[name]

    for component in ("Fx", "Fy", "Fz"):

        error = abs(
            calculated[component]
            - reference[component]
        )

        assert error <= tolerance_kN, (
            f"{name} {component} regression failed: "
            f"calculated={calculated[component]:.4f} kN, "
            f"reference={reference[component]:.4f} kN"
        )


# ============================================================
# 11. WRITE CSV RESULT TABLE
# ============================================================

output_path = Path(__file__).resolve().parent / "phase1_load_envelope.csv"

with output_path.open("w", newline="") as file:

    writer = csv.writer(file)

    writer.writerow([
        "Load Case",
        "Fx Limit (kN)",
        "Fy Limit (kN)",
        "Fz Limit (kN)",
        "Fx Ultimate (kN)",
        "Fy Ultimate (kN)",
        "Fz Ultimate (kN)",
    ])

    for name in limit_cases:

        limit = limit_cases[name]
        ultimate = ultimate_cases[name]

        writer.writerow([
            name,
            limit["Fx_N"] / 1000.0,
            limit["Fy_N"] / 1000.0,
            limit["Fz_N"] / 1000.0,
            ultimate["Fx_N"] / 1000.0,
            ultimate["Fy_N"] / 1000.0,
            ultimate["Fz_N"] / 1000.0,
        ])


# ============================================================
# 12. PRINT ENGINEERING REPORT
# ============================================================

print()
print("=" * 76)
print(" PHASE 1A — FROZEN LANDING-GEAR LOAD ENVELOPE")
print("=" * 76)

print()
print("--- AIRCRAFT BASELINE ---")
print(f"Aircraft mass:                    {m_aircraft:.1f} kg")
print(f"Exact m*g weight:                 {W_exact / 1000:.4f} kN")
print(f"Frozen screening weight:          {W / 1000:.2f} kN")
print(f"Wheelbase:                        {wheelbase:.3f} m")
print(f"Track:                            {track:.3f} m")
print(f"CG range forward of mains:        {x_cg_min:.2f} to {x_cg_max:.2f} m")
print(f"CG height:                        {h_cg:.3f} m")
print(f"Ultimate factor:                  {ultimate_factor:.2f}")

print()
print("--- LC0 STATIC REACTIONS AT WORST MAIN-GEAR CG ---")
print(f"Nose reaction:                    {R_nose_LC0 / 1000:.3f} kN")
print(f"Total main reaction:              {R_mains_total_LC0 / 1000:.3f} kN")
print(f"Each main reaction:               {R_main_each_LC0 / 1000:.3f} kN")

print()
print("--- LC4 LEGACY SIDE-LOAD SPLIT ---")
print(f"Per-main vertical load:           {Fz_LC4 / 1000:.3f} kN")
print(f"Heavy/inboard lateral load:       {Fy_LC4_heavy / 1000:.3f} kN")
print(f"Opposite/outboard lateral load:   {Fy_LC4_other / 1000:.3f} kN")

print()
print("--- FROZEN LIMIT / ULTIMATE LOAD CASES ---")

header = (
    f"{'Case':<7}"
    f"{'Fx_lim':>10}"
    f"{'Fy_lim':>10}"
    f"{'Fz_lim':>10}"
    f"{'Fx_ult':>10}"
    f"{'Fy_ult':>10}"
    f"{'Fz_ult':>10}"
)

print(header)
print("-" * len(header))

for name in limit_cases:

    L = limit_cases[name]
    U = ultimate_cases[name]

    print(
        f"{name:<7}"
        f"{L['Fx_N']/1000:>10.2f}"
        f"{L['Fy_N']/1000:>10.2f}"
        f"{L['Fz_N']/1000:>10.2f}"
        f"{U['Fx_N']/1000:>10.2f}"
        f"{U['Fy_N']/1000:>10.2f}"
        f"{U['Fz_N']/1000:>10.2f}"
    )

print()
print("Regression checks:                PASS")
print(f"CSV written to:                   {output_path.name}")
print("=" * 76)
