from pathlib import Path
import io
import math
import runpy
from contextlib import redirect_stdout

import numpy as np
import pandas as pd


# =============================================================================
# LANDING GEAR DESIGN PROJECT
# PHASE 2E3-B2 — COUPLED TRUNNION JOURNAL / BEARING / Kt SIZING V0.1
#
# PURPOSE
#   Couple the Phase 2E3-B1 physical-centerline geometry with the original
#   Phase 2D9 journal-root mechanics.
#
#   IMPORTANT:
#   - The D9 ARCHITECTURE and stress function are reused directly from the
#     authoritative local phase2_upper_trunnion_sizing.py.
#   - The D9 LOADS at equivalent datum U are NOT reused.
#   - Current E3 loads come from the B1 reaction trade after transporting the
#     current Phase 1 envelope to the geometry-coupled physical trunnion station.
#
#   This script evaluates:
#       * journal/root VM screen,
#       * projected bronze-bushing pressure,
#       * transverse shear screen,
#       * Kt = D9 sensitivity values,
#       * support-span / bearing-width / journal-diameter / ligament trade.
#
#   It does NOT freeze a final trunnion design.
#
# OUTPUTS
#   phase2e3b2_trunnion_design_sweep.csv
#   phase2e3b2_minimum_passing_by_layout.csv
#   phase2e3b2_robust_candidate_summary.csv
#   phase2e3b2_summary.txt
# =============================================================================


HERE = Path(__file__).resolve().parent

D9_PY = HERE / "phase2_upper_trunnion_sizing.py"
D5_CSV = HERE / "phase2_bushing_material_gland_requirements.csv"

B1_CENTERLINE = HERE / "phase2e3b1_centerline_trade.csv"
B1_REACTIONS = HERE / "phase2e3b1_trunnion_reaction_trade.csv"

OUTPUT_SWEEP = HERE / "phase2e3b2_trunnion_design_sweep.csv"
OUTPUT_MIN = HERE / "phase2e3b2_minimum_passing_by_layout.csv"
OUTPUT_ROBUST = HERE / "phase2e3b2_robust_candidate_summary.csv"
OUTPUT_SUMMARY = HERE / "phase2e3b2_summary.txt"


# =============================================================================
# UTILITIES
# =============================================================================

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


def first_numeric(namespace, candidates):
    for name in candidates:
        if name in namespace:
            value = namespace[name]

            if isinstance(
                value,
                (int, float, np.integer, np.floating),
            ):
                return float(value), name

    return None, None


def find_d5_capacity(df):
    candidate_cols = [
        "AMS4640_static_capacity_MPa",
        "bronze_static_capacity_MPa",
        "static_capacity_MPa",
    ]

    for col in candidate_cols:
        if col in df.columns:
            vals = pd.to_numeric(
                df[col],
                errors="coerce",
            ).dropna()

            if not vals.empty:
                return float(vals.iloc[0]), col

    # Parameter/value fallback.
    if (
        "parameter" in df.columns
        and "value" in df.columns
    ):
        norm = (
            df["parameter"]
            .astype(str)
            .str.lower()
            .str.replace(
                r"[^a-z0-9]",
                "",
                regex=True,
            )
        )

        aliases = {
            "ams4640staticcapacitympa",
            "bronzestaticcapacitympa",
        }

        rows = df.loc[
            norm.isin(aliases)
        ]

        if not rows.empty:
            return (
                float(
                    rows.iloc[0]["value"]
                ),
                "parameter/value",
            )

    raise KeyError(
        "Could not resolve AMS 4640 preliminary static bearing capacity "
        f"from {D5_CSV}."
    )


def margin(
    allowable_MPa,
    demand_MPa,
):
    if demand_MPa <= 0.0:
        return np.inf

    return (
        allowable_MPa
        / demand_MPa
        - 1.0
    )


# =============================================================================
# LOAD AUTHORITATIVE D9 MECHANICS WITHOUT PRINTING ITS OLD REPORT
# =============================================================================

if not D9_PY.exists():
    raise FileNotFoundError(
        f"Required Phase 2D9 source not found:\n{D9_PY}"
    )

_old_stdout = io.StringIO()

with redirect_stdout(
    _old_stdout
):
    d9 = runpy.run_path(
        str(D9_PY),
        run_name="phase2d9_reuse_for_e3b2",
    )


required_d9_items = [
    "journal_root_stress",
    "bearing_width_values_mm",
    "journal_diameter_values_mm",
    "support_span_values_mm",
    "Kt_values",
    "root_clearance_mm",
]

missing = [
    name
    for name in required_d9_items
    if name not in d9
]

if missing:
    raise KeyError(
        "Required D9 mechanics/source variables were not exposed: "
        + ", ".join(missing)
    )


journal_root_stress = d9[
    "journal_root_stress"
]

bearing_width_values_mm = [
    float(x)
    for x in d9[
        "bearing_width_values_mm"
    ]
]

journal_diameter_values_mm = [
    float(x)
    for x in d9[
        "journal_diameter_values_mm"
    ]
]

support_span_values_mm = [
    float(x)
    for x in d9[
        "support_span_values_mm"
    ]
]

Kt_values = [
    float(x)
    for x in d9[
        "Kt_values"
    ]
]

root_clearance_mm = float(
    d9[
        "root_clearance_mm"
    ]
)


# =============================================================================
# MATERIAL INPUTS — SOURCE-READ
# =============================================================================

# Try the D9 namespace first so the current D9 allowable convention remains
# source-connected.
Sy_raw, Sy_name = first_numeric(
    d9,
    [
        "Sy_Pa",
        "Sy_300M_Pa",
        "yield_strength_Pa",
        "sigma_yield_Pa",
    ],
)

Su_raw, Su_name = first_numeric(
    d9,
    [
        "Su_Pa",
        "Su_300M_Pa",
        "ultimate_strength_Pa",
        "sigma_ultimate_Pa",
    ],
)

if (
    Sy_raw is None
    or Su_raw is None
):
    raise KeyError(
        "Could not source-read the D9 300M yield/ultimate allowables. "
        "Expected one of the recognized Sy/Su variable names in "
        "phase2_upper_trunnion_sizing.py."
    )

# D9 is expected to store Pa. Detect MPa defensively only if values are small.
Sy_MPa = (
    Sy_raw / 1e6
    if Sy_raw > 1e6
    else Sy_raw
)

Su_MPa = (
    Su_raw / 1e6
    if Su_raw > 1e6
    else Su_raw
)

# Shear screens use von-Mises equivalent pure-shear limits.
tau_yield_allow_MPa = (
    Sy_MPa
    / math.sqrt(3.0)
)

tau_ultimate_allow_MPa = (
    Su_MPa
    / math.sqrt(3.0)
)

d5 = read_csv(
    D5_CSV
)

bronze_capacity_MPa, bronze_source_col = find_d5_capacity(
    d5
)


# =============================================================================
# READ B1 GEOMETRY / REACTION TRADE
# =============================================================================

centerline = read_csv(
    B1_CENTERLINE
)

reactions = read_csv(
    B1_REACTIONS
)


required_reaction_cols = [
    "journal_diameter_mm",
    "ligament_mm",
    "centerline_offset_above_boundary_mm",
    "station_above_U_mm",
    "level",
    "case",
    "support_span_mm",
    "Fx_thrust_kN",
    "Rmax_kN",
]

for col in required_reaction_cols:
    if col not in reactions.columns:
        raise KeyError(
            f"B1 reaction column missing: {col}"
        )


# =============================================================================
# COUPLED DESIGN EVALUATION
# =============================================================================

design_rows = []

group_cols = [
    "journal_diameter_mm",
    "ligament_mm",
    "support_span_mm",
]

for (
    diameter_mm,
    ligament_mm,
    span_mm,
), group in reactions.groupby(
    group_cols,
    sort=True,
):

    diameter_mm = float(
        diameter_mm
    )

    ligament_mm = float(
        ligament_mm
    )

    span_mm = float(
        span_mm
    )

    if not any(
        abs(
            diameter_mm - d
        ) < 1e-9
        for d in journal_diameter_values_mm
    ):
        continue

    station_above_U_mm = float(
        group[
            "station_above_U_mm"
        ].iloc[0]
    )

    cl_offset_mm = float(
        group[
            "centerline_offset_above_boundary_mm"
        ].iloc[0]
    )

    for bearing_width_mm in bearing_width_values_mm:

        bearing_width_mm = float(
            bearing_width_mm
        )

        for Kt in Kt_values:

            Kt = float(
                Kt
            )

            case_rows = []

            for _, row in group.iterrows():

                level = str(
                    row[
                        "level"
                    ]
                ).lower()

                case = str(
                    row[
                        "case"
                    ]
                )

                Rgov_kN = float(
                    row[
                        "Rmax_kN"
                    ]
                )

                Fx_kN = float(
                    row[
                        "Fx_thrust_kN"
                    ]
                )

                # Reuse authoritative D9 journal-root stress function directly.
                stress = journal_root_stress(
                    Rgov_kN,
                    Fx_kN,
                    diameter_mm,
                    bearing_width_mm,
                    Kt_bending=Kt,
                )

                if "vm_MPa" not in stress:
                    raise KeyError(
                        "D9 journal_root_stress did not return vm_MPa."
                    )

                vm_MPa = float(
                    stress[
                        "vm_MPa"
                    ]
                )

                tau_transverse_MPa = float(
                    stress.get(
                        "tau_transverse_MPa",
                        np.nan,
                    )
                )

                bearing_pressure_MPa = (
                    Rgov_kN
                    * 1000.0
                    / (
                        diameter_mm
                        * bearing_width_mm
                    )
                )

                if level == "limit":
                    strength_allowable_MPa = Sy_MPa
                    shear_allowable_MPa = tau_yield_allow_MPa

                elif level == "ultimate":
                    strength_allowable_MPa = Su_MPa
                    shear_allowable_MPa = tau_ultimate_allow_MPa

                else:
                    raise ValueError(
                        f"Unexpected load level: {level}"
                    )

                MS_strength = margin(
                    strength_allowable_MPa,
                    vm_MPa,
                )

                MS_bearing = margin(
                    bronze_capacity_MPa,
                    bearing_pressure_MPa,
                )

                if np.isfinite(
                    tau_transverse_MPa
                ):
                    MS_shear = margin(
                        shear_allowable_MPa,
                        tau_transverse_MPa,
                    )
                else:
                    MS_shear = np.nan

                case_rows.append({
                    "level":
                        level,
                    "case":
                        case,
                    "Rgov_kN":
                        Rgov_kN,
                    "Fx_thrust_kN":
                        Fx_kN,
                    "vm_MPa":
                        vm_MPa,
                    "tau_transverse_MPa":
                        tau_transverse_MPa,
                    "bearing_pressure_MPa":
                        bearing_pressure_MPa,
                    "MS_strength":
                        MS_strength,
                    "MS_bearing":
                        MS_bearing,
                    "MS_shear":
                        MS_shear,
                    **{
                        key: value
                        for key, value
                        in stress.items()
                        if key not in {
                            "vm_MPa",
                            "tau_transverse_MPa",
                        }
                    },
                })

            case_df = pd.DataFrame(
                case_rows
            )

            limit_rows = case_df.loc[
                case_df[
                    "level"
                ] == "limit"
            ]

            ultimate_rows = case_df.loc[
                case_df[
                    "level"
                ] == "ultimate"
            ]

            def gov_max(
                df,
                column,
            ):
                idx = df[
                    column
                ].idxmax()

                return df.loc[
                    idx
                ]

            def gov_min_margin(
                df,
                column,
            ):
                finite = df.loc[
                    pd.to_numeric(
                        df[column],
                        errors="coerce",
                    ).notna()
                ]

                if finite.empty:
                    return None

                idx = finite[
                    column
                ].idxmin()

                return finite.loc[
                    idx
                ]

            gov_lim_vm = gov_max(
                limit_rows,
                "vm_MPa",
            )

            gov_ult_vm = gov_max(
                ultimate_rows,
                "vm_MPa",
            )

            gov_lim_bearing = gov_max(
                limit_rows,
                "bearing_pressure_MPa",
            )

            gov_ult_bearing = gov_max(
                ultimate_rows,
                "bearing_pressure_MPa",
            )

            gov_lim_shear = gov_min_margin(
                limit_rows,
                "MS_shear",
            )

            gov_ult_shear = gov_min_margin(
                ultimate_rows,
                "MS_shear",
            )

            MS_limit_shear = (
                float(
                    gov_lim_shear[
                        "MS_shear"
                    ]
                )
                if gov_lim_shear is not None
                else np.nan
            )

            MS_ultimate_shear = (
                float(
                    gov_ult_shear[
                        "MS_shear"
                    ]
                )
                if gov_ult_shear is not None
                else np.nan
            )

            checks = [
                float(
                    gov_lim_vm[
                        "MS_strength"
                    ]
                ) >= 0.0,
                float(
                    gov_ult_vm[
                        "MS_strength"
                    ]
                ) >= 0.0,
                float(
                    gov_lim_bearing[
                        "MS_bearing"
                    ]
                ) >= 0.0,
                float(
                    gov_ult_bearing[
                        "MS_bearing"
                    ]
                ) >= 0.0,
            ]

            # Keep the D9 transverse-shear screen if the function provides it.
            if np.isfinite(
                MS_limit_shear
            ):
                checks.append(
                    MS_limit_shear >= 0.0
                )

            if np.isfinite(
                MS_ultimate_shear
            ):
                checks.append(
                    MS_ultimate_shear >= 0.0
                )

            passes = all(
                checks
            )

            design_rows.append({
                "journal_diameter_mm":
                    diameter_mm,
                "ligament_mm":
                    ligament_mm,
                "centerline_offset_above_boundary_mm":
                    cl_offset_mm,
                "station_above_U_mm":
                    station_above_U_mm,
                "support_span_mm":
                    span_mm,
                "bearing_width_mm":
                    bearing_width_mm,
                "root_clearance_mm":
                    root_clearance_mm,
                "Kt_bending":
                    Kt,

                "limit_vm_case":
                    gov_lim_vm[
                        "case"
                    ],
                "limit_vm_MPa":
                    gov_lim_vm[
                        "vm_MPa"
                    ],
                "MS_limit_yield":
                    gov_lim_vm[
                        "MS_strength"
                    ],

                "ultimate_vm_case":
                    gov_ult_vm[
                        "case"
                    ],
                "ultimate_vm_MPa":
                    gov_ult_vm[
                        "vm_MPa"
                    ],
                "MS_ultimate_strength":
                    gov_ult_vm[
                        "MS_strength"
                    ],

                "limit_bearing_case":
                    gov_lim_bearing[
                        "case"
                    ],
                "limit_bearing_pressure_MPa":
                    gov_lim_bearing[
                        "bearing_pressure_MPa"
                    ],
                "MS_limit_bearing":
                    gov_lim_bearing[
                        "MS_bearing"
                    ],

                "ultimate_bearing_case":
                    gov_ult_bearing[
                        "case"
                    ],
                "ultimate_bearing_pressure_MPa":
                    gov_ult_bearing[
                        "bearing_pressure_MPa"
                    ],
                "MS_ultimate_bearing":
                    gov_ult_bearing[
                        "MS_bearing"
                    ],

                "MS_limit_transverse_shear":
                    MS_limit_shear,
                "MS_ultimate_transverse_shear":
                    MS_ultimate_shear,

                "PASS":
                    passes,
            })


design_df = pd.DataFrame(
    design_rows
)

design_df.to_csv(
    OUTPUT_SWEEP,
    index=False,
)


# =============================================================================
# MINIMUM PASSING DIAMETER PER LAYOUT / Kt
# =============================================================================

minimum_rows = []

layout_cols = [
    "ligament_mm",
    "support_span_mm",
    "bearing_width_mm",
    "Kt_bending",
]

for key, group in design_df.groupby(
    layout_cols,
    sort=True,
):

    ligament_mm, span_mm, bearing_width_mm, Kt = key

    passing = (
        group.loc[
            group["PASS"]
        ]
        .sort_values(
            "journal_diameter_mm"
        )
    )

    if passing.empty:
        minimum_rows.append({
            "ligament_mm":
                ligament_mm,
            "support_span_mm":
                span_mm,
            "bearing_width_mm":
                bearing_width_mm,
            "Kt_bending":
                Kt,
            "minimum_passing_diameter_mm":
                np.nan,
            "station_above_U_mm":
                np.nan,
            "ultimate_vm_MPa":
                np.nan,
            "MS_ultimate_strength":
                np.nan,
            "ultimate_bearing_pressure_MPa":
                np.nan,
            "MS_ultimate_bearing":
                np.nan,
            "status":
                "NO_PASS_IN_D9_DIAMETER_SWEEP",
        })

    else:
        first = passing.iloc[0]

        minimum_rows.append({
            "ligament_mm":
                ligament_mm,
            "support_span_mm":
                span_mm,
            "bearing_width_mm":
                bearing_width_mm,
            "Kt_bending":
                Kt,
            "minimum_passing_diameter_mm":
                first[
                    "journal_diameter_mm"
                ],
            "station_above_U_mm":
                first[
                    "station_above_U_mm"
                ],
            "ultimate_vm_MPa":
                first[
                    "ultimate_vm_MPa"
                ],
            "MS_ultimate_strength":
                first[
                    "MS_ultimate_strength"
                ],
            "ultimate_bearing_pressure_MPa":
                first[
                    "ultimate_bearing_pressure_MPa"
                ],
            "MS_ultimate_bearing":
                first[
                    "MS_ultimate_bearing"
                ],
            "status":
                "PASS",
        })


minimum_df = pd.DataFrame(
    minimum_rows
)

minimum_df.to_csv(
    OUTPUT_MIN,
    index=False,
)


# =============================================================================
# ROBUST-CANDIDATE SUMMARY
#
# A design is called "ROBUST_WITHIN_SCREEN" only when it passes every D9 Kt
# sensitivity value for the SAME diameter/ligament/span/bearing-width geometry.
# This is not equivalent to a validated fillet.
# =============================================================================

robust_rows = []

robust_group_cols = [
    "journal_diameter_mm",
    "ligament_mm",
    "support_span_mm",
    "bearing_width_mm",
]

for key, group in design_df.groupby(
    robust_group_cols,
    sort=True,
):

    diameter_mm, ligament_mm, span_mm, bearing_width_mm = key

    kt_set = set(
        round(
            float(x),
            10,
        )
        for x in group[
            "Kt_bending"
        ]
    )

    expected_kt_set = set(
        round(
            float(x),
            10,
        )
        for x in Kt_values
    )

    full_kt_coverage = (
        kt_set
        == expected_kt_set
    )

    robust_pass = (
        full_kt_coverage
        and bool(
            group[
                "PASS"
            ].all()
        )
    )

    worst_strength_row = group.loc[
        group[
            "MS_ultimate_strength"
        ].idxmin()
    ]

    worst_bearing_row = group.loc[
        group[
            "MS_ultimate_bearing"
        ].idxmin()
    ]

    robust_rows.append({
        "journal_diameter_mm":
            diameter_mm,
        "ligament_mm":
            ligament_mm,
        "station_above_U_mm":
            float(
                group[
                    "station_above_U_mm"
                ].iloc[0]
            ),
        "support_span_mm":
            span_mm,
        "bearing_width_mm":
            bearing_width_mm,
        "max_Kt_checked":
            max(
                Kt_values
            ),
        "full_Kt_coverage":
            full_kt_coverage,
        "ROBUST_WITHIN_SCREEN":
            robust_pass,
        "worst_MS_ultimate_strength":
            worst_strength_row[
                "MS_ultimate_strength"
            ],
        "worst_strength_Kt":
            worst_strength_row[
                "Kt_bending"
            ],
        "worst_strength_case":
            worst_strength_row[
                "ultimate_vm_case"
            ],
        "worst_MS_ultimate_bearing":
            worst_bearing_row[
                "MS_ultimate_bearing"
            ],
        "ultimate_bearing_pressure_MPa":
            worst_bearing_row[
                "ultimate_bearing_pressure_MPa"
            ],
    })


robust_df = pd.DataFrame(
    robust_rows
)

robust_df.to_csv(
    OUTPUT_ROBUST,
    index=False,
)


# =============================================================================
# CONSOLE REPORT
# =============================================================================

print("=" * 124)
print(
    " PHASE 2E3-B2 — COUPLED TRUNNION JOURNAL / BEARING / Kt SIZING V0.1"
)
print("=" * 124)

print("\nSOURCE CONNECTION")
print("-" * 124)
print(
    f"Reused D9 source mechanics:       {D9_PY}"
)
print(
    f"B1 reaction/geometry trade:       {B1_REACTIONS}"
)
print(
    f"D5 bronze capacity source:        {D5_CSV}"
)

print("\nSOURCE-READ MATERIAL / SCREEN VALUES")
print("-" * 124)
print(
    f"300M yield:                       {Sy_MPa:.3f} MPa  ({Sy_name})"
)
print(
    f"300M ultimate:                    {Su_MPa:.3f} MPa  ({Su_name})"
)
print(
    f"Pure-shear yield screen:          {tau_yield_allow_MPa:.3f} MPa"
)
print(
    f"Pure-shear ultimate screen:       {tau_ultimate_allow_MPa:.3f} MPa"
)
print(
    f"AMS 4640 static bearing screen:   {bronze_capacity_MPa:.3f} MPa  ({bronze_source_col})"
)

print("\nD9 MECHANICS / SENSITIVITY RETAINED")
print("-" * 124)
print(
    f"Journal diameters:                "
    f"{', '.join(f'{x:.0f}' for x in journal_diameter_values_mm)} mm"
)
print(
    f"Bearing widths:                   "
    f"{', '.join(f'{x:.0f}' for x in bearing_width_values_mm)} mm"
)
print(
    f"Support spans:                    "
    f"{', '.join(f'{x:.0f}' for x in support_span_values_mm)} mm"
)
print(
    f"Kt bending sensitivities:         "
    f"{', '.join(f'{x:.1f}' for x in Kt_values)}"
)
print(
    f"Root-to-bearing-edge clearance:   {root_clearance_mm:.3f} mm (old D9 working assumption)"
)

print("\nMINIMUM PASSING DIAMETER — 5 mm LIGAMENT SENSITIVITY")
print("-" * 124)
print(
    f"{'Span':>6}"
    f"{'Bw':>6}"
    f"{'Kt':>6}"
    f"{'d_min':>8}"
    f"{'z>U':>10}"
    f"{'Ult VM':>12}"
    f"{'MSu':>10}"
    f"{'p_ult':>12}"
    f"{'MSp':>10}"
)
print("-" * 86)

display = minimum_df.loc[
    np.isclose(
        minimum_df[
            "ligament_mm"
        ],
        5.0,
    )
].sort_values(
    [
        "support_span_mm",
        "bearing_width_mm",
        "Kt_bending",
    ]
)

for _, row in display.iterrows():

    if pd.isna(
        row[
            "minimum_passing_diameter_mm"
        ]
    ):
        print(
            f"{row['support_span_mm']:>6.0f}"
            f"{row['bearing_width_mm']:>6.0f}"
            f"{row['Kt_bending']:>6.1f}"
            f"{'NO PASS':>8}"
        )
    else:
        print(
            f"{row['support_span_mm']:>6.0f}"
            f"{row['bearing_width_mm']:>6.0f}"
            f"{row['Kt_bending']:>6.1f}"
            f"{row['minimum_passing_diameter_mm']:>8.0f}"
            f"{row['station_above_U_mm']:>10.1f}"
            f"{row['ultimate_vm_MPa']:>12.1f}"
            f"{row['MS_ultimate_strength']:>10.3f}"
            f"{row['ultimate_bearing_pressure_MPa']:>12.1f}"
            f"{row['MS_ultimate_bearing']:>10.3f}"
        )

print("\nROBUST-WITHIN-SCREEN CANDIDATES")
print("-" * 124)
print(
    "Definition: same geometry passes every D9 Kt sensitivity through "
    f"Kt={max(Kt_values):.1f}. This is NOT final fillet validation."
)

robust_pass_df = (
    robust_df.loc[
        robust_df[
            "ROBUST_WITHIN_SCREEN"
        ]
    ]
    .sort_values(
        [
            "journal_diameter_mm",
            "support_span_mm",
            "bearing_width_mm",
            "ligament_mm",
        ]
    )
)

if robust_pass_df.empty:
    print(
        "No geometry in the inherited D9 sweep passes all Kt sensitivities."
    )
else:
    print(
        f"{'d':>6}"
        f"{'Lig':>6}"
        f"{'Span':>8}"
        f"{'Bw':>6}"
        f"{'z>U':>10}"
        f"{'worst MSu':>12}"
        f"{'p_ult':>12}"
        f"{'MSp':>10}"
    )
    print("-" * 78)

    # Show the first 30 to keep console readable.
    for _, row in robust_pass_df.head(
        30
    ).iterrows():
        print(
            f"{row['journal_diameter_mm']:>6.0f}"
            f"{row['ligament_mm']:>6.0f}"
            f"{row['support_span_mm']:>8.0f}"
            f"{row['bearing_width_mm']:>6.0f}"
            f"{row['station_above_U_mm']:>10.1f}"
            f"{row['worst_MS_ultimate_strength']:>12.3f}"
            f"{row['ultimate_bearing_pressure_MPa']:>12.1f}"
            f"{row['worst_MS_ultimate_bearing']:>10.3f}"
        )

print("\nINTERPRETATION")
print("-" * 124)
print(
    "1. This is the first E3 sizing step where physical centerline geometry and journal strength are coupled."
)
print(
    "2. A smaller support span reduces package width but strongly increases journal radial reaction."
)
print(
    "3. A wider bearing lowers projected bearing pressure but increases the journal-root bending lever arm."
)
print(
    "4. Ligament remains a NON-FROZEN geometric sensitivity; passing it here does not validate the solid-head ligament itself."
)
print(
    "5. The next freeze decision should be based on a practical candidate, not the mathematical minimum diameter."
)

print("\nOUTPUT FILES")
print("-" * 124)
print(
    f"Full design sweep:                {OUTPUT_SWEEP}"
)
print(
    f"Minimum passing by layout:        {OUTPUT_MIN}"
)
print(
    f"Robust candidate summary:         {OUTPUT_ROBUST}"
)
print(
    f"Summary:                          {OUTPUT_SUMMARY}"
)

# Compact text summary.
summary_lines = [
    "=" * 124,
    " PHASE 2E3-B2 — COUPLED TRUNNION JOURNAL / BEARING / Kt SIZING V0.1",
    "=" * 124,
    "",
    f"300M yield: {Sy_MPa:.3f} MPa ({Sy_name})",
    f"300M ultimate: {Su_MPa:.3f} MPa ({Su_name})",
    f"AMS 4640 static bearing screen: {bronze_capacity_MPa:.3f} MPa",
    f"Kt sweep: {Kt_values}",
    "",
    f"Total coupled designs evaluated: {len(design_df)}",
    f"Robust-within-screen geometries: {int(robust_df['ROBUST_WITHIN_SCREEN'].sum())}",
    "",
    "No final trunnion dimension is frozen by this script.",
    "Next step: select/review one practical geometry and audit solid-head/lug architecture around it.",
    "=" * 124,
]

OUTPUT_SUMMARY.write_text(
    "\n".join(
        summary_lines
    ),
    encoding="utf-8",
)

print("=" * 124)
