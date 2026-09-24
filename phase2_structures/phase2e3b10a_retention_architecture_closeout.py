"""
Landing_Gear_Design_Project
Phase 2E3-B10A — Cross-Trunnion Positive Retention Architecture Closeout V0.1

Purpose
-------
Close the retention/locking architecture left open by B10.

B10 V0.1 screened a transverse 300M keeper pin in double shear. That proved the
keeper PIN itself was not strength-driven, but it did NOT validate the local
cross-hole introduced into the main 38 mm trunnion shaft/head region.

B10A therefore separates two concepts:

    Concept A — central transverse keeper pin
        Static pin shear: feasible
        Main-shaft cross-hole: creates an avoidable local discontinuity
        Disposition: NOT selected as the working architecture

    Concept B — outboard positive retention
        - uniform 38 mm working trunnion through the head/journal span
        - dedicated thrust washer/spacer on each side of the 106 mm head
        - axial Fx is reacted at one thrust face, conservatively one side at a time
        - shaft positively retained outboard by:
              integral flange/head on one end
              threaded tail + castellated/slotted nut on the other
              cotter pin / positive secondary lock through the OUTBOARD tail
        - no thread, groove, or keeper cross-hole is introduced in the working
          journal/root span
        - Mx remains on the independent upper brace / lock-link path

This is an architecture closeout, not final hardware sizing.
Final thread standard, nut, washer material, fits, tolerances and airframe-lug
geometry remain to be selected after B11/B12 local structural validation.
"""

from __future__ import annotations

import csv
import math
import re
from pathlib import Path


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent

B10_RECORD = HERE / "phase2e3b10_design_record.csv"
B10_SPAN = HERE / "phase2e3b10_span_trade.csv"

LOAD_CANDIDATES = [
    PROJECT_ROOT / "phase1_loads" / "phase1_load_envelope.csv",
    HERE / "phase1_load_envelope.csv",
]

# Working B10 values; source-read values take precedence.
FALLBACK_HEAD_OD_MM = 106.0
FALLBACK_SPAN_MM = 150.0
FALLBACK_SHAFT_D_MM = 38.0
FALLBACK_BEARING_WIDTH_MM = 25.0

# Existing project 300M screens.
SY_300M_MPA = 1517.0
SU_300M_MPA = 1862.0

# Candidate nominal thread-root diameters.
# These are NOT standard thread selections; they are only axial-area sensitivity.
THREAD_ROOT_DIAMETER_SWEEP_MM = [
    12.0,
    16.0,
    20.0,
    24.0,
    28.0,
    30.0,
]


def read_csv_rows(path: Path):
    with path.open(
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as f:
        return list(csv.DictReader(f))


def read_b10_value(
    parameter: str,
    fallback: float,
) -> tuple[float, str]:
    if B10_RECORD.exists():
        rows = read_csv_rows(B10_RECORD)
        for row in rows:
            if row.get("parameter") == parameter:
                return float(row["value"]), str(B10_RECORD)

    return fallback, "FALLBACK_FROM_B10_V0.1_WORKING_GEOMETRY"


def normalized_header_map(fieldnames):
    return {
        re.sub(r"[^a-z0-9]+", "", name.lower()): name
        for name in fieldnames
    }


def resolve_column(fieldnames, aliases):
    hmap = normalized_header_map(fieldnames)

    for alias in aliases:
        key = re.sub(r"[^a-z0-9]+", "", alias.lower())
        if key in hmap:
            return hmap[key]

    raise KeyError(
        f"Could not resolve {aliases} from {fieldnames}"
    )


def find_load_source():
    for path in LOAD_CANDIDATES:
        if path.exists():
            return path

    raise FileNotFoundError(
        "Could not find phase1_load_envelope.csv."
    )


def read_max_axial_loads(path: Path):
    with path.open(
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []

        case_col = resolve_column(
            fields,
            ["Load Case", "case", "load_case"],
        )
        fx_limit_col = resolve_column(
            fields,
            ["Fx Limit (kN)", "Fx_limit_kN"],
        )
        fx_ultimate_col = resolve_column(
            fields,
            ["Fx Ultimate (kN)", "Fx_ultimate_kN"],
        )

        rows = list(reader)

    limit_row = max(
        rows,
        key=lambda row: abs(float(row[fx_limit_col])),
    )
    ultimate_row = max(
        rows,
        key=lambda row: abs(float(row[fx_ultimate_col])),
    )

    return {
        "limit_case": limit_row[case_col].strip(),
        "limit_Fx_kN": abs(float(limit_row[fx_limit_col])),
        "ultimate_case":
            ultimate_row[case_col].strip(),
        "ultimate_Fx_kN":
            abs(float(ultimate_row[fx_ultimate_col])),
    }


def thread_root_screen(
    Fx_limit_kN: float,
    Fx_ultimate_kN: float,
):
    rows = []

    for d_root_mm in THREAD_ROOT_DIAMETER_SWEEP_MM:
        area_mm2 = math.pi * d_root_mm**2 / 4.0

        sigma_limit_MPa = (
            Fx_limit_kN * 1000.0
            / area_mm2
        )
        sigma_ultimate_MPa = (
            Fx_ultimate_kN * 1000.0
            / area_mm2
        )

        rows.append({
            "nominal_thread_root_diameter_mm":
                d_root_mm,
            "root_area_mm2":
                area_mm2,
            "limit_axial_stress_MPa":
                sigma_limit_MPa,
            "MS_limit_yield":
                SY_300M_MPA / sigma_limit_MPa - 1.0,
            "ultimate_axial_stress_MPa":
                sigma_ultimate_MPa,
            "MS_ultimate":
                SU_300M_MPA
                / sigma_ultimate_MPa
                - 1.0,
        })

    return rows


def write_csv(path: Path, rows):
    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=list(rows[0].keys()),
        )
        writer.writeheader()
        writer.writerows(rows)


def main():
    head_od_mm, head_src = read_b10_value(
        "B9_upper_head_OD",
        FALLBACK_HEAD_OD_MM,
    )
    span_mm, span_src = read_b10_value(
        "working_bearing_center_span",
        FALLBACK_SPAN_MM,
    )
    shaft_d_mm, shaft_src = read_b10_value(
        "working_300M_cross_shaft_diameter",
        FALLBACK_SHAFT_D_MM,
    )

    # Bearing width was not necessarily stored as a design-record row.
    bearing_width_mm = FALLBACK_BEARING_WIDTH_MM

    if B10_SPAN.exists():
        rows = read_csv_rows(B10_SPAN)
        for row in rows:
            if (
                abs(float(row["span_mm"]) - span_mm)
                < 1e-12
            ):
                bearing_width_mm = float(
                    row["bearing_width_mm"]
                )
                break

    side_gap_mm = (
        span_mm
        - head_od_mm
        - bearing_width_mm
    ) / 2.0

    load_source = find_load_source()
    axial = read_max_axial_loads(load_source)

    # Minimum gross equivalent tensile area/diameter required if the tail were
    # sized ONLY by direct axial stress. This is deliberately not used as a
    # hardware selection because thread fatigue, preload, standard sizes and
    # manufacturing control the practical choice.
    A_req_limit_mm2 = (
        axial["limit_Fx_kN"] * 1000.0
        / SY_300M_MPA
    )
    A_req_ultimate_mm2 = (
        axial["ultimate_Fx_kN"] * 1000.0
        / SU_300M_MPA
    )

    d_eq_limit_mm = math.sqrt(
        4.0 * A_req_limit_mm2 / math.pi
    )
    d_eq_ultimate_mm = math.sqrt(
        4.0 * A_req_ultimate_mm2 / math.pi
    )

    thread_rows = thread_root_screen(
        axial["limit_Fx_kN"],
        axial["ultimate_Fx_kN"],
    )

    architecture_rows = [
        {
            "item": "Concept_A_central_keeper_pin",
            "classification": "SCREENED_NOT_SELECTED",
            "result":
                "Keeper pin shear was feasible in B10 V0.1, but the "
                "central cross-hole creates an avoidable stress concentration "
                "in the main shaft/head region.",
        },
        {
            "item": "Concept_B_outboard_positive_retention",
            "classification": "WORKING_B10A_SELECTION",
            "result":
                "Uniform 38 mm working shaft through loaded span; integral "
                "flange/head at one outboard end; threaded tail with "
                "castellated/slotted nut and cotter/positive secondary lock "
                "beyond the opposite support bearing.",
        },
        {
            "item": "axial_Fx_load_path",
            "classification": "WORKING_B10A_SELECTION",
            "result":
                "Dedicated thrust washer/spacer between upper head and "
                "airframe support; conservatively one side reacts full |Fx|.",
        },
        {
            "item": "Mx_load_path",
            "classification": "FROZEN_ARCHITECTURE_RULE",
            "result":
                "Mx is not credited to shaft retention hardware; it remains "
                "on the independent upper brace / lock-link path.",
        },
        {
            "item": "journal_discontinuity_rule",
            "classification": "WORKING_B10A_RULE",
            "result":
                "No thread, retaining groove, or keeper cross-hole in the "
                "working journal/root span. Locking feature stays outboard "
                "of the bearing support plane.",
        },
        {
            "item": "thread_size",
            "classification": "NOT_YET_FROZEN",
            "result":
                "Select from a real standard only after airframe fitting, "
                "preload/torque, fatigue and manufacturing checks. B10A only "
                "shows that direct axial strength is not the driver.",
        },
    ]

    out_thread = (
        HERE
        / "phase2e3b10a_thread_root_sensitivity.csv"
    )
    out_arch = (
        HERE
        / "phase2e3b10a_retention_architecture.csv"
    )
    out_summary = (
        HERE
        / "phase2e3b10a_retention_summary.txt"
    )

    write_csv(out_thread, thread_rows)
    write_csv(out_arch, architecture_rows)

    line = "=" * 124
    dash = "-" * 124

    print()
    print(line)
    print(
        " PHASE 2E3-B10A — CROSS-TRUNNION POSITIVE RETENTION "
        "ARCHITECTURE CLOSEOUT V0.1"
    )
    print(line)

    print()
    print("SOURCE CONNECTION")
    print(dash)
    print(f"B10 head source:                  {head_src}")
    print(f"B10 span source:                  {span_src}")
    print(f"B10 shaft source:                 {shaft_src}")
    print(f"Load source:                      {load_source}")

    print()
    print("RETAINED B10 WORKING GEOMETRY")
    print(dash)
    print(f"Head OD:                          {head_od_mm:.3f} mm")
    print(f"Bearing-center span:              {span_mm:.3f} mm")
    print(f"Bearing width:                    {bearing_width_mm:.3f} mm")
    print(f"Working shaft diameter:           {shaft_d_mm:.3f} mm")
    print(f"Available head-to-bearing gap:    {side_gap_mm:.3f} mm per side")

    print()
    print("AXIAL RETENTION LOAD")
    print(dash)
    print(
        f"Limit |Fx|:                       "
        f"{axial['limit_Fx_kN']:.5f} kN "
        f"({axial['limit_case']})"
    )
    print(
        f"Ultimate |Fx|:                    "
        f"{axial['ultimate_Fx_kN']:.5f} kN "
        f"({axial['ultimate_case']})"
    )
    print(
        f"300M direct-tension yield screen: {SY_300M_MPA:.1f} MPa"
    )
    print(
        f"300M direct-tension UTS screen:   {SU_300M_MPA:.1f} MPa"
    )
    print(
        f"Strength-only req. area, limit:   {A_req_limit_mm2:.3f} mm^2"
    )
    print(
        f"Strength-only req. area, ult:     {A_req_ultimate_mm2:.3f} mm^2"
    )
    print(
        f"Equivalent solid d, limit:        {d_eq_limit_mm:.3f} mm"
    )
    print(
        f"Equivalent solid d, ultimate:     {d_eq_ultimate_mm:.3f} mm"
    )
    print(
        "Interpretation: direct axial strength is tiny relative to the 38 mm "
        "shaft. Standard thread/fatigue/manufacturing requirements will govern."
    )

    print()
    print("THREAD-ROOT DIAMETER SENSITIVITY — DIRECT AXIAL STRESS ONLY")
    print(dash)
    print(
        f"{'d_root':>10}"
        f"{'sigma_lim':>14}"
        f"{'MSy':>12}"
        f"{'sigma_ult':>14}"
        f"{'MSu':>12}"
    )
    print("-" * 64)

    for row in thread_rows:
        print(
            f"{row['nominal_thread_root_diameter_mm']:>9.0f} "
            f"{row['limit_axial_stress_MPa']:>12.2f} "
            f"{row['MS_limit_yield']:>10.3f} "
            f"{row['ultimate_axial_stress_MPa']:>12.2f} "
            f"{row['MS_ultimate']:>10.3f}"
        )

    print()
    print("CONCEPT A — CENTRAL KEEPER PIN")
    print(dash)
    print(
        "B10 V0.1 proved the keeper pin itself is very lightly stressed."
    )
    print(
        "However, its required cross-hole would introduce a new local notch "
        "in the main trunnion/head region."
    )
    print(
        "Disposition: SCREENED BUT NOT SELECTED. Keep the B10 V0.1 result "
        "in the repository for traceability."
    )

    print()
    print("CONCEPT B — SELECTED WORKING POSITIVE RETENTION ARCHITECTURE")
    print(dash)
    print(
        "1. Keep the 38 mm main shaft geometrically continuous through the "
        "head and loaded journal/root span."
    )
    print(
        "2. Use a dedicated thrust washer/spacer in the available side gap; "
        "one side conservatively reacts full |Fx|."
    )
    print(
        "3. Retain the shaft outboard with an integral flange/head on one end."
    )
    print(
        "4. Use a reduced threaded tail beyond the opposite support bearing "
        "with a castellated/slotted nut."
    )
    print(
        "5. Positively lock the nut with a cotter pin or equivalent approved "
        "mechanical secondary lock located OUTBOARD of the bearing."
    )
    print(
        "6. Do not put threads, grooves, or a keeper cross-hole in the "
        "working journal/root span."
    )
    print(
        "7. Do not credit this retention system with reacting Mx; the "
        "independent upper brace remains the Mx reaction path."
    )

    print()
    print("STATUS")
    print(dash)
    print(
        "Positive retention architecture:      SELECTED FOR B11/B12 DEVELOPMENT"
    )
    print(
        "Final thread/nut/washer dimensions:   OPEN"
    )
    print(
        "Journal/root main-shaft diameter:     38 mm WORKING B10 VALUE"
    )
    print(
        "Central 8 mm keeper pin:              SUPERSEDED AS WORKING ARCHITECTURE"
    )
    print(
        "Reason: eliminate avoidable main-shaft cross-hole before local FEA."
    )
    print(
        "Next: B11 analytical head-bore, edge-ligament, net-section and "
        "thrust-face screens; then B12 local contact/FEA."
    )

    summary = [
        line,
        "PHASE 2E3-B10A — RETENTION ARCHITECTURE CLOSEOUT V0.1",
        line,
        "",
        f"Head OD = {head_od_mm:.3f} mm",
        f"Span = {span_mm:.3f} mm",
        f"Shaft = {shaft_d_mm:.3f} mm",
        f"Side gap = {side_gap_mm:.3f} mm",
        f"Ultimate |Fx| = {axial['ultimate_Fx_kN']:.5f} kN "
        f"({axial['ultimate_case']})",
        "",
        "Concept A central keeper pin: screened, NOT selected.",
        "Reason: avoid a transverse cross-hole in the main loaded shaft/head region.",
        "",
        "Concept B selected:",
        "- uniform main shaft through loaded span",
        "- dedicated thrust washer/spacer for Fx",
        "- integral outboard flange/head at one end",
        "- threaded outboard tail + castellated/slotted nut at the other",
        "- positive secondary nut lock outboard of support bearing",
        "- no Mx credit; Mx remains on independent upper brace",
        "",
        "Final thread/nut/washer dimensions remain open pending B11/B12.",
    ]

    out_summary.write_text(
        "\n".join(summary) + "\n",
        encoding="utf-8",
    )

    print()
    print("OUTPUT FILES")
    print(dash)
    print(f"Architecture record:              {out_arch}")
    print(f"Thread-root sensitivity:          {out_thread}")
    print(f"Summary:                          {out_summary}")
    print(line)


if __name__ == "__main__":
    main()
