"""
Landing_Gear_Design_Project
Phase 2E3-B10 — Upper Head / 300M Cross-Trunnion Integration V0.1

Purpose
-------
Recouple the frozen/screened upper-head geometry with the transverse trunnion
architecture after B9/B9A.

This script intentionally shows WHY the working dimensions are selected.

Main questions answered:
    1. Does the old 120 mm bearing-center span still physically fit the B9 head?
    2. Is 150 mm or 180 mm the better integrated support span once the REAL
       journal cantilever from the head face to bearing center is included?
    3. What 300M shaft diameter survives the retained D9 Kt sensitivity through
       Kt = 3 using the integrated geometry?
    4. How sensitive is the result to solid-head ligament below the cross-shaft?
    5. Is a small positive-retention keeper pin statically feasible in double shear?

Architecture retained from Phase 2D9
------------------------------------
Trunnion axis: aircraft +x.

The two radial trunnion supports react:
    Fy, Fz, My, Mz

Full |Fx| is conservatively treated as thrust on the locating shaft/journal.

Mx about the trunnion axis is NOT credited to the shaft journals or keeper pin.
It remains on the independent upper brace / lock-link path.

Important
---------
This is a PRELIMINARY STATIC integration screen.

It does NOT close:
    - real shoulder/fillet Kt
    - shaft/head contact distribution
    - head-bore bearing and net section
    - keeper cross-hole local SCF
    - fretting / wear / fits
    - fatigue / fracture mechanics
    - final airframe fitting
    - certification allowables

Those remain B11/B12 validation items.
"""

from __future__ import annotations

import csv
import math
import re
from pathlib import Path


# =============================================================================
# 0. PROJECT PATHS
# =============================================================================

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent


# =============================================================================
# 1. LOCKED / WORKING GEOMETRY
# =============================================================================

# B9/B9A upper-head outer envelope.
# This value is intentionally classified as a B9 geometry freeze, not as a
# newly-derived B10 value.
HEAD_OD_MM = 106.0

# D9/B2 bearing width retained for the first integrated trade.
BEARING_WIDTH_MM = 25.0

# Candidate support spans already investigated in D9/B2.
SPAN_VALUES_MM = [120.0, 150.0, 180.0]

# Actual integrated shaft-diameter sweep.
SHAFT_DIAMETER_VALUES_MM = [34.0, 36.0, 38.0, 40.0, 42.0, 44.0]

# Retained D9 bending stress-concentration sensitivity.
KT_VALUES = [1.0, 1.5, 2.0, 2.5, 3.0]
KT_ROBUST = 3.0

# Old D9 root-to-bearing-edge packaging allowance.
# In B10 this becomes an explicit minimum geometric clearance requirement,
# not the actual root lever arm.
MIN_HEAD_TO_BEARING_EDGE_CLEARANCE_MM = 5.0

# B10 working integration choices.
WORKING_SPAN_MM = 150.0
WORKING_SHAFT_DIAMETER_MM = 38.0
WORKING_LOWER_LIGAMENT_MM = 20.0
WORKING_UPPER_LIGAMENT_MM = 20.0

# The lower ligament controls trunnion-center height above the E3 pressure
# boundary. It is intentionally swept rather than silently frozen.
LOWER_LIGAMENT_VALUES_MM = [10.0, 15.0, 20.0, 25.0, 30.0]

# Positive retention / locking concept:
# a transverse 300M keeper pin through the central solid-head/shaft region.
# This pin is screened only for axial-thrust retention in double shear.
KEEPER_PIN_VALUES_MM = [5.0, 6.0, 8.0, 10.0, 12.0]
WORKING_KEEPER_PIN_MM = 8.0


# =============================================================================
# 2. FROZEN PHASE 2B / D9 LOAD-PATH GEOMETRY
# =============================================================================

# Wheel/load eccentricity used by Phase 2D9.
E_M = 0.120

# D9 upper datum U is:
#     r_t + h_UA = 0.175 + 0.475 = 0.650 m
RT_M = 0.175
H_UA_STATIC_M = 0.475
BASE_UPPER_ARM_M = RT_M + H_UA_STATIC_M


# =============================================================================
# 3. PROJECT MATERIAL SCREENS
# =============================================================================

# These are the already-carried Phase 2E3-B2 project static screens.
# The script tries to source-read them from the B2 summary first. If that
# summary is unavailable, these explicit project-baseline values are used and
# the fallback is reported in the console/summary.
SY_300M_MPA_FALLBACK = 1517.0
SU_300M_MPA_FALLBACK = 1862.0
BRONZE_STATIC_MPA_FALLBACK = 413.685

# E3A pressure-cavity / solid-head boundary.
# Source resolver searches current project outputs first.
E3_BOUNDARY_MM_FALLBACK = 498.780


# =============================================================================
# 4. SMALL SOURCE-RESOLUTION HELPERS
# =============================================================================

def read_text_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def resolve_e3_boundary_mm() -> tuple[float, str]:
    """
    Resolve the Phase 2E3-A / E2->E3 pressure-cavity boundary.

    Searches project text/CSV artifacts for phrases such as:
        "solid-head boundary: 498.780 mm"
        "E2 +498.780 mm interface"

    Falls back to the locked project value only if no source artifact can be
    parsed. The fallback is explicitly reported.
    """
    patterns = [
        re.compile(
            r"(?:solid[- ]head boundary|E3.*?interface|E2\s*\+)"
            r"[^0-9+\-]*\+?([0-9]+(?:\.[0-9]+)?)\s*mm",
            re.IGNORECASE | re.DOTALL,
        ),
        re.compile(
            r"(?:pressure[- ]closure.*?(?:face|boundary)|E3.*?boundary)"
            r"[^0-9+\-]*\+?([0-9]+(?:\.[0-9]+)?)\s*mm",
            re.IGNORECASE | re.DOTALL,
        ),
    ]

    candidates = []
    for glob_pat in (
        "phase2e3a*.txt",
        "phase2e3a*.csv",
        "phase2e2*interface*.csv",
        "phase2e2*summary*.txt",
    ):
        candidates.extend(HERE.glob(glob_pat))

    for path in candidates:
        text = read_text_safe(path)
        for pat in patterns:
            match = pat.search(text)
            if match:
                value = float(match.group(1))
                if 400.0 <= value <= 650.0:
                    return value, str(path)

    return (
        E3_BOUNDARY_MM_FALLBACK,
        "FALLBACK_LOCKED_PROJECT_VALUE: Phase 2E3-A +498.780 mm boundary",
    )


def resolve_material_screens() -> tuple[float, float, float, str]:
    """
    Prefer the Phase 2E3-B2 summary if present because B2 already source-read
    the D9 300M properties and D5 bronze screen.
    """
    candidates = [
        HERE / "phase2e3b2_summary.txt",
        HERE / "phase2e3b2_trunnion_summary.txt",
    ]

    for path in candidates:
        if not path.exists():
            continue

        text = read_text_safe(path)

        sy_m = re.search(
            r"300M\s+yield\s*:\s*([0-9.]+)\s*MPa",
            text,
            flags=re.IGNORECASE,
        )
        su_m = re.search(
            r"300M\s+ultimate\s*:\s*([0-9.]+)\s*MPa",
            text,
            flags=re.IGNORECASE,
        )
        br_m = re.search(
            r"AMS\s*4640.*?([0-9.]+)\s*MPa",
            text,
            flags=re.IGNORECASE,
        )

        if sy_m and su_m and br_m:
            return (
                float(sy_m.group(1)),
                float(su_m.group(1)),
                float(br_m.group(1)),
                str(path),
            )

    return (
        SY_300M_MPA_FALLBACK,
        SU_300M_MPA_FALLBACK,
        BRONZE_STATIC_MPA_FALLBACK,
        "FALLBACK_LOCKED_PROJECT_SCREENS: Phase 2E3-B2",
    )


# =============================================================================
# 5. LOAD SOURCE
# =============================================================================

def find_load_source() -> Path:
    """
    Prefer the transparent Phase 1 load envelope because its force columns and
    units are explicit and it is the upstream source used by Phase 2.

    No force values are pasted into this script.
    """
    candidates = [
        PROJECT_ROOT / "phase1_loads" / "phase1_load_envelope.csv",
        HERE / "phase1_load_envelope.csv",
    ]

    for path in candidates:
        if path.exists():
            return path

    raise FileNotFoundError(
        "Could not find phase1_load_envelope.csv.\n"
        "Expected one of:\n"
        + "\n".join(f"  {p}" for p in candidates)
    )


def normalized_header_map(fieldnames):
    return {
        re.sub(r"[^a-z0-9]+", "", name.lower()): name
        for name in fieldnames
    }


def resolve_column(fieldnames, aliases):
    hmap = normalized_header_map(fieldnames)

    for alias in aliases:
        key = re.sub(r"[^a-z0-9]+", "", alias.lower())
        if key in hmap:
            return hmap[key]

    raise KeyError(
        f"Could not resolve any of {aliases} from columns:\n{fieldnames}"
    )


def read_force_cases(path: Path):
    """
    Return:
        loads["limit"][case]    = {"Fx_kN", "Fy_kN", "Fz_kN"}
        loads["ultimate"][case] = {"Fx_kN", "Fy_kN", "Fz_kN"}
    """
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []

        case_col = resolve_column(
            fields,
            ["Load Case", "case", "load_case"],
        )

        cols = {
            ("limit", "Fx"): resolve_column(
                fields,
                ["Fx Limit (kN)", "Fx_limit_kN", "Fx_lim_kN"],
            ),
            ("limit", "Fy"): resolve_column(
                fields,
                ["Fy Limit (kN)", "Fy_limit_kN", "Fy_lim_kN"],
            ),
            ("limit", "Fz"): resolve_column(
                fields,
                ["Fz Limit (kN)", "Fz_limit_kN", "Fz_lim_kN"],
            ),
            ("ultimate", "Fx"): resolve_column(
                fields,
                ["Fx Ultimate (kN)", "Fx_ultimate_kN", "Fx_ult_kN"],
            ),
            ("ultimate", "Fy"): resolve_column(
                fields,
                ["Fy Ultimate (kN)", "Fy_ultimate_kN", "Fy_ult_kN"],
            ),
            ("ultimate", "Fz"): resolve_column(
                fields,
                ["Fz Ultimate (kN)", "Fz_ultimate_kN", "Fz_ult_kN"],
            ),
        }

        loads = {
            "limit": {},
            "ultimate": {},
        }

        for row in reader:
            case = row[case_col].strip()

            for level in ("limit", "ultimate"):
                loads[level][case] = {
                    "Fx_kN": float(row[cols[(level, "Fx")]]),
                    "Fy_kN": float(row[cols[(level, "Fy")]]),
                    "Fz_kN": float(row[cols[(level, "Fz")]]),
                }

    if not loads["limit"]:
        raise ValueError(f"No load cases were read from {path}")

    return loads


# =============================================================================
# 6. TRUNNION LOCATION AND UPPER RESULTANTS
# =============================================================================

def trunnion_center_above_U_mm(
    e3_boundary_mm: float,
    lower_ligament_mm: float,
    shaft_diameter_mm: float,
) -> float:
    """
    The lower surface of the shaft bore is kept above the pressure-cavity
    boundary by the selected lower solid-head ligament.

        z_center = z_boundary + ligament + d/2
    """
    return (
        e3_boundary_mm
        + lower_ligament_mm
        + shaft_diameter_mm / 2.0
    )


def upper_resultants_at_trunnion(
    force,
    z_trunnion_above_U_mm: float,
):
    """
    Reconstruct D9 upper-resultant mechanics at the ACTUAL trunnion station.

    D9 at datum U:
        arm_U = 0.650 m

    B10 trunnion is z above U, so:
        arm_T = 0.650 + z

        Mx = e*Fz + arm_T*Fy
        My = -arm_T*Fx
        Mz = -e*Fx

    Units:
        forces  kN
        moments kN*m
    """
    Fx = force["Fx_kN"]
    Fy = force["Fy_kN"]
    Fz = force["Fz_kN"]

    arm_T_m = (
        BASE_UPPER_ARM_M
        + z_trunnion_above_U_mm / 1000.0
    )

    Mx_kNm = (
        E_M * Fz
        + arm_T_m * Fy
    )
    My_kNm = -arm_T_m * Fx
    Mz_kNm = -E_M * Fx

    return {
        "Fx_kN": Fx,
        "Fy_kN": Fy,
        "Fz_kN": Fz,
        "arm_T_m": arm_T_m,
        "Mx_kNm": Mx_kNm,
        "My_kNm": My_kNm,
        "Mz_kNm": Mz_kNm,
    }


# =============================================================================
# 7. TWO-SUPPORT TRUNNION REACTIONS
# =============================================================================

def trunnion_reactions(upper, span_mm: float):
    """
    Two support planes:
        left  x = -s/2
        right x = +s/2

    Equilibrium:
        RLy + RRy + Fy = 0
        RLz + RRz + Fz = 0

    The D9 solution is:
        RLy = (-Fy + 2*Mz/s)/2
        RRy = (-Fy - 2*Mz/s)/2

        RLz = (-Fz - 2*My/s)/2
        RRz = (-Fz + 2*My/s)/2
    """
    s_m = span_mm / 1000.0

    if s_m <= 0.0:
        raise ValueError("Support span must be positive.")

    Fy = upper["Fy_kN"]
    Fz = upper["Fz_kN"]
    My = upper["My_kNm"]
    Mz = upper["Mz_kNm"]

    RLy = (-Fy + 2.0 * Mz / s_m) / 2.0
    RRy = (-Fy - 2.0 * Mz / s_m) / 2.0

    RLz = (-Fz - 2.0 * My / s_m) / 2.0
    RRz = (-Fz + 2.0 * My / s_m) / 2.0

    RL = math.hypot(RLy, RLz)
    RR = math.hypot(RRy, RRz)

    # Exact equilibrium diagnostics.
    force_y_residual = RLy + RRy + Fy
    force_z_residual = RLz + RRz + Fz

    # From the sign convention implied by the closed-form solution.
    moment_y_residual = My + (s_m / 2.0) * (RLz - RRz)
    moment_z_residual = Mz + (s_m / 2.0) * (RRy - RLy)

    assert abs(force_y_residual) < 1e-10
    assert abs(force_z_residual) < 1e-10
    assert abs(moment_y_residual) < 1e-10
    assert abs(moment_z_residual) < 1e-10

    return {
        "RLy_kN": RLy,
        "RRy_kN": RRy,
        "RLz_kN": RLz,
        "RRz_kN": RRz,
        "RL_kN": RL,
        "RR_kN": RR,
    }


# =============================================================================
# 8. INTEGRATED PACKAGING GEOMETRY
# =============================================================================

def head_to_bearing_edge_clearance_mm(
    span_mm: float,
    bearing_width_mm: float,
    head_od_mm: float,
) -> float:
    """
    Bearing inner edge:
        span/2 - bearing_width/2

    Head face:
        head_od/2

    Clearance:
        g = (span - head_od - bearing_width)/2
    """
    return (
        span_mm
        - head_od_mm
        - bearing_width_mm
    ) / 2.0


def actual_root_lever_mm(
    span_mm: float,
    head_od_mm: float,
) -> float:
    """
    IMPORTANT B10 recoupling.

    The old D9 stress model used:
        5 mm gap + bearing_width/2

    Once the real B9 head is introduced, the journal root is the head face.
    Therefore the actual cantilever from head face to bearing center is:

        l = span/2 - head_od/2
    """
    return (
        span_mm
        - head_od_mm
    ) / 2.0


# =============================================================================
# 9. 300M SHAFT/JOURNAL STATIC SCREEN
# =============================================================================

def solid_round_area_mm2(d_mm: float) -> float:
    return math.pi * d_mm**2 / 4.0


def journal_stress_screen(
    radial_reaction_kN: float,
    axial_thrust_kN: float,
    diameter_mm: float,
    root_lever_mm: float,
    Kt_bending: float,
):
    """
    D9-style static journal-root screen with the B10 ACTUAL lever arm.

    Solid circular shaft:
        sigma_b = 32 M / (pi d^3)
        sigma_a = F / A

    Conservative tensile-side normal stress:
        sigma_max = sigma_a + Kt*sigma_b

    At the free outer surface of a solid circular section, transverse shear from
    the radial force is zero, so the local surface von Mises value used by the
    D9/B2 root screen is the magnitude of sigma_max.

    Transverse shear is still checked separately using:
        tau_max = 4V/(3A)
    """
    d_m = diameter_mm / 1000.0
    lever_m = root_lever_mm / 1000.0

    A_m2 = math.pi * d_m**2 / 4.0

    R_N = radial_reaction_kN * 1000.0
    Fx_N = abs(axial_thrust_kN) * 1000.0

    M_root_Nm = R_N * lever_m

    sigma_b_MPa = (
        32.0 * M_root_Nm
        / (math.pi * d_m**3)
        / 1e6
    )

    sigma_axial_MPa = (
        Fx_N
        / A_m2
        / 1e6
    )

    sigma_surface_MPa = (
        sigma_axial_MPa
        + Kt_bending * sigma_b_MPa
    )

    vm_surface_MPa = abs(sigma_surface_MPa)

    tau_transverse_MPa = (
        4.0 * R_N
        / (3.0 * A_m2)
        / 1e6
    )

    return {
        "M_root_kNm": M_root_Nm / 1000.0,
        "sigma_b_nominal_MPa": sigma_b_MPa,
        "sigma_axial_MPa": sigma_axial_MPa,
        "vm_surface_MPa": vm_surface_MPa,
        "tau_transverse_MPa": tau_transverse_MPa,
    }


# =============================================================================
# 10. SINGLE INTEGRATED DESIGN EVALUATION
# =============================================================================

def evaluate_design(
    loads,
    sy_300m_mpa,
    su_300m_mpa,
    bronze_static_mpa,
    e3_boundary_mm,
    span_mm,
    bearing_width_mm,
    shaft_diameter_mm,
    lower_ligament_mm,
    Kt_bending,
):
    z_trunnion_mm = trunnion_center_above_U_mm(
        e3_boundary_mm,
        lower_ligament_mm,
        shaft_diameter_mm,
    )

    clearance_mm = head_to_bearing_edge_clearance_mm(
        span_mm,
        bearing_width_mm,
        HEAD_OD_MM,
    )

    root_lever_mm = actual_root_lever_mm(
        span_mm,
        HEAD_OD_MM,
    )

    tau_yield_mpa = sy_300m_mpa / math.sqrt(3.0)
    tau_ultimate_mpa = su_300m_mpa / math.sqrt(3.0)

    case_rows = []

    for level in ("limit", "ultimate"):
        for case_name, force in loads[level].items():
            upper = upper_resultants_at_trunnion(
                force,
                z_trunnion_mm,
            )

            reaction = trunnion_reactions(
                upper,
                span_mm,
            )

            if reaction["RL_kN"] >= reaction["RR_kN"]:
                governing_side = "LEFT"
                Rgov_kN = reaction["RL_kN"]
            else:
                governing_side = "RIGHT"
                Rgov_kN = reaction["RR_kN"]

            stress = journal_stress_screen(
                Rgov_kN,
                upper["Fx_kN"],
                shaft_diameter_mm,
                root_lever_mm,
                Kt_bending,
            )

            bearing_pressure_MPa = (
                Rgov_kN * 1000.0
                / (
                    shaft_diameter_mm
                    * bearing_width_mm
                )
            )

            allowable_vm = (
                sy_300m_mpa
                if level == "limit"
                else su_300m_mpa
            )

            allowable_tau = (
                tau_yield_mpa
                if level == "limit"
                else tau_ultimate_mpa
            )

            case_rows.append({
                "level": level,
                "case": case_name,
                "governing_side": governing_side,
                "z_trunnion_above_U_mm": z_trunnion_mm,
                "arm_T_m": upper["arm_T_m"],
                "Fx_kN": upper["Fx_kN"],
                "Fy_kN": upper["Fy_kN"],
                "Fz_kN": upper["Fz_kN"],
                "Mx_kNm": upper["Mx_kNm"],
                "My_kNm": upper["My_kNm"],
                "Mz_kNm": upper["Mz_kNm"],
                "RL_kN": reaction["RL_kN"],
                "RR_kN": reaction["RR_kN"],
                "Rgov_kN": Rgov_kN,
                "bearing_pressure_MPa": bearing_pressure_MPa,
                "MS_bearing": (
                    bronze_static_mpa
                    / bearing_pressure_MPa
                    - 1.0
                ),
                "MS_vm": (
                    allowable_vm
                    / stress["vm_surface_MPa"]
                    - 1.0
                ),
                "MS_transverse_shear": (
                    allowable_tau
                    / stress["tau_transverse_MPa"]
                    - 1.0
                ),
                **stress,
            })

    limit_rows = [
        row for row in case_rows
        if row["level"] == "limit"
    ]
    ultimate_rows = [
        row for row in case_rows
        if row["level"] == "ultimate"
    ]

    gov_limit_vm = max(
        limit_rows,
        key=lambda row: row["vm_surface_MPa"],
    )
    gov_ultimate_vm = max(
        ultimate_rows,
        key=lambda row: row["vm_surface_MPa"],
    )

    gov_limit_bearing = max(
        limit_rows,
        key=lambda row: row["bearing_pressure_MPa"],
    )
    gov_ultimate_bearing = max(
        ultimate_rows,
        key=lambda row: row["bearing_pressure_MPa"],
    )

    gov_limit_shear = max(
        limit_rows,
        key=lambda row: row["tau_transverse_MPa"],
    )
    gov_ultimate_shear = max(
        ultimate_rows,
        key=lambda row: row["tau_transverse_MPa"],
    )

    packaging_pass = (
        clearance_mm
        >= MIN_HEAD_TO_BEARING_EDGE_CLEARANCE_MM
    )

    strength_pass = all([
        gov_limit_vm["MS_vm"] >= 0.0,
        gov_ultimate_vm["MS_vm"] >= 0.0,
        gov_limit_bearing["MS_bearing"] >= 0.0,
        gov_ultimate_bearing["MS_bearing"] >= 0.0,
        gov_limit_shear["MS_transverse_shear"] >= 0.0,
        gov_ultimate_shear["MS_transverse_shear"] >= 0.0,
    ])

    return {
        "span_mm": span_mm,
        "head_od_mm": HEAD_OD_MM,
        "bearing_width_mm": bearing_width_mm,
        "shaft_diameter_mm": shaft_diameter_mm,
        "lower_ligament_mm": lower_ligament_mm,
        "Kt_bending": Kt_bending,
        "z_trunnion_above_U_mm": z_trunnion_mm,
        "head_to_bearing_edge_clearance_mm": clearance_mm,
        "actual_root_lever_mm": root_lever_mm,
        "packaging_pass": packaging_pass,
        "strength_pass": strength_pass,
        "PASS": packaging_pass and strength_pass,

        "limit_governing_case": gov_limit_vm["case"],
        "limit_governing_side": gov_limit_vm["governing_side"],
        "limit_Rgov_kN": gov_limit_vm["Rgov_kN"],
        "limit_root_moment_kNm": gov_limit_vm["M_root_kNm"],
        "limit_vm_MPa": gov_limit_vm["vm_surface_MPa"],
        "MS_limit_yield": gov_limit_vm["MS_vm"],

        "ultimate_governing_case": gov_ultimate_vm["case"],
        "ultimate_governing_side": gov_ultimate_vm["governing_side"],
        "ultimate_Rgov_kN": gov_ultimate_vm["Rgov_kN"],
        "ultimate_root_moment_kNm": gov_ultimate_vm["M_root_kNm"],
        "ultimate_vm_MPa": gov_ultimate_vm["vm_surface_MPa"],
        "MS_ultimate": gov_ultimate_vm["MS_vm"],

        "ultimate_bearing_pressure_MPa":
            gov_ultimate_bearing["bearing_pressure_MPa"],
        "MS_ultimate_bearing":
            gov_ultimate_bearing["MS_bearing"],

        "ultimate_tau_transverse_MPa":
            gov_ultimate_shear["tau_transverse_MPa"],
        "MS_ultimate_transverse_shear":
            gov_ultimate_shear["MS_transverse_shear"],

        "_case_rows": case_rows,
    }


# =============================================================================
# 11. POSITIVE RETENTION / KEEPER-PIN SCREEN
# =============================================================================

def max_abs_fx(loads, level):
    case_name, force = max(
        loads[level].items(),
        key=lambda item: abs(item[1]["Fx_kN"]),
    )
    return case_name, abs(force["Fx_kN"])


def keeper_pin_screen(
    loads,
    sy_300m_mpa,
    su_300m_mpa,
    main_shaft_diameter_mm,
):
    """
    Working retention architecture:
        - transverse keeper pin through central shaft/head region
        - 300M pin
        - double shear for axial shaft-retention load
        - NOT credited with reacting Mx

    This is only a global static pin screen. The local cross-hole SCF in the
    main shaft/head is deliberately deferred to B11/B12.
    """
    limit_case, Fx_limit_kN = max_abs_fx(loads, "limit")
    ult_case, Fx_ult_kN = max_abs_fx(loads, "ultimate")

    tau_yield_mpa = sy_300m_mpa / math.sqrt(3.0)
    tau_ult_mpa = su_300m_mpa / math.sqrt(3.0)

    rows = []

    for d_pin_mm in KEEPER_PIN_VALUES_MM:
        A_pin_mm2 = math.pi * d_pin_mm**2 / 4.0

        tau_limit_MPa = (
            Fx_limit_kN * 1000.0
            / (2.0 * A_pin_mm2)
        )

        tau_ultimate_MPa = (
            Fx_ult_kN * 1000.0
            / (2.0 * A_pin_mm2)
        )

        # Nominal projected bearing at the cross-hole through the main shaft.
        # This is recorded for B11; no local bearing allowable is assigned here.
        p_nominal_shaft_MPa = (
            Fx_ult_kN * 1000.0
            / (
                d_pin_mm
                * main_shaft_diameter_mm
            )
        )

        rows.append({
            "keeper_pin_diameter_mm": d_pin_mm,
            "limit_case": limit_case,
            "limit_retention_load_kN": Fx_limit_kN,
            "limit_double_shear_MPa": tau_limit_MPa,
            "MS_limit_pin_shear": (
                tau_yield_mpa / tau_limit_MPa - 1.0
            ),
            "ultimate_case": ult_case,
            "ultimate_retention_load_kN": Fx_ult_kN,
            "ultimate_double_shear_MPa": tau_ultimate_MPa,
            "MS_ultimate_pin_shear": (
                tau_ult_mpa / tau_ultimate_MPa - 1.0
            ),
            "nominal_cross_hole_bearing_MPa":
                p_nominal_shaft_MPa,
            "pin_to_main_shaft_diameter_ratio":
                d_pin_mm / main_shaft_diameter_mm,
            "STATIC_PIN_PASS":
                (
                    tau_limit_MPa <= tau_yield_mpa
                    and tau_ultimate_MPa <= tau_ult_mpa
                ),
        })

    return rows


# =============================================================================
# 12. CSV WRITER
# =============================================================================

def write_csv(path: Path, rows):
    if not rows:
        raise ValueError(f"No rows supplied for {path.name}")

    cleaned_rows = []
    for row in rows:
        cleaned_rows.append({
            key: value
            for key, value in row.items()
            if not key.startswith("_")
        })

    fieldnames = list(cleaned_rows[0].keys())

    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        writer.writerows(cleaned_rows)


# =============================================================================
# 13. MAIN
# =============================================================================

def main():
    # -------------------------------------------------------------------------
    # Resolve sources
    # -------------------------------------------------------------------------
    load_source = find_load_source()
    loads = read_force_cases(load_source)

    e3_boundary_mm, e3_boundary_source = (
        resolve_e3_boundary_mm()
    )

    (
        sy_300m_mpa,
        su_300m_mpa,
        bronze_static_mpa,
        material_source,
    ) = resolve_material_screens()

    tau_yield_mpa = sy_300m_mpa / math.sqrt(3.0)
    tau_ultimate_mpa = su_300m_mpa / math.sqrt(3.0)

    # -------------------------------------------------------------------------
    # A. Integrated span trade at the working shaft/ligament
    # -------------------------------------------------------------------------
    span_trade = []

    for span_mm in SPAN_VALUES_MM:
        result = evaluate_design(
            loads=loads,
            sy_300m_mpa=sy_300m_mpa,
            su_300m_mpa=su_300m_mpa,
            bronze_static_mpa=bronze_static_mpa,
            e3_boundary_mm=e3_boundary_mm,
            span_mm=span_mm,
            bearing_width_mm=BEARING_WIDTH_MM,
            shaft_diameter_mm=
                WORKING_SHAFT_DIAMETER_MM,
            lower_ligament_mm=
                WORKING_LOWER_LIGAMENT_MM,
            Kt_bending=KT_ROBUST,
        )

        span_trade.append(result)

    # -------------------------------------------------------------------------
    # B. Shaft diameter sweep at working 150 mm span
    # -------------------------------------------------------------------------
    shaft_sweep = []

    for diameter_mm in SHAFT_DIAMETER_VALUES_MM:
        for Kt in KT_VALUES:
            result = evaluate_design(
                loads=loads,
                sy_300m_mpa=sy_300m_mpa,
                su_300m_mpa=su_300m_mpa,
                bronze_static_mpa=bronze_static_mpa,
                e3_boundary_mm=e3_boundary_mm,
                span_mm=WORKING_SPAN_MM,
                bearing_width_mm=BEARING_WIDTH_MM,
                shaft_diameter_mm=diameter_mm,
                lower_ligament_mm=
                    WORKING_LOWER_LIGAMENT_MM,
                Kt_bending=Kt,
            )
            shaft_sweep.append(result)

    robust_diameter_rows = [
        row
        for row in shaft_sweep
        if (
            abs(row["Kt_bending"] - KT_ROBUST) < 1e-12
            and row["PASS"]
        )
    ]

    if not robust_diameter_rows:
        raise RuntimeError(
            "No shaft diameter passes the Kt=3 integrated screen."
        )

    mathematical_minimum_diameter_mm = min(
        row["shaft_diameter_mm"]
        for row in robust_diameter_rows
    )

    # -------------------------------------------------------------------------
    # C. Ligament sensitivity at the working span / diameter
    # -------------------------------------------------------------------------
    ligament_sweep = []

    for ligament_mm in LOWER_LIGAMENT_VALUES_MM:
        result = evaluate_design(
            loads=loads,
            sy_300m_mpa=sy_300m_mpa,
            su_300m_mpa=su_300m_mpa,
            bronze_static_mpa=bronze_static_mpa,
            e3_boundary_mm=e3_boundary_mm,
            span_mm=WORKING_SPAN_MM,
            bearing_width_mm=BEARING_WIDTH_MM,
            shaft_diameter_mm=
                WORKING_SHAFT_DIAMETER_MM,
            lower_ligament_mm=ligament_mm,
            Kt_bending=KT_ROBUST,
        )
        ligament_sweep.append(result)

    # -------------------------------------------------------------------------
    # D. Positive-retention keeper-pin screen
    # -------------------------------------------------------------------------
    keeper_rows = keeper_pin_screen(
        loads,
        sy_300m_mpa,
        su_300m_mpa,
        WORKING_SHAFT_DIAMETER_MM,
    )

    working_keeper = next(
        row
        for row in keeper_rows
        if abs(
            row["keeper_pin_diameter_mm"]
            - WORKING_KEEPER_PIN_MM
        ) < 1e-12
    )

    # -------------------------------------------------------------------------
    # E. Working design result
    # -------------------------------------------------------------------------
    working = evaluate_design(
        loads=loads,
        sy_300m_mpa=sy_300m_mpa,
        su_300m_mpa=su_300m_mpa,
        bronze_static_mpa=bronze_static_mpa,
        e3_boundary_mm=e3_boundary_mm,
        span_mm=WORKING_SPAN_MM,
        bearing_width_mm=BEARING_WIDTH_MM,
        shaft_diameter_mm=
            WORKING_SHAFT_DIAMETER_MM,
        lower_ligament_mm=
            WORKING_LOWER_LIGAMENT_MM,
        Kt_bending=KT_ROBUST,
    )

    solid_head_height_mm = (
        WORKING_LOWER_LIGAMENT_MM
        + WORKING_SHAFT_DIAMETER_MM
        + WORKING_UPPER_LIGAMENT_MM
    )

    # -------------------------------------------------------------------------
    # F. Design record / traceability rows
    # -------------------------------------------------------------------------
    design_record = [
        {
            "parameter":
                "B9_upper_head_OD",
            "value": HEAD_OD_MM,
            "units": "mm",
            "classification":
                "FROZEN_B9_GEOMETRY",
            "derivation":
                "Retained B9/B9A upper-head envelope.",
            "status":
                "FROZEN_FOR_B10_INTEGRATION",
        },
        {
            "parameter":
                "E3_pressure_cavity_boundary_above_U",
            "value": e3_boundary_mm,
            "units": "mm",
            "classification":
                "SOURCE_E3A_E2_INTERFACE",
            "derivation":
                e3_boundary_source,
            "status":
                "FROZEN_PACKAGING_BOUNDARY",
        },
        {
            "parameter":
                "minimum_support_span_from_packaging",
            "value": (
                HEAD_OD_MM
                + BEARING_WIDTH_MM
                + 2.0
                * MIN_HEAD_TO_BEARING_EDGE_CLEARANCE_MM
            ),
            "units": "mm",
            "classification":
                "DERIVED_B10",
            "derivation":
                "s_min = D_head + L_bearing + 2*g_min",
            "status":
                "DERIVED_REQUIREMENT",
        },
        {
            "parameter":
                "working_bearing_center_span",
            "value": WORKING_SPAN_MM,
            "units": "mm",
            "classification":
                "WORKING_B10_SELECTION",
            "derivation":
                (
                    "120 mm fails B9 head packaging; "
                    "150 mm clears head and gives shorter real journal "
                    "cantilever than 180 mm."
                ),
            "status":
                "PRELIMINARY_NOT_AIRFRAME_FREEZE",
        },
        {
            "parameter":
                "mathematical_min_shaft_diameter_Kt3",
            "value":
                mathematical_minimum_diameter_mm,
            "units": "mm",
            "classification":
                "DERIVED_B10",
            "derivation":
                (
                    "Minimum diameter passing limit/ultimate VM, bearing, "
                    "shear and packaging at Kt=3."
                ),
            "status":
                "DO_NOT_FREEZE_AT_MATHEMATICAL_MINIMUM",
        },
        {
            "parameter":
                "working_300M_cross_shaft_diameter",
            "value":
                WORKING_SHAFT_DIAMETER_MM,
            "units": "mm",
            "classification":
                "WORKING_B10_SELECTION",
            "derivation":
                (
                    "One nominal step above mathematical minimum; "
                    "verified through Kt=3 integrated static screen."
                ),
            "status":
                "PRELIMINARY_PENDING_LOCAL_FEA",
        },
        {
            "parameter":
                "working_lower_solid_head_ligament",
            "value":
                WORKING_LOWER_LIGAMENT_MM,
            "units": "mm",
            "classification":
                "WORKING_B10_GEOMETRY",
            "derivation":
                (
                    "Packaging choice above pressure boundary; sensitivity "
                    "reported separately. Not yet local-strength validated."
                ),
            "status":
                "PRELIMINARY_PENDING_B11_B12",
        },
        {
            "parameter":
                "working_upper_solid_head_ligament",
            "value":
                WORKING_UPPER_LIGAMENT_MM,
            "units": "mm",
            "classification":
                "WORKING_B10_GEOMETRY",
            "derivation":
                (
                    "Initial symmetric solid-head cap allowance above shaft."
                ),
            "status":
                "PRELIMINARY_PENDING_B11_B12",
        },
        {
            "parameter":
                "working_solid_head_axial_height",
            "value":
                solid_head_height_mm,
            "units": "mm",
            "classification":
                "DERIVED_B10",
            "derivation":
                "lower_ligament + shaft_diameter + upper_ligament",
            "status":
                "PRELIMINARY_PENDING_B11_B12",
        },
        {
            "parameter":
                "working_trunnion_center_above_U",
            "value":
                working["z_trunnion_above_U_mm"],
            "units": "mm",
            "classification":
                "DERIVED_B10",
            "derivation":
                "E3_boundary + lower_ligament + shaft_diameter/2",
            "status":
                "PRELIMINARY_PENDING_HEAD_VALIDATION",
        },
        {
            "parameter":
                "working_keeper_pin_diameter",
            "value":
                WORKING_KEEPER_PIN_MM,
            "units": "mm",
            "classification":
                "WORKING_B10_RETENTION",
            "derivation":
                (
                    "300M transverse keeper, double-shear static retention "
                    "screen for axial Fx only."
                ),
            "status":
                "PRELIMINARY_PENDING_CROSS_HOLE_FEA",
        },
    ]

    # -------------------------------------------------------------------------
    # G. Outputs
    # -------------------------------------------------------------------------
    span_csv = HERE / "phase2e3b10_span_trade.csv"
    shaft_csv = HERE / "phase2e3b10_shaft_sweep.csv"
    ligament_csv = HERE / "phase2e3b10_ligament_sensitivity.csv"
    keeper_csv = HERE / "phase2e3b10_keeper_pin_screen.csv"
    record_csv = HERE / "phase2e3b10_design_record.csv"
    summary_txt = HERE / "phase2e3b10_summary.txt"

    write_csv(span_csv, span_trade)
    write_csv(shaft_csv, shaft_sweep)
    write_csv(ligament_csv, ligament_sweep)
    write_csv(keeper_csv, keeper_rows)
    write_csv(record_csv, design_record)

    # -------------------------------------------------------------------------
    # H. Console report
    # -------------------------------------------------------------------------
    line = "=" * 124
    dash = "-" * 124

    print()
    print(line)
    print(
        " PHASE 2E3-B10 — UPPER HEAD / 300M CROSS-TRUNNION "
        "INTEGRATION V0.1"
    )
    print(line)

    print()
    print("SOURCE CONNECTION")
    print(dash)
    print(f"Load envelope:                    {load_source}")
    print(f"E3 pressure boundary source:      {e3_boundary_source}")
    print(f"Material-screen source:           {material_source}")

    print()
    print("SOURCE / FROZEN VALUES")
    print(dash)
    print(f"B9 upper-head OD:                 {HEAD_OD_MM:.3f} mm")
    print(
        f"E3 solid-head boundary:           "
        f"{e3_boundary_mm:.3f} mm above U"
    )
    print(f"300M yield screen:                {sy_300m_mpa:.3f} MPa")
    print(f"300M ultimate screen:             {su_300m_mpa:.3f} MPa")
    print(f"300M pure-shear yield screen:     {tau_yield_mpa:.3f} MPa")
    print(f"300M pure-shear ultimate screen:  {tau_ultimate_mpa:.3f} MPa")
    print(
        f"AMS 4640 static bearing screen:   "
        f"{bronze_static_mpa:.3f} MPa"
    )

    print()
    print("B10A — SUPPORT-SPAN RECOUPLING")
    print(dash)
    minimum_span_mm = (
        HEAD_OD_MM
        + BEARING_WIDTH_MM
        + 2.0
        * MIN_HEAD_TO_BEARING_EDGE_CLEARANCE_MM
    )
    print(
        "Packaging equation:               "
        "s_min = D_head + L_bearing + 2*g_min"
    )
    print(
        f"Minimum packaging span:           "
        f"{minimum_span_mm:.3f} mm"
    )
    print(
        f"Trade basis shaft / bearing:      "
        f"{WORKING_SHAFT_DIAMETER_MM:.0f} mm / "
        f"{BEARING_WIDTH_MM:.0f} mm"
    )
    print(
        f"Trade basis lower ligament:       "
        f"{WORKING_LOWER_LIGAMENT_MM:.0f} mm"
    )
    print(
        f"Stress sensitivity shown:         "
        f"Kt = {KT_ROBUST:.1f}"
    )
    print()
    print(
        f"{'Span':>8}"
        f"{'Gap':>12}"
        f"{'Root arm':>12}"
        f"{'Rult':>12}"
        f"{'Mroot':>12}"
        f"{'VMult':>12}"
        f"{'MSu':>10}"
        f"{'Status':>20}"
    )
    print("-" * 98)

    for row in span_trade:
        if not row["packaging_pass"]:
            status = "FAIL PACKAGING"
        elif not row["strength_pass"]:
            status = "FAIL STATIC"
        else:
            status = "PASS"

        print(
            f"{row['span_mm']:>7.0f} "
            f"{row['head_to_bearing_edge_clearance_mm']:>10.1f} "
            f"{row['actual_root_lever_mm']:>10.1f} "
            f"{row['ultimate_Rgov_kN']:>10.2f} "
            f"{row['ultimate_root_moment_kNm']:>10.3f} "
            f"{row['ultimate_vm_MPa']:>10.1f} "
            f"{row['MS_ultimate']:>9.3f} "
            f"{status:>18}"
        )

    print()
    print("B10 SPAN DECISION")
    print(dash)
    print(
        "120 mm: rejected because the 25 mm bearing physically overlaps "
        "the 106 mm B9 head."
    )
    print(
        "180 mm: keeps generous packaging clearance but increases the REAL "
        "head-face-to-bearing-center cantilever."
    )
    print(
        "150 mm: retained as the working integrated span because it clears "
        "the B9 head while materially shortening journal-root leverage."
    )
    print(
        "This supersedes the earlier post-B9 180 mm packaging preference; "
        "the earlier trade remains valid history, but B10 adds the missing "
        "root-lever coupling."
    )

    print()
    print("B10B — 300M CROSS-SHAFT DIAMETER SWEEP AT 150 mm SPAN")
    print(dash)
    print(
        f"{'d':>8}"
        f"{'z>U':>12}"
        f"{'Rult':>12}"
        f"{'VM @ Kt3':>14}"
        f"{'MSu':>10}"
        f"{'p_brg':>12}"
        f"{'MSp':>10}"
        f"{'Status':>14}"
    )
    print("-" * 92)

    robust_rows = [
        row
        for row in shaft_sweep
        if abs(row["Kt_bending"] - KT_ROBUST) < 1e-12
    ]

    for row in robust_rows:
        status = "PASS" if row["PASS"] else "FAIL"
        print(
            f"{row['shaft_diameter_mm']:>7.0f} "
            f"{row['z_trunnion_above_U_mm']:>10.1f} "
            f"{row['ultimate_Rgov_kN']:>10.2f} "
            f"{row['ultimate_vm_MPa']:>12.1f} "
            f"{row['MS_ultimate']:>9.3f} "
            f"{row['ultimate_bearing_pressure_MPa']:>10.1f} "
            f"{row['MS_ultimate_bearing']:>9.3f} "
            f"{status:>12}"
        )

    print()
    print(
        f"Mathematical minimum passing d:    "
        f"{mathematical_minimum_diameter_mm:.0f} mm"
    )
    print(
        f"Working B10 shaft diameter:        "
        f"{WORKING_SHAFT_DIAMETER_MM:.0f} mm"
    )
    print(
        "Reason: do not freeze at the mathematical minimum; retain additional "
        "margin before real shoulder/cross-hole/contact FEA."
    )

    print()
    print("WORKING B10 INTEGRATED SHAFT RESULT — Kt = 3")
    print(dash)
    print(
        f"Span / shaft / bearing:           "
        f"{WORKING_SPAN_MM:.0f} / "
        f"{WORKING_SHAFT_DIAMETER_MM:.0f} / "
        f"{BEARING_WIDTH_MM:.0f} mm"
    )
    print(
        f"Head-to-bearing-edge gap:         "
        f"{working['head_to_bearing_edge_clearance_mm']:.3f} mm"
    )
    print(
        f"Actual root lever:                "
        f"{working['actual_root_lever_mm']:.3f} mm"
    )
    print(
        f"Trunnion center above U:          "
        f"{working['z_trunnion_above_U_mm']:.3f} mm"
    )
    print(
        f"Ultimate governing case:          "
        f"{working['ultimate_governing_case']}"
    )
    print(
        f"Ultimate radial reaction:         "
        f"{working['ultimate_Rgov_kN']:.3f} kN"
    )
    print(
        f"Ultimate root moment:             "
        f"{working['ultimate_root_moment_kNm']:.3f} kN*m"
    )
    print(
        f"Ultimate VM root screen:          "
        f"{working['ultimate_vm_MPa']:.3f} MPa"
    )
    print(
        f"Ultimate strength margin:         "
        f"{working['MS_ultimate']:+.3f}"
    )
    print(
        f"Ultimate bearing pressure:        "
        f"{working['ultimate_bearing_pressure_MPa']:.3f} MPa"
    )
    print(
        f"Bronze static margin:             "
        f"{working['MS_ultimate_bearing']:+.3f}"
    )
    print(
        f"Ultimate transverse shear:        "
        f"{working['ultimate_tau_transverse_MPa']:.3f} MPa"
    )
    print(
        f"Ultimate shear margin:            "
        f"{working['MS_ultimate_transverse_shear']:+.3f}"
    )

    print()
    print("B10C — SOLID-HEAD LIGAMENT SENSITIVITY")
    print(dash)
    print(
        f"{'Lower lig':>12}"
        f"{'z>U':>12}"
        f"{'Rult':>12}"
        f"{'VMult':>12}"
        f"{'MSu':>10}"
        f"{'Status':>14}"
    )
    print("-" * 72)

    for row in ligament_sweep:
        status = "PASS" if row["PASS"] else "FAIL"
        print(
            f"{row['lower_ligament_mm']:>10.0f} "
            f"{row['z_trunnion_above_U_mm']:>10.1f} "
            f"{row['ultimate_Rgov_kN']:>10.2f} "
            f"{row['ultimate_vm_MPa']:>10.1f} "
            f"{row['MS_ultimate']:>9.3f} "
            f"{status:>12}"
        )

    print()
    print(
        "Important: ligament PASS here only means the shaft/journal screen "
        "remains acceptable as the trunnion center moves."
    )
    print(
        "It does NOT validate the 7075 head ligament, bore bearing, net section "
        "or local hole stresses. Those are B11/B12."
    )

    print()
    print("B10D — POSITIVE SHAFT RETENTION / LOCKING")
    print(dash)
    print(
        "Working architecture: central transverse 300M keeper pin through the "
        "solid-head / cross-shaft region."
    )
    print(
        "Credited load: axial shaft-retention Fx only, pin in double shear."
    )
    print(
        "NOT credited: Mx. The independent upper brace remains the Mx load path."
    )
    print()
    print(
        f"{'Pin d':>8}"
        f"{'tau_ult':>14}"
        f"{'MSu shear':>14}"
        f"{'p_nom hole':>16}"
        f"{'d_pin/d':>12}"
        f"{'Status':>12}"
    )
    print("-" * 80)

    for row in keeper_rows:
        status = (
            "PASS"
            if row["STATIC_PIN_PASS"]
            else "FAIL"
        )
        print(
            f"{row['keeper_pin_diameter_mm']:>7.0f} "
            f"{row['ultimate_double_shear_MPa']:>12.1f} "
            f"{row['MS_ultimate_pin_shear']:>12.3f} "
            f"{row['nominal_cross_hole_bearing_MPa']:>14.1f} "
            f"{row['pin_to_main_shaft_diameter_ratio']:>10.3f} "
            f"{status:>10}"
        )

    print()
    print(
        f"Working keeper pin:               "
        f"{WORKING_KEEPER_PIN_MM:.0f} mm 300M"
    )
    print(
        f"Ultimate pin double shear:        "
        f"{working_keeper['ultimate_double_shear_MPa']:.3f} MPa"
    )
    print(
        f"Ultimate pin shear margin:        "
        f"{working_keeper['MS_ultimate_pin_shear']:+.3f}"
    )
    print(
        "Keeper diameter is NOT frozen by this static screen. The cross-hole "
        "notch in the main shaft/head must be validated locally before finalizing."
    )

    print()
    print("B10 WORKING GEOMETRY RECORD")
    print(dash)
    print(f"Head OD:                          {HEAD_OD_MM:.1f} mm")
    print(f"Bearing-center span:              {WORKING_SPAN_MM:.1f} mm")
    print(f"300M cross-shaft diameter:        {WORKING_SHAFT_DIAMETER_MM:.1f} mm")
    print(f"Bearing width:                    {BEARING_WIDTH_MM:.1f} mm")
    print(f"Lower solid ligament:             {WORKING_LOWER_LIGAMENT_MM:.1f} mm")
    print(f"Upper solid ligament:             {WORKING_UPPER_LIGAMENT_MM:.1f} mm")
    print(f"Working solid-head height:        {solid_head_height_mm:.1f} mm")
    print(
        f"Trunnion center above U:          "
        f"{working['z_trunnion_above_U_mm']:.3f} mm"
    )
    print(f"Keeper pin:                       {WORKING_KEEPER_PIN_MM:.1f} mm")

    print()
    print("STATUS")
    print(dash)
    print(
        "B10 integrated static screen:     "
        + ("PASS" if working["PASS"] else "FAIL")
    )
    print(
        "Classification:                   "
        "PRELIMINARY INTEGRATION — NOT FINAL AIRFRAME FREEZE"
    )
    print(
        "Next: B11 local analytical head/bore/net-section/cross-hole checks, "
        "then B12 integrated local FEA."
    )

    # -------------------------------------------------------------------------
    # I. Text summary
    # -------------------------------------------------------------------------
    summary = []
    summary.append(line)
    summary.append(
        "PHASE 2E3-B10 — UPPER HEAD / 300M CROSS-TRUNNION INTEGRATION V0.1"
    )
    summary.append(line)
    summary.append("")
    summary.append(f"Load source: {load_source}")
    summary.append(
        f"E3 boundary: {e3_boundary_mm:.3f} mm above U | "
        f"source={e3_boundary_source}"
    )
    summary.append(
        f"Material source: {material_source}"
    )
    summary.append("")
    summary.append(
        "Decision chain: requirement -> equation/constraint -> trade -> "
        "working value -> validation status"
    )
    summary.append("")
    summary.append(
        f"Packaging minimum span = "
        f"{minimum_span_mm:.3f} mm."
    )
    summary.append(
        "120 mm rejected for geometric overlap with the 106 mm B9 head."
    )
    summary.append(
        "150 mm retained over 180 mm after recoupling the REAL "
        "head-face-to-bearing-center journal lever."
    )
    summary.append(
        f"Mathematical minimum shaft diameter at Kt=3: "
        f"{mathematical_minimum_diameter_mm:.0f} mm."
    )
    summary.append(
        f"Working shaft diameter: "
        f"{WORKING_SHAFT_DIAMETER_MM:.0f} mm."
    )
    summary.append(
        f"Working result: LC={working['ultimate_governing_case']}, "
        f"Rult={working['ultimate_Rgov_kN']:.3f} kN, "
        f"Mroot={working['ultimate_root_moment_kNm']:.3f} kN*m, "
        f"VMult={working['ultimate_vm_MPa']:.3f} MPa, "
        f"MSu={working['MS_ultimate']:+.3f}."
    )
    summary.append(
        f"Working keeper pin: {WORKING_KEEPER_PIN_MM:.0f} mm 300M; "
        f"ultimate double-shear stress="
        f"{working_keeper['ultimate_double_shear_MPa']:.3f} MPa; "
        f"MS={working_keeper['MS_ultimate_pin_shear']:+.3f}."
    )
    summary.append("")
    summary.append(
        "OPEN: head-bore bearing, head net section/shear-out, real shoulder "
        "fillet, keeper cross-hole SCF, contact/fretting, fits, fatigue, "
        "fracture mechanics and final airframe fitting."
    )

    summary_txt.write_text(
        "\n".join(summary) + "\n",
        encoding="utf-8",
    )

    print()
    print("OUTPUT FILES")
    print(dash)
    print(f"Span trade:                       {span_csv}")
    print(f"Shaft sweep:                      {shaft_csv}")
    print(f"Ligament sensitivity:            {ligament_csv}")
    print(f"Keeper-pin screen:               {keeper_csv}")
    print(f"Design record:                    {record_csv}")
    print(f"Summary:                          {summary_txt}")
    print(line)


if __name__ == "__main__":
    main()
