from pathlib import Path
import ast
import math

import numpy as np
import pandas as pd


# =============================================================================
# LANDING GEAR DESIGN PROJECT
# PHASE 2E3-B4 — 300M CROSS-TRUNNION / 7075 HEAD INTERFACE REQUIREMENTS V0.1
#
# PURPOSE
#   Carry the Phase 2E3-B3 shortlist into an explicit upper-head interface
#   requirement study.
#
#   B3 showed that:
#       - D9 journal mechanics are based on solid 300M steel journals.
#       - the frozen E2 barrel / upper-head baseline remains 7075-T6.
#       - the steel-to-aluminum load-transfer interface is the current blocker.
#
#   This script therefore selects Architecture A FOR DETAILED SCREENING ONLY:
#
#       300M cross-trunnion / through-shaft
#       rigidly captured by a locally enlarged 7075-T6 solid upper-head boss.
#
#   IMPORTANT:
#       - this is NOT a final architecture freeze,
#       - no interference fit / spline / key / clamp geometry is invented,
#       - friction is NOT credited,
#       - local 7075 contact / fretting / fatigue is NOT declared solved.
#
#   The script converts the existing B1/B3 results into the interface load
#   requirements that any positive mechanical capture must transmit:
#
#       per-journal radial reaction,
#       full locating-journal axial thrust,
#       journal-root bending moment,
#       equivalent moment-transfer force couple over available half-head width,
#       force-only average projected shaft/head bearing pressure (LOWER BOUND),
#       separate Mx brace / anti-rotation load.
#
#   It also compares the three robust 120-mm-span B3 layouts:
#
#       34 mm journal / 20 mm bearing
#       36 mm journal / 25 mm bearing
#       36 mm journal / 30 mm bearing
#
#   and carries 36 / 25 / 120 as the WORKING INTERFACE STUDY candidate because
#   it reduces head width and bearing pressure relative to 34 / 20 / 120 while
#   retaining meaningful Kt=3 robustness; the 36 / 30 / 120 option is retained
#   only as a comparator because its B3 ultimate margin is nearly exhausted.
#
# OUTPUTS
#   phase2e3b4_interface_load_envelope.csv
#   phase2e3b4_120mm_family_comparison.csv
#   phase2e3b4_architecture_decision.csv
#   phase2e3b4_summary.txt
# =============================================================================


HERE = Path(__file__).resolve().parent

B3_LAYOUT = HERE / "phase2e3b3_layout_shortlist.csv"
B3_ANCHORS = HERE / "phase2e3b3_span_anchor_candidates.csv"
B1_REACTIONS = HERE / "phase2e3b1_trunnion_reaction_trade.csv"
B1_BRACE = HERE / "phase2e3b1_brace_force_trade.csv"

D9_PY = HERE / "phase2_upper_trunnion_sizing.py"
D10_PY = HERE / "phase2_upper_brace_sizing.py"
E2_BASELINE = HERE / "phase2e2_v1_baseline.csv"

OUTPUT_ENVELOPE = HERE / "phase2e3b4_interface_load_envelope.csv"
OUTPUT_FAMILY = HERE / "phase2e3b4_120mm_family_comparison.csv"
OUTPUT_DECISION = HERE / "phase2e3b4_architecture_decision.csv"
OUTPUT_SUMMARY = HERE / "phase2e3b4_summary.txt"


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
            value = ast.literal_eval(
                node.value
            )
        except Exception:
            continue

        for target in node.targets:
            if isinstance(target, ast.Name):
                values[
                    target.id
                ] = value

    return values


def find_parameter(df, aliases):
    if (
        "parameter" not in df.columns
        or "value" not in df.columns
    ):
        return None

    def norm(text):
        return "".join(
            ch
            for ch in str(text).lower()
            if ch.isalnum()
        )

    pnorm = (
        df["parameter"]
        .astype(str)
        .map(norm)
    )

    for alias in aliases:
        rows = df.loc[
            pnorm == norm(alias)
        ]

        if not rows.empty:
            return rows.iloc[0][
                "value"
            ]

    return None


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


def require_one(df, mask, label):
    rows = df.loc[
        mask
    ]

    if len(rows) != 1:
        raise ValueError(
            f"Expected exactly one row for {label}; "
            f"found {len(rows)}."
        )

    return rows.iloc[
        0
    ]


# =============================================================================
# SOURCE DATA
# =============================================================================

layout = read_csv(
    B3_LAYOUT
)

anchors = read_csv(
    B3_ANCHORS
)

reactions = read_csv(
    B1_REACTIONS
)

brace = read_csv(
    B1_BRACE
)

e2 = read_csv(
    E2_BASELINE
)

d9 = ast_literal_assignments(
    D9_PY
)

d10 = ast_literal_assignments(
    D10_PY
)

root_clearance_mm = float(
    d9[
        "root_clearance_mm"
    ]
)

working_brace_arm_mm = float(
    d10.get(
        "working_effective_arm_mm",
        250.0,
    )
)

barrel_OD_mm = float(
    find_parameter(
        e2,
        [
            "barrel_OD",
            "barrel_OD_mm",
        ],
    )
)

e2_boundary_mm = float(
    find_parameter(
        e2,
        [
            "preliminary_E3_interface_outer_face_above_U",
        ],
    )
)


# =============================================================================
# CANDIDATE SET
# =============================================================================

# Robust minimum layouts from B3, 120-mm support-span family.
family120 = layout.loc[
    near(
        layout[
            "support_span_mm"
        ],
        120.0,
    )
    &
    (
        layout[
            "status"
        ].astype(str)
        == "ROBUST_ACROSS_ALL_Kt_AND_LIGAMENTS"
    )
].copy()

if family120.empty:
    raise ValueError(
        "No robust 120-mm-span B3 layouts were found."
    )

# Explicit working interface-study candidate.
working_mask = (
    near(
        family120[
            "bearing_width_mm"
        ],
        25.0,
    )
    &
    near(
        family120[
            "minimum_robust_diameter_mm"
        ],
        36.0,
    )
)

working_row = require_one(
    family120,
    working_mask,
    "120 / 25 / 36 working interface-study candidate",
)


# =============================================================================
# INTERFACE LOAD ENVELOPE FUNCTION
# =============================================================================

def candidate_envelope(
    diameter_mm,
    span_mm,
    bearing_width_mm,
):
    """
    Build an interface load envelope across ALL B1 ligament sensitivities.

    The root bending moment is:
        M_root = R * (g + L_b/2)

    A moment-transfer force-couple requirement is also reported:
        C = M_root / L_eng

    where L_eng is the available half-head width:
        L_eng = W_head / 2

    C is a statics REQUIREMENT only. It is not a contact-pressure solution.

    The force-only average projected pressure:
        p_avg = R / (d * L_eng)

    is explicitly a LOWER BOUND because it ignores the root moment, local contact
    concentration, interference-fit effects, fretting and edge loading.
    """

    root_lever_mm = (
        root_clearance_mm
        + bearing_width_mm / 2.0
    )

    head_width_mm = (
        span_mm
        - 2.0 * root_lever_mm
    )

    if head_width_mm <= 0.0:
        raise ValueError(
            "Computed non-positive head width."
        )

    engagement_half_mm = (
        head_width_mm / 2.0
    )

    rx = reactions.loc[
        near(
            reactions[
                "journal_diameter_mm"
            ],
            diameter_mm,
        )
        &
        near(
            reactions[
                "support_span_mm"
            ],
            span_mm,
        )
    ].copy()

    if rx.empty:
        raise ValueError(
            f"No B1 reaction data found for d={diameter_mm}, "
            f"span={span_mm}."
        )

    br = brace.loc[
        near(
            brace[
                "journal_diameter_mm"
            ],
            diameter_mm,
        )
        &
        near(
            brace[
                "brace_effective_arm_mm"
            ],
            working_brace_arm_mm,
        )
    ].copy()

    if br.empty:
        raise ValueError(
            f"No B1 brace data found for d={diameter_mm}, "
            f"arm={working_brace_arm_mm}."
        )

    out = []

    for ligament_mm in sorted(
        float(x)
        for x in rx[
            "ligament_mm"
        ].unique()
    ):

        rlig = rx.loc[
            near(
                rx[
                    "ligament_mm"
                ],
                ligament_mm,
            )
        ].copy()

        blig = br.loc[
            near(
                br[
                    "ligament_mm"
                ],
                ligament_mm,
            )
        ].copy()

        for level in [
            "limit",
            "ultimate",
        ]:

            sub = rlig.loc[
                rlig[
                    "level"
                ].astype(str)
                .str.lower()
                == level
            ]

            bsub = blig.loc[
                blig[
                    "level"
                ].astype(str)
                .str.lower()
                == level
            ]

            if sub.empty or bsub.empty:
                raise ValueError(
                    f"Missing {level} data at ligament {ligament_mm} mm."
                )

            gov_R = sub.loc[
                sub[
                    "Rmax_kN"
                ].idxmax()
            ]

            gov_Fx = sub.loc[
                sub[
                    "Fx_thrust_kN"
                ].abs().idxmax()
            ]

            gov_brace = bsub.loc[
                bsub[
                    "brace_force_abs_kN"
                ].idxmax()
            ]

            R_kN = float(
                gov_R[
                    "Rmax_kN"
                ]
            )

            Fx_kN = abs(
                float(
                    gov_Fx[
                        "Fx_thrust_kN"
                    ]
                )
            )

            Mroot_kNm = (
                R_kN
                * root_lever_mm
                / 1000.0
            )

            moment_couple_kN = (
                Mroot_kNm
                / (
                    engagement_half_mm
                    / 1000.0
                )
            )

            p_force_only_MPa = (
                R_kN
                * 1000.0
                / (
                    diameter_mm
                    * engagement_half_mm
                )
            )

            resultant_force_kN = math.hypot(
                R_kN,
                Fx_kN,
            )

            out.append({
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
                "head_root_to_root_width_mm":
                    head_width_mm,
                "half_head_engagement_mm":
                    engagement_half_mm,
                "boss_extension_each_side_vs_74mm_barrel_mm":
                    (
                        head_width_mm
                        - barrel_OD_mm
                    ) / 2.0,
                "ligament_mm":
                    ligament_mm,
                "station_above_U_mm":
                    float(
                        gov_R[
                            "station_above_U_mm"
                        ]
                    ),
                "station_above_E2_boundary_mm":
                    float(
                        gov_R[
                            "station_above_U_mm"
                        ]
                    )
                    - e2_boundary_mm,
                "level":
                    level,

                "governing_radial_case":
                    str(
                        gov_R[
                            "case"
                        ]
                    ),
                "per_journal_radial_reaction_kN":
                    R_kN,

                "governing_thrust_case":
                    str(
                        gov_Fx[
                            "case"
                        ]
                    ),
                "full_locating_journal_thrust_kN":
                    Fx_kN,

                "journal_root_bending_moment_kNm":
                    Mroot_kNm,
                "journal_interface_resultant_force_kN":
                    resultant_force_kN,

                "moment_transfer_force_couple_requirement_kN":
                    moment_couple_kN,

                "force_only_avg_projected_shaft_head_pressure_MPa":
                    p_force_only_MPa,

                "governing_brace_case":
                    str(
                        gov_brace[
                            "case"
                        ]
                    ),
                "brace_effective_arm_mm":
                    working_brace_arm_mm,
                "brace_force_abs_kN":
                    float(
                        gov_brace[
                            "brace_force_abs_kN"
                        ]
                    ),

                "contact_pressure_interpretation":
                    (
                        "LOWER_BOUND_FORCE_ONLY; journal-root moment transfer "
                        "requires nonuniform/reversing 3D contact or positive "
                        "mechanical capture."
                    ),
            })

    return pd.DataFrame(
        out
    )


# =============================================================================
# BUILD ENVELOPES
# =============================================================================

envelope_frames = []

for _, row in family120.iterrows():

    diameter_mm = float(
        row[
            "minimum_robust_diameter_mm"
        ]
    )

    span_mm = float(
        row[
            "support_span_mm"
        ]
    )

    bearing_width_mm = float(
        row[
            "bearing_width_mm"
        ]
    )

    frame = candidate_envelope(
        diameter_mm,
        span_mm,
        bearing_width_mm,
    )

    envelope_frames.append(
        frame
    )


envelope = pd.concat(
    envelope_frames,
    ignore_index=True,
)

envelope.to_csv(
    OUTPUT_ENVELOPE,
    index=False,
)


# =============================================================================
# 120-mm FAMILY COMPARISON
# =============================================================================

family_rows = []

for _, row in family120.sort_values(
    "bearing_width_mm"
).iterrows():

    diameter_mm = float(
        row[
            "minimum_robust_diameter_mm"
        ]
    )

    bearing_width_mm = float(
        row[
            "bearing_width_mm"
        ]
    )

    sub = envelope.loc[
        near(
            envelope[
                "journal_diameter_mm"
            ],
            diameter_mm,
        )
        &
        near(
            envelope[
                "support_span_mm"
            ],
            120.0,
        )
        &
        near(
            envelope[
                "bearing_width_mm"
            ],
            bearing_width_mm,
        )
        &
        (
            envelope[
                "level"
            ]
            == "ultimate"
        )
    ]

    # Highest station / 20-mm ligament gives the largest transported moments
    # within the B1 sensitivity sweep.
    worst_station = sub.loc[
        sub[
            "station_above_U_mm"
        ].idxmax()
    ]

    family_rows.append({
        "support_span_mm":
            120.0,
        "journal_diameter_mm":
            diameter_mm,
        "bearing_width_mm":
            bearing_width_mm,
        "head_root_to_root_width_mm":
            float(
                worst_station[
                    "head_root_to_root_width_mm"
                ]
            ),
        "boss_extension_each_side_vs_barrel_mm":
            float(
                worst_station[
                    "boss_extension_each_side_vs_74mm_barrel_mm"
                ]
            ),
        "B3_worst_MS_ultimate_strength":
            float(
                row[
                    "worst_MS_ultimate_strength"
                ]
            ),
        "B3_worst_bearing_pressure_MPa":
            float(
                row[
                    "worst_bearing_pressure_MPa"
                ]
            ),
        "B3_worst_MS_ultimate_bearing":
            float(
                row[
                    "worst_MS_ultimate_bearing"
                ]
            ),
        "interface_envelope_ligament_mm":
            float(
                worst_station[
                    "ligament_mm"
                ]
            ),
        "ultimate_per_journal_radial_reaction_kN":
            float(
                worst_station[
                    "per_journal_radial_reaction_kN"
                ]
            ),
        "ultimate_journal_root_moment_kNm":
            float(
                worst_station[
                    "journal_root_bending_moment_kNm"
                ]
            ),
        "ultimate_moment_transfer_couple_kN":
            float(
                worst_station[
                    "moment_transfer_force_couple_requirement_kN"
                ]
            ),
        "force_only_avg_shaft_head_pressure_MPa":
            float(
                worst_station[
                    "force_only_avg_projected_shaft_head_pressure_MPa"
                ]
            ),
        "ultimate_locating_journal_thrust_kN":
            float(
                worst_station[
                    "full_locating_journal_thrust_kN"
                ]
            ),
        "ultimate_brace_force_kN_at_working_arm":
            float(
                worst_station[
                    "brace_force_abs_kN"
                ]
            ),
        "working_interface_study_candidate":
            (
                abs(
                    diameter_mm
                    - 36.0
                ) < 1e-9
                and abs(
                    bearing_width_mm
                    - 25.0
                ) < 1e-9
            ),
    })


family_df = pd.DataFrame(
    family_rows
)

family_df.to_csv(
    OUTPUT_FAMILY,
    index=False,
)


# =============================================================================
# ARCHITECTURE DECISION RECORD
# =============================================================================

decision_rows = [
    {
        "architecture":
            "A",
        "concept":
            (
                "300M cross-trunnion / through-shaft rigidly captured "
                "inside a locally enlarged 7075-T6 solid upper-head boss"
            ),
        "disposition":
            "SELECT_FOR_DETAILED_SCREENING",
        "reason":
            (
                "Preserves both the existing D9 300M journal strength basis "
                "and the frozen E2 7075-T6 barrel/head baseline without "
                "requiring an entire steel upper-head module."
            ),
        "open_requirements":
            (
                "Positive shaft/head moment lock; local 7075 contact/bearing; "
                "boss net section; edge/ligament; thrust retention; fretting; "
                "fatigue; tolerances; corrosion isolation; 3D FEA."
            ),
    },
    {
        "architecture":
            "B",
        "concept":
            (
                "Separate 300M trunnion/head structural module joined to "
                "7075-T6 barrel above pressure closure"
            ),
        "disposition":
            "BACKUP_ARCHITECTURE",
        "reason":
            (
                "Allows integral steel journals but creates a major "
                "steel-to-aluminum barrel/head structural joint carrying "
                "landing loads."
            ),
        "open_requirements":
            (
                "Module-to-barrel joint architecture, preload/retention, "
                "local barrel reinforcement, fatigue, corrosion and pressure "
                "closure integration."
            ),
    },
    {
        "architecture":
            "C",
        "concept":
            "Integral 7075-T6 upper-head trunnion journals",
        "disposition":
            "BACKUP_REQUIRES_COMPLETE_JOURNAL_RESIZE",
        "reason":
            (
                "Simplifies material continuity but invalidates the current "
                "300M journal sizing and introduces aluminum wear/fatigue "
                "concerns at the oscillating support interface."
            ),
        "open_requirements":
            (
                "New allowable basis, larger journal sweep, wear sleeve/bushing "
                "strategy, fatigue and local-head sizing."
            ),
    },
]

decision_df = pd.DataFrame(
    decision_rows
)

decision_df.to_csv(
    OUTPUT_DECISION,
    index=False,
)


# =============================================================================
# CONSOLE REPORT
# =============================================================================

print("=" * 124)
print(
    " PHASE 2E3-B4 — 300M CROSS-TRUNNION / 7075 HEAD INTERFACE REQUIREMENTS V0.1"
)
print("=" * 124)

print("\nARCHITECTURE STUDY DECISION")
print("-" * 124)
print(
    "Architecture A selected FOR DETAILED SCREENING ONLY:"
)
print(
    "300M cross-trunnion / through-shaft rigidly captured by a locally enlarged 7075-T6 solid head."
)
print(
    "No friction-only load transfer is credited and no shaft/head fit is frozen."
)

print("\n120-mm ROBUST FAMILY — INTERFACE COMPARISON")
print("-" * 124)
print(
    f"{'d':>6}"
    f"{'Bw':>6}"
    f"{'Head W':>10}"
    f"{'Boss/side':>12}"
    f"{'B3 MSu':>10}"
    f"{'Rult':>10}"
    f"{'Mroot':>10}"
    f"{'Couple':>10}"
    f"{'pavg*':>10}"
)
print("-" * 84)

for _, row in family_df.sort_values(
    "bearing_width_mm"
).iterrows():

    marker = (
        "  <-- WORKING"
        if bool(
            row[
                "working_interface_study_candidate"
            ]
        )
        else ""
    )

    print(
        f"{row['journal_diameter_mm']:>6.0f}"
        f"{row['bearing_width_mm']:>6.0f}"
        f"{row['head_root_to_root_width_mm']:>10.1f}"
        f"{row['boss_extension_each_side_vs_barrel_mm']:>12.1f}"
        f"{row['B3_worst_MS_ultimate_strength']:>10.3f}"
        f"{row['ultimate_per_journal_radial_reaction_kN']:>10.1f}"
        f"{row['ultimate_journal_root_moment_kNm']:>10.3f}"
        f"{row['ultimate_moment_transfer_couple_kN']:>10.1f}"
        f"{row['force_only_avg_shaft_head_pressure_MPa']:>10.1f}"
        f"{marker}"
    )

print(
    "\n*pavg is FORCE-ONLY average projected pressure over half the head width. "
    "It is a LOWER BOUND and is NOT a local contact allowable check."
)

working = family_df.loc[
    family_df[
        "working_interface_study_candidate"
    ]
].iloc[0]

print("\nWORKING INTERFACE-STUDY CANDIDATE")
print("-" * 124)
print(
    f"Support span:                     {working['support_span_mm']:.0f} mm"
)
print(
    f"300M journal diameter:            {working['journal_diameter_mm']:.0f} mm"
)
print(
    f"Airframe bearing width:           {working['bearing_width_mm']:.0f} mm"
)
print(
    f"Implied root-to-root head width:  {working['head_root_to_root_width_mm']:.1f} mm"
)
print(
    f"Boss growth vs 74-mm barrel:      {working['boss_extension_each_side_vs_barrel_mm']:.1f} mm / side"
)
print(
    f"B3 worst ultimate journal MS:     {working['B3_worst_MS_ultimate_strength']:+.3f}"
)
print(
    f"B3 ultimate bronze-bearing p:     {working['B3_worst_bearing_pressure_MPa']:.1f} MPa"
)
print(
    f"B3 bronze-bearing MS:             {working['B3_worst_MS_ultimate_bearing']:+.3f}"
)

print("\nULTIMATE INTERFACE REQUIREMENTS — HIGHEST B1 STATION SENSITIVITY")
print("-" * 124)
print(
    f"Per-journal radial reaction:      {working['ultimate_per_journal_radial_reaction_kN']:.3f} kN"
)
print(
    f"Journal-root bending moment:      {working['ultimate_journal_root_moment_kNm']:.3f} kN*m"
)
print(
    f"Moment-transfer couple requirement:{working['ultimate_moment_transfer_couple_kN']:>10.3f} kN"
)
print(
    f"Full locating-journal thrust:     {working['ultimate_locating_journal_thrust_kN']:.3f} kN"
)
print(
    f"Brace force @ {working_brace_arm_mm:.0f} mm effective arm: "
    f"{working['ultimate_brace_force_kN_at_working_arm']:.3f} kN"
)

print("\nINTERPRETATION")
print("-" * 124)
print(
    "1. The 7075 head must transfer BOTH radial force and the journal-root bending moment; "
    "force-only bearing pressure is insufficient as a design proof."
)
print(
    "2. The reported moment-transfer couple is a pure statics requirement, not a contact-pressure solution."
)
print(
    "3. Architecture A therefore requires a positive, moment-capable shaft/head capture; "
    "a loose pin-in-hole or friction-only assumption is not acceptable."
)
print(
    "4. 36 mm journal / 25 mm bearing / 120 mm span is carried as the WORKING INTERFACE-STUDY candidate, "
    "not yet the final frozen trunnion."
)
print(
    "5. Next step: preliminary 7075 solid-head boss sizing and load-transfer checks around this candidate, "
    "with 34/20 and 36/30 retained as local comparators."
)

print("\nOUTPUT FILES")
print("-" * 124)
print(
    f"Interface load envelope:          {OUTPUT_ENVELOPE}"
)
print(
    f"120-mm family comparison:         {OUTPUT_FAMILY}"
)
print(
    f"Architecture decision record:     {OUTPUT_DECISION}"
)
print(
    f"Summary:                          {OUTPUT_SUMMARY}"
)

summary_lines = [
    "=" * 124,
    " PHASE 2E3-B4 — 300M CROSS-TRUNNION / 7075 HEAD INTERFACE REQUIREMENTS V0.1",
    "=" * 124,
    "",
    "Architecture A selected FOR DETAILED SCREENING ONLY.",
    "",
    "Working interface-study candidate:",
    f"  span = {working['support_span_mm']:.0f} mm",
    f"  journal = {working['journal_diameter_mm']:.0f} mm 300M",
    f"  bearing width = {working['bearing_width_mm']:.0f} mm",
    f"  head root-to-root width = {working['head_root_to_root_width_mm']:.1f} mm",
    f"  boss growth vs 74-mm barrel = {working['boss_extension_each_side_vs_barrel_mm']:.1f} mm/side",
    "",
    "Ultimate highest-station interface requirements:",
    f"  per-journal radial reaction = {working['ultimate_per_journal_radial_reaction_kN']:.6f} kN",
    f"  journal-root moment = {working['ultimate_journal_root_moment_kNm']:.6f} kN*m",
    f"  moment-transfer force couple = {working['ultimate_moment_transfer_couple_kN']:.6f} kN",
    f"  locating-journal thrust = {working['ultimate_locating_journal_thrust_kN']:.6f} kN",
    f"  brace force at {working_brace_arm_mm:.0f} mm arm = {working['ultimate_brace_force_kN_at_working_arm']:.6f} kN",
    "",
    "No local 7075-T6 head PASS is claimed by this script.",
    "Next: local solid-head boss / shaft-capture structural screen.",
    "=" * 124,
]

OUTPUT_SUMMARY.write_text(
    "\n".join(
        summary_lines
    ),
    encoding="utf-8",
)

print("=" * 124)


if __name__ == "__main__":
    pass
