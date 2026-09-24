from pathlib import Path
import io
import math
import runpy
from contextlib import redirect_stdout

import numpy as np
import pandas as pd


# =============================================================================
# LANDING GEAR DESIGN PROJECT
# PHASE 2E3-B9 — LOCAL TRANSITION FEA CONVERGENCE CLOSEOUT V0.1
#
# PURPOSE
#   Consolidate the three ANSYS LC4+ ULTIMATE local-transition runs and
#   calculate a meaningful local VM amplification factor at the ACTUAL
#   converged FEA peak station.
#
# IMPORTANT CORRECTION
#   The previous quick ratio 469 MPa / 440 MPa used a nominal analytical
#   reference at A = 375 mm.  The converged FEA peak is near A = 315 mm.
#   Therefore that ratio is not a proper local amplification measure.
#
#   This script recomputes the nominal Kt=1 analytical stress at the actual
#   converged FEA peak station before calculating:
#
#       K_VM = sigma_VM,FEA_peak / sigma_VM,nominal_same_station
#
#   K_VM is a combined-load von-Mises amplification factor, NOT a classical
#   load-mode-specific elastic stress concentration factor Kt.
#
# FEA INPUTS RECORDED FROM ANSYS
#   Run 0 — baseline/coarse local mesh
#       peak VM = 469.23 MPa
#       peak A  = 314.078599 mm
#       total deformation = 28.043 mm
#
#   Run 1 — local refinement, nominal 2.5 mm sphere sizing
#       peak VM = 469.18 MPa
#       peak A  = 316.222675 mm
#       total deformation = 28.043 mm
#
#   Run 2 — local refinement, nominal 2.0 mm sphere sizing
#       peak VM = 469.18 MPa
#       peak A  = 315.278277 mm
#       total deformation = 28.043 mm
#
#   Final reported peak node coordinates from Run 2:
#       X = -0.000001 mm
#       Y = 32.126392 mm
#       Z = 315.278277 mm
#
# PRELIMINARY MATERIAL SCREENS
#   7075-T6 project baseline:
#       yield    = 503 MPa
#       ultimate = 572 MPa
#
# OUTPUTS
#   phase2e3b9_fea_convergence.csv
#   phase2e3b9_local_nominal_reference.csv
#   phase2e3b9_closeout_summary.txt
# =============================================================================


HERE = Path(__file__).resolve().parent

B5B_PY = HERE / "phase2e3b5b_upper_barrel_reinforcement_profile_v01.py"

OUTPUT_CONVERGENCE = HERE / "phase2e3b9_fea_convergence.csv"
OUTPUT_NOMINAL = HERE / "phase2e3b9_local_nominal_reference.csv"
OUTPUT_SUMMARY = HERE / "phase2e3b9_closeout_summary.txt"


# =============================================================================
# RECORDED FEA RESULTS
# =============================================================================

FEA_RUNS = [
    {
        "run":
            "RUN0_BASELINE",
        "local_mesh_label":
            "baseline/coarse local mesh",
        "peak_VM_MPa":
            469.23,
        "peak_A_mm":
            314.078599,
        "peak_X_mm":
            -0.000001,
        "peak_Y_mm":
            32.168623,
        "total_deformation_mm":
            28.043,
    },
    {
        "run":
            "RUN1_LOCAL_2p5MM",
        "local_mesh_label":
            "local refinement ~2.5 mm",
        "peak_VM_MPa":
            469.18,
        "peak_A_mm":
            316.222675,
        "peak_X_mm":
            -0.000001,
        "peak_Y_mm":
            32.093131,
        "total_deformation_mm":
            28.043,
    },
    {
        "run":
            "RUN2_LOCAL_2p0MM",
        "local_mesh_label":
            "local refinement ~2.0 mm",
        "peak_VM_MPa":
            469.18,
        "peak_A_mm":
            315.278277,
        "peak_X_mm":
            -0.000001,
        "peak_Y_mm":
            32.126392,
        "total_deformation_mm":
            28.043,
    },
]


# =============================================================================
# PRIMARY 106/64 PROFILE
# =============================================================================

LOWER_OD_MM = 74.0
UPPER_OD_MM = 106.0
BARREL_ID_MM = 64.0

TAPER_START_A_MM = 275.0
TAPER_END_A_MM = 973.780357

MODEL_LENGTH_MM = 650.0


def smoothstep(s):
    s = max(
        0.0,
        min(
            1.0,
            float(s),
        ),
    )

    return (
        3.0 * s**2
        - 2.0 * s**3
    )


def profile_OD_mm(zA_mm):
    if zA_mm <= TAPER_START_A_MM:
        return LOWER_OD_MM

    if zA_mm >= TAPER_END_A_MM:
        return UPPER_OD_MM

    s = (
        zA_mm
        - TAPER_START_A_MM
    ) / (
        TAPER_END_A_MM
        - TAPER_START_A_MM
    )

    return (
        LOWER_OD_MM
        + (
            UPPER_OD_MM
            - LOWER_OD_MM
        )
        * smoothstep(
            s
        )
    )


# =============================================================================
# LOAD B5B ANALYTICAL MECHANICS
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
        run_name="phase2e3b5b_reuse_for_b9_closeout",
    )


required = [
    "resultants_at_h",
    "annular_combined_vm_MPa",
    "loads",
    "case_col",
    "limit_cols",
    "ultimate_cols",
    "P_LIMIT_DIFF_MPa",
    "P_ULT_DIFF_MPa",
    "SY_7075_MPa",
    "SU_7075_MPa",
]

missing = [
    name
    for name in required
    if name not in b5b
]

if missing:
    raise KeyError(
        "B5B source did not expose required items: "
        + ", ".join(
            missing
        )
    )


resultants_at_h = b5b[
    "resultants_at_h"
]

annular_combined_vm_MPa = b5b[
    "annular_combined_vm_MPa"
]

loads = b5b[
    "loads"
]

case_col = b5b[
    "case_col"
]

limit_cols = b5b[
    "limit_cols"
]

ultimate_cols = b5b[
    "ultimate_cols"
]

P_LIMIT_DIFF_MPa = float(
    b5b[
        "P_LIMIT_DIFF_MPa"
    ]
)

P_ULT_DIFF_MPa = float(
    b5b[
        "P_ULT_DIFF_MPa"
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


# =============================================================================
# FEA CONVERGENCE TABLE
# =============================================================================

conv_rows = []

for i, run in enumerate(
    FEA_RUNS
):
    row = dict(
        run
    )

    row[
        "local_OD_at_peak_mm"
    ] = profile_OD_mm(
        run[
            "peak_A_mm"
        ]
    )

    row[
        "local_wall_at_peak_mm"
    ] = (
        row[
            "local_OD_at_peak_mm"
        ]
        - BARREL_ID_MM
    ) / 2.0

    row[
        "deformation_over_model_length_percent"
    ] = (
        run[
            "total_deformation_mm"
        ]
        / MODEL_LENGTH_MM
        * 100.0
    )

    if i == 0:
        row[
            "stress_change_from_previous_percent"
        ] = np.nan
        row[
            "peak_A_shift_from_previous_mm"
        ] = np.nan
    else:
        prev = FEA_RUNS[
            i - 1
        ]

        row[
            "stress_change_from_previous_percent"
        ] = (
            abs(
                run[
                    "peak_VM_MPa"
                ]
                - prev[
                    "peak_VM_MPa"
                ]
            )
            / run[
                "peak_VM_MPa"
            ]
            * 100.0
        )

        row[
            "peak_A_shift_from_previous_mm"
        ] = abs(
            run[
                "peak_A_mm"
            ]
            - prev[
                "peak_A_mm"
            ]
        )

    conv_rows.append(
        row
    )


conv_df = pd.DataFrame(
    conv_rows
)

conv_df.to_csv(
    OUTPUT_CONVERGENCE,
    index=False,
)


# =============================================================================
# LOCAL NOMINAL ANALYTICAL REFERENCE AT CONVERGED FEA PEAK
# =============================================================================

final_run = FEA_RUNS[
    -1
]

PEAK_A_MM = float(
    final_run[
        "peak_A_mm"
    ]
)

PEAK_FEA_VM_MPa = float(
    final_run[
        "peak_VM_MPa"
    ]
)

PEAK_OD_MM = profile_OD_mm(
    PEAK_A_MM
)


lc4_rows = loads.loc[
    loads[
        case_col
    ].astype(
        str
    ).str.strip()
    == "LC4+"
]

if len(
    lc4_rows
) != 1:
    raise ValueError(
        f"Expected exactly one LC4+ row; found {len(lc4_rows)}."
    )

lc4 = lc4_rows.iloc[
    0
]


nominal_rows = []

for (
    level,
    cols,
    pressure_MPa,
    allowable_MPa,
) in [
    (
        "limit",
        limit_cols,
        P_LIMIT_DIFF_MPa,
        SY_7075_MPa,
    ),
    (
        "ultimate",
        ultimate_cols,
        P_ULT_DIFF_MPa,
        SU_7075_MPa,
    ),
]:

    res = resultants_at_h(
        float(
            lc4[
                cols[
                    "Fx"
                ]
            ]
        ),
        float(
            lc4[
                cols[
                    "Fy"
                ]
            ]
        ),
        float(
            lc4[
                cols[
                    "Fz"
                ]
            ]
        ),
        PEAK_A_MM,
    )

    stress = annular_combined_vm_MPa(
        res,
        PEAK_OD_MM,
        BARREL_ID_MM,
        pressure_MPa,
        1.0,
    )

    nominal_rows.append({
        "level":
            level,
        "case":
            "LC4+",
        "reference_station_A_mm":
            PEAK_A_MM,
        "local_OD_mm":
            PEAK_OD_MM,
        "local_ID_mm":
            BARREL_ID_MM,
        "local_wall_mm":
            (
                PEAK_OD_MM
                - BARREL_ID_MM
            )
            / 2.0,
        "pressure_MPa":
            pressure_MPa,

        "Fx_kN":
            res[
                "Fx_kN"
            ],
        "Fy_kN":
            res[
                "Fy_kN"
            ],
        "Fz_kN":
            res[
                "Fz_kN"
            ],
        "Mx_kNm":
            res[
                "Mx_kNm"
            ],
        "My_kNm":
            res[
                "My_kNm"
            ],
        "Mz_kNm":
            res[
                "Mz_kNm"
            ],
        "Mb_kNm":
            res[
                "Mb_kNm"
            ],

        "nominal_surface":
            stress[
                "surface"
            ],
        "nominal_sigma_z_MPa":
            stress[
                "sigma_z_MPa"
            ],
        "nominal_sigma_theta_MPa":
            stress[
                "sigma_theta_MPa"
            ],
        "nominal_sigma_r_MPa":
            stress[
                "sigma_r_MPa"
            ],
        "nominal_tau_torsion_MPa":
            stress[
                "tau_torsion_MPa"
            ],
        "nominal_VM_MPa":
            stress[
                "vm_MPa"
            ],

        "material_screen_MPa":
            allowable_MPa,
        "nominal_MS":
            (
                allowable_MPa
                / stress[
                    "vm_MPa"
                ]
                - 1.0
            ),
    })


nominal_df = pd.DataFrame(
    nominal_rows
)

nominal_df.to_csv(
    OUTPUT_NOMINAL,
    index=False,
)


ult_nominal = nominal_df.loc[
    nominal_df[
        "level"
    ]
    == "ultimate"
].iloc[
    0
]

lim_nominal = nominal_df.loc[
    nominal_df[
        "level"
    ]
    == "limit"
].iloc[
    0
]


# =============================================================================
# FEA METRICS
# =============================================================================

K_VM = (
    PEAK_FEA_VM_MPa
    / float(
        ult_nominal[
            "nominal_VM_MPa"
        ]
    )
)

FEA_MS_ULT = (
    SU_7075_MPa
    / PEAK_FEA_VM_MPa
    - 1.0
)

# Because the current model is linear elastic and every Phase 1 ultimate
# mechanical load plus the E2 ultimate pressure state is exactly 1.5x the
# corresponding limit state, the FEA limit result scales linearly.
FEA_LIMIT_VM_SCALED_MPa = (
    PEAK_FEA_VM_MPa
    / 1.5
)

FEA_LIMIT_DEFORMATION_SCALED_MM = (
    final_run[
        "total_deformation_mm"
    ]
    / 1.5
)

FEA_MS_LIMIT = (
    SY_7075_MPa
    / FEA_LIMIT_VM_SCALED_MPa
    - 1.0
)

last_delta_percent = (
    conv_df.iloc[
        -1
    ][
        "stress_change_from_previous_percent"
    ]
)

last_location_shift_mm = (
    conv_df.iloc[
        -1
    ][
        "peak_A_shift_from_previous_mm"
    ]
)

mesh_converged = bool(
    last_delta_percent
    <= 1.0
    and last_location_shift_mm
    <= 5.0
)


# =============================================================================
# REPORT
# =============================================================================

print("=" * 126)
print(
    " PHASE 2E3-B9 — LOCAL TRANSITION FEA CONVERGENCE CLOSEOUT V0.1"
)
print("=" * 126)

print("\nFEA MESH-CONVERGENCE HISTORY")
print("-" * 126)
print(
    f"{'Run':<22}"
    f"{'Peak VM':>12}"
    f"{'Peak A':>12}"
    f"{'Wall':>10}"
    f"{'Defl':>10}"
    f"{'dStress %':>12}"
    f"{'dA':>10}"
)
print("-" * 94)

for _, row in conv_df.iterrows():

    dstress = (
        "-"
        if pd.isna(
            row[
                "stress_change_from_previous_percent"
            ]
        )
        else f"{row['stress_change_from_previous_percent']:.4f}"
    )

    da = (
        "-"
        if pd.isna(
            row[
                "peak_A_shift_from_previous_mm"
            ]
        )
        else f"{row['peak_A_shift_from_previous_mm']:.3f}"
    )

    print(
        f"{row['run']:<22}"
        f"{row['peak_VM_MPa']:>12.2f}"
        f"{row['peak_A_mm']:>12.3f}"
        f"{row['local_wall_at_peak_mm']:>10.3f}"
        f"{row['total_deformation_mm']:>10.3f}"
        f"{dstress:>12}"
        f"{da:>10}"
    )

print("\nCONVERGED PEAK")
print("-" * 126)
print(
    f"FEA peak VM:                      {PEAK_FEA_VM_MPa:.3f} MPa"
)
print(
    f"Peak station A = Z:               {PEAK_A_MM:.6f} mm"
)
print(
    f"Peak X / Y:                       "
    f"{final_run['peak_X_mm']:.6f} / {final_run['peak_Y_mm']:.6f} mm"
)
print(
    f"Local OD / ID:                    {PEAK_OD_MM:.3f} / {BARREL_ID_MM:.3f} mm"
)
print(
    f"Local wall thickness:             {(PEAK_OD_MM-BARREL_ID_MM)/2.0:.3f} mm"
)
print(
    f"Total deformation:                {final_run['total_deformation_mm']:.3f} mm"
)
print(
    f"Deformation / model length:       "
    f"{final_run['total_deformation_mm']/MODEL_LENGTH_MM*100.0:.3f} %"
)

print("\nSAME-STATION ANALYTICAL NOMINAL REFERENCE")
print("-" * 126)
print(
    f"Ultimate nominal Kt=1 VM:         {ult_nominal['nominal_VM_MPa']:.3f} MPa"
)
print(
    f"FEA / nominal VM amplification:   {K_VM:.4f}"
)
print(
    "Interpretation: K_VM is a combined-load VM amplification factor, not classical Kt."
)

print("\nPRELIMINARY STATIC SCREENS")
print("-" * 126)
print(
    f"Ultimate project screen:          {SU_7075_MPa:.1f} MPa"
)
print(
    f"Ultimate FEA peak:                {PEAK_FEA_VM_MPa:.3f} MPa"
)
print(
    f"Ultimate FEA margin:              {FEA_MS_ULT:+.3f}"
)
print()
print(
    f"Linear-scaled limit FEA peak:     {FEA_LIMIT_VM_SCALED_MPa:.3f} MPa"
)
print(
    f"Limit project yield screen:       {SY_7075_MPa:.1f} MPa"
)
print(
    f"Limit FEA margin:                 {FEA_MS_LIMIT:+.3f}"
)
print(
    f"Linear-scaled limit deformation:  {FEA_LIMIT_DEFORMATION_SCALED_MM:.3f} mm"
)

print("\nB9 DISPOSITION")
print("-" * 126)
print(
    f"Mesh convergence criterion:       {'PASS' if mesh_converged else 'HOLD'}"
)
print(
    f"Final refinement stress change:   {last_delta_percent:.6f} %"
)
print(
    f"Final refinement peak shift:      {last_location_shift_mm:.3f} mm"
)

if mesh_converged and FEA_MS_ULT >= 0.0 and FEA_MS_LIMIT >= 0.0:
    print(
        "PRELIMINARY STATIC LOCAL-TRANSITION SCREEN: PASS"
    )
else:
    print(
        "PRELIMINARY STATIC LOCAL-TRANSITION SCREEN: HOLD / FAIL"
    )

print()
print(
    "Next recommended sensitivity: rerun the final mesh with Large Deflection ON "
    "because the current maximum deformation is several percent of the 650-mm local-model length."
)
print(
    "Do not interpret this B9 PASS as fatigue, contact, fretting, pressure-closure, "
    "certification, or final allowable substantiation."
)

print("\nOUTPUT FILES")
print("-" * 126)
print(
    f"FEA convergence table:            {OUTPUT_CONVERGENCE}"
)
print(
    f"Local nominal reference:          {OUTPUT_NOMINAL}"
)
print(
    f"Summary:                          {OUTPUT_SUMMARY}"
)
print("=" * 126)


summary_lines = [
    "=" * 126,
    " PHASE 2E3-B9 — LOCAL TRANSITION FEA CONVERGENCE CLOSEOUT V0.1",
    "=" * 126,
    "",
    f"Converged ultimate FEA peak VM: {PEAK_FEA_VM_MPa:.6f} MPa",
    f"Peak station A: {PEAK_A_MM:.6f} mm",
    f"Peak Y: {final_run['peak_Y_mm']:.6f} mm",
    f"Local OD: {PEAK_OD_MM:.6f} mm",
    f"Local wall: {(PEAK_OD_MM-BARREL_ID_MM)/2.0:.6f} mm",
    f"Total deformation: {final_run['total_deformation_mm']:.6f} mm",
    "",
    f"Final refinement stress change: {last_delta_percent:.9f} %",
    f"Final refinement station shift: {last_location_shift_mm:.6f} mm",
    f"Mesh convergence: {'PASS' if mesh_converged else 'HOLD'}",
    "",
    f"Same-station ultimate nominal VM: {ult_nominal['nominal_VM_MPa']:.6f} MPa",
    f"K_VM: {K_VM:.9f}",
    "",
    f"Ultimate FEA margin: {FEA_MS_ULT:+.6f}",
    f"Scaled limit FEA peak: {FEA_LIMIT_VM_SCALED_MPa:.6f} MPa",
    f"Limit FEA margin: {FEA_MS_LIMIT:+.6f}",
    "",
    "Next recommended sensitivity: Large Deflection ON using the final mesh.",
    "=" * 126,
]

OUTPUT_SUMMARY.write_text(
    "\n".join(
        summary_lines
    ),
    encoding="utf-8",
)
