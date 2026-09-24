"""
Landing_Gear_Design_Project
Phase 2D7 — Lower Barrel Boss / Shoulder Local Radial-Load Sizing

Purpose
-------
Screen the locally thickened lower barrel boss and the transition back to the
smooth outer barrel under the CALCULATED lower-bushing radial reaction.

The script reads:
    1) phase2_bushing_material_gland_requirements.csv  (Phase 2D5)
    2) phase2_internal_loads.csv                       (Phase 2C)

No reaction, moment, or stress result from chat is used as an input.

Local load-path model
---------------------
The lower bronze guide bushing transfers a resultant radial force R_L into the
barrel-end boss.  The load is distributed over the 30 mm bushing length.

For a preliminary beam-section screen, the distributed load is replaced by its
resultant acting at the bushing mid-plane.

The critical section is taken at the boss-to-smooth-barrel transition, located a
distance 'land' above the upper edge of the lower bushing:

    lever arm = L_b/2 + land

    M_local = R_L * lever arm
    V_local = R_L

This local barrel segment lies BELOW the upper guide bushing.  Therefore the
lower-bushing reaction is the appropriate local transverse load; we do NOT add
the Phase 2C upper-interface bending moment again, which would double-count the
same load path.

The LC4+ axial compression Fz is read directly from the Phase 2C CSV and is
included at the transition section.

Pressure combination
--------------------
The physical-stroke gas pressure from Phase 2D5 is conservatively combined with
the LC4+ radial/axial structural case.  These maxima are not guaranteed to be
simultaneous, so this remains a bounding preliminary screen.

Transition geometry
-------------------
Working smooth barrel:
    ID = 64 mm
    OD = 74 mm

Working local boss:
    OD = 84 mm

The boss-to-barrel OD step is therefore 84 -> 74 mm.

The fillet radius is NOT yet defined, so no fake chart-derived stress
concentration factor is assigned.  Instead the script:
    - reports nominal stress (Kt = 1)
    - reports sensitivity at Kt = 1.5, 2.0, 2.5, 3.0
    - solves for the maximum bending Kt that would exhaust the selected
      yield/ultimate screening strength

Kt is applied only to the OUTER-SURFACE bending stress at the shoulder root.
Pressure stresses and axial membrane stress are not multiplied by this Kt.

Important limitations
---------------------
This is a local beam/thick-cylinder SCREEN, not a shell/contact FEA.

It does not yet capture:
    - barrel ovalization from localized bushing contact
    - detailed 3-D shoulder load spreading
    - actual fillet stress concentration
    - thread/bushing/gland interaction
    - elastic bushing load distribution
    - fatigue / fracture mechanics

Those are later detailed-design / FEA tasks.
"""

import csv
import math
from pathlib import Path


# =============================================================================
# 1. PRELIMINARY 300M MATERIAL BASIS
# =============================================================================

Sy_Pa = 1517e6
Su_Pa = 1862e6


# =============================================================================
# 2. WORKING LOCAL GEOMETRY
# =============================================================================

barrel_ID_mm = 64.0
barrel_OD_mm = 74.0
boss_OD_mm = 84.0

bushing_length_mm = 30.0

# Distance from upper edge of lower bushing to the nominal smooth-barrel
# shoulder/root section.  Swept rather than frozen.
transition_land_values_mm = [
    5.0,
    10.0,
    15.0,
    20.0,
    30.0,
    40.0,
]

working_land_mm = 15.0

Kt_values = [
    1.0,
    1.5,
    2.0,
    2.5,
    3.0,
]


# =============================================================================
# 3. FIND INPUT FILES
# =============================================================================

here = Path(__file__).resolve().parent

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


p2c_candidates = [
    here / "phase2_internal_loads.csv",
    here.parent
    / "phase2_structures"
    / "phase2_internal_loads.csv",
]

p2c_csv = None
for path in p2c_candidates:
    if path.exists():
        p2c_csv = path
        break

if p2c_csv is None:
    raise FileNotFoundError(
        "Could not find phase2_internal_loads.csv. "
        "Run Phase 2C first."
    )


# =============================================================================
# 4. READ D5 LOWER-BUSHING / PRESSURE REQUIREMENTS
# =============================================================================

with d5_csv.open(
    "r",
    newline="",
    encoding="utf-8",
) as file:
    rows = list(
        csv.DictReader(file)
    )

if len(rows) != 1:
    raise RuntimeError(
        "Expected exactly one Phase 2D5 summary row."
    )

d5 = rows[0]

R_limit_kN = float(
    d5["limit_lower_R_kN"]
)

R_ultimate_kN = float(
    d5["ultimate_lower_R_kN"]
)

housing_limit_pressure_MPa = float(
    d5["housing_limit_pressure_MPa"]
)

housing_ultimate_pressure_MPa = float(
    d5["housing_ultimate_pressure_MPa"]
)

physical_pressure_MPa = float(
    d5["physical_pressure_MPa"]
)

virtual_pressure_MPa = float(
    d5["virtual_pressure_MPa"]
)


# =============================================================================
# 5. READ CONSISTENT LC4+ AXIAL LOAD DIRECTLY FROM PHASE 2C
# =============================================================================

def read_lc4plus_axial(path):
    result = {}

    with path.open(
        "r",
        newline="",
        encoding="utf-8",
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:
            if row["case"] == "LC4+":
                level = row["level"]
                result[level] = abs(
                    float(row["Fz_kN"])
                )

    if (
        "limit" not in result
        or "ultimate" not in result
    ):
        raise RuntimeError(
            "Could not find both limit and ultimate LC4+ rows."
        )

    return result


lc4_axial = read_lc4plus_axial(
    p2c_csv
)

Fz_limit_kN = lc4_axial["limit"]
Fz_ultimate_kN = lc4_axial["ultimate"]


# =============================================================================
# 6. SECTION PROPERTIES
# =============================================================================

def annulus_properties(
    ID_mm,
    OD_mm,
):
    a_m = (
        ID_mm / 1000.0
        / 2.0
    )

    b_m = (
        OD_mm / 1000.0
        / 2.0
    )

    if b_m <= a_m:
        raise ValueError(
            "OD must exceed ID."
        )

    A_m2 = math.pi * (
        b_m**2
        - a_m**2
    )

    I_m4 = (
        math.pi
        / 4.0
        * (
            b_m**4
            - a_m**4
        )
    )

    J_m4 = 2.0 * I_m4

    return {
        "a_m": a_m,
        "b_m": b_m,
        "A_m2": A_m2,
        "I_m4": I_m4,
        "J_m4": J_m4,
    }


section = annulus_properties(
    barrel_ID_mm,
    barrel_OD_mm,
)


# =============================================================================
# 7. LAME PRESSURE STRESSES
# =============================================================================

def lame_stresses_Pa(
    p_Pa,
    a_m,
    b_m,
    r_m,
):
    denom = (
        b_m**2
        - a_m**2
    )

    A_L = (
        p_Pa
        * a_m**2
        / denom
    )

    B_L = (
        p_Pa
        * a_m**2
        * b_m**2
        / denom
    )

    sigma_r = (
        A_L
        - B_L / r_m**2
    )

    sigma_theta = (
        A_L
        + B_L / r_m**2
    )

    # Closed-end pressure axial membrane stress.
    sigma_z_pressure = A_L

    return {
        "sigma_r_Pa": sigma_r,
        "sigma_theta_Pa": sigma_theta,
        "sigma_z_pressure_Pa": sigma_z_pressure,
    }


# =============================================================================
# 8. VON MISES
# =============================================================================

def vm_3d_Pa(
    sigma_r,
    sigma_theta,
    sigma_z,
    tau=0.0,
):
    return math.sqrt(
        0.5
        * (
            (sigma_theta - sigma_r)**2
            + (sigma_r - sigma_z)**2
            + (sigma_z - sigma_theta)**2
        )
        + 3.0 * tau**2
    )


# =============================================================================
# 9. LOCAL TRANSITION STRESS EVALUATION
# =============================================================================

def evaluate_case(
    reaction_kN,
    axial_kN,
    pressure_MPa,
    land_mm,
    Kt_bending,
):
    A = section["A_m2"]
    I = section["I_m4"]
    a = section["a_m"]
    b = section["b_m"]

    lever_arm_m = (
        bushing_length_mm / 2.0
        + land_mm
    ) / 1000.0

    V_N = (
        reaction_kN
        * 1000.0
    )

    M_Nm = (
        V_N
        * lever_arm_m
    )

    N_N = (
        axial_kN
        * 1000.0
    )

    p_Pa = (
        pressure_MPa
        * 1e6
    )

    candidates = []

    for surface, r in (
        ("inner", a),
        ("outer", b),
    ):

        pressure = lame_stresses_Pa(
            p_Pa,
            a,
            b,
            r,
        )

        sigma_axial_structural = (
            -N_N / A
        )

        # Shoulder Kt applies only to the outer-surface bending stress.
        local_Kt = (
            Kt_bending
            if surface == "outer"
            else 1.0
        )

        sigma_bending = (
            local_Kt
            * M_Nm
            * r
            / I
        )

        for side in (
            -1.0,
            +1.0,
        ):

            sigma_z = (
                pressure["sigma_z_pressure_Pa"]
                + sigma_axial_structural
                + side * sigma_bending
            )

            vm = vm_3d_Pa(
                pressure["sigma_r_Pa"],
                pressure["sigma_theta_Pa"],
                sigma_z,
            )

            candidates.append({
                "surface": surface,
                "bending_side": side,
                "sigma_r_Pa":
                    pressure["sigma_r_Pa"],
                "sigma_theta_Pa":
                    pressure["sigma_theta_Pa"],
                "sigma_z_Pa": sigma_z,
                "sigma_bending_Pa":
                    side * sigma_bending,
                "vm_Pa": vm,
            })

    worst = max(
        candidates,
        key=lambda row: row["vm_Pa"],
    )

    # Separate conservative transverse-shear screen.
    tau_transverse_screen_Pa = (
        2.0
        * V_N
        / A
    )

    return {
        "lever_arm_mm":
            lever_arm_m * 1000.0,
        "local_moment_kNm":
            M_Nm / 1000.0,
        "local_shear_kN":
            V_N / 1000.0,
        "surface":
            worst["surface"],
        "bending_side":
            worst["bending_side"],
        "vm_MPa":
            worst["vm_Pa"] / 1e6,
        "sigma_theta_MPa":
            worst["sigma_theta_Pa"] / 1e6,
        "sigma_z_MPa":
            worst["sigma_z_Pa"] / 1e6,
        "tau_transverse_screen_MPa":
            tau_transverse_screen_Pa / 1e6,
    }


# =============================================================================
# 10. SOLVE MAXIMUM ALLOWABLE BENDING Kt
# =============================================================================

def allowable_Kt(
    reaction_kN,
    axial_kN,
    pressure_MPa,
    land_mm,
    allowable_Pa,
):
    """
    Find Kt such that worst VM == allowable.
    If the design still passes at Kt = 50, return >50.
    """

    def demand_Pa(Kt):
        return (
            evaluate_case(
                reaction_kN,
                axial_kN,
                pressure_MPa,
                land_mm,
                Kt,
            )["vm_MPa"]
            * 1e6
        )

    if demand_Pa(1.0) > allowable_Pa:
        return 1.0

    upper = 50.0

    if demand_Pa(upper) <= allowable_Pa:
        return float("inf")

    lower = 1.0

    for _ in range(100):
        mid = (
            lower + upper
        ) / 2.0

        if demand_Pa(mid) <= allowable_Pa:
            lower = mid
        else:
            upper = mid

    return lower


# =============================================================================
# 11. SWEEP
# =============================================================================

rows_out = []

for land_mm in transition_land_values_mm:

    Kt_allow_limit = allowable_Kt(
        R_limit_kN,
        Fz_limit_kN,
        physical_pressure_MPa,
        land_mm,
        Sy_Pa,
    )

    Kt_allow_ultimate = allowable_Kt(
        R_ultimate_kN,
        Fz_ultimate_kN,
        physical_pressure_MPa,
        land_mm,
        Su_Pa,
    )

    for Kt in Kt_values:

        lim = evaluate_case(
            R_limit_kN,
            Fz_limit_kN,
            physical_pressure_MPa,
            land_mm,
            Kt,
        )

        ult = evaluate_case(
            R_ultimate_kN,
            Fz_ultimate_kN,
            physical_pressure_MPa,
            land_mm,
            Kt,
        )

        rows_out.append({
            "land_mm": land_mm,
            "lever_arm_mm":
                ult["lever_arm_mm"],
            "Kt_bending": Kt,

            "limit_local_moment_kNm":
                lim["local_moment_kNm"],
            "ultimate_local_moment_kNm":
                ult["local_moment_kNm"],

            "limit_vm_MPa":
                lim["vm_MPa"],
            "ultimate_vm_MPa":
                ult["vm_MPa"],

            "limit_surface":
                lim["surface"],
            "ultimate_surface":
                ult["surface"],

            "limit_tau_transverse_screen_MPa":
                lim[
                    "tau_transverse_screen_MPa"
                ],
            "ultimate_tau_transverse_screen_MPa":
                ult[
                    "tau_transverse_screen_MPa"
                ],

            "MS_limit_yield":
                Sy_Pa / (
                    lim["vm_MPa"] * 1e6
                ) - 1.0,

            "MS_ultimate":
                Su_Pa / (
                    ult["vm_MPa"] * 1e6
                ) - 1.0,

            "Kt_allow_limit":
                Kt_allow_limit,

            "Kt_allow_ultimate":
                Kt_allow_ultimate,
        })


# =============================================================================
# 12. WORKING SCREEN
# =============================================================================

def get_row(
    land_mm,
    Kt,
):
    for row in rows_out:
        if (
            abs(
                row["land_mm"]
                - land_mm
            ) < 1e-12
            and abs(
                row["Kt_bending"]
                - Kt
            ) < 1e-12
        ):
            return row

    raise KeyError(
        "Requested D7 row not found."
    )


working_Kt_2 = get_row(
    working_land_mm,
    2.0,
)

working_Kt_3 = get_row(
    working_land_mm,
    3.0,
)


# =============================================================================
# 13. CONSISTENCY CHECKS
# =============================================================================

assert R_ultimate_kN > R_limit_kN
assert Fz_ultimate_kN > Fz_limit_kN
assert boss_OD_mm > barrel_OD_mm
assert barrel_OD_mm > barrel_ID_mm

# Local beam equilibrium check:
expected_ultimate_M_kNm = (
    R_ultimate_kN
    * (
        bushing_length_mm / 2.0
        + working_land_mm
    )
    / 1000.0
)

assert abs(
    working_Kt_2[
        "ultimate_local_moment_kNm"
    ]
    - expected_ultimate_M_kNm
) < 1e-12


# =============================================================================
# 14. CSV OUTPUT
# =============================================================================

output_csv = (
    here
    / "phase2_lower_barrel_boss_sizing.csv"
)

with output_csv.open(
    "w",
    newline="",
    encoding="utf-8",
) as file:

    writer = csv.DictWriter(
        file,
        fieldnames=list(
            rows_out[0].keys()
        ),
    )

    writer.writeheader()
    writer.writerows(
        rows_out
    )


# =============================================================================
# 15. CONSOLE REPORT
# =============================================================================

print()
print("=" * 108)
print(
    " PHASE 2D7 — LOWER BARREL BOSS / SHOULDER "
    "LOCAL RADIAL-LOAD SIZING"
)
print("=" * 108)

print()
print("--- INPUT CONNECTION ---")
print(
    f"Phase 2D5 result file:            "
    f"{d5_csv}"
)
print(
    f"Phase 2C result file:             "
    f"{p2c_csv}"
)

print()
print("--- WORKING LOCAL GEOMETRY ---")
print(
    f"Smooth barrel ID / OD:            "
    f"{barrel_ID_mm:.1f} / "
    f"{barrel_OD_mm:.1f} mm"
)
print(
    f"Local boss OD:                    "
    f"{boss_OD_mm:.1f} mm"
)
print(
    f"Boss-to-barrel OD step:           "
    f"{boss_OD_mm:.1f} -> "
    f"{barrel_OD_mm:.1f} mm"
)
print(
    f"Bushing length:                   "
    f"{bushing_length_mm:.1f} mm"
)
print(
    f"Transition land sweep:            "
    f"{', '.join(f'{x:.0f}' for x in transition_land_values_mm)} mm"
)

print()
print("--- CALCULATED LOAD REQUIREMENTS ---")
print(
    f"Lower radial reaction, limit:     "
    f"{R_limit_kN:.3f} kN"
)
print(
    f"Lower radial reaction, ultimate:  "
    f"{R_ultimate_kN:.3f} kN"
)
print(
    f"LC4+ axial compression, limit:    "
    f"{Fz_limit_kN:.3f} kN"
)
print(
    f"LC4+ axial compression, ultimate: "
    f"{Fz_ultimate_kN:.3f} kN"
)
print(
    f"Conservative pressure combination:"
    f" {physical_pressure_MPa:.3f} MPa"
)
print(
    f"Housing projected pressure, ult:  "
    f"{housing_ultimate_pressure_MPa:.3f} MPa"
)

print()
print(
    "--- WORKING TRANSITION: "
    f"{working_land_mm:.0f} mm LAND ---"
)
print(
    f"Reaction-centroid lever arm:      "
    f"{working_Kt_2['lever_arm_mm']:.1f} mm"
)
print(
    f"Local ultimate bending moment:    "
    f"{working_Kt_2['ultimate_local_moment_kNm']:.3f} kN*m"
)
print(
    f"Separate transverse-shear screen: "
    f"{working_Kt_2['ultimate_tau_transverse_screen_MPa']:.1f} MPa"
)

print()
print("--- STRESS-CONCENTRATION SENSITIVITY ---")
print(
    f"{'Kt':>6}"
    f"{'Limit VM MPa':>16}"
    f"{'MS_yield':>12}"
    f"{'Ult VM MPa':>16}"
    f"{'MS_ult':>12}"
)
print("-" * 62)

for Kt in Kt_values:
    row = get_row(
        working_land_mm,
        Kt,
    )

    print(
        f"{Kt:>6.1f}"
        f"{row['limit_vm_MPa']:>16.1f}"
        f"{row['MS_limit_yield']:>12.3f}"
        f"{row['ultimate_vm_MPa']:>16.1f}"
        f"{row['MS_ultimate']:>12.3f}"
    )

print()
print("--- ALLOWABLE Kt BEFORE SCREENING FAILURE ---")
print(
    f"Limit/yield allowable Kt:         "
    f"{working_Kt_2['Kt_allow_limit']:.2f}"
)
print(
    f"Ultimate-strength allowable Kt:   "
    f"{working_Kt_2['Kt_allow_ultimate']:.2f}"
)

print()
print("--- LAND-LENGTH EFFECT AT Kt = 2.0 ---")
print(
    f"{'Land mm':>10}"
    f"{'Lever mm':>12}"
    f"{'M_ult kNm':>14}"
    f"{'VM_ult MPa':>14}"
    f"{'MS_ult':>12}"
)
print("-" * 66)

for land_mm in transition_land_values_mm:
    row = get_row(
        land_mm,
        2.0,
    )

    print(
        f"{land_mm:>10.0f}"
        f"{row['lever_arm_mm']:>12.1f}"
        f"{row['ultimate_local_moment_kNm']:>14.3f}"
        f"{row['ultimate_vm_MPa']:>14.1f}"
        f"{row['MS_ultimate']:>12.3f}"
    )

print()
print("--- INTERPRETATION ---")
print(
    "The 84 -> 74 mm lower-barrel transition is screened using the "
    "smaller 74 mm OD section, which is conservative for nominal bending."
)
print(
    "No actual fillet Kt has been invented.  The Kt sensitivity shows how "
    "much geometric stress concentration the working section can tolerate."
)
print(
    "The ~61 kN radial reaction is NOT added to the Phase 2C upper-interface "
    "bending moment; doing so would double-count the same load path."
)
print(
    "Local shell ovalization, detailed bushing-contact load spreading, and "
    "the actual fillet/root stress field remain FEA/detail-design tasks."
)

print()
print("Consistency checks:               PASS")
print(
    f"CSV written to:                   "
    f"{output_csv.name}"
)
print("=" * 108)
