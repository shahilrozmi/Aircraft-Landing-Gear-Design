from pathlib import Path
import ast
import re

import numpy as np
import pandas as pd


# =============================================================================
# LANDING GEAR DESIGN PROJECT
# PHASE 2E3-B3 — PRACTICAL TRUNNION SHORTLIST / HEAD-INTEGRATION AUDIT V0.1
#
# PURPOSE
#   Convert the large Phase 2E3-B2 coupled sweep into a small engineering
#   shortlist WITHOUT freezing a final trunnion design prematurely.
#
#   This script:
#       1. requires a candidate geometry to pass the FULL inherited Kt sweep,
#       2. requires the SAME diameter/span/bearing-width geometry to remain
#          robust across ALL B1 ligament sensitivities (5/10/15/20 mm),
#       3. identifies the minimum robust diameter for each support-span /
#          bearing-width layout,
#       4. reconstructs the D9 root-to-root head-boss width implied by the
#          support span, bearing width, and root clearance,
#       5. compares that boss width with the frozen 74 mm barrel OD,
#       6. audits the material/interface issue:
#              D9 journal = solid 300M
#              E2 barrel/head architecture = 7075-T6 baseline
#
#   IMPORTANT
#   ---------
#   This script does NOT claim that the 7075 head locally passes trunnion loads.
#   It does NOT size a steel/aluminum joint.
#   It does NOT freeze the final ligament.
#
#   The purpose is to determine which trunnion families are worth carrying into
#   the next local-head/interface design step.
#
# OUTPUTS
#   phase2e3b3_layout_shortlist.csv
#   phase2e3b3_span_anchor_candidates.csv
#   phase2e3b3_material_interface_audit.csv
#   phase2e3b3_summary.txt
# =============================================================================


HERE = Path(__file__).resolve().parent

B2_SWEEP = HERE / "phase2e3b2_trunnion_design_sweep.csv"
B2_ROBUST = HERE / "phase2e3b2_robust_candidate_summary.csv"

D9_PY = HERE / "phase2_upper_trunnion_sizing.py"
BARREL_PY = HERE / "phase2_barrel_sizing.py"
TRACEABILITY = HERE / "phase2_traceability_register_v1.csv"
E2_BASELINE = HERE / "phase2e2_v1_baseline.csv"

OUTPUT_LAYOUT = HERE / "phase2e3b3_layout_shortlist.csv"
OUTPUT_ANCHORS = HERE / "phase2e3b3_span_anchor_candidates.csv"
OUTPUT_INTERFACE = HERE / "phase2e3b3_material_interface_audit.csv"
OUTPUT_SUMMARY = HERE / "phase2e3b3_summary.txt"


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


def ast_literal_assignments(path):
    if not path.exists():
        return {}

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
        if not isinstance(
            node,
            ast.Assign,
        ):
            continue

        try:
            value = ast.literal_eval(
                node.value
            )
        except Exception:
            continue

        for target in node.targets:
            if isinstance(
                target,
                ast.Name,
            ):
                values[
                    target.id
                ] = value

    return values


def source_has(path, pattern):
    if not path.exists():
        return False

    text = path.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    return re.search(
        pattern,
        text,
        flags=re.IGNORECASE,
    ) is not None


def find_parameter(df, names):
    if df is None:
        return None

    cols = {
        "".join(
            ch
            for ch in str(col).lower()
            if ch.isalnum()
        ): col
        for col in df.columns
    }

    pcol = cols.get(
        "parameter"
    )

    vcol = cols.get(
        "value"
    )

    if pcol is None or vcol is None:
        return None

    pnorm = (
        df[pcol]
        .astype(str)
        .map(
            lambda x: "".join(
                ch
                for ch in x.lower()
                if ch.isalnum()
            )
        )
    )

    for name in names:
        key = "".join(
            ch
            for ch in name.lower()
            if ch.isalnum()
        )

        rows = df.loc[
            pnorm == key
        ]

        if not rows.empty:
            return rows.iloc[0][
                vcol
            ]

    return None


# =============================================================================
# READ B2 RESULTS
# =============================================================================

sweep = read_csv(
    B2_SWEEP
)

robust = read_csv(
    B2_ROBUST
)

required_robust_cols = [
    "journal_diameter_mm",
    "ligament_mm",
    "station_above_U_mm",
    "support_span_mm",
    "bearing_width_mm",
    "max_Kt_checked",
    "ROBUST_WITHIN_SCREEN",
    "worst_MS_ultimate_strength",
    "ultimate_bearing_pressure_MPa",
    "worst_MS_ultimate_bearing",
]

for col in required_robust_cols:
    if col not in robust.columns:
        raise KeyError(
            f"B2 robust-summary column missing: {col}"
        )


# Normalize boolean robust field.
robust[
    "ROBUST_WITHIN_SCREEN"
] = (
    robust[
        "ROBUST_WITHIN_SCREEN"
    ]
    .astype(str)
    .str.strip()
    .str.lower()
    .isin(
        [
            "true",
            "1",
            "yes",
        ]
    )
)


# =============================================================================
# SOURCE-READ D9 GEOMETRY
# =============================================================================

d9 = ast_literal_assignments(
    D9_PY
)

root_clearance_mm = float(
    d9[
        "root_clearance_mm"
    ]
)

support_spans_mm = [
    float(x)
    for x in d9[
        "support_span_values_mm"
    ]
]

bearing_widths_mm = [
    float(x)
    for x in d9[
        "bearing_width_values_mm"
    ]
]

Kt_values = [
    float(x)
    for x in d9[
        "Kt_values"
    ]
]

expected_ligaments = sorted(
    float(x)
    for x in robust[
        "ligament_mm"
    ].dropna().unique()
)


# =============================================================================
# FROZEN BARREL OD
# =============================================================================

barrel_OD_mm = np.nan

if E2_BASELINE.exists():
    e2 = read_csv(
        E2_BASELINE
    )

    value = find_parameter(
        e2,
        [
            "barrel_OD",
            "barrel_OD_mm",
        ],
    )

    if value is not None:
        try:
            barrel_OD_mm = float(
                value
            )
        except Exception:
            pass

# Fallback to known retained Phase 2E2 baseline only if source CSV explicitly
# did not expose the value. We do not hide this fallback.
barrel_OD_source = (
    "phase2e2_v1_baseline.csv"
    if np.isfinite(
        barrel_OD_mm
    )
    else "PROJECT_FROZEN_BASELINE_FALLBACK"
)

if not np.isfinite(
    barrel_OD_mm
):
    barrel_OD_mm = 74.0


# =============================================================================
# REQUIRE ROBUSTNESS ACROSS ALL LIGAMENT SENSITIVITIES
# =============================================================================

geometry_group_cols = [
    "journal_diameter_mm",
    "support_span_mm",
    "bearing_width_mm",
]

geometry_rows = []

for key, group in robust.groupby(
    geometry_group_cols,
    sort=True,
):

    diameter_mm, span_mm, bearing_width_mm = [
        float(x)
        for x in key
    ]

    ligaments_present = sorted(
        float(x)
        for x in group[
            "ligament_mm"
        ].unique()
    )

    full_ligament_coverage = (
        ligaments_present
        == expected_ligaments
    )

    robust_all_ligaments = (
        full_ligament_coverage
        and bool(
            group[
                "ROBUST_WITHIN_SCREEN"
            ].all()
        )
    )

    # D9 journal root lever:
    #   root -> bearing load centroid = g + L_b/2
    root_lever_mm = (
        root_clearance_mm
        + bearing_width_mm / 2.0
    )

    # With support planes at +/-s/2 and symmetric journals, the implied
    # root-face separation is:
    root_to_root_head_width_mm = (
        span_mm
        - 2.0 * root_lever_mm
    )

    boss_extension_each_side_mm = (
        (
            root_to_root_head_width_mm
            - barrel_OD_mm
        )
        / 2.0
    )

    # If a through-shaft were centered through an otherwise 74 mm circular
    # head envelope, this is the nominal transverse radial ligament. This is
    # ONLY a geometric diagnostic, not a structural proof.
    nominal_side_ligament_if_74mm_head_mm = (
        (
            barrel_OD_mm
            - diameter_mm
        )
        / 2.0
    )

    worst_strength_idx = (
        group[
            "worst_MS_ultimate_strength"
        ].idxmin()
    )

    worst_bearing_idx = (
        group[
            "worst_MS_ultimate_bearing"
        ].idxmin()
    )

    worst_strength = group.loc[
        worst_strength_idx
    ]

    worst_bearing = group.loc[
        worst_bearing_idx
    ]

    geometry_rows.append({
        "journal_diameter_mm":
            diameter_mm,
        "support_span_mm":
            span_mm,
        "bearing_width_mm":
            bearing_width_mm,
        "root_clearance_mm":
            root_clearance_mm,
        "root_lever_mm":
            root_lever_mm,
        "root_to_root_head_width_mm":
            root_to_root_head_width_mm,
        "barrel_OD_mm":
            barrel_OD_mm,
        "boss_extension_each_side_vs_barrel_mm":
            boss_extension_each_side_mm,
        "nominal_side_ligament_if_74mm_head_mm":
            nominal_side_ligament_if_74mm_head_mm,
        "ligaments_checked_mm":
            ",".join(
                f"{x:.0f}"
                for x in ligaments_present
            ),
        "full_ligament_coverage":
            full_ligament_coverage,
        "ROBUST_ALL_LIGAMENTS_AND_Kt":
            robust_all_ligaments,
        "worst_MS_ultimate_strength_over_ligaments":
            float(
                worst_strength[
                    "worst_MS_ultimate_strength"
                ]
            ),
        "worst_strength_ligament_mm":
            float(
                worst_strength[
                    "ligament_mm"
                ]
            ),
        "worst_MS_ultimate_bearing_over_ligaments":
            float(
                worst_bearing[
                    "worst_MS_ultimate_bearing"
                ]
            ),
        "worst_bearing_pressure_MPa":
            float(
                worst_bearing[
                    "ultimate_bearing_pressure_MPa"
                ]
            ),
        "max_Kt_checked":
            float(
                group[
                    "max_Kt_checked"
                ].max()
            ),
    })


geometry_df = pd.DataFrame(
    geometry_rows
)

robust_geometry = geometry_df.loc[
    geometry_df[
        "ROBUST_ALL_LIGAMENTS_AND_Kt"
    ]
].copy()


# =============================================================================
# MINIMUM ROBUST DIAMETER FOR EACH SPAN / BEARING WIDTH
# =============================================================================

layout_rows = []

for (
    span_mm,
    bearing_width_mm,
), group in geometry_df.groupby(
    [
        "support_span_mm",
        "bearing_width_mm",
    ],
    sort=True,
):

    passing = (
        group.loc[
            group[
                "ROBUST_ALL_LIGAMENTS_AND_Kt"
            ]
        ]
        .sort_values(
            "journal_diameter_mm"
        )
    )

    if passing.empty:
        layout_rows.append({
            "support_span_mm":
                span_mm,
            "bearing_width_mm":
                bearing_width_mm,
            "minimum_robust_diameter_mm":
                np.nan,
            "root_to_root_head_width_mm":
                np.nan,
            "boss_extension_each_side_vs_barrel_mm":
                np.nan,
            "worst_MS_ultimate_strength":
                np.nan,
            "worst_bearing_pressure_MPa":
                np.nan,
            "worst_MS_ultimate_bearing":
                np.nan,
            "status":
                "NO_ROBUST_GEOMETRY",
        })
    else:
        first = passing.iloc[
            0
        ]

        layout_rows.append({
            "support_span_mm":
                span_mm,
            "bearing_width_mm":
                bearing_width_mm,
            "minimum_robust_diameter_mm":
                first[
                    "journal_diameter_mm"
                ],
            "root_to_root_head_width_mm":
                first[
                    "root_to_root_head_width_mm"
                ],
            "boss_extension_each_side_vs_barrel_mm":
                first[
                    "boss_extension_each_side_vs_barrel_mm"
                ],
            "worst_MS_ultimate_strength":
                first[
                    "worst_MS_ultimate_strength_over_ligaments"
                ],
            "worst_bearing_pressure_MPa":
                first[
                    "worst_bearing_pressure_MPa"
                ],
            "worst_MS_ultimate_bearing":
                first[
                    "worst_MS_ultimate_bearing_over_ligaments"
                ],
            "status":
                "ROBUST_ACROSS_ALL_Kt_AND_LIGAMENTS",
        })


layout_df = pd.DataFrame(
    layout_rows
)

layout_df.to_csv(
    OUTPUT_LAYOUT,
    index=False,
)


# =============================================================================
# ONE COMPACT "ANCHOR" PER SUPPORT SPAN
#
# For each support span:
#   1. minimum robust journal diameter,
#   2. among equal diameters, minimum root-to-root head width,
#   3. among remaining ties, maximum worst strength margin.
#
# This is a deterministic SHORTLIST rule, not a final design selection.
# =============================================================================

anchor_rows = []

for span_mm, group in robust_geometry.groupby(
    "support_span_mm",
    sort=True,
):

    min_d = group[
        "journal_diameter_mm"
    ].min()

    subset = group.loc[
        np.isclose(
            group[
                "journal_diameter_mm"
            ],
            min_d,
        )
    ].copy()

    min_head_width = subset[
        "root_to_root_head_width_mm"
    ].min()

    subset = subset.loc[
        np.isclose(
            subset[
                "root_to_root_head_width_mm"
            ],
            min_head_width,
        )
    ].copy()

    subset = subset.sort_values(
        "worst_MS_ultimate_strength_over_ligaments",
        ascending=False,
    )

    chosen = subset.iloc[
        0
    ]

    anchor_rows.append({
        "support_span_mm":
            chosen[
                "support_span_mm"
            ],
        "journal_diameter_mm":
            chosen[
                "journal_diameter_mm"
            ],
        "bearing_width_mm":
            chosen[
                "bearing_width_mm"
            ],
        "root_to_root_head_width_mm":
            chosen[
                "root_to_root_head_width_mm"
            ],
        "boss_extension_each_side_vs_barrel_mm":
            chosen[
                "boss_extension_each_side_vs_barrel_mm"
            ],
        "nominal_side_ligament_if_74mm_head_mm":
            chosen[
                "nominal_side_ligament_if_74mm_head_mm"
            ],
        "worst_MS_ultimate_strength_over_ligaments":
            chosen[
                "worst_MS_ultimate_strength_over_ligaments"
            ],
        "worst_bearing_pressure_MPa":
            chosen[
                "worst_bearing_pressure_MPa"
            ],
        "worst_MS_ultimate_bearing_over_ligaments":
            chosen[
                "worst_MS_ultimate_bearing_over_ligaments"
            ],
        "max_Kt_checked":
            chosen[
                "max_Kt_checked"
            ],
        "status":
            "SPAN_ANCHOR_ONLY_NOT_FINAL",
    })


anchors_df = pd.DataFrame(
    anchor_rows
)

anchors_df.to_csv(
    OUTPUT_ANCHORS,
    index=False,
)


# =============================================================================
# MATERIAL / INTERFACE AUDIT
# =============================================================================

d9_300M = source_has(
    D9_PY,
    r"solid\s+300M[-\s]*steel\s+cantilever\s+root",
)

traceability_df = (
    read_csv(
        TRACEABILITY
    )
    if TRACEABILITY.exists()
    else None
)

barrel_material_text = ""

if traceability_df is not None:
    text_blob = " ".join(
        traceability_df.astype(
            str
        ).fillna(
            ""
        ).values.flatten()
    )

    if re.search(
        r"7075",
        text_blob,
        flags=re.IGNORECASE,
    ):
        barrel_material_text = (
            "7075-T6 baseline appears in traceability register"
        )

# Fallback project baseline, explicitly labeled as such.
if not barrel_material_text:
    barrel_material_text = (
        "7075-T6 PROJECT FROZEN BASELINE "
        "(traceability text token not automatically found)"
    )

interface_rows = [
    {
        "audit_item":
            "Trunnion journal material",
        "finding":
            (
                "D9 explicitly models each journal as a solid 300M-steel "
                "cantilever root."
                if d9_300M
                else
                "D9 300M journal wording not automatically found."
            ),
        "status":
            (
                "SOURCE_CONFIRMED"
                if d9_300M
                else "REVIEW"
            ),
        "design_consequence":
            (
                "B2 journal stress results are valid only for the D9 "
                "300M journal concept and its preliminary allowable convention."
            ),
    },
    {
        "audit_item":
            "Barrel / upper-head material baseline",
        "finding":
            barrel_material_text,
        "status":
            "PROJECT_BASELINE",
        "design_consequence":
            (
                "A 300M journal cannot be silently treated as integral with "
                "a 7075-T6 barrel/head. A real material/interface architecture "
                "must be defined."
            ),
    },
    {
        "audit_item":
            "Steel-to-head load-transfer interface",
        "finding":
            (
                "No frozen E2/D9 definition of how the 300M trunnion journal "
                "is structurally fixed to the upper head was identified by "
                "this audit."
            ),
        "status":
            "OPEN_BLOCKING_FINAL_FREEZE",
        "design_consequence":
            (
                "Do not freeze final trunnion diameter/station until the "
                "journal-to-head load path is selected and screened."
            ),
    },
    {
        "audit_item":
            "Working architecture A",
        "finding":
            (
                "300M through-trunnion / cross-shaft rigidly captured by a "
                "locally enlarged 7075-T6 solid head boss."
            ),
        "status":
            "CANDIDATE",
        "design_consequence":
            (
                "Preserves E2 aluminum barrel/head baseline and D9 300M journal "
                "allowables, but requires shaft-to-head bearing/contact, retention, "
                "fretting/fatigue and local 7075 boss checks."
            ),
    },
    {
        "audit_item":
            "Working architecture B",
        "finding":
            (
                "Separate 300M trunnion/head module joined structurally to the "
                "7075-T6 barrel above the pressure closure."
            ),
        "status":
            "CANDIDATE",
        "design_consequence":
            (
                "Allows integral steel journals but introduces a major steel-to-"
                "aluminum barrel/head joint carrying the upper structural loads."
            ),
    },
    {
        "audit_item":
            "Working architecture C",
        "finding":
            (
                "Integral 7075-T6 trunnion journals formed with the upper head."
            ),
        "status":
            "CANDIDATE_REQUIRES_RESIZING",
        "design_consequence":
            (
                "Invalidates the current 300M journal sizing and would require a "
                "new journal/wear-surface sizing study."
            ),
    },
]

interface_df = pd.DataFrame(
    interface_rows
)

interface_df.to_csv(
    OUTPUT_INTERFACE,
    index=False,
)


# =============================================================================
# CONSOLE REPORT
# =============================================================================

print("=" * 124)
print(
    " PHASE 2E3-B3 — PRACTICAL TRUNNION SHORTLIST / HEAD-INTEGRATION AUDIT V0.1"
)
print("=" * 124)

print("\nB2 ROBUSTNESS REQUIREMENT")
print("-" * 124)
print(
    f"Kt values required:               "
    f"{', '.join(f'{x:.1f}' for x in Kt_values)}"
)
print(
    f"Ligament sensitivities required:  "
    f"{', '.join(f'{x:.0f}' for x in expected_ligaments)} mm"
)
print(
    "A geometry is carried forward only if it passes the FULL Kt sweep at EVERY ligament sensitivity."
)

print("\nSOURCE / PACKAGING GEOMETRY")
print("-" * 124)
print(
    f"Frozen barrel OD:                 {barrel_OD_mm:.3f} mm  ({barrel_OD_source})"
)
print(
    f"D9 root clearance:                {root_clearance_mm:.3f} mm"
)

print("\nMINIMUM ROBUST DIAMETER BY SUPPORT SPAN / BEARING WIDTH")
print("-" * 124)
print(
    f"{'Span':>6}"
    f"{'Bw':>6}"
    f"{'d_min':>8}"
    f"{'Head W':>10}"
    f"{'Boss/side':>12}"
    f"{'worst MSu':>12}"
    f"{'p_ult':>12}"
    f"{'MSp':>10}"
)
print("-" * 82)

for _, row in layout_df.sort_values(
    [
        "support_span_mm",
        "bearing_width_mm",
    ]
).iterrows():

    if pd.isna(
        row[
            "minimum_robust_diameter_mm"
        ]
    ):
        print(
            f"{row['support_span_mm']:>6.0f}"
            f"{row['bearing_width_mm']:>6.0f}"
            f"{'NO PASS':>8}"
        )
    else:
        print(
            f"{row['support_span_mm']:>6.0f}"
            f"{row['bearing_width_mm']:>6.0f}"
            f"{row['minimum_robust_diameter_mm']:>8.0f}"
            f"{row['root_to_root_head_width_mm']:>10.1f}"
            f"{row['boss_extension_each_side_vs_barrel_mm']:>12.1f}"
            f"{row['worst_MS_ultimate_strength']:>12.3f}"
            f"{row['worst_bearing_pressure_MPa']:>12.1f}"
            f"{row['worst_MS_ultimate_bearing']:>10.3f}"
        )

print("\nSPAN ANCHOR SHORTLIST")
print("-" * 124)
print(
    "Rule: minimum robust diameter for the span; then most compact root-to-root head width. "
    "ANCHOR ONLY — not final."
)
print(
    f"{'Span':>6}"
    f"{'d':>6}"
    f"{'Bw':>6}"
    f"{'Head W':>10}"
    f"{'Boss/side':>12}"
    f"{'Side lig*':>12}"
    f"{'worst MSu':>12}"
    f"{'p_ult':>12}"
)
print("-" * 82)

for _, row in anchors_df.sort_values(
    "support_span_mm"
).iterrows():
    print(
        f"{row['support_span_mm']:>6.0f}"
        f"{row['journal_diameter_mm']:>6.0f}"
        f"{row['bearing_width_mm']:>6.0f}"
        f"{row['root_to_root_head_width_mm']:>10.1f}"
        f"{row['boss_extension_each_side_vs_barrel_mm']:>12.1f}"
        f"{row['nominal_side_ligament_if_74mm_head_mm']:>12.1f}"
        f"{row['worst_MS_ultimate_strength_over_ligaments']:>12.3f}"
        f"{row['worst_bearing_pressure_MPa']:>12.1f}"
    )

print(
    "\n*Side lig = purely geometric (74 mm envelope - journal diameter)/2; "
    "NOT a validated 7075-T6 local ligament."
)

print("\nMATERIAL / INTERFACE AUDIT")
print("-" * 124)
print(
    interface_df[
        [
            "audit_item",
            "status",
            "finding",
        ]
    ].to_string(
        index=False,
    )
)

print("\nB3 DISPOSITION")
print("-" * 124)
print(
    "PASS FOR SHORTLISTING — the B2 sweep can now be reduced to a few practical support-span families."
)
print(
    "HOLD FINAL FREEZE — D9 sizes a 300M journal while the frozen E2 barrel/head baseline is 7075-T6."
)
print(
    "Next step must define and screen the journal-to-solid-head interface before a final trunnion candidate is frozen."
)

print("\nOUTPUT FILES")
print("-" * 124)
print(
    f"Layout shortlist:                 {OUTPUT_LAYOUT}"
)
print(
    f"Span anchors:                     {OUTPUT_ANCHORS}"
)
print(
    f"Material/interface audit:         {OUTPUT_INTERFACE}"
)
print(
    f"Summary:                          {OUTPUT_SUMMARY}"
)

summary = [
    "=" * 124,
    " PHASE 2E3-B3 — PRACTICAL TRUNNION SHORTLIST / HEAD-INTEGRATION AUDIT V0.1",
    "=" * 124,
    "",
    f"Frozen barrel OD: {barrel_OD_mm:.3f} mm ({barrel_OD_source})",
    f"Required Kt sweep: {Kt_values}",
    f"Required ligament sensitivities: {expected_ligaments} mm",
    "",
    "Disposition:",
    "  PASS for practical shortlist.",
    "  HOLD final trunnion freeze until the 300M-journal / 7075-head interface is defined.",
    "",
    "The current B2 journal strengths do not themselves validate the local 7075-T6 upper head.",
    "=" * 124,
]

OUTPUT_SUMMARY.write_text(
    "\n".join(summary),
    encoding="utf-8",
)

print("=" * 124)


if __name__ == "__main__":
    pass
