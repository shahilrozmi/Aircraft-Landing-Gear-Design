from pathlib import Path
import math
import re

import numpy as np
import pandas as pd


# =============================================================================
# LANDING GEAR DESIGN PROJECT
# PHASE 2 — AXLE REGRESSION RESOLUTION AUDIT V0.1
#
# PURPOSE
#   Resolve the historical 610.3 / 915.4 MPa axle result versus the current
#   source-driven ~320.8 / 481.2 MPa result.
#
#   This audit does NOT change the design. It:
#       1. prints the authoritative CURRENT Phase 1 load envelope exactly,
#       2. prints the relevant CURRENT axle-source stress logic,
#       3. identifies whether an explicit Kt / SCF is used by the axle script,
#       4. reconstructs the historical LC4 result transparently,
#       5. compares all current load cases with the same transparent root formula,
#       6. reports working 50 x 8 mm axle rows from phase2_axle_sizing.csv.
#
#   No historical/current case is silently mapped by name.
# =============================================================================


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.resolve()

LOAD_CSV = (
    PROJECT_ROOT
    / "phase1_loads"
    / "phase1_load_envelope.csv"
).resolve()

AXLE_PY = (
    HERE
    / "phase2_axle_sizing.py"
).resolve()

AXLE_CSV = (
    HERE
    / "phase2_axle_sizing.csv"
).resolve()

OUTPUT_CSV = (
    HERE
    / "phase2_axle_regression_resolution.csv"
).resolve()

OUTPUT_TXT = (
    HERE
    / "phase2_axle_regression_resolution.txt"
).resolve()


# Historical audit reference only.
HIST_FX_KN = 7.506
HIST_FY_KN = 10.008
HIST_FZ_KN = 25.020

HIST_VM_LIMIT_TARGET_MPA = 610.3
HIST_VM_ULT_TARGET_MPA = 915.4

# Frozen preliminary axle-root geometry.
OD_M = 0.050
ID_M = 0.034
E_M = 0.120
RT_M = 0.175


def normalize(text):
    return "".join(
        ch for ch in str(text).lower()
        if ch.isalnum()
    )


def read_csv(path):
    if not path.exists():
        raise FileNotFoundError(
            f"Required file not found:\n{path}"
        )

    df = pd.read_csv(
        path,
        encoding="utf-8-sig",
    )

    df.columns = [
        str(col).replace("\ufeff", "").strip()
        for col in df.columns
    ]

    return df


def find_column(df, aliases):
    norm = {
        normalize(col): col
        for col in df.columns
    }

    for alias in aliases:
        key = normalize(alias)

        if key in norm:
            return norm[key]

    return None


def candidate_force_columns(df, component, level):
    """
    Return all columns containing both the force component token and level token.
    This is printed so we can detect parser ambiguity rather than hiding it.
    """
    out = []

    comp = component.lower()
    lvl = level.lower()

    for col in df.columns:
        key = normalize(col)

        if comp in key and lvl in key:
            out.append(col)

    return out


def choose_force_column(df, component, level):
    candidates = candidate_force_columns(
        df,
        component,
        level,
    )

    if not candidates:
        return None, None

    # Prefer explicit kN/N force columns with the shortest normalized name.
    scored = []

    for col in candidates:
        key = normalize(col)

        score = 0

        if key.startswith(
            component.lower()
        ):
            score += 10

        if "force" in key:
            score += 2

        if key.endswith("kn"):
            scale = 1000.0
            score += 2
        elif key.endswith("n"):
            scale = 1.0
            score += 1
        elif "kn" in key:
            scale = 1000.0
        else:
            scale = 1.0

        scored.append(
            (
                -score,
                len(key),
                col,
                scale,
            )
        )

    scored.sort()

    _, _, col, scale = scored[0]

    return col, scale


def case_column(df):
    for aliases in [
        ["case"],
        ["load_case"],
        ["case_name"],
        ["loadcase"],
        ["name"],
    ]:
        col = find_column(
            df,
            aliases,
        )

        if col is not None:
            return col

    return None


def section_properties():
    A = (
        math.pi
        / 4.0
        * (
            OD_M**2
            - ID_M**2
        )
    )

    I = (
        math.pi
        / 64.0
        * (
            OD_M**4
            - ID_M**4
        )
    )

    J = (
        math.pi
        / 32.0
        * (
            OD_M**4
            - ID_M**4
        )
    )

    c = OD_M / 2.0

    return A, I, J, c


def root_stress(
    Fx_kN,
    Fy_kN,
    Fz_kN,
    Kt_bending=1.0,
    include_torque=False,
):
    """
    Transparent axle-root diagnostic using the documented Phase 2 geometry:

        N_y = F_y
        M_x = e F_z + r_t F_y
        M_z = -e F_x
        M_b = sqrt(M_x^2 + M_z^2)

    Optional torque:
        T_y = -r_t F_x
    """

    Fx = Fx_kN * 1000.0
    Fy = Fy_kN * 1000.0
    Fz = Fz_kN * 1000.0

    A, I, J, c = section_properties()

    N = Fy

    Mx = (
        E_M * Fz
        + RT_M * Fy
    )

    Mz = (
        -E_M * Fx
    )

    Mb = math.hypot(
        Mx,
        Mz,
    )

    T = (
        -RT_M * Fx
        if include_torque
        else 0.0
    )

    sigma_ax = (
        abs(N)
        / A
    )

    sigma_b = (
        Kt_bending
        * Mb
        * c
        / I
    )

    tau = (
        abs(T)
        * c
        / J
    )

    sigma = (
        sigma_ax
        + sigma_b
    )

    vm = math.sqrt(
        sigma**2
        + 3.0 * tau**2
    )

    return {
        "N_kN": N / 1000.0,
        "Mx_kNm": Mx / 1000.0,
        "Mz_kNm": Mz / 1000.0,
        "Mb_kNm": Mb / 1000.0,
        "T_kNm": T / 1000.0,
        "sigma_ax_MPa": sigma_ax / 1e6,
        "sigma_bend_MPa": sigma_b / 1e6,
        "tau_MPa": tau / 1e6,
        "vm_MPa": vm / 1e6,
    }


def source_snippets(path, patterns, radius=5):
    if not path.exists():
        return []

    lines = path.read_text(
        encoding="utf-8",
        errors="ignore",
    ).splitlines()

    hits = []

    for i, line in enumerate(lines):
        low = line.lower()

        if any(
            pattern.lower() in low
            for pattern in patterns
        ):
            hits.append(i)

    ranges = []

    for i in hits:
        start = max(
            0,
            i - radius,
        )

        stop = min(
            len(lines) - 1,
            i + radius,
        )

        if (
            ranges
            and start <= ranges[-1][1] + 1
        ):
            ranges[-1] = (
                ranges[-1][0],
                max(
                    ranges[-1][1],
                    stop,
                ),
            )
        else:
            ranges.append(
                (start, stop)
            )

    blocks = []

    for start, stop in ranges:
        block = []

        for i in range(
            start,
            stop + 1,
        ):
            block.append(
                f"{i+1:5d}: {lines[i]}"
            )

        blocks.append(
            "\n".join(block)
        )

    return blocks


def main():

    print("=" * 122)
    print(
        " PHASE 2 — AXLE REGRESSION RESOLUTION AUDIT V0.1"
    )
    print("=" * 122)

    loads = read_csv(
        LOAD_CSV
    )

    case_col = case_column(
        loads
    )

    if case_col is None:
        raise ValueError(
            "Could not identify load-case column."
        )

    print("\nCURRENT LOAD SOURCE — RAW TABLE")
    print("-" * 122)
    print(
        f"Source: {LOAD_CSV}"
    )
    print(
        f"Columns: {list(loads.columns)}"
    )
    print()
    print(
        loads.to_string(
            index=False,
        )
    )

    print("\nFORCE-COLUMN RESOLUTION DIAGNOSTIC")
    print("-" * 122)

    selected = {}

    for level in [
        "limit",
        "ultimate",
    ]:
        for comp in [
            "fx",
            "fy",
            "fz",
        ]:
            candidates = candidate_force_columns(
                loads,
                comp,
                level,
            )

            chosen, scale = choose_force_column(
                loads,
                comp,
                level,
            )

            selected[
                (
                    level,
                    comp,
                )
            ] = (
                chosen,
                scale,
            )

            print(
                f"{level.upper():<9} {comp.upper():<2} candidates: "
                f"{candidates}"
            )
            print(
                f"{'':<12}chosen: {chosen}  "
                f"scale-to-N: {scale}"
            )

    if any(
        selected[
            (
                "limit",
                comp,
            )
        ][0] is None
        for comp in [
            "fx",
            "fy",
            "fz",
        ]
    ):
        raise ValueError(
            "Could not uniquely resolve limit force columns."
        )

    print("\nCURRENT LOAD CASES — TRANSPARENT ROOT RECONSTRUCTION")
    print("-" * 122)

    rows = []

    for _, row in loads.iterrows():
        case = str(
            row[case_col]
        )

        values = {}

        for level in [
            "limit",
            "ultimate",
        ]:
            for comp in [
                "fx",
                "fy",
                "fz",
            ]:
                col, scale = selected[
                    (
                        level,
                        comp,
                    )
                ]

                if col is None:
                    values[
                        f"{comp}_{level}_kN"
                    ] = np.nan
                else:
                    values[
                        f"{comp}_{level}_kN"
                    ] = (
                        float(
                            row[col]
                        )
                        * scale
                        / 1000.0
                    )

        lim = root_stress(
            values[
                "fx_limit_kN"
            ],
            values[
                "fy_limit_kN"
            ],
            values[
                "fz_limit_kN"
            ],
            Kt_bending=1.0,
            include_torque=(
                normalize(case)
                == normalize("LC5")
            ),
        )

        lim_Kt12 = root_stress(
            values[
                "fx_limit_kN"
            ],
            values[
                "fy_limit_kN"
            ],
            values[
                "fz_limit_kN"
            ],
            Kt_bending=1.2,
            include_torque=(
                normalize(case)
                == normalize("LC5")
            ),
        )

        if all(
            pd.notna(
                values[
                    f"{comp}_ultimate_kN"
                ]
            )
            for comp in [
                "fx",
                "fy",
                "fz",
            ]
        ):
            ult = root_stress(
                values[
                    "fx_ultimate_kN"
                ],
                values[
                    "fy_ultimate_kN"
                ],
                values[
                    "fz_ultimate_kN"
                ],
                Kt_bending=1.0,
                include_torque=(
                    normalize(case)
                    == normalize("LC5")
                ),
            )
        else:
            ult = {
                "vm_MPa": np.nan,
            }

        rows.append({
            "case": case,
            **values,
            "VM_limit_Kt1p0_MPa": lim[
                "vm_MPa"
            ],
            "VM_limit_Kt1p2_MPa": lim_Kt12[
                "vm_MPa"
            ],
            "VM_ultimate_Kt1p0_MPa": ult[
                "vm_MPa"
            ],
        })

    reconstruction = pd.DataFrame(
        rows
    )

    reconstruction.to_csv(
        OUTPUT_CSV,
        index=False,
    )

    print(
        reconstruction.to_string(
            index=False,
        )
    )

    print("\nHISTORICAL LC4 RECONSTRUCTION")
    print("-" * 122)

    historical_rows = []

    for Kt in [
        1.0,
        1.2,
        1.5,
    ]:
        result = root_stress(
            HIST_FX_KN,
            HIST_FY_KN,
            HIST_FZ_KN,
            Kt_bending=Kt,
            include_torque=False,
        )

        historical_rows.append({
            "Kt_bending": Kt,
            **result,
        })

        print(
            f"Kt={Kt:.1f}: VM = "
            f"{result['vm_MPa']:.3f} MPa"
        )

    noKt = historical_rows[0]

    A, I, J, c = section_properties()

    # Effective Kt that reproduces the historical target, when applied only
    # to bending while axial stress remains nominal.
    sigma_ax = noKt[
        "sigma_ax_MPa"
    ]

    sigma_b_nom = noKt[
        "sigma_bend_MPa"
    ]

    effective_Kt = (
        HIST_VM_LIMIT_TARGET_MPA
        - sigma_ax
    ) / sigma_b_nom

    print(
        f"Historic target limit VM:       "
        f"{HIST_VM_LIMIT_TARGET_MPA:.3f} MPa"
    )
    print(
        f"Effective bending Kt required:  "
        f"{effective_Kt:.6f}"
    )
    print(
        f"1.5 x historic limit target:    "
        f"{1.5*HIST_VM_LIMIT_TARGET_MPA:.3f} MPa"
    )
    print(
        f"Historic ultimate target:       "
        f"{HIST_VM_ULT_TARGET_MPA:.3f} MPa"
    )

    print("\nCURRENT AXLE PYTHON — Kt / SCF TOKEN AUDIT")
    print("-" * 122)

    source = AXLE_PY.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    kt_lines = []

    for i, line in enumerate(
        source.splitlines(),
        start=1,
    ):
        if re.search(
            r"\b(Kt|SCF|stress[_ ]?concentration)\b",
            line,
            flags=re.IGNORECASE,
        ):
            kt_lines.append(
                (
                    i,
                    line,
                )
            )

    if not kt_lines:
        print(
            "No explicit Kt / SCF / stress-concentration token found "
            "in phase2_axle_sizing.py."
        )
    else:
        for line_no, line in kt_lines:
            print(
                f"{line_no:5d}: {line}"
            )

    print("\nCURRENT AXLE PYTHON — STRESS LOGIC CONTEXT")
    print("-" * 122)

    snippets = source_snippets(
        AXLE_PY,
        [
            "sigma_ax",
            "sigma_b",
            "tau_t",
            "vm_MPa",
            "von_mises",
            "section_check",
            "working_OD_mm",
            "working_wall_mm",
        ],
        radius=6,
    )

    if snippets:
        for block in snippets:
            print(block)
            print()
    else:
        print(
            "No targeted stress-source lines found."
        )

    print("\nCURRENT AXLE CSV — WORKING 50 x 8 mm ROWS")
    print("-" * 122)

    if AXLE_CSV.exists():
        axle_df = read_csv(
            AXLE_CSV
        )

        print(
            f"Columns: {list(axle_df.columns)}"
        )

        od_col = find_column(
            axle_df,
            [
                "OD_mm",
                "outer_diameter_mm",
            ],
        )

        wall_col = find_column(
            axle_df,
            [
                "wall_mm",
                "wall_thickness_mm",
            ],
        )

        if (
            od_col is not None
            and wall_col is not None
        ):
            mask = (
                np.isclose(
                    pd.to_numeric(
                        axle_df[od_col],
                        errors="coerce",
                    ),
                    50.0,
                )
                & np.isclose(
                    pd.to_numeric(
                        axle_df[wall_col],
                        errors="coerce",
                    ),
                    8.0,
                )
            )

            working = axle_df.loc[
                mask
            ]

            if working.empty:
                print(
                    "No exact 50 x 8 mm row found."
                )
            else:
                print(
                    working.to_string(
                        index=False,
                    )
                )
        else:
            print(
                "OD/wall columns were not recognized; full CSV follows:"
            )
            print(
                axle_df.to_string(
                    index=False,
                )
            )
    else:
        print(
            "phase2_axle_sizing.csv not found."
        )

    # Determine current transparent governing case at Kt=1.0.
    idx = reconstruction[
        "VM_limit_Kt1p0_MPa"
    ].idxmax()

    current_gov = reconstruction.loc[
        idx
    ]

    print("\nPRELIMINARY RESOLUTION SUMMARY")
    print("-" * 122)
    print(
        f"Historical LC4 target:          "
        f"{HIST_VM_LIMIT_TARGET_MPA:.1f} / "
        f"{HIST_VM_ULT_TARGET_MPA:.1f} MPa"
    )
    print(
        f"Historical effective Kt:        "
        f"{effective_Kt:.6f}"
    )
    print(
        f"Transparent current governor:   "
        f"{current_gov['case']}"
    )
    print(
        f"Current VM @ Kt=1.0:            "
        f"{current_gov['VM_limit_Kt1p0_MPa']:.3f} MPa"
    )
    print(
        f"Current VM @ Kt=1.2:            "
        f"{current_gov['VM_limit_Kt1p2_MPa']:.3f} MPa"
    )
    print()
    print(
        "Interpretation gate: use the raw current load table, the explicit Kt/SCF "
        "token audit, the stress-source context, and the working-row CSV above to "
        "decide whether the historic result was superseded by (a) a revised load "
        "envelope, (b) removal/separation of a preliminary Kt from the nominal axle "
        "root screen, or (c) both. This script does not guess the answer."
    )

    report = []
    report.append(
        "PHASE 2 — AXLE REGRESSION RESOLUTION AUDIT V0.1"
    )
    report.append(
        f"Historic target limit / ultimate: "
        f"{HIST_VM_LIMIT_TARGET_MPA:.3f} / "
        f"{HIST_VM_ULT_TARGET_MPA:.3f} MPa"
    )
    report.append(
        f"Effective historical bending Kt: {effective_Kt:.6f}"
    )
    report.append(
        f"Transparent current governing case: {current_gov['case']}"
    )
    report.append(
        f"Transparent current VM Kt=1.0: "
        f"{current_gov['VM_limit_Kt1p0_MPa']:.6f} MPa"
    )
    report.append(
        f"Transparent current VM Kt=1.2: "
        f"{current_gov['VM_limit_Kt1p2_MPa']:.6f} MPa"
    )
    report.append(
        f"Explicit Kt/SCF tokens in authoritative axle source: "
        f"{len(kt_lines)}"
    )
    report.append(
        "See console / CSV for the complete raw current load envelope and source context."
    )

    OUTPUT_TXT.write_text(
        "\n".join(report),
        encoding="utf-8",
    )

    print("\nOUTPUT FILES")
    print("-" * 122)
    print(
        f"Current-case reconstruction:    {OUTPUT_CSV}"
    )
    print(
        f"Resolution summary:             {OUTPUT_TXT}"
    )
    print("=" * 122)


if __name__ == "__main__":
    main()
