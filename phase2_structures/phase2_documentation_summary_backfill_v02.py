"""
Landing_Gear_Design_Project
PHASE 2 / 2E3 — DOCUMENTATION SUMMARY BACKFILL V0.2

Purpose
-------
Close the remaining CALCULATION-script summary gaps reported by
phase2e3_documentation_audit_v02.py.

This script reruns only the calculation scripts currently reported as NEEDS_SUMMARY
and captures each script's own stdout/stderr into:
    <script_stem>_summary.txt

It does NOT change formulas or copy engineering results from chat.

Run from phase2_structures:
    python phase2_documentation_summary_backfill_v02.py

Outputs:
    phase2_documentation_summary_backfill_v02.csv
    phase2_documentation_summary_backfill_v02.txt
"""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TIMEOUT_S = 300

TARGETS = [
    Path("current_design") / "phase2e3b13b_bushing_interface_sizing.py",
    Path("current_design") / "phase2e3b13b_v02r1_interference_fit_min_ligament_correction.py",
    Path("current_design") / "phase2e3b13b_v03_axial_thrust_flange_sizing.py",
    Path("phase2e3a2_upper_attachment_fbd_transport_v01.py"),
    Path("phase2e3b3_trunnion_shortlist_head_integration_v01.py"),
    Path("phase2e3b4_cross_trunnion_head_interface_v01.py"),
    Path("phase2e3b5_local_head_interface_screen_v01.py"),
    Path("phase2e3b5b_upper_barrel_reinforcement_profile_v01.py"),
    Path("phase2e3b6_head_span_recoupling_v01.py"),
    Path("phase2e3b8_transition_fea_load_package_v01.py"),
]


def run_and_capture(relpath: Path):
    script = HERE / relpath
    summary = script.with_name(script.stem + "_summary.txt")

    if not script.exists():
        return {
            "script": str(relpath),
            "returncode": "",
            "summary": str(summary.relative_to(HERE)),
            "status": "SOURCE_MISSING",
            "note": "Python source not found."
        }

    cp = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(script.parent),
        text=True,
        capture_output=True,
        timeout=TIMEOUT_S,
    )

    lines = [
        "=" * 118,
        f" DOCUMENTATION BACKFILL — {relpath}",
        "=" * 118,
        "",
        f"Python executable: {sys.executable}",
        f"Working directory: {script.parent}",
        f"Return code: {cp.returncode}",
        "",
        "STDOUT",
        "-" * 118,
        cp.stdout.rstrip(),
        "",
        "STDERR",
        "-" * 118,
        cp.stderr.rstrip(),
        "",
        "=" * 118,
    ]

    summary.write_text("\n".join(lines), encoding="utf-8")

    return {
        "script": str(relpath),
        "returncode": cp.returncode,
        "summary": str(summary.relative_to(HERE)),
        "status": "PASS" if cp.returncode == 0 else "RUN_FAILED",
        "note": "Existing calculation rerun; its own console report was captured to TXT."
    }


def main():
    rows = []
    print("Backfilling the remaining calculation summaries...")

    for relpath in TARGETS:
        print(f"  {relpath}")
        try:
            rows.append(run_and_capture(relpath))
        except subprocess.TimeoutExpired:
            rows.append({
                "script": str(relpath),
                "returncode": "",
                "summary": "",
                "status": "TIMEOUT",
                "note": f"Exceeded {TIMEOUT_S} s."
            })

    csv_path = HERE / "phase2_documentation_summary_backfill_v02.csv"
    txt_path = HERE / "phase2_documentation_summary_backfill_v02.txt"

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["script", "returncode", "summary", "status", "note"]
        )
        w.writeheader()
        w.writerows(rows)

    lines = [
        "=" * 118,
        " LANDING GEAR PROJECT — DOCUMENTATION SUMMARY BACKFILL V0.2",
        "=" * 118,
        "",
    ]
    for row in rows:
        lines.append(f"{row['status']:18s} {row['script']}")
        lines.append(f"    {row['note']}")

    lines += [
        "",
        "After this script finishes, rerun:",
        "    python phase2e3_documentation_audit_v02.py",
        "",
        "Builder-only audit items are intentionally not rerun here because they are not",
        "engineering calculation steps and may invoke CAD/FEA model-generation workflows.",
        "=" * 118,
    ]

    report = "\n".join(lines)
    txt_path.write_text(report, encoding="utf-8")
    print("\n" + report)
    print(f"\nCSV: {csv_path}")
    print(f"TXT: {txt_path}")


if __name__ == "__main__":
    main()
