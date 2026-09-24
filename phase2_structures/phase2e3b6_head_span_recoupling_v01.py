from pathlib import Path
import io
import runpy
from contextlib import redirect_stdout

import numpy as np
import pandas as pd


# =============================================================================
# LANDING GEAR DESIGN PROJECT
# PHASE 2E3-B6 — TRUNNION SPAN / SOLID-HEAD ENVELOPE RE-COUPLING V0.1
#
# PURPOSE
#   Re-couple the Phase 2E3-B3 trunnion shortlist with the corrected 7075-T6
#   upper-head structural requirement established by B5A/B5B.
#
# WHY THIS IS NECESSARY
#   The earlier 120 mm trunnion-span working candidate implied an 85 mm
#   root-to-root head width. B5B showed that the solid 7075 upper-head neck
#   near the shaft-hole region may require a substantially larger circular-
#   equivalent structural envelope when Kt sensitivity is retained.
#
#   A trunnion support span cannot be frozen independently of that head width.
#
#   This script therefore:
#       1. reuses the B5B solid-neck stress function directly,
#       2. evaluates every B3 robust span/bearing/journal family,
#       3. finds the minimum solid 7075 neck OD required at the bottom of the
#          shaft hole for Kt = 1.0 ... 3.0,
#       4. compares required OD against the B3 root-to-root head width,
#       5. computes available total and per-side geometric reserve,
#       6. identifies which support-span families remain geometrically
#          compatible with the corrected head strength requirement.
#
# IMPORTANT
#   - This is a GLOBAL solid-neck envelope check only.
#   - The transverse shaft hole, boss fillets, steel/aluminum contact, fretting,
#     local net section, and true 3D stresses are still open.
#   - A passing geometry here is only eligible for continued development.
#   - No final support span is frozen by this script.
#
# OUTPUTS
#   phase2e3b6_head_span_compatibility.csv
#   phase2e3b6_family_summary.csv
#   phase2e3b6_working_candidate_record.csv
#   phase2e3b6_summary.txt
# =============================================================================


HERE = Path(__file__).resolve().parent

B3_LAYOUT = HERE / "phase2e3b3_layout_shortlist.csv"
B5B_PY = HERE / "phase2e3b5b_upper_barrel_reinforcement_profile_v01.py"

OUTPUT_COMPAT = HERE / "phase2e3b6_head_span_compatibility.csv"
OUTPUT_FAMILY = HERE / "phase2e3b6_family_summary.csv"
OUTPUT_WORKING = HERE / "phase2e3b6_working_candidate_record.csv"
OUTPUT_SUMMARY = HERE / "phase2e3b6_summary.txt"


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


def near(series, value, atol=1e-9):
    return np.isclose(
        pd.to_numeric(
            series,
            errors="coerce",
        ),
        float(value),
        atol=atol,
        rtol=0.0,
    )


# =============================================================================
# LOAD AUTHORITATIVE B5B MECHANICS WITHOUT REPRINTING ITS REPORT
# =============================================================================

if not B5B_PY.exists():
    raise FileNotFoundError(
        f"Required B5B source not found:\n{B5B_PY}"
    )

with redirect_stdout(
    io.StringIO()
):
    b5b = runpy.run_path(
        str(B5B_PY),
        run_name="phase2e3b5b_reuse_for_b6",
    )


required_b5b = [
    "governing_solid",
    "h_UA_static_m",
    "e2_boundary_above_U_mm",
    "WORKING_LOWER_LIGAMENT_MM",
    "SY_7075_MPa",
    "SU_7075_MPa",
    "KT_VALUES",
]

missing = [
    name
    for name in required_b5b
    if name not in b5b
]

if missing:
    raise KeyError(
        "B5B did not expose required mechanics/constants: "
        + ", ".join(missing)
    )


governing_solid = b5b[
    "governing_solid"
]

h_UA_static_m = float(
    b5b[
        "h_UA_static_m"
    ]
)

e2_boundary_above_U_mm = float(
    b5b[
        "e2_boundary_above_U_mm"
    ]
)

working_lower_ligament_mm = float(
    b5b[
        "WORKING_LOWER_LIGAMENT_MM"
    ]
)

SY_7075_MPa = float(
    b5b[
        "SY_7075_MPa"
    ]
)

SU_7075_MPa = float(
    b5b[
        "SU_7075_MPa"
    ]
)

Kt_values = [
    float(x)
    for x in b5b[
        "KT_VALUES"
    ]
]


# =============================================================================
# B3 ROBUST LAYOUTS
# =============================================================================

layout = read_csv(
    B3_LAYOUT
)

required_cols = [
    "support_span_mm",
    "bearing_width_mm",
    "minimum_robust_diameter_mm",
    "root_to_root_head_width_mm",
    "boss_extension_each_side_vs_barrel_mm",
    "worst_MS_ultimate_strength",
    "worst_bearing_pressure_MPa",
    "worst_MS_ultimate_bearing",
    "status",
]

for col in required_cols:
    if col not in layout.columns:
        raise KeyError(
            f"B3 layout column missing: {col}"
        )


robust_layouts = layout.loc[
    layout[
        "status"
    ].astype(str)
    == "ROBUST_ACROSS_ALL_Kt_AND_LIGAMENTS"
].copy()

if robust_layouts.empty:
    raise ValueError(
        "No robust B3 layouts available."
    )


# =============================================================================
# HEAD-NECK REQUIREMENT
# =============================================================================

shaft_hole_bottom_above_U_mm = (
    e2_boundary_above_U_mm
    + working_lower_ligament_mm
)

shaft_hole_bottom_above_A_mm = (
    h_UA_static_m
    * 1000.0
    + shaft_hole_bottom_above_U_mm
)


def minimum_solid_OD_for_Kt(
    Kt,
    OD_start_mm=74.0,
    OD_stop_mm=140.0,
    OD_step_mm=0.5,
):
    for OD_mm in np.arange(
        OD_start_mm,
        OD_stop_mm + 1e-9,
        OD_step_mm,
    ):
        lim = governing_solid(
            shaft_hole_bottom_above_A_mm,
            OD_mm,
            Kt,
            "limit",
        )

        ult = governing_solid(
            shaft_hole_bottom_above_A_mm,
            OD_mm,
            Kt,
            "ultimate",
        )

        if (
            lim["MS"] >= 0.0
            and ult["MS"] >= 0.0
        ):
            return {
                "minimum_required_OD_mm":
                    float(
                        OD_mm
                    ),
                "limit_case":
                    lim[
                        "case"
                    ],
                "limit_vm_MPa":
                    lim[
                        "vm_MPa"
                    ],
                "MS_limit":
                    lim[
                        "MS"
                    ],
                "ultimate_case":
                    ult[
                        "case"
                    ],
                "ultimate_vm_MPa":
                    ult[
                        "vm_MPa"
                    ],
                "MS_ultimate":
                    ult[
                        "MS"
                    ],
            }

    return {
        "minimum_required_OD_mm":
            np.nan,
        "limit_case":
            "",
        "limit_vm_MPa":
            np.nan,
        "MS_limit":
            np.nan,
        "ultimate_case":
            "",
        "ultimate_vm_MPa":
            np.nan,
        "MS_ultimate":
            np.nan,
    }


head_requirement_by_Kt = {
    Kt:
        minimum_solid_OD_for_Kt(
            Kt
        )
    for Kt in Kt_values
}


# =============================================================================
# COMPATIBILITY MATRIX
# =============================================================================

compat_rows = []

for _, candidate in robust_layouts.iterrows():

    span_mm = float(
        candidate[
            "support_span_mm"
        ]
    )

    bearing_width_mm = float(
        candidate[
            "bearing_width_mm"
        ]
    )

    diameter_mm = float(
        candidate[
            "minimum_robust_diameter_mm"
        ]
    )

    head_width_mm = float(
        candidate[
            "root_to_root_head_width_mm"
        ]
    )

    shaft_center_above_U_mm = (
        shaft_hole_bottom_above_U_mm
        + diameter_mm / 2.0
    )

    for Kt in Kt_values:

        req = head_requirement_by_Kt[
            Kt
        ]

        required_OD_mm = float(
            req[
                "minimum_required_OD_mm"
            ]
        )

        if np.isfinite(
            required_OD_mm
        ):
            total_width_reserve_mm = (
                head_width_mm
                - required_OD_mm
            )

            per_side_width_reserve_mm = (
                total_width_reserve_mm
                / 2.0
            )

            geometry_compatible = (
                total_width_reserve_mm
                >= 0.0
            )
        else:
            total_width_reserve_mm = (
                np.nan
            )

            per_side_width_reserve_mm = (
                np.nan
            )

            geometry_compatible = False

        compat_rows.append({
            "support_span_mm":
                span_mm,
            "bearing_width_mm":
                bearing_width_mm,
            "journal_diameter_mm":
                diameter_mm,
            "root_to_root_head_width_mm":
                head_width_mm,

            "working_lower_ligament_mm":
                working_lower_ligament_mm,
            "shaft_hole_bottom_above_U_mm":
                shaft_hole_bottom_above_U_mm,
            "shaft_center_above_U_mm":
                shaft_center_above_U_mm,

            "Kt_bending":
                Kt,
            "minimum_required_solid_neck_OD_mm":
                required_OD_mm,

            "head_width_total_reserve_mm":
                total_width_reserve_mm,
            "head_width_reserve_each_side_mm":
                per_side_width_reserve_mm,

            "global_neck_geometry_compatible":
                geometry_compatible,

            "limit_case":
                req[
                    "limit_case"
                ],
            "limit_vm_MPa_at_min_OD":
                req[
                    "limit_vm_MPa"
                ],
            "MS_limit_at_min_OD":
                req[
                    "MS_limit"
                ],

            "ultimate_case":
                req[
                    "ultimate_case"
                ],
            "ultimate_vm_MPa_at_min_OD":
                req[
                    "ultimate_vm_MPa"
                ],
            "MS_ultimate_at_min_OD":
                req[
                    "MS_ultimate"
                ],

            "B3_worst_MS_ultimate_journal":
                candidate[
                    "worst_MS_ultimate_strength"
                ],
            "B3_worst_bearing_pressure_MPa":
                candidate[
                    "worst_bearing_pressure_MPa"
                ],
            "B3_worst_MS_ultimate_bearing":
                candidate[
                    "worst_MS_ultimate_bearing"
                ],
        })


compat_df = pd.DataFrame(
    compat_rows
)

compat_df.to_csv(
    OUTPUT_COMPAT,
    index=False,
)


# =============================================================================
# FAMILY SUMMARY
# =============================================================================

family_rows = []

for (
    span_mm,
    bearing_width_mm,
    diameter_mm,
), group in compat_df.groupby(
    [
        "support_span_mm",
        "bearing_width_mm",
        "journal_diameter_mm",
    ],
    sort=True,
):

    full_kt_coverage = (
        set(
            round(
                float(x),
                10,
            )
            for x in group[
                "Kt_bending"
            ]
        )
        ==
        set(
            round(
                float(x),
                10,
            )
            for x in Kt_values
        )
    )

    compatible_all_Kt = (
        full_kt_coverage
        and bool(
            group[
                "global_neck_geometry_compatible"
            ].all()
        )
    )

    kt3 = group.loc[
        near(
            group[
                "Kt_bending"
            ],
            max(
                Kt_values
            ),
        )
    ].iloc[0]

    family_rows.append({
        "support_span_mm":
            span_mm,
        "bearing_width_mm":
            bearing_width_mm,
        "journal_diameter_mm":
            diameter_mm,
        "root_to_root_head_width_mm":
            kt3[
                "root_to_root_head_width_mm"
            ],
        "required_neck_OD_at_max_Kt_mm":
            kt3[
                "minimum_required_solid_neck_OD_mm"
            ],
        "head_total_reserve_at_max_Kt_mm":
            kt3[
                "head_width_total_reserve_mm"
            ],
        "head_reserve_each_side_at_max_Kt_mm":
            kt3[
                "head_width_reserve_each_side_mm"
            ],
        "B3_worst_MS_ultimate_journal":
            kt3[
                "B3_worst_MS_ultimate_journal"
            ],
        "B3_worst_bearing_pressure_MPa":
            kt3[
                "B3_worst_bearing_pressure_MPa"
            ],
        "B3_worst_MS_ultimate_bearing":
            kt3[
                "B3_worst_MS_ultimate_bearing"
            ],
        "COMPATIBLE_ALL_Kt":
            compatible_all_Kt,
    })


family_df = pd.DataFrame(
    family_rows
)

family_df.to_csv(
    OUTPUT_FAMILY,
    index=False,
)


# =============================================================================
# WORKING-CANDIDATE RECORD
# =============================================================================

preferred_mask = (
    near(
        family_df[
            "support_span_mm"
        ],
        150.0,
    )
    &
    near(
        family_df[
            "bearing_width_mm"
        ],
        25.0,
    )
    &
    near(
        family_df[
            "journal_diameter_mm"
        ],
        34.0,
    )
)

preferred_rows = family_df.loc[
    preferred_mask
]

working_rows = []

if len(
    preferred_rows
) == 1:

    candidate = preferred_rows.iloc[
        0
    ]

    if bool(
        candidate[
            "COMPATIBLE_ALL_Kt"
        ]
    ):
        working_rows.append({
            "status":
                "WORKING_CANDIDATE_NOT_FROZEN",
            "support_span_mm":
                candidate[
                    "support_span_mm"
                ],
            "journal_diameter_mm":
                candidate[
                    "journal_diameter_mm"
                ],
            "bearing_width_mm":
                candidate[
                    "bearing_width_mm"
                ],
            "root_to_root_head_width_mm":
                candidate[
                    "root_to_root_head_width_mm"
                ],
            "required_neck_OD_at_Kt3_mm":
                candidate[
                    "required_neck_OD_at_max_Kt_mm"
                ],
            "head_reserve_each_side_at_Kt3_mm":
                candidate[
                    "head_reserve_each_side_at_max_Kt_mm"
                ],
            "B3_worst_MS_ultimate_journal":
                candidate[
                    "B3_worst_MS_ultimate_journal"
                ],
            "B3_worst_bearing_pressure_MPa":
                candidate[
                    "B3_worst_bearing_pressure_MPa"
                ],
            "B3_worst_MS_ultimate_bearing":
                candidate[
                    "B3_worst_MS_ultimate_bearing"
                ],
            "working_lower_ligament_mm":
                working_lower_ligament_mm,
            "reason":
                (
                    "150-mm span provides materially more head-width reserve "
                    "than the 120-mm family while retaining a moderate package "
                    "size. The 34/25 journal/bearing pair avoids the near-zero "
                    "journal margin of the 34/30 alternative and reduces bearing "
                    "pressure versus the 32/20 alternative."
                ),
        })


working_df = pd.DataFrame(
    working_rows
)

working_df.to_csv(
    OUTPUT_WORKING,
    index=False,
)


# =============================================================================
# CONSOLE REPORT
# =============================================================================

print("=" * 124)
print(
    " PHASE 2E3-B6 — TRUNNION SPAN / SOLID-HEAD ENVELOPE RE-COUPLING V0.1"
)
print("=" * 124)

print("\nCORRECTED HEAD REQUIREMENT")
print("-" * 124)
print(
    f"Working lower ligament:           {working_lower_ligament_mm:.1f} mm"
)
print(
    f"Shaft-hole bottom:                {shaft_hole_bottom_above_U_mm:.6f} mm above U"
)
print(
    f"7075 screen:                      {SY_7075_MPa:.1f} / {SU_7075_MPa:.1f} MPa"
)

print("\nMINIMUM SOLID-NECK OD AT SHAFT-HOLE BOTTOM")
print("-" * 124)
print(
    f"{'Kt':>8}"
    f"{'Min OD':>12}"
    f"{'Limit':>12}"
    f"{'MSlim':>10}"
    f"{'Ultimate':>12}"
    f"{'MSult':>10}"
)
print("-" * 68)

for Kt in Kt_values:
    req = head_requirement_by_Kt[
        Kt
    ]

    print(
        f"{Kt:>8.1f}"
        f"{req['minimum_required_OD_mm']:>12.1f}"
        f"{req['limit_vm_MPa']:>12.1f}"
        f"{req['MS_limit']:>10.3f}"
        f"{req['ultimate_vm_MPa']:>12.1f}"
        f"{req['MS_ultimate']:>10.3f}"
    )

print("\nB3 ROBUST LAYOUTS RE-COUPLED TO Kt=3 HEAD REQUIREMENT")
print("-" * 124)
print(
    f"{'Span':>6}"
    f"{'d':>6}"
    f"{'Bw':>6}"
    f"{'Head W':>10}"
    f"{'Req OD':>10}"
    f"{'Reserve':>10}"
    f"{'Res/side':>10}"
    f"{'J MSu':>10}"
    f"{'p_brg':>10}"
    f"{'All Kt':>9}"
)
print("-" * 92)

for _, row in family_df.sort_values(
    [
        "support_span_mm",
        "bearing_width_mm",
    ]
).iterrows():
    print(
        f"{row['support_span_mm']:>6.0f}"
        f"{row['journal_diameter_mm']:>6.0f}"
        f"{row['bearing_width_mm']:>6.0f}"
        f"{row['root_to_root_head_width_mm']:>10.1f}"
        f"{row['required_neck_OD_at_max_Kt_mm']:>10.1f}"
        f"{row['head_total_reserve_at_max_Kt_mm']:>10.1f}"
        f"{row['head_reserve_each_side_at_max_Kt_mm']:>10.1f}"
        f"{row['B3_worst_MS_ultimate_journal']:>10.3f}"
        f"{row['B3_worst_bearing_pressure_MPa']:>10.1f}"
        f"{str(bool(row['COMPATIBLE_ALL_Kt'])):>9}"
    )

print("\nB6 DISPOSITION")
print("-" * 124)

compatible = family_df.loc[
    family_df[
        "COMPATIBLE_ALL_Kt"
    ]
]

if compatible.empty:
    print(
        "No B3 robust layout is geometrically compatible with the corrected Kt=3 solid-head requirement."
    )
    print(
        "A larger support span or different head/trunnion architecture is required."
    )
else:
    spans = sorted(
        compatible[
            "support_span_mm"
        ].unique()
    )

    print(
        "Support-span families remaining compatible through the full Kt sweep: "
        + ", ".join(
            f"{x:.0f} mm"
            for x in spans
        )
    )

if not working_df.empty:
    w = working_df.iloc[0]

    print()
    print(
        "WORKING CANDIDATE FOR NEXT DETAIL STEP — NOT FROZEN:"
    )
    print(
        f"  support span:                  {w['support_span_mm']:.0f} mm"
    )
    print(
        f"  journal diameter:              {w['journal_diameter_mm']:.0f} mm"
    )
    print(
        f"  bearing width:                 {w['bearing_width_mm']:.0f} mm"
    )
    print(
        f"  head root-to-root width:       {w['root_to_root_head_width_mm']:.1f} mm"
    )
    print(
        f"  Kt=3 solid-neck required OD:   {w['required_neck_OD_at_Kt3_mm']:.1f} mm"
    )
    print(
        f"  head reserve each side:        {w['head_reserve_each_side_at_Kt3_mm']:.1f} mm"
    )
    print(
        f"  B3 worst journal ultimate MS:  {w['B3_worst_MS_ultimate_journal']:+.3f}"
    )
    print(
        f"  B3 worst bearing pressure:     {w['B3_worst_bearing_pressure_MPa']:.1f} MPa"
    )
else:
    print()
    print(
        "The predefined 150/34/25 balanced candidate did not survive the corrected head requirement."
    )

print()
print(
    "The 120-mm family must not be retained merely because its journal itself passes; "
    "the head envelope must also fit between journal roots."
)
print(
    "Next: select the reinforced annular-barrel -> solid-head transition around the surviving "
    "working family and screen transition radius / Kt sensitivity."
)

print("\nOUTPUT FILES")
print("-" * 124)
print(
    f"Compatibility matrix:             {OUTPUT_COMPAT}"
)
print(
    f"Family summary:                   {OUTPUT_FAMILY}"
)
print(
    f"Working candidate record:         {OUTPUT_WORKING}"
)
print(
    f"Summary:                          {OUTPUT_SUMMARY}"
)


# =============================================================================
# SUMMARY FILE
# =============================================================================

summary_lines = [
    "=" * 124,
    " PHASE 2E3-B6 — TRUNNION SPAN / SOLID-HEAD ENVELOPE RE-COUPLING V0.1",
    "=" * 124,
    "",
    f"Working lower ligament: {working_lower_ligament_mm:.1f} mm",
    f"Shaft-hole bottom: {shaft_hole_bottom_above_U_mm:.6f} mm above U",
    "",
    "Solid-neck requirement:",
]

for Kt in Kt_values:
    summary_lines.append(
        f"  Kt={Kt:.1f}: OD >= "
        f"{head_requirement_by_Kt[Kt]['minimum_required_OD_mm']:.1f} mm"
    )

summary_lines.append("")

if not working_df.empty:
    w = working_df.iloc[0]
    summary_lines.extend([
        "Working candidate — NOT FROZEN:",
        f"  span = {w['support_span_mm']:.0f} mm",
        f"  journal = {w['journal_diameter_mm']:.0f} mm",
        f"  bearing width = {w['bearing_width_mm']:.0f} mm",
        f"  head width = {w['root_to_root_head_width_mm']:.1f} mm",
        f"  Kt=3 required neck OD = {w['required_neck_OD_at_Kt3_mm']:.1f} mm",
        f"  reserve each side = {w['head_reserve_each_side_at_Kt3_mm']:.1f} mm",
    ])
else:
    summary_lines.append(
        "No predefined working candidate survived."
    )

summary_lines.extend([
    "",
    "No final trunnion span or head OD is frozen.",
    "Next: reinforced barrel-to-solid-head transition geometry / Kt screen.",
    "=" * 124,
])

OUTPUT_SUMMARY.write_text(
    "\n".join(
        summary_lines
    ),
    encoding="utf-8",
)

print("=" * 124)


if __name__ == "__main__":
    pass
