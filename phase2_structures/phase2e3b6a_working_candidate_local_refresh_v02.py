from pathlib import Path
import ast
import math

import numpy as np
import pandas as pd


# =============================================================================
# LANDING GEAR DESIGN PROJECT
# PHASE 2E3-B6A — WORKING 150-mm TRUNNION LOCAL-HEAD REFRESH V0.2
#
# PURPOSE
#   Correct the contact-model issue identified in V0.1.
#
# V0.1 finding:
#   All rows reported PASS=False despite strongly positive stress margins.
#   The cause is not a structural stress failure. It is that the full-length
#   LINEAR contact distribution becomes tensile at the inboard end of the
#   57.5-mm engagement:
#
#       e_contact = M/R = 17.5 mm
#       L = 57.5 mm
#       e/L = 0.304 < 1/3
#
#   A unilateral contact interface cannot carry tension, so the physical
#   first-order model must switch to PARTIAL triangular contact near the root.
#
# CONTACT MODEL
#   Let x be measured inward from the journal root over engagement 0 <= x <= L.
#
#   Required force:
#       integral q(x) dx = R
#
#   Required moment:
#       integral x q(x) dx = M
#
#   Define the resultant line-of-action:
#       e = M/R
#
#   Cases:
#
#   A) e < L/3
#      Root-side triangular partial contact:
#
#          c = 3e
#          q(x) = q0(1 - x/c),  0 <= x <= c
#          q0 = 2R/c
#
#      Contact is zero for c < x <= L.
#
#   B) L/3 <= e <= 2L/3
#      Full-length linear contact:
#
#          q(x) = a + b x
#
#      with exact force/moment equilibrium.
#
#   C) e > 2L/3
#      Inboard-side triangular partial contact of length:
#
#          c = 3(L-e)
#
#   This is still a simplified projected-contact model, not Hertzian/contact FEA.
#
#   The lower-ligament shear-out, side-ligament, and thrust-shoulder screens are
#   retained from V0.1.
#
# OUTPUTS
#   phase2e3b6a_v02_working_local_head_screen.csv
#   phase2e3b6a_v02_contact_distribution.csv
#   phase2e3b6a_v02_contact_model_audit.csv
#   phase2e3b6a_v02_summary.txt
# =============================================================================


HERE = Path(__file__).resolve().parent

B6_WORKING = HERE / "phase2e3b6_working_candidate_record.csv"
B1_REACTIONS = HERE / "phase2e3b1_trunnion_reaction_trade.csv"
D9_PY = HERE / "phase2_upper_trunnion_sizing.py"

OUTPUT_SCREEN = HERE / "phase2e3b6a_v02_working_local_head_screen.csv"
OUTPUT_CONTACT = HERE / "phase2e3b6a_v02_contact_distribution.csv"
OUTPUT_AUDIT = HERE / "phase2e3b6a_v02_contact_model_audit.csv"
OUTPUT_SUMMARY = HERE / "phase2e3b6a_v02_summary.txt"


# =============================================================================
# PROJECT PRELIMINARY MATERIAL SCREENS
# =============================================================================

SY_7075_MPa = 503.0
SU_7075_MPa = 572.0

LIGAMENT_VALUES_MM = [
    5.0,
    10.0,
    15.0,
    20.0,
]


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


def margin(allowable, demand):
    if demand <= 0.0:
        return np.inf

    return allowable / demand - 1.0


def equivalent_shoulder_od_mm(
    shaft_diameter_mm,
    force_kN,
    allowable_MPa,
):
    A_req_mm2 = (
        force_kN
        * 1000.0
        / allowable_MPa
    )

    D_req_mm = math.sqrt(
        shaft_diameter_mm**2
        + 4.0
        * A_req_mm2
        / math.pi
    )

    return (
        A_req_mm2,
        D_req_mm,
    )


# =============================================================================
# CONTACT MODEL
# =============================================================================

def unilateral_projected_contact(
    R_kN,
    Mroot_kNm,
    L_mm,
    diameter_mm,
    n_points=101,
):
    """
    First-order unilateral projected contact model.

    Returns a non-negative q(x) satisfying resultant force and moment exactly.
    """

    R_N = (
        R_kN
        * 1000.0
    )

    M_Nmm = (
        Mroot_kNm
        * 1e6
    )

    if R_N <= 0.0:
        raise ValueError(
            "Radial reaction must be positive."
        )

    if L_mm <= 0.0:
        raise ValueError(
            "Engagement length must be positive."
        )

    e_mm = (
        M_Nmm
        / R_N
    )

    if (
        e_mm < 0.0
        or e_mm > L_mm
    ):
        raise ValueError(
            f"Resultant line of action e={e_mm:.6f} mm lies outside "
            f"engagement L={L_mm:.6f} mm."
        )

    x = np.linspace(
        0.0,
        L_mm,
        n_points,
    )

    q = np.zeros_like(
        x
    )

    tol = 1e-12

    # -------------------------------------------------------------------------
    # Root-side triangular partial contact.
    # -------------------------------------------------------------------------
    if e_mm < (
        L_mm / 3.0 - tol
    ):

        regime = (
            "PARTIAL_ROOT_TRIANGULAR"
        )

        contact_length_mm = (
            3.0
            * e_mm
        )

        q0_N_per_mm = (
            2.0
            * R_N
            / contact_length_mm
        )

        mask = (
            x
            <= contact_length_mm
            + 1e-12
        )

        q[
            mask
        ] = (
            q0_N_per_mm
            * (
                1.0
                - x[
                    mask
                ]
                / contact_length_mm
            )
        )

        q_root = (
            q0_N_per_mm
        )

        q_inner = 0.0

        separation_length_mm = (
            L_mm
            - contact_length_mm
        )

    # -------------------------------------------------------------------------
    # Full-length linear contact.
    # -------------------------------------------------------------------------
    elif e_mm <= (
        2.0
        * L_mm
        / 3.0
        + tol
    ):

        regime = (
            "FULL_LINEAR"
        )

        a = (
            4.0
            * R_N
            / L_mm
            - 6.0
            * M_Nmm
            / L_mm**2
        )

        b = (
            12.0
            * M_Nmm
            / L_mm**3
            - 6.0
            * R_N
            / L_mm**2
        )

        q = (
            a
            + b
            * x
        )

        # Numerical guard only.
        q = np.maximum(
            q,
            0.0,
        )

        q_root = (
            a
        )

        q_inner = (
            a
            + b
            * L_mm
        )

        contact_length_mm = (
            L_mm
        )

        separation_length_mm = (
            0.0
        )

    # -------------------------------------------------------------------------
    # Inboard-side triangular partial contact.
    # -------------------------------------------------------------------------
    else:

        regime = (
            "PARTIAL_INBOARD_TRIANGULAR"
        )

        contact_length_mm = (
            3.0
            * (
                L_mm
                - e_mm
            )
        )

        x_start = (
            L_mm
            - contact_length_mm
        )

        qL_N_per_mm = (
            2.0
            * R_N
            / contact_length_mm
        )

        mask = (
            x
            >= x_start
            - 1e-12
        )

        q[
            mask
        ] = (
            qL_N_per_mm
            * (
                x[
                    mask
                ]
                - x_start
            )
            / contact_length_mm
        )

        q_root = 0.0

        q_inner = (
            qL_N_per_mm
        )

        separation_length_mm = (
            x_start
        )

    p = (
        q
        / diameter_mm
    )

    p_peak_MPa = float(
        p.max()
    )

    # Exact analytic equilibrium reconstruction by regime.
    if regime == "PARTIAL_ROOT_TRIANGULAR":

        R_rec_N = (
            0.5
            * q_root
            * contact_length_mm
        )

        M_rec_Nmm = (
            R_rec_N
            * contact_length_mm
            / 3.0
        )

    elif regime == "FULL_LINEAR":

        # Recover coefficients from endpoint values.
        a = q_root

        b = (
            q_inner
            - q_root
        ) / L_mm

        R_rec_N = (
            a
            * L_mm
            + b
            * L_mm**2
            / 2.0
        )

        M_rec_Nmm = (
            a
            * L_mm**2
            / 2.0
            + b
            * L_mm**3
            / 3.0
        )

    else:

        R_rec_N = (
            0.5
            * q_inner
            * contact_length_mm
        )

        centroid_mm = (
            L_mm
            - contact_length_mm
            / 3.0
        )

        M_rec_Nmm = (
            R_rec_N
            * centroid_mm
        )

    force_residual_N = (
        R_rec_N
        - R_N
    )

    moment_residual_Nmm = (
        M_rec_Nmm
        - M_Nmm
    )

    if max(
        abs(
            force_residual_N
        ),
        abs(
            moment_residual_Nmm
        ),
    ) > 1e-6:
        raise AssertionError(
            "Unilateral contact equilibrium check failed."
        )

    return {
        "regime":
            regime,
        "resultant_offset_e_mm":
            e_mm,
        "e_over_L":
            e_mm
            / L_mm,
        "contact_length_mm":
            contact_length_mm,
        "separation_length_mm":
            separation_length_mm,
        "contact_fraction":
            contact_length_mm
            / L_mm,
        "q_root_N_per_mm":
            q_root,
        "q_inner_N_per_mm":
            q_inner,
        "p_peak_MPa":
            p_peak_MPa,
        "force_residual_N":
            force_residual_N,
        "moment_residual_Nmm":
            moment_residual_Nmm,
        "x_mm":
            x,
        "q_N_per_mm":
            q,
        "p_MPa":
            p,
    }


# =============================================================================
# READ WORKING GEOMETRY / SOURCE REACTIONS
# =============================================================================

working_record = read_csv(
    B6_WORKING
)

if working_record.empty:
    raise ValueError(
        "B6 working candidate record is empty."
    )

working = working_record.iloc[0]

SPAN_MM = float(
    working[
        "support_span_mm"
    ]
)

JOURNAL_D_MM = float(
    working[
        "journal_diameter_mm"
    ]
)

BEARING_WIDTH_MM = float(
    working[
        "bearing_width_mm"
    ]
)

HEAD_WIDTH_MM = float(
    working[
        "root_to_root_head_width_mm"
    ]
)

NECK_OD_KT3_MM = float(
    working[
        "required_neck_OD_at_Kt3_mm"
    ]
)

WORKING_LIGAMENT_MM = float(
    working[
        "working_lower_ligament_mm"
    ]
)

d9 = ast_literal_assignments(
    D9_PY
)

ROOT_CLEARANCE_MM = float(
    d9[
        "root_clearance_mm"
    ]
)

ROOT_LEVER_MM = (
    ROOT_CLEARANCE_MM
    + BEARING_WIDTH_MM
    / 2.0
)

HALF_HEAD_ENGAGEMENT_MM = (
    HEAD_WIDTH_MM
    / 2.0
)

SIDE_LIGAMENT_MM = (
    NECK_OD_KT3_MM
    - JOURNAL_D_MM
) / 2.0


reactions = read_csv(
    B1_REACTIONS
)

candidate_rx = reactions.loc[
    near(
        reactions[
            "journal_diameter_mm"
        ],
        JOURNAL_D_MM,
    )
    &
    near(
        reactions[
            "support_span_mm"
        ],
        SPAN_MM,
    )
].copy()

if candidate_rx.empty:
    raise ValueError(
        "Could not find B1 reactions for B6 working geometry."
    )


# =============================================================================
# SCREEN
# =============================================================================

screen_rows = []
contact_rows = []
audit_rows = []

for ligament_mm in LIGAMENT_VALUES_MM:

    lig_rows = candidate_rx.loc[
        near(
            candidate_rx[
                "ligament_mm"
            ],
            ligament_mm,
        )
    ]

    if lig_rows.empty:
        raise ValueError(
            f"No B1 rows at ligament {ligament_mm} mm."
        )

    for level in [
        "limit",
        "ultimate",
    ]:

        sub = lig_rows.loc[
            lig_rows[
                "level"
            ].astype(str)
            .str.lower()
            == level
        ]

        if sub.empty:
            raise ValueError(
                f"No {level} B1 rows at ligament {ligament_mm} mm."
            )

        gov = sub.loc[
            sub[
                "Rmax_kN"
            ].idxmax()
        ]

        R_kN = float(
            gov[
                "Rmax_kN"
            ]
        )

        Fx_kN = abs(
            float(
                gov[
                    "Fx_thrust_kN"
                ]
            )
        )

        Mroot_kNm = (
            R_kN
            * ROOT_LEVER_MM
            / 1000.0
        )

        contact = unilateral_projected_contact(
            R_kN,
            Mroot_kNm,
            HALF_HEAD_ENGAGEMENT_MM,
            JOURNAL_D_MM,
        )

        R_N = (
            R_kN
            * 1000.0
        )

        # Lower-ligament shear-out.
        A_lower_mm2 = (
            2.0
            * ligament_mm
            * HALF_HEAD_ENGAGEMENT_MM
        )

        tau_lower_MPa = (
            R_N
            / A_lower_mm2
        )

        vm_lower_MPa = (
            math.sqrt(3.0)
            * tau_lower_MPa
        )

        # Side-ligament shear-out using corrected 96-mm neck envelope.
        A_side_mm2 = (
            2.0
            * SIDE_LIGAMENT_MM
            * HALF_HEAD_ENGAGEMENT_MM
        )

        tau_side_MPa = (
            R_N
            / A_side_mm2
        )

        vm_side_MPa = (
            math.sqrt(3.0)
            * tau_side_MPa
        )

        if level == "limit":
            allowable_MPa = (
                SY_7075_MPa
            )

        else:
            allowable_MPa = (
                SU_7075_MPa
            )

        MS_contact = margin(
            allowable_MPa,
            contact[
                "p_peak_MPa"
            ],
        )

        MS_lower = margin(
            allowable_MPa,
            vm_lower_MPa,
        )

        MS_side = margin(
            allowable_MPa,
            vm_side_MPa,
        )

        required_ligament_mm = (
            math.sqrt(3.0)
            * R_N
            / (
                2.0
                * HALF_HEAD_ENGAGEMENT_MM
                * allowable_MPa
            )
        )

        A_thrust_req_mm2, D_shoulder_req_mm = (
            equivalent_shoulder_od_mm(
                JOURNAL_D_MM,
                Fx_kN,
                allowable_MPa,
            )
        )

        passes = (
            MS_contact >= 0.0
            and MS_lower >= 0.0
            and MS_side >= 0.0
        )

        screen_rows.append({
            "level":
                level,
            "ligament_mm":
                ligament_mm,
            "case":
                gov[
                    "case"
                ],
            "station_above_U_mm":
                gov[
                    "station_above_U_mm"
                ],

            "support_span_mm":
                SPAN_MM,
            "journal_diameter_mm":
                JOURNAL_D_MM,
            "bearing_width_mm":
                BEARING_WIDTH_MM,
            "root_clearance_mm":
                ROOT_CLEARANCE_MM,
            "root_lever_mm":
                ROOT_LEVER_MM,
            "head_width_mm":
                HEAD_WIDTH_MM,
            "half_head_engagement_mm":
                HALF_HEAD_ENGAGEMENT_MM,
            "neck_OD_Kt3_mm":
                NECK_OD_KT3_MM,
            "side_ligament_mm":
                SIDE_LIGAMENT_MM,

            "radial_reaction_kN":
                R_kN,
            "axial_thrust_kN":
                Fx_kN,
            "journal_root_moment_kNm":
                Mroot_kNm,

            "contact_regime":
                contact[
                    "regime"
                ],
            "resultant_offset_e_mm":
                contact[
                    "resultant_offset_e_mm"
                ],
            "e_over_L":
                contact[
                    "e_over_L"
                ],
            "contact_length_mm":
                contact[
                    "contact_length_mm"
                ],
            "separation_length_mm":
                contact[
                    "separation_length_mm"
                ],
            "contact_fraction":
                contact[
                    "contact_fraction"
                ],
            "contact_peak_projected_pressure_MPa":
                contact[
                    "p_peak_MPa"
                ],
            "contact_proxy_MS":
                MS_contact,

            "lower_shearout_VM_proxy_MPa":
                vm_lower_MPa,
            "lower_shearout_MS":
                MS_lower,
            "zero_margin_required_lower_ligament_mm":
                required_ligament_mm,

            "side_shearout_VM_proxy_MPa":
                vm_side_MPa,
            "side_shearout_MS":
                MS_side,

            "minimum_annular_thrust_area_mm2":
                A_thrust_req_mm2,
            "equivalent_minimum_shoulder_OD_mm":
                D_shoulder_req_mm,

            "simple_screen_PASS":
                passes,
        })

        audit_rows.append({
            "level":
                level,
            "ligament_mm":
                ligament_mm,
            "contact_regime":
                contact[
                    "regime"
                ],
            "resultant_offset_e_mm":
                contact[
                    "resultant_offset_e_mm"
                ],
            "engagement_L_mm":
                HALF_HEAD_ENGAGEMENT_MM,
            "e_over_L":
                contact[
                    "e_over_L"
                ],
            "L_over_3_mm":
                HALF_HEAD_ENGAGEMENT_MM
                / 3.0,
            "twoL_over_3_mm":
                2.0
                * HALF_HEAD_ENGAGEMENT_MM
                / 3.0,
            "contact_length_mm":
                contact[
                    "contact_length_mm"
                ],
            "separation_length_mm":
                contact[
                    "separation_length_mm"
                ],
            "force_residual_N":
                contact[
                    "force_residual_N"
                ],
            "moment_residual_Nmm":
                contact[
                    "moment_residual_Nmm"
                ],
        })

        for x_mm, q, p in zip(
            contact[
                "x_mm"
            ],
            contact[
                "q_N_per_mm"
            ],
            contact[
                "p_MPa"
            ],
        ):
            contact_rows.append({
                "level":
                    level,
                "ligament_mm":
                    ligament_mm,
                "contact_regime":
                    contact[
                        "regime"
                    ],
                "x_from_root_mm":
                    x_mm,
                "q_N_per_mm":
                    q,
                "projected_pressure_MPa":
                    p,
            })


screen_df = pd.DataFrame(
    screen_rows
)

contact_df = pd.DataFrame(
    contact_rows
)

audit_df = pd.DataFrame(
    audit_rows
)

screen_df.to_csv(
    OUTPUT_SCREEN,
    index=False,
)

contact_df.to_csv(
    OUTPUT_CONTACT,
    index=False,
)

audit_df.to_csv(
    OUTPUT_AUDIT,
    index=False,
)


# =============================================================================
# DISPOSITION
# =============================================================================

passing_ligaments = []

for ligament_mm in LIGAMENT_VALUES_MM:

    sub = screen_df.loc[
        near(
            screen_df[
                "ligament_mm"
            ],
            ligament_mm,
        )
    ]

    if (
        len(
            sub
        ) == 2
        and bool(
            sub[
                "simple_screen_PASS"
            ].all()
        )
    ):
        passing_ligaments.append(
            ligament_mm
        )


first_pass_mm = (
    min(
        passing_ligaments
    )
    if passing_ligaments
    else np.nan
)


working_10 = screen_df.loc[
    near(
        screen_df[
            "ligament_mm"
        ],
        WORKING_LIGAMENT_MM,
    )
    &
    (
        screen_df[
            "level"
        ]
        == "ultimate"
    )
].iloc[0]


# =============================================================================
# CONSOLE REPORT
# =============================================================================

print("=" * 124)
print(
    " PHASE 2E3-B6A — WORKING 150-mm TRUNNION LOCAL-HEAD REFRESH V0.2"
)
print("=" * 124)

print("\nCONTACT-MODEL CORRECTION")
print("-" * 124)
print(
    f"Journal-root resultant offset e:  {ROOT_LEVER_MM:.3f} mm"
)
print(
    f"Half-head engagement L:           {HALF_HEAD_ENGAGEMENT_MM:.3f} mm"
)
print(
    f"e/L:                              {ROOT_LEVER_MM/HALF_HEAD_ENGAGEMENT_MM:.6f}"
)
print(
    f"L/3:                              {HALF_HEAD_ENGAGEMENT_MM/3.0:.3f} mm"
)
print(
    "Because e < L/3, a full-length linear pressure law requires tensile contact at the inboard end."
)
print(
    "V0.2 therefore uses unilateral ROOT-SIDE TRIANGULAR partial contact."
)
print(
    f"Analytical contact length c=3e:   {3.0*ROOT_LEVER_MM:.3f} mm"
)
print(
    f"Predicted inboard separation:     "
    f"{HALF_HEAD_ENGAGEMENT_MM-3.0*ROOT_LEVER_MM:.3f} mm"
)

print("\nB6 WORKING GEOMETRY")
print("-" * 124)
print(
    f"Support span:                     {SPAN_MM:.1f} mm"
)
print(
    f"300M journal diameter:            {JOURNAL_D_MM:.1f} mm"
)
print(
    f"Airframe bearing width:           {BEARING_WIDTH_MM:.1f} mm"
)
print(
    f"Head width:                       {HEAD_WIDTH_MM:.1f} mm"
)
print(
    f"Kt=3 global neck OD:              {NECK_OD_KT3_MM:.1f} mm"
)
print(
    f"Transverse side ligament:         {SIDE_LIGAMENT_MM:.1f} mm"
)

print("\nCORRECTED LOCAL HEAD SCREEN")
print("-" * 124)
print(
    f"{'Lvl':>9}"
    f"{'Lig':>7}"
    f"{'R':>10}"
    f"{'Mroot':>10}"
    f"{'Regime':>26}"
    f"{'c':>8}"
    f"{'sep':>8}"
    f"{'p_peak':>10}"
    f"{'MS_p':>9}"
    f"{'MS_so':>9}"
    f"{'PASS':>8}"
)
print("-" * 122)

for _, row in screen_df.sort_values(
    [
        "level",
        "ligament_mm",
    ]
).iterrows():

    print(
        f"{row['level']:>9}"
        f"{row['ligament_mm']:>7.0f}"
        f"{row['radial_reaction_kN']:>10.2f}"
        f"{row['journal_root_moment_kNm']:>10.3f}"
        f"{row['contact_regime']:>26}"
        f"{row['contact_length_mm']:>8.1f}"
        f"{row['separation_length_mm']:>8.1f}"
        f"{row['contact_peak_projected_pressure_MPa']:>10.1f}"
        f"{row['contact_proxy_MS']:>9.3f}"
        f"{row['lower_shearout_MS']:>9.3f}"
        f"{str(bool(row['simple_screen_PASS'])):>8}"
    )

print("\nB6A V0.2 DISPOSITION")
print("-" * 124)

if np.isfinite(
    first_pass_mm
):
    print(
        f"First tested ligament passing all corrected simple screens: "
        f"{first_pass_mm:.0f} mm"
    )
else:
    print(
        "No tested ligament passes the corrected simple screens."
    )

print(
    f"Working 10-mm ligament ultimate contact regime: "
    f"{working_10['contact_regime']}"
)
print(
    f"Working 10-mm contact length:      "
    f"{working_10['contact_length_mm']:.3f} mm"
)
print(
    f"Working 10-mm separation length:   "
    f"{working_10['separation_length_mm']:.3f} mm"
)
print(
    f"Working 10-mm ultimate p_peak:     "
    f"{working_10['contact_peak_projected_pressure_MPa']:.3f} MPa"
)
print(
    f"Working 10-mm contact-proxy MS:    "
    f"{working_10['contact_proxy_MS']:+.3f}"
)
print(
    f"Working 10-mm shear-out MS:        "
    f"{working_10['lower_shearout_MS']:+.3f}"
)
print(
    f"Working 10-mm side-ligament MS:    "
    f"{working_10['side_shearout_MS']:+.3f}"
)

print()
print(
    "Interpretation: V0.1 PASS=False was a contact-assumption flag, not a stress-margin failure."
)
print(
    "Retain 10 mm as the practical working lower ligament if V0.2 passes; "
    "5 mm remains only a mathematical/simple-screen lower bound."
)
print(
    "Next: barrel-to-reinforced-upper-section-to-solid-head transition geometry and Kt-budget study."
)

print("\nOUTPUT FILES")
print("-" * 124)
print(
    f"Corrected local head screen:      {OUTPUT_SCREEN}"
)
print(
    f"Corrected contact distribution:   {OUTPUT_CONTACT}"
)
print(
    f"Contact-model audit:              {OUTPUT_AUDIT}"
)
print(
    f"Summary:                          {OUTPUT_SUMMARY}"
)


summary_lines = [
    "=" * 124,
    " PHASE 2E3-B6A — WORKING 150-mm TRUNNION LOCAL-HEAD REFRESH V0.2",
    "=" * 124,
    "",
    f"e = {ROOT_LEVER_MM:.6f} mm",
    f"L = {HALF_HEAD_ENGAGEMENT_MM:.6f} mm",
    f"e/L = {ROOT_LEVER_MM/HALF_HEAD_ENGAGEMENT_MM:.9f}",
    f"Contact regime = {working_10['contact_regime']}",
    f"Contact length = {working_10['contact_length_mm']:.6f} mm",
    f"Separation length = {working_10['separation_length_mm']:.6f} mm",
    "",
    f"First corrected simple-screen passing ligament = {first_pass_mm}",
    f"10-mm ultimate p_peak = {working_10['contact_peak_projected_pressure_MPa']:.6f} MPa",
    f"10-mm ultimate contact-proxy MS = {working_10['contact_proxy_MS']:+.6f}",
    f"10-mm ultimate lower shear-out MS = {working_10['lower_shearout_MS']:+.6f}",
    f"10-mm ultimate side-ligament MS = {working_10['side_shearout_MS']:+.6f}",
    "",
    "No final contact fit / local FEA / fatigue validation is claimed.",
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
