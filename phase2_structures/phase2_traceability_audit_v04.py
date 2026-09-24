from pathlib import Path
import ast
import csv
import hashlib
import math
import re

import numpy as np
import pandas as pd


# =============================================================================
# LANDING GEAR DESIGN PROJECT
# PHASE 0–2E2 — ASSUMPTION / DECISION / TRACEABILITY AUDIT V0.4
#
# PURPOSE
#   Create a live engineering traceability register before Phase 2E3.
#
#   The register distinguishes:
#       SOURCE
#       DERIVED
#       DESIGN_CHOICE
#       MODEL_ASSUMPTION
#       NEEDS_VALIDATION
#
#   This script also performs two targeted source audits that were intentionally
#   left open:
#
#       A. 460 mm piston / guide-length semantics
#       B. historical-vs-current axle regression discrepancy
#
# IMPORTANT
#   This is a documentation and source-traceability audit. It does not silently
#   "fix" any design value. Ambiguities are reported as OPEN rather than guessed.
#
# OUTPUTS
#   phase2_traceability_register.csv
#   phase2_open_validation_items.csv
#   phase2_460mm_semantics_audit.txt
#   phase2_axle_regression_audit.csv
#   phase2_axle_regression_audit.txt
#   phase2_traceability_source_manifest.csv
#   phase2_traceability_summary.txt
# =============================================================================


# =============================================================================
# 1. PATHS
# =============================================================================

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.resolve()

PHASE1_DIR = PROJECT_ROOT / "phase1_model_development"
PHASE1_LOADS_DIR = PROJECT_ROOT / "phase1_loads"
PHASE2_DIR = PROJECT_ROOT / "phase2_structures"

PATHS = {
    "phase1_model": PHASE1_DIR / "landing_dynamic_v04_2dof.py",
    "phase1_load_envelope": PHASE1_LOADS_DIR / "phase1_load_envelope.csv",
    "phase2_packaging_py": PHASE2_DIR / "phase2_packaging_overlap.py",
    "phase2_packaging_csv": PHASE2_DIR / "phase2_packaging_overlap.csv",
    "phase2_axle_py": PHASE2_DIR / "phase2_axle_sizing.py",
    "phase2_axle_csv": PHASE2_DIR / "phase2_axle_sizing.csv",
    "phase2_internal_loads": PHASE2_DIR / "phase2_internal_loads.csv",
    "phase2e1_geometry": PHASE2_DIR / "phase2e1_lower_end_geometry.csv",
    "phase2e2_baseline": PHASE2_DIR / "phase2e2_v1_baseline.csv",
    "phase2e2_release_checks": PHASE2_DIR / "phase2e2_v1_release_checks.csv",
    "phase2e2_continuity": PHASE2_DIR / "phase2e2c_fluid_continuity_states.csv",
    "phase2e2_metering_compare": PHASE2_DIR / "phase2e2_metering_law_comparison.csv",
    "phase2_barrel_sizing": PHASE2_DIR / "phase2_barrel_sizing.csv",
}

OUTPUT_REGISTER = PHASE2_DIR / "phase2_traceability_register.csv"
OUTPUT_OPEN = PHASE2_DIR / "phase2_open_validation_items.csv"
OUTPUT_460 = PHASE2_DIR / "phase2_460mm_semantics_audit.txt"
OUTPUT_AXLE_CSV = PHASE2_DIR / "phase2_axle_regression_audit.csv"
OUTPUT_AXLE_TXT = PHASE2_DIR / "phase2_axle_regression_audit.txt"
OUTPUT_MANIFEST = PHASE2_DIR / "phase2_traceability_source_manifest.csv"
OUTPUT_SUMMARY = PHASE2_DIR / "phase2_traceability_summary.txt"


# =============================================================================
# 2. PROJECT BASELINES USED ONLY FOR DOCUMENTATION / CROSS-CHECKS
# =============================================================================

# Historic pre-current-load-envelope hand summary, retained ONLY as an audit
# reference so the old/current axle discrepancy can be explained.
HISTORIC_LOADS_KN = {
    "LC0": {"Fx": 0.000, "Fy": 0.000, "Fz": 8.338},
    "LC1": {"Fx": 0.000, "Fy": 0.000, "Fz": 25.020},
    "LC2": {"Fx": 7.506, "Fy": 0.000, "Fz": 25.020},
    "LC3": {"Fx": 0.000, "Fy": 10.008, "Fz": 25.020},
    "LC4": {"Fx": 7.506, "Fy": 10.008, "Fz": 25.020},
    "LC5": {"Fx": -7.506, "Fy": 0.000, "Fz": 25.020},
}

# Geometry carried by the prior axle screening.
AXLE_OD_M = 0.050
AXLE_ID_M = 0.034
TIRE_RADIUS_M = 0.175
STRUT_OFFSET_M = 0.120

# These historical numbers are NOT authoritative design outputs. They are the
# old hand-summary regression targets we are trying to explain.
HISTORIC_AXLE_LIMIT_VM_MPA = 610.3
HISTORIC_AXLE_ULT_VM_MPA = 915.4

# Known current E1 regression values from the project history. The script will
# still search project files for a source-backed copy.
CURRENT_E1_LIMIT_VM_REFERENCE_MPA = 320.8
CURRENT_E1_ULT_VM_REFERENCE_MPA = 481.2


# =============================================================================
# 3. BASIC UTILITIES
# =============================================================================

def normalize(text):
    return "".join(
        ch for ch in str(text).lower()
        if ch.isalnum()
    )


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
        str(col).replace("\ufeff", "").strip()
        for col in df.columns
    ]

    return df


def sha256(path):
    h = hashlib.sha256()

    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)

            if not chunk:
                break

            h.update(chunk)

    return h.hexdigest()


def safe_float(value):
    try:
        return float(value)
    except Exception:
        return np.nan


def parameter_lookup(df, names):
    if df is None:
        return None, None

    cols = {
        normalize(col): col
        for col in df.columns
    }

    pcol = cols.get("parameter")
    vcol = cols.get("value")

    if pcol is None or vcol is None:
        return None, None

    pnorm = (
        df[pcol]
        .astype(str)
        .map(normalize)
    )

    for name in names:
        mask = pnorm == normalize(name)
        rows = df.loc[mask]

        if not rows.empty:
            return rows.iloc[0][vcol], name

    return None, None


def find_column(df, aliases):
    if df is None:
        return None

    norm = {
        normalize(col): col
        for col in df.columns
    }

    for alias in aliases:
        key = normalize(alias)

        if key in norm:
            return norm[key]

    return None


def extract_numeric_assignments(path):
    """
    Safely recover simple top-level numeric Python assignments.
    """

    if not path.exists():
        return {}

    source = path.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    try:
        tree = ast.parse(
            source,
            filename=str(path),
        )
    except Exception:
        return {}

    env = {}
    pending = []

    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = [
                target.id
                for target in node.targets
                if isinstance(target, ast.Name)
            ]

            if names:
                pending.append((names, node.value))

        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                pending.append(
                    ([node.target.id], node.value)
                )

    def eval_node(node):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return float(node.value)

        if isinstance(node, ast.Name):
            return env.get(node.id)

        if isinstance(node, ast.UnaryOp):
            val = eval_node(node.operand)

            if val is None:
                return None

            if isinstance(node.op, ast.USub):
                return -val

            if isinstance(node.op, ast.UAdd):
                return val

        if isinstance(node, ast.BinOp):
            a = eval_node(node.left)
            b = eval_node(node.right)

            if a is None or b is None:
                return None

            if isinstance(node.op, ast.Add):
                return a + b
            if isinstance(node.op, ast.Sub):
                return a - b
            if isinstance(node.op, ast.Mult):
                return a * b
            if isinstance(node.op, ast.Div):
                return a / b
            if isinstance(node.op, ast.Pow):
                return a**b

        return None

    for _ in range(
        max(
            len(pending) + 1,
            1,
        )
    ):
        changed = False

        for names, expr in pending:
            value = eval_node(expr)

            if value is None:
                continue

            for name in names:
                if (
                    name not in env
                    or env[name] != value
                ):
                    env[name] = value
                    changed = True

        if not changed:
            break

    return env


def source_context(path, tokens, radius=4):
    """
    Return numbered source snippets around any line containing one of tokens.
    """

    if not path.exists():
        return []

    lines = path.read_text(
        encoding="utf-8",
        errors="ignore",
    ).splitlines()

    hit_lines = []

    for i, line in enumerate(lines):
        lower = line.lower()

        if any(
            token.lower() in lower
            for token in tokens
        ):
            hit_lines.append(i)

    ranges = []

    for i in hit_lines:
        start = max(0, i - radius)
        stop = min(len(lines), i + radius + 1)

        if ranges and start <= ranges[-1][1] + 1:
            ranges[-1] = (
                ranges[-1][0],
                max(
                    ranges[-1][1],
                    stop - 1,
                ),
            )
        else:
            ranges.append(
                (start, stop - 1)
            )

    snippets = []

    for start, stop in ranges:
        block = []

        for idx in range(start, stop + 1):
            block.append(
                f"{idx + 1:5d}: {lines[idx]}"
            )

        snippets.append(
            "\n".join(block)
        )

    return snippets


def ast_assignment_source(path, target_name):
    """
    Return exact source segment for assignments whose target is target_name.
    """

    if not path.exists():
        return []

    source = path.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    try:
        tree = ast.parse(
            source,
            filename=str(path),
        )
    except Exception:
        return []

    segments = []

    for node in ast.walk(tree):
        targets = []

        if isinstance(node, ast.Assign):
            targets = [
                target.id
                for target in node.targets
                if isinstance(target, ast.Name)
            ]

        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                targets = [node.target.id]

        if target_name in targets:
            segment = ast.get_source_segment(
                source,
                node,
            )

            if segment:
                segments.append(segment)

    return segments


# =============================================================================
# 4. TRACEABILITY REGISTER BUILDER
# =============================================================================

register_rows = []


def add_register(
    item_id,
    phase,
    category,
    parameter,
    value,
    units,
    classification,
    status,
    source_or_derivation,
    engineering_basis,
    limitation_or_validation,
    sensitivity,
):
    register_rows.append({
        "item_id": item_id,
        "phase": phase,
        "category": category,
        "parameter": parameter,
        "value": value,
        "units": units,
        "classification": classification,
        "status": status,
        "source_or_derivation": source_or_derivation,
        "engineering_basis": engineering_basis,
        "limitation_or_validation": limitation_or_validation,
        "sensitivity_or_consequence": sensitivity,
    })


def build_register():
    e2 = read_csv_flexible(
        PATHS["phase2e2_baseline"]
    )

    phase1_env = extract_numeric_assignments(
        PATHS["phase1_model"]
    )

    e2_values = {}

    if e2 is not None:
        pcol = find_column(
            e2,
            ["parameter"],
        )

        vcol = find_column(
            e2,
            ["value"],
        )

        if pcol is not None and vcol is not None:
            for _, row in e2.iterrows():
                e2_values[
                    normalize(
                        row[pcol]
                    )
                ] = row[vcol]

    def e2v(name, fallback=""):
        return e2_values.get(
            normalize(name),
            fallback,
        )

    # -------------------------------------------------------------------------
    # Scope / aircraft baseline
    # -------------------------------------------------------------------------

    add_register(
        "P0-001",
        "Phase 0",
        "Aircraft baseline",
        "Aircraft class",
        "generic 4–6 seat single-engine low-wing tricycle aircraft",
        "-",
        "DESIGN_CHOICE",
        "FROZEN_SCOPE",
        "Phase 0 project definition",
        "Provides a coherent conceptual aircraft for landing-gear design work.",
        "Not tied to one certificated production aircraft.",
        "All loads and packaging are conditional on this project aircraft.",
    )

    add_register(
        "P0-002",
        "Phase 0",
        "Aircraft baseline",
        "Design mass",
        "1700",
        "kg",
        "DESIGN_CHOICE",
        "FROZEN_SCOPE",
        "Phase 0 project definition",
        "Used as the baseline gross aircraft mass for load development.",
        "Must not be presented as manufacturer data.",
        "Directly scales static and landing loads.",
    )

    add_register(
        "P0-003",
        "Phase 0",
        "Configuration",
        "Detailed design focus",
        "one oleo-pneumatic single-wheel main landing gear",
        "-",
        "DESIGN_CHOICE",
        "FROZEN_SCOPE",
        "Phase 0 scope",
        "Keeps the project deep enough for structural, dynamic, hydraulic and CAD analysis.",
        "Opposite main gear / nose gear are represented through global equilibrium, not fully detailed.",
        "Defines what is and is not physically designed.",
    )

    add_register(
        "P0-004",
        "Phase 0",
        "Certification",
        "Certification-level substantiation",
        "not yet claimed",
        "-",
        "NEEDS_VALIDATION",
        "OPEN_VALIDATION",
        "Project scope boundary",
        "Current work is a preliminary engineering design study.",
        "Applicable FAA/EASA landing-load requirements should be explicitly mapped before claiming certification compliance.",
        "High — affects formal load cases and margins.",
    )

    # -------------------------------------------------------------------------
    # Phase 1 dynamics / fluid model
    # -------------------------------------------------------------------------

    phase1_source = str(
        PATHS["phase1_model"]
    )

    phase1_items = [
        (
            "P1-001",
            "Oil density",
            phase1_env.get(
                "rho_oil",
                850.0,
            ),
            "kg/m^3",
            "MODEL_ASSUMPTION",
            "WORKING_MODEL",
            "Equivalent hydraulic-fluid property.",
            "Temperature dependence is not yet modeled.",
            "Affects damping force.",
        ),
        (
            "P1-002",
            "Orifice discharge coefficient",
            phase1_env.get(
                "C_d",
                0.70,
            ),
            "-",
            "MODEL_ASSUMPTION",
            "WORKING_MODEL",
            "Effective orifice-loss coefficient.",
            "Not calibrated against hardware flow-bench data.",
            "High effect on hydraulic force.",
        ),
        (
            "P1-003",
            "Gas polytropic exponent",
            phase1_env.get(
                "n_poly",
                1.30,
            ),
            "-",
            "MODEL_ASSUMPTION",
            "WORKING_MODEL",
            "Effective N2 compression process.",
            "Heat-transfer transient not resolved explicitly.",
            "Moderate effect on gas pressure / stroke.",
        ),
        (
            "P1-004",
            "Initial gas length",
            phase1_env.get(
                "L_gas_0",
                0.350,
            )
            * 1000.0,
            "mm",
            "DESIGN_CHOICE",
            "WORKING_MODEL",
            "Phase 1 effective pneumatic geometry.",
            "Effective model dimension, not manufacturer hardware data.",
            "Strong effect on gas-volume ratio.",
        ),
        (
            "P1-005",
            "Initial absolute gas pressure",
            phase1_env.get(
                "P_gas_0_abs",
                2.336e6,
            )
            / 1e6,
            "MPa abs",
            "DESIGN_CHOICE",
            "WORKING_MODEL",
            "Phase 1 precharge / initial gas state.",
            "Requires future servicing / real-hardware feasibility review.",
            "Strong effect on static sag and landing stroke.",
        ),
        (
            "P1-006",
            "Seal friction / stiction",
            "neglected",
            "-",
            "MODEL_ASSUMPTION",
            "OPEN_VALIDATION",
            "Simplified oleo dynamic model.",
            "Real seals add breakaway force and hysteresis.",
            "Moderate for low-speed response; possibly significant near reversals.",
        ),
        (
            "P1-007",
            "Oil compressibility",
            "neglected",
            "-",
            "MODEL_ASSUMPTION",
            "OPEN_VALIDATION",
            "Incompressible-fluid approximation.",
            "Bulk modulus / entrained gas not represented.",
            "Usually secondary for preliminary sizing; relevant to pressure transients.",
        ),
        (
            "P1-008",
            "Temperature-dependent viscosity",
            "neglected",
            "-",
            "MODEL_ASSUMPTION",
            "OPEN_VALIDATION",
            "Constant effective oil property.",
            "Cold / hot oil can significantly change damping.",
            "High for operational envelope robustness.",
        ),
        (
            "P1-009",
            "Cavitation / aeration / foaming",
            "not explicitly modeled",
            "-",
            "MODEL_ASSUMPTION",
            "OPEN_VALIDATION",
            "Single-phase hydraulic treatment.",
            "Direct N2-over-oil architecture requires later interface / aeration assessment.",
            "Potentially high for repeated-cycle behavior.",
        ),
    ]

    for (
        item_id,
        parameter,
        value,
        units,
        classification,
        status,
        basis,
        limitation,
        sensitivity,
    ) in phase1_items:
        add_register(
            item_id,
            "Phase 1",
            "Landing dynamics",
            parameter,
            value,
            units,
            classification,
            status,
            phase1_source,
            basis,
            limitation,
            sensitivity,
        )

    # -------------------------------------------------------------------------
    # Load / structural modeling
    # -------------------------------------------------------------------------

    add_register(
        "P2-001",
        "Phase 2",
        "Load path",
        "Tire loaded radius",
        TIRE_RADIUS_M * 1000.0,
        "mm",
        "DESIGN_CHOICE",
        "FROZEN_PRELIM",
        "Phase 2 load-path baseline",
        "Moment arm from axle center to tire contact force.",
        "Should later be reconciled with selected tire / wheel data.",
        "Direct effect on axle and piston bending / torque.",
    )

    add_register(
        "P2-002",
        "Phase 2",
        "Load path",
        "Wheel centerplane to strut-axis offset",
        STRUT_OFFSET_M * 1000.0,
        "mm",
        "DESIGN_CHOICE",
        "FROZEN_PRELIM",
        "Phase 2 load-path baseline",
        "Defines eccentric load transfer into the strut.",
        "Requires eventual CAD packaging confirmation.",
        "Direct effect on bending moments.",
    )

    add_register(
        "P2-003",
        "Phase 2",
        "Strength methodology",
        "Limit allowable",
        "material yield strength",
        "-",
        "MODEL_ASSUMPTION",
        "FROZEN_PRELIM",
        "Project structural screening convention",
        "Appropriate preliminary elastic-strength criterion.",
        "Does not substitute for certification factors / fatigue / damage tolerance.",
        "Controls limit margins.",
    )

    add_register(
        "P2-004",
        "Phase 2",
        "Strength methodology",
        "Ultimate allowable",
        "material tensile strength",
        "-",
        "MODEL_ASSUMPTION",
        "FROZEN_PRELIM",
        "Project structural screening convention",
        "Used for preliminary ultimate-strength screening.",
        "Detailed allowables must eventually reflect material form, heat treatment, environment, knockdowns and specification data.",
        "Controls ultimate margins.",
    )

    add_register(
        "P2-005",
        "Phase 2E1",
        "Local stress",
        "Lower-end stress-concentration factor",
        "Kt = 1.5 baseline; sensitivity checked to 3.0",
        "-",
        "MODEL_ASSUMPTION",
        "OPEN_VALIDATION",
        str(
            PATHS["phase2e1_geometry"]
        ),
        "Provides conservative screening before final local geometry exists.",
        "Must be replaced / supported by final CAD stress concentration or 3D FEA.",
        "High at piston/knuckle transitions.",
    )

    add_register(
        "P2-006",
        "Phase 2",
        "Axle",
        "Axle section",
        "50 mm OD / 34 mm ID",
        "-",
        "DESIGN_CHOICE",
        "FROZEN_PRELIM",
        str(
            PATHS["phase2_axle_csv"]
        ),
        "Hollow 300M axle preliminary sizing.",
        "Bearing seats, threads, spacers and local notches remain detail-design items.",
        "Local geometry can reduce margin.",
    )

    add_register(
        "P2-007",
        "Phase 2",
        "Regression",
        "Historic-vs-current axle result",
        "OPEN — automated audit generated in this run",
        "-",
        "NEEDS_VALIDATION",
        "AUDIT_THIS_RUN",
        "phase2_axle_regression_audit.*",
        "Old hand summary and current source-driven E1 regression do not agree.",
        "Must be closed before final lower-structure release.",
        "High — affects confidence in axle governing case / stress.",
    )

    # -------------------------------------------------------------------------
    # E2 frozen release
    # -------------------------------------------------------------------------

    e2_entries = [
        (
            "P2E2-001",
            "Barrel ID",
            e2v(
                "barrel_ID",
                64.0,
            ),
            "mm",
            "DESIGN_CHOICE",
            "FROZEN_PRELIM",
            "Retained Phase 2D working barrel baseline.",
            "Not minimum-mass optimized; local barrel details still pending.",
            "Affects pressure stress, guide packaging and cavity volume.",
        ),
        (
            "P2E2-002",
            "Barrel OD",
            e2v(
                "barrel_OD",
                74.0,
            ),
            "mm",
            "DESIGN_CHOICE",
            "FROZEN_PRELIM",
            "Retained Phase 2D working barrel baseline.",
            "Detail features may locally increase OD.",
            "Affects stiffness / mass / local features.",
        ),
        (
            "P2E2-003",
            "Piston OD",
            e2v(
                "piston_OD",
                58.0,
            ),
            "mm",
            "DESIGN_CHOICE",
            "FROZEN",
            "Source-connected Phase 1 / Phase 2 piston geometry.",
            "Final surface finish / tolerance / plating not yet defined.",
            "Controls area and guide interface.",
        ),
        (
            "P2E2-004",
            "Piston ID",
            e2v(
                "piston_ID",
                50.0,
            ),
            "mm",
            "DESIGN_CHOICE",
            "FROZEN",
            "58 x 4 mm hollow piston baseline.",
            "Blind-end and local transition detail still require CAD/FEA.",
            "Controls section modulus and reservoir volume.",
        ),
        (
            "P2E2-005",
            "Physical oleo stroke",
            e2v(
                "physical_stroke",
                230.0,
            ),
            "mm",
            "DESIGN_CHOICE",
            "FROZEN",
            str(
                PATHS["phase2e2_baseline"]
            ),
            "Physical travel available to the dynamic model.",
            "Must later be checked against detailed stops / seals / bump clearance.",
            "Critical bottoming parameter.",
        ),
        (
            "P2E2-006",
            "Metering law",
            e2v(
                "metering_law",
                "SMOOTH_CLAMPED_LINEAR",
            ),
            "-",
            "DESIGN_CHOICE",
            "FROZEN_EFFECTIVE_MODEL",
            str(
                PATHS["phase2e2_metering_compare"]
            ),
            "Selected after direct comparison with historical two-stage law.",
            "Equivalent law still requires hardware / flow calibration for production design.",
            "Controls force shaping.",
        ),
        (
            "P2E2-007",
            "Equivalent orifice start",
            e2v(
                "d_eq_start",
                10.301,
            ),
            "mm",
            "DERIVED",
            "FROZEN_EFFECTIVE_MODEL",
            str(
                PATHS["phase2e2_baseline"]
            ),
            "Phase 1 effective hydraulic law.",
            "Equivalent hydraulic diameter, not necessarily a literal drilled hole.",
            "Controls initial damping.",
        ),
        (
            "P2E2-008",
            "Equivalent orifice end",
            e2v(
                "d_eq_end",
                9.742,
            ),
            "mm",
            "DERIVED",
            "FROZEN_EFFECTIVE_MODEL",
            str(
                PATHS["phase2e2_baseline"]
            ),
            "Phase 1 effective hydraulic law.",
            "Equivalent hydraulic diameter; clamped beyond 205 mm.",
            "Controls late-stroke damping.",
        ),
        (
            "P2E2-009",
            "Fixed metering bore",
            e2v(
                "fixed_orifice_bore",
                14.0,
            ),
            "mm",
            "DESIGN_CHOICE",
            "FROZEN_PRELIM",
            str(
                PATHS["phase2e2_baseline"]
            ),
            "Working annular-orifice hardware mapping for the effective law.",
            "Pin support, tolerance, wear and manufacturability remain to be analyzed.",
            "Small diameter errors affect effective area strongly.",
        ),
        (
            "P2E2-010",
            "Direct N2-over-oil topology",
            "upper gas/oil chamber + lower hydraulic reservoir; no separator piston",
            "-",
            "DESIGN_CHOICE",
            "FROZEN_PRELIM_ARCHITECTURE",
            "Phase 2E2 architecture",
            "Physically volume-consistent in the E2-C audit.",
            "Gas/oil interface behavior, aeration and servicing still need detail design.",
            "Potential operational sensitivity.",
        ),
        (
            "P2E2-011",
            "Closure inner face above U",
            e2v(
                "pressure_closure_inner_face_above_U",
                492.780357,
            ),
            "mm",
            "DERIVED",
            "FROZEN_PRELIM",
            str(
                PATHS["phase2e2_continuity"]
            ),
            "Derived from fixed-volume gas/oil/pin continuity.",
            "Depends on retained 25 mm initial upper-oil head and 14 mm metering candidate.",
            "Changes if internal architecture changes.",
        ),
        (
            "P2E2-012",
            "Preliminary closure thickness",
            e2v(
                "pressure_closure_preliminary_thickness",
                6.0,
            ),
            "mm",
            "DERIVED",
            "PRELIM_SCREEN_ONLY",
            str(
                PATHS["phase2e2_baseline"]
            ),
            "Simply-supported circular-plate pressure screen.",
            "Not final CAD thickness; seals, retainer/thread, ports and local SCFs still required.",
            "Local detail may increase required thickness.",
        ),
        (
            "P2E2-013",
            "Preliminary E3 solid-head interface",
            e2v(
                "preliminary_E3_interface_outer_face_above_U",
                498.780357,
            ),
            "mm above U",
            "DERIVED",
            "FROZEN_PRELIM_INTERFACE",
            str(
                PATHS["phase2e2_baseline"]
            ),
            "6 mm structural screen added above continuity-derived closure face.",
            "Actual final solid-head boundary may move outward when retainers/seals are detailed.",
            "E3 attachment must remain outside live pressure cavity.",
        ),
        (
            "P2E2-014",
            "Initial upper-oil head",
            "25",
            "mm",
            "DESIGN_CHOICE",
            "WORKING_BASELINE",
            "Phase 2E2 metering candidate",
            "Provides full-extension liquid inventory above the fixed orifice.",
            "Not independently optimized; changing it moves closure location.",
            "Moderate packaging effect.",
        ),
        (
            "P2E2-015",
            "Metering-pin tip projection at full extension",
            "15",
            "mm",
            "DESIGN_CHOICE",
            "WORKING_BASELINE",
            "Phase 2E2 metering candidate",
            "Ensures pin engagement through the fixed metering plane at extension.",
            "Requires later support / buckling / tolerance analysis.",
            "Affects pin length and cavity displacement.",
        ),
        (
            "P2E2-016",
            "Metering-pin support stiffness / buckling",
            "not yet analyzed in detail",
            "-",
            "NEEDS_VALIDATION",
            "OPEN_VALIDATION",
            "Phase 2E2 limitation register",
            "Current model treats the profiled pin as geometrically ideal.",
            "Analyze lateral support, buckling, vibration and eccentricity.",
            "Could affect metering repeatability.",
        ),
        (
            "P2E2-017",
            "Pressure closure local details",
            "not yet modeled",
            "-",
            "NEEDS_VALIDATION",
            "OPEN_VALIDATION",
            "Phase 2E2 release boundary",
            "6 mm result is a global plate screen only.",
            "Seal groove, retainer/thread, ports and local FEA required.",
            "Potential local stress driver.",
        ),
    ]

    # E2 entries intentionally use two traceability forms:
    #
    #   9 fields:
    #       item_id, parameter, value, units, classification, status,
    #       basis, limitation, sensitivity
    #
    #   10 fields:
    #       same as above, but with an explicit source inserted before basis.
    #
    # Normalize both forms here so rows with a more specific source file remain
    # traceable instead of causing a tuple-unpack failure.
    for entry in e2_entries:

        if len(entry) == 9:
            (
                item_id,
                parameter,
                value,
                units,
                classification,
                status,
                basis,
                limitation,
                sensitivity,
            ) = entry

            source_or_derivation = str(
                PATHS["phase2e2_baseline"]
            )

        elif len(entry) == 10:
            (
                item_id,
                parameter,
                value,
                units,
                classification,
                status,
                source_or_derivation,
                basis,
                limitation,
                sensitivity,
            ) = entry

        else:
            raise ValueError(
                "Unexpected Phase 2E2 traceability tuple length "
                f"{len(entry)} for entry {entry!r}. Expected 9 or 10 fields."
            )

        add_register(
            item_id,
            "Phase 2E2",
            "Oleo architecture",
            parameter,
            value,
            units,
            classification,
            status,
            source_or_derivation,
            basis,
            limitation,
            sensitivity,
        )

    # -------------------------------------------------------------------------
    # 460 mm semantics as explicit open/closed item
    # -------------------------------------------------------------------------

    add_register(
        "P2D-460",
        "Phase 2D / E2",
        "Packaging semantics",
        "460 mm required piston / guide length",
        "460",
        "mm",
        "NEEDS_VALIDATION",
        "AUDIT_THIS_RUN",
        str(
            PATHS["phase2_packaging_py"]
        ),
        "E2 treated this as A-to-piston-top length.",
        "Source-code semantic audit below determines whether that interpretation is proven.",
        "High if misinterpreted because it shifts internal axial packaging.",
    )

    # -------------------------------------------------------------------------
    # Future validation / end-of-project items
    # -------------------------------------------------------------------------

    future_items = [
        (
            "V-001",
            "Fatigue / spectrum loading",
            "not yet completed",
            "NEEDS_VALIDATION",
            "OPEN_VALIDATION",
            "Repeated landing / taxi cycles require fatigue evaluation.",
        ),
        (
            "V-002",
            "3D local FEA",
            "not yet completed",
            "NEEDS_VALIDATION",
            "OPEN_VALIDATION",
            "Required for knuckle, axle transitions, barrel/head and trunnion detail.",
        ),
        (
            "V-003",
            "Manufacturing tolerances / fits",
            "not yet completed",
            "NEEDS_VALIDATION",
            "OPEN_VALIDATION",
            "Needed for piston/barrel running fit, bushings, pin and bearing interfaces.",
        ),
        (
            "V-004",
            "Corrosion / surface treatment",
            "not yet completed",
            "NEEDS_VALIDATION",
            "OPEN_VALIDATION",
            "Material allowables and wear surfaces require environmental/detail definition.",
        ),
        (
            "V-005",
            "Certification load-case mapping",
            "not yet completed",
            "NEEDS_VALIDATION",
            "OPEN_VALIDATION",
            "Map project load cases to applicable regulatory landing conditions.",
        ),
    ]

    for (
        item_id,
        parameter,
        value,
        classification,
        status,
        limitation,
    ) in future_items:
        add_register(
            item_id,
            "Project-wide",
            "Final validation",
            parameter,
            value,
            "-",
            classification,
            status,
            "End-of-project validation plan",
            "Necessary to move from preliminary design toward detailed/certification-level substantiation.",
            limitation,
            "High",
        )


# =============================================================================
# 5. 460 mm PACKAGING-SEMANTICS AUDIT
# =============================================================================

def audit_460mm_semantics():
    py_path = PATHS["phase2_packaging_py"]
    csv_path = PATHS["phase2_packaging_csv"]

    report = []

    report.append(
        "=" * 118
    )
    report.append(
        " PHASE 2D / E2 — 460 mm PISTON-LENGTH SEMANTICS AUDIT"
    )
    report.append(
        "=" * 118
    )
    report.append("")
    report.append(
        f"Python source: {py_path}"
    )
    report.append(
        f"CSV source:    {csv_path}"
    )
    report.append("")

    if not py_path.exists():
        report.append(
            "STATUS: OPEN — phase2_packaging_overlap.py was not found."
        )
        report.append(
            "The 460 mm interpretation cannot be proven from source in this run."
        )

        OUTPUT_460.write_text(
            "\n".join(report),
            encoding="utf-8",
        )

        return "OPEN_SOURCE_MISSING"

    target = "required_piston_guide_length_mm"

    report.append(
        "EXACT ASSIGNMENTS TO required_piston_guide_length_mm"
    )
    report.append(
        "-" * 118
    )

    segments = ast_assignment_source(
        py_path,
        target,
    )

    if not segments:
        report.append(
            "No direct assignment found by AST."
        )
    else:
        for i, segment in enumerate(
            segments,
            start=1,
        ):
            report.append(
                f"[Assignment {i}]"
            )
            report.append(segment)
            report.append("")

    report.append(
        "SOURCE CONTEXT AROUND PACKAGING VARIABLES"
    )
    report.append(
        "-" * 118
    )

    snippets = source_context(
        py_path,
        [
            "required_piston_guide_length_mm",
            "nominal_top_intrusion_above_U_mm",
            "physical_top_intrusion_above_U_mm",
            "virtual_top_intrusion_above_U_mm",
            "axle_A_above_U",
            "piston",
            "guide",
        ],
        radius=5,
    )

    if snippets:
        report.extend(snippets)
    else:
        report.append(
            "No matching source context found."
        )

    report.append("")
    report.append(
        "CSV PREFERRED-ROW CROSS-CHECK"
    )
    report.append(
        "-" * 118
    )

    df = read_csv_flexible(
        csv_path
    )

    value_460 = None
    top_nom = None
    top_phys = None
    top_virtual = None

    if df is None:
        report.append(
            "Packaging CSV not found."
        )
    else:
        required_col = find_column(
            df,
            [
                "required_piston_guide_length_mm",
            ],
        )

        hL_col = find_column(
            df,
            ["hL_mm"],
        )

        spacing_col = find_column(
            df,
            ["spacing_mm"],
        )

        hU_col = find_column(
            df,
            ["hU_mm"],
        )

        top_nom_col = find_column(
            df,
            [
                "nominal_top_intrusion_above_U_mm",
            ],
        )

        top_phys_col = find_column(
            df,
            [
                "physical_top_intrusion_above_U_mm",
            ],
        )

        top_virtual_col = find_column(
            df,
            [
                "virtual_top_intrusion_above_U_mm",
            ],
        )

        pref = df

        if (
            hL_col is not None
            and spacing_col is not None
            and hU_col is not None
        ):
            mask = (
                np.isclose(
                    pd.to_numeric(
                        df[hL_col],
                        errors="coerce",
                    ),
                    250.0,
                )
                & np.isclose(
                    pd.to_numeric(
                        df[spacing_col],
                        errors="coerce",
                    ),
                    150.0,
                )
                & np.isclose(
                    pd.to_numeric(
                        df[hU_col],
                        errors="coerce",
                    ),
                    400.0,
                )
            )

            rows = df.loc[mask]

            if not rows.empty:
                pref = rows.iloc[[0]]

        row = pref.iloc[0]

        if required_col is not None:
            value_460 = safe_float(
                row[required_col]
            )

            report.append(
                f"required_piston_guide_length_mm = {value_460:.6f}"
            )

        if top_nom_col is not None:
            top_nom = safe_float(
                row[top_nom_col]
            )

            report.append(
                f"nominal_top_intrusion_above_U_mm = {top_nom:.6f}"
            )

        if top_phys_col is not None:
            top_phys = safe_float(
                row[top_phys_col]
            )

            report.append(
                f"physical_top_intrusion_above_U_mm = {top_phys:.6f}"
            )

        if top_virtual_col is not None:
            top_virtual = safe_float(
                row[top_virtual_col]
            )

            report.append(
                f"virtual_top_intrusion_above_U_mm = {top_virtual:.6f}"
            )

    report.append("")
    report.append(
        "AUTOMATED DISPOSITION"
    )
    report.append(
        "-" * 118
    )

    # We do NOT claim semantic proof merely because the number is 460.
    # Strong evidence exists only if source comments / variable names explicitly
    # connect this length with piston-top position / guide engagement.
    source_text = py_path.read_text(
        encoding="utf-8",
        errors="ignore",
    ).lower()

    semantic_tokens = [
        "piston top",
        "piston_top",
        "top intrusion",
        "top_intrusion",
    ]

    has_top_semantics = any(
        token in source_text
        for token in semantic_tokens
    )

    has_required_length = (
        target.lower()
        in source_text
    )

    if (
        value_460 is not None
        and abs(
            value_460
            - 460.0
        )
        <= 1e-6
        and has_required_length
        and has_top_semantics
    ):
        status = "SOURCE_LINK_PRESENT_REVIEW_CONTEXT"
        report.append(
            "The source contains both the 460 mm required-length variable and "
            "explicit piston-top / top-intrusion logic."
        )
        report.append(
            "This is strong evidence that E2 did not invent the axial dimension, "
            "but the exact assignment context printed above should still be "
            "reviewed before marking the semantic issue fully CLOSED."
        )
    else:
        status = "OPEN_SEMANTICS_NOT_PROVEN"
        report.append(
            "The source link is not strong enough for an automatic semantic close."
        )
        report.append(
            "Do NOT treat 460 mm as independently proven A-to-piston-top length "
            "until the source context is reviewed."
        )

    OUTPUT_460.write_text(
        "\n".join(report),
        encoding="utf-8",
    )

    return status


# =============================================================================
# 6. AXLE REGRESSION AUDIT
# =============================================================================

def load_case_column(df):
    return find_column(
        df,
        [
            "case",
            "load_case",
            "case_name",
            "name",
            "loadcase",
        ],
    )


def resolve_force_column(
    df,
    component,
    level,
):
    """
    Find a component column such as Fx_limit_N / Fx_limit_kN.
    Returns (column, scale_to_N).
    """

    if df is None:
        return None, None

    comp = component.lower()
    lvl = level.lower()

    candidates = []

    for col in df.columns:
        key = normalize(col)

        if comp not in key:
            continue

        if lvl not in key:
            continue

        score = 0

        if key.startswith(comp):
            score += 2

        if "force" in key:
            score += 1

        if "kn" in key:
            scale = 1000.0
        else:
            scale = 1.0

        candidates.append(
            (
                score,
                col,
                scale,
            )
        )

    if not candidates:
        return None, None

    candidates.sort(
        key=lambda x: (
            -x[0],
            len(x[1]),
        )
    )

    _, col, scale = candidates[0]

    return col, scale


def current_load_rows(df):
    case_col = load_case_column(
        df
    )

    if case_col is None:
        raise ValueError(
            "Could not resolve load-case column in phase1_load_envelope.csv"
        )

    fx_lim_col, fx_lim_scale = resolve_force_column(
        df,
        "fx",
        "limit",
    )

    fy_lim_col, fy_lim_scale = resolve_force_column(
        df,
        "fy",
        "limit",
    )

    fz_lim_col, fz_lim_scale = resolve_force_column(
        df,
        "fz",
        "limit",
    )

    fx_ult_col, fx_ult_scale = resolve_force_column(
        df,
        "fx",
        "ultimate",
    )

    fy_ult_col, fy_ult_scale = resolve_force_column(
        df,
        "fy",
        "ultimate",
    )

    fz_ult_col, fz_ult_scale = resolve_force_column(
        df,
        "fz",
        "ultimate",
    )

    needed = [
        fx_lim_col,
        fy_lim_col,
        fz_lim_col,
    ]

    if any(
        col is None
        for col in needed
    ):
        raise ValueError(
            "Could not resolve current limit Fx/Fy/Fz columns. "
            f"Columns are: {list(df.columns)}"
        )

    rows = []

    for _, row in df.iterrows():
        case = str(
            row[case_col]
        )

        rows.append({
            "case": case,
            "Fx_limit_N": safe_float(
                row[fx_lim_col]
            )
            * fx_lim_scale,
            "Fy_limit_N": safe_float(
                row[fy_lim_col]
            )
            * fy_lim_scale,
            "Fz_limit_N": safe_float(
                row[fz_lim_col]
            )
            * fz_lim_scale,
            "Fx_ultimate_N": (
                safe_float(
                    row[fx_ult_col]
                )
                * fx_ult_scale
                if fx_ult_col is not None
                else np.nan
            ),
            "Fy_ultimate_N": (
                safe_float(
                    row[fy_ult_col]
                )
                * fy_ult_scale
                if fy_ult_col is not None
                else np.nan
            ),
            "Fz_ultimate_N": (
                safe_float(
                    row[fz_ult_col]
                )
                * fz_ult_scale
                if fz_ult_col is not None
                else np.nan
            ),
        })

    return pd.DataFrame(
        rows
    )


def axle_section_properties():
    area = (
        math.pi
        / 4.0
        * (
            AXLE_OD_M**2
            - AXLE_ID_M**2
        )
    )

    I = (
        math.pi
        / 64.0
        * (
            AXLE_OD_M**4
            - AXLE_ID_M**4
        )
    )

    J = (
        math.pi
        / 32.0
        * (
            AXLE_OD_M**4
            - AXLE_ID_M**4
        )
    )

    c = AXLE_OD_M / 2.0

    return area, I, J, c


def transparent_axle_root_stress(
    Fx_N,
    Fy_N,
    Fz_N,
    Kt=1.0,
    include_torque=False,
):
    """
    Transparent common-root reconstruction:
        N_y = Fy
        M_x = e Fz + r_t Fy
        M_z = -e Fx
        T_y = -r_t Fx only when include_torque=True

    This is NOT allowed to replace the authoritative Phase 2 axle script. It is
    only a diagnostic to show how much of the discrepancy comes from changed
    loads versus changed local-stress assumptions.
    """

    area, I, J, c = (
        axle_section_properties()
    )

    N = Fy_N

    Mx = (
        STRUT_OFFSET_M
        * Fz_N
        + TIRE_RADIUS_M
        * Fy_N
    )

    Mz = (
        -STRUT_OFFSET_M
        * Fx_N
    )

    Mb = math.hypot(
        Mx,
        Mz,
    )

    T = (
        -TIRE_RADIUS_M
        * Fx_N
        if include_torque
        else 0.0
    )

    sigma_ax = (
        abs(N)
        / area
    )

    sigma_b = (
        Kt
        * Mb
        * c
        / I
    )

    tau = (
        Kt
        * abs(T)
        * c
        / J
    )

    sigma = (
        sigma_ax
        + sigma_b
    )

    vm = math.sqrt(
        sigma**2
        + 3.0 * tau**2
    )

    return {
        "N_kN": N / 1000.0,
        "Mx_kNm": Mx / 1000.0,
        "Mz_kNm": Mz / 1000.0,
        "Mb_kNm": Mb / 1000.0,
        "T_kNm": T / 1000.0,
        "sigma_ax_MPa": sigma_ax / 1e6,
        "sigma_bend_MPa": sigma_b / 1e6,
        "tau_MPa": tau / 1e6,
        "von_mises_MPa": vm / 1e6,
    }


def audit_axle_regression():
    load_path = PATHS[
        "phase1_load_envelope"
    ]

    df = read_csv_flexible(
        load_path
    )

    report = []

    report.append(
        "=" * 118
    )
    report.append(
        " PHASE 2 — HISTORICAL VS CURRENT AXLE REGRESSION AUDIT"
    )
    report.append(
        "=" * 118
    )
    report.append("")
    report.append(
        f"Current load source: {load_path}"
    )
    report.append(
        f"Historic hand-summary target: {HISTORIC_AXLE_LIMIT_VM_MPA:.1f} MPa limit / "
        f"{HISTORIC_AXLE_ULT_VM_MPA:.1f} MPa ultimate"
    )
    report.append(
        f"Known current E1 regression reference: "
        f"{CURRENT_E1_LIMIT_VM_REFERENCE_MPA:.1f} / "
        f"{CURRENT_E1_ULT_VM_REFERENCE_MPA:.1f} MPa"
    )
    report.append("")

    if df is None:
        report.append(
            "STATUS: OPEN — current Phase 1 load-envelope CSV not found."
        )

        OUTPUT_AXLE_TXT.write_text(
            "\n".join(report),
            encoding="utf-8",
        )

        pd.DataFrame().to_csv(
            OUTPUT_AXLE_CSV,
            index=False,
        )

        return "OPEN_SOURCE_MISSING"

    try:
        current = current_load_rows(
            df
        )
    except Exception as exc:
        report.append(
            f"STATUS: OPEN — load-column parser failed: {exc}"
        )
        report.append(
            f"Columns: {list(df.columns)}"
        )

        OUTPUT_AXLE_TXT.write_text(
            "\n".join(report),
            encoding="utf-8",
        )

        pd.DataFrame().to_csv(
            OUTPUT_AXLE_CSV,
            index=False,
        )

        return "OPEN_PARSE"

    # Historical cases as rows.
    hist_rows = []

    for case, vals in HISTORIC_LOADS_KN.items():
        hist_rows.append({
            "historic_case": case,
            "historic_Fx_limit_N": vals["Fx"] * 1000.0,
            "historic_Fy_limit_N": vals["Fy"] * 1000.0,
            "historic_Fz_limit_N": vals["Fz"] * 1000.0,
        })

    hist = pd.DataFrame(
        hist_rows
    )

    # Map old names to current names only when relation is obvious enough for an
    # audit. LC2 is kept unresolved if both LC2A and LC2B exist.
    mappings = []

    current_names = list(
        current["case"].astype(str)
    )

    for old_case in HISTORIC_LOADS_KN:
        exact = [
            name for name in current_names
            if normalize(name)
            == normalize(old_case)
        ]

        plus_variant = [
            name for name in current_names
            if normalize(name)
            == normalize(
                old_case + "+"
            )
        ]

        prefix = [
            name for name in current_names
            if normalize(name).startswith(
                normalize(old_case)
            )
        ]

        if len(exact) == 1:
            mapped = exact[0]
            mapping_status = "EXACT"
        elif len(plus_variant) == 1:
            mapped = plus_variant[0]
            mapping_status = "PLUS_VARIANT"
        elif len(prefix) == 1:
            mapped = prefix[0]
            mapping_status = "UNIQUE_PREFIX"
        else:
            mapped = None
            mapping_status = (
                "AMBIGUOUS_OR_MISSING"
            )

        mappings.append({
            "historic_case": old_case,
            "current_case": mapped,
            "mapping_status": mapping_status,
        })

    map_df = pd.DataFrame(
        mappings
    )

    audit_rows = []

    # Use a small Kt sweep only as a diagnostic. We do not assume which Kt was
    # used by the historic script.
    diagnostic_Kt = [
        1.0,
        1.2,
        1.5,
    ]

    for _, mrow in map_df.iterrows():
        old_case = mrow[
            "historic_case"
        ]

        mapped = mrow[
            "current_case"
        ]

        hist_load = HISTORIC_LOADS_KN[
            old_case
        ]

        # When the mapping list is converted to a pandas DataFrame, Python
        # None values can become NaN. Therefore `mapped is None` is not a
        # sufficient missing-value test.
        if mapped is None or pd.isna(mapped) or not str(mapped).strip():
            audit_rows.append({
                "historic_case": old_case,
                "current_case": "",
                "mapping_status": mrow[
                    "mapping_status"
                ],
                "historic_Fx_kN": hist_load["Fx"],
                "historic_Fy_kN": hist_load["Fy"],
                "historic_Fz_kN": hist_load["Fz"],
                "current_Fx_kN": np.nan,
                "current_Fy_kN": np.nan,
                "current_Fz_kN": np.nan,
                "Fx_change_pct": np.nan,
                "Fy_change_pct": np.nan,
                "Fz_change_pct": np.nan,
                "diagnostic_vm_current_Kt1p0_MPa": np.nan,
                "diagnostic_vm_current_Kt1p2_MPa": np.nan,
                "diagnostic_vm_current_Kt1p5_MPa": np.nan,
            })

            continue

        matched_current_rows = current.loc[
            current["case"].astype(str)
            == str(mapped)
        ]

        if matched_current_rows.empty:
            audit_rows.append({
                "historic_case": old_case,
                "current_case": "",
                "mapping_status": "MAPPED_NAME_NOT_FOUND_DEFENSIVE_STOP",
                "historic_Fx_kN": hist_load["Fx"],
                "historic_Fy_kN": hist_load["Fy"],
                "historic_Fz_kN": hist_load["Fz"],
                "current_Fx_kN": np.nan,
                "current_Fy_kN": np.nan,
                "current_Fz_kN": np.nan,
                "Fx_change_pct": np.nan,
                "Fy_change_pct": np.nan,
                "Fz_change_pct": np.nan,
                "diagnostic_vm_current_Kt1p0_MPa": np.nan,
                "diagnostic_vm_current_Kt1p2_MPa": np.nan,
                "diagnostic_vm_current_Kt1p5_MPa": np.nan,
            })
            continue

        crow = matched_current_rows.iloc[0]

        Fx = float(
            crow["Fx_limit_N"]
        )

        Fy = float(
            crow["Fy_limit_N"]
        )

        Fz = float(
            crow["Fz_limit_N"]
        )

        def pct(new, old):
            if abs(old) < 1e-12:
                return (
                    np.nan
                    if abs(new) > 1e-12
                    else 0.0
                )

            return (
                100.0
                * (
                    new - old
                )
                / abs(old)
            )

        vm_vals = {}

        for Kt in diagnostic_Kt:
            s = (
                transparent_axle_root_stress(
                    Fx,
                    Fy,
                    Fz,
                    Kt=Kt,
                    include_torque=False,
                )
            )

            vm_vals[Kt] = s[
                "von_mises_MPa"
            ]

        audit_rows.append({
            "historic_case": old_case,
            "current_case": mapped,
            "mapping_status": mrow[
                "mapping_status"
            ],
            "historic_Fx_kN": hist_load["Fx"],
            "historic_Fy_kN": hist_load["Fy"],
            "historic_Fz_kN": hist_load["Fz"],
            "current_Fx_kN": Fx / 1000.0,
            "current_Fy_kN": Fy / 1000.0,
            "current_Fz_kN": Fz / 1000.0,
            "Fx_change_pct": pct(
                Fx / 1000.0,
                hist_load["Fx"],
            ),
            "Fy_change_pct": pct(
                Fy / 1000.0,
                hist_load["Fy"],
            ),
            "Fz_change_pct": pct(
                Fz / 1000.0,
                hist_load["Fz"],
            ),
            "diagnostic_vm_current_Kt1p0_MPa": vm_vals[1.0],
            "diagnostic_vm_current_Kt1p2_MPa": vm_vals[1.2],
            "diagnostic_vm_current_Kt1p5_MPa": vm_vals[1.5],
        })

    audit = pd.DataFrame(
        audit_rows
    )

    audit.to_csv(
        OUTPUT_AXLE_CSV,
        index=False,
    )

    report.append(
        "CASE / LOAD COMPARISON"
    )
    report.append(
        "-" * 118
    )

    with pd.option_context(
        "display.max_columns",
        None,
        "display.width",
        220,
    ):
        report.append(
            audit.to_string(
                index=False,
            )
        )

    report.append("")
    report.append(
        "AUTHORITATIVE AXLE SOURCE CONTEXT"
    )
    report.append(
        "-" * 118
    )

    axle_py = PATHS[
        "phase2_axle_py"
    ]

    if axle_py.exists():
        snippets = source_context(
            axle_py,
            [
                "Kt",
                "50",
                "34",
                "r_t",
                "tire",
                "offset",
                "torque",
                "LC4",
                "LC2",
            ],
            radius=4,
        )

        if snippets:
            report.extend(
                snippets
            )
        else:
            report.append(
                "No targeted source lines found."
            )
    else:
        report.append(
            "phase2_axle_sizing.py not found."
        )

    report.append("")
    report.append(
        "AUTOMATED DISPOSITION"
    )
    report.append(
        "-" * 118
    )

    # If current LC4+ exists, compare it directly to historic LC4 because that
    # is the old governing case. A large source-load change strongly indicates
    # that the regression difference is primarily source revision.
    lc4_rows = audit.loc[
        audit["historic_case"]
        .astype(str)
        .eq("LC4")
    ]

    status = "OPEN_REVIEW_REQUIRED"

    if not lc4_rows.empty:
        row = lc4_rows.iloc[0]

        if (
            pd.notna(
                row["current_case"]
            )
            and str(
                row["current_case"]
            ).strip()
        ):
            hist_resultant = math.sqrt(
                row["historic_Fx_kN"]**2
                + row["historic_Fy_kN"]**2
                + row["historic_Fz_kN"]**2
            )

            curr_resultant = math.sqrt(
                row["current_Fx_kN"]**2
                + row["current_Fy_kN"]**2
                + row["current_Fz_kN"]**2
            )

            ratio = (
                curr_resultant
                / hist_resultant
            )

            report.append(
                f"Historic LC4 resultant limit load: {hist_resultant:.3f} kN"
            )
            report.append(
                f"Current mapped LC4 resultant:     {curr_resultant:.3f} kN"
            )
            report.append(
                f"Current / historic load ratio:    {ratio:.4f}"
            )

            if (
                ratio < 0.80
                or ratio > 1.20
            ):
                status = (
                    "SOURCE_LOAD_REVISION_IDENTIFIED_REVIEW_FORMULA"
                )

                report.append(
                    "A material change in the authoritative load source is present."
                )
                report.append(
                    "This can explain a large part of the old/current stress regression "
                    "difference, but the axle-script Kt / torque conventions printed above "
                    "must still be checked before marking the issue fully CLOSED."
                )
            else:
                report.append(
                    "Current LC4 load magnitude is close to the historic value; load-source "
                    "revision alone does NOT explain the stress discrepancy."
                )
        else:
            report.append(
                "Historic LC4 could not be uniquely mapped to a current case."
            )

    report.append("")
    report.append(
        "IMPORTANT: diagnostic von-Mises columns above are transparent common-formula "
        "reconstructions only. The authoritative Phase 2 axle script remains the source "
        "for the actual design result."
    )

    OUTPUT_AXLE_TXT.write_text(
        "\n".join(report),
        encoding="utf-8",
    )

    return status


# =============================================================================
# 7. SOURCE MANIFEST
# =============================================================================

def write_manifest():
    rows = []

    for key, path in PATHS.items():
        rows.append({
            "source_key": key,
            "path": str(
                path.resolve()
            ),
            "exists": path.exists(),
            "sha256": (
                sha256(path)
                if path.exists()
                else ""
            ),
        })

    pd.DataFrame(
        rows
    ).to_csv(
        OUTPUT_MANIFEST,
        index=False,
    )


# =============================================================================
# 8. MAIN
# =============================================================================

def main():
    print("=" * 124)
    print(
        " PHASE 0–2E2 — ASSUMPTION / DECISION / TRACEABILITY AUDIT V0.4"
    )
    print("=" * 124)

    build_register()

    status_460 = (
        audit_460mm_semantics()
    )

    status_axle = (
        audit_axle_regression()
    )

    # Update the two audit-dependent register rows.
    for row in register_rows:
        if row[
            "item_id"
        ] == "P2D-460":
            row["status"] = (
                status_460
            )

        if row[
            "item_id"
        ] == "P2-007":
            row["status"] = (
                status_axle
            )

    register = pd.DataFrame(
        register_rows
    )

    register.to_csv(
        OUTPUT_REGISTER,
        index=False,
    )

    open_mask = (
        register["classification"]
        .astype(str)
        .eq("NEEDS_VALIDATION")
        | register["status"]
        .astype(str)
        .str.contains(
            "OPEN|AUDIT|REVIEW",
            case=False,
            regex=True,
            na=False,
        )
    )

    open_items = register.loc[
        open_mask
    ].copy()

    open_items.to_csv(
        OUTPUT_OPEN,
        index=False,
    )

    write_manifest()

    counts_class = (
        register[
            "classification"
        ]
        .value_counts()
        .sort_index()
    )

    counts_status = (
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
        " PHASE 0–2E2 — TRACEABILITY SUMMARY"
    )
    summary.append(
        "=" * 124
    )
    summary.append("")
    summary.append(
        f"Total registered items:       {len(register)}"
    )
    summary.append(
        f"Open / validation items:      {len(open_items)}"
    )
    summary.append("")
    summary.append(
        "Classification counts:"
    )

    for key, value in counts_class.items():
        summary.append(
            f"  {key:<24} {value}"
        )

    summary.append("")
    summary.append(
        "Status counts:"
    )

    for key, value in counts_status.items():
        summary.append(
            f"  {key:<40} {value}"
        )

    summary.append("")
    summary.append(
        "Targeted audit status:"
    )
    summary.append(
        f"  460 mm packaging semantics: {status_460}"
    )
    summary.append(
        f"  axle regression:            {status_axle}"
    )
    summary.append("")
    summary.append(
        "Interpretation:"
    )
    summary.append(
        "  The register is a living engineering document. SOURCE / DERIVED / DESIGN_CHOICE"
    )
    summary.append(
        "  items are not automatically 'validated hardware'. MODEL_ASSUMPTION and"
    )
    summary.append(
        "  NEEDS_VALIDATION entries must remain visible in the final project report."
    )
    summary.append(
        "=" * 124
    )

    OUTPUT_SUMMARY.write_text(
        "\n".join(summary),
        encoding="utf-8",
    )

    print("\nTRACEABILITY REGISTER")
    print("-" * 124)
    print(
        f"Registered items:              {len(register)}"
    )
    print(
        f"Open / validation items:       {len(open_items)}"
    )

    print("\nCLASSIFICATION COUNTS")
    print("-" * 124)

    for key, value in counts_class.items():
        print(
            f"{key:<28} {value}"
        )

    print("\nTARGETED AUDITS")
    print("-" * 124)
    print(
        f"460 mm semantics:              {status_460}"
    )
    print(
        f"Axle regression:               {status_axle}"
    )

    print("\nOPEN / VALIDATION ITEMS")
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
            "limitation_or_validation",
        ]

        print(
            open_items[
                display_cols
            ].to_string(
                index=False,
            )
        )

    print("\nOUTPUT FILES")
    print("-" * 124)
    print(
        f"Traceability register:         {OUTPUT_REGISTER}"
    )
    print(
        f"Open validation register:      {OUTPUT_OPEN}"
    )
    print(
        f"460 mm semantics audit:        {OUTPUT_460}"
    )
    print(
        f"Axle regression CSV:           {OUTPUT_AXLE_CSV}"
    )
    print(
        f"Axle regression report:        {OUTPUT_AXLE_TXT}"
    )
    print(
        f"Source manifest:               {OUTPUT_MANIFEST}"
    )
    print(
        f"Summary report:                {OUTPUT_SUMMARY}"
    )
    print("=" * 124)


if __name__ == "__main__":
    main()
