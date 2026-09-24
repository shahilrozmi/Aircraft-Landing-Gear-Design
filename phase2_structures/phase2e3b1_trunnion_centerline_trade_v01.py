from pathlib import Path
import ast
import math

import numpy as np
import pandas as pd


# =============================================================================
# LANDING GEAR DESIGN PROJECT
# PHASE 2E3-B1 — TRUNNION CENTERLINE GEOMETRY / LOAD TRADE STUDY V0.1
#
# PURPOSE
#   Determine how close the physical +x trunnion centerline can plausibly be
#   placed above the frozen Phase 2E2 solid-head boundary WITHOUT inventing a
#   final station.
#
#   The E2 boundary is a minimum solid-head boundary, not a trunnion axis.
#
#   A first-order geometric envelope is therefore imposed:
#
#       z_CL - z_E2_boundary >= d_journal/2 + t_ligament
#
#   where:
#       d_journal = candidate trunnion journal/root diameter
#       t_ligament = explicit NON-FROZEN solid-head ligament sensitivity
#
#   The ligament values are not claimed as final allowables. They are only a
#   transparent geometry sensitivity so that station choice is not arbitrary.
#
#   For each candidate geometry this script:
#       - computes the minimum geometric trunnion centerline station,
#       - transports the six-component resultant to that station,
#       - computes left/right trunnion radial reactions for the D9 span sweep,
#       - computes Mx brace force for the D9/D10 arm sweep,
#       - quantifies the load penalty relative to the E2 minimum boundary.
#
#   This phase DOES NOT size the journal stress, lug, bearing, fillet or airframe
#   fitting. It only creates the geometry/load coupling needed for E3-B2 sizing.
#
# OUTPUTS
#   phase2e3b1_centerline_trade.csv
#   phase2e3b1_trunnion_reaction_trade.csv
#   phase2e3b1_brace_force_trade.csv
#   phase2e3b1_summary.txt
# =============================================================================


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.resolve()

LOAD_CSV = (
    PROJECT_ROOT
    / "phase1_loads"
    / "phase1_load_envelope.csv"
)

D9_PY = HERE / "phase2_upper_trunnion_sizing.py"
D10_PY = HERE / "phase2_upper_brace_sizing.py"
E2_BASELINE = HERE / "phase2e2_v1_baseline.csv"

OUTPUT_CENTERLINE = HERE / "phase2e3b1_centerline_trade.csv"
OUTPUT_REACTIONS = HERE / "phase2e3b1_trunnion_reaction_trade.csv"
OUTPUT_BRACE = HERE / "phase2e3b1_brace_force_trade.csv"
OUTPUT_SUMMARY = HERE / "phase2e3b1_summary.txt"


# =============================================================================
# UTILITIES
# =============================================================================

def normalize(text):
    return "".join(
        ch
        for ch in str(text).lower()
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


def parameter_lookup(df, aliases):
    pcol = find_column(df, ["parameter"])
    vcol = find_column(df, ["value"])

    if pcol is None or vcol is None:
        return None

    pnorm = df[pcol].astype(str).map(normalize)

    for alias in aliases:
        rows = df.loc[
            pnorm == normalize(alias)
        ]

        if not rows.empty:
            return rows.iloc[0][vcol]

    return None


def ast_literal_assignments(path):
    if not path.exists():
        raise FileNotFoundError(
            f"Required source not found:\n{path}"
        )

    source = path.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    tree = ast.parse(
        source,
        filename=str(path),
    )

    values = {}

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue

        try:
            value = ast.literal_eval(node.value)
        except Exception:
            continue

        for target in node.targets:
            if isinstance(target, ast.Name):
                values[target.id] = value

    return values


def force_columns(df, level):
    result = {}

    for comp in ["Fx", "Fy", "Fz"]:
        aliases = [
            f"{comp} {level} (kN)",
            f"{comp}_{level}_kN",
            f"{comp}_{level}",
        ]

        col = find_column(
            df,
            aliases,
        )

        if col is None:
            raise KeyError(
                f"Could not resolve {comp} {level}. "
                f"Columns: {list(df.columns)}"
            )

        result[comp] = col

    return result


# =============================================================================
# SOURCE INPUTS
# =============================================================================

d9 = ast_literal_assignments(D9_PY)
d10 = ast_literal_assignments(D10_PY)

e_m = float(d9["e_m"])
rt_m = float(d9["rt_m"])
h_UA_static_m = float(d9["h_UA_static_m"])

support_spans_mm = [
    float(x)
    for x in d9["support_span_values_mm"]
]

journal_diameters_mm = [
    float(x)
    for x in d9["journal_diameter_values_mm"]
]

if "brace_arm_values_mm" in d9:
    brace_arms_mm = [
        float(x)
        for x in d9["brace_arm_values_mm"]
    ]
else:
    brace_arms_mm = [
        float(x)
        for x in d10["effective_arm_values_mm"]
    ]

loads = read_csv(LOAD_CSV)
e2 = read_csv(E2_BASELINE)

e2_boundary_mm = float(
    parameter_lookup(
        e2,
        [
            "preliminary_E3_interface_outer_face_above_U",
        ],
    )
)

case_col = find_column(
    loads,
    [
        "Load Case",
        "case",
        "load_case",
    ],
)

if case_col is None:
    raise KeyError(
        "Could not resolve load-case column."
    )

limit_cols = force_columns(
    loads,
    "Limit",
)

ultimate_cols = force_columns(
    loads,
    "Ultimate",
)


# =============================================================================
# NON-FROZEN GEOMETRIC SENSITIVITY
# =============================================================================

# This is NOT a structural allowable.
# It is only an explicit geometry variable replacing an arbitrary station pick.
ligament_values_mm = [
    5.0,
    10.0,
    15.0,
    20.0,
]


# =============================================================================
# MECHANICS
# =============================================================================

def resultants_at_station(
    Fx_kN,
    Fy_kN,
    Fz_kN,
    station_above_U_mm,
):
    delta_m = (
        station_above_U_mm
        / 1000.0
    )

    h_from_A_m = (
        h_UA_static_m
        + delta_m
    )

    arm_m = (
        rt_m
        + h_from_A_m
    )

    return {
        "Fx_kN":
            Fx_kN,
        "Fy_kN":
            Fy_kN,
        "Fz_kN":
            Fz_kN,
        "Mx_kNm":
            e_m * Fz_kN
            + arm_m * Fy_kN,
        "My_kNm":
            -arm_m * Fx_kN,
        "Mz_kNm":
            -e_m * Fx_kN,
    }


def trunnion_reactions(
    Fy_kN,
    Fz_kN,
    My_kNm,
    Mz_kNm,
    span_mm,
):
    s_m = (
        span_mm
        / 1000.0
    )

    RLy = (
        -Fy_kN
        + 2.0 * Mz_kNm / s_m
    ) / 2.0

    RRy = (
        -Fy_kN
        - 2.0 * Mz_kNm / s_m
    ) / 2.0

    RLz = (
        -Fz_kN
        - 2.0 * My_kNm / s_m
    ) / 2.0

    RRz = (
        -Fz_kN
        + 2.0 * My_kNm / s_m
    ) / 2.0

    RL = math.hypot(
        RLy,
        RLz,
    )

    RR = math.hypot(
        RRy,
        RRz,
    )

    # Exact equilibrium checks.
    force_y_res = (
        RLy
        + RRy
        + Fy_kN
    )

    force_z_res = (
        RLz
        + RRz
        + Fz_kN
    )

    moment_y_res = (
        (s_m / 2.0)
        * (RLz - RRz)
        + My_kNm
    )

    moment_z_res = (
        (s_m / 2.0)
        * (RRy - RLy)
        + Mz_kNm
    )

    if max(
        abs(force_y_res),
        abs(force_z_res),
        abs(moment_y_res),
        abs(moment_z_res),
    ) > 1e-10:
        raise AssertionError(
            "Trunnion equilibrium failed."
        )

    return {
        "RLy_kN": RLy,
        "RRy_kN": RRy,
        "RLz_kN": RLz,
        "RRz_kN": RRz,
        "RL_kN": RL,
        "RR_kN": RR,
        "Rmax_kN": max(RL, RR),
    }


def brace_force_kN(
    Mx_kNm,
    arm_mm,
):
    return abs(
        Mx_kNm
    ) / (
        arm_mm / 1000.0
    )


# =============================================================================
# BASELINE AT E2 MINIMUM BOUNDARY
# =============================================================================

boundary_rows = []

for level, cols in [
    ("limit", limit_cols),
    ("ultimate", ultimate_cols),
]:

    for _, row in loads.iterrows():

        case = str(
            row[case_col]
        )

        resultants = resultants_at_station(
            float(row[cols["Fx"]]),
            float(row[cols["Fy"]]),
            float(row[cols["Fz"]]),
            e2_boundary_mm,
        )

        boundary_rows.append({
            "level": level,
            "case": case,
            **resultants,
        })

boundary_df = pd.DataFrame(
    boundary_rows
)


# =============================================================================
# GEOMETRY / LOAD TRADE
# =============================================================================

centerline_rows = []
reaction_rows = []
brace_rows = []

for diameter_mm in journal_diameters_mm:

    for ligament_mm in ligament_values_mm:

        centerline_offset_above_boundary_mm = (
            diameter_mm / 2.0
            + ligament_mm
        )

        station_above_U_mm = (
            e2_boundary_mm
            + centerline_offset_above_boundary_mm
        )

        station_above_A_static_mm = (
            h_UA_static_m * 1000.0
            + station_above_U_mm
        )

        # Evaluate every current load case.
        case_results = []

        for level, cols in [
            ("limit", limit_cols),
            ("ultimate", ultimate_cols),
        ]:

            for _, row in loads.iterrows():

                case = str(
                    row[case_col]
                )

                resultants = resultants_at_station(
                    float(row[cols["Fx"]]),
                    float(row[cols["Fy"]]),
                    float(row[cols["Fz"]]),
                    station_above_U_mm,
                )

                case_results.append({
                    "level": level,
                    "case": case,
                    **resultants,
                })

                for span_mm in support_spans_mm:

                    reactions = trunnion_reactions(
                        resultants["Fy_kN"],
                        resultants["Fz_kN"],
                        resultants["My_kNm"],
                        resultants["Mz_kNm"],
                        span_mm,
                    )

                    reaction_rows.append({
                        "journal_diameter_mm":
                            diameter_mm,
                        "ligament_mm":
                            ligament_mm,
                        "centerline_offset_above_boundary_mm":
                            centerline_offset_above_boundary_mm,
                        "station_above_U_mm":
                            station_above_U_mm,
                        "level":
                            level,
                        "case":
                            case,
                        "support_span_mm":
                            span_mm,
                        "Fx_thrust_kN":
                            abs(resultants["Fx_kN"]),
                        "My_kNm":
                            resultants["My_kNm"],
                        "Mz_kNm":
                            resultants["Mz_kNm"],
                        **reactions,
                    })

                for arm_mm in brace_arms_mm:

                    brace_rows.append({
                        "journal_diameter_mm":
                            diameter_mm,
                        "ligament_mm":
                            ligament_mm,
                        "centerline_offset_above_boundary_mm":
                            centerline_offset_above_boundary_mm,
                        "station_above_U_mm":
                            station_above_U_mm,
                        "level":
                            level,
                        "case":
                            case,
                        "brace_effective_arm_mm":
                            arm_mm,
                        "Mx_kNm":
                            resultants["Mx_kNm"],
                        "brace_force_abs_kN":
                            brace_force_kN(
                                resultants["Mx_kNm"],
                                arm_mm,
                            ),
                    })

        cases_df = pd.DataFrame(
            case_results
        )

        # Governing transported moments for this geometry.
        summary = {
            "journal_diameter_mm":
                diameter_mm,
            "ligament_mm":
                ligament_mm,
            "centerline_offset_above_boundary_mm":
                centerline_offset_above_boundary_mm,
            "station_above_U_mm":
                station_above_U_mm,
            "station_above_A_static_mm":
                station_above_A_static_mm,
        }

        for level in [
            "limit",
            "ultimate",
        ]:

            subset = cases_df.loc[
                cases_df["level"] == level
            ]

            for comp in [
                "Mx_kNm",
                "My_kNm",
                "Mz_kNm",
            ]:

                idx = (
                    subset[comp]
                    .abs()
                    .idxmax()
                )

                gov = subset.loc[
                    idx
                ]

                summary[
                    f"{level}_{comp}_gov_case"
                ] = gov["case"]

                summary[
                    f"{level}_{comp}_gov_value"
                ] = gov[comp]

        # Relative penalty versus governing boundary loads.
        for level in [
            "limit",
            "ultimate",
        ]:

            B = boundary_df.loc[
                boundary_df["level"] == level
            ]

            for comp in [
                "Mx_kNm",
                "My_kNm",
            ]:

                idx_B = (
                    B[comp]
                    .abs()
                    .idxmax()
                )

                B_val = abs(
                    float(
                        B.loc[
                            idx_B,
                            comp,
                        ]
                    )
                )

                current_val = abs(
                    float(
                        summary[
                            f"{level}_{comp}_gov_value"
                        ]
                    )
                )

                summary[
                    f"{level}_{comp}_penalty_pct_vs_E2_boundary"
                ] = (
                    100.0
                    * (
                        current_val
                        / B_val
                        - 1.0
                    )
                )

        centerline_rows.append(
            summary
        )


centerline_df = pd.DataFrame(
    centerline_rows
)

reaction_df = pd.DataFrame(
    reaction_rows
)

brace_df = pd.DataFrame(
    brace_rows
)

centerline_df.to_csv(
    OUTPUT_CENTERLINE,
    index=False,
)

reaction_df.to_csv(
    OUTPUT_REACTIONS,
    index=False,
)

brace_df.to_csv(
    OUTPUT_BRACE,
    index=False,
)


# =============================================================================
# CONSOLE / SUMMARY
# =============================================================================

print("=" * 124)
print(
    " PHASE 2E3-B1 — TRUNNION CENTERLINE GEOMETRY / LOAD TRADE STUDY V0.1"
)
print("=" * 124)

print("\nSOURCE CONNECTION")
print("-" * 124)
print(
    f"Phase 1 load envelope:            {LOAD_CSV}"
)
print(
    f"Phase 2D9 source:                 {D9_PY}"
)
print(
    f"Phase 2D10 source:                {D10_PY}"
)
print(
    f"Phase 2E2 baseline:               {E2_BASELINE}"
)

print("\nFROZEN / SOURCE-READ GEOMETRY")
print("-" * 124)
print(
    f"E2 solid-head boundary:           {e2_boundary_mm:.6f} mm above U"
)
print(
    f"Equivalent U above A:             {h_UA_static_m*1000.0:.3f} mm"
)
print(
    f"Old D9 journal diameters:         "
    f"{', '.join(f'{x:.0f}' for x in journal_diameters_mm)} mm"
)
print(
    f"Old D9 support spans:             "
    f"{', '.join(f'{x:.0f}' for x in support_spans_mm)} mm"
)
print(
    f"Old brace effective arms:         "
    f"{', '.join(f'{x:.0f}' for x in brace_arms_mm)} mm"
)

print("\nNON-FROZEN GEOMETRIC SENSITIVITY")
print("-" * 124)
print(
    "Centerline rule:                  "
    "z_CL = z_E2 + d_journal/2 + t_ligament"
)
print(
    f"Ligament sensitivities:           "
    f"{', '.join(f'{x:.0f}' for x in ligament_values_mm)} mm"
)
print(
    "These ligament values are geometry sensitivities ONLY, not final structural allowables."
)

# Compact table: old working journal 32 mm if present.
working_d = 32.0

if any(
    abs(d - working_d) < 1e-12
    for d in journal_diameters_mm
):

    print("\n32 mm OLD D9 WORKING JOURNAL — CENTERLINE TRADE")
    print("-" * 124)
    print(
        f"{'Lig mm':>8}"
        f"{'CL>E2 mm':>12}"
        f"{'CL>U mm':>12}"
        f"{'Ult Mx':>12}"
        f"{'Mx +%':>10}"
        f"{'Ult My':>12}"
        f"{'My +%':>10}"
    )
    print("-" * 76)

    rows = centerline_df.loc[
        np.isclose(
            centerline_df[
                "journal_diameter_mm"
            ],
            working_d,
        )
    ].sort_values(
        "ligament_mm"
    )

    for _, row in rows.iterrows():
        print(
            f"{row['ligament_mm']:>8.0f}"
            f"{row['centerline_offset_above_boundary_mm']:>12.1f}"
            f"{row['station_above_U_mm']:>12.1f}"
            f"{abs(row['ultimate_Mx_kNm_gov_value']):>12.3f}"
            f"{row['ultimate_Mx_kNm_penalty_pct_vs_E2_boundary']:>10.2f}"
            f"{abs(row['ultimate_My_kNm_gov_value']):>12.3f}"
            f"{row['ultimate_My_kNm_penalty_pct_vs_E2_boundary']:>10.2f}"
        )

# For each diameter, show the lowest geometric station (5 mm ligament).
print("\nLOWEST GEOMETRIC STATION IN EACH D9 JOURNAL-DIAMETER CASE")
print("-" * 124)
print(
    f"{'d mm':>8}"
    f"{'Lig mm':>8}"
    f"{'CL>E2 mm':>12}"
    f"{'CL>U mm':>12}"
    f"{'Ult Mx':>12}"
    f"{'Ult My':>12}"
)
print("-" * 64)

lowest_rows = centerline_df.loc[
    np.isclose(
        centerline_df["ligament_mm"],
        min(ligament_values_mm),
    )
].sort_values(
    "journal_diameter_mm"
)

for _, row in lowest_rows.iterrows():
    print(
        f"{row['journal_diameter_mm']:>8.0f}"
        f"{row['ligament_mm']:>8.0f}"
        f"{row['centerline_offset_above_boundary_mm']:>12.1f}"
        f"{row['station_above_U_mm']:>12.1f}"
        f"{abs(row['ultimate_Mx_kNm_gov_value']):>12.3f}"
        f"{abs(row['ultimate_My_kNm_gov_value']):>12.3f}"
    )

print("\nENGINEERING INTERPRETATION")
print("-" * 124)
print(
    "1. The structurally favorable trunnion station is the LOWEST station that final head geometry can safely support."
)
print(
    "2. The E2 boundary itself cannot be used as the journal centerline because a finite journal/root envelope must fit above it."
)
print(
    "3. This study deliberately does NOT choose a ligament value or final journal diameter."
)
print(
    "4. E3-B2 must now combine journal/root strength + bearing pressure + Kt sensitivity with this geometry coupling."
)

print("\nOUTPUT FILES")
print("-" * 124)
print(
    f"Centerline trade:                 {OUTPUT_CENTERLINE}"
)
print(
    f"Trunnion reaction trade:          {OUTPUT_REACTIONS}"
)
print(
    f"Brace force trade:                {OUTPUT_BRACE}"
)
print(
    f"Summary:                          {OUTPUT_SUMMARY}"
)

# Write compact summary.
summary_lines = [
    "=" * 124,
    " PHASE 2E3-B1 — TRUNNION CENTERLINE GEOMETRY / LOAD TRADE STUDY V0.1",
    "=" * 124,
    "",
    f"E2 minimum solid-head boundary: {e2_boundary_mm:.6f} mm above U",
    "",
    "Geometry rule:",
    "    z_CL = z_E2_boundary + d_journal/2 + t_ligament",
    "",
    "Ligament values are NON-FROZEN geometry sensitivities only.",
    "",
    "Disposition:",
    "    Proceed to E3-B2 coupled journal/root strength + bearing + Kt sizing.",
    "    Do not freeze a centerline station from geometry alone.",
    "=" * 124,
]

OUTPUT_SUMMARY.write_text(
    "\n".join(summary_lines),
    encoding="utf-8",
)

print("=" * 124)


if __name__ == "__main__":
    pass
