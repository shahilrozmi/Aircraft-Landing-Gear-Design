"""
Landing_Gear_Design_Project
PHASE 2E3-B14A — ANSYS BRACE-REACTION DECOMPOSITION DOCUMENTATION V0.1

Purpose
-------
Convert RAW ANSYS support-reaction results into a reproducible Python calculation
record before B14B is allowed to consume the brace reaction.

This script deliberately does NOT contain the frozen B14A result numbers.
Raw reaction values must come from ANSYS and be entered/exported into:
    phase2e3b14a_ansys_reactions_raw.csv

Required cases
--------------
    combined
    force_only
    moment_only
    pressure_only

The script computes:
    - signed and absolute SUP_BRACE_RX Mx for each case
    - force + moment + pressure superposition reconstruction
    - superposition residual
    - pressure contribution fraction
    - optional journal force-equilibrium residuals when raw journal reactions
      and applied forces are supplied

Outputs
-------
    phase2e3b14a_reaction_decomposition.csv
    phase2e3b14a_summary.txt
    phase2e3b14a_freeze_record.csv

B14B should read phase2e3b14a_freeze_record.csv, NOT copy values from chat.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Dict, List


HERE = Path(__file__).resolve().parent
RAW = HERE / "phase2e3b14a_ansys_reactions_raw.csv"

OUT_DECOMP = HERE / "phase2e3b14a_reaction_decomposition.csv"
OUT_FREEZE = HERE / "phase2e3b14a_freeze_record.csv"
OUT_SUMMARY = HERE / "phase2e3b14a_summary.txt"

REQUIRED_CASES = ("combined", "force_only", "moment_only", "pressure_only")

NUMERIC_FIELDS = [
    "pressure_MPa",
    "applied_Fx_N", "applied_Fy_N", "applied_Fz_N",
    "applied_Mx_Nmm", "applied_My_Nmm", "applied_Mz_Nmm",
    "brace_Rx_N", "brace_Ry_N", "brace_Rz_N",
    "brace_Mx_Nmm", "brace_My_Nmm", "brace_Mz_Nmm",
    "left_Rx_N", "left_Ry_N", "left_Rz_N",
    "right_Rx_N", "right_Ry_N", "right_Rz_N",
]

SUPERPOSITION_REL_TOL = 0.005   # 0.5% documentation/linearity check
PRESSURE_REL_WARN = 0.01        # warn if pressure Mx exceeds 1% of combined


def fnum(s: str):
    s = (s or "").strip()
    if s == "":
        return None
    return float(s)


def read_raw() -> Dict[str, dict]:
    if not RAW.exists():
        raise FileNotFoundError(
            f"Missing {RAW.name}. Populate the provided template with RAW ANSYS "
            "results before running B14A documentation."
        )

    out = {}
    with RAW.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            case = row["case"].strip().lower()
            if not case:
                continue
            for k in NUMERIC_FIELDS:
                row[k] = fnum(row.get(k, ""))
            out[case] = row

    missing = [c for c in REQUIRED_CASES if c not in out]
    if missing:
        raise ValueError(f"Missing required B14A case rows: {missing}")

    for c in REQUIRED_CASES:
        if out[c]["brace_Mx_Nmm"] is None:
            raise ValueError(f"{c}: brace_Mx_Nmm is required.")

    return out


def journal_residuals(row: dict):
    req = [
        "applied_Fx_N", "applied_Fy_N", "applied_Fz_N",
        "left_Rx_N", "left_Ry_N", "left_Rz_N",
        "right_Rx_N", "right_Ry_N", "right_Rz_N",
        "brace_Rx_N", "brace_Ry_N", "brace_Rz_N",
    ]
    if any(row[k] is None for k in req):
        return None

    return {
        "Fx_residual_N":
            row["applied_Fx_N"] + row["left_Rx_N"] + row["right_Rx_N"] + row["brace_Rx_N"],
        "Fy_residual_N":
            row["applied_Fy_N"] + row["left_Ry_N"] + row["right_Ry_N"] + row["brace_Ry_N"],
        "Fz_residual_N":
            row["applied_Fz_N"] + row["left_Rz_N"] + row["right_Rz_N"] + row["brace_Rz_N"],
    }


def main():
    rows = read_raw()

    for case, r in rows.items():
        r["brace_Mx_kNm"] = r["brace_Mx_Nmm"] / 1e6
        r["brace_Mx_abs_kNm"] = abs(r["brace_Mx_kNm"])

    combined = rows["combined"]["brace_Mx_kNm"]
    force = rows["force_only"]["brace_Mx_kNm"]
    moment = rows["moment_only"]["brace_Mx_kNm"]
    pressure = rows["pressure_only"]["brace_Mx_kNm"]

    reconstructed = force + moment + pressure
    residual = combined - reconstructed

    denom = max(abs(combined), 1e-12)
    residual_rel = abs(residual) / denom
    pressure_rel = abs(pressure) / denom

    superposition_pass = residual_rel <= SUPERPOSITION_REL_TOL

    # Optional journal equilibrium audit for every case with sufficient raw data.
    eq_rows = {}
    for case, r in rows.items():
        eq_rows[case] = journal_residuals(r)

    # Decomposition CSV
    fieldnames = [
        "case", "model_name", "analysis_name", "result_name", "support_name",
        "pressure_MPa",
        "applied_Fx_N", "applied_Fy_N", "applied_Fz_N",
        "applied_Mx_Nmm", "applied_My_Nmm", "applied_Mz_Nmm",
        "brace_Rx_N", "brace_Ry_N", "brace_Rz_N",
        "brace_Mx_Nmm", "brace_My_Nmm", "brace_Mz_Nmm",
        "brace_Mx_kNm", "brace_Mx_abs_kNm",
        "left_Rx_N", "left_Ry_N", "left_Rz_N",
        "right_Rx_N", "right_Ry_N", "right_Rz_N",
        "source_note",
    ]
    with OUT_DECOMP.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for case in REQUIRED_CASES:
            w.writerow(rows[case])

    # Freeze record is the only B14A quantity B14B should consume.
    freeze_fields = [
        "governing_case",
        "brace_support_name",
        "combined_Mx_kNm",
        "combined_abs_Mx_kNm",
        "force_only_Mx_kNm",
        "moment_only_Mx_kNm",
        "pressure_only_Mx_kNm",
        "reconstructed_Mx_kNm",
        "superposition_residual_kNm",
        "superposition_residual_fraction",
        "pressure_fraction_of_combined",
        "superposition_pass",
        "raw_source_csv",
    ]
    freeze = {
        "governing_case": rows["combined"].get("load_case_id", "") or "LC4+_ULT",
        "brace_support_name": rows["combined"].get("support_name", "") or "SUP_BRACE_RX",
        "combined_Mx_kNm": combined,
        "combined_abs_Mx_kNm": abs(combined),
        "force_only_Mx_kNm": force,
        "moment_only_Mx_kNm": moment,
        "pressure_only_Mx_kNm": pressure,
        "reconstructed_Mx_kNm": reconstructed,
        "superposition_residual_kNm": residual,
        "superposition_residual_fraction": residual_rel,
        "pressure_fraction_of_combined": pressure_rel,
        "superposition_pass": superposition_pass,
        "raw_source_csv": RAW.name,
    }
    with OUT_FREEZE.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=freeze_fields)
        w.writeheader()
        w.writerow(freeze)

    lines: List[str] = []
    emit = lines.append
    emit("=" * 116)
    emit(" PHASE 2E3-B14A — ANSYS BRACE-REACTION DECOMPOSITION / PYTHON DOCUMENTATION V0.1")
    emit("=" * 116)
    emit("")
    emit("RAW SOURCE")
    emit("-" * 116)
    emit(f"Input CSV: {RAW}")
    emit("The numeric reactions in this file are raw ANSYS results, not chat-derived values.")
    emit("")
    emit("BRACE Mx DECOMPOSITION")
    emit("-" * 116)
    for case in REQUIRED_CASES:
        emit(f"{case:14s}: {rows[case]['brace_Mx_kNm']: .9f} kN*m")
    emit("")
    emit(f"Reconstructed F + M + P: {reconstructed: .9f} kN*m")
    emit(f"Combined reaction:       {combined: .9f} kN*m")
    emit(f"Residual:                {residual: .9e} kN*m")
    emit(f"Residual fraction:       {residual_rel: .6%}")
    emit(f"Superposition check:     {'PASS' if superposition_pass else 'REVIEW'}")
    emit("")
    emit(f"Pressure fraction of |combined Mx|: {pressure_rel:.6%}")
    if pressure_rel > PRESSURE_REL_WARN:
        emit("Pressure contribution warning: exceeds 1% of combined brace Mx.")
    else:
        emit("Pressure contribution: small relative to combined brace Mx.")
    emit("")
    emit("OPTIONAL FORCE-EQUILIBRIUM CHECKS")
    emit("-" * 116)
    any_eq = False
    for case in REQUIRED_CASES:
        eq = eq_rows[case]
        if eq is None:
            emit(f"{case:14s}: not evaluated (journal/applied-force fields incomplete)")
            continue
        any_eq = True
        mag = math.sqrt(
            eq["Fx_residual_N"]**2 +
            eq["Fy_residual_N"]**2 +
            eq["Fz_residual_N"]**2
        )
        emit(
            f"{case:14s}: "
            f"Fx={eq['Fx_residual_N']:+.6f} N, "
            f"Fy={eq['Fy_residual_N']:+.6f} N, "
            f"Fz={eq['Fz_residual_N']:+.6f} N, "
            f"|R|={mag:.6f} N"
        )
    if not any_eq:
        emit("Populate applied/journal/brace force fields in the raw CSV to enable this check.")
    emit("")
    emit("B14B HANDOFF")
    emit("-" * 116)
    emit(f"B14B source file must read: {OUT_FREEZE.name}")
    emit("Do not paste the B14A brace Mx into B14B source code.")
    emit("")
    emit("OUTPUTS")
    emit("-" * 116)
    emit(f"Decomposition CSV: {OUT_DECOMP}")
    emit(f"Freeze record CSV: {OUT_FREEZE}")
    emit(f"Summary TXT:       {OUT_SUMMARY}")
    emit("=" * 116)

    report = "\n".join(lines)
    OUT_SUMMARY.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
