"""
Landing_Gear_Design_Project
Phase 2D4 — Piston / Barrel Packaging and Guide-Overlap Study

Purpose
-------
Take the Phase 2D3 bushing layouts and check whether the sliding piston remains
geometrically engaged with the two fixed guide bushings throughout the oleo stroke.

This script does NOT paste reaction loads from chat. It reads the CSV produced by
phase2_bushing_load_transfer.py and combines those calculated loads with the frozen
Phase 1 / Phase 2 stroke geometry.

Architecture used for this preliminary packaging study
------------------------------------------------------
- Both radial guide bushings are treated as fixed in the outer barrel.
- Bushing stations h_L and h_U from Phase 2D3 are defined relative to the axle in
  the STATIC condition (x_static = 50 mm).
- The piston/axle assembly translates upward into the barrel as oleo compression x
  increases.
- The piston bearing surface is idealized as a straight cylindrical guide surface
  extending upward from the axle/shoulder datum.

For any fixed barrel station:

    h(x) = h_static + x_static - x

where h is the distance from the axle upward to that station.

Therefore:
    full extension x = 0       -> h increases by 50 mm from static
    physical bottom x = 230 mm -> h decreases by 180 mm from static

The lower edge of the lower bushing must remain above the axle/shoulder datum:

    lower_surface_reserve
        = h_L(x) - L_b/2

A positive value means the whole lower bushing still lies on the idealized
cylindrical piston guide surface.

Required piston guide-surface length
------------------------------------
At full extension, the upper bushing is farthest from the axle. If the piston guide
surface is to extend a chosen overrun distance beyond the upper edge of the upper
bushing:

    L_piston,required
        = h_U(full extension) + L_b/2 + overrun

The overrun is a packaging design variable, not a regulatory requirement.
We report 0, 10, 20, and 30 mm cases instead of pretending one value is mandatory.

Important interpretation
------------------------
U is still an EQUIVALENT STRUCTURAL DATUM, not yet a physical barrel cap.
If the calculated piston top passes above U at high compression, the script reports
the required intrusion. This is not automatically a failure; it tells us how much
physical upper-barrel/cavity packaging would be required if U remains at its current
structural location.
"""

import csv
from pathlib import Path


# =============================================================================
# 1. FROZEN STROKE / GEOMETRY STATES
# =============================================================================

x_static_m = 0.050

x_full_extension_m = 0.000
x_nominal_peak_m = 0.206338
x_physical_m = 0.230000
x_virtual_m = 0.240779

L_UA_full_extension_m = 0.525

def L_UA_m(x_m):
    """Upper structural datum U to axle A."""
    return L_UA_full_extension_m - x_m


states = {
    "FULL_EXTENSION": x_full_extension_m,
    "STATIC": x_static_m,
    "NOMINAL_PEAK": x_nominal_peak_m,
    "PHYSICAL_STROKE": x_physical_m,
    "VIRTUAL_DIAGNOSTIC": x_virtual_m,
}

overrun_cases_mm = [
    0.0,
    10.0,
    20.0,
    30.0,
]

working_overrun_mm = 20.0


# =============================================================================
# 2. READ PHASE 2D3 LAYOUT / REACTION RESULTS
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


def read_layouts(path):
    rows = []

    with path.open(
        "r",
        newline="",
        encoding="utf-8",
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:
            rows.append({
                "hL_mm": float(row["hL_mm"]),
                "spacing_mm": float(row["spacing_mm"]),
                "hU_mm": float(row["hU_mm"]),
                "bushing_length_mm": float(row["bushing_length_mm"]),

                "ultimate_lower_case": row["ultimate_lower_case"],
                "ultimate_lower_R_kN": float(row["ultimate_lower_R_kN"]),
                "ultimate_upper_case": row["ultimate_upper_case"],
                "ultimate_upper_R_kN": float(row["ultimate_upper_R_kN"]),
                "max_ultimate_reaction_kN": float(row["max_ultimate_reaction_kN"]),
                "max_ultimate_pressure_MPa": float(row["max_ultimate_pressure_MPa"]),
            })

    return rows


d3_layouts = read_layouts(
    d3_csv
)


# =============================================================================
# 3. PACKAGING FUNCTIONS
# =============================================================================

def station_h_mm(
    h_static_mm,
    x_m,
):
    """
    Distance from axle upward to a BARREL-FIXED station at compression x.
    """

    return (
        h_static_mm
        + (x_static_m - x_m) * 1000.0
    )


def barrel_station_from_U_mm(
    h_static_mm,
):
    """
    Fixed barrel station measured downward from U.

    At static:
        U->A = 475 mm

    so:
        s_from_U = 475 - h_static
    """

    return (
        L_UA_m(x_static_m) * 1000.0
        - h_static_mm
    )


def required_piston_length_mm(
    hU_static_mm,
    bushing_length_mm,
    overrun_mm,
):
    hU_full_mm = station_h_mm(
        hU_static_mm,
        x_full_extension_m,
    )

    upper_bushing_upper_edge_mm = (
        hU_full_mm
        + 0.5 * bushing_length_mm
    )

    return (
        upper_bushing_upper_edge_mm
        + overrun_mm
    )


def top_intrusion_above_U_mm(
    piston_length_mm,
    x_m,
):
    """
    Positive result = piston top lies this far ABOVE U.
    Zero result = piston top is at or below U.
    """

    L_UA_mm = (
        L_UA_m(x_m) * 1000.0
    )

    return max(
        0.0,
        piston_length_mm - L_UA_mm,
    )


def evaluate_layout(
    row,
    overrun_mm,
):
    hL_static = row["hL_mm"]
    hU_static = row["hU_mm"]
    Lb = row["bushing_length_mm"]

    hL_by_state = {}
    hU_by_state = {}
    lower_reserve_by_state = {}

    for name, x_m in states.items():

        hL = station_h_mm(
            hL_static,
            x_m,
        )

        hU = station_h_mm(
            hU_static,
            x_m,
        )

        hL_by_state[name] = hL
        hU_by_state[name] = hU

        lower_reserve_by_state[name] = (
            hL
            - 0.5 * Lb
        )

    piston_length = required_piston_length_mm(
        hU_static,
        Lb,
        overrun_mm,
    )

    physical_intrusion = top_intrusion_above_U_mm(
        piston_length,
        x_physical_m,
    )

    nominal_intrusion = top_intrusion_above_U_mm(
        piston_length,
        x_nominal_peak_m,
    )

    virtual_intrusion = top_intrusion_above_U_mm(
        piston_length,
        x_virtual_m,
    )

    # Strict geometry-only engagement checks:
    # > 0 means the complete lower bushing remains above the axle/shoulder datum.
    physical_engaged = (
        lower_reserve_by_state["PHYSICAL_STROKE"] > 0.0
    )

    virtual_engaged = (
        lower_reserve_by_state["VIRTUAL_DIAGNOSTIC"] > 0.0
    )

    return {
        **row,

        "overrun_mm": overrun_mm,

        "lower_station_from_U_mm": barrel_station_from_U_mm(
            hL_static
        ),
        "upper_station_from_U_mm": barrel_station_from_U_mm(
            hU_static
        ),

        "full_extension_hL_mm": hL_by_state["FULL_EXTENSION"],
        "full_extension_hU_mm": hU_by_state["FULL_EXTENSION"],

        "nominal_hL_mm": hL_by_state["NOMINAL_PEAK"],
        "nominal_hU_mm": hU_by_state["NOMINAL_PEAK"],

        "physical_hL_mm": hL_by_state["PHYSICAL_STROKE"],
        "physical_hU_mm": hU_by_state["PHYSICAL_STROKE"],

        "virtual_hL_mm": hL_by_state["VIRTUAL_DIAGNOSTIC"],
        "virtual_hU_mm": hU_by_state["VIRTUAL_DIAGNOSTIC"],

        "physical_lower_surface_reserve_mm":
            lower_reserve_by_state["PHYSICAL_STROKE"],

        "virtual_lower_surface_reserve_mm":
            lower_reserve_by_state["VIRTUAL_DIAGNOSTIC"],

        "required_piston_guide_length_mm": piston_length,

        "nominal_top_intrusion_above_U_mm": nominal_intrusion,
        "physical_top_intrusion_above_U_mm": physical_intrusion,
        "virtual_top_intrusion_above_U_mm": virtual_intrusion,

        "physical_full_bushing_engagement": physical_engaged,
        "virtual_full_bushing_engagement": virtual_engaged,
    }


# =============================================================================
# 4. EVALUATE ALL D3 LAYOUTS AT ALL OVERRUNS
# =============================================================================

packaging_rows = []

for row in d3_layouts:

    for overrun_mm in overrun_cases_mm:

        packaging_rows.append(
            evaluate_layout(
                row,
                overrun_mm,
            )
        )


# =============================================================================
# 5. WORKING / COMPARISON LAYOUTS
# =============================================================================

def find_layout(
    hL_mm,
    spacing_mm,
    bushing_length_mm,
    overrun_mm,
):
    for row in packaging_rows:

        if (
            abs(row["hL_mm"] - hL_mm) < 1e-12
            and abs(row["spacing_mm"] - spacing_mm) < 1e-12
            and abs(row["bushing_length_mm"] - bushing_length_mm) < 1e-12
            and abs(row["overrun_mm"] - overrun_mm) < 1e-12
        ):
            return row

    raise KeyError(
        "Requested packaging layout not found."
    )


working = find_layout(
    hL_mm=300.0,
    spacing_mm=125.0,
    bushing_length_mm=30.0,
    overrun_mm=working_overrun_mm,
)

candidate_A = find_layout(
    hL_mm=250.0,
    spacing_mm=125.0,
    bushing_length_mm=30.0,
    overrun_mm=working_overrun_mm,
)

candidate_B = find_layout(
    hL_mm=250.0,
    spacing_mm=150.0,
    bushing_length_mm=30.0,
    overrun_mm=working_overrun_mm,
)


# =============================================================================
# 6. CSV OUTPUT
# =============================================================================

output_csv = (
    here
    / "phase2_packaging_overlap.csv"
)

with output_csv.open(
    "w",
    newline="",
    encoding="utf-8",
) as file:

    writer = csv.DictWriter(
        file,
        fieldnames=list(
            packaging_rows[0].keys()
        ),
    )

    writer.writeheader()
    writer.writerows(
        packaging_rows
    )


# =============================================================================
# 7. CONSOLE REPORT
# =============================================================================

print()
print("=" * 104)
print(
    " PHASE 2D4 — PISTON / BARREL PACKAGING "
    "+ GUIDE-OVERLAP STUDY"
)
print("=" * 104)

print()
print("--- INPUT CONNECTION ---")
print(
    f"Phase 2D3 result file:            "
    f"{d3_csv}"
)

print()
print("--- OLEO STATES ---")
for name, x_m in states.items():
    print(
        f"{name:<28}"
        f"x = {x_m*1000:>8.3f} mm    "
        f"U->A = {L_UA_m(x_m)*1000:>8.3f} mm"
    )

print()
print("--- PACKAGING MODEL ---")
print(
    "Both guide bushings are fixed in the outer barrel."
)
print(
    "Bushing h-values from D3 are interpreted at the 50 mm static-sag state."
)
print(
    "Positive lower-surface reserve means the complete lower bushing remains "
    "above the axle/shoulder datum."
)
print(
    f"Guide-surface overrun values:     "
    f"{', '.join(f'{x:.0f}' for x in overrun_cases_mm)} mm"
)

def print_layout_block(
    title,
    row,
):
    print()
    print(title)
    print(
        f"h_L / spacing / h_U static:       "
        f"{row['hL_mm']:.0f} / "
        f"{row['spacing_mm']:.0f} / "
        f"{row['hU_mm']:.0f} mm"
    )
    print(
        f"Bushing axial length:             "
        f"{row['bushing_length_mm']:.0f} mm"
    )
    print(
        f"Chosen top overrun:               "
        f"{row['overrun_mm']:.0f} mm"
    )
    print(
        f"Lower / upper station from U:     "
        f"{row['lower_station_from_U_mm']:.1f} / "
        f"{row['upper_station_from_U_mm']:.1f} mm downward"
    )
    print(
        f"Required piston guide length:     "
        f"{row['required_piston_guide_length_mm']:.1f} mm"
    )
    print(
        f"Physical lower-surface reserve:   "
        f"{row['physical_lower_surface_reserve_mm']:+.1f} mm"
    )
    print(
        f"Virtual lower-surface reserve:    "
        f"{row['virtual_lower_surface_reserve_mm']:+.1f} mm"
    )
    print(
        f"Physical top intrusion above U:   "
        f"{row['physical_top_intrusion_above_U_mm']:.1f} mm"
    )
    print(
        f"Virtual top intrusion above U:    "
        f"{row['virtual_top_intrusion_above_U_mm']:.1f} mm"
    )
    print(
        f"Max ultimate bushing reaction:    "
        f"{row['max_ultimate_reaction_kN']:.2f} kN"
    )
    print(
        f"Max ultimate projected pressure:  "
        f"{row['max_ultimate_pressure_MPa']:.2f} MPa"
    )
    print(
        f"Physical full engagement:         "
        f"{'PASS' if row['physical_full_bushing_engagement'] else 'FAIL'}"
    )
    print(
        f"Virtual diagnostic engagement:    "
        f"{'PASS' if row['virtual_full_bushing_engagement'] else 'FAIL'}"
    )

print_layout_block(
    "--- ORIGINAL WORKING LAYOUT ---",
    working,
)

print_layout_block(
    "--- COMPARISON A: 250 / 125 / 375 mm ---",
    candidate_A,
)

print_layout_block(
    "--- COMPARISON B: 250 / 150 / 400 mm ---",
    candidate_B,
)

print()
print("--- 30 mm BUSHINGS, 20 mm TOP OVERRUN ---")
print(
    f"{'hL':>6}"
    f"{'b':>6}"
    f"{'hU':>6}"
    f"{'Rult':>10}"
    f"{'pult':>10}"
    f"{'PhysRes':>10}"
    f"{'VirtRes':>10}"
    f"{'Lp req':>10}"
    f"{'PhysIntr':>10}"
    f"{'P/V':>8}"
)
print("-" * 92)

table_rows = [
    row
    for row in packaging_rows
    if (
        abs(row["bushing_length_mm"] - 30.0) < 1e-12
        and abs(row["overrun_mm"] - working_overrun_mm) < 1e-12
    )
]

for row in table_rows:
    status = (
        f"{'P' if row['physical_full_bushing_engagement'] else 'F'}/"
        f"{'P' if row['virtual_full_bushing_engagement'] else 'F'}"
    )

    print(
        f"{row['hL_mm']:>6.0f}"
        f"{row['spacing_mm']:>6.0f}"
        f"{row['hU_mm']:>6.0f}"
        f"{row['max_ultimate_reaction_kN']:>10.2f}"
        f"{row['max_ultimate_pressure_MPa']:>10.2f}"
        f"{row['physical_lower_surface_reserve_mm']:>10.1f}"
        f"{row['virtual_lower_surface_reserve_mm']:>10.1f}"
        f"{row['required_piston_guide_length_mm']:>10.1f}"
        f"{row['physical_top_intrusion_above_U_mm']:>10.1f}"
        f"{status:>8}"
    )

print()
print(
    "P/V = physical-stroke engagement / V0.5b virtual-diagnostic engagement."
)
print(
    "No arbitrary shoulder-clearance or cap-clearance allowable has been imposed."
)
print(
    "The reported reserves/intrusions are geometry outputs for the next CAD/package decision."
)
print()
print(
    f"CSV written to:                   "
    f"{output_csv.name}"
)
print("=" * 104)
