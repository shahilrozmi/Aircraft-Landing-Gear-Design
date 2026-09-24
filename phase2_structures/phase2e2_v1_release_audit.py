from pathlib import Path
import hashlib
import math

import numpy as np
import pandas as pd


# =============================================================================
# LANDING GEAR DESIGN PROJECT
# PHASE 2E2 — V1 RELEASE / FREEZE AUDIT
#
# PURPOSE
#   Consolidate the completed Phase 2E2 analyses into one release gate.
#
#   This script does NOT redesign the oleo. It verifies that the current project
#   outputs remain mutually consistent and records the Phase 2E2 V1 baseline:
#
#       - retained 64 / 74 mm 7075-T6 barrel,
#       - 58 x 4 mm 300M piston,
#       - smooth-linear Phase 1 metering law,
#       - 14 mm fixed metering bore / profiled pin,
#       - volume-consistent upper gas/oil cavity,
#       - continuity-derived pressure-closure station,
#       - preliminary 6 mm pressure-closure structural screen,
#       - E2 -> E3 solid-head interface.
#
# RELEASE BOUNDARY
#   "Frozen" here means frozen at PRELIMINARY ARCHITECTURE / STRUCTURAL-SCREEN
#   level. Detailed CAD geometry for seals, retainers, threads, ports, local
#   fillets and the upper trunnion still belongs to subsequent detail work.
# =============================================================================


# =============================================================================
# 1. PATHS
# =============================================================================

HERE = Path(__file__).resolve().parent

FILES = {
    "architecture": HERE / "phase2e2_architecture_inputs.csv",
    "states": HERE / "phase2e2_stroke_cavity_states.csv",
    "metering_candidate": HERE / "phase2e2_metering_working_candidate.csv",
    "metering_profile": HERE / "phase2e2_metering_pin_profile_map.csv",
    "metering_compare": HERE / "phase2e2_metering_law_comparison.csv",
    "metering_delta": HERE / "phase2e2_metering_law_delta.csv",
    "continuity_states": HERE / "phase2e2c_fluid_continuity_states.csv",
    "continuity_checks": HERE / "phase2e2c_continuity_checks.csv",
    "closure_screen": HERE / "phase2e2c_closure_structural_screen.csv",
    "e3_interface": HERE / "phase2e2c_e3_interface.csv",
}

OUTPUT_CHECKS = HERE / "phase2e2_v1_release_checks.csv"
OUTPUT_BASELINE = HERE / "phase2e2_v1_baseline.csv"
OUTPUT_MANIFEST = HERE / "phase2e2_v1_source_manifest.csv"
OUTPUT_REPORT = HERE / "phase2e2_v1_release_report.txt"


# =============================================================================
# 2. EXPECTED RELEASE BASELINE
# =============================================================================

EXPECTED = {
    "barrel_ID_mm": 64.0,
    "barrel_OD_mm": 74.0,
    "piston_OD_mm": 58.0,
    "piston_ID_mm": 50.0,
    "fixed_orifice_bore_mm": 14.0,
    "metering_design_stroke_mm": 205.0,
    "d_eq_start_mm": 10.3010,
    "d_eq_end_mm": 9.7420,
    "physical_stroke_mm": 230.0,
    "closure_grid_mm": 6.0,
}

TOL = {
    "geometry_mm": 0.10,
    "metering_mm": 0.002,
    "continuity_cm3": 0.05,
    "closure_mm": 0.10,
}


# =============================================================================
# 3. HELPERS
# =============================================================================

def normalize(text):
    return "".join(
        ch for ch in str(text).lower()
        if ch.isalnum()
    )


def read_csv(path):
    if not path.exists():
        raise FileNotFoundError(
            f"Required Phase 2E2 release source is missing:\n{path}"
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


def parameter_float(df, parameter):
    cols = {
        normalize(col): col
        for col in df.columns
    }

    if "parameter" not in cols or "value" not in cols:
        raise ValueError(
            "Expected parameter/value CSV table."
        )

    pcol = cols["parameter"]
    vcol = cols["value"]

    mask = (
        df[pcol]
        .astype(str)
        .map(normalize)
        == normalize(parameter)
    )

    rows = df.loc[mask]

    if rows.empty:
        raise KeyError(
            f"Parameter not found: {parameter}"
        )

    return float(
        pd.to_numeric(
            pd.Series([rows.iloc[0][vcol]]),
            errors="raise",
        ).iloc[0]
    )


def interface_value(df, quantity):
    cols = {
        normalize(col): col
        for col in df.columns
    }

    qcol = cols.get("quantity")
    vcol = cols.get("value")

    if qcol is None or vcol is None:
        raise ValueError(
            "Expected quantity/value interface table."
        )

    mask = (
        df[qcol]
        .astype(str)
        .map(normalize)
        == normalize(quantity)
    )

    rows = df.loc[mask]

    if rows.empty:
        raise KeyError(
            f"Interface quantity not found: {quantity}"
        )

    return float(rows.iloc[0][vcol])


def state_row(df, name):
    mask = (
        df["state"]
        .astype(str)
        .map(normalize)
        == normalize(name)
    )

    rows = df.loc[mask]

    if rows.empty:
        raise KeyError(
            f"State not found: {name}"
        )

    return rows.iloc[0]


def add_check(
    checks,
    name,
    value,
    criterion,
    passed,
    units="",
    note="",
):
    checks.append({
        "check": name,
        "value": value,
        "units": units,
        "criterion": criterion,
        "status": "PASS" if passed else "FAIL",
        "note": note,
    })


def sha256(path):
    h = hashlib.sha256()

    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)

            if not chunk:
                break

            h.update(chunk)

    return h.hexdigest()


# =============================================================================
# 4. MAIN
# =============================================================================

def main():

    print("=" * 124)
    print(" PHASE 2E2 — V1 RELEASE / FREEZE AUDIT")
    print("=" * 124)

    data = {
        name: read_csv(path)
        for name, path in FILES.items()
    }

    arch = data["architecture"]
    states = data["states"]
    candidate = data["metering_candidate"]
    compare = data["metering_compare"]
    continuity_states = data["continuity_states"]
    continuity_checks = data["continuity_checks"]
    closure_screen = data["closure_screen"]
    e3_interface = data["e3_interface"]

    checks = []

    # -------------------------------------------------------------------------
    # Geometry
    # -------------------------------------------------------------------------

    barrel_ID = parameter_float(
        arch,
        "barrel_ID",
    )

    barrel_OD = parameter_float(
        arch,
        "barrel_OD",
    )

    piston_OD = parameter_float(
        arch,
        "piston_OD",
    )

    piston_ID = parameter_float(
        arch,
        "piston_ID",
    )

    for label, value, expected in [
        ("BARREL_ID", barrel_ID, EXPECTED["barrel_ID_mm"]),
        ("BARREL_OD", barrel_OD, EXPECTED["barrel_OD_mm"]),
        ("PISTON_OD", piston_OD, EXPECTED["piston_OD_mm"]),
        ("PISTON_ID", piston_ID, EXPECTED["piston_ID_mm"]),
    ]:
        add_check(
            checks,
            label,
            value,
            f"|value - {expected}| <= {TOL['geometry_mm']} mm",
            abs(value - expected) <= TOL["geometry_mm"],
            "mm",
        )

    radial_clearance = (
        barrel_ID - piston_OD
    ) / 2.0

    add_check(
        checks,
        "BARREL_TO_PISTON_RADIAL_CLEARANCE",
        radial_clearance,
        "> 0 mm",
        radial_clearance > 0.0,
        "mm / side",
    )

    # -------------------------------------------------------------------------
    # Metering baseline
    # -------------------------------------------------------------------------

    fixed_bore = parameter_float(
        candidate,
        "fixed_orifice_bore",
    )

    x_design = parameter_float(
        candidate,
        "phase1_metering_design_stroke",
    )

    d_start = parameter_float(
        candidate,
        "phase1_equivalent_orifice_start",
    )

    d_end = parameter_float(
        candidate,
        "phase1_equivalent_orifice_end",
    )

    for label, value, expected in [
        ("FIXED_ORIFICE_BORE", fixed_bore, EXPECTED["fixed_orifice_bore_mm"]),
        ("METERING_DESIGN_STROKE", x_design, EXPECTED["metering_design_stroke_mm"]),
        ("EQUIVALENT_ORIFICE_START", d_start, EXPECTED["d_eq_start_mm"]),
        ("EQUIVALENT_ORIFICE_END", d_end, EXPECTED["d_eq_end_mm"]),
    ]:
        add_check(
            checks,
            label,
            value,
            f"|value - {expected}| <= {TOL['metering_mm']} mm",
            abs(value - expected) <= TOL["metering_mm"],
            "mm",
        )

    # -------------------------------------------------------------------------
    # Smooth vs historical two-stage audit
    # -------------------------------------------------------------------------

    smooth = compare.loc[
        compare["metering_law"]
        .astype(str)
        .map(normalize)
        == normalize("CURRENT_SMOOTH_LINEAR")
    ].iloc[0]

    twostage = compare.loc[
        compare["metering_law"]
        .astype(str)
        .map(normalize)
        == normalize("HISTORICAL_TWO_STAGE")
    ].iloc[0]

    smooth_stroke = float(
        smooth["peak_oleo_stroke_mm"]
    )

    two_stroke = float(
        twostage["peak_oleo_stroke_mm"]
    )

    smooth_strut = float(
        smooth["peak_internal_strut_force_kN"]
    )

    two_strut = float(
        twostage["peak_internal_strut_force_kN"]
    )

    smooth_hyd = float(
        smooth["peak_hydraulic_force_kN"]
    )

    two_hyd = float(
        twostage["peak_hydraulic_force_kN"]
    )

    add_check(
        checks,
        "SMOOTH_VS_TWOSTAGE_STROKE_DIFFERENCE",
        smooth_stroke - two_stroke,
        "|difference| <= 1.0 mm",
        abs(smooth_stroke - two_stroke) <= 1.0,
        "mm",
        "Smooth law preserves essentially identical peak stroke.",
    )

    add_check(
        checks,
        "SMOOTH_VS_TWOSTAGE_INTERNAL_STRUT_FORCE",
        smooth_strut - two_strut,
        "smooth <= two-stage",
        smooth_strut <= two_strut,
        "kN difference",
    )

    add_check(
        checks,
        "SMOOTH_VS_TWOSTAGE_HYDRAULIC_FORCE",
        smooth_hyd - two_hyd,
        "smooth <= two-stage",
        smooth_hyd <= two_hyd,
        "kN difference",
    )

    # -------------------------------------------------------------------------
    # Stroke reserve
    # -------------------------------------------------------------------------

    full_phys = state_row(
        states,
        "FULL_PHYSICAL_STROKE",
    )

    packaging_ref = state_row(
        states,
        "PHASE2D_NOMINAL_REFERENCE",
    )

    physical_stroke = float(
        full_phys["compression_mm"]
    )

    packaging_reference_stroke = float(
        packaging_ref["compression_mm"]
    )

    remaining_stroke = (
        physical_stroke
        - packaging_reference_stroke
    )

    add_check(
        checks,
        "PHYSICAL_STROKE_BASELINE",
        physical_stroke,
        f"|value - {EXPECTED['physical_stroke_mm']}| <= 0.1 mm",
        abs(
            physical_stroke
            - EXPECTED["physical_stroke_mm"]
        ) <= 0.1,
        "mm",
    )

    add_check(
        checks,
        "STROKE_RESERVE_AT_PHASE2D_REFERENCE",
        remaining_stroke,
        "> 0 mm",
        remaining_stroke > 0.0,
        "mm",
        "Phase 2D nominal remains a packaging reference, not static sag.",
    )

    # -------------------------------------------------------------------------
    # Continuity release checks
    # -------------------------------------------------------------------------

    all_continuity_pass = bool(
        continuity_checks["status"]
        .astype(str)
        .str.upper()
        .eq("PASS")
        .all()
    )

    add_check(
        checks,
        "PHASE2E2C_ALL_CONTINUITY_CHECKS",
        int(all_continuity_pass),
        "all continuity checks == PASS",
        all_continuity_pass,
        "boolean",
    )

    full_phys_cont = state_row(
        continuity_states,
        "FULL_PHYSICAL_STROKE",
    )

    virtual_cont = state_row(
        continuity_states,
        "VIRTUAL_DIAGNOSTIC",
    )

    reservoir_phys = float(
        full_phys_cont[
            "lower_reservoir_remaining_cm3"
        ]
    )

    reservoir_virtual = float(
        virtual_cont[
            "lower_reservoir_remaining_cm3"
        ]
    )

    add_check(
        checks,
        "LOWER_RESERVOIR_REMAINING_PHYSICAL",
        reservoir_phys,
        "> 0 cm^3",
        reservoir_phys > 0.0,
        "cm^3",
    )

    add_check(
        checks,
        "LOWER_RESERVOIR_REMAINING_VIRTUAL_DIAGNOSTIC",
        reservoir_virtual,
        "> 0 cm^3 diagnostic",
        reservoir_virtual > 0.0,
        "cm^3",
    )

    continuity_residual = float(
        continuity_states[
            "fixed_cavity_volume_residual_cm3"
        ]
        .abs()
        .max()
    )

    add_check(
        checks,
        "MAX_FIXED_CAVITY_VOLUME_RESIDUAL",
        continuity_residual,
        f"<= {TOL['continuity_cm3']} cm^3",
        continuity_residual <= TOL["continuity_cm3"],
        "cm^3",
    )

    # -------------------------------------------------------------------------
    # Closure / E3 interface
    # -------------------------------------------------------------------------

    closure_inner = interface_value(
        e3_interface,
        "continuity_based_pressure_closure_inner_face_above_U",
    )

    closure_theoretical_t = interface_value(
        e3_interface,
        "closure_theoretical_structural_minimum_thickness",
    )

    closure_grid_t = interface_value(
        e3_interface,
        "closure_first_0p5mm_grid_pass_thickness",
    )

    e3_outer_face = interface_value(
        e3_interface,
        "six_mm_screen_outer_face_above_U",
    )

    add_check(
        checks,
        "PRELIMINARY_CLOSURE_6MM",
        closure_grid_t,
        f"|value - {EXPECTED['closure_grid_mm']}| <= {TOL['closure_mm']} mm",
        abs(
            closure_grid_t
            - EXPECTED["closure_grid_mm"]
        ) <= TOL["closure_mm"],
        "mm",
    )

    add_check(
        checks,
        "CLOSURE_GRID_EXCEEDS_THEORETICAL_MIN",
        closure_grid_t - closure_theoretical_t,
        ">= 0 mm",
        closure_grid_t >= closure_theoretical_t,
        "mm reserve",
    )

    add_check(
        checks,
        "E3_INTERFACE_ABOVE_PRESSURE_CAVITY",
        e3_outer_face - closure_inner,
        "> 0 mm",
        e3_outer_face > closure_inner,
        "mm",
    )

    # Confirm the 6 mm row itself passes both checks.
    closure_6 = closure_screen.loc[
        np.isclose(
            pd.to_numeric(
                closure_screen["thickness_mm"],
                errors="coerce",
            ),
            6.0,
        )
    ]

    if closure_6.empty:
        closure_6_pass = False
    else:
        closure_6_pass = (
            str(
                closure_6.iloc[0][
                    "status"
                ]
            ).upper()
            == "PASS_BOTH"
        )

    add_check(
        checks,
        "CLOSURE_6MM_LIMIT_AND_ULTIMATE_STATUS",
        int(closure_6_pass),
        "6 mm row == PASS_BOTH",
        closure_6_pass,
        "boolean",
    )

    # -------------------------------------------------------------------------
    # Final release result
    # -------------------------------------------------------------------------

    checks_df = pd.DataFrame(
        checks
    )

    checks_df.to_csv(
        OUTPUT_CHECKS,
        index=False,
    )

    release_pass = bool(
        checks_df["status"]
        .eq("PASS")
        .all()
    )

    baseline = pd.DataFrame([
        {"parameter": "release_id", "value": "PHASE2E2-V1", "units": "-", "classification": "FROZEN_PRELIMINARY_ARCHITECTURE"},
        {"parameter": "barrel_ID", "value": barrel_ID, "units": "mm", "classification": "RETAINED_PHASE2D_WORKING_BASELINE"},
        {"parameter": "barrel_OD", "value": barrel_OD, "units": "mm", "classification": "RETAINED_PHASE2D_WORKING_BASELINE"},
        {"parameter": "barrel_wall", "value": (barrel_OD-barrel_ID)/2.0, "units": "mm", "classification": "RETAINED_PHASE2D_WORKING_BASELINE"},
        {"parameter": "piston_OD", "value": piston_OD, "units": "mm", "classification": "LOCKED"},
        {"parameter": "piston_ID", "value": piston_ID, "units": "mm", "classification": "LOCKED"},
        {"parameter": "physical_stroke", "value": physical_stroke, "units": "mm", "classification": "LOCKED"},
        {"parameter": "metering_law", "value": "SMOOTH_CLAMPED_LINEAR", "units": "-", "classification": "SELECTED_AFTER_COMPARISON"},
        {"parameter": "d_eq_start", "value": d_start, "units": "mm", "classification": "LOCKED_EFFECTIVE_MODEL"},
        {"parameter": "d_eq_end", "value": d_end, "units": "mm", "classification": "LOCKED_EFFECTIVE_MODEL"},
        {"parameter": "metering_design_stroke", "value": x_design, "units": "mm", "classification": "LOCKED_EFFECTIVE_MODEL"},
        {"parameter": "fixed_orifice_bore", "value": fixed_bore, "units": "mm", "classification": "E2_V1_WORKING_HARDWARE_BASELINE"},
        {"parameter": "pressure_closure_inner_face_above_U", "value": closure_inner, "units": "mm", "classification": "CONTINUITY_DERIVED"},
        {"parameter": "pressure_closure_theoretical_min_thickness", "value": closure_theoretical_t, "units": "mm", "classification": "SCREEN_ONLY"},
        {"parameter": "pressure_closure_preliminary_thickness", "value": closure_grid_t, "units": "mm", "classification": "PRELIMINARY_STRUCTURAL_SCREEN"},
        {"parameter": "preliminary_E3_interface_outer_face_above_U", "value": e3_outer_face, "units": "mm", "classification": "MINIMUM_SOLID_HEAD_INTERFACE"},
        {"parameter": "lower_reservoir_remaining_at_physical_stroke", "value": reservoir_phys, "units": "cm^3", "classification": "CONTINUITY_RESULT"},
        {"parameter": "release_status", "value": "PASS" if release_pass else "FAIL", "units": "-", "classification": "RELEASE_GATE"},
    ])

    baseline.to_csv(
        OUTPUT_BASELINE,
        index=False,
    )

    manifest_rows = []

    for name, path in FILES.items():
        manifest_rows.append({
            "source_key": name,
            "filename": path.name,
            "path": str(path.resolve()),
            "sha256": sha256(path),
        })

    manifest = pd.DataFrame(
        manifest_rows
    )

    manifest.to_csv(
        OUTPUT_MANIFEST,
        index=False,
    )

    # -------------------------------------------------------------------------
    # Human-readable report
    # -------------------------------------------------------------------------

    report_lines = []

    report_lines.append(
        "=" * 124
    )

    report_lines.append(
        " PHASE 2E2 — V1 RELEASE / FREEZE AUDIT"
    )

    report_lines.append(
        "=" * 124
    )

    report_lines.append("")
    report_lines.append(
        f"Release status:               {'PASS' if release_pass else 'FAIL'}"
    )
    report_lines.append(
        "Release level:                PRELIMINARY ARCHITECTURE / STRUCTURAL SCREEN"
    )
    report_lines.append("")
    report_lines.append(
        f"Barrel:                       {barrel_ID:.3f} mm ID / {barrel_OD:.3f} mm OD"
    )
    report_lines.append(
        f"Piston:                       {piston_OD:.3f} mm OD / {piston_ID:.3f} mm ID"
    )
    report_lines.append(
        f"Physical stroke:              {physical_stroke:.3f} mm"
    )
    report_lines.append(
        f"Stroke reserve at P2D ref.:   {remaining_stroke:.3f} mm"
    )
    report_lines.append("")
    report_lines.append(
        "Metering law:                 SMOOTH_CLAMPED_LINEAR"
    )
    report_lines.append(
        f"Equivalent orifice:           {d_start:.4f} -> {d_end:.4f} mm over {x_design:.3f} mm"
    )
    report_lines.append(
        f"Fixed metering bore:          {fixed_bore:.3f} mm"
    )
    report_lines.append("")
    report_lines.append(
        f"Closure inner face:           {closure_inner:.3f} mm above U"
    )
    report_lines.append(
        f"Theoretical closure minimum:  {closure_theoretical_t:.3f} mm"
    )
    report_lines.append(
        f"Preliminary closure screen:   {closure_grid_t:.3f} mm"
    )
    report_lines.append(
        f"Preliminary E3 interface:     {e3_outer_face:.3f} mm above U"
    )
    report_lines.append("")
    report_lines.append(
        f"Reservoir remaining @230 mm:  {reservoir_phys:.3f} cm^3"
    )
    report_lines.append("")
    report_lines.append(
        "Freeze boundary:"
    )
    report_lines.append(
        "  The Phase 2E2 hydraulic architecture, working barrel/piston geometry,"
    )
    report_lines.append(
        "  metering law, 14 mm metering-bore baseline, continuity-derived cavity"
    )
    report_lines.append(
        "  closure station, and preliminary 6 mm closure screen are released for"
    )
    report_lines.append(
        "  Phase 2E3 integration."
    )
    report_lines.append(
        "  Detailed seals, gland/retainer/thread geometry, ports, local fillets,"
    )
    report_lines.append(
        "  manufacturing tolerances, metering-pin support dynamics and local 3D"
    )
    report_lines.append(
        "  FEA remain later-detail items and are NOT claimed frozen here."
    )
    report_lines.append("")
    report_lines.append(
        f"Checks passed:                {(checks_df['status']=='PASS').sum()}/{len(checks_df)}"
    )
    report_lines.append(
        "=" * 124
    )

    OUTPUT_REPORT.write_text(
        "\n".join(report_lines),
        encoding="utf-8",
    )

    # -------------------------------------------------------------------------
    # Console
    # -------------------------------------------------------------------------

    print("\nRELEASE CHECKS")
    print("-" * 124)
    print(
        checks_df.to_string(
            index=False,
        )
    )

    print("\nPHASE 2E2 V1 BASELINE")
    print("-" * 124)
    print(
        baseline.to_string(
            index=False,
        )
    )

    print("\nRELEASE DISPOSITION")
    print("-" * 124)

    if release_pass:
        print(
            "PASS — Phase 2E2 V1 may be frozen at the preliminary architecture / "
            "structural-screen level and released to Phase 2E3."
        )
    else:
        print(
            "FAIL — do not freeze Phase 2E2. Review failed checks above."
        )

    print("\nOUTPUT FILES")
    print("-" * 124)
    print(
        f"Release checks:               {OUTPUT_CHECKS}"
    )
    print(
        f"Frozen baseline:              {OUTPUT_BASELINE}"
    )
    print(
        f"Source manifest:              {OUTPUT_MANIFEST}"
    )
    print(
        f"Release report:               {OUTPUT_REPORT}"
    )

    print("=" * 124)


if __name__ == "__main__":
    main()
