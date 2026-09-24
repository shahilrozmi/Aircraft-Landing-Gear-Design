"""
Landing_Gear_Design_Project
Phase 2D6 — Gland / Retainer Architecture + Preliminary Thread/Boss Sizing

Purpose
-------
Define a credible lower-end gland architecture and size its PRELIMINARY axial
retention envelope from the calculated Phase 2D5 loads.

Architecture
------------
The selected preliminary architecture is:

    outer barrel
        -> integral lower bearing shoulder
        -> C63000 / AMS 4640 lower guide bushing + seal carrier
        -> threaded gland nut / wiper retainer at the open end

Load-path rule:
    RADIAL bushing load is reacted primarily by the close-fitting bushing /
    shoulder / locally thickened barrel-end boss.

    AXIAL pressure-retention load is carried by the gland nut and its threaded
    engagement into the barrel-end boss.

The 61 kN-class radial bushing reaction is therefore NOT artificially added to
the thread axial load.

This script reads the Phase 2D5 CSV. No chat result is used as a calculation input.

Preliminary working thread geometry
-----------------------------------
A 60-degree metric-profile thread ENVELOPE is used for screening:

    nominal major diameter d = 70 mm
    pitch P                  = 2 mm

This is NOT a frozen production thread specification. It is a packaging/sizing
geometry used to determine whether a threaded gland is structurally plausible.

Approximate ISO-profile diameters:
    pitch diameter:
        d2 = d - 0.649519 P

    external-thread minor/root diameter:
        d3 = d - 1.226869 P

    internal-thread minor diameter:
        D1 = d - 1.082532 P

Thread stripping screen
-----------------------
For a preliminary 60-degree thread-envelope screen, effective cylindrical
thread shear areas are approximated as:

    A_strip,external ~= 0.5*pi*d3*Le
    A_strip,internal ~= 0.5*pi*d*Le

The 0.5 factor represents approximately half-pitch tooth occupancy in the
axial direction. This is NOT a final detailed thread-stripping calculation and
does not model first-thread load concentration.

Final thread design must use the selected thread standard's exact stripping /
fatigue method, tolerances, root radii, locking method, and certified material
allowables.

Local boss pressure screen
--------------------------
The locally thickened barrel-end boss is also screened as a thick cylinder at
the V0.5b virtual pressure using Lame equations.

The lower-bushing radial reaction remains a separate local-load requirement for
later detailed gland/boss FEA.
"""

import csv
import math
from pathlib import Path


# =============================================================================
# 1. PRELIMINARY MATERIAL BASIS — 300M STEEL
# =============================================================================

Sy_Pa = 1517e6
Su_Pa = 1862e6

tau_y_Pa = Sy_Pa / math.sqrt(3.0)
tau_u_Pa = Su_Pa / math.sqrt(3.0)


# =============================================================================
# 2. PRELIMINARY GLAND / THREAD GEOMETRY
# =============================================================================

thread_major_mm = 70.0
thread_pitch_mm = 2.0

# Approximate 60-degree ISO-profile diameters.
thread_pitch_diameter_mm = (
    thread_major_mm
    - 0.649519 * thread_pitch_mm
)

external_thread_minor_mm = (
    thread_major_mm
    - 1.226869 * thread_pitch_mm
)

internal_thread_minor_mm = (
    thread_major_mm
    - 1.082532 * thread_pitch_mm
)

# Gland passes over the 58 mm piston.
# 59 mm is a WORKING through-bore envelope, not a seal tolerance.
gland_bore_mm = 59.0

engagement_values_mm = [
    6.0,
    8.0,
    10.0,
    12.0,
    15.0,
    20.0,
]

boss_OD_values_mm = [
    80.0,
    82.0,
    84.0,
    86.0,
    88.0,
]

working_engagement_mm = 12.0
working_boss_OD_mm = 84.0


# =============================================================================
# 3. READ PHASE 2D5 LOAD REQUIREMENTS
# =============================================================================

here = Path(__file__).resolve().parent

candidate_paths = [
    here / "phase2_bushing_material_gland_requirements.csv",
    here.parent
    / "phase2_structures"
    / "phase2_bushing_material_gland_requirements.csv",
]

d5_csv = None

for path in candidate_paths:
    if path.exists():
        d5_csv = path
        break

if d5_csv is None:
    raise FileNotFoundError(
        "Could not find phase2_bushing_material_gland_requirements.csv. "
        "Run phase2_bushing_material_gland.py first."
    )


with d5_csv.open(
    "r",
    newline="",
    encoding="utf-8",
) as file:

    reader = csv.DictReader(file)
    rows = list(reader)

if len(rows) != 1:
    raise RuntimeError(
        "Expected one D5 summary row."
    )

src = rows[0]

radial_limit_kN = float(
    src["limit_lower_R_kN"]
)

radial_ultimate_kN = float(
    src["ultimate_lower_R_kN"]
)

housing_limit_pressure_MPa = float(
    src["housing_limit_pressure_MPa"]
)

housing_ultimate_pressure_MPa = float(
    src["housing_ultimate_pressure_MPa"]
)

physical_pressure_MPa = float(
    src["physical_pressure_MPa"]
)

virtual_pressure_MPa = float(
    src["virtual_pressure_MPa"]
)

physical_full_bore_thrust_kN = float(
    src["physical_full_bore_thrust_kN"]
)

virtual_full_bore_thrust_kN = float(
    src["virtual_full_bore_thrust_kN"]
)


# =============================================================================
# 4. THREAD / GLAND FUNCTIONS
# =============================================================================

def external_thread_strip_area_mm2(
    engagement_mm,
):
    return (
        0.5
        * math.pi
        * external_thread_minor_mm
        * engagement_mm
    )


def internal_thread_strip_area_mm2(
    engagement_mm,
):
    return (
        0.5
        * math.pi
        * thread_major_mm
        * engagement_mm
    )


def gland_neck_area_mm2():
    """
    Net axial area at the external-thread root outside the gland through-bore.
    """

    return (
        math.pi
        / 4.0
        * (
            external_thread_minor_mm**2
            - gland_bore_mm**2
        )
    )


def boss_annulus_area_mm2(
    boss_OD_mm,
):
    """
    Net metal annulus outside the internal-thread major/root envelope.
    """

    return (
        math.pi
        / 4.0
        * (
            boss_OD_mm**2
            - thread_major_mm**2
        )
    )


def lame_inner_surface_stresses_MPa(
    pressure_MPa,
    ID_mm,
    OD_mm,
):
    """
    Thick-cylinder inner-surface radial and hoop stresses.

    Internal pressure = pressure_MPa
    External pressure = 0
    """

    a = ID_mm / 2.0
    b = OD_mm / 2.0

    if b <= a:
        raise ValueError(
            "Boss OD must exceed thread-root ID."
        )

    A = (
        pressure_MPa
        * a**2
        / (
            b**2 - a**2
        )
    )

    B = (
        pressure_MPa
        * a**2
        * b**2
        / (
            b**2 - a**2
        )
    )

    sigma_r = (
        A
        - B / a**2
    )

    sigma_theta = (
        A
        + B / a**2
    )

    # Closed-end axial membrane stress.
    sigma_z = A

    return {
        "sigma_r_MPa": sigma_r,
        "sigma_theta_MPa": sigma_theta,
        "sigma_z_MPa": sigma_z,
    }


def von_mises_3d_MPa(
    sr,
    st,
    sz,
):
    return math.sqrt(
        0.5
        * (
            (st - sr)**2
            + (sr - sz)**2
            + (sz - st)**2
        )
    )


# =============================================================================
# 5. DESIGN SWEEP
# =============================================================================

gland_area_mm2 = gland_neck_area_mm2()

designs = []

for engagement_mm in engagement_values_mm:

    A_ext_mm2 = external_thread_strip_area_mm2(
        engagement_mm
    )

    A_int_mm2 = internal_thread_strip_area_mm2(
        engagement_mm
    )

    for boss_OD_mm in boss_OD_values_mm:

        boss_area_mm2 = boss_annulus_area_mm2(
            boss_OD_mm
        )

        boss_stress = lame_inner_surface_stresses_MPa(
            virtual_pressure_MPa,
            thread_major_mm,
            boss_OD_mm,
        )

        boss_vm_MPa = von_mises_3d_MPa(
            boss_stress["sigma_r_MPa"],
            boss_stress["sigma_theta_MPa"],
            boss_stress["sigma_z_MPa"],
        )

        # AXIAL pressure-retention loads only.
        F_phys_N = (
            physical_full_bore_thrust_kN
            * 1000.0
        )

        F_virtual_N = (
            virtual_full_bore_thrust_kN
            * 1000.0
        )

        tau_ext_phys_MPa = (
            F_phys_N
            / A_ext_mm2
        )

        tau_ext_virtual_MPa = (
            F_virtual_N
            / A_ext_mm2
        )

        tau_int_phys_MPa = (
            F_phys_N
            / A_int_mm2
        )

        tau_int_virtual_MPa = (
            F_virtual_N
            / A_int_mm2
        )

        gland_neck_phys_MPa = (
            F_phys_N
            / gland_area_mm2
        )

        gland_neck_virtual_MPa = (
            F_virtual_N
            / gland_area_mm2
        )

        boss_axial_phys_MPa = (
            F_phys_N
            / boss_area_mm2
        )

        boss_axial_virtual_MPa = (
            F_virtual_N
            / boss_area_mm2
        )

        # Simple preliminary material margins.
        ext_thread_virtual_MS_yield = (
            tau_y_Pa / 1e6
            / tau_ext_virtual_MPa
            - 1.0
        )

        int_thread_virtual_MS_yield = (
            tau_y_Pa / 1e6
            / tau_int_virtual_MPa
            - 1.0
        )

        gland_neck_virtual_MS_yield = (
            Sy_Pa / 1e6
            / gland_neck_virtual_MPa
            - 1.0
        )

        boss_pressure_virtual_MS_yield = (
            Sy_Pa / 1e6
            / boss_vm_MPa
            - 1.0
        )

        boss_root_wall_mm = (
            boss_OD_mm
            - thread_major_mm
        ) / 2.0

        gland_root_wall_mm = (
            external_thread_minor_mm
            - gland_bore_mm
        ) / 2.0

        engaged_threads = (
            engagement_mm
            / thread_pitch_mm
        )

        designs.append({
            "thread_major_mm": thread_major_mm,
            "thread_pitch_mm": thread_pitch_mm,
            "thread_pitch_diameter_mm":
                thread_pitch_diameter_mm,
            "external_thread_minor_mm":
                external_thread_minor_mm,
            "internal_thread_minor_mm":
                internal_thread_minor_mm,

            "engagement_mm": engagement_mm,
            "engaged_threads": engaged_threads,

            "boss_OD_mm": boss_OD_mm,
            "boss_root_wall_mm": boss_root_wall_mm,
            "gland_bore_mm": gland_bore_mm,
            "gland_root_wall_mm": gland_root_wall_mm,

            "external_strip_area_mm2": A_ext_mm2,
            "internal_strip_area_mm2": A_int_mm2,
            "gland_neck_area_mm2": gland_area_mm2,
            "boss_annulus_area_mm2": boss_area_mm2,

            "tau_ext_phys_MPa": tau_ext_phys_MPa,
            "tau_ext_virtual_MPa": tau_ext_virtual_MPa,
            "tau_int_phys_MPa": tau_int_phys_MPa,
            "tau_int_virtual_MPa": tau_int_virtual_MPa,

            "gland_neck_phys_MPa": gland_neck_phys_MPa,
            "gland_neck_virtual_MPa":
                gland_neck_virtual_MPa,

            "boss_axial_phys_MPa": boss_axial_phys_MPa,
            "boss_axial_virtual_MPa":
                boss_axial_virtual_MPa,

            "boss_hoop_virtual_MPa":
                boss_stress["sigma_theta_MPa"],
            "boss_vm_virtual_MPa": boss_vm_MPa,

            "ext_thread_virtual_MS_yield":
                ext_thread_virtual_MS_yield,
            "int_thread_virtual_MS_yield":
                int_thread_virtual_MS_yield,
            "gland_neck_virtual_MS_yield":
                gland_neck_virtual_MS_yield,
            "boss_pressure_virtual_MS_yield":
                boss_pressure_virtual_MS_yield,
        })


# =============================================================================
# 6. WORKING CANDIDATE
# =============================================================================

def get_design(
    engagement_mm,
    boss_OD_mm,
):
    for row in designs:
        if (
            abs(
                row["engagement_mm"]
                - engagement_mm
            ) < 1e-12
            and abs(
                row["boss_OD_mm"]
                - boss_OD_mm
            ) < 1e-12
        ):
            return row

    raise KeyError(
        "Working gland design not found."
    )


working = get_design(
    working_engagement_mm,
    working_boss_OD_mm,
)


# =============================================================================
# 7. CONSISTENCY CHECKS
# =============================================================================

assert radial_ultimate_kN > radial_limit_kN
assert virtual_full_bore_thrust_kN > physical_full_bore_thrust_kN
assert working["boss_root_wall_mm"] > 0.0
assert working["gland_root_wall_mm"] > 0.0


# =============================================================================
# 8. CSV OUTPUT
# =============================================================================

output_csv = (
    here
    / "phase2_gland_retainer_sizing.csv"
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
# 9. CONSOLE REPORT
# =============================================================================

print()
print("=" * 106)
print(
    " PHASE 2D6 — GLAND / RETAINER ARCHITECTURE "
    "+ PRELIMINARY THREAD/BOSS SIZING"
)
print("=" * 106)

print()
print("--- INPUT CONNECTION ---")
print(
    f"Phase 2D5 result file:            "
    f"{d5_csv}"
)

print()
print("--- SELECTED PRELIMINARY ARCHITECTURE ---")
print(
    "Integral barrel shoulder -> lower bronze guide/seal carrier "
    "-> threaded gland nut / wiper retainer."
)
print(
    "Radial bushing load is carried into the barrel shoulder/boss; "
    "threads are credited only with axial pressure retention."
)

print()
print("--- CALCULATED LOAD REQUIREMENTS FROM D5 ---")
print(
    f"Lower radial reaction, limit:     "
    f"{radial_limit_kN:.3f} kN"
)
print(
    f"Lower radial reaction, ultimate:  "
    f"{radial_ultimate_kN:.3f} kN"
)
print(
    f"Housing bearing pressure, limit:  "
    f"{housing_limit_pressure_MPa:.3f} MPa"
)
print(
    f"Housing bearing pressure, ult:    "
    f"{housing_ultimate_pressure_MPa:.3f} MPa"
)
print()
print(
    f"Physical full-bore thrust:        "
    f"{physical_full_bore_thrust_kN:.3f} kN"
)
print(
    f"V0.5b full-bore thrust:           "
    f"{virtual_full_bore_thrust_kN:.3f} kN"
)

print()
print("--- WORKING THREAD ENVELOPE ---")
print(
    f"Major diameter / pitch:           "
    f"{thread_major_mm:.1f} x "
    f"{thread_pitch_mm:.1f} mm"
)
print(
    f"Approx pitch diameter:            "
    f"{thread_pitch_diameter_mm:.3f} mm"
)
print(
    f"Approx external root diameter:    "
    f"{external_thread_minor_mm:.3f} mm"
)
print(
    f"Approx internal minor diameter:   "
    f"{internal_thread_minor_mm:.3f} mm"
)

print()
print(
    "--- WORKING CANDIDATE: "
    f"{working_engagement_mm:.0f} mm ENGAGEMENT / "
    f"{working_boss_OD_mm:.0f} mm BOSS OD ---"
)
print(
    f"Engaged thread pitches:           "
    f"{working['engaged_threads']:.1f}"
)
print(
    f"Local boss root wall:             "
    f"{working['boss_root_wall_mm']:.2f} mm"
)
print(
    f"Gland root wall over 59 mm bore:  "
    f"{working['gland_root_wall_mm']:.2f} mm"
)

print()
print("--- THREAD STRIPPING ENVELOPE ---")
print(
    f"External strip shear, physical:   "
    f"{working['tau_ext_phys_MPa']:.2f} MPa"
)
print(
    f"External strip shear, V0.5b:      "
    f"{working['tau_ext_virtual_MPa']:.2f} MPa"
)
print(
    f"External-thread margin vs yield:  "
    f"{working['ext_thread_virtual_MS_yield']:+.2f}"
)
print()
print(
    f"Internal strip shear, physical:   "
    f"{working['tau_int_phys_MPa']:.2f} MPa"
)
print(
    f"Internal strip shear, V0.5b:      "
    f"{working['tau_int_virtual_MPa']:.2f} MPa"
)
print(
    f"Internal-thread margin vs yield:  "
    f"{working['int_thread_virtual_MS_yield']:+.2f}"
)

print()
print("--- GLAND / BOSS NET-SECTION SCREEN ---")
print(
    f"Gland neck stress, physical:      "
    f"{working['gland_neck_phys_MPa']:.2f} MPa"
)
print(
    f"Gland neck stress, V0.5b:         "
    f"{working['gland_neck_virtual_MPa']:.2f} MPa"
)
print(
    f"Gland neck margin vs yield:       "
    f"{working['gland_neck_virtual_MS_yield']:+.2f}"
)
print()
print(
    f"Boss axial stress, V0.5b:         "
    f"{working['boss_axial_virtual_MPa']:.2f} MPa"
)
print(
    f"Boss inner hoop stress, V0.5b:    "
    f"{working['boss_hoop_virtual_MPa']:.2f} MPa"
)
print(
    f"Boss pressure VM stress, V0.5b:   "
    f"{working['boss_vm_virtual_MPa']:.2f} MPa"
)
print(
    f"Boss pressure margin vs yield:    "
    f"{working['boss_pressure_virtual_MS_yield']:+.2f}"
)

print()
print("--- INTERPRETATION ---")
print(
    "The threaded gland architecture is structurally plausible at the "
    "global/preliminary level."
)
print(
    "The thread is NOT currently strength-driven by pressure thrust; "
    "manufacturing, fatigue, locking, tolerance, and first-thread load "
    "concentration will control the final detail."
)
print(
    "The ~61 kN ultimate radial bushing load remains a separate local "
    "shoulder/boss load for detailed geometry/FEA."
)
print(
    "The 70 x 2 mm thread envelope and 84 mm boss OD remain WORKING "
    "dimensions only, not frozen production geometry."
)

print()
print("Consistency checks:               PASS")
print(
    f"CSV written to:                   "
    f"{output_csv.name}"
)
print("=" * 106)
