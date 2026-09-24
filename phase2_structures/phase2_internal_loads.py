"""
Landing_Gear_Design_Project
Phase 2B–2C — Structural Geometry + Internal Load Resultants

Purpose
-------
Backfill the already-frozen Phase 2B geometry and Phase 2C internal-load
calculations into reproducible Python.

This script consumes the Phase 1A CSV load envelope. It does NOT redefine
or retune Phase 1 loads.

Static right-main-gear geometry:
    +x forward
    +y right
    +z upward

    tire free radius             r0 = 0.222 m
    static loaded tire radius    rt = 0.175 m
    strut-to-wheel offset         e = 0.120 m
    full-extension U->A length   L0 = 0.525 m
    static oleo sag              xs = 0.050 m
    static U->A length           Ls = 0.475 m
    static U->contact height      H = 0.650 m

For the static LC0–LC5 model:
    r_UC = [0, e, -H]

For a strut section h above axle station A:
    r_SC = [0, e, -(rt+h)]

Internal section resultants:
    N_c = Fz
    Vx  = Fx
    Vy  = Fy
    Mx  = e*Fz + (rt+h)*Fy
    My  = -(rt+h)*Fx
    Tz  = -e*Fx
    Mb  = sqrt(Mx^2 + My^2)

At the upper interface:
    h = Ls
    rt + h = H

At axle root A:
    h = 0

Axle local y-axis model:
    N_y = Fy
    Vx  = Fx
    Vz  = Fz
    Mx  = e*Fz + rt*Fy
    Mz  = -e*Fx
    Ty_geom = -rt*Fx
    Mb = sqrt(Mx^2 + Mz^2)

IMPORTANT:
- For LC5, Ty_geom is a real brake torque path load.
- For LC2A/B, Ty_geom is the contact-patch wheel spin-up moment and is NOT
  automatically treated as shaft/gear structural torsion. It is retained as a
  separate wheel rotational load until the wheel rotational FBD is modeled.
"""

import csv
import math
from pathlib import Path


# =============================================================================
# 1. LOCKED PHASE 2B GEOMETRY
# =============================================================================

track_m = 3.20

r0_m = 0.222
rt_static_m = 0.175

wheel_offset_m = 0.120       # e

L_UA_full_extension_m = 0.525
static_oleo_sag_m = 0.050
L_UA_static_m = (
    L_UA_full_extension_m
    - static_oleo_sag_m
)

H_static_m = (
    L_UA_static_m
    + rt_static_m
)

physical_stroke_m = 0.230

# Right-main lateral coordinates
y_contact_m = track_m / 2.0
y_strut_m = (
    y_contact_m
    - wheel_offset_m
)


def dynamic_height_m(
    oleo_compression_m,
    tire_deflection_m,
):
    """
    Phase 2B dynamic geometry relation:

        H(t) = 0.747 - x(t) - delta_t(t)

    because:
        full-extension U->A length = 0.525 m
        free tire radius           = 0.222 m
    """

    return (
        L_UA_full_extension_m
        + r0_m
        - oleo_compression_m
        - tire_deflection_m
    )


# =============================================================================
# 2. FIND + READ PHASE 1A LOAD ENVELOPE
# =============================================================================

here = Path(__file__).resolve().parent

candidate_paths = [
    here / "phase1_load_envelope.csv",
    here.parent / "phase1_loads" / "phase1_load_envelope.csv",
    here.parent / "phase1" / "phase1_load_envelope.csv",
]

phase1_csv = None

for candidate in candidate_paths:
    if candidate.exists():
        phase1_csv = candidate
        break

if phase1_csv is None:
    searched = "\n".join(
        str(path)
        for path in candidate_paths
    )
    raise FileNotFoundError(
        "Could not find phase1_load_envelope.csv.\n"
        "Searched:\n"
        f"{searched}\n"
        "Run phase1_loads.py first."
    )


def read_phase1_cases(path):
    """
    Read both limit and ultimate forces from the Phase 1A CSV.
    Returned force units are kN.
    """

    cases = {}

    with path.open(
        "r",
        newline="",
        encoding="utf-8",
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:

            name = row["Load Case"]

            cases[name] = {
                "limit": {
                    "Fx_kN": float(
                        row["Fx Limit (kN)"]
                    ),
                    "Fy_kN": float(
                        row["Fy Limit (kN)"]
                    ),
                    "Fz_kN": float(
                        row["Fz Limit (kN)"]
                    ),
                },
                "ultimate": {
                    "Fx_kN": float(
                        row["Fx Ultimate (kN)"]
                    ),
                    "Fy_kN": float(
                        row["Fy Ultimate (kN)"]
                    ),
                    "Fz_kN": float(
                        row["Fz Ultimate (kN)"]
                    ),
                },
            }

    return cases


load_cases = read_phase1_cases(
    phase1_csv
)


# =============================================================================
# 3. INTERNAL-LOAD FUNCTIONS
# =============================================================================

def strut_resultants(
    Fx_kN,
    Fy_kN,
    Fz_kN,
    h_above_axle_m,
):
    """
    Internal resultants at a vertical strut section h above axle root A.

    Returns:
        N_c_kN   axial compression magnitude
        Vx_kN
        Vy_kN
        Mx_kNm
        My_kNm
        Tz_kNm
        Mb_kNm   resultant bending
    """

    vertical_arm_m = (
        rt_static_m
        + h_above_axle_m
    )

    N_c_kN = Fz_kN
    Vx_kN = Fx_kN
    Vy_kN = Fy_kN

    Mx_kNm = (
        wheel_offset_m * Fz_kN
        + vertical_arm_m * Fy_kN
    )

    My_kNm = (
        -vertical_arm_m * Fx_kN
    )

    Tz_kNm = (
        -wheel_offset_m * Fx_kN
    )

    Mb_kNm = math.hypot(
        Mx_kNm,
        My_kNm,
    )

    return {
        "N_c_kN": N_c_kN,
        "Vx_kN": Vx_kN,
        "Vy_kN": Vy_kN,
        "Mx_kNm": Mx_kNm,
        "My_kNm": My_kNm,
        "Tz_kNm": Tz_kNm,
        "Mb_kNm": Mb_kNm,
    }


def axle_resultants(
    Fx_kN,
    Fy_kN,
    Fz_kN,
):
    """
    Resultants at axle root in an axle-local coordinate system
    with axle axis approximately along +y.
    """

    Ny_kN = Fy_kN
    Vx_kN = Fx_kN
    Vz_kN = Fz_kN

    Mx_kNm = (
        wheel_offset_m * Fz_kN
        + rt_static_m * Fy_kN
    )

    Mz_kNm = (
        -wheel_offset_m * Fx_kN
    )

    Ty_geom_kNm = (
        -rt_static_m * Fx_kN
    )

    Mb_kNm = math.hypot(
        Mx_kNm,
        Mz_kNm,
    )

    return {
        "Ny_kN": Ny_kN,
        "Vx_kN": Vx_kN,
        "Vz_kN": Vz_kN,
        "Mx_kNm": Mx_kNm,
        "Mz_kNm": Mz_kNm,
        "Ty_geom_kNm": Ty_geom_kNm,
        "Mb_kNm": Mb_kNm,
    }


def torque_classification(
    case_name,
):
    """
    Distinguish true brake torque from wheel spin-up moment.
    """

    if case_name == "LC5":
        return "BRAKE TORQUE PATH"

    if case_name in (
        "LC2A",
        "LC2B",
    ):
        return (
            "WHEEL SPIN-UP MOMENT; "
            "NOT YET STRUCTURAL TORSION"
        )

    return "NO LONGITUDINAL CONTACT TORQUE"


# =============================================================================
# 4. CALCULATE ALL LIMIT + ULTIMATE RESULTANTS
# =============================================================================

results = []

for case_name, case_data in load_cases.items():

    for level in (
        "limit",
        "ultimate",
    ):

        force = case_data[level]

        Fx = force["Fx_kN"]
        Fy = force["Fy_kN"]
        Fz = force["Fz_kN"]

        upper = strut_resultants(
            Fx,
            Fy,
            Fz,
            h_above_axle_m=L_UA_static_m,
        )

        axle_root_strut = strut_resultants(
            Fx,
            Fy,
            Fz,
            h_above_axle_m=0.0,
        )

        axle = axle_resultants(
            Fx,
            Fy,
            Fz,
        )

        results.append({
            "case": case_name,
            "level": level,
            "Fx_kN": Fx,
            "Fy_kN": Fy,
            "Fz_kN": Fz,

            "U_Nc_kN": upper["N_c_kN"],
            "U_Vx_kN": upper["Vx_kN"],
            "U_Vy_kN": upper["Vy_kN"],
            "U_Mx_kNm": upper["Mx_kNm"],
            "U_My_kNm": upper["My_kNm"],
            "U_Tz_kNm": upper["Tz_kNm"],
            "U_Mb_kNm": upper["Mb_kNm"],

            "A_Nc_kN": axle_root_strut["N_c_kN"],
            "A_Vx_kN": axle_root_strut["Vx_kN"],
            "A_Vy_kN": axle_root_strut["Vy_kN"],
            "A_Mx_kNm": axle_root_strut["Mx_kNm"],
            "A_My_kNm": axle_root_strut["My_kNm"],
            "A_Tz_kNm": axle_root_strut["Tz_kNm"],
            "A_Mb_kNm": axle_root_strut["Mb_kNm"],

            "AX_Ny_kN": axle["Ny_kN"],
            "AX_Vx_kN": axle["Vx_kN"],
            "AX_Vz_kN": axle["Vz_kN"],
            "AX_Mx_kNm": axle["Mx_kNm"],
            "AX_Mz_kNm": axle["Mz_kNm"],
            "AX_Ty_geom_kNm": axle["Ty_geom_kNm"],
            "AX_Mb_kNm": axle["Mb_kNm"],

            "torque_note": torque_classification(
                case_name
            ),
        })


# =============================================================================
# 5. REGRESSION CHECKS AGAINST FROZEN PHASE 2C RESULTS
# =============================================================================

def get_result(
    case_name,
    level,
):
    for row in results:
        if (
            row["case"] == case_name
            and row["level"] == level
        ):
            return row

    raise KeyError(
        f"Missing {case_name} / {level}"
    )


def assert_close(
    label,
    calculated,
    reference,
    tolerance,
):
    error = abs(
        calculated
        - reference
    )

    assert error <= tolerance, (
        f"{label} regression failed: "
        f"calculated={calculated:.6f}, "
        f"reference={reference:.6f}, "
        f"error={error:.6f}"
    )


# NOTE:
# These regression references are based on the FULL-PRECISION Phase 1 CSV values,
# not the rounded values printed in the chat tables (e.g. 11.0922 kN rather than
# 11.09 kN). This prevents false regression failures caused only by display rounding.

# Upper-interface limit checks
assert_close(
    "LC4+ upper resultant bending limit",
    get_result(
        "LC4+",
        "limit",
    )["U_Mb_kNm"],
    6.752064,
    1.0e-6,
)

assert_close(
    "LC5 upper resultant bending limit",
    get_result(
        "LC5",
        "limit",
    )["U_Mb_kNm"],
    5.919536245284085,
    1.0e-6,
)

# Axle-root lower-strut limit check
assert_close(
    "LC2A axle-root strut bending limit",
    get_result(
        "LC2A",
        "limit",
    )["A_Mb_kNm"],
    3.1957173921711224,
    1.0e-6,
)

# Axle limit checks
assert_close(
    "LC2A axle bending limit",
    get_result(
        "LC2A",
        "limit",
    )["AX_Mb_kNm"],
    3.0948030825886157,
    1.0e-6,
)

assert_close(
    "LC5 brake torque limit",
    abs(
        get_result(
            "LC5",
            "limit",
        )["AX_Ty_geom_kNm"]
    ),
    1.552908,
    1.0e-6,
)

# Key ultimate values
assert_close(
    "Upper bending ultimate",
    get_result(
        "LC4+",
        "ultimate",
    )["U_Mb_kNm"],
    10.128096,
    1.0e-6,
)

assert_close(
    "Axle bending ultimate",
    get_result(
        "LC2A",
        "ultimate",
    )["AX_Mb_kNm"],
    4.6422046238829235,
    1.0e-6,
)

assert_close(
    "LC5 brake torque ultimate",
    abs(
        get_result(
            "LC5",
            "ultimate",
        )["AX_Ty_geom_kNm"]
    ),
    2.329362,
    1.0e-6,
)


# =============================================================================
# 6. GOVERNING-CASE SEARCH
# =============================================================================

def governing(
    level,
    key,
):
    subset = [
        row
        for row in results
        if row["level"] == level
    ]

    row = max(
        subset,
        key=lambda r: abs(r[key]),
    )

    return (
        row["case"],
        row[key],
    )


governing_summary = {
    "Upper axial compression": governing(
        "ultimate",
        "U_Nc_kN",
    ),
    "Upper longitudinal shear": governing(
        "ultimate",
        "U_Vx_kN",
    ),
    "Upper lateral shear": governing(
        "ultimate",
        "U_Vy_kN",
    ),
    "Upper resultant bending": governing(
        "ultimate",
        "U_Mb_kNm",
    ),
    "Upper torsion": governing(
        "ultimate",
        "U_Tz_kNm",
    ),
    "Axle vertical shear": governing(
        "ultimate",
        "AX_Vz_kN",
    ),
    "Axle axial load": governing(
        "ultimate",
        "AX_Ny_kN",
    ),
    "Axle resultant bending": governing(
        "ultimate",
        "AX_Mb_kNm",
    ),
}


# =============================================================================
# 7. CSV OUTPUT
# =============================================================================

output_csv = (
    here
    / "phase2_internal_loads.csv"
)

fieldnames = list(
    results[0].keys()
)

with output_csv.open(
    "w",
    newline="",
    encoding="utf-8",
) as file:

    writer = csv.DictWriter(
        file,
        fieldnames=fieldnames,
    )

    writer.writeheader()
    writer.writerows(results)


# =============================================================================
# 8. CONSOLE REPORT
# =============================================================================

print()
print("=" * 92)
print(
    " PHASE 2B–2C — STRUCTURAL GEOMETRY "
    "+ INTERNAL LOAD RESULTANTS"
)
print("=" * 92)

print()
print("--- INPUT CONNECTION ---")
print(
    f"Phase 1 load envelope:            "
    f"{phase1_csv}"
)

print()
print("--- LOCKED PHASE 2B GEOMETRY ---")
print(
    f"Track:                            "
    f"{track_m:.3f} m"
)
print(
    f"Right contact-patch y:            "
    f"{y_contact_m:.3f} m"
)
print(
    f"Right strut-axis y:               "
    f"{y_strut_m:.3f} m"
)
print(
    f"Wheel offset e:                   "
    f"{wheel_offset_m:.3f} m"
)
print(
    f"Free tire radius:                 "
    f"{r0_m:.3f} m"
)
print(
    f"Static loaded tire radius:        "
    f"{rt_static_m:.3f} m"
)
print(
    f"Full-extension U->A length:       "
    f"{L_UA_full_extension_m:.3f} m"
)
print(
    f"Static oleo sag:                  "
    f"{static_oleo_sag_m:.3f} m"
)
print(
    f"Static U->A length:               "
    f"{L_UA_static_m:.3f} m"
)
print(
    f"Static U->contact height H:       "
    f"{H_static_m:.3f} m"
)

print()
print("--- UPPER INTERFACE, LIMIT LOADS ---")
print(
    f"{'Case':<7}"
    f"{'Nc kN':>9}"
    f"{'Vx kN':>9}"
    f"{'Vy kN':>9}"
    f"{'Mx kNm':>10}"
    f"{'My kNm':>10}"
    f"{'Tz kNm':>10}"
    f"{'Mb kNm':>10}"
)
print("-" * 74)

for case_name in load_cases:

    row = get_result(
        case_name,
        "limit",
    )

    print(
        f"{case_name:<7}"
        f"{row['U_Nc_kN']:>9.2f}"
        f"{row['U_Vx_kN']:>9.2f}"
        f"{row['U_Vy_kN']:>9.2f}"
        f"{row['U_Mx_kNm']:>10.3f}"
        f"{row['U_My_kNm']:>10.3f}"
        f"{row['U_Tz_kNm']:>10.3f}"
        f"{row['U_Mb_kNm']:>10.3f}"
    )

print()
print("--- AXLE, LIMIT LOADS ---")
print(
    f"{'Case':<7}"
    f"{'Ny kN':>9}"
    f"{'Vx kN':>9}"
    f"{'Vz kN':>9}"
    f"{'Mx kNm':>10}"
    f"{'Mz kNm':>10}"
    f"{'Ty* kNm':>10}"
    f"{'Mb kNm':>10}"
)
print("-" * 74)

for case_name in load_cases:

    row = get_result(
        case_name,
        "limit",
    )

    print(
        f"{case_name:<7}"
        f"{row['AX_Ny_kN']:>9.2f}"
        f"{row['AX_Vx_kN']:>9.2f}"
        f"{row['AX_Vz_kN']:>9.2f}"
        f"{row['AX_Mx_kNm']:>10.3f}"
        f"{row['AX_Mz_kNm']:>10.3f}"
        f"{row['AX_Ty_geom_kNm']:>10.3f}"
        f"{row['AX_Mb_kNm']:>10.3f}"
    )

print()
print(
    "* LC5 Ty is confirmed brake-path torque. "
    "LC2 Ty is wheel spin-up moment only."
)

print()
print("--- GOVERNING ULTIMATE RESULTANTS ---")

for label, (
    case_name,
    value,
) in governing_summary.items():

    unit = (
        "kN·m"
        if (
            "bending" in label.lower()
            or "torsion" in label.lower()
        )
        else "kN"
    )

    print(
        f"{label:<31}"
        f"{case_name:<8}"
        f"{abs(value):>10.3f} {unit}"
    )

lc5_ult = get_result(
    "LC5",
    "ultimate",
)

print(
    f"{'Confirmed axle brake torque':<31}"
    f"{'LC5':<8}"
    f"{abs(lc5_ult['AX_Ty_geom_kNm']):>10.3f} kN·m"
)

print()
print("--- DYNAMIC-GEOMETRY SANITY CHECK ---")
H_static_check = dynamic_height_m(
    oleo_compression_m=0.050,
    tire_deflection_m=0.047,
)

print(
    f"H(x=50 mm, delta=47 mm):         "
    f"{H_static_check:.3f} m"
)

assert_close(
    "Dynamic/static geometry consistency",
    H_static_check,
    H_static_m,
    1.0e-12,
)

print()
print("Regression checks:                PASS")
print(
    f"CSV written to:                   "
    f"{output_csv.name}"
)
print("=" * 92)
