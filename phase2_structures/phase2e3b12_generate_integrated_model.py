"""
Landing_Gear_Design_Project
Phase 2E3-B12 — Integrated Upper-Head / Cross-Trunnion FEA Geometry Generator V0.1

Purpose
-------
Generate the B12 ANSYS geometry and the exact LC5-ultimate setup data for the
working Phase 2E3 upper attachment.

The geometry carries forward:
    PRIMARY_106 outer transition candidate
    64 mm pressurized bore
    106 mm solid upper-head OD
    38 mm 300M transverse cross-shaft
    150 mm bearing-center span
    25 mm bearing support widths
    20 mm lower + 20 mm upper solid-head ligaments

Coordinate system
-----------------
    +x : aircraft longitudinal / trunnion shaft axis
    +y : lateral
    +z : strut axis upward
    A  : axle-center structural datum, z = 0 in the full landing-gear model

B7B/B9 transition reconstruction
--------------------------------
The PRIMARY_106 outer transition is the cubic smoothstep profile

    D(A) = D0 + (D1-D0) * [3 t^2 - 2 t^3]

where

    t = (A - A_start)/(A_end - A_start)
    A_start = 275.000 mm
    A_end   = 973.780 mm
    D0      = 74.000 mm
    D1      = 106.000 mm

This reproduces the previously documented regression points:
    A=315 mm -> OD=74.3026 mm
    A=365 mm -> OD=75.4557 mm
    A=375 mm -> OD=75.7785 mm
    A=700 mm -> OD=95.1127 mm

The B9 local STEP ended at A=700 mm, so it showed OD ~=95.113 mm even though
PRIMARY_106 reaches 106 mm only at A=973.780 mm.

B12 model extent
----------------
Lower cut:
    A = 700.000 mm

Pressure-closure / solid-head boundary:
    A = 973.780 mm

Working trunnion center:
    U is A=475.000 mm
    z_trunnion above U = 537.780 mm
    therefore A_trunnion = 1012.780 mm

Upper head top:
    A = 1051.780 mm

The 64 mm bore terminates at the pressure closure. The head above the closure
is solid except for the 38 mm transverse trunnion bore.

Shaft segmentation
------------------
The 300M shaft is exported as three touching bodies so the two 25 mm support
journal bands are easy to scope in ANSYS:

    LEFT_JOURNAL  : x = -87.5 to -62.5 mm
    CENTER_SHAFT  : x = -62.5 to +62.5 mm
    RIGHT_JOURNAL : x = +62.5 to +87.5 mm

In Mechanical, connect the shaft segments with Shared Topology or Bonded
interfaces. The head-to-center-shaft interface is a STRUCTURAL-EQUIVALENT
bonded baseline for B12 V0.1. This preserves the rigidly integrated trunnion
assumption used by B10. The actual interference/fit definition remains open.

The outboard flange/nut retention hardware is intentionally omitted from this
local radial/bending model; B10A already showed direct axial retention strength
is not the driver. The left support acts as the locating support in x.

Outputs
-------
    phase2e3b12_integrated_head_trunnion.step
    phase2e3b12_transition_profile.csv
    phase2e3b12_geometry_parameters.csv
    phase2e3b12_lc5_ultimate_loads.csv
    phase2e3b12_generation_summary.txt
"""

from __future__ import annotations

import csv
import math
import re
from pathlib import Path

try:
    import cadquery as cq
except ImportError as exc:
    raise ImportError(
        "CadQuery is required only to regenerate the STEP file. "
        "Install cadquery in the Python environment used for the project."
    ) from exc


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent

B10_RECORD = HERE / "phase2e3b10_design_record.csv"
B10_SPAN = HERE / "phase2e3b10_span_trade.csv"

LOAD_CANDIDATES = [
    PROJECT_ROOT / "phase1_loads" / "phase1_load_envelope.csv",
    HERE / "phase1_load_envelope.csv",
]


# =============================================================================
# 1. B7B / B9 PROFILE DEFINITION
# =============================================================================

A_TAPER_START_MM = 275.000
A_CLOSURE_MM = 973.780

LOWER_OD_MM = 74.000
INNER_BORE_DIAMETER_MM = 64.000

# B12 starts at the exact B9 upper-cut station.
A_MODEL_BOTTOM_MM = 700.000

# U is 475 mm above axle datum A in the frozen Phase 2 geometry.
A_U_MM = 475.000


# =============================================================================
# 2. FALLBACK B10 VALUES
# =============================================================================

HEAD_OD_FALLBACK_MM = 106.000
SPAN_FALLBACK_MM = 150.000
SHAFT_D_FALLBACK_MM = 38.000
BEARING_WIDTH_FALLBACK_MM = 25.000
LOWER_LIGAMENT_FALLBACK_MM = 20.000
UPPER_LIGAMENT_FALLBACK_MM = 20.000
TRUNNION_Z_ABOVE_U_FALLBACK_MM = 537.780


# =============================================================================
# 3. PROJECT LOAD / PRESSURE VALUES
# =============================================================================

E_M = 0.120
RT_M = 0.175

# B9/E2-C ultimate differential pressure baseline.
ULTIMATE_PRESSURE_MPA = 13.938000


# =============================================================================
# 4. HELPERS
# =============================================================================

def read_csv_rows(path: Path):
    with path.open(
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as f:
        return list(csv.DictReader(f))


def read_b10_value(
    parameter: str,
    fallback: float,
) -> tuple[float, str]:
    if B10_RECORD.exists():
        for row in read_csv_rows(B10_RECORD):
            if row.get("parameter") == parameter:
                return (
                    float(row["value"]),
                    str(B10_RECORD),
                )

    return (
        fallback,
        "FALLBACK_FROM_B10_WORKING_GEOMETRY",
    )


def normalized_header_map(fieldnames):
    return {
        re.sub(
            r"[^a-z0-9]+",
            "",
            name.lower(),
        ): name
        for name in fieldnames
    }


def resolve_column(fieldnames, aliases):
    hmap = normalized_header_map(fieldnames)

    for alias in aliases:
        key = re.sub(
            r"[^a-z0-9]+",
            "",
            alias.lower(),
        )
        if key in hmap:
            return hmap[key]

    raise KeyError(
        f"Could not resolve any of {aliases} "
        f"from columns {fieldnames}"
    )


def resolve_bearing_width(
    working_span_mm: float,
) -> tuple[float, str]:
    if B10_SPAN.exists():
        rows = read_csv_rows(B10_SPAN)
        for row in rows:
            if (
                abs(
                    float(row["span_mm"])
                    - working_span_mm
                )
                < 1e-9
            ):
                return (
                    float(
                        row["bearing_width_mm"]
                    ),
                    str(B10_SPAN),
                )

    return (
        BEARING_WIDTH_FALLBACK_MM,
        "FALLBACK_FROM_B10_WORKING_GEOMETRY",
    )


def find_load_source() -> Path:
    for path in LOAD_CANDIDATES:
        if path.exists():
            return path

    raise FileNotFoundError(
        "Could not find phase1_load_envelope.csv."
    )


def read_lc5_ultimate(path: Path):
    with path.open(
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []

        case_col = resolve_column(
            fields,
            ["Load Case", "case", "load_case"],
        )

        fx_col = resolve_column(
            fields,
            [
                "Fx Ultimate (kN)",
                "Fx_ultimate_kN",
            ],
        )
        fy_col = resolve_column(
            fields,
            [
                "Fy Ultimate (kN)",
                "Fy_ultimate_kN",
            ],
        )
        fz_col = resolve_column(
            fields,
            [
                "Fz Ultimate (kN)",
                "Fz_ultimate_kN",
            ],
        )

        for row in reader:
            if row[case_col].strip().upper() == "LC5":
                return {
                    "Fx_kN":
                        float(row[fx_col]),
                    "Fy_kN":
                        float(row[fy_col]),
                    "Fz_kN":
                        float(row[fz_col]),
                }

    raise KeyError(
        "LC5 was not found in the load envelope."
    )


def smoothstep(t: float) -> float:
    return (
        3.0 * t**2
        - 2.0 * t**3
    )


def primary_outer_diameter_mm(
    A_mm: float,
    head_od_mm: float,
) -> float:
    if A_mm <= A_TAPER_START_MM:
        return LOWER_OD_MM

    if A_mm >= A_CLOSURE_MM:
        return head_od_mm

    t = (
        A_mm
        - A_TAPER_START_MM
    ) / (
        A_CLOSURE_MM
        - A_TAPER_START_MM
    )

    return (
        LOWER_OD_MM
        + (
            head_od_mm
            - LOWER_OD_MM
        )
        * smoothstep(t)
    )


def write_csv(path: Path, rows):
    if not rows:
        raise ValueError(
            f"No data supplied for {path.name}"
        )

    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=list(
                rows[0].keys()
            ),
        )
        writer.writeheader()
        writer.writerows(rows)


# =============================================================================
# 5. GEOMETRY BUILD
# =============================================================================

def build_head_barrel(
    head_od_mm: float,
    shaft_d_mm: float,
    A_trunnion_mm: float,
    A_head_top_mm: float,
):
    # Use enough stations for a smooth CAD loft/revolve while retaining the
    # analytical smoothstep definition in the exported profile CSV.
    n_profile = 60

    stations = []

    for i in range(
        n_profile + 1
    ):
        A_mm = (
            A_MODEL_BOTTOM_MM
            + (
                A_CLOSURE_MM
                - A_MODEL_BOTTOM_MM
            )
            * i
            / n_profile
        )

        OD_mm = (
            primary_outer_diameter_mm(
                A_mm,
                head_od_mm,
            )
        )

        stations.append(
            (
                A_mm,
                OD_mm,
            )
        )

    # Build the full outside as a body of revolution around global z.
    profile = (
        cq.Workplane("XZ")
        .moveTo(
            0.0,
            A_MODEL_BOTTOM_MM,
        )
        .lineTo(
            stations[0][1] / 2.0,
            A_MODEL_BOTTOM_MM,
        )
    )

    for A_mm, OD_mm in (
        stations[1:]
    ):
        profile = profile.lineTo(
            OD_mm / 2.0,
            A_mm,
        )

    profile = (
        profile
        .lineTo(
            head_od_mm / 2.0,
            A_head_top_mm,
        )
        .lineTo(
            0.0,
            A_head_top_mm,
        )
        .close()
    )

    outer = profile.revolve(
        360.0,
        (
            0.0,
            A_MODEL_BOTTOM_MM,
        ),
        (
            0.0,
            A_head_top_mm,
        ),
    )

    # Active 64 mm pressure cavity ends at the pressure closure.
    bore = (
        cq.Workplane("XY")
        .workplane(
            offset=A_MODEL_BOTTOM_MM
        )
        .circle(
            INNER_BORE_DIAMETER_MM
            / 2.0
        )
        .extrude(
            A_CLOSURE_MM
            - A_MODEL_BOTTOM_MM
        )
    )

    head = outer.cut(
        bore
    )

    # Transverse shaft bore, with extra cutting length so it fully clears the
    # 106 mm head.
    cross_bore_length_mm = (
        head_od_mm
        + 20.0
    )

    cross_bore = (
        cq.Solid.makeCylinder(
            shaft_d_mm / 2.0,
            cross_bore_length_mm,
            cq.Vector(
                -cross_bore_length_mm
                / 2.0,
                0.0,
                A_trunnion_mm,
            ),
            cq.Vector(
                1.0,
                0.0,
                0.0,
            ),
        )
    )

    head = head.cut(
        cq.Workplane(
            obj=cross_bore
        )
    )

    return (
        head,
        stations,
    )


def build_shaft_segments(
    shaft_d_mm: float,
    span_mm: float,
    bearing_width_mm: float,
    A_trunnion_mm: float,
):
    half_span = (
        span_mm / 2.0
    )

    half_bearing = (
        bearing_width_mm / 2.0
    )

    left_outer_x = (
        -half_span
        - half_bearing
    )
    left_inner_x = (
        -half_span
        + half_bearing
    )

    right_inner_x = (
        half_span
        - half_bearing
    )
    right_outer_x = (
        half_span
        + half_bearing
    )

    radius = shaft_d_mm / 2.0

    left_length = (
        left_inner_x
        - left_outer_x
    )

    center_length = (
        right_inner_x
        - left_inner_x
    )

    right_length = (
        right_outer_x
        - right_inner_x
    )

    left = cq.Solid.makeCylinder(
        radius,
        left_length,
        cq.Vector(
            left_outer_x,
            0.0,
            A_trunnion_mm,
        ),
        cq.Vector(
            1.0,
            0.0,
            0.0,
        ),
    )

    center = cq.Solid.makeCylinder(
        radius,
        center_length,
        cq.Vector(
            left_inner_x,
            0.0,
            A_trunnion_mm,
        ),
        cq.Vector(
            1.0,
            0.0,
            0.0,
        ),
    )

    right = cq.Solid.makeCylinder(
        radius,
        right_length,
        cq.Vector(
            right_inner_x,
            0.0,
            A_trunnion_mm,
        ),
        cq.Vector(
            1.0,
            0.0,
            0.0,
        ),
    )

    geometry = {
        "left_outer_x_mm":
            left_outer_x,
        "left_inner_x_mm":
            left_inner_x,
        "right_inner_x_mm":
            right_inner_x,
        "right_outer_x_mm":
            right_outer_x,
    }

    return (
        left,
        center,
        right,
        geometry,
    )


# =============================================================================
# 6. MAIN
# =============================================================================

def main():
    # -------------------------------------------------------------------------
    # Source-connect B10 geometry.
    # -------------------------------------------------------------------------
    head_od_mm, head_src = (
        read_b10_value(
            "B9_upper_head_OD",
            HEAD_OD_FALLBACK_MM,
        )
    )

    span_mm, span_src = (
        read_b10_value(
            "working_bearing_center_span",
            SPAN_FALLBACK_MM,
        )
    )

    shaft_d_mm, shaft_src = (
        read_b10_value(
            "working_300M_cross_shaft_diameter",
            SHAFT_D_FALLBACK_MM,
        )
    )

    lower_ligament_mm, lower_src = (
        read_b10_value(
            "working_lower_solid_head_ligament",
            LOWER_LIGAMENT_FALLBACK_MM,
        )
    )

    upper_ligament_mm, upper_src = (
        read_b10_value(
            "working_upper_solid_head_ligament",
            UPPER_LIGAMENT_FALLBACK_MM,
        )
    )

    z_trunnion_above_U_mm, z_src = (
        read_b10_value(
            "working_trunnion_center_above_U",
            TRUNNION_Z_ABOVE_U_FALLBACK_MM,
        )
    )

    bearing_width_mm, bearing_src = (
        resolve_bearing_width(
            span_mm
        )
    )

    # PRIMARY_106 geometry source gate.
    if abs(
        head_od_mm
        - 106.0
    ) > 1e-6:
        raise ValueError(
            "B12 V0.1 is the PRIMARY_106 geometry continuation. "
            f"B10 currently reports head OD={head_od_mm:.6f} mm. "
            "Do not silently regenerate the B7B profile with another OD."
        )

    A_trunnion_mm = (
        A_U_MM
        + z_trunnion_above_U_mm
    )

    A_head_top_mm = (
        A_trunnion_mm
        + shaft_d_mm / 2.0
        + upper_ligament_mm
    )

    lower_ligament_from_geometry_mm = (
        A_trunnion_mm
        - shaft_d_mm / 2.0
        - A_CLOSURE_MM
    )

    if abs(
        lower_ligament_from_geometry_mm
        - lower_ligament_mm
    ) > 1e-6:
        raise ValueError(
            "B10 trunnion station / lower ligament are inconsistent:\n"
            f"recorded lower ligament={lower_ligament_mm:.6f} mm\n"
            f"derived lower ligament={lower_ligament_from_geometry_mm:.6f} mm"
        )

    # -------------------------------------------------------------------------
    # Regression checks for exact B7B/B9 smoothstep continuation.
    # -------------------------------------------------------------------------
    regression = {
        315.0: 74.3025605684,
        365.0: 75.4557478680,
        375.0: 75.7784627976,
        700.0: 95.1126609150,
        973.780: 106.0000000000,
    }

    for A_mm, expected_od in (
        regression.items()
    ):
        actual_od = (
            primary_outer_diameter_mm(
                A_mm,
                head_od_mm,
            )
        )

        if abs(
            actual_od
            - expected_od
        ) > 1e-6:
            raise AssertionError(
                "PRIMARY_106 regression failed at "
                f"A={A_mm:.3f} mm: "
                f"{actual_od:.9f} vs "
                f"{expected_od:.9f} mm"
            )

    # -------------------------------------------------------------------------
    # Build geometry.
    # -------------------------------------------------------------------------
    (
        head,
        profile_stations,
    ) = build_head_barrel(
        head_od_mm=head_od_mm,
        shaft_d_mm=shaft_d_mm,
        A_trunnion_mm=A_trunnion_mm,
        A_head_top_mm=A_head_top_mm,
    )

    (
        shaft_left,
        shaft_center,
        shaft_right,
        shaft_geometry,
    ) = build_shaft_segments(
        shaft_d_mm=shaft_d_mm,
        span_mm=span_mm,
        bearing_width_mm=
            bearing_width_mm,
        A_trunnion_mm=
            A_trunnion_mm,
    )

    assembly = cq.Assembly(
        name="B12_UPPER_HEAD_TRUNNION"
    )

    assembly.add(
        head,
        name="HEAD_BARREL_7075",
    )

    assembly.add(
        shaft_left,
        name="SHAFT_JOURNAL_LEFT_300M",
    )

    assembly.add(
        shaft_center,
        name="SHAFT_CENTER_300M",
    )

    assembly.add(
        shaft_right,
        name="SHAFT_JOURNAL_RIGHT_300M",
    )

    step_path = (
        HERE
        / "phase2e3b12_integrated_head_trunnion.step"
    )

    assembly.save(
        str(step_path)
    )

    # -------------------------------------------------------------------------
    # Profile output.
    # -------------------------------------------------------------------------
    profile_rows = []

    n_export = 140

    for i in range(
        n_export + 1
    ):
        A_mm = (
            A_MODEL_BOTTOM_MM
            + (
                A_CLOSURE_MM
                - A_MODEL_BOTTOM_MM
            )
            * i
            / n_export
        )

        profile_rows.append({
            "A_mm":
                A_mm,
            "OD_mm":
                primary_outer_diameter_mm(
                    A_mm,
                    head_od_mm,
                ),
            "ID_mm":
                INNER_BORE_DIAMETER_MM,
            "region":
                "PRIMARY_106_SMOOTHSTEP_TRANSITION",
        })

    profile_rows.append({
        "A_mm":
            A_head_top_mm,
        "OD_mm":
            head_od_mm,
        "ID_mm":
            0.0,
        "region":
            "SOLID_UPPER_HEAD_TOP",
    })

    profile_csv = (
        HERE
        / "phase2e3b12_transition_profile.csv"
    )

    write_csv(
        profile_csv,
        profile_rows,
    )

    # -------------------------------------------------------------------------
    # Load reconstruction.
    # -------------------------------------------------------------------------
    load_source = find_load_source()
    lc5 = read_lc5_ultimate(
        load_source
    )

    # At any structural section A:
    #   arm = r_t + A
    #   Mx  = e*Fz + arm*Fy
    #   My  = -arm*Fx
    #   Mz  = -e*Fx
    A_load_m = (
        A_MODEL_BOTTOM_MM
        / 1000.0
    )

    arm_load_m = (
        RT_M
        + A_load_m
    )

    Mx_kNm = (
        E_M
        * lc5["Fz_kN"]
        + arm_load_m
        * lc5["Fy_kN"]
    )

    My_kNm = (
        -arm_load_m
        * lc5["Fx_kN"]
    )

    Mz_kNm = (
        -E_M
        * lc5["Fx_kN"]
    )

    closure_area_mm2 = (
        math.pi
        / 4.0
        * INNER_BORE_DIAMETER_MM**2
    )

    pressure_thrust_N = (
        ULTIMATE_PRESSURE_MPA
        * closure_area_mm2
    )

    load_rows = [
        {
            "load_case":
                "LC5_ULTIMATE",
            "application":
                "LOWER_CUT_REMOTE_FORCE_STRUCTURAL_ONLY",
            "Fx_N":
                lc5["Fx_kN"] * 1000.0,
            "Fy_N":
                lc5["Fy_kN"] * 1000.0,
            "Fz_N":
                lc5["Fz_kN"] * 1000.0,
            "Mx_Nmm":
                Mx_kNm * 1e6,
            "My_Nmm":
                My_kNm * 1e6,
            "Mz_Nmm":
                Mz_kNm * 1e6,
            "pressure_MPa":
                0.0,
            "note":
                (
                    "Apply structural force/moment on A=700 mm lower annular "
                    "cut face using deformable remote coupling."
                ),
        },
        {
            "load_case":
                "LC5_ULTIMATE",
            "application":
                "INTERNAL_PRESSURE",
            "Fx_N":
                0.0,
            "Fy_N":
                0.0,
            "Fz_N":
                0.0,
            "Mx_Nmm":
                0.0,
            "My_Nmm":
                0.0,
            "Mz_Nmm":
                0.0,
            "pressure_MPa":
                ULTIMATE_PRESSURE_MPA,
            "note":
                (
                    "Apply to 64 mm cylindrical bore AND the pressure-closure "
                    "face at A=973.780 mm. Do not add pressure thrust again "
                    "to the remote structural force because the closure is "
                    "explicit in B12."
                ),
        },
    ]

    loads_csv = (
        HERE
        / "phase2e3b12_lc5_ultimate_loads.csv"
    )

    write_csv(
        loads_csv,
        load_rows,
    )

    # -------------------------------------------------------------------------
    # Geometry record.
    # -------------------------------------------------------------------------
    geometry_rows = [
        {
            "parameter":
                "model_bottom_A",
            "value":
                A_MODEL_BOTTOM_MM,
            "units":
                "mm",
            "classification":
                "B12_MODEL_BOUNDARY",
        },
        {
            "parameter":
                "outer_OD_at_model_bottom",
            "value":
                primary_outer_diameter_mm(
                    A_MODEL_BOTTOM_MM,
                    head_od_mm,
                ),
            "units":
                "mm",
            "classification":
                "DERIVED_PRIMARY_106",
        },
        {
            "parameter":
                "pressure_closure_A",
            "value":
                A_CLOSURE_MM,
            "units":
                "mm",
            "classification":
                "SOURCE_B7B_E3",
        },
        {
            "parameter":
                "head_OD",
            "value":
                head_od_mm,
            "units":
                "mm",
            "classification":
                "SOURCE_B10_PRIMARY_106",
        },
        {
            "parameter":
                "inner_bore_ID",
            "value":
                INNER_BORE_DIAMETER_MM,
            "units":
                "mm",
            "classification":
                "FROZEN_E2",
        },
        {
            "parameter":
                "trunnion_center_A",
            "value":
                A_trunnion_mm,
            "units":
                "mm",
            "classification":
                "DERIVED_B10",
        },
        {
            "parameter":
                "head_top_A",
            "value":
                A_head_top_mm,
            "units":
                "mm",
            "classification":
                "DERIVED_B10",
        },
        {
            "parameter":
                "head_axial_height_above_closure",
            "value":
                A_head_top_mm
                - A_CLOSURE_MM,
            "units":
                "mm",
            "classification":
                "DERIVED_B10",
        },
        {
            "parameter":
                "shaft_diameter",
            "value":
                shaft_d_mm,
            "units":
                "mm",
            "classification":
                "SOURCE_B10",
        },
        {
            "parameter":
                "bearing_center_span",
            "value":
                span_mm,
            "units":
                "mm",
            "classification":
                "SOURCE_B10",
        },
        {
            "parameter":
                "bearing_width",
            "value":
                bearing_width_mm,
            "units":
                "mm",
            "classification":
                "SOURCE_B10",
        },
        {
            "parameter":
                "left_journal_outer_x",
            "value":
                shaft_geometry[
                    "left_outer_x_mm"
                ],
            "units":
                "mm",
            "classification":
                "DERIVED_B12",
        },
        {
            "parameter":
                "left_journal_inner_x",
            "value":
                shaft_geometry[
                    "left_inner_x_mm"
                ],
            "units":
                "mm",
            "classification":
                "DERIVED_B12",
        },
        {
            "parameter":
                "right_journal_inner_x",
            "value":
                shaft_geometry[
                    "right_inner_x_mm"
                ],
            "units":
                "mm",
            "classification":
                "DERIVED_B12",
        },
        {
            "parameter":
                "right_journal_outer_x",
            "value":
                shaft_geometry[
                    "right_outer_x_mm"
                ],
            "units":
                "mm",
            "classification":
                "DERIVED_B12",
        },
        {
            "parameter":
                "ultimate_pressure",
            "value":
                ULTIMATE_PRESSURE_MPA,
            "units":
                "MPa",
            "classification":
                "SOURCE_B9_E2C",
        },
        {
            "parameter":
                "pressure_closure_thrust",
            "value":
                pressure_thrust_N
                / 1000.0,
            "units":
                "kN",
            "classification":
                "DERIVED_FOR_LOAD_AUDIT",
        },
    ]

    geometry_csv = (
        HERE
        / "phase2e3b12_geometry_parameters.csv"
    )

    write_csv(
        geometry_csv,
        geometry_rows,
    )

    # -------------------------------------------------------------------------
    # Console and summary.
    # -------------------------------------------------------------------------
    line = "=" * 124
    dash = "-" * 124

    messages = []

    def emit(s=""):
        print(s)
        messages.append(s)

    emit()
    emit(line)
    emit(
        " PHASE 2E3-B12 — INTEGRATED UPPER-HEAD / "
        "CROSS-TRUNNION FEA GEOMETRY V0.1"
    )
    emit(line)

    emit()
    emit("SOURCE CONNECTION")
    emit(dash)
    emit(
        f"Head source:                      "
        f"{head_src}"
    )
    emit(
        f"Span source:                      "
        f"{span_src}"
    )
    emit(
        f"Shaft source:                     "
        f"{shaft_src}"
    )
    emit(
        f"Lower ligament source:            "
        f"{lower_src}"
    )
    emit(
        f"Upper ligament source:            "
        f"{upper_src}"
    )
    emit(
        f"Trunnion station source:          "
        f"{z_src}"
    )
    emit(
        f"Bearing-width source:             "
        f"{bearing_src}"
    )
    emit(
        f"LC5 load source:                  "
        f"{load_source}"
    )

    emit()
    emit("PRIMARY_106 PROFILE REGRESSION")
    emit(dash)

    for A_mm, expected_od in (
        regression.items()
    ):
        actual_od = (
            primary_outer_diameter_mm(
                A_mm,
                head_od_mm,
            )
        )
        emit(
            f"A={A_mm:>8.3f} mm   "
            f"OD={actual_od:>10.6f} mm   "
            f"target={expected_od:>10.6f}   PASS"
        )

    # Maximum cubic-smoothstep slope occurs at t=0.5.
    diameter_slope_max = (
        (
            head_od_mm
            - LOWER_OD_MM
        )
        * 1.5
        / (
            A_CLOSURE_MM
            - A_TAPER_START_MM
        )
    )

    radius_slope_max = (
        diameter_slope_max
        / 2.0
    )

    max_half_angle_deg = (
        math.degrees(
            math.atan(
                radius_slope_max
            )
        )
    )

    emit(
        f"Maximum smoothstep half-angle:    "
        f"{max_half_angle_deg:.3f} deg"
    )

    emit()
    emit("B12 GEOMETRY")
    emit(dash)
    emit(
        f"Lower model cut A:                "
        f"{A_MODEL_BOTTOM_MM:.3f} mm"
    )
    emit(
        f"OD at lower cut:                  "
        f"{primary_outer_diameter_mm(A_MODEL_BOTTOM_MM, head_od_mm):.3f} mm"
    )
    emit(
        f"Pressure closure A:               "
        f"{A_CLOSURE_MM:.3f} mm"
    )
    emit(
        f"Solid-head OD:                    "
        f"{head_od_mm:.3f} mm"
    )
    emit(
        f"Pressure bore ID:                 "
        f"{INNER_BORE_DIAMETER_MM:.3f} mm"
    )
    emit(
        f"Trunnion center A:                "
        f"{A_trunnion_mm:.3f} mm"
    )
    emit(
        f"Head top A:                       "
        f"{A_head_top_mm:.3f} mm"
    )
    emit(
        f"Lower / upper ligament:           "
        f"{lower_ligament_mm:.3f} / "
        f"{upper_ligament_mm:.3f} mm"
    )
    emit(
        f"Cross-shaft diameter:             "
        f"{shaft_d_mm:.3f} mm"
    )
    emit(
        f"Bearing-center span:              "
        f"{span_mm:.3f} mm"
    )
    emit(
        f"Bearing width:                    "
        f"{bearing_width_mm:.3f} mm"
    )
    emit(
        f"Left support band:                "
        f"x={shaft_geometry['left_outer_x_mm']:.3f} to "
        f"{shaft_geometry['left_inner_x_mm']:.3f} mm"
    )
    emit(
        f"Right support band:               "
        f"x={shaft_geometry['right_inner_x_mm']:.3f} to "
        f"{shaft_geometry['right_outer_x_mm']:.3f} mm"
    )

    emit()
    emit("LC5 ULTIMATE STRUCTURAL LOAD AT B12 LOWER CUT A=700 mm")
    emit(dash)
    emit(
        f"Fx / Fy / Fz:                     "
        f"{lc5['Fx_kN']:.5f} / "
        f"{lc5['Fy_kN']:.5f} / "
        f"{lc5['Fz_kN']:.5f} kN"
    )
    emit(
        f"Mx / My / Mz:                     "
        f"{Mx_kNm:.6f} / "
        f"{My_kNm:.6f} / "
        f"{Mz_kNm:.6f} kN*m"
    )
    emit(
        f"Ultimate internal pressure:       "
        f"{ULTIMATE_PRESSURE_MPA:.6f} MPa"
    )
    emit(
        f"64 mm closure pressure thrust:    "
        f"{pressure_thrust_N/1000.0:.6f} kN"
    )
    emit(
        "Pressure rule: apply pressure to the cylindrical bore AND explicit "
        "closure face; do NOT add the closure thrust again to Fz."
    )

    emit()
    emit("B12 V0.1 INTERFACE MODEL")
    emit(dash)
    emit(
        "Shaft segment interfaces:         Shared Topology or Bonded"
    )
    emit(
        "Head <-> center shaft:            BONDED structural-equivalent baseline"
    )
    emit(
        "Reason: preserve B10 rigidly-integrated trunnion load-path assumption."
    )
    emit(
        "Actual interference/fit/contact:  OPEN — sensitivity after baseline convergence"
    )
    emit(
        "Left support:                     locating cylindrical support"
    )
    emit(
        "Right support:                    floating cylindrical support"
    )

    emit()
    emit("OUTPUT FILES")
    emit(dash)
    emit(
        f"STEP assembly:                    "
        f"{step_path}"
    )
    emit(
        f"Transition profile:               "
        f"{profile_csv}"
    )
    emit(
        f"Geometry parameters:              "
        f"{geometry_csv}"
    )
    emit(
        f"LC5 ultimate load record:         "
        f"{loads_csv}"
    )

    summary_path = (
        HERE
        / "phase2e3b12_generation_summary.txt"
    )

    summary_path.write_text(
        "\n".join(messages)
        + "\n",
        encoding="utf-8",
    )

    print(
        f"Summary:                          "
        f"{summary_path}"
    )
    print(line)


if __name__ == "__main__":
    main()
