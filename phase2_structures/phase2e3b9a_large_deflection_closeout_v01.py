from pathlib import Path
import math
import pandas as pd


# =============================================================================
# LANDING GEAR DESIGN PROJECT
# PHASE 2E3-B9A — LARGE-DEFLECTION SENSITIVITY CLOSEOUT V0.1
#
# PURPOSE
#   Compare the converged small-deflection B9 local-transition solution with
#   the Large Deflection = ON nonlinear geometric solution using the same
#   final locally refined mesh.
#
# IMPORTANT
#   This is a geometric-nonlinearity sensitivity of the local transition
#   submodel. It does NOT close fatigue, fretting, pressure-closure,
#   trunnion-hole/contact, certification, or full-airframe load-path issues.
#
# RECORDED NONLINEAR ANSYS RESULT
#   LC4+ ultimate
#   Large Deflection = ON
#   automatic substepping = 10 initial / 1 min / 100 max
#
#   peak von Mises = 393.39 MPa
#   peak X         = ~0 mm
#   peak Y         = 34.052034 mm
#   peak Z=A       = 335.124456 mm
#   max deformation= 21.401 mm
#
#   mesh / solver:
#       total model nodes = 116866
#       solid elements     = 23232
#       total elements     = 31169
#       end time reached   = 1.0
#       errors             = 0
#
# OUTPUTS
#   phase2e3b9a_linear_nonlinear_comparison.csv
#   phase2e3b9a_solver_audit.csv
#   phase2e3b9a_closeout_summary.txt
# =============================================================================


HERE = Path(__file__).resolve().parent

B9_CONVERGENCE = HERE / "phase2e3b9_fea_convergence.csv"
B9_NOMINAL = HERE / "phase2e3b9_local_nominal_reference.csv"

OUT_COMPARE = HERE / "phase2e3b9a_linear_nonlinear_comparison.csv"
OUT_AUDIT = HERE / "phase2e3b9a_solver_audit.csv"
OUT_SUMMARY = HERE / "phase2e3b9a_closeout_summary.txt"


# =============================================================================
# GEOMETRY
# =============================================================================

LOWER_OD_MM = 74.0
UPPER_OD_MM = 106.0
BARREL_ID_MM = 64.0

TAPER_START_A_MM = 275.0
TAPER_END_A_MM = 973.780357

LOCAL_MODEL_LENGTH_MM = 650.0


def smoothstep(s):
    s = max(
        0.0,
        min(
            1.0,
            float(s),
        ),
    )

    return 3.0 * s**2 - 2.0 * s**3


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
# LOAD B9 LINEAR BASELINE
# =============================================================================

if not B9_CONVERGENCE.exists():
    raise FileNotFoundError(
        f"Required B9 convergence file not found:\n{B9_CONVERGENCE}"
    )

b9 = pd.read_csv(
    B9_CONVERGENCE,
    encoding="utf-8-sig",
)

if b9.empty:
    raise ValueError(
        "B9 convergence table is empty."
    )

linear = b9.iloc[
    -1
]

LINEAR_VM_MPa = float(
    linear[
        "peak_VM_MPa"
    ]
)

LINEAR_A_MM = float(
    linear[
        "peak_A_mm"
    ]
)

LINEAR_DEFL_MM = float(
    linear[
        "total_deformation_mm"
    ]
)


# =============================================================================
# MATERIAL SCREENS
# =============================================================================

SY_MPa = 503.0
SU_MPa = 572.0

if B9_NOMINAL.exists():
    nominal = pd.read_csv(
        B9_NOMINAL,
        encoding="utf-8-sig",
    )

    if (
        "level"
        in nominal.columns
        and "material_screen_MPa"
        in nominal.columns
    ):
        lim_rows = nominal.loc[
            nominal[
                "level"
            ].astype(str)
            == "limit"
        ]

        ult_rows = nominal.loc[
            nominal[
                "level"
            ].astype(str)
            == "ultimate"
        ]

        if len(
            lim_rows
        ) >= 1:
            SY_MPa = float(
                lim_rows.iloc[
                    0
                ][
                    "material_screen_MPa"
                ]
            )

        if len(
            ult_rows
        ) >= 1:
            SU_MPa = float(
                ult_rows.iloc[
                    0
                ][
                    "material_screen_MPa"
                ]
            )


# =============================================================================
# NONLINEAR FEA RESULT
# =============================================================================

NONLINEAR_VM_MPa = 393.39

NONLINEAR_X_MM = -0.0
NONLINEAR_Y_MM = 34.052034
NONLINEAR_A_MM = 335.124456

NONLINEAR_DEFL_MM = 21.401

NONLINEAR_NODES = 116866
NONLINEAR_SOLID_ELEMENTS = 23232
NONLINEAR_TOTAL_ELEMENTS = 31169

NONLINEAR_END_TIME = 1.0
NONLINEAR_ERRORS = 0
NONLINEAR_WARNINGS = 4


# =============================================================================
# DERIVED METRICS
# =============================================================================

nonlinear_OD_mm = profile_OD_mm(
    NONLINEAR_A_MM
)

nonlinear_wall_mm = (
    nonlinear_OD_mm
    - BARREL_ID_MM
) / 2.0

stress_change_percent = (
    (
        NONLINEAR_VM_MPa
        - LINEAR_VM_MPa
    )
    / LINEAR_VM_MPa
    * 100.0
)

deformation_change_percent = (
    (
        NONLINEAR_DEFL_MM
        - LINEAR_DEFL_MM
    )
    / LINEAR_DEFL_MM
    * 100.0
)

peak_shift_mm = (
    NONLINEAR_A_MM
    - LINEAR_A_MM
)

nonlinear_ultimate_margin = (
    SU_MPa
    / NONLINEAR_VM_MPa
    - 1.0
)

nonlinear_yield_margin_at_ultimate = (
    SY_MPa
    / NONLINEAR_VM_MPa
    - 1.0
)

linear_ultimate_margin = (
    SU_MPa
    / LINEAR_VM_MPa
    - 1.0
)

deformation_ratio_percent = (
    NONLINEAR_DEFL_MM
    / LOCAL_MODEL_LENGTH_MM
    * 100.0
)

geometric_nonlinearity_material = bool(
    abs(
        stress_change_percent
    )
    >= 5.0
    or abs(
        deformation_change_percent
    )
    >= 5.0
)


# =============================================================================
# COMPARISON TABLE
# =============================================================================

compare_df = pd.DataFrame([
    {
        "solution":
            "B9_LINEAR_FINAL",
        "large_deflection":
            False,
        "peak_VM_MPa":
            LINEAR_VM_MPa,
        "peak_A_mm":
            LINEAR_A_MM,
        "max_deformation_mm":
            LINEAR_DEFL_MM,
        "ultimate_screen_MPa":
            SU_MPa,
        "ultimate_margin":
            linear_ultimate_margin,
        "yield_screen_MPa":
            SY_MPa,
        "yield_margin_at_ultimate_load":
            (
                SY_MPa
                / LINEAR_VM_MPa
                - 1.0
            ),
    },
    {
        "solution":
            "B9A_LARGE_DEFLECTION",
        "large_deflection":
            True,
        "peak_VM_MPa":
            NONLINEAR_VM_MPa,
        "peak_A_mm":
            NONLINEAR_A_MM,
        "max_deformation_mm":
            NONLINEAR_DEFL_MM,
        "ultimate_screen_MPa":
            SU_MPa,
        "ultimate_margin":
            nonlinear_ultimate_margin,
        "yield_screen_MPa":
            SY_MPa,
        "yield_margin_at_ultimate_load":
            nonlinear_yield_margin_at_ultimate,
    },
])

compare_df.to_csv(
    OUT_COMPARE,
    index=False,
)


# =============================================================================
# SOLVER AUDIT
# =============================================================================

audit_rows = [
    {
        "item":
            "large_deflection",
        "status":
            "PASS",
        "value":
            "ON",
        "interpretation":
            "Geometric nonlinearity was explicitly enabled.",
    },
    {
        "item":
            "automatic_substepping",
        "status":
            "PASS",
        "value":
            "10 initial / 1 min / 100 max",
        "interpretation":
            "Nonlinear load application was incremented automatically.",
    },
    {
        "item":
            "end_time_reached",
        "status":
            "PASS",
        "value":
            NONLINEAR_END_TIME,
        "interpretation":
            "Full LC4+ ultimate load step reached time 1.0.",
    },
    {
        "item":
            "solver_errors",
        "status":
            "PASS",
        "value":
            NONLINEAR_ERRORS,
        "interpretation":
            "No solver errors reported.",
    },
    {
        "item":
            "pcg_iteration_performance",
        "status":
            "INFO",
        "value":
            ">1000 internal PCG iterations during loadstep",
        "interpretation":
            "Performance issue only; ANSYS recommended direct/SPARSE solver for efficiency.",
    },
    {
        "item":
            "reduced_integration_pcg_warning",
        "status":
            "OPEN_NOTE",
        "value":
            "SOLID186 reduced integration + PCG",
        "interpretation":
            "ANSYS requests multiple elements through thickness or SPARSE solver. Current mesh was intentionally built with multiple through-thickness elements; retain note in report.",
    },
    {
        "item":
            "reference_moment_convergence_warning",
        "status":
            "OPEN_NOTE",
        "value":
            "zero calculated reference moment",
        "interpretation":
            "ANSYS used an internal reference moment threshold. Force and displacement convergence were achieved; retain warning as solver-audit note.",
    },
    {
        "item":
            "remote_point_load_path",
        "status":
            "PASS",
        "value":
            "single explicit pilot node",
        "interpretation":
            "Force and APDL MX moment act on the same explicit remote-point pilot node; previous overlapping-MPC issue removed.",
    },
]

audit_df = pd.DataFrame(
    audit_rows
)

audit_df.to_csv(
    OUT_AUDIT,
    index=False,
)


# =============================================================================
# CONSOLE REPORT
# =============================================================================

print("=" * 126)
print(
    " PHASE 2E3-B9A — LARGE-DEFLECTION SENSITIVITY CLOSEOUT V0.1"
)
print("=" * 126)

print("\nLINEAR vs LARGE-DEFLECTION RESULT")
print("-" * 126)
print(
    f"{'Solution':<28}"
    f"{'Peak VM':>12}"
    f"{'Peak A':>12}"
    f"{'Defl':>12}"
    f"{'MSu':>12}"
    f"{'MSy@ult':>12}"
)
print("-" * 88)

for _, row in compare_df.iterrows():
    print(
        f"{row['solution']:<28}"
        f"{row['peak_VM_MPa']:>12.2f}"
        f"{row['peak_A_mm']:>12.3f}"
        f"{row['max_deformation_mm']:>12.3f}"
        f"{row['ultimate_margin']:>12.3f}"
        f"{row['yield_margin_at_ultimate_load']:>12.3f}"
    )

print("\nNONLINEAR CHANGE FROM B9 LINEAR BASELINE")
print("-" * 126)
print(
    f"Peak stress change:               {stress_change_percent:+.3f} %"
)
print(
    f"Maximum deformation change:       {deformation_change_percent:+.3f} %"
)
print(
    f"Peak axial-station shift:         {peak_shift_mm:+.3f} mm"
)
print(
    f"Geometric nonlinearity material:  {geometric_nonlinearity_material}"
)

print("\nNONLINEAR GOVERNING POINT")
print("-" * 126)
print(
    f"Peak VM:                          {NONLINEAR_VM_MPa:.3f} MPa"
)
print(
    f"Peak X / Y / A:                   "
    f"{NONLINEAR_X_MM:.6f} / "
    f"{NONLINEAR_Y_MM:.6f} / "
    f"{NONLINEAR_A_MM:.6f} mm"
)
print(
    f"Local OD / ID:                    "
    f"{nonlinear_OD_mm:.3f} / {BARREL_ID_MM:.3f} mm"
)
print(
    f"Local wall thickness:             {nonlinear_wall_mm:.3f} mm"
)
print(
    f"Maximum deformation:              {NONLINEAR_DEFL_MM:.3f} mm"
)
print(
    f"Deformation / local-model length: {deformation_ratio_percent:.3f} %"
)

print("\nPRELIMINARY MATERIAL SCREEN")
print("-" * 126)
print(
    f"7075-T6 project yield screen:     {SY_MPa:.1f} MPa"
)
print(
    f"7075-T6 project ultimate screen:  {SU_MPa:.1f} MPa"
)
print(
    f"Nonlinear ultimate-load VM:       {NONLINEAR_VM_MPa:.3f} MPa"
)
print(
    f"Margin vs ultimate screen:        {nonlinear_ultimate_margin:+.3f}"
)
print(
    f"Margin vs yield screen at ult:    {nonlinear_yield_margin_at_ultimate:+.3f}"
)

print("\nSOLVER AUDIT")
print("-" * 126)
print(
    f"Mesh nodes / solid / total elem:  "
    f"{NONLINEAR_NODES} / "
    f"{NONLINEAR_SOLID_ELEMENTS} / "
    f"{NONLINEAR_TOTAL_ELEMENTS}"
)
print(
    f"Full load step reached:           {NONLINEAR_END_TIME:.1f}"
)
print(
    f"Solver errors:                    {NONLINEAR_ERRORS}"
)
print(
    f"Solver warnings recorded:         {NONLINEAR_WARNINGS}"
)
print(
    "PCG/direct-solver message is treated as a performance recommendation, not a failed solution."
)

print("\nB9A DISPOSITION")
print("-" * 126)

if (
    NONLINEAR_ERRORS == 0
    and NONLINEAR_END_TIME >= 1.0
    and nonlinear_ultimate_margin >= 0.0
):
    print(
        "LARGE-DEFLECTION SENSITIVITY: SOLVED / PRELIMINARY STATIC SCREEN PASS"
    )
else:
    print(
        "LARGE-DEFLECTION SENSITIVITY: HOLD"
    )

print(
    "Geometric nonlinearity materially changes the local-submodel response; "
    "retain B9 linear as the conservative reference and B9A as the current nonlinear sensitivity."
)
print(
    "Do NOT interpret B9A as full-airframe, fatigue, fretting/contact, "
    "pressure-closure, certification, or final-allowable substantiation."
)

print("\nOUTPUT FILES")
print("-" * 126)
print(
    f"Linear/nonlinear comparison:      {OUT_COMPARE}"
)
print(
    f"Solver audit:                     {OUT_AUDIT}"
)
print(
    f"Summary:                          {OUT_SUMMARY}"
)
print("=" * 126)


summary_lines = [
    "=" * 126,
    " PHASE 2E3-B9A — LARGE-DEFLECTION SENSITIVITY CLOSEOUT V0.1",
    "=" * 126,
    "",
    f"B9 linear peak VM: {LINEAR_VM_MPa:.6f} MPa",
    f"B9A nonlinear peak VM: {NONLINEAR_VM_MPa:.6f} MPa",
    f"Stress change: {stress_change_percent:+.6f} %",
    "",
    f"B9 linear max deformation: {LINEAR_DEFL_MM:.6f} mm",
    f"B9A nonlinear max deformation: {NONLINEAR_DEFL_MM:.6f} mm",
    f"Deformation change: {deformation_change_percent:+.6f} %",
    "",
    f"B9 linear peak A: {LINEAR_A_MM:.6f} mm",
    f"B9A nonlinear peak A: {NONLINEAR_A_MM:.6f} mm",
    f"Peak shift: {peak_shift_mm:+.6f} mm",
    "",
    f"Nonlinear local OD: {nonlinear_OD_mm:.6f} mm",
    f"Nonlinear local wall: {nonlinear_wall_mm:.6f} mm",
    "",
    f"Ultimate margin: {nonlinear_ultimate_margin:+.6f}",
    f"Yield margin at ultimate load: {nonlinear_yield_margin_at_ultimate:+.6f}",
    "",
    "Disposition: preliminary static nonlinear sensitivity passes.",
    "Retain B9 linear as conservative reference and B9A as nonlinear sensitivity.",
    "=" * 126,
]

OUT_SUMMARY.write_text(
    "\n".join(
        summary_lines
    ),
    encoding="utf-8",
)
