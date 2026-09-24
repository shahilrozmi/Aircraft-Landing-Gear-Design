from pathlib import Path
import csv
import hashlib
import math
import re

import numpy as np
import pandas as pd


# =============================================================================
# LANDING GEAR DESIGN PROJECT
# PHASE 2E3-A — UPPER ATTACHMENT LOAD-PATH / SOURCE AUDIT V0.1
#
# PURPOSE
#   Establish what the existing Phase 0–2E2 project actually supports for the
#   upper landing-gear attachment BEFORE selecting a trunnion pin diameter,
#   lug thickness, boss size, bearing, bushing, or attachment geometry.
#
#   This audit deliberately separates:
#
#       A. EXTERNAL airframe-attachment loads
#       B. INTERNAL barrel / guide-bushing reactions
#       C. previously-sized moment-reaction brace / link loads
#       D. E2 pressure-cavity / solid-head packaging boundary
#
#   Those quantities are NOT assumed to be interchangeable.
#
#   The script does not invent trunnion dimensions or a load path. If the
#   current sources are insufficient to define an external attachment FBD,
#   the disposition will remain OPEN and state exactly what is missing.
#
# OUTPUTS
#   phase2e3a_source_inventory.csv
#   phase2e3a_interface_evidence.csv
#   phase2e3a_open_items.csv
#   phase2e3a_source_snippets.txt
#   phase2e3a_load_path_audit.txt
# =============================================================================


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.resolve()

PHASE1_LOADS = (
    PROJECT_ROOT
    / "phase1_loads"
    / "phase1_load_envelope.csv"
)

E2_BASELINE = (
    HERE
    / "phase2e2_v1_baseline.csv"
)

TRACEABILITY_V1 = (
    HERE
    / "phase2_traceability_register_v1.csv"
)

KNOWN_CANDIDATE_FILES = [
    HERE / "phase2_internal_loads.csv",
    HERE / "phase2_upper_brace_sizing.py",
    HERE / "phase2_upper_brace_sizing.csv",
    HERE / "phase2_bushing_load_transfer.py",
    HERE / "phase2_bushing_load_transfer.csv",
    HERE / "phase2_packaging_overlap.py",
    HERE / "phase2_packaging_overlap.csv",
    HERE / "phase2e2_v1_baseline.csv",
    HERE / "phase2e2c_e3_interface.csv",
    HERE / "phase2e1_lower_end_architecture.py",
    HERE / "phase2e1_lower_end_geometry.csv",
    PHASE1_LOADS,
]

OUTPUT_INVENTORY = (
    HERE
    / "phase2e3a_source_inventory.csv"
)

OUTPUT_EVIDENCE = (
    HERE
    / "phase2e3a_interface_evidence.csv"
)

OUTPUT_OPEN = (
    HERE
    / "phase2e3a_open_items.csv"
)

OUTPUT_SNIPPETS = (
    HERE
    / "phase2e3a_source_snippets.txt"
)

OUTPUT_REPORT = (
    HERE
    / "phase2e3a_load_path_audit.txt"
)


# =============================================================================
# UTILITIES
# =============================================================================

def normalize(text):
    return "".join(
        ch
        for ch in str(text).lower()
        if ch.isalnum()
    )


def sha256(path):
    h = hashlib.sha256()

    with path.open("rb") as f:
        while True:
            chunk = f.read(
                1024 * 1024
            )

            if not chunk:
                break

            h.update(
                chunk
            )

    return h.hexdigest()


def read_csv_flexible(path):
    if not path.exists():
        return None

    try:
        df = pd.read_csv(
            path,
            encoding="utf-8-sig",
        )
    except Exception:
        df = pd.read_csv(
            path,
            sep=None,
            engine="python",
            encoding="utf-8-sig",
        )

    df.columns = [
        str(col)
        .replace(
            "\ufeff",
            "",
        )
        .strip()
        for col in df.columns
    ]

    return df


def find_column(df, aliases):
    if df is None:
        return None

    cols = {
        normalize(col): col
        for col in df.columns
    }

    for alias in aliases:
        key = normalize(
            alias
        )

        if key in cols:
            return cols[key]

    return None


def parameter_lookup(df, aliases):
    if df is None:
        return None, None

    pcol = find_column(
        df,
        ["parameter"],
    )

    vcol = find_column(
        df,
        ["value"],
    )

    if (
        pcol is None
        or vcol is None
    ):
        return None, None

    pnorm = (
        df[pcol]
        .astype(str)
        .map(normalize)
    )

    for alias in aliases:
        mask = (
            pnorm
            == normalize(alias)
        )

        rows = df.loc[
            mask
        ]

        if not rows.empty:
            return (
                rows.iloc[0][
                    vcol
                ],
                alias,
            )

    return None, None


def text_lines(path):
    if not path.exists():
        return []

    return path.read_text(
        encoding="utf-8",
        errors="ignore",
    ).splitlines()


def source_context(
    path,
    keywords,
    radius=5,
    max_blocks=30,
):
    lines = text_lines(
        path
    )

    if not lines:
        return []

    hit_indices = []

    for i, line in enumerate(
        lines
    ):
        low = line.lower()

        if any(
            kw.lower() in low
            for kw in keywords
        ):
            hit_indices.append(
                i
            )

    ranges = []

    for i in hit_indices:
        start = max(
            0,
            i - radius,
        )

        stop = min(
            len(lines) - 1,
            i + radius,
        )

        if (
            ranges
            and start
            <= ranges[-1][1] + 1
        ):
            ranges[-1] = (
                ranges[-1][0],
                max(
                    ranges[-1][1],
                    stop,
                ),
            )
        else:
            ranges.append(
                (
                    start,
                    stop,
                )
            )

    blocks = []

    for start, stop in ranges[
        :max_blocks
    ]:
        block = []

        for j in range(
            start,
            stop + 1,
        ):
            block.append(
                f"{j+1:5d}: "
                f"{lines[j]}"
            )

        blocks.append(
            "\n".join(
                block
            )
        )

    return blocks


def search_text(
    path,
    keywords,
):
    """
    Return keyword hit counts for text files.
    """

    if not path.exists():
        return {}

    text = path.read_text(
        encoding="utf-8",
        errors="ignore",
    ).lower()

    return {
        kw: text.count(
            kw.lower()
        )
        for kw in keywords
    }


def numeric(value):
    try:
        return float(
            value
        )
    except Exception:
        return np.nan


# =============================================================================
# 1. SOURCE DISCOVERY
# =============================================================================

def discover_sources():
    """
    Discover likely Phase 2E3-A source files without assuming exact filenames.
    """

    patterns = [
        "*upper*",
        "*brace*",
        "*bushing*",
        "*internal*load*",
        "*packaging*",
        "*e3*interface*",
        "*traceability*",
        "*e2*v1*baseline*",
    ]

    found = set()

    for path in KNOWN_CANDIDATE_FILES:
        if path.exists():
            found.add(
                path.resolve()
            )

    for pattern in patterns:
        for path in HERE.glob(
            pattern
        ):
            if (
                path.is_file()
                and path.suffix.lower()
                in {
                    ".py",
                    ".csv",
                    ".txt",
                }
            ):
                found.add(
                    path.resolve()
                )

    if PHASE1_LOADS.exists():
        found.add(
            PHASE1_LOADS.resolve()
        )

    return sorted(
        found,
        key=lambda p: p.name.lower(),
    )


# =============================================================================
# 2. E2 SOLID-HEAD / PRESSURE-BOUNDARY EVIDENCE
# =============================================================================

def e2_interface_evidence():
    rows = []

    df = read_csv_flexible(
        E2_BASELINE
    )

    if df is None:
        rows.append({
            "evidence_id":
                "E2-BOUNDARY-001",
            "evidence_type":
                "MISSING_SOURCE",
            "quantity":
                "E2 V1 baseline",
            "value":
                "",
            "units":
                "",
            "meaning":
                "phase2e2_v1_baseline.csv not found.",
            "engineering_use":
                "Cannot establish pressure-cavity / solid-head interface.",
        })

        return rows

    lookups = [
        (
            "E2-BOUNDARY-001",
            [
                "pressure_closure_inner_face_above_U",
            ],
            "Pressure closure inner face",
            "mm above U",
            (
                "Continuity-derived inner face of the preliminary "
                "upper pressure closure."
            ),
        ),
        (
            "E2-BOUNDARY-002",
            [
                "pressure_closure_preliminary_thickness",
            ],
            "Preliminary pressure closure thickness",
            "mm",
            (
                "Global plate screen only; not detailed head geometry."
            ),
        ),
        (
            "E2-BOUNDARY-003",
            [
                "preliminary_E3_interface_outer_face_above_U",
            ],
            "Preliminary E3 solid-head interface",
            "mm above U",
            (
                "Minimum preliminary solid-head boundary outside "
                "the live pressure cavity."
            ),
        ),
    ]

    for (
        evidence_id,
        aliases,
        quantity,
        units,
        meaning,
    ) in lookups:
        value, matched = parameter_lookup(
            df,
            aliases,
        )

        rows.append({
            "evidence_id":
                evidence_id,
            "evidence_type":
                "E2_PRESSURE_BOUNDARY",
            "quantity":
                quantity,
            "value":
                value,
            "units":
                units,
            "meaning":
                meaning,
            "engineering_use":
                (
                    "Packaging boundary only. This does NOT by itself "
                    "define trunnion loads, pin diameter, lug spacing, "
                    "or airframe reaction distribution."
                ),
        })

    return rows


# =============================================================================
# 3. CSV EVIDENCE AUDIT
# =============================================================================

def summarize_relevant_csv(path):
    """
    Return structured evidence for relevant CSVs without pretending that
    similarly-named quantities are the same physical interface.
    """

    df = read_csv_flexible(
        path
    )

    if df is None:
        return []

    rows = []

    lname = path.name.lower()

    # -------------------------------------------------------------------------
    # Internal-load table
    # -------------------------------------------------------------------------

    if (
        "internal"
        in lname
        and "load"
        in lname
    ):
        rows.append({
            "evidence_id":
                f"CSV::{path.name}",
            "evidence_type":
                "INTERNAL_LOAD_SOURCE",
            "quantity":
                "table_schema",
            "value":
                " | ".join(
                    df.columns
                ),
            "units":
                "",
            "meaning":
                (
                    "Internal structural resultants / section loads "
                    "generated earlier in Phase 2."
                ),
            "engineering_use":
                (
                    "May feed attachment FBD only if the structural "
                    "cut/interface is explicitly identified in the source."
                ),
        })

        # Include a compact table dump as evidence.
        for idx, row in df.head(
            30
        ).iterrows():
            rows.append({
                "evidence_id":
                    f"CSV::{path.name}::row{idx}",
                "evidence_type":
                    "INTERNAL_LOAD_ROW",
                "quantity":
                    "row",
                "value":
                    " ; ".join(
                        f"{col}={row[col]}"
                        for col in df.columns
                    ),
                "units":
                    "",
                "meaning":
                    "Raw source row.",
                "engineering_use":
                    "Do not reinterpret without source-code FBD semantics.",
            })

    # -------------------------------------------------------------------------
    # Upper brace / link sizing
    # -------------------------------------------------------------------------

    if (
        "brace"
        in lname
        or "upper"
        in lname
    ):
        rows.append({
            "evidence_id":
                f"CSV::{path.name}",
            "evidence_type":
                "UPPER_BRACE_OR_LINK_SOURCE",
            "quantity":
                "table_schema",
            "value":
                " | ".join(
                    df.columns
                ),
            "units":
                "",
            "meaning":
                (
                    "Candidate prior source for upper moment-reaction "
                    "brace/link sizing."
                ),
            "engineering_use":
                (
                    "Could constrain the E3 load path if the source "
                    "explicitly says the member connects the strut/head "
                    "to the airframe."
                ),
        })

        for idx, row in df.head(
            30
        ).iterrows():
            rows.append({
                "evidence_id":
                    f"CSV::{path.name}::row{idx}",
                "evidence_type":
                    "UPPER_BRACE_OR_LINK_ROW",
                "quantity":
                    "row",
                "value":
                    " ; ".join(
                        f"{col}={row[col]}"
                        for col in df.columns
                    ),
                "units":
                    "",
                "meaning":
                    "Raw source row.",
                "engineering_use":
                    (
                        "Use only after confirming load-path semantics "
                        "from the producing script."
                    ),
            })

    # -------------------------------------------------------------------------
    # Guide-bushing reactions
    # -------------------------------------------------------------------------

    if (
        "bushing"
        in lname
    ):
        rows.append({
            "evidence_id":
                f"CSV::{path.name}",
            "evidence_type":
                "GUIDE_REACTION_SOURCE",
            "quantity":
                "table_schema",
            "value":
                " | ".join(
                    df.columns
                ),
            "units":
                "",
            "meaning":
                (
                    "Internal piston/barrel guide reaction data."
                ),
            "engineering_use":
                (
                    "Guide reactions are INTERNAL to the strut assembly "
                    "unless a source explicitly identifies a guide station "
                    "as an external airframe attachment."
                ),
        })

        for idx, row in df.head(
            30
        ).iterrows():
            rows.append({
                "evidence_id":
                    f"CSV::{path.name}::row{idx}",
                "evidence_type":
                    "GUIDE_REACTION_ROW",
                "quantity":
                    "row",
                "value":
                    " ; ".join(
                        f"{col}={row[col]}"
                        for col in df.columns
                    ),
                "units":
                    "",
                "meaning":
                    "Raw source row.",
                "engineering_use":
                    (
                        "Do not equate to external trunnion reaction "
                        "without an assembly FBD."
                    ),
            })

    # -------------------------------------------------------------------------
    # Packaging geometry
    # -------------------------------------------------------------------------

    if (
        "packaging"
        in lname
    ):
        rows.append({
            "evidence_id":
                f"CSV::{path.name}",
            "evidence_type":
                "PACKAGING_SOURCE",
            "quantity":
                "table_schema",
            "value":
                " | ".join(
                    df.columns
                ),
            "units":
                "",
            "meaning":
                "Existing Phase 2 axial guide / piston packaging study.",
            "engineering_use":
                (
                    "Provides geometry/datum relationships, not necessarily "
                    "external attachment reactions."
                ),
        })

    return rows


# =============================================================================
# 4. SOURCE-SEMANTICS AUDIT
# =============================================================================

SOURCE_KEYWORDS = [
    "upper brace",
    "moment-reaction",
    "moment reaction",
    "brace",
    "link",
    "airframe",
    "attachment",
    "trunnion",
    "pivot",
    "lug",
    "bearing",
    "reaction",
    "h_u",
    "hu_",
    "upper bushing",
    "guide",
    "datum u",
    "structural datum",
    "external",
    "internal",
]


def audit_text_sources(paths):
    evidence = []
    snippet_sections = []

    for path in paths:
        if path.suffix.lower() not in {
            ".py",
            ".txt",
        }:
            continue

        hits = search_text(
            path,
            SOURCE_KEYWORDS,
        )

        total_hits = sum(
            hits.values()
        )

        if total_hits == 0:
            continue

        evidence.append({
            "evidence_id":
                f"TEXT::{path.name}",
            "evidence_type":
                "SOURCE_SEMANTICS",
            "quantity":
                "keyword_hits",
            "value":
                " ; ".join(
                    f"{key}={value}"
                    for key, value
                    in hits.items()
                    if value > 0
                ),
            "units":
                "",
            "meaning":
                (
                    "Source-code/text terminology relevant to the "
                    "upper attachment load path."
                ),
            "engineering_use":
                (
                    "Review snippets before promoting any internal "
                    "reaction or previous brace load to E3 external "
                    "attachment design input."
                ),
        })

        blocks = source_context(
            path,
            SOURCE_KEYWORDS,
            radius=5,
            max_blocks=40,
        )

        if blocks:
            snippet_sections.append(
                "\n".join([
                    "=" * 120,
                    f"SOURCE: {path}",
                    "=" * 120,
                    *blocks,
                    "",
                ])
            )

    return evidence, snippet_sections


# =============================================================================
# 5. SOURCE INVENTORY
# =============================================================================

def source_inventory(paths):
    rows = []

    for path in paths:
        rows.append({
            "filename":
                path.name,
            "path":
                str(
                    path
                ),
            "suffix":
                path.suffix.lower(),
            "size_bytes":
                path.stat().st_size,
            "sha256":
                sha256(
                    path
                ),
        })

    return pd.DataFrame(
        rows
    )


# =============================================================================
# 6. LOGIC GATES
# =============================================================================

def has_file(paths, substrings):
    for path in paths:
        lname = path.name.lower()

        if all(
            token.lower()
            in lname
            for token in substrings
        ):
            return True

    return False


def file_for(paths, substrings):
    for path in paths:
        lname = path.name.lower()

        if all(
            token.lower()
            in lname
            for token in substrings
        ):
            return path

    return None


def text_has_any(path, tokens):
    if (
        path is None
        or not path.exists()
    ):
        return False

    text = path.read_text(
        encoding="utf-8",
        errors="ignore",
    ).lower()

    return any(
        token.lower()
        in text
        for token in tokens
    )


def text_has_all_groups(path, groups):
    if (
        path is None
        or not path.exists()
    ):
        return False

    text = path.read_text(
        encoding="utf-8",
        errors="ignore",
    ).lower()

    return all(
        any(
            token.lower()
            in text
            for token in group
        )
        for group in groups
    )


# =============================================================================
# 7. MAIN
# =============================================================================

def main():
    print("=" * 124)
    print(
        " PHASE 2E3-A — UPPER ATTACHMENT LOAD-PATH / SOURCE AUDIT V0.1"
    )
    print("=" * 124)

    paths = discover_sources()

    inventory = source_inventory(
        paths
    )

    inventory.to_csv(
        OUTPUT_INVENTORY,
        index=False,
    )

    print("\nSOURCE INVENTORY")
    print("-" * 124)
    print(
        inventory[
            [
                "filename",
                "suffix",
                "size_bytes",
            ]
        ].to_string(
            index=False,
        )
    )

    evidence_rows = []

    # E2 pressure-boundary evidence
    evidence_rows.extend(
        e2_interface_evidence()
    )

    # CSV evidence
    for path in paths:
        if path.suffix.lower() == ".csv":
            evidence_rows.extend(
                summarize_relevant_csv(
                    path
                )
            )

    # Source semantics and snippets
    text_evidence, snippet_sections = (
        audit_text_sources(
            paths
        )
    )

    evidence_rows.extend(
        text_evidence
    )

    evidence = pd.DataFrame(
        evidence_rows
    )

    if evidence.empty:
        evidence = pd.DataFrame(
            columns=[
                "evidence_id",
                "evidence_type",
                "quantity",
                "value",
                "units",
                "meaning",
                "engineering_use",
            ]
        )

    evidence.to_csv(
        OUTPUT_EVIDENCE,
        index=False,
    )

    OUTPUT_SNIPPETS.write_text(
        "\n".join(
            snippet_sections
        ),
        encoding="utf-8",
    )

    # -------------------------------------------------------------------------
    # Core evidence gates
    # -------------------------------------------------------------------------

    upper_brace_py = file_for(
        paths,
        [
            "upper",
            "brace",
        ],
    )

    internal_loads_csv = file_for(
        paths,
        [
            "internal",
            "load",
        ],
    )

    bushing_py = file_for(
        paths,
        [
            "bushing",
            "load",
        ],
    )

    packaging_py = file_for(
        paths,
        [
            "packaging",
        ],
    )

    e2_exists = E2_BASELINE.exists()

    has_upper_brace_source = (
        upper_brace_py is not None
    )

    has_internal_load_source = (
        internal_loads_csv is not None
    )

    # Strong semantic evidence that the old upper brace/link was actually
    # intended as an airframe-connected member.
    brace_airframe_semantics = (
        text_has_all_groups(
            upper_brace_py,
            [
                [
                    "brace",
                    "link",
                ],
                [
                    "airframe",
                    "attachment",
                    "ground",
                    "support",
                ],
            ],
        )
        if upper_brace_py
        else False
    )

    # Evidence that an explicit trunnion architecture was already defined.
    explicit_trunnion_semantics = (
        any(
            text_has_any(
                path,
                [
                    "trunnion",
                ],
            )
            for path in paths
            if path.suffix.lower()
            in {
                ".py",
                ".txt",
            }
        )
    )

    # E2 interface values
    e2_df = read_csv_flexible(
        E2_BASELINE
    )

    e3_interface = np.nan

    if e2_df is not None:
        value, _ = parameter_lookup(
            e2_df,
            [
                "preliminary_E3_interface_outer_face_above_U",
            ],
        )

        e3_interface = numeric(
            value
        )

    # -------------------------------------------------------------------------
    # Open-item logic
    # -------------------------------------------------------------------------

    open_rows = []

    def add_open(
        item_id,
        status,
        item,
        why_it_matters,
        close_condition,
    ):
        open_rows.append({
            "item_id":
                item_id,
            "status":
                status,
            "item":
                item,
            "why_it_matters":
                why_it_matters,
            "close_condition":
                close_condition,
        })

    if not e2_exists:
        add_open(
            "E3A-001",
            "BLOCKING",
            "E2 solid-head interface source missing",
            (
                "E3 attachment cannot be placed relative to the "
                "pressure cavity without the frozen E2 interface."
            ),
            "Restore/read phase2e2_v1_baseline.csv.",
        )

    if not has_internal_load_source:
        add_open(
            "E3A-002",
            "BLOCKING",
            "Phase 2 internal-load source not found",
            (
                "Need the existing structural resultants before "
                "building an external upper-attachment FBD."
            ),
            "Locate/restore phase2_internal_loads.csv or equivalent source.",
        )

    if not has_upper_brace_source:
        add_open(
            "E3A-003",
            "BLOCKING",
            "Previous upper brace/link source not found",
            (
                "Phase 2D10 reportedly sized an upper moment-reaction "
                "brace/link; E3 must know whether that member is part "
                "of the external airframe load path."
            ),
            "Locate/restore the Phase 2D10 upper brace/link sizing source.",
        )

    if (
        has_upper_brace_source
        and not brace_airframe_semantics
    ):
        add_open(
            "E3A-004",
            "REVIEW",
            "Upper brace/link external-interface semantics not automatically proven",
            (
                "A member called 'upper brace' is not automatically "
                "an airframe trunnion reaction."
            ),
            (
                "Review phase2e3a_source_snippets.txt and identify the "
                "brace/link endpoints and FBD explicitly."
            ),
        )

    if not explicit_trunnion_semantics:
        add_open(
            "E3A-005",
            "EXPECTED",
            "No source-defined trunnion geometry yet",
            (
                "Pin axis, lug count, bearing spacing, boss diameter "
                "and attachment orientation must not be invented."
            ),
            (
                "Define E3 architecture only after the external load "
                "path is established."
            ),
        )

    add_open(
        "E3A-006",
        "EXPECTED",
        "Do not equate guide-bushing reaction with airframe reaction",
        (
            "The upper/lower guide reactions are internal piston-barrel "
            "load transfer unless an assembly FBD proves otherwise."
        ),
        (
            "Use guide reactions only for barrel/guide/local-head design "
            "unless explicitly carried into an external attachment FBD."
        ),
    )

    add_open(
        "E3A-007",
        "EXPECTED",
        "E2 +498.780 mm interface is a packaging minimum, not a trunnion station",
        (
            "It only says the external attachment must be in solid head "
            "outside the pressure cavity."
        ),
        (
            "E3 architecture will choose the actual attachment station "
            "after the load path and local head geometry are defined."
        ),
    )

    open_df = pd.DataFrame(
        open_rows
    )

    open_df.to_csv(
        OUTPUT_OPEN,
        index=False,
    )

    # -------------------------------------------------------------------------
    # Disposition
    # -------------------------------------------------------------------------

    blocking_count = int(
        (
            open_df[
                "status"
            ]
            == "BLOCKING"
        ).sum()
    )

    review_count = int(
        (
            open_df[
                "status"
            ]
            == "REVIEW"
        ).sum()
    )

    print("\nE2 -> E3 INTERFACE")
    print("-" * 124)

    if np.isfinite(
        e3_interface
    ):
        print(
            f"Frozen preliminary E3 solid-head boundary: "
            f"{e3_interface:.6f} mm above U"
        )
        print(
            "Interpretation: minimum preliminary location outside the "
            "live pressure cavity; NOT a selected trunnion centerline."
        )
    else:
        print(
            "E3 interface value could not be resolved."
        )

    print("\nCORE SOURCE GATES")
    print("-" * 124)
    print(
        f"Internal-load source present:       "
        f"{has_internal_load_source}"
    )
    print(
        f"Upper brace/link source present:    "
        f"{has_upper_brace_source}"
    )
    print(
        f"Brace/link airframe semantics:      "
        f"{brace_airframe_semantics}"
    )
    print(
        f"Explicit trunnion source semantics: "
        f"{explicit_trunnion_semantics}"
    )

    print("\nOPEN / REVIEW ITEMS")
    print("-" * 124)
    print(
        open_df.to_string(
            index=False,
        )
    )

    print("\nE3-A DISPOSITION")
    print("-" * 124)

    if blocking_count > 0:
        disposition = (
            "BLOCKED — required prior-phase source(s) are missing. "
            "Do not size a trunnion yet."
        )
    elif review_count > 0:
        disposition = (
            "SOURCE REVIEW REQUIRED — all key files exist, but the external "
            "upper-attachment FBD is not yet proven. Review the generated "
            "source snippets before selecting hardware geometry."
        )
    else:
        disposition = (
            "SOURCE BASIS PRESENT — proceed to explicit upper-attachment FBD "
            "definition. Hardware sizing still waits until that FBD is frozen."
        )

    print(
        disposition
    )

    # -------------------------------------------------------------------------
    # Final report
    # -------------------------------------------------------------------------

    report = []

    report.append(
        "=" * 124
    )
    report.append(
        " PHASE 2E3-A — UPPER ATTACHMENT LOAD-PATH / SOURCE AUDIT V0.1"
    )
    report.append(
        "=" * 124
    )
    report.append("")
    report.append(
        f"E2 preliminary solid-head boundary: "
        f"{e3_interface if np.isfinite(e3_interface) else 'UNRESOLVED'} "
        f"mm above U"
    )
    report.append(
        "This is a pressure-cavity packaging boundary, not automatically "
        "the trunnion centerline."
    )
    report.append("")
    report.append(
        f"Internal-load source present:       {has_internal_load_source}"
    )
    report.append(
        f"Upper brace/link source present:    {has_upper_brace_source}"
    )
    report.append(
        f"Brace/link airframe semantics:      {brace_airframe_semantics}"
    )
    report.append(
        f"Explicit trunnion semantics:        {explicit_trunnion_semantics}"
    )
    report.append("")
    report.append(
        f"Blocking items: {blocking_count}"
    )
    report.append(
        f"Review items:   {review_count}"
    )
    report.append("")
    report.append(
        "DISPOSITION:"
    )
    report.append(
        disposition
    )
    report.append("")
    report.append(
        "ENGINEERING RULE:"
    )
    report.append(
        "Do not use internal guide-bushing reactions as trunnion/airframe "
        "reactions without an explicit assembly free-body diagram."
    )
    report.append(
        "Do not choose pin/lug/bearing dimensions from the E2 498.780 mm "
        "boundary; it is an axial packaging minimum only."
    )
    report.append(
        "=" * 124
    )

    OUTPUT_REPORT.write_text(
        "\n".join(
            report
        ),
        encoding="utf-8",
    )

    print("\nOUTPUT FILES")
    print("-" * 124)
    print(
        f"Source inventory:                {OUTPUT_INVENTORY}"
    )
    print(
        f"Interface evidence:              {OUTPUT_EVIDENCE}"
    )
    print(
        f"Open/review items:               {OUTPUT_OPEN}"
    )
    print(
        f"Source snippets:                 {OUTPUT_SNIPPETS}"
    )
    print(
        f"Load-path audit report:          {OUTPUT_REPORT}"
    )
    print("=" * 124)


if __name__ == "__main__":
    main()
