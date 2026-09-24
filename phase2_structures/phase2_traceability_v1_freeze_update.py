from pathlib import Path
import pandas as pd


# =============================================================================
# LANDING GEAR DESIGN PROJECT
# PHASE 0–2E2 — TRACEABILITY REGISTER V1 FREEZE UPDATE
#
# PURPOSE
#   Close the two targeted pre-E3 audit items after source review:
#
#       1. 460 mm piston-guide-surface semantics
#       2. historical-vs-current axle regression discrepancy
#
#   This script updates the existing traceability register. It does not alter
#   any structural geometry, loads, stresses, or Phase 2E2 release data.
#
# RESOLUTION BASIS
#
#   460 mm:
#       Source code explicitly defines required piston guide-surface length as
#
#           L_required = h_U(full extension) + L_b/2 + overrun
#
#       and uses the same length to compute piston-top intrusion above U.
#       Therefore 460 mm is confirmed as the required cylindrical piston
#       guide-surface length measured upward from the axle/shoulder datum.
#
#   Axle regression:
#       The historical 610.3 / 915.4 MPa result is NOT a valid regression
#       target for the current Phase 2 baseline because:
#
#       - the authoritative Phase 1 load envelope has been revised/restructured,
#       - the current axle source contains no explicit Kt / SCF multiplier,
#       - the current 50 x 8 mm working-row result is exactly
#             320.772903 MPa limit
#             481.159355 MPa ultimate
#         governing at LC2A,
#       - reconstructing the historical LC4 load set gives
#             510.974 MPa at Kt=1.0
#             611.272 MPa at Kt=1.2,
#         with an effective Kt = 1.198061 needed to reproduce 610.3 MPa.
#
#       Thus the old result came from a different load/methodology version and
#       is retained only as historical provenance. The current source-driven
#       nominal axle screen is authoritative for the present design.
#
# IMPORTANT LIMIT
#   This closes the REGRESSION-DISCREPANCY bookkeeping item only.
#   It does NOT mean the final axle spindle detail is fully validated.
#   Bearing seats, root fillet, brake flange, threads/nut, fatigue, fretting,
#   contact stress and manufacturing remain later-detail items.
# =============================================================================


HERE = Path(__file__).resolve().parent

REGISTER_IN = HERE / "phase2_traceability_register.csv"
OPEN_IN = HERE / "phase2_open_validation_items.csv"

AXLE_RESOLUTION_CSV = HERE / "phase2_axle_regression_resolution.csv"
AXLE_RESOLUTION_TXT = HERE / "phase2_axle_regression_resolution.txt"
PISTON_AUDIT_TXT = HERE / "phase2_460mm_semantics_audit.txt"

REGISTER_OUT = HERE / "phase2_traceability_register_v1.csv"
OPEN_OUT = HERE / "phase2_open_validation_items_v1.csv"
CLOSURE_OUT = HERE / "phase2_preE3_audit_closure.csv"
SUMMARY_OUT = HERE / "phase2_traceability_v1_summary.txt"


def read_required(path):
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


def require_item(df, item_id):
    rows = df.loc[
        df["item_id"].astype(str)
        == item_id
    ]

    if len(rows) != 1:
        raise ValueError(
            f"Expected exactly one row for {item_id}; "
            f"found {len(rows)}."
        )

    return rows.index[0]


def update_row(df, item_id, updates):
    idx = require_item(
        df,
        item_id,
    )

    for key, value in updates.items():
        if key not in df.columns:
            raise KeyError(
                f"Traceability column not found: {key}"
            )

        df.loc[
            idx,
            key,
        ] = value


def main():

    print("=" * 124)
    print(
        " PHASE 0–2E2 — TRACEABILITY REGISTER V1 FREEZE UPDATE"
    )
    print("=" * 124)

    register = read_required(
        REGISTER_IN
    )

    # Required audit evidence must exist before we close anything.
    for source in [
        AXLE_RESOLUTION_CSV,
        AXLE_RESOLUTION_TXT,
        PISTON_AUDIT_TXT,
    ]:
        if not source.exists():
            raise FileNotFoundError(
                f"Audit evidence missing:\n{source}"
            )

    # -------------------------------------------------------------------------
    # 1. Close the 460 mm semantics item.
    # -------------------------------------------------------------------------

    update_row(
        register,
        "P2D-460",
        {
            "classification":
                "DERIVED",
            "status":
                "CLOSED_SOURCE_CONFIRMED",
            "source_or_derivation":
                str(
                    PISTON_AUDIT_TXT.resolve()
                ),
            "engineering_basis":
                (
                    "Source code defines required piston guide-surface length "
                    "as h_U(full extension) + L_b/2 + overrun and uses that "
                    "same length for piston-top intrusion calculations."
                ),
            "limitation_or_validation":
                (
                    "460 mm is the required cylindrical piston guide-surface "
                    "length measured upward from the axle/shoulder datum. It "
                    "is not automatically the total forged piston/knuckle "
                    "component length."
                ),
            "sensitivity_or_consequence":
                (
                    "CLOSED — E2 axial cavity/packaging interpretation is "
                    "source-supported."
                ),
        },
    )

    # -------------------------------------------------------------------------
    # 2. Close the axle regression bookkeeping discrepancy.
    # -------------------------------------------------------------------------

    update_row(
        register,
        "P2-007",
        {
            "classification":
                "DERIVED",
            "status":
                "CLOSED_VERSION_MISMATCH_RESOLVED",
            "source_or_derivation":
                (
                    f"{AXLE_RESOLUTION_TXT.resolve()} ; "
                    f"{AXLE_RESOLUTION_CSV.resolve()}"
                ),
            "engineering_basis":
                (
                    "The historical 610.3/915.4 MPa result belongs to an older "
                    "load/methodology version. The current authoritative Phase 1 "
                    "envelope is revised/restructured, and the current axle source "
                    "uses nominal root axial+bending+torsion stress with no explicit "
                    "Kt/SCF. The current 50x8 mm row is 320.772903 MPa limit and "
                    "481.159355 MPa ultimate, governing at LC2A."
                ),
            "limitation_or_validation":
                (
                    "Historical LC4 reconstruction requires effective bending "
                    "Kt=1.198061 to reproduce 610.3 MPa. This strongly explains "
                    "the old result but does not prove the exact historical code "
                    "implementation. The old result is retained only as provenance, "
                    "not as a current regression target."
                ),
            "sensitivity_or_consequence":
                (
                    "CLOSED as a source-version discrepancy. Final axle local "
                    "geometry still requires bearing-seat/root-fillet/brake-flange/"
                    "thread/fatigue/fretting/contact/manufacturing validation."
                ),
        },
    )

    # -------------------------------------------------------------------------
    # 3. Regenerate open / validation list.
    #
    # Keep MODEL_ASSUMPTION entries with OPEN_VALIDATION visible.
    # Keep NEEDS_VALIDATION entries visible.
    # Do not keep the two newly closed audit items.
    # -------------------------------------------------------------------------

    open_mask = (
        register[
            "classification"
        ]
        .astype(str)
        .eq(
            "NEEDS_VALIDATION"
        )
        |
        register[
            "status"
        ]
        .astype(str)
        .str.contains(
            "OPEN_VALIDATION",
            case=False,
            regex=False,
            na=False,
        )
    )

    open_items = register.loc[
        open_mask
    ].copy()

    # Closed items must not survive this filter.
    for closed_id in [
        "P2D-460",
        "P2-007",
    ]:
        if closed_id in set(
            open_items[
                "item_id"
            ].astype(str)
        ):
            raise AssertionError(
                f"{closed_id} incorrectly remains in open register."
            )

    # -------------------------------------------------------------------------
    # 4. Freeze outputs.
    # -------------------------------------------------------------------------

    register.to_csv(
        REGISTER_OUT,
        index=False,
    )

    open_items.to_csv(
        OPEN_OUT,
        index=False,
    )

    closure = pd.DataFrame([
        {
            "item_id":
                "P2D-460",
            "issue":
                "460 mm piston / guide-surface semantics",
            "resolution":
                (
                    "CLOSED — confirmed source-derived required cylindrical "
                    "piston guide-surface length from axle/shoulder datum."
                ),
            "current_design_effect":
                (
                    "No E2 geometry change required."
                ),
        },
        {
            "item_id":
                "P2-007",
            "issue":
                "Historic vs current axle regression",
            "resolution":
                (
                    "CLOSED — historical result belongs to older load/methodology "
                    "version; current source-driven nominal axle screen is authoritative."
                ),
            "current_design_effect":
                (
                    "No current axle geometry change required by the regression audit. "
                    "Final local-detail validation remains open."
                ),
        },
    ])

    closure.to_csv(
        CLOSURE_OUT,
        index=False,
    )

    class_counts = (
        register[
            "classification"
        ]
        .value_counts()
        .sort_index()
    )

    status_counts = (
        register[
            "status"
        ]
        .value_counts()
        .sort_index()
    )

    summary = []

    summary.append(
        "=" * 124
    )
    summary.append(
        " PHASE 0–2E2 — TRACEABILITY REGISTER V1 SUMMARY"
    )
    summary.append(
        "=" * 124
    )
    summary.append("")
    summary.append(
        f"Total traceability items:       {len(register)}"
    )
    summary.append(
        f"Open / validation items:        {len(open_items)}"
    )
    summary.append("")
    summary.append(
        "Closed pre-E3 targeted audits:"
    )
    summary.append(
        "  P2D-460  CLOSED_SOURCE_CONFIRMED"
    )
    summary.append(
        "  P2-007   CLOSED_VERSION_MISMATCH_RESOLVED"
    )
    summary.append("")
    summary.append(
        "Classification counts:"
    )

    for key, value in class_counts.items():
        summary.append(
            f"  {key:<28} {value}"
        )

    summary.append("")
    summary.append(
        "Remaining open items are intentionally retained for later phases "
        "(hydraulic fidelity, local FEA, fatigue, tolerances, corrosion, "
        "certification mapping, metering-pin detail, closure detail, etc.)."
    )
    summary.append("")
    summary.append(
        "PRE-E3 DISPOSITION: PASS"
    )
    summary.append(
        "The two source-traceability issues identified before Phase 2E3 are closed."
    )
    summary.append(
        "This does not convert the project into a certification-level or fully "
        "detailed production design."
    )
    summary.append(
        "=" * 124
    )

    SUMMARY_OUT.write_text(
        "\n".join(
            summary
        ),
        encoding="utf-8",
    )

    # -------------------------------------------------------------------------
    # Console report.
    # -------------------------------------------------------------------------

    print("\nTARGETED AUDIT CLOSURE")
    print("-" * 124)
    print(
        closure.to_string(
            index=False,
        )
    )

    print("\nTRACEABILITY STATUS")
    print("-" * 124)
    print(
        f"Total items:                    {len(register)}"
    )
    print(
        f"Remaining open/validation:      {len(open_items)}"
    )

    print("\nCLASSIFICATION COUNTS")
    print("-" * 124)

    for key, value in class_counts.items():
        print(
            f"{key:<28} {value}"
        )

    print("\nREMAINING OPEN / VALIDATION ITEMS")
    print("-" * 124)

    if open_items.empty:
        print(
            "None."
        )
    else:
        display_cols = [
            "item_id",
            "phase",
            "parameter",
            "classification",
            "status",
        ]

        print(
            open_items[
                display_cols
            ].to_string(
                index=False,
            )
        )

    print("\nPRE-E3 DISPOSITION")
    print("-" * 124)
    print(
        "PASS — 460 mm packaging semantics and the historic/current axle "
        "regression discrepancy are closed at the source-traceability level."
    )
    print(
        "The remaining open items are legitimate later-phase validation/detail "
        "tasks and do not need to be falsely closed before beginning Phase 2E3."
    )

    print("\nOUTPUT FILES")
    print("-" * 124)
    print(
        f"V1 traceability register:       {REGISTER_OUT}"
    )
    print(
        f"V1 open-items register:         {OPEN_OUT}"
    )
    print(
        f"Pre-E3 closure record:          {CLOSURE_OUT}"
    )
    print(
        f"V1 summary:                     {SUMMARY_OUT}"
    )
    print("=" * 124)


if __name__ == "__main__":
    main()
