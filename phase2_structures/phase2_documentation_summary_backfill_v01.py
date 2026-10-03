"""
Landing_Gear_Design_Project
PHASE 2 / 2E — DOCUMENTATION SUMMARY BACKFILL V0.1

Purpose
-------
Backfill human-readable TXT summaries for older calculation scripts that already
produce structured CSV results but historically printed their engineering report only
to the console.

This script DOES NOT rewrite formulas or invent results. It reruns each existing
calculation script and captures that script's own stdout/stderr into:
    <script_stem>_summary.txt

It also reruns Phase 2E3-B7A once and checks whether its declared working-profile
artifact is actually regenerated.

Run from phase2_structures:
    python phase2_documentation_summary_backfill_v01.py

Outputs:
    phase2_documentation_summary_backfill_v01.csv
    phase2_documentation_summary_backfill_v01.txt
"""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent

SUMMARY_TARGETS = [
    "phase2_barrel_sizing.py",
    "phase2_bushing_material_gland.py",
    "phase2_gland_retainer_sizing.py",
    "phase2_internal_loads.py",
    "phase2_lower_barrel_boss_sizing.py",
    "phase2_packaging_overlap.py",
    "phase2_piston_sizing.py",
    "phase2_upper_brace_sizing.py",
    "phase2_upper_trunnion_sizing.py",
    "phase2e1_lower_end_architecture_v04.py",
    "phase2e2_metering_upper_head_layout_v04.py",
    "phase2e2_oleo_cavity_packaging_v03.py",
    "phase2e2b_upper_head_closure_audit_v03.py",
    "phase2e2c_fluid_continuity_closure_finalize_v01.py",
]

B7A_SCRIPT = "phase2e3b7a_expanded_transition_robustness_trade_v01.py"
B7A_REQUIRED = "phase2e3b7a_working_profile.csv"

TIMEOUT_S = 180


def run_and_capture(script_name: str):
    script = HERE / script_name
    summary = HERE / f"{script.stem}_summary.txt"

    if not script.exists():
        return {
            "script": script_name,
            "returncode": "",
            "summary": str(summary.name),
            "status": "SOURCE_MISSING",
            "note": "Python source not found."
        }

    cp = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(HERE),
        text=True,
        capture_output=True,
        timeout=TIMEOUT_S,
    )

    text = []
    text.append("=" * 112)
    text.append(f" DOCUMENTATION BACKFILL — {script_name}")
    text.append("=" * 112)
    text.append("")
    text.append(f"Python executable: {sys.executable}")
    text.append(f"Return code: {cp.returncode}")
    text.append("")
    text.append("STDOUT")
    text.append("-" * 112)
    text.append(cp.stdout.rstrip())
    text.append("")
    text.append("STDERR")
    text.append("-" * 112)
    text.append(cp.stderr.rstrip())
    text.append("")
    text.append("=" * 112)

    summary.write_text("\n".join(text), encoding="utf-8")

    return {
        "script": script_name,
        "returncode": cp.returncode,
        "summary": str(summary.name),
        "status": "PASS" if cp.returncode == 0 else "RUN_FAILED",
        "note": "Existing script rerun; own console report captured to TXT."
    }


def main():
    rows = []

    print("Backfilling calculation summaries...")
    for name in SUMMARY_TARGETS:
        print(f"  {name}")
        try:
            rows.append(run_and_capture(name))
        except subprocess.TimeoutExpired:
            rows.append({
                "script": name,
                "returncode": "",
                "summary": "",
                "status": "TIMEOUT",
                "note": f"Exceeded {TIMEOUT_S} s."
            })

    # Targeted B7A repair check.
    b7a = HERE / B7A_SCRIPT
    if b7a.exists():
        print(f"\nTargeted B7A regeneration check: {B7A_SCRIPT}")
        try:
            row = run_and_capture(B7A_SCRIPT)
            required = HERE / B7A_REQUIRED
            if row["status"] == "PASS" and required.exists():
                row["status"] = "PASS_B7A_ARTIFACT_RESTORED"
                row["note"] = f"Rerun succeeded and {B7A_REQUIRED} exists."
            elif row["status"] == "PASS":
                row["status"] = "B7A_ARTIFACT_STILL_MISSING"
                row["note"] = (
                    f"Script ran successfully but {B7A_REQUIRED} was not produced. "
                    "Inspect B7A source logic before B7B traceability is considered fully closed."
                )
            rows.append(row)
        except subprocess.TimeoutExpired:
            rows.append({
                "script": B7A_SCRIPT,
                "returncode": "",
                "summary": "",
                "status": "TIMEOUT",
                "note": f"Exceeded {TIMEOUT_S} s."
            })

    csv_path = HERE / "phase2_documentation_summary_backfill_v01.csv"
    txt_path = HERE / "phase2_documentation_summary_backfill_v01.txt"

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["script", "returncode", "summary", "status", "note"]
        )
        w.writeheader()
        w.writerows(rows)

    lines = [
        "=" * 112,
        " LANDING GEAR PROJECT — DOCUMENTATION SUMMARY BACKFILL V0.1",
        "=" * 112,
        "",
    ]
    for row in rows:
        lines.append(f"{row['status']:32s} {row['script']}")
        lines.append(f"    {row['note']}")
    lines.extend([
        "",
        "Important:",
        "- This script only backfills documentation from each calculation script's own rerun.",
        "- It does not create B14A data and does not copy B14A values from chat.",
        "- Rerun phase2e3_documentation_audit_v02.py after this cleanup.",
        "=" * 112,
    ])

    report = "\n".join(lines)
    txt_path.write_text(report, encoding="utf-8")

    print("\n" + report)
    print(f"\nCSV: {csv_path}")
    print(f"TXT: {txt_path}")


if __name__ == "__main__":
    main()
