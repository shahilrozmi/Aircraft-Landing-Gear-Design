from pathlib import Path
import ast
import math
import os
import re
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd


# =============================================================================
# LANDING GEAR DESIGN PROJECT
# PHASE 2E2-A — METERING-LAW COMPARISON AUDIT V0.3
#
# PURPOSE
#   Compare the CURRENT smooth-linear Phase 1 metering law against the earlier
#   historical two-stage law using the EXACT SAME current Phase 1 landing model.
#
# METHOD
#   1. Locate the authoritative current Phase 1 model:
#          landing_dynamic_v04_2dof.py
#   2. Read / verify its current smooth-linear orifice_diameter() definition.
#   3. Create temporary source copies of that SAME model in which ONLY
#      orifice_diameter() is replaced.
#   4. Run each temporary model in a subprocess with a non-interactive plotting
#      backend.
#   5. Parse the model's own printed engineering metrics.
#   6. Compare stroke, forces, energy, timing when available, and the inherent
#      metering-law discontinuity.
#
# IMPORTANT
#   The current Phase 1 source itself is not modified.
#
# HISTORICAL REFERENCE
#   Earlier Phase 1 V0.2 used:
#
#       if x < 0.050 m:
#           d = 0.01030 m
#       else:
#           d = 0.00997 m
#
#   These are historical configuration inputs, NOT copied calculated results.
#
# OUTPUTS
#   phase2e2_metering_law_comparison.csv
#   phase2e2_metering_law_delta.csv
#   phase2e2_metering_law_smoothness.csv
#   phase2e2_metering_smooth_raw_output.txt
#   phase2e2_metering_twostage_raw_output.txt
# =============================================================================


# =============================================================================
# 1. PATHS
# =============================================================================

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.resolve()

CURRENT_PHASE1_FILENAME = "landing_dynamic_v04_2dof.py"

OUTPUT_SUMMARY_CSV = (
    HERE / "phase2e2_metering_law_comparison.csv"
).resolve()

OUTPUT_DELTA_CSV = (
    HERE / "phase2e2_metering_law_delta.csv"
).resolve()

OUTPUT_SMOOTHNESS_CSV = (
    HERE / "phase2e2_metering_law_smoothness.csv"
).resolve()

OUTPUT_SMOOTH_RAW = (
    HERE / "phase2e2_metering_smooth_raw_output.txt"
).resolve()

OUTPUT_TWOSTAGE_RAW = (
    HERE / "phase2e2_metering_twostage_raw_output.txt"
).resolve()


# =============================================================================
# 2. HISTORICAL TWO-STAGE REFERENCE
# =============================================================================

HISTORICAL_SWITCH_M = 0.050
HISTORICAL_D_STAGE1_M = 0.01030
HISTORICAL_D_STAGE2_M = 0.00997


# =============================================================================
# 3. EXECUTION CONTROLS
# =============================================================================

SUBPROCESS_TIMEOUT_S = 180.0

METRIC_PATTERNS = {
    "peak_oleo_stroke_mm": {
        # Optional because different Phase 1 revisions print this quantity with
        # different wording. The audit must not discard otherwise valid force /
        # energy comparisons merely because this one label changed.
        "required": False,
        "patterns": [
            r"Peak demanded oleo stroke\s*:\s*([+\-0-9.eE]+)\s*mm",
            r"Peak oleo stroke\s*:\s*([+\-0-9.eE]+)\s*mm",
            r"Peak oleo compression\s*:\s*([+\-0-9.eE]+)\s*mm",
            r"Peak compression\s*:\s*([+\-0-9.eE]+)\s*mm",
            r"Maximum oleo stroke\s*:\s*([+\-0-9.eE]+)\s*mm",
            r"Maximum oleo compression\s*:\s*([+\-0-9.eE]+)\s*mm",
            r"Maximum compression\s*:\s*([+\-0-9.eE]+)\s*mm",
            r"Max(?:imum)?\s+(?:oleo\s+)?(?:stroke|compression|travel)\s*:\s*([+\-0-9.eE]+)\s*mm",
            r"Peak\s+(?:shock\s+strut\s+)?(?:stroke|compression|travel)\s*:\s*([+\-0-9.eE]+)\s*mm",
        ],
    },
    "peak_tire_deflection_mm": {
        "required": False,
        "patterns": [
            r"Peak tire deflection\s*:\s*([+\-0-9.eE]+)\s*mm",
        ],
    },
    "peak_ground_reaction_kN": {
        "required": False,
        "patterns": [
            r"Peak ground reaction\s*:\s*([+\-0-9.eE]+)\s*kN",
        ],
    },
    "peak_internal_strut_force_kN": {
        "required": True,
        "patterns": [
            r"Peak internal strut force\s*:\s*([+\-0-9.eE]+)\s*kN",
            r"Peak strut force\s*:\s*([+\-0-9.eE]+)\s*kN",
        ],
    },
    "peak_gas_force_kN": {
        "required": False,
        "patterns": [
            r"Peak gas force\s*:\s*([+\-0-9.eE]+)\s*kN",
        ],
    },
    "peak_hydraulic_force_kN": {
        "required": True,
        "patterns": [
            r"Peak hydraulic force\s*:\s*([+\-0-9.eE]+)\s*kN",
        ],
    },
    "gas_work_kJ": {
        "required": False,
        "patterns": [
            r"Gas work\s*:\s*([+\-0-9.eE]+)\s*kJ",
        ],
    },
    "hydraulic_energy_kJ": {
        "required": True,
        "patterns": [
            r"Hydraulic energy dissipated\s*:\s*([+\-0-9.eE]+)\s*kJ",
            r"Hydraulic energy\s*:\s*([+\-0-9.eE]+)\s*kJ",
        ],
    },
    "energy_residual_J": {
        "required": False,
        "patterns": [
            r"Energy residual\s*:\s*([+\-0-9.eE]+)\s*J",
        ],
    },
    "time_to_peak_s": {
        "required": False,
        "patterns": [
            r"First maximum compression time\s*:\s*([+\-0-9.eE]+)\s*s",
            r"Time to first maximum compression\s*:\s*([+\-0-9.eE]+)\s*s",
            r"Time to peak compression\s*:\s*([+\-0-9.eE]+)\s*s",
        ],
    },
}


# =============================================================================
# 4. AST / SOURCE UTILITIES
# =============================================================================

def numeric_literal(node, env=None):
    if env is None:
        env = {}

    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        return None

    if isinstance(node, ast.Name):
        value = env.get(node.id)

        if isinstance(value, (int, float)):
            return float(value)

        return None

    if isinstance(node, ast.UnaryOp):
        value = numeric_literal(node.operand, env)

        if value is None:
            return None

        if isinstance(node.op, ast.USub):
            return -value

        if isinstance(node.op, ast.UAdd):
            return value

        return None

    if isinstance(node, ast.BinOp):
        left = numeric_literal(node.left, env)
        right = numeric_literal(node.right, env)

        if left is None or right is None:
            return None

        if isinstance(node.op, ast.Add):
            return left + right

        if isinstance(node.op, ast.Sub):
            return left - right

        if isinstance(node.op, ast.Mult):
            return left * right

        if isinstance(node.op, ast.Div):
            return left / right

        if isinstance(node.op, ast.Pow):
            return left**right

    return None


def build_numeric_environment(tree):
    assignments = []

    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = [
                target.id
                for target in node.targets
                if isinstance(target, ast.Name)
            ]

            if names:
                assignments.append((names, node.value))

        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                assignments.append(
                    ([node.target.id], node.value)
                )

    env = {}

    for _ in range(max(1, len(assignments) + 1)):
        changed = False

        for names, expr in assignments:
            value = numeric_literal(expr, env)

            if value is None:
                continue

            for name in names:
                if name not in env or env[name] != value:
                    env[name] = value
                    changed = True

        if not changed:
            break

    return env


def locate_current_phase1_source():
    preferred = (
        PROJECT_ROOT
        / "phase1_model_development"
        / CURRENT_PHASE1_FILENAME
    ).resolve()

    if preferred.exists():
        return preferred

    matches = list(
        PROJECT_ROOT.rglob(
            CURRENT_PHASE1_FILENAME
        )
    )

    if len(matches) == 1:
        return matches[0].resolve()

    if len(matches) > 1:
        ranked = sorted(
            matches,
            key=lambda p: (
                "phase1_model_development"
                not in str(p.parent).lower(),
                len(str(p)),
            ),
        )
        return ranked[0].resolve()

    raise FileNotFoundError(
        f"Could not locate {CURRENT_PHASE1_FILENAME} below:\n"
        f"{PROJECT_ROOT}"
    )


def current_smooth_configuration(source_path):
    source = source_path.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    tree = ast.parse(
        source,
        filename=str(source_path),
    )

    env = build_numeric_environment(tree)

    required_names = [
        "d_orifice_start",
        "d_orifice_end",
    ]

    missing = [
        name
        for name in required_names
        if name not in env
    ]

    x_design_name = None

    for candidate in [
        "x_metering",
        "x_hand",
        "x_design",
    ]:
        if candidate in env:
            x_design_name = candidate
            break

    if x_design_name is None:
        missing.append(
            "x_metering/x_hand/x_design"
        )

    if missing:
        raise ValueError(
            "Current Phase 1 smooth schedule configuration could not be "
            "resolved: "
            + ", ".join(missing)
        )

    functions = [
        node
        for node in tree.body
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == "orifice_diameter"
        )
    ]

    if len(functions) != 1:
        raise ValueError(
            "Expected exactly one module-level orifice_diameter() "
            "in the current Phase 1 source."
        )

    function = functions[0]

    referenced_names = {
        node.id
        for node in ast.walk(function)
        if isinstance(node, ast.Name)
    }

    for required in [
        "d_orifice_start",
        "d_orifice_end",
        x_design_name,
    ]:
        if required not in referenced_names:
            raise ValueError(
                "Current orifice_diameter() does not reference "
                f"{required}; refusing to call it the expected smooth law."
            )

    return {
        "d_start_m": float(
            env["d_orifice_start"]
        ),
        "d_end_m": float(
            env["d_orifice_end"]
        ),
        "x_design_m": float(
            env[x_design_name]
        ),
        "x_design_name": x_design_name,
        "function": function,
        "source": source,
    }


def replace_function_in_source(
    source,
    function_node,
    replacement_text,
):
    lines = source.splitlines(
        keepends=True
    )

    start = function_node.lineno - 1
    end = function_node.end_lineno

    replacement = (
        replacement_text.rstrip()
        + "\n\n"
    )

    return "".join(
        lines[:start]
        + [replacement]
        + lines[end:]
    )


# =============================================================================
# 5. VARIANT FUNCTION DEFINITIONS
# =============================================================================

def smooth_function_text(config):
    """
    Return valid Python source for the current smooth metering law.

    Comments are used instead of an injected docstring so there is no quoting /
    escaping ambiguity when this text is spliced into the temporary Phase 1
    source.
    """
    return f"""def orifice_diameter(x):
    # Phase 2E2-A comparison variant:
    # CURRENT smooth clamped-linear metering law.
    x_clamped = np.clip(
        x,
        0.0,
        {config["x_design_m"]:.17g},
    )

    fraction = (
        x_clamped
        / {config["x_design_m"]:.17g}
    )

    return (
        {config["d_start_m"]:.17g}
        + (
            {config["d_end_m"]:.17g}
            - {config["d_start_m"]:.17g}
        )
        * fraction
    )
"""


def historical_twostage_function_text():
    """
    Return valid Python source for the archived Phase 1 V0.2 two-stage law.
    """
    return f"""def orifice_diameter(x):
    # Phase 2E2-A comparison variant:
    # HISTORICAL Phase 1 V0.2 two-stage metering law.
    if x < {HISTORICAL_SWITCH_M:.17g}:
        return {HISTORICAL_D_STAGE1_M:.17g}
    else:
        return {HISTORICAL_D_STAGE2_M:.17g}
"""


# =============================================================================
# 6. RUN EXACT CURRENT MODEL WITH PATCHED METERING LAW
# =============================================================================

def run_variant(
    source_path,
    source_text,
    label,
):
    env = os.environ.copy()

    env["MPLBACKEND"] = "Agg"

    with tempfile.TemporaryDirectory(
        prefix=f"phase2e2_metering_{label.lower()}_",
        dir=str(HERE),
    ) as tmpdir:

        tmpdir = Path(tmpdir)

        variant_path = (
            tmpdir
            / f"{source_path.stem}_{label.lower()}.py"
        )

        variant_path.write_text(
            source_text,
            encoding="utf-8",
        )

        completed = subprocess.run(
            [
                sys.executable,
                str(variant_path),
            ],
            cwd=str(source_path.parent),
            env=env,
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT_S,
        )

        stdout = completed.stdout
        stderr = completed.stderr

        combined = stdout

        if stderr.strip():
            combined += (
                "\n\n--- STDERR ---\n"
                + stderr
            )

        if completed.returncode != 0:
            raise RuntimeError(
                f"{label} Phase 1 variant failed with return code "
                f"{completed.returncode}.\n\n"
                f"{combined[-6000:]}"
            )

        return combined


# =============================================================================
# 7. METRIC EXTRACTION
# =============================================================================

def first_regex_value(text, patterns):
    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if match:
            return float(match.group(1))

    return np.nan


def diagnostic_motion_lines(output_text):
    """
    Return likely stroke/compression report lines for parser diagnostics.
    """
    lines = []

    for raw_line in output_text.splitlines():
        lower = raw_line.lower()

        if (
            ("stroke" in lower or "compression" in lower or "travel" in lower)
            and ("mm" in lower or " m" in lower)
        ):
            lines.append(raw_line.strip())

    # Keep the console readable.
    return lines[:20]


def parse_metrics(output_text):
    result = {}

    for metric_name, info in METRIC_PATTERNS.items():
        result[metric_name] = (
            first_regex_value(
                output_text,
                info["patterns"],
            )
        )

    lower = output_text.lower()

    if "bottomed" in lower:
        if re.search(
            r"bottom(?:ed|ing)[^\n:]*:\s*(yes|true|fail)",
            lower,
        ):
            result["bottoming_status"] = "BOTTOMING_INDICATED"
        elif re.search(
            r"bottom(?:ed|ing)[^\n:]*:\s*(no|false|pass)",
            lower,
        ):
            result["bottoming_status"] = "NO_BOTTOMING"
        else:
            result["bottoming_status"] = "MENTIONED_REVIEW_RAW"
    else:
        result["bottoming_status"] = "NOT_PRINTED"

    missing_required = [
        name
        for name, info in METRIC_PATTERNS.items()
        if (
            info["required"]
            and not np.isfinite(
                result[name]
            )
        )
    ]

    return result, missing_required


# =============================================================================
# 8. ANALYTICAL SMOOTHNESS / HYDRAULIC-COEFFICIENT DIAGNOSTIC
# =============================================================================

def relative_hydraulic_coefficient(d_m):
    return 1.0 / d_m**4


def smoothness_table(config):
    rows = []

    C_smooth_start = relative_hydraulic_coefficient(
        config["d_start_m"]
    )

    C_smooth_end = relative_hydraulic_coefficient(
        config["d_end_m"]
    )

    C_two_before = relative_hydraulic_coefficient(
        HISTORICAL_D_STAGE1_M
    )

    C_two_after = relative_hydraulic_coefficient(
        HISTORICAL_D_STAGE2_M
    )

    rows.append({
        "law": "CURRENT_SMOOTH_LINEAR",
        "diameter_start_mm": (
            config["d_start_m"] * 1000.0
        ),
        "diameter_end_mm": (
            config["d_end_m"] * 1000.0
        ),
        "design_stroke_mm": (
            config["x_design_m"] * 1000.0
        ),
        "internal_diameter_jump_mm": 0.0,
        "hydraulic_coefficient_jump_pct": 0.0,
        "overall_C_h_end_vs_start_pct": (
            (
                C_smooth_end
                / C_smooth_start
                - 1.0
            )
            * 100.0
        ),
        "classification": (
            "CONTINUOUS_METERING_LAW"
        ),
    })

    rows.append({
        "law": "HISTORICAL_TWO_STAGE",
        "diameter_start_mm": (
            HISTORICAL_D_STAGE1_M
            * 1000.0
        ),
        "diameter_end_mm": (
            HISTORICAL_D_STAGE2_M
            * 1000.0
        ),
        "design_stroke_mm": (
            HISTORICAL_SWITCH_M
            * 1000.0
        ),
        "internal_diameter_jump_mm": (
            (
                HISTORICAL_D_STAGE2_M
                - HISTORICAL_D_STAGE1_M
            )
            * 1000.0
        ),
        "hydraulic_coefficient_jump_pct": (
            (
                C_two_after
                / C_two_before
                - 1.0
            )
            * 100.0
        ),
        "overall_C_h_end_vs_start_pct": (
            (
                C_two_after
                / C_two_before
                - 1.0
            )
            * 100.0
        ),
        "classification": (
            "DISCRETE_METERING_STEP"
        ),
    })

    return pd.DataFrame(rows)


# =============================================================================
# 9. MAIN
# =============================================================================

def main():

    print("=" * 112)
    print(
        " PHASE 2E2-A — METERING-LAW COMPARISON AUDIT V0.3"
    )
    print("=" * 112)

    source_path = (
        locate_current_phase1_source()
    )

    config = current_smooth_configuration(
        source_path
    )

    print("\nCURRENT PHASE 1 SOURCE")
    print("-" * 112)
    print(f"File:                         {source_path}")
    print(
        "Current metering law:         smooth clamped-linear"
    )
    print(
        f"Start diameter:               "
        f"{config['d_start_m']*1000.0:.4f} mm"
    )
    print(
        f"End diameter:                 "
        f"{config['d_end_m']*1000.0:.4f} mm"
    )
    print(
        f"Design metering stroke:       "
        f"{config['x_design_m']*1000.0:.3f} mm"
    )

    print("\nHISTORICAL COMPARISON LAW")
    print("-" * 112)
    print(
        f"Stage transition:             "
        f"{HISTORICAL_SWITCH_M*1000.0:.3f} mm"
    )
    print(
        f"Before transition:            "
        f"{HISTORICAL_D_STAGE1_M*1000.0:.4f} mm"
    )
    print(
        f"After transition:             "
        f"{HISTORICAL_D_STAGE2_M*1000.0:.4f} mm"
    )

    smooth_source = replace_function_in_source(
        config["source"],
        config["function"],
        smooth_function_text(
            config
        ),
    )

    twostage_source = replace_function_in_source(
        config["source"],
        config["function"],
        historical_twostage_function_text(),
    )

    # Validate the complete temporary sources before subprocess execution.
    try:
        compile(
            smooth_source,
            "<phase1_smooth_variant>",
            "exec",
        )
    except SyntaxError as exc:
        raise SyntaxError(
            "Generated CURRENT_SMOOTH_LINEAR Phase 1 source is invalid. "
            f"Line {exc.lineno}: {exc.msg}"
        ) from exc

    try:
        compile(
            twostage_source,
            "<phase1_twostage_variant>",
            "exec",
        )
    except SyntaxError as exc:
        raise SyntaxError(
            "Generated HISTORICAL_TWO_STAGE Phase 1 source is invalid. "
            f"Line {exc.lineno}: {exc.msg}"
        ) from exc

    print("\nPATCHED PHASE 1 SOURCE VALIDATION")
    print("-" * 112)
    print("CURRENT_SMOOTH_LINEAR source:  PASS")
    print("HISTORICAL_TWO_STAGE source:   PASS")

    print("\nRUNNING EXACT CURRENT PHASE 1 MODEL")
    print("-" * 112)
    print(
        "Case 1/2: CURRENT_SMOOTH_LINEAR ..."
    )

    smooth_output = run_variant(
        source_path,
        smooth_source,
        "SMOOTH",
    )

    print(
        "Case 2/2: HISTORICAL_TWO_STAGE ..."
    )

    twostage_output = run_variant(
        source_path,
        twostage_source,
        "TWOSTAGE",
    )

    OUTPUT_SMOOTH_RAW.write_text(
        smooth_output,
        encoding="utf-8",
    )

    OUTPUT_TWOSTAGE_RAW.write_text(
        twostage_output,
        encoding="utf-8",
    )

    smooth_metrics, smooth_missing = (
        parse_metrics(
            smooth_output
        )
    )

    twostage_metrics, twostage_missing = (
        parse_metrics(
            twostage_output
        )
    )

    # Do not fail merely because one optional printed label changed between
    # Phase 1 revisions. Require only that the core comparison metrics exist.
    core_metrics = [
        "peak_internal_strut_force_kN",
        "peak_hydraulic_force_kN",
        "hydraulic_energy_kJ",
    ]

    smooth_core_missing = [
        name
        for name in core_metrics
        if not np.isfinite(
            smooth_metrics[name]
        )
    ]

    twostage_core_missing = [
        name
        for name in core_metrics
        if not np.isfinite(
            twostage_metrics[name]
        )
    ]

    if smooth_core_missing or twostage_core_missing:
        raise ValueError(
            "The Phase 1 model ran successfully, but core comparison metrics "
            "could not be parsed.\n"
            f"Smooth core missing: {smooth_core_missing}\n"
            f"Two-stage core missing: {twostage_core_missing}\n\n"
            "Raw outputs were written for diagnosis:\n"
            f"{OUTPUT_SMOOTH_RAW}\n"
            f"{OUTPUT_TWOSTAGE_RAW}"
        )

    # If peak stroke is still not found, keep the comparison alive and print the
    # source lines that probably contain the differently worded quantity.
    smooth_motion_diag = []
    twostage_motion_diag = []

    if not np.isfinite(
        smooth_metrics["peak_oleo_stroke_mm"]
    ):
        smooth_motion_diag = diagnostic_motion_lines(
            smooth_output
        )

    if not np.isfinite(
        twostage_metrics["peak_oleo_stroke_mm"]
    ):
        twostage_motion_diag = diagnostic_motion_lines(
            twostage_output
        )

    comparison_rows = []

    for label, metrics in [
        (
            "CURRENT_SMOOTH_LINEAR",
            smooth_metrics,
        ),
        (
            "HISTORICAL_TWO_STAGE",
            twostage_metrics,
        ),
    ]:

        row = {
            "metering_law": label,
        }

        row.update(metrics)

        comparison_rows.append(row)

    comparison = pd.DataFrame(
        comparison_rows
    )

    comparison.to_csv(
        OUTPUT_SUMMARY_CSV,
        index=False,
    )

    delta_rows = []

    for metric_name in METRIC_PATTERNS:

        smooth_value = (
            smooth_metrics[metric_name]
        )

        two_value = (
            twostage_metrics[metric_name]
        )

        if (
            np.isfinite(smooth_value)
            and np.isfinite(two_value)
        ):
            absolute_delta = (
                two_value
                - smooth_value
            )

            if abs(smooth_value) > 1e-15:
                percent_delta = (
                    absolute_delta
                    / smooth_value
                    * 100.0
                )
            else:
                percent_delta = np.nan
        else:
            absolute_delta = np.nan
            percent_delta = np.nan

        delta_rows.append({
            "metric": metric_name,
            "current_smooth": smooth_value,
            "historical_two_stage": two_value,
            "two_stage_minus_smooth": (
                absolute_delta
            ),
            "delta_percent_vs_smooth": (
                percent_delta
            ),
        })

    delta = pd.DataFrame(
        delta_rows
    )

    delta.to_csv(
        OUTPUT_DELTA_CSV,
        index=False,
    )

    smoothness = smoothness_table(
        config
    )

    smoothness.to_csv(
        OUTPUT_SMOOTHNESS_CSV,
        index=False,
    )

    if (
        smooth_motion_diag
        or twostage_motion_diag
    ):
        print("\nPEAK-STROKE PARSER DIAGNOSTIC")
        print("-" * 112)
        print(
            "The simulations completed successfully, but the current Phase 1 "
            "revision does not print peak stroke using one of the recognized "
            "labels. The comparison will continue with stroke shown as NaN."
        )

        if smooth_motion_diag:
            print("\nLikely CURRENT_SMOOTH_LINEAR source lines:")
            for line in smooth_motion_diag:
                print(f"  {line}")

        if twostage_motion_diag:
            print("\nLikely HISTORICAL_TWO_STAGE source lines:")
            for line in twostage_motion_diag:
                print(f"  {line}")

    print("\nDYNAMIC RESPONSE COMPARISON")
    print("-" * 112)

    display_columns = [
        "metering_law",
        "peak_oleo_stroke_mm",
        "peak_internal_strut_force_kN",
        "peak_hydraulic_force_kN",
        "hydraulic_energy_kJ",
        "time_to_peak_s",
        "bottoming_status",
    ]

    print(
        comparison[
            display_columns
        ].to_string(
            index=False,
            formatters={
                "peak_oleo_stroke_mm": (
                    lambda x: (
                        "not parsed"
                        if not np.isfinite(x)
                        else f"{x:.3f}"
                    )
                ),
                "peak_internal_strut_force_kN": (
                    lambda x: f"{x:.3f}"
                ),
                "peak_hydraulic_force_kN": (
                    lambda x: f"{x:.3f}"
                ),
                "hydraulic_energy_kJ": (
                    lambda x: f"{x:.4f}"
                ),
                "time_to_peak_s": (
                    lambda x: (
                        "not printed"
                        if not np.isfinite(x)
                        else f"{x:.5f}"
                    )
                ),
            },
        )
    )

    print("\nTWO-STAGE MINUS CURRENT-SMOOTH")
    print("-" * 112)

    delta_display = delta.loc[
        delta["metric"].isin([
            "peak_oleo_stroke_mm",
            "peak_internal_strut_force_kN",
            "peak_hydraulic_force_kN",
            "hydraulic_energy_kJ",
            "time_to_peak_s",
        ])
    ].copy()

    print(
        delta_display.to_string(
            index=False,
            formatters={
                "current_smooth": (
                    lambda x: (
                        "nan"
                        if not np.isfinite(x)
                        else f"{x:.5f}"
                    )
                ),
                "historical_two_stage": (
                    lambda x: (
                        "nan"
                        if not np.isfinite(x)
                        else f"{x:.5f}"
                    )
                ),
                "two_stage_minus_smooth": (
                    lambda x: (
                        "nan"
                        if not np.isfinite(x)
                        else f"{x:+.5f}"
                    )
                ),
                "delta_percent_vs_smooth": (
                    lambda x: (
                        "nan"
                        if not np.isfinite(x)
                        else f"{x:+.3f}%"
                    )
                ),
            },
        )
    )

    print("\nMETERING-LAW SMOOTHNESS DIAGNOSTIC")
    print("-" * 112)

    print(
        smoothness.to_string(
            index=False,
            formatters={
                "diameter_start_mm": (
                    lambda x: f"{x:.4f}"
                ),
                "diameter_end_mm": (
                    lambda x: f"{x:.4f}"
                ),
                "design_stroke_mm": (
                    lambda x: f"{x:.3f}"
                ),
                "internal_diameter_jump_mm": (
                    lambda x: f"{x:+.4f}"
                ),
                "hydraulic_coefficient_jump_pct": (
                    lambda x: f"{x:+.3f}%"
                ),
                "overall_C_h_end_vs_start_pct": (
                    lambda x: f"{x:+.3f}%"
                ),
            },
        )
    )

    print("\nINTERPRETATION RULE")
    print("-" * 112)
    print(
        "No metering law is automatically selected by this script. "
        "Use the dynamic response together with the discontinuity diagnostic. "
        "The preferred E2 baseline should preserve acceptable stroke / force / "
        "energy response without introducing an unnecessary force discontinuity."
    )

    print("\nOUTPUT FILES")
    print("-" * 112)
    print(
        f"Comparison summary:          {OUTPUT_SUMMARY_CSV}"
    )
    print(
        f"Response deltas:             {OUTPUT_DELTA_CSV}"
    )
    print(
        f"Smoothness audit:            {OUTPUT_SMOOTHNESS_CSV}"
    )
    print(
        f"Smooth raw Phase 1 output:   {OUTPUT_SMOOTH_RAW}"
    )
    print(
        f"Two-stage raw Phase 1 output:{OUTPUT_TWOSTAGE_RAW}"
    )

    print("=" * 112)


if __name__ == "__main__":
    main()
