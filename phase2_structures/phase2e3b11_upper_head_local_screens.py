"""
Landing_Gear_Design_Project
Phase 2E3-B11 — Upper-Head Local Analytical Screens V0.1

Purpose
-------
Perform the first local analytical checks on the B10/B10A upper-head /
cross-trunnion architecture before integrated contact FEA.

This script source-connects to:
    - phase2e3b10_design_record.csv
    - phase2e3b10_span_trade.csv
    - phase1_load_envelope.csv

It reconstructs the actual trunnion reactions at the B10 trunnion station and
screens the 7075-T6 upper head for:

    A. pin/bore projected bearing stress
    B. local net-section stress around the transverse bore
    C. edge/shear-out stress toward the nearest free ligament
    D. lateral side-ligament sensitivity
    E. axial thrust-face / washer average contact pressure
    F. geometric ratios for the B12 FEA model

Important modeling convention
-----------------------------
The 106 mm head is treated conservatively as two local "half-head lugs", one on
each side of the strut centerplane.

For each side:
    effective lug thickness along trunnion axis x = D_head / 2

The actual head is a 3-D curved body, so these are only nominal local screens.
They are NOT substitutes for the B12 contact/solid FEA.

Load-path convention retained from D9/B10
-----------------------------------------
    Fy, Fz, My, Mz -> trunnion/airframe support system
    Fx             -> axial thrust face / retention system
    Mx             -> independent upper brace / lock-link path

No credit is given to the trunnion retention hardware for Mx.

Material convention
-------------------
The current project B9/B9A 7075-T6 screening values are:
    yield    = 503 MPa
    ultimate = 572 MPa

These are project preliminary static screens only. A true bearing allowable,
fatigue allowable, corrosion/environment knockdown, and certification basis are
NOT established here.

The projected bearing-pressure comparison against yield/ultimate is therefore
only a nominal sanity screen; it is not a certified bearing allowable.
"""

from __future__ import annotations

import csv
import math
import re
from pathlib import Path


# =============================================================================
# 0. PATHS
# =============================================================================

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent

B10_RECORD = HERE / "phase2e3b10_design_record.csv"
B10_SPAN = HERE / "phase2e3b10_span_trade.csv"

LOAD_CANDIDATES = [
    PROJECT_ROOT / "phase1_loads" / "phase1_load_envelope.csv",
    HERE / "phase1_load_envelope.csv",
]


# =============================================================================
# 1. FALLBACK WORKING VALUES
# =============================================================================
# Source-read values take precedence. Fallbacks are only the B10 working values
# and are reported if used.

FALLBACK_HEAD_OD_MM = 106.0
FALLBACK_SPAN_MM = 150.0
FALLBACK_SHAFT_D_MM = 38.0
FALLBACK_BEARING_WIDTH_MM = 25.0
FALLBACK_LOWER_LIGAMENT_MM = 20.0
FALLBACK_UPPER_LIGAMENT_MM = 20.0
FALLBACK_TRUNNION_Z_ABOVE_U_MM = 537.780

# Phase 2D9 geometry.
E_M = 0.120
RT_M = 0.175
H_UA_STATIC_M = 0.475
BASE_UPPER_ARM_M = RT_M + H_UA_STATIC_M

# Current B9 project material screens.
SY_7075_MPA = 503.0
SU_7075_MPA = 572.0
TAU_YIELD_7075_MPA = SY_7075_MPA / math.sqrt(3.0)
TAU_ULT_7075_MPA = SU_7075_MPA / math.sqrt(3.0)

# Thrust-washer OD sensitivity only.
# No final washer OD is selected in B11.
THRUST_WASHER_OD_VALUES_MM = [
    50.0,
    60.0,
    70.0,
    80.0,
    90.0,
]

# Lower/upper edge-ligament sensitivity.
# The current B10 working geometry is 20 mm / 20 mm.
EDGE_LIGAMENT_SWEEP_MM = [
    15.0,
    20.0,
    25.0,
    30.0,
    35.0,
]


# =============================================================================
# 2. GENERIC CSV HELPERS
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
        rows = read_csv_rows(B10_RECORD)

        for row in rows:
            if row.get("parameter") == parameter:
                return (
                    float(row["value"]),
                    str(B10_RECORD),
                )

    return (
        fallback,
        "FALLBACK_FROM_B10_V0.1_WORKING_GEOMETRY",
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
        f"from columns: {fieldnames}"
    )


# =============================================================================
# 3. SOURCE RESOLUTION
# =============================================================================

def find_load_source() -> Path:
    for path in LOAD_CANDIDATES:
        if path.exists():
            return path

    raise FileNotFoundError(
        "Could not find phase1_load_envelope.csv."
    )


def read_force_cases(path: Path):
    with path.open(
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []

        case_col = resolve_column(
            fields,
            [
                "Load Case",
                "case",
                "load_case",
            ],
        )

        columns = {
            ("limit", "Fx"):
                resolve_column(
                    fields,
                    [
                        "Fx Limit (kN)",
                        "Fx_limit_kN",
                    ],
                ),
            ("limit", "Fy"):
                resolve_column(
                    fields,
                    [
                        "Fy Limit (kN)",
                        "Fy_limit_kN",
                    ],
                ),
            ("limit", "Fz"):
                resolve_column(
                    fields,
                    [
                        "Fz Limit (kN)",
                        "Fz_limit_kN",
                    ],
                ),
            ("ultimate", "Fx"):
                resolve_column(
                    fields,
                    [
                        "Fx Ultimate (kN)",
                        "Fx_ultimate_kN",
                    ],
                ),
            ("ultimate", "Fy"):
                resolve_column(
                    fields,
                    [
                        "Fy Ultimate (kN)",
                        "Fy_ultimate_kN",
                    ],
                ),
            ("ultimate", "Fz"):
                resolve_column(
                    fields,
                    [
                        "Fz Ultimate (kN)",
                        "Fz_ultimate_kN",
                    ],
                ),
        }

        loads = {
            "limit": {},
            "ultimate": {},
        }

        for row in reader:
            case_name = row[case_col].strip()

            for level in (
                "limit",
                "ultimate",
            ):
                loads[level][case_name] = {
                    "Fx_kN":
                        float(
                            row[
                                columns[
                                    (level, "Fx")
                                ]
                            ]
                        ),
                    "Fy_kN":
                        float(
                            row[
                                columns[
                                    (level, "Fy")
                                ]
                            ]
                        ),
                    "Fz_kN":
                        float(
                            row[
                                columns[
                                    (level, "Fz")
                                ]
                            ]
                        ),
                }

    return loads


def resolve_bearing_width_mm(
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
                < 1e-12
            ):
                return (
                    float(
                        row[
                            "bearing_width_mm"
                        ]
                    ),
                    str(B10_SPAN),
                )

    return (
        FALLBACK_BEARING_WIDTH_MM,
        "FALLBACK_FROM_B10_V0.1_WORKING_GEOMETRY",
    )


# =============================================================================
# 4. D9/B10 UPPER RESULTANTS AND SUPPORT REACTIONS
# =============================================================================

def upper_resultants_at_trunnion(
    force,
    z_trunnion_above_U_mm: float,
):
    Fx = force["Fx_kN"]
    Fy = force["Fy_kN"]
    Fz = force["Fz_kN"]

    arm_T_m = (
        BASE_UPPER_ARM_M
        + z_trunnion_above_U_mm
        / 1000.0
    )

    return {
        "Fx_kN": Fx,
        "Fy_kN": Fy,
        "Fz_kN": Fz,
        "arm_T_m": arm_T_m,
        "Mx_kNm":
            E_M * Fz
            + arm_T_m * Fy,
        "My_kNm":
            -arm_T_m * Fx,
        "Mz_kNm":
            -E_M * Fx,
    }


def trunnion_reactions(
    upper,
    span_mm: float,
):
    s_m = span_mm / 1000.0

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

    # Equilibrium self-checks.
    assert abs(
        RLy + RRy + Fy
    ) < 1e-10

    assert abs(
        RLz + RRz + Fz
    ) < 1e-10

    assert abs(
        My
        + (s_m / 2.0)
        * (RLz - RRz)
    ) < 1e-10

    assert abs(
        Mz
        + (s_m / 2.0)
        * (RRy - RLy)
    ) < 1e-10

    return {
        "RLy_kN": RLy,
        "RRy_kN": RRy,
        "RLz_kN": RLz,
        "RRz_kN": RRz,
        "RL_kN": RL,
        "RR_kN": RR,
    }


# =============================================================================
# 5. LOCAL HALF-HEAD LUG MODEL
# =============================================================================

def local_lug_screens(
    Ry_kN: float,
    Rz_kN: float,
    head_od_mm: float,
    shaft_d_mm: float,
    lower_ligament_mm: float,
    upper_ligament_mm: float,
    level: str,
):
    """
    Conservative local idealization of one side of the upper head.

    Effective material thickness along x:
        t = D_head / 2

    Vertical z-direction width:
        Wz = lower ligament + hole diameter + upper ligament

    Lateral y-direction width:
        Wy = D_head

    Vertical nearest edge ligament:
        ez = min(lower, upper)

    Lateral side ligament:
        ey = (D_head - hole diameter)/2

    For each direction:
        projected bearing:
            p = P / (t*d)

        net section:
            sigma_net = P / [t*(W-d)]

        two-plane shear-out:
            tau_so = P / (2*t*e)

    These are nominal screens only.
    """
    if level == "limit":
        sigma_allow = SY_7075_MPA
        tau_allow = TAU_YIELD_7075_MPA
    elif level == "ultimate":
        sigma_allow = SU_7075_MPA
        tau_allow = TAU_ULT_7075_MPA
    else:
        raise ValueError(
            "level must be 'limit' or 'ultimate'"
        )

    t_mm = head_od_mm / 2.0

    Wz_mm = (
        lower_ligament_mm
        + shaft_d_mm
        + upper_ligament_mm
    )

    Wy_mm = head_od_mm

    ez_mm = min(
        lower_ligament_mm,
        upper_ligament_mm,
    )

    ey_mm = (
        head_od_mm
        - shaft_d_mm
    ) / 2.0

    Py_N = abs(Ry_kN) * 1000.0
    Pz_N = abs(Rz_kN) * 1000.0

    # Vertical direction.
    p_bearing_z_MPa = (
        Pz_N
        / (
            t_mm
            * shaft_d_mm
        )
    )

    A_net_z_mm2 = (
        t_mm
        * (
            Wz_mm
            - shaft_d_mm
        )
    )

    sigma_net_z_MPa = (
        Pz_N
        / A_net_z_mm2
    )

    A_shearout_z_mm2 = (
        2.0
        * t_mm
        * ez_mm
    )

    tau_shearout_z_MPa = (
        Pz_N
        / A_shearout_z_mm2
    )

    # Lateral direction.
    p_bearing_y_MPa = (
        Py_N
        / (
            t_mm
            * shaft_d_mm
        )
    )

    A_net_y_mm2 = (
        t_mm
        * (
            Wy_mm
            - shaft_d_mm
        )
    )

    sigma_net_y_MPa = (
        Py_N
        / A_net_y_mm2
    )

    A_shearout_y_mm2 = (
        2.0
        * t_mm
        * ey_mm
    )

    tau_shearout_y_MPa = (
        Py_N
        / A_shearout_y_mm2
    )

    return {
        "effective_half_head_thickness_mm":
            t_mm,
        "vertical_width_mm":
            Wz_mm,
        "lateral_width_mm":
            Wy_mm,
        "vertical_edge_ligament_mm":
            ez_mm,
        "lateral_edge_ligament_mm":
            ey_mm,

        "bearing_z_MPa":
            p_bearing_z_MPa,
        "MS_bearing_z_nominal":
            (
                sigma_allow
                / p_bearing_z_MPa
                - 1.0
                if p_bearing_z_MPa > 0.0
                else math.inf
            ),

        "net_z_MPa":
            sigma_net_z_MPa,
        "MS_net_z":
            (
                sigma_allow
                / sigma_net_z_MPa
                - 1.0
                if sigma_net_z_MPa > 0.0
                else math.inf
            ),

        "shearout_z_MPa":
            tau_shearout_z_MPa,
        "MS_shearout_z":
            (
                tau_allow
                / tau_shearout_z_MPa
                - 1.0
                if tau_shearout_z_MPa > 0.0
                else math.inf
            ),

        "bearing_y_MPa":
            p_bearing_y_MPa,
        "MS_bearing_y_nominal":
            (
                sigma_allow
                / p_bearing_y_MPa
                - 1.0
                if p_bearing_y_MPa > 0.0
                else math.inf
            ),

        "net_y_MPa":
            sigma_net_y_MPa,
        "MS_net_y":
            (
                sigma_allow
                / sigma_net_y_MPa
                - 1.0
                if sigma_net_y_MPa > 0.0
                else math.inf
            ),

        "shearout_y_MPa":
            tau_shearout_y_MPa,
        "MS_shearout_y":
            (
                tau_allow
                / tau_shearout_y_MPa
                - 1.0
                if tau_shearout_y_MPa > 0.0
                else math.inf
            ),
    }


# =============================================================================
# 6. ALL LOAD CASES
# =============================================================================

def evaluate_all_cases(
    loads,
    span_mm,
    z_trunnion_mm,
    head_od_mm,
    shaft_d_mm,
    lower_ligament_mm,
    upper_ligament_mm,
):
    rows = []

    for level in (
        "limit",
        "ultimate",
    ):
        for case_name, force in (
            loads[level].items()
        ):
            upper = (
                upper_resultants_at_trunnion(
                    force,
                    z_trunnion_mm,
                )
            )

            reactions = (
                trunnion_reactions(
                    upper,
                    span_mm,
                )
            )

            for side in (
                "LEFT",
                "RIGHT",
            ):
                if side == "LEFT":
                    Ry_kN = reactions["RLy_kN"]
                    Rz_kN = reactions["RLz_kN"]
                    R_kN = reactions["RL_kN"]
                else:
                    Ry_kN = reactions["RRy_kN"]
                    Rz_kN = reactions["RRz_kN"]
                    R_kN = reactions["RR_kN"]

                lug = local_lug_screens(
                    Ry_kN=Ry_kN,
                    Rz_kN=Rz_kN,
                    head_od_mm=head_od_mm,
                    shaft_d_mm=shaft_d_mm,
                    lower_ligament_mm=
                        lower_ligament_mm,
                    upper_ligament_mm=
                        upper_ligament_mm,
                    level=level,
                )

                rows.append({
                    "level": level,
                    "case": case_name,
                    "side": side,

                    "Fx_kN":
                        upper["Fx_kN"],
                    "Fy_kN":
                        upper["Fy_kN"],
                    "Fz_kN":
                        upper["Fz_kN"],

                    "Mx_kNm":
                        upper["Mx_kNm"],
                    "My_kNm":
                        upper["My_kNm"],
                    "Mz_kNm":
                        upper["Mz_kNm"],

                    "Ry_kN":
                        Ry_kN,
                    "Rz_kN":
                        Rz_kN,
                    "R_kN":
                        R_kN,

                    **lug,
                })

    return rows


# =============================================================================
# 7. THRUST-FACE / WASHER SCREEN
# =============================================================================

def maximum_axial_loads(loads):
    results = {}

    for level in (
        "limit",
        "ultimate",
    ):
        case_name, force = max(
            loads[level].items(),
            key=lambda item:
                abs(item[1]["Fx_kN"]),
        )

        results[level] = {
            "case": case_name,
            "Fx_abs_kN":
                abs(force["Fx_kN"]),
        }

    return results


def thrust_face_sweep(
    loads,
    shaft_d_mm,
    head_od_mm,
):
    axial = maximum_axial_loads(loads)

    rows = []

    for washer_od_mm in (
        THRUST_WASHER_OD_VALUES_MM
    ):
        if washer_od_mm <= shaft_d_mm:
            continue

        if washer_od_mm > head_od_mm:
            continue

        annular_area_mm2 = (
            math.pi
            / 4.0
            * (
                washer_od_mm**2
                - shaft_d_mm**2
            )
        )

        p_limit_MPa = (
            axial["limit"]["Fx_abs_kN"]
            * 1000.0
            / annular_area_mm2
        )

        p_ultimate_MPa = (
            axial["ultimate"]["Fx_abs_kN"]
            * 1000.0
            / annular_area_mm2
        )

        rows.append({
            "washer_OD_mm":
                washer_od_mm,
            "shaft_ID_clearance_reference_mm":
                shaft_d_mm,
            "annular_contact_area_mm2":
                annular_area_mm2,

            "limit_case":
                axial["limit"]["case"],
            "limit_Fx_kN":
                axial["limit"]["Fx_abs_kN"],
            "limit_avg_face_pressure_MPa":
                p_limit_MPa,
            "MS_limit_vs_7075_yield":
                SY_7075_MPA
                / p_limit_MPa
                - 1.0,

            "ultimate_case":
                axial["ultimate"]["case"],
            "ultimate_Fx_kN":
                axial[
                    "ultimate"
                ]["Fx_abs_kN"],
            "ultimate_avg_face_pressure_MPa":
                p_ultimate_MPa,
            "MS_ultimate_vs_7075_UTS":
                SU_7075_MPA
                / p_ultimate_MPa
                - 1.0,
        })

    return rows


# =============================================================================
# 8. EDGE-LIGAMENT SENSITIVITY
# =============================================================================

def ligament_sensitivity(
    loads,
    span_mm,
    z_trunnion_mm,
    head_od_mm,
    shaft_d_mm,
):
    rows = []

    for ligament_mm in (
        EDGE_LIGAMENT_SWEEP_MM
    ):
        case_rows = evaluate_all_cases(
            loads=loads,
            span_mm=span_mm,
            z_trunnion_mm=
                z_trunnion_mm,
            head_od_mm=head_od_mm,
            shaft_d_mm=shaft_d_mm,
            lower_ligament_mm=
                ligament_mm,
            upper_ligament_mm=
                ligament_mm,
        )

        ultimate_rows = [
            row
            for row in case_rows
            if row["level"] == "ultimate"
        ]

        gov_net = max(
            ultimate_rows,
            key=lambda row:
                row["net_z_MPa"],
        )

        gov_shear = max(
            ultimate_rows,
            key=lambda row:
                row["shearout_z_MPa"],
        )

        rows.append({
            "edge_ligament_mm":
                ligament_mm,
            "head_height_mm":
                (
                    ligament_mm
                    + shaft_d_mm
                    + ligament_mm
                ),
            "governing_case":
                gov_net["case"],
            "governing_side":
                gov_net["side"],
            "ultimate_Rz_kN":
                abs(gov_net["Rz_kN"]),
            "ultimate_net_z_MPa":
                gov_net["net_z_MPa"],
            "MS_net_z":
                gov_net["MS_net_z"],
            "ultimate_shearout_z_MPa":
                gov_shear[
                    "shearout_z_MPa"
                ],
            "MS_shearout_z":
                gov_shear[
                    "MS_shearout_z"
                ],
            "STATIC_PASS":
                (
                    gov_net["MS_net_z"]
                    >= 0.0
                    and
                    gov_shear[
                        "MS_shearout_z"
                    ]
                    >= 0.0
                ),
        })

    return rows


# =============================================================================
# 9. OUTPUT HELPER
# =============================================================================

def write_csv(
    path: Path,
    rows,
):
    if not rows:
        raise ValueError(
            f"No rows supplied for {path.name}"
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
# 10. MAIN
# =============================================================================

def main():
    # -------------------------------------------------------------------------
    # Source-read B10 values
    # -------------------------------------------------------------------------
    head_od_mm, head_src = (
        read_b10_value(
            "B9_upper_head_OD",
            FALLBACK_HEAD_OD_MM,
        )
    )

    span_mm, span_src = (
        read_b10_value(
            "working_bearing_center_span",
            FALLBACK_SPAN_MM,
        )
    )

    shaft_d_mm, shaft_src = (
        read_b10_value(
            "working_300M_cross_shaft_diameter",
            FALLBACK_SHAFT_D_MM,
        )
    )

    lower_ligament_mm, lower_src = (
        read_b10_value(
            "working_lower_solid_head_ligament",
            FALLBACK_LOWER_LIGAMENT_MM,
        )
    )

    upper_ligament_mm, upper_src = (
        read_b10_value(
            "working_upper_solid_head_ligament",
            FALLBACK_UPPER_LIGAMENT_MM,
        )
    )

    z_trunnion_mm, z_src = (
        read_b10_value(
            "working_trunnion_center_above_U",
            FALLBACK_TRUNNION_Z_ABOVE_U_MM,
        )
    )

    bearing_width_mm, bearing_src = (
        resolve_bearing_width_mm(
            span_mm
        )
    )

    load_source = find_load_source()
    loads = read_force_cases(
        load_source
    )

    # -------------------------------------------------------------------------
    # Evaluate all load cases / both head sides
    # -------------------------------------------------------------------------
    all_rows = evaluate_all_cases(
        loads=loads,
        span_mm=span_mm,
        z_trunnion_mm=
            z_trunnion_mm,
        head_od_mm=head_od_mm,
        shaft_d_mm=shaft_d_mm,
        lower_ligament_mm=
            lower_ligament_mm,
        upper_ligament_mm=
            upper_ligament_mm,
    )

    limit_rows = [
        row
        for row in all_rows
        if row["level"] == "limit"
    ]

    ultimate_rows = [
        row
        for row in all_rows
        if row["level"] == "ultimate"
    ]

    # Governing nominal local screens.
    gov_lim_bearing_z = max(
        limit_rows,
        key=lambda row:
            row["bearing_z_MPa"],
    )

    gov_ult_bearing_z = max(
        ultimate_rows,
        key=lambda row:
            row["bearing_z_MPa"],
    )

    gov_lim_net_z = max(
        limit_rows,
        key=lambda row:
            row["net_z_MPa"],
    )

    gov_ult_net_z = max(
        ultimate_rows,
        key=lambda row:
            row["net_z_MPa"],
    )

    gov_lim_shearout_z = max(
        limit_rows,
        key=lambda row:
            row["shearout_z_MPa"],
    )

    gov_ult_shearout_z = max(
        ultimate_rows,
        key=lambda row:
            row["shearout_z_MPa"],
    )

    gov_ult_bearing_y = max(
        ultimate_rows,
        key=lambda row:
            row["bearing_y_MPa"],
    )

    gov_ult_net_y = max(
        ultimate_rows,
        key=lambda row:
            row["net_y_MPa"],
    )

    gov_ult_shearout_y = max(
        ultimate_rows,
        key=lambda row:
            row["shearout_y_MPa"],
    )

    # -------------------------------------------------------------------------
    # Thrust face / washer
    # -------------------------------------------------------------------------
    thrust_rows = thrust_face_sweep(
        loads=loads,
        shaft_d_mm=shaft_d_mm,
        head_od_mm=head_od_mm,
    )

    # -------------------------------------------------------------------------
    # Ligament sensitivity
    # -------------------------------------------------------------------------
    ligament_rows = (
        ligament_sensitivity(
            loads=loads,
            span_mm=span_mm,
            z_trunnion_mm=
                z_trunnion_mm,
            head_od_mm=
                head_od_mm,
            shaft_d_mm=
                shaft_d_mm,
        )
    )

    # -------------------------------------------------------------------------
    # Geometry ratios
    # -------------------------------------------------------------------------
    half_head_thickness_mm = (
        head_od_mm / 2.0
    )

    vertical_head_height_mm = (
        lower_ligament_mm
        + shaft_d_mm
        + upper_ligament_mm
    )

    side_ligament_mm = (
        head_od_mm
        - shaft_d_mm
    ) / 2.0

    head_to_bearing_gap_mm = (
        span_mm
        - head_od_mm
        - bearing_width_mm
    ) / 2.0

    lower_edge_center_distance_mm = (
        lower_ligament_mm
        + shaft_d_mm / 2.0
    )

    upper_edge_center_distance_mm = (
        upper_ligament_mm
        + shaft_d_mm / 2.0
    )

    # -------------------------------------------------------------------------
    # Overall static nominal pass
    # -------------------------------------------------------------------------
    static_pass = all([
        gov_lim_bearing_z[
            "MS_bearing_z_nominal"
        ] >= 0.0,

        gov_ult_bearing_z[
            "MS_bearing_z_nominal"
        ] >= 0.0,

        gov_lim_net_z[
            "MS_net_z"
        ] >= 0.0,

        gov_ult_net_z[
            "MS_net_z"
        ] >= 0.0,

        gov_lim_shearout_z[
            "MS_shearout_z"
        ] >= 0.0,

        gov_ult_shearout_z[
            "MS_shearout_z"
        ] >= 0.0,

        gov_ult_bearing_y[
            "MS_bearing_y_nominal"
        ] >= 0.0,

        gov_ult_net_y[
            "MS_net_y"
        ] >= 0.0,

        gov_ult_shearout_y[
            "MS_shearout_y"
        ] >= 0.0,
    ])

    # -------------------------------------------------------------------------
    # Output files
    # -------------------------------------------------------------------------
    cases_csv = (
        HERE
        / "phase2e3b11_head_local_cases.csv"
    )

    ligament_csv = (
        HERE
        / "phase2e3b11_ligament_sensitivity.csv"
    )

    thrust_csv = (
        HERE
        / "phase2e3b11_thrust_face_sweep.csv"
    )

    geometry_csv = (
        HERE
        / "phase2e3b11_geometry_record.csv"
    )

    summary_txt = (
        HERE
        / "phase2e3b11_summary.txt"
    )

    geometry_rows = [
        {
            "parameter":
                "head_OD",
            "value":
                head_od_mm,
            "units":
                "mm",
            "classification":
                "SOURCE_B10",
        },
        {
            "parameter":
                "cross_shaft_diameter",
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
                "half_head_lug_thickness",
            "value":
                half_head_thickness_mm,
            "units":
                "mm",
            "classification":
                "B11_IDEALIZATION",
        },
        {
            "parameter":
                "lower_edge_ligament",
            "value":
                lower_ligament_mm,
            "units":
                "mm",
            "classification":
                "SOURCE_B10_WORKING",
        },
        {
            "parameter":
                "upper_edge_ligament",
            "value":
                upper_ligament_mm,
            "units":
                "mm",
            "classification":
                "SOURCE_B10_WORKING",
        },
        {
            "parameter":
                "side_ligament",
            "value":
                side_ligament_mm,
            "units":
                "mm",
            "classification":
                "DERIVED_B11",
        },
        {
            "parameter":
                "vertical_head_height",
            "value":
                vertical_head_height_mm,
            "units":
                "mm",
            "classification":
                "DERIVED_B11",
        },
        {
            "parameter":
                "head_to_bearing_gap",
            "value":
                head_to_bearing_gap_mm,
            "units":
                "mm",
            "classification":
                "DERIVED_B11",
        },
        {
            "parameter":
                "lower_center_to_edge",
            "value":
                lower_edge_center_distance_mm,
            "units":
                "mm",
            "classification":
                "DERIVED_B11",
        },
        {
            "parameter":
                "upper_center_to_edge",
            "value":
                upper_edge_center_distance_mm,
            "units":
                "mm",
            "classification":
                "DERIVED_B11",
        },
        {
            "parameter":
                "lower_ligament_over_d",
            "value":
                lower_ligament_mm
                / shaft_d_mm,
            "units":
                "-",
            "classification":
                "DERIVED_B11",
        },
        {
            "parameter":
                "side_ligament_over_d",
            "value":
                side_ligament_mm
                / shaft_d_mm,
            "units":
                "-",
            "classification":
                "DERIVED_B11",
        },
    ]

    write_csv(
        cases_csv,
        all_rows,
    )

    write_csv(
        ligament_csv,
        ligament_rows,
    )

    write_csv(
        thrust_csv,
        thrust_rows,
    )

    write_csv(
        geometry_csv,
        geometry_rows,
    )

    # -------------------------------------------------------------------------
    # Console report
    # -------------------------------------------------------------------------
    line = "=" * 124
    dash = "-" * 124

    print()
    print(line)
    print(
        " PHASE 2E3-B11 — UPPER-HEAD LOCAL ANALYTICAL "
        "SCREENS V0.1"
    )
    print(line)

    print()
    print("SOURCE CONNECTION")
    print(dash)
    print(
        f"B10 head source:                  "
        f"{head_src}"
    )
    print(
        f"B10 span source:                  "
        f"{span_src}"
    )
    print(
        f"B10 shaft source:                 "
        f"{shaft_src}"
    )
    print(
        f"B10 lower ligament source:        "
        f"{lower_src}"
    )
    print(
        f"B10 upper ligament source:        "
        f"{upper_src}"
    )
    print(
        f"B10 trunnion-z source:            "
        f"{z_src}"
    )
    print(
        f"B10 bearing-width source:         "
        f"{bearing_src}"
    )
    print(
        f"Load source:                      "
        f"{load_source}"
    )

    print()
    print("WORKING B10/B10A GEOMETRY")
    print(dash)
    print(
        f"Head OD:                          "
        f"{head_od_mm:.3f} mm"
    )
    print(
        f"Cross-shaft diameter:             "
        f"{shaft_d_mm:.3f} mm"
    )
    print(
        f"Bearing-center span:              "
        f"{span_mm:.3f} mm"
    )
    print(
        f"Bearing width:                    "
        f"{bearing_width_mm:.3f} mm"
    )
    print(
        f"Trunnion center above U:          "
        f"{z_trunnion_mm:.3f} mm"
    )
    print(
        f"Lower / upper ligament:           "
        f"{lower_ligament_mm:.3f} / "
        f"{upper_ligament_mm:.3f} mm"
    )
    print(
        f"Derived side ligament:            "
        f"{side_ligament_mm:.3f} mm"
    )
    print(
        f"Half-head lug thickness model:    "
        f"{half_head_thickness_mm:.3f} mm"
    )
    print(
        f"Head-to-bearing gap:              "
        f"{head_to_bearing_gap_mm:.3f} mm"
    )

    print()
    print("7075-T6 PRELIMINARY PROJECT STATIC SCREENS")
    print(dash)
    print(
        f"Yield screen:                     "
        f"{SY_7075_MPA:.3f} MPa"
    )
    print(
        f"Ultimate screen:                  "
        f"{SU_7075_MPA:.3f} MPa"
    )
    print(
        f"Von-Mises shear-yield screen:     "
        f"{TAU_YIELD_7075_MPA:.3f} MPa"
    )
    print(
        f"Von-Mises shear-ultimate screen:  "
        f"{TAU_ULT_7075_MPA:.3f} MPa"
    )
    print(
        "Bearing comparisons below are nominal sanity screens, "
        "NOT certified 7075 bearing allowables."
    )

    print()
    print("B11A — GOVERNING VERTICAL BORE / LUG SCREENS")
    print(dash)

    def print_gov(
        label,
        row,
        value_key,
        margin_key,
        units="MPa",
    ):
        print(
            f"{label:<34}"
            f"{row[value_key]:>10.3f} {units:<4}  "
            f"MS={row[margin_key]:>+8.3f}  "
            f"{row['case']} {row['side']}"
        )

    print_gov(
        "Limit projected bore bearing:",
        gov_lim_bearing_z,
        "bearing_z_MPa",
        "MS_bearing_z_nominal",
    )

    print_gov(
        "Ultimate projected bore bearing:",
        gov_ult_bearing_z,
        "bearing_z_MPa",
        "MS_bearing_z_nominal",
    )

    print_gov(
        "Limit net-section:",
        gov_lim_net_z,
        "net_z_MPa",
        "MS_net_z",
    )

    print_gov(
        "Ultimate net-section:",
        gov_ult_net_z,
        "net_z_MPa",
        "MS_net_z",
    )

    print_gov(
        "Limit edge shear-out:",
        gov_lim_shearout_z,
        "shearout_z_MPa",
        "MS_shearout_z",
    )

    print_gov(
        "Ultimate edge shear-out:",
        gov_ult_shearout_z,
        "shearout_z_MPa",
        "MS_shearout_z",
    )

    print()
    print("B11B — GOVERNING LATERAL SIDE-LIGAMENT SCREENS")
    print(dash)

    print_gov(
        "Ultimate lateral bore bearing:",
        gov_ult_bearing_y,
        "bearing_y_MPa",
        "MS_bearing_y_nominal",
    )

    print_gov(
        "Ultimate lateral net-section:",
        gov_ult_net_y,
        "net_y_MPa",
        "MS_net_y",
    )

    print_gov(
        "Ultimate lateral shear-out:",
        gov_ult_shearout_y,
        "shearout_y_MPa",
        "MS_shearout_y",
    )

    print()
    print("B11C — EDGE-LIGAMENT SENSITIVITY")
    print(dash)
    print(
        f"{'Lig':>8}"
        f"{'Head H':>10}"
        f"{'Rz ult':>12}"
        f"{'Net':>12}"
        f"{'MS net':>12}"
        f"{'Shearout':>12}"
        f"{'MS shear':>12}"
        f"{'Status':>12}"
    )
    print("-" * 92)

    for row in ligament_rows:
        print(
            f"{row['edge_ligament_mm']:>7.0f} "
            f"{row['head_height_mm']:>9.1f} "
            f"{row['ultimate_Rz_kN']:>10.2f} "
            f"{row['ultimate_net_z_MPa']:>10.2f} "
            f"{row['MS_net_z']:>10.3f} "
            f"{row['ultimate_shearout_z_MPa']:>10.2f} "
            f"{row['MS_shearout_z']:>10.3f} "
            f"{('PASS' if row['STATIC_PASS'] else 'FAIL'):>10}"
        )

    print()
    print(
        "Interpretation: this table does NOT by itself select a ligament. "
        "It only tells us whether simple net/shear-out strength is driving."
    )

    print()
    print("B11D — AXIAL THRUST-FACE / WASHER PRESSURE")
    print(dash)
    print(
        f"{'Washer OD':>12}"
        f"{'Area':>14}"
        f"{'p limit':>14}"
        f"{'MSy':>12}"
        f"{'p ult':>14}"
        f"{'MSu':>12}"
    )
    print("-" * 82)

    for row in thrust_rows:
        print(
            f"{row['washer_OD_mm']:>11.0f} "
            f"{row['annular_contact_area_mm2']:>12.1f} "
            f"{row['limit_avg_face_pressure_MPa']:>12.3f} "
            f"{row['MS_limit_vs_7075_yield']:>10.3f} "
            f"{row['ultimate_avg_face_pressure_MPa']:>12.3f} "
            f"{row['MS_ultimate_vs_7075_UTS']:>10.3f}"
        )

    print()
    print(
        "No washer OD is frozen here. Average face pressure is expected to be "
        "non-governing; local contact, washer bending, support geometry and "
        "standard hardware still control the practical detail."
    )

    print()
    print("B11E — GEOMETRIC RATIOS FOR B12")
    print(dash)
    print(
        f"Lower center-to-edge:              "
        f"{lower_edge_center_distance_mm:.3f} mm"
    )
    print(
        f"Upper center-to-edge:              "
        f"{upper_edge_center_distance_mm:.3f} mm"
    )
    print(
        f"Lower ligament / shaft d:          "
        f"{lower_ligament_mm/shaft_d_mm:.3f}"
    )
    print(
        f"Side ligament / shaft d:           "
        f"{side_ligament_mm/shaft_d_mm:.3f}"
    )
    print(
        f"Head OD / shaft d:                 "
        f"{head_od_mm/shaft_d_mm:.3f}"
    )
    print(
        f"Vertical head H / shaft d:         "
        f"{vertical_head_height_mm/shaft_d_mm:.3f}"
    )

    print()
    print("STATUS")
    print(dash)
    print(
        "B11 nominal static analytical screen: "
        + (
            "PASS"
            if static_pass
            else "FAIL"
        )
    )
    print(
        "20 mm lower/upper ligament status:    "
        "WORKING GEOMETRY ONLY — NOT FATIGUE/FEA FREEZE"
    )
    print(
        "Projected bore bearing status:        "
        "NOMINAL SCREEN ONLY — CONTACT FEA STILL REQUIRED"
    )
    print(
        "Thrust washer dimensions:             "
        "OPEN — AIRFRAME FITTING/HARDWARE DETAIL REQUIRED"
    )
    print(
        "Next: B12 integrated 3-D head + Ø38 shaft + support-contact FEA, "
        "including bore contact and the real curved head geometry."
    )

    # -------------------------------------------------------------------------
    # Text summary
    # -------------------------------------------------------------------------
    summary = [
        line,
        "PHASE 2E3-B11 — UPPER-HEAD LOCAL ANALYTICAL SCREENS V0.1",
        line,
        "",
        f"Head OD = {head_od_mm:.3f} mm",
        f"Shaft diameter = {shaft_d_mm:.3f} mm",
        f"Span = {span_mm:.3f} mm",
        f"Lower/upper ligament = {lower_ligament_mm:.3f} / "
        f"{upper_ligament_mm:.3f} mm",
        f"Trunnion center = {z_trunnion_mm:.3f} mm above U",
        "",
        "Governing vertical nominal screens:",
        (
            f"  Ultimate bearing = "
            f"{gov_ult_bearing_z['bearing_z_MPa']:.3f} MPa, "
            f"MS={gov_ult_bearing_z['MS_bearing_z_nominal']:+.3f}, "
            f"{gov_ult_bearing_z['case']} "
            f"{gov_ult_bearing_z['side']}"
        ),
        (
            f"  Ultimate net section = "
            f"{gov_ult_net_z['net_z_MPa']:.3f} MPa, "
            f"MS={gov_ult_net_z['MS_net_z']:+.3f}, "
            f"{gov_ult_net_z['case']} "
            f"{gov_ult_net_z['side']}"
        ),
        (
            f"  Ultimate shear-out = "
            f"{gov_ult_shearout_z['shearout_z_MPa']:.3f} MPa, "
            f"MS={gov_ult_shearout_z['MS_shearout_z']:+.3f}, "
            f"{gov_ult_shearout_z['case']} "
            f"{gov_ult_shearout_z['side']}"
        ),
        "",
        (
            "B11 nominal static screen = "
            + (
                "PASS"
                if static_pass
                else "FAIL"
            )
        ),
        "",
        "Interpretation:",
        "- simple bore bearing/net/shear-out screens are pre-FEA checks only",
        "- 20 mm edge ligaments remain working geometry, not a fatigue freeze",
        "- thrust-face average pressure is screened but hardware geometry is open",
        "- B12 must resolve real 3-D contact and local stress concentration",
    ]

    summary_txt.write_text(
        "\n".join(summary) + "\n",
        encoding="utf-8",
    )

    print()
    print("OUTPUT FILES")
    print(dash)
    print(
        f"All local cases:                   "
        f"{cases_csv}"
    )
    print(
        f"Ligament sensitivity:              "
        f"{ligament_csv}"
    )
    print(
        f"Thrust-face sweep:                 "
        f"{thrust_csv}"
    )
    print(
        f"Geometry record:                   "
        f"{geometry_csv}"
    )
    print(
        f"Summary:                           "
        f"{summary_txt}"
    )
    print(line)


if __name__ == "__main__":
    main()
