from pathlib import Path
import math
import numpy as np
import pandas as pd


# =============================================================================
# LANDING GEAR DESIGN PROJECT
# PHASE 2E1 — AXLE-TO-PISTON LOWER-END ARCHITECTURE V0.4
#
# PURPOSE
#   Develop and screen a physically realistic lower-end load path:
#
#       wheel/contact loads
#           -> hollow axle root
#           -> integral 300M lower knuckle / boss
#           -> 58 x 4 mm piston tube
#
#   IMPORTANT:
#   - Calculated loads are NOT copied from chat.
#   - Load components come from phase1_load_envelope.csv.
#   - Full-compression packaging reserve comes from phase2_packaging_overlap.csv.
#   - Locked Phase 2 Preliminary Design Baseline V1 dimensions remain unchanged.
#   - New lower-knuckle geometry below is a WORKING Phase 2E1 V0.1 candidate,
#     not yet part of the locked baseline.
# =============================================================================


# =============================================================================
# 1. FILE PATHS
# =============================================================================

HERE = Path(__file__).resolve().parent

# Project root is expected to be:
# Landing_Gear_Project/
#     phase1_loads/
#     phase2_structures/
#
# However, Phase 2E1 V0.2 does NOT require the source CSVs to be in those exact
# folders. The preferred locations below are tried first, then the script
# searches the project tree recursively for files with the required names.
PROJECT_ROOT = HERE.parent.resolve()

PHASE1_LOADS_PREFERRED = (
    PROJECT_ROOT / "phase1_loads" / "phase1_load_envelope.csv"
).resolve()

PACKAGING_PREFERRED = (
    HERE / "phase2_packaging_overlap.csv"
).resolve()

OUTPUT_CHECKS_CSV = (
    HERE / "phase2e1_lower_end_checks.csv"
).resolve()

OUTPUT_GEOMETRY_CSV = (
    HERE / "phase2e1_lower_end_geometry.csv"
).resolve()

OUTPUT_GEOMETRY_CHECKS_CSV = (
    HERE / "phase2e1_geometry_checks.csv"
).resolve()

OUTPUT_KT_SWEEP_CSV = (
    HERE / "phase2e1_kt_sweep.csv"
).resolve()

OUTPUT_KT_CAPACITY_CSV = (
    HERE / "phase2e1_kt_capacity.csv"
).resolve()


# =============================================================================
# 2. LOCKED BASELINE INPUTS
# =============================================================================

# Coordinate / load geometry
r_tire = 0.175                   # loaded tire radius [m]
wheel_offset_e = 0.120           # strut axis -> wheel centerplane [m]

# Piston: LOCKED Phase 2 baseline
D_piston_o = 0.058               # [m]
t_piston = 0.004                 # [m]
D_piston_i = D_piston_o - 2.0 * t_piston

# Axle root: LOCKED Phase 2 baseline
D_axle_o = 0.050                 # [m]
t_axle = 0.008                   # [m]
D_axle_i = D_axle_o - 2.0 * t_axle

# 300M material baseline
E_300M = 205.0e9                 # Young's modulus [Pa]
nu_300M = 0.28
rho_300M = 7870.0                # [kg/m^3]
Sy_300M = 1517.0e6               # yield strength [Pa]
Su_300M = 1862.0e6               # ultimate strength [Pa]


# =============================================================================
# 3. PHASE 2E1 V0.1 WORKING LOWER-END GEOMETRY — NOT YET LOCKED
# =============================================================================

# Architecture:
# One-piece forged / machined 300M lower piston-knuckle-axle component.
#
# The 50 mm piston internal bore is blind-ended ABOVE the axle branch.
# The 34 mm axle internal bore is blind-ended BEFORE the strut centerline.
# Therefore the two internal cavities do NOT intersect at the highly loaded node.

D_knuckle_max = 0.080            # max local knuckle width / OD envelope [m]

# Axle center A is z = 0.
# Keep the enlarged upper node short because the lower guide/bushing must still
# remain on the 58 mm piston surface at maximum physical stroke.
z_knuckle_upper = 0.030          # top of full-size local knuckle [m above A]
z_knuckle_lower = -0.040         # lower extent [m below A]

# Blend returns completely to the LOCKED 58 mm piston OD by this station.
z_transition_end = 0.050         # [m above A]
transition_length = z_transition_end - z_knuckle_upper

# Preliminary external blend radii
r_fillet_axle_knuckle = 0.010    # [m] working CAD/FEA start value
r_fillet_piston_blend = 0.008    # [m] working CAD/FEA start value

# Internal blind-end locations
# Piston bore ends 15 mm above the top of the 50 mm axle branch.
z_piston_bore_end = 0.040        # [m above A]

# Axle bore stops 12 mm outboard of the strut centerline.
y_axle_bore_end = 0.012          # [m from A toward wheel]

# Preliminary stress-concentration screening factor.
# This is NOT a substitute for detailed 3D FEA. It is a sensitivity screen only.
Kt_screen = 1.50

# Phase 2E1 robustness sweep. These are analytical sensitivity values only;
# the actual local Kt must ultimately come from the detailed 3D geometry / FEA.
Kt_sweep_values = [
    1.00,
    1.25,
    1.50,
    1.75,
    2.00,
    2.25,
    2.50,
    3.00,
]


# =============================================================================
# 4. SMALL UTILITIES
# =============================================================================

def normalize_column_name(name):
    """Lowercase alphanumeric-only column name for tolerant CSV lookup."""
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def circular_annulus_properties(D_o, D_i):
    """Return A, I, J, c for a circular annulus."""
    if D_o <= D_i:
        raise ValueError("Outer diameter must be greater than inner diameter.")

    A = math.pi / 4.0 * (D_o**2 - D_i**2)
    I = math.pi / 64.0 * (D_o**4 - D_i**4)
    J = math.pi / 32.0 * (D_o**4 - D_i**4)
    c = D_o / 2.0

    return A, I, J, c


def combined_vm(
    N,
    M_b,
    T,
    A,
    I,
    J,
    c,
    Kt_bending=1.0,
    Kt_torsion=1.0,
):
    """
    Phase-2-consistent nominal combined-stress model.

    sigma_max = |N|/A + Kt_b * M_b*c/I
    tau_T     = Kt_t * |T|*c/J
    sigma_VM  = sqrt(sigma_max^2 + 3*tau_T^2)

    Transverse shear is not added to the surface VM expression here, matching
    the previous preliminary piston/axle sizing convention.
    """

    sigma_axial = abs(N) / A
    sigma_bending = Kt_bending * abs(M_b) * c / I
    tau_torsion = Kt_torsion * abs(T) * c / J

    sigma_max = sigma_axial + sigma_bending

    sigma_vm = math.sqrt(
        sigma_max**2
        + 3.0 * tau_torsion**2
    )

    return {
        "sigma_axial_Pa": sigma_axial,
        "sigma_bending_Pa": sigma_bending,
        "tau_torsion_Pa": tau_torsion,
        "sigma_vm_Pa": sigma_vm,
    }


def external_transition_diameter(z):
    """
    Linearized external diameter through the Phase 2E1 V0.4 transition.

    z <= z_knuckle_upper:
        use full knuckle diameter.

    z >= z_transition_end:
        use locked piston OD.

    This is only the analytical packaging envelope. The eventual CAD transition
    should use smooth tangent blends / fillets rather than a sharp linear cone.
    """

    if z <= z_knuckle_upper:
        return D_knuckle_max

    if z >= z_transition_end:
        return D_piston_o

    fraction = (
        (z - z_knuckle_upper)
        / (z_transition_end - z_knuckle_upper)
    )

    return (
        D_knuckle_max
        + fraction * (D_piston_o - D_knuckle_max)
    )


def kt_to_allowable(
    sigma_axial,
    sigma_bending_nominal,
    tau_torsion_nominal,
    allowable,
):
    """
    Return the positive Kt at which the von Mises stress reaches allowable.

    Model:
        sigma_vm^2 =
            (sigma_axial + Kt*sigma_bending_nominal)^2
            + 3*(Kt*tau_torsion_nominal)^2

    This provides an analytical robustness threshold for the same preliminary
    stress model used in the Kt sweep.
    """

    if allowable <= 0.0:
        raise ValueError("Allowable stress must be positive.")

    if sigma_axial >= allowable:
        return 0.0

    a = (
        sigma_bending_nominal**2
        + 3.0 * tau_torsion_nominal**2
    )

    b = (
        2.0
        * sigma_axial
        * sigma_bending_nominal
    )

    c = (
        sigma_axial**2
        - allowable**2
    )

    if abs(a) < 1e-30:
        return math.inf

    discriminant = (
        b**2
        - 4.0 * a * c
    )

    if discriminant < 0.0:
        return math.nan

    root_1 = (
        -b
        + math.sqrt(discriminant)
    ) / (2.0 * a)

    root_2 = (
        -b
        - math.sqrt(discriminant)
    ) / (2.0 * a)

    positive_roots = [
        root
        for root in [root_1, root_2]
        if root >= 0.0
    ]

    if not positive_roots:
        return math.nan

    return min(positive_roots)


# =============================================================================
# 5. LOAD RESULTANTS
# =============================================================================

def piston_side_resultants(Fx, Fy, Fz, h):
    """
    Resultants on a piston/strut cut at height h above axle station A.

    Locked Phase 2B/2C convention:
        Nc = Fz
        Vx = Fx
        Vy = Fy
        Mx = e*Fz + (r_t + h)*Fy
        My = -(r_t + h)*Fx
        Tz = -e*Fx
        Mb = sqrt(Mx^2 + My^2)
    """

    Nc = Fz
    Vx = Fx
    Vy = Fy

    Mx = (
        wheel_offset_e * Fz
        + (r_tire + h) * Fy
    )

    My = -(
        r_tire + h
    ) * Fx

    Tz = -wheel_offset_e * Fx

    Mb = math.hypot(Mx, My)

    return {
        "N_N": Nc,
        "Vx_N": Vx,
        "Vy_N": Vy,
        "Mx_Nm": Mx,
        "My_Nm": My,
        "T_Nm": Tz,
        "Mb_Nm": Mb,
    }


def axle_resultants(Fx, Fy, Fz, lever_y, case_name):
    """
    Resultants on an axle cut.

    lever_y is cut -> wheel-centerplane lateral distance.

    Phase 2D8 convention is preserved:
        Ny = Fy
        Vx = Fx
        Vz = Fz
        Mx = lever_y*Fz + r_t*Fy
        Mz = -lever_y*Fx
        Mb = sqrt(Mx^2 + Mz^2)

    Baseline structural axle torsion:
        - LC5 brake torque is included.
        - LC2 geometric spin-up torque is reported as a sensitivity only and
          is NOT included in baseline structural torsion, preserving Phase 2D8.
    """

    Ny = Fy
    Vx = Fx
    Vz = Fz

    Mx = (
        lever_y * Fz
        + r_tire * Fy
    )

    Mz = -lever_y * Fx
    Mb = math.hypot(Mx, Mz)

    case_upper = str(case_name).upper()

    # Baseline structural torsion convention from Phase 2D8
    if case_upper.startswith("LC5"):
        T_struct = -r_tire * Fx
    else:
        T_struct = 0.0

    # Geometric torque sensitivity
    T_geom = -r_tire * Fx

    return {
        "N_N": Ny,
        "Vx_N": Vx,
        "Vz_N": Vz,
        "Mx_Nm": Mx,
        "Mz_Nm": Mz,
        "T_Nm": T_struct,
        "T_geom_Nm": T_geom,
        "Mb_Nm": Mb,
    }


# =============================================================================
# 6. SOURCE CSV READERS
# =============================================================================

def read_csv_flexible(path):
    """
    Read a CSV robustly.

    - Automatically detects comma / semicolon / tab delimiters.
    - Removes UTF-8 BOM characters and surrounding whitespace from headers.
    """
    df = pd.read_csv(
        path,
        sep=None,
        engine="python",
        encoding="utf-8-sig",
    )

    df.columns = [
        str(col).replace("\ufeff", "").strip()
        for col in df.columns
    ]

    return df


def candidate_source_paths(filename, preferred_path):
    """
    Return candidate source files in priority order.

    1. Preferred known project location.
    2. Same folder as this Phase 2E1 script.
    3. Anywhere below Landing_Gear_Project.
    """
    candidates = []

    def add(path):
        path = Path(path).resolve()
        if path.exists() and path.is_file() and path not in candidates:
            candidates.append(path)

    add(preferred_path)
    add(HERE / filename)

    for path in PROJECT_ROOT.rglob(filename):
        add(path)

    return candidates


def resolve_columns(df, alias_map):
    """
    Resolve required canonical fields from tolerant header aliases.

    Matching ignores case, spaces, underscores, hyphens, brackets, etc.
    """
    normalized_to_actual = {
        normalize_column_name(col): col
        for col in df.columns
    }

    resolved = {}
    missing = []

    for canonical, aliases in alias_map.items():

        found = None

        for alias in aliases:
            key = normalize_column_name(alias)

            if key in normalized_to_actual:
                found = normalized_to_actual[key]
                break

        if found is None:
            missing.append(canonical)
        else:
            resolved[canonical] = found

    return resolved, missing


def read_phase1_loads():
    """
    Locate and read the Phase 1 load envelope.

    The script deliberately obtains loads from the generated Phase 1 CSV rather
    than duplicating previously calculated load values.
    """

    aliases = {
        "Case": [
            "Case",
            "LoadCase",
            "Load_Case",
            "case_name",
            "load_case",
        ],
        "Fx_lim": [
            "Fx_lim",
            "Fx_limit",
            "FxLimit",
            "limit_Fx",
            "Fx_limit_kN",
        ],
        "Fy_lim": [
            "Fy_lim",
            "Fy_limit",
            "FyLimit",
            "limit_Fy",
            "Fy_limit_kN",
        ],
        "Fz_lim": [
            "Fz_lim",
            "Fz_limit",
            "FzLimit",
            "limit_Fz",
            "Fz_limit_kN",
        ],
        "Fx_ult": [
            "Fx_ult",
            "Fx_ultimate",
            "FxUltimate",
            "ultimate_Fx",
            "Fx_ultimate_kN",
        ],
        "Fy_ult": [
            "Fy_ult",
            "Fy_ultimate",
            "FyUltimate",
            "ultimate_Fy",
            "Fy_ultimate_kN",
        ],
        "Fz_ult": [
            "Fz_ult",
            "Fz_ultimate",
            "FzUltimate",
            "ultimate_Fz",
            "Fz_ultimate_kN",
        ],
    }

    candidates = candidate_source_paths(
        "phase1_load_envelope.csv",
        PHASE1_LOADS_PREFERRED,
    )

    if not candidates:
        raise FileNotFoundError(
            "Could not find phase1_load_envelope.csv anywhere below:\n"
            f"{PROJECT_ROOT}\n\n"
            "Expected preferred location:\n"
            f"{PHASE1_LOADS_PREFERRED}"
        )

    diagnostics = []

    for path in candidates:

        try:
            df = read_csv_flexible(path)
        except Exception as exc:
            diagnostics.append(
                f"{path} -> could not read: {exc}"
            )
            continue

        resolved, missing = resolve_columns(
            df,
            aliases,
        )

        if missing:
            diagnostics.append(
                f"{path} -> columns found: {df.columns.tolist()} "
                f"-> missing semantic fields: {missing}"
            )
            continue

        # Rename whatever valid header convention was found to the canonical
        # names used by the remainder of Phase 2E1.
        rename_map = {
            actual: canonical
            for canonical, actual in resolved.items()
        }

        df = df.rename(
            columns=rename_map
        )

        required = list(aliases.keys())

        # Make sure load columns are numeric before accepting the file.
        for col in required[1:]:
            df[col] = pd.to_numeric(
                df[col],
                errors="raise",
            )

        print("\nPHASE 1 SOURCE RESOLVED")
        print("-" * 110)
        print(f"File: {path}")
        print(
            "Columns: "
            + ", ".join(required)
        )

        return df, path

    message = (
        "A file named phase1_load_envelope.csv was found, but none of the "
        "candidates contained a compatible Phase 1 load-envelope schema.\n\n"
        "Candidates checked:\n  - "
        + "\n  - ".join(diagnostics)
    )

    raise ValueError(message)


def read_preferred_packaging_row():
    """
    Locate the Phase 2D packaging CSV and read the preferred
    hL / spacing / hU = 250 / 150 / 400 mm row.

    The exact Phase 2D CSV headers are resolved by semantic aliases so the
    Phase 2E1 script remains connected to the generated project output rather
    than duplicating previously calculated packaging values.
    """

    packaging_candidates = candidate_source_paths(
        "phase2_packaging_overlap.csv",
        PACKAGING_PREFERRED,
    )

    if not packaging_candidates:
        raise FileNotFoundError(
            "Could not find phase2_packaging_overlap.csv anywhere below:\n"
            f"{PROJECT_ROOT}\n\n"
            "Expected preferred location:\n"
            f"{PACKAGING_PREFERRED}"
        )

    aliases = {
        "hL_mm": [
            "hL_mm",
            "hL",
            "lower_height_mm",
            "lowerheightmm",
        ],
        "spacing_mm": [
            "spacing_mm",
            "spacing",
            "b_mm",
            "b",
            "bushing_spacing_mm",
        ],
        "hU_mm": [
            "hU_mm",
            "hU",
            "upper_height_mm",
            "upperheightmm",
        ],
        "physical_reserve_mm": [
            "physical_lower_surface_reserve_mm",
            "physical_lower_surface_reserve",
            "physical_reserve_mm",
            "physical_reserve",
            "phys_res_mm",
            "phys_res",
            "PhysRes",
        ],
        "virtual_reserve_mm": [
            "virtual_lower_surface_reserve_mm",
            "virtual_lower_surface_reserve",
            "virtual_reserve_mm",
            "virtual_reserve",
            "virt_res_mm",
            "virt_res",
            "VirtRes",
        ],
    }

    diagnostics = []

    for packaging_path in packaging_candidates:

        try:
            df = read_csv_flexible(packaging_path)
        except Exception as exc:
            diagnostics.append(
                f"{packaging_path} -> could not read: {exc}"
            )
            continue

        resolved, missing = resolve_columns(
            df,
            aliases,
        )

        # Virtual reserve is useful but diagnostic only, so it is optional.
        required_fields = [
            "hL_mm",
            "spacing_mm",
            "hU_mm",
            "physical_reserve_mm",
        ]

        required_missing = [
            field for field in required_fields
            if field not in resolved
        ]

        if required_missing:
            diagnostics.append(
                f"{packaging_path} -> columns found: {df.columns.tolist()} "
                f"-> missing semantic fields: {required_missing}"
            )
            continue

        col_hL = resolved["hL_mm"]
        col_spacing = resolved["spacing_mm"]
        col_hU = resolved["hU_mm"]
        col_phys = resolved["physical_reserve_mm"]

        hL_values = pd.to_numeric(
            df[col_hL],
            errors="coerce",
        )

        spacing_values = pd.to_numeric(
            df[col_spacing],
            errors="coerce",
        )

        hU_values = pd.to_numeric(
            df[col_hU],
            errors="coerce",
        )

        mask = (
            np.isclose(hL_values, 250.0)
            & np.isclose(spacing_values, 150.0)
            & np.isclose(hU_values, 400.0)
        )

        selected = df.loc[mask]

        if selected.empty:
            diagnostics.append(
                f"{packaging_path} -> compatible columns found, but no "
                "250 / 150 / 400 mm preferred row exists."
            )
            continue

        row = selected.iloc[0]

        phys_res_mm = float(
            pd.to_numeric(
                pd.Series([row[col_phys]]),
                errors="raise",
            ).iloc[0]
        )

        phys_res_m = phys_res_mm / 1000.0

        virt_res_m = None

        if "virtual_reserve_mm" in resolved:
            col_virt = resolved["virtual_reserve_mm"]

            virt_res_mm = float(
                pd.to_numeric(
                    pd.Series([row[col_virt]]),
                    errors="raise",
                ).iloc[0]
            )

            virt_res_m = virt_res_mm / 1000.0

        print("\nPHASE 2D PACKAGING SOURCE RESOLVED")
        print("-" * 110)
        print(f"File: {packaging_path}")
        print(f"hL column:                  {col_hL}")
        print(f"Spacing column:             {col_spacing}")
        print(f"hU column:                  {col_hU}")
        print(f"Physical reserve column:    {col_phys}")

        if "virtual_reserve_mm" in resolved:
            print(
                f"Virtual reserve column:     "
                f"{resolved['virtual_reserve_mm']}"
            )

        return {
            "row": row,
            "physical_reserve_m": phys_res_m,
            "virtual_reserve_m": virt_res_m,
            "source_path": packaging_path,
        }

    message = (
        "A phase2_packaging_overlap.csv file was found, but no candidate "
        "contained both a compatible packaging schema and the preferred "
        "250 / 150 / 400 mm row.\n\nCandidates checked:\n  - "
        + "\n  - ".join(diagnostics)
    )

    raise ValueError(message)


# =============================================================================
# 7. ANALYSIS
# =============================================================================

def main():

    loads, phase1_source_path = read_phase1_loads()
    packaging = read_preferred_packaging_row()
    packaging_source_path = packaging["source_path"]

    physical_guide_reserve = packaging["physical_reserve_m"]
    virtual_guide_reserve = packaging["virtual_reserve_m"]

    # -------------------------------------------------------------------------
    # Derived geometry
    # -------------------------------------------------------------------------

    axle_exposed_length = (
        wheel_offset_e
        - D_knuckle_max / 2.0
    )

    if axle_exposed_length <= 0.0:
        raise ValueError(
            "Working knuckle envelope reaches or passes the wheel centerplane."
        )

    physical_clearance = (
        physical_guide_reserve
        - z_transition_end
    )

    virtual_clearance = None

    if virtual_guide_reserve is not None:
        virtual_clearance = (
            virtual_guide_reserve
            - z_transition_end
        )

    radial_step = (
        D_knuckle_max
        - D_piston_o
    ) / 2.0

    material_above_axle = (
        z_knuckle_upper
        - D_axle_o / 2.0
    )

    piston_internal_web = (
        z_piston_bore_end
        - D_axle_o / 2.0
    )

    # Axle bore is blind-ended y_axle_bore_end outboard of A, leaving a solid
    # axial bridge between the bore end and strut centerline.
    axle_bore_solid_bridge = y_axle_bore_end

    # External transition diameter and radial wall at the piston-bore blind end.
    D_transition_at_bore_end = external_transition_diameter(
        z_piston_bore_end
    )

    radial_wall_at_bore_end = (
        D_transition_at_bore_end
        - D_piston_i
    ) / 2.0

    # Minimum wall in the bored portion of the transition occurs where the
    # geometry returns to the locked 58 x 4 mm piston tube.
    min_transition_radial_wall = (
        D_piston_o
        - D_piston_i
    ) / 2.0

    transition_half_angle_deg = math.degrees(
        math.atan2(
            radial_step,
            transition_length,
        )
    )

    # -------------------------------------------------------------------------
    # Section properties
    # -------------------------------------------------------------------------

    A_axle, I_axle, J_axle, c_axle = circular_annulus_properties(
        D_axle_o,
        D_axle_i,
    )

    A_piston, I_piston, J_piston, c_piston = circular_annulus_properties(
        D_piston_o,
        D_piston_i,
    )

    A_knuckle, I_knuckle, J_knuckle, c_knuckle = circular_annulus_properties(
        D_knuckle_max,
        D_piston_i,
    )

    records = []

    # -------------------------------------------------------------------------
    # Load-loop
    # -------------------------------------------------------------------------

    for _, row in loads.iterrows():

        case_name = str(row["Case"])

        for level in ["limit", "ultimate"]:

            if level == "limit":
                Fx = float(row["Fx_lim"]) * 1e3
                Fy = float(row["Fy_lim"]) * 1e3
                Fz = float(row["Fz_lim"]) * 1e3
                allowable = Sy_300M
            else:
                Fx = float(row["Fx_ult"]) * 1e3
                Fy = float(row["Fy_ult"]) * 1e3
                Fz = float(row["Fz_ult"]) * 1e3
                allowable = Su_300M

            # =================================================================
            # CHECK 1 — LOCKED AXLE ROOT AT STRUCTURAL DATUM A
            # Regression of Phase 2D8 load/stress convention.
            # =================================================================

            axle_A = axle_resultants(
                Fx,
                Fy,
                Fz,
                wheel_offset_e,
                case_name,
            )

            stress_A = combined_vm(
                axle_A["N_N"],
                axle_A["Mb_Nm"],
                axle_A["T_Nm"],
                A_axle,
                I_axle,
                J_axle,
                c_axle,
            )

            # LC2 geometric spin-up torque sensitivity
            stress_A_sens = combined_vm(
                axle_A["N_N"],
                axle_A["Mb_Nm"],
                axle_A["T_geom_Nm"],
                A_axle,
                I_axle,
                J_axle,
                c_axle,
            )

            records.append({
                "check": "AXLE_A_BASELINE_REGRESSION",
                "case": case_name,
                "load_level": level,
                "station_m": 0.0,
                "lever_y_m": wheel_offset_e,
                "Kt": 1.0,
                "N_kN": axle_A["N_N"] / 1e3,
                "Mb_kNm": axle_A["Mb_Nm"] / 1e3,
                "T_struct_kNm": axle_A["T_Nm"] / 1e3,
                "T_geom_kNm": axle_A["T_geom_Nm"] / 1e3,
                "sigma_axial_MPa": stress_A["sigma_axial_Pa"] / 1e6,
                "sigma_bending_MPa": stress_A["sigma_bending_Pa"] / 1e6,
                "tau_torsion_MPa": stress_A["tau_torsion_Pa"] / 1e6,
                "vm_MPa": stress_A["sigma_vm_Pa"] / 1e6,
                "vm_geom_torsion_sens_MPa": (
                    stress_A_sens["sigma_vm_Pa"] / 1e6
                ),
                "allowable_MPa": allowable / 1e6,
                "MS": allowable / stress_A["sigma_vm_Pa"] - 1.0,
                "status": (
                    "PASS"
                    if stress_A["sigma_vm_Pa"] <= allowable
                    else "FAIL"
                ),
            })

            # =================================================================
            # CHECK 2 — PHYSICAL AXLE SECTION AT OUTBOARD KNUCKLE FACE
            # Uses the shortened physical lever generated by the new knuckle.
            # Apply Kt_screen as a preliminary local branch sensitivity.
            # =================================================================

            axle_face = axle_resultants(
                Fx,
                Fy,
                Fz,
                axle_exposed_length,
                case_name,
            )

            stress_face = combined_vm(
                axle_face["N_N"],
                axle_face["Mb_Nm"],
                axle_face["T_Nm"],
                A_axle,
                I_axle,
                J_axle,
                c_axle,
                Kt_bending=Kt_screen,
                Kt_torsion=Kt_screen,
            )

            stress_face_sens = combined_vm(
                axle_face["N_N"],
                axle_face["Mb_Nm"],
                axle_face["T_geom_Nm"],
                A_axle,
                I_axle,
                J_axle,
                c_axle,
                Kt_bending=Kt_screen,
                Kt_torsion=Kt_screen,
            )

            records.append({
                "check": "AXLE_KNUCKLE_FACE_KT_SCREEN",
                "case": case_name,
                "load_level": level,
                "station_m": 0.0,
                "lever_y_m": axle_exposed_length,
                "Kt": Kt_screen,
                "N_kN": axle_face["N_N"] / 1e3,
                "Mb_kNm": axle_face["Mb_Nm"] / 1e3,
                "T_struct_kNm": axle_face["T_Nm"] / 1e3,
                "T_geom_kNm": axle_face["T_geom_Nm"] / 1e3,
                "sigma_axial_MPa": stress_face["sigma_axial_Pa"] / 1e6,
                "sigma_bending_MPa": stress_face["sigma_bending_Pa"] / 1e6,
                "tau_torsion_MPa": stress_face["tau_torsion_Pa"] / 1e6,
                "vm_MPa": stress_face["sigma_vm_Pa"] / 1e6,
                "vm_geom_torsion_sens_MPa": (
                    stress_face_sens["sigma_vm_Pa"] / 1e6
                ),
                "allowable_MPa": allowable / 1e6,
                "MS": allowable / stress_face["sigma_vm_Pa"] - 1.0,
                "status": (
                    "PASS"
                    if stress_face["sigma_vm_Pa"] <= allowable
                    else "FAIL"
                ),
            })

            # =================================================================
            # CHECK 3 — LARGE END OF PISTON/KNUCKLE TRANSITION
            # Conservative annulus model: Do = 80 mm, Di = 50 mm.
            # =================================================================

            node_big = piston_side_resultants(
                Fx,
                Fy,
                Fz,
                z_knuckle_upper,
            )

            stress_node_big = combined_vm(
                node_big["N_N"],
                node_big["Mb_Nm"],
                node_big["T_Nm"],
                A_knuckle,
                I_knuckle,
                J_knuckle,
                c_knuckle,
                Kt_bending=Kt_screen,
                Kt_torsion=Kt_screen,
            )

            records.append({
                "check": "KNUCKLE_BIG_END_KT_SCREEN",
                "case": case_name,
                "load_level": level,
                "station_m": z_knuckle_upper,
                "lever_y_m": np.nan,
                "Kt": Kt_screen,
                "N_kN": node_big["N_N"] / 1e3,
                "Mb_kNm": node_big["Mb_Nm"] / 1e3,
                "T_struct_kNm": node_big["T_Nm"] / 1e3,
                "T_geom_kNm": np.nan,
                "sigma_axial_MPa": (
                    stress_node_big["sigma_axial_Pa"] / 1e6
                ),
                "sigma_bending_MPa": (
                    stress_node_big["sigma_bending_Pa"] / 1e6
                ),
                "tau_torsion_MPa": (
                    stress_node_big["tau_torsion_Pa"] / 1e6
                ),
                "vm_MPa": stress_node_big["sigma_vm_Pa"] / 1e6,
                "vm_geom_torsion_sens_MPa": np.nan,
                "allowable_MPa": allowable / 1e6,
                "MS": (
                    allowable / stress_node_big["sigma_vm_Pa"]
                    - 1.0
                ),
                "status": (
                    "PASS"
                    if stress_node_big["sigma_vm_Pa"] <= allowable
                    else "FAIL"
                ),
            })

            # =================================================================
            # CHECK 4 — SMALL END WHERE 58 x 4 mm SLIDING PISTON IS RESTORED
            # This is the more important analytical screen before 3D FEA.
            # =================================================================

            piston_small = piston_side_resultants(
                Fx,
                Fy,
                Fz,
                z_transition_end,
            )

            stress_piston_small = combined_vm(
                piston_small["N_N"],
                piston_small["Mb_Nm"],
                piston_small["T_Nm"],
                A_piston,
                I_piston,
                J_piston,
                c_piston,
                Kt_bending=Kt_screen,
                Kt_torsion=Kt_screen,
            )

            records.append({
                "check": "PISTON_SMALL_END_KT_SCREEN",
                "case": case_name,
                "load_level": level,
                "station_m": z_transition_end,
                "lever_y_m": np.nan,
                "Kt": Kt_screen,
                "N_kN": piston_small["N_N"] / 1e3,
                "Mb_kNm": piston_small["Mb_Nm"] / 1e3,
                "T_struct_kNm": piston_small["T_Nm"] / 1e3,
                "T_geom_kNm": np.nan,
                "sigma_axial_MPa": (
                    stress_piston_small["sigma_axial_Pa"] / 1e6
                ),
                "sigma_bending_MPa": (
                    stress_piston_small["sigma_bending_Pa"] / 1e6
                ),
                "tau_torsion_MPa": (
                    stress_piston_small["tau_torsion_Pa"] / 1e6
                ),
                "vm_MPa": stress_piston_small["sigma_vm_Pa"] / 1e6,
                "vm_geom_torsion_sens_MPa": np.nan,
                "allowable_MPa": allowable / 1e6,
                "MS": (
                    allowable / stress_piston_small["sigma_vm_Pa"]
                    - 1.0
                ),
                "status": (
                    "PASS"
                    if stress_piston_small["sigma_vm_Pa"] <= allowable
                    else "FAIL"
                ),
            })

            # =================================================================
            # SERVICEABILITY REPORT — EXPOSED AXLE DEFLECTION
            # No pass/fail limit is imposed yet.
            # =================================================================

            L = axle_exposed_length

            # Bending about x: vertical wheel load plus end couple from side load.
            Mx_end_from_side = r_tire * Fy

            delta_z = (
                Fz * L**3 / (3.0 * E_300M * I_axle)
                + Mx_end_from_side * L**2 / (2.0 * E_300M * I_axle)
            )

            # Bending about z from longitudinal force.
            delta_x = (
                Fx * L**3
                / (3.0 * E_300M * I_axle)
            )

            records.append({
                "check": "AXLE_WHEEL_CENTER_DEFLECTION_REPORT",
                "case": case_name,
                "load_level": level,
                "station_m": 0.0,
                "lever_y_m": L,
                "Kt": np.nan,
                "N_kN": Fy / 1e3,
                "Mb_kNm": np.nan,
                "T_struct_kNm": np.nan,
                "T_geom_kNm": np.nan,
                "sigma_axial_MPa": np.nan,
                "sigma_bending_MPa": np.nan,
                "tau_torsion_MPa": np.nan,
                "vm_MPa": np.nan,
                "vm_geom_torsion_sens_MPa": np.nan,
                "allowable_MPa": np.nan,
                "MS": np.nan,
                "status": "REPORT",
                "delta_x_mm": delta_x * 1e3,
                "delta_z_mm": delta_z * 1e3,
                "delta_resultant_mm": math.hypot(
                    delta_x,
                    delta_z,
                ) * 1e3,
            })

    results = pd.DataFrame(records)

    # Ensure deflection columns exist for every row.
    for col in [
        "delta_x_mm",
        "delta_z_mm",
        "delta_resultant_mm",
    ]:
        if col not in results.columns:
            results[col] = np.nan

    results.to_csv(
        OUTPUT_CHECKS_CSV,
        index=False,
    )

    # -------------------------------------------------------------------------
    # Kt ROBUSTNESS SWEEP + ANALYTICAL Kt CAPACITY
    # -------------------------------------------------------------------------

    kt_sweep_records = []
    kt_capacity_records = []

    for _, row in loads.iterrows():

        case_name = str(row["Case"])

        for level in ["limit", "ultimate"]:

            if level == "limit":
                Fx = float(row["Fx_lim"]) * 1e3
                Fy = float(row["Fy_lim"]) * 1e3
                Fz = float(row["Fz_lim"]) * 1e3
                allowable = Sy_300M
            else:
                Fx = float(row["Fx_ult"]) * 1e3
                Fy = float(row["Fy_ult"]) * 1e3
                Fz = float(row["Fz_ult"]) * 1e3
                allowable = Su_300M

            local_sections = []

            # Axle at the physical outboard knuckle face
            axle_face = axle_resultants(
                Fx,
                Fy,
                Fz,
                axle_exposed_length,
                case_name,
            )

            local_sections.append({
                "check": "AXLE_KNUCKLE_FACE",
                "N": axle_face["N_N"],
                "Mb": axle_face["Mb_Nm"],
                "T": axle_face["T_Nm"],
                "A": A_axle,
                "I": I_axle,
                "J": J_axle,
                "c": c_axle,
            })

            # Large end of the 80 -> 58 mm transition
            node_big = piston_side_resultants(
                Fx,
                Fy,
                Fz,
                z_knuckle_upper,
            )

            local_sections.append({
                "check": "KNUCKLE_BIG_END",
                "N": node_big["N_N"],
                "Mb": node_big["Mb_Nm"],
                "T": node_big["T_Nm"],
                "A": A_knuckle,
                "I": I_knuckle,
                "J": J_knuckle,
                "c": c_knuckle,
            })

            # Small end where the locked 58 x 4 mm piston is restored
            piston_small = piston_side_resultants(
                Fx,
                Fy,
                Fz,
                z_transition_end,
            )

            local_sections.append({
                "check": "PISTON_SMALL_END",
                "N": piston_small["N_N"],
                "Mb": piston_small["Mb_Nm"],
                "T": piston_small["T_Nm"],
                "A": A_piston,
                "I": I_piston,
                "J": J_piston,
                "c": c_piston,
            })

            for section in local_sections:

                nominal = combined_vm(
                    section["N"],
                    section["Mb"],
                    section["T"],
                    section["A"],
                    section["I"],
                    section["J"],
                    section["c"],
                    Kt_bending=1.0,
                    Kt_torsion=1.0,
                )

                kt_failure = kt_to_allowable(
                    nominal["sigma_axial_Pa"],
                    nominal["sigma_bending_Pa"],
                    nominal["tau_torsion_Pa"],
                    allowable,
                )

                kt_capacity_records.append({
                    "check": section["check"],
                    "case": case_name,
                    "load_level": level,
                    "Kt_to_allowable": kt_failure,
                    "Kt_screen": Kt_screen,
                    "Kt_capacity_ratio_vs_screen": (
                        kt_failure / Kt_screen
                        if np.isfinite(kt_failure)
                        else math.inf
                    ),
                    "allowable_MPa": allowable / 1e6,
                    "sigma_axial_nominal_MPa": (
                        nominal["sigma_axial_Pa"] / 1e6
                    ),
                    "sigma_bending_nominal_MPa": (
                        nominal["sigma_bending_Pa"] / 1e6
                    ),
                    "tau_torsion_nominal_MPa": (
                        nominal["tau_torsion_Pa"] / 1e6
                    ),
                })

                for Kt_value in Kt_sweep_values:

                    stress = combined_vm(
                        section["N"],
                        section["Mb"],
                        section["T"],
                        section["A"],
                        section["I"],
                        section["J"],
                        section["c"],
                        Kt_bending=Kt_value,
                        Kt_torsion=Kt_value,
                    )

                    kt_sweep_records.append({
                        "check": section["check"],
                        "case": case_name,
                        "load_level": level,
                        "Kt": Kt_value,
                        "vm_MPa": stress["sigma_vm_Pa"] / 1e6,
                        "allowable_MPa": allowable / 1e6,
                        "MS": (
                            allowable / stress["sigma_vm_Pa"]
                            - 1.0
                        ),
                        "status": (
                            "PASS"
                            if stress["sigma_vm_Pa"] <= allowable
                            else "FAIL"
                        ),
                    })

    kt_sweep_df = pd.DataFrame(
        kt_sweep_records
    )

    kt_capacity_df = pd.DataFrame(
        kt_capacity_records
    )

    kt_sweep_df.to_csv(
        OUTPUT_KT_SWEEP_CSV,
        index=False,
    )

    kt_capacity_df.to_csv(
        OUTPUT_KT_CAPACITY_CSV,
        index=False,
    )

    governing_kt_capacity = (
        kt_capacity_df
        .sort_values(
            "Kt_to_allowable",
            ascending=True,
        )
        .groupby(
            ["check", "load_level"],
            as_index=False,
        )
        .first()
    )

    # Governing result at each explicit Kt sweep value.
    governing_kt_sweep = (
        kt_sweep_df
        .sort_values(
            "vm_MPa",
            ascending=False,
        )
        .groupby(
            ["check", "load_level", "Kt"],
            as_index=False,
        )
        .first()
    )

    # -------------------------------------------------------------------------
    # GEOMETRIC NON-INTERSECTION / LIGAMENT CHECKS
    #
    # These checks verify that the candidate architecture has positive material
    # separation. They are NOT standalone strength allowables.
    # -------------------------------------------------------------------------

    geometry_check_rows = [
        {
            "check": "PHYSICAL_BUSHING_CLEARANCE",
            "value_mm": physical_clearance * 1e3,
            "criterion": "> 0 mm",
            "status": (
                "PASS_GEOMETRIC"
                if physical_clearance > 0.0
                else "FAIL_GEOMETRIC"
            ),
            "note": (
                "Transition must finish below the lower-guide surface reserve "
                "at full physical stroke."
            ),
        },
        {
            "check": "PISTON_BORE_TO_AXLE_OD_AXIAL_WEB",
            "value_mm": piston_internal_web * 1e3,
            "criterion": "> 0 mm",
            "status": (
                "PASS_GEOMETRIC"
                if piston_internal_web > 0.0
                else "FAIL_GEOMETRIC"
            ),
            "note": (
                "Positive axial solid web between the piston blind-bore end "
                "and the top of the 50 mm axle branch."
            ),
        },
        {
            "check": "AXLE_BORE_TO_STRUT_CENTERLINE_SOLID_BRIDGE",
            "value_mm": axle_bore_solid_bridge * 1e3,
            "criterion": "> 0 mm",
            "status": (
                "PASS_GEOMETRIC"
                if axle_bore_solid_bridge > 0.0
                else "FAIL_GEOMETRIC"
            ),
            "note": (
                "Positive solid axial bridge between axle blind-bore end "
                "and strut centerline A."
            ),
        },
        {
            "check": "RADIAL_WALL_AT_PISTON_BORE_BLIND_END",
            "value_mm": radial_wall_at_bore_end * 1e3,
            "criterion": "> 0 mm",
            "status": (
                "PASS_GEOMETRIC"
                if radial_wall_at_bore_end > 0.0
                else "FAIL_GEOMETRIC"
            ),
            "note": (
                "Radial material between 50 mm piston bore and local "
                "external transition envelope at z = piston blind-bore end."
            ),
        },
        {
            "check": "MIN_BORED_TRANSITION_RADIAL_WALL",
            "value_mm": min_transition_radial_wall * 1e3,
            "criterion": "> 0 mm",
            "status": (
                "PASS_GEOMETRIC"
                if min_transition_radial_wall > 0.0
                else "FAIL_GEOMETRIC"
            ),
            "note": (
                "Minimum radial wall in the bored transition; occurs at the "
                "restored locked 58 x 4 mm piston section."
            ),
        },
    ]

    geometry_checks = pd.DataFrame(
        geometry_check_rows
    )

    geometry_checks.to_csv(
        OUTPUT_GEOMETRY_CHECKS_CSV,
        index=False,
    )

    # -------------------------------------------------------------------------
    # Geometry / packaging documentation
    # -------------------------------------------------------------------------

    geometry_rows = [
        {
            "parameter": "piston_OD",
            "value": D_piston_o * 1e3,
            "units": "mm",
            "classification": "LOCKED_BASELINE",
        },
        {
            "parameter": "piston_wall",
            "value": t_piston * 1e3,
            "units": "mm",
            "classification": "LOCKED_BASELINE",
        },
        {
            "parameter": "piston_ID",
            "value": D_piston_i * 1e3,
            "units": "mm",
            "classification": "DERIVED_LOCKED_BASELINE",
        },
        {
            "parameter": "axle_root_OD",
            "value": D_axle_o * 1e3,
            "units": "mm",
            "classification": "LOCKED_BASELINE",
        },
        {
            "parameter": "axle_root_wall",
            "value": t_axle * 1e3,
            "units": "mm",
            "classification": "LOCKED_BASELINE",
        },
        {
            "parameter": "axle_root_ID",
            "value": D_axle_i * 1e3,
            "units": "mm",
            "classification": "DERIVED_LOCKED_BASELINE",
        },
        {
            "parameter": "wheel_offset_e",
            "value": wheel_offset_e * 1e3,
            "units": "mm",
            "classification": "LOCKED_BASELINE",
        },
        {
            "parameter": "knuckle_max_envelope",
            "value": D_knuckle_max * 1e3,
            "units": "mm",
            "classification": "PHASE2E1_WORKING",
        },
        {
            "parameter": "knuckle_upper_extent",
            "value": z_knuckle_upper * 1e3,
            "units": "mm above A",
            "classification": "PHASE2E1_WORKING",
        },
        {
            "parameter": "knuckle_lower_extent",
            "value": abs(z_knuckle_lower) * 1e3,
            "units": "mm below A",
            "classification": "PHASE2E1_WORKING",
        },
        {
            "parameter": "transition_end",
            "value": z_transition_end * 1e3,
            "units": "mm above A",
            "classification": "PHASE2E1_WORKING",
        },
        {
            "parameter": "transition_length",
            "value": transition_length * 1e3,
            "units": "mm",
            "classification": "PHASE2E1_WORKING",
        },
        {
            "parameter": "axle_knuckle_fillet",
            "value": r_fillet_axle_knuckle * 1e3,
            "units": "mm",
            "classification": "PHASE2E1_WORKING",
        },
        {
            "parameter": "piston_blend_fillet",
            "value": r_fillet_piston_blend * 1e3,
            "units": "mm",
            "classification": "PHASE2E1_WORKING",
        },
        {
            "parameter": "piston_bore_blind_end",
            "value": z_piston_bore_end * 1e3,
            "units": "mm above A",
            "classification": "PHASE2E1_WORKING",
        },
        {
            "parameter": "axle_bore_blind_end",
            "value": y_axle_bore_end * 1e3,
            "units": "mm outboard of A",
            "classification": "PHASE2E1_WORKING",
        },
        {
            "parameter": "exposed_axle_to_wheel_center",
            "value": axle_exposed_length * 1e3,
            "units": "mm",
            "classification": "DERIVED_PHASE2E1",
        },
        {
            "parameter": "knuckle_radial_step_over_piston",
            "value": radial_step * 1e3,
            "units": "mm per side",
            "classification": "DERIVED_PHASE2E1",
        },
        {
            "parameter": "material_above_axle_OD_before_blend",
            "value": material_above_axle * 1e3,
            "units": "mm",
            "classification": "DERIVED_PHASE2E1",
        },
        {
            "parameter": "piston_bore_to_axle_OD_web",
            "value": piston_internal_web * 1e3,
            "units": "mm",
            "classification": "DERIVED_PHASE2E1",
        },
        {
            "parameter": "axle_bore_solid_bridge",
            "value": axle_bore_solid_bridge * 1e3,
            "units": "mm",
            "classification": "DERIVED_PHASE2E1",
        },
        {
            "parameter": "transition_OD_at_piston_bore_end",
            "value": D_transition_at_bore_end * 1e3,
            "units": "mm",
            "classification": "DERIVED_PHASE2E1",
        },
        {
            "parameter": "radial_wall_at_piston_bore_end",
            "value": radial_wall_at_bore_end * 1e3,
            "units": "mm",
            "classification": "DERIVED_PHASE2E1",
        },
        {
            "parameter": "min_bored_transition_radial_wall",
            "value": min_transition_radial_wall * 1e3,
            "units": "mm",
            "classification": "DERIVED_PHASE2E1",
        },
        {
            "parameter": "transition_half_angle",
            "value": transition_half_angle_deg,
            "units": "deg",
            "classification": "DERIVED_PHASE2E1_ANALYTICAL_ENVELOPE",
        },
        {
            "parameter": "physical_guide_reserve_from_D4",
            "value": physical_guide_reserve * 1e3,
            "units": "mm",
            "classification": "SOURCE_CSV",
        },
        {
            "parameter": "physical_clearance_to_lower_bushing",
            "value": physical_clearance * 1e3,
            "units": "mm",
            "classification": "DERIVED_PHASE2E1",
        },
        {
            "parameter": "Kt_screen",
            "value": Kt_screen,
            "units": "-",
            "classification": "PHASE2E1_SCREENING",
        },
    ]

    if virtual_guide_reserve is not None:
        geometry_rows.extend([
            {
                "parameter": "virtual_guide_reserve_from_D4",
                "value": virtual_guide_reserve * 1e3,
                "units": "mm",
                "classification": "SOURCE_CSV_DIAGNOSTIC",
            },
            {
                "parameter": "virtual_clearance_to_lower_bushing",
                "value": virtual_clearance * 1e3,
                "units": "mm",
                "classification": "DIAGNOSTIC_ONLY",
            },
        ])

    geometry = pd.DataFrame(geometry_rows)

    geometry.to_csv(
        OUTPUT_GEOMETRY_CSV,
        index=False,
    )

    # -------------------------------------------------------------------------
    # Governing table
    # -------------------------------------------------------------------------

    stress_results = results[
        results["vm_MPa"].notna()
    ].copy()

    governing = (
        stress_results
        .sort_values("vm_MPa", ascending=False)
        .groupby(
            ["check", "load_level"],
            as_index=False,
        )
        .first()
    )

    # -------------------------------------------------------------------------
    # Console report
    # -------------------------------------------------------------------------

    print("=" * 110)
    print(" PHASE 2E1 — AXLE-TO-PISTON LOWER-END ARCHITECTURE V0.4")
    print("=" * 110)

    print("\nSOURCE FILES")
    print("-" * 110)
    print(f"Phase 1 loads:              {phase1_source_path}")
    print(f"Phase 2D packaging:         {packaging_source_path}")

    print("\nLOCKED BASELINE PRESERVED")
    print("-" * 110)
    print(
        f"Piston:                     "
        f"{D_piston_o*1e3:.1f} x {t_piston*1e3:.1f} mm"
    )
    print(
        f"Axle root:                  "
        f"{D_axle_o*1e3:.1f} x {t_axle*1e3:.1f} mm"
    )
    print(
        f"Wheel offset e:             "
        f"{wheel_offset_e*1e3:.1f} mm"
    )
    print("Material:                   300M steel")

    print("\nPHASE 2E1 WORKING ARCHITECTURE")
    print("-" * 110)
    print(
        f"Integral knuckle envelope:  "
        f"{D_knuckle_max*1e3:.1f} mm max"
    )
    print(
        f"Full-size node upper extent:"
        f" {z_knuckle_upper*1e3:.1f} mm above A"
    )
    print(
        f"58 mm piston restored by:   "
        f"{z_transition_end*1e3:.1f} mm above A"
    )
    print(
        f"Exposed axle to wheel ctr:  "
        f"{axle_exposed_length*1e3:.1f} mm"
    )
    print(
        f"Piston bore blind end:      "
        f"{z_piston_bore_end*1e3:.1f} mm above A"
    )
    print(
        f"Axle bore blind end:        "
        f"{y_axle_bore_end*1e3:.1f} mm outboard of A"
    )
    print(
        f"Local Kt screening factor:  "
        f"{Kt_screen:.2f}"
    )

    print("\nPACKAGING CHECK")
    print("-" * 110)
    print(
        f"Physical guide reserve read from D4 CSV: "
        f"{physical_guide_reserve*1e3:.3f} mm"
    )
    print(
        f"Transition ends above A at:             "
        f"{z_transition_end*1e3:.3f} mm"
    )
    print(
        f"Physical clearance remaining:           "
        f"{physical_clearance*1e3:+.3f} mm"
    )

    if physical_clearance > 0.0:
        print("Physical-stroke knuckle/bushing clearance: PASS")
    else:
        print("Physical-stroke knuckle/bushing clearance: FAIL")

    if virtual_clearance is not None:
        print(
            f"Virtual-stroke diagnostic clearance:     "
            f"{virtual_clearance*1e3:+.3f} mm"
        )
        print(
            "NOTE: virtual-stroke clearance is diagnostic only; "
            "the physical design stroke remains authoritative."
        )

    print("\nGOVERNING STRESS CHECKS")
    print("-" * 110)

    display_cols = [
        "check",
        "load_level",
        "case",
        "vm_MPa",
        "allowable_MPa",
        "MS",
        "status",
    ]

    print(
        governing[display_cols]
        .to_string(
            index=False,
            formatters={
                "vm_MPa": lambda x: f"{x:.1f}",
                "allowable_MPa": lambda x: f"{x:.1f}",
                "MS": lambda x: f"{x:+.3f}",
            },
        )
    )

    print("\nGEOMETRIC NON-INTERSECTION / LIGAMENT CHECKS")
    print("-" * 110)

    print(
        geometry_checks[
            [
                "check",
                "value_mm",
                "criterion",
                "status",
            ]
        ]
        .to_string(
            index=False,
            formatters={
                "value_mm": lambda x: f"{x:.3f}",
            },
        )
    )

    print("\nKt ROBUSTNESS — GOVERNING CAPACITY")
    print("-" * 110)

    kt_capacity_display = governing_kt_capacity[
        [
            "check",
            "load_level",
            "case",
            "Kt_to_allowable",
            "Kt_capacity_ratio_vs_screen",
        ]
    ].copy()

    print(
        kt_capacity_display
        .to_string(
            index=False,
            formatters={
                "Kt_to_allowable": lambda x: (
                    "inf"
                    if not np.isfinite(x)
                    else f"{x:.3f}"
                ),
                "Kt_capacity_ratio_vs_screen": lambda x: (
                    "inf"
                    if not np.isfinite(x)
                    else f"{x:.3f}"
                ),
            },
        )
    )

    print("\nKt SWEEP — PISTON SMALL END (GOVERNING SECTION CANDIDATE)")
    print("-" * 110)

    piston_sweep_display = (
        governing_kt_sweep[
            governing_kt_sweep["check"]
            == "PISTON_SMALL_END"
        ][
            [
                "load_level",
                "Kt",
                "case",
                "vm_MPa",
                "allowable_MPa",
                "MS",
                "status",
            ]
        ]
        .sort_values(
            ["load_level", "Kt"]
        )
    )

    print(
        piston_sweep_display
        .to_string(
            index=False,
            formatters={
                "Kt": lambda x: f"{x:.2f}",
                "vm_MPa": lambda x: f"{x:.1f}",
                "allowable_MPa": lambda x: f"{x:.1f}",
                "MS": lambda x: f"{x:+.3f}",
            },
        )
    )

    print("\nOUTPUT FILES")
    print("-" * 110)
    print(f"Detailed checks:            {OUTPUT_CHECKS_CSV}")
    print(f"Geometry / packaging:       {OUTPUT_GEOMETRY_CSV}")
    print(f"Geometry checks:            {OUTPUT_GEOMETRY_CHECKS_CSV}")
    print(f"Kt sweep:                   {OUTPUT_KT_SWEEP_CSV}")
    print(f"Kt capacity:                {OUTPUT_KT_CAPACITY_CSV}")

    print("\nINTERPRETATION")
    print("-" * 110)
    print(
        "Phase 2E1 V0.4 now checks both nominal structural response and "
        "robustness to assumed local stress concentration. Geometric PASS "
        "means the blind bores / transition do not intersect and retain "
        "positive material; it is not a local 3D strength certification. "
        "The forged branch intersection, blind-bore ends, and fillets still "
        "require detailed CAD + ANSYS validation later."
    )

    print("=" * 110)


if __name__ == "__main__":
    main()
