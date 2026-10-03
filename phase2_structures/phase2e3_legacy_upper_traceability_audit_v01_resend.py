"""
Landing_Gear_Design_Project
PHASE 2E3 — LEGACY UPPER-ATTACHMENT GEOMETRY / TRACEABILITY AUDIT V0.1

PURPOSE
-------
Backfill engineering traceability for the upper landing-gear attachment geometry
before the physical B14B horn/brace is added.

This is NOT a redesign and it does NOT silently "upgrade" old provisional values.

The audit asks, for each significant feature:
    1) Was it sized / selected in Python or another engineering source?
    2) Is it physically present and dimensionally verified in the B13C geometry?
    3) If not physically modeled yet, is it clearly marked OPEN rather than frozen?

PRIMARY SCOPE
-------------
- upper-head boss
- continuous trunnion shaft
- bronze sleeves / flanges
- Ø50 central relief
- curved-head spotfaces
- shaft/head clearance
- axial-retention architecture (shoulder / thrust washer / collar-type hardware)
- airframe-side support / bearing geometry status

IMPORTANT
---------
A feature does NOT fail merely because it is still open.
The audit fails only if a modeled/frozen-looking feature conflicts with its source
or if the project would incorrectly imply that an unmodeled detail is frozen.

OUTPUTS
-------
phase2e3_legacy_upper_traceability_matrix.csv
phase2e3_legacy_upper_dimension_checks.csv
phase2e3_legacy_upper_open_items.csv
phase2e3_legacy_upper_traceability_summary.txt
"""

from __future__ import annotations

import csv
import math
import re
from pathlib import Path


HERE = Path(__file__).resolve().parent

OUT_MATRIX = HERE / "phase2e3_legacy_upper_traceability_matrix.csv"
OUT_CHECKS = HERE / "phase2e3_legacy_upper_dimension_checks.csv"
OUT_OPEN = HERE / "phase2e3_legacy_upper_open_items.csv"
OUT_SUMMARY = HERE / "phase2e3_legacy_upper_traceability_summary.txt"

ABS_TOL_MM = 1e-3


# =============================================================================
# 1. FILE DISCOVERY
# =============================================================================

def first_match(patterns):
    for pattern in patterns:
        matches = sorted(HERE.rglob(pattern))
        if matches:
            return matches[0]
    return None


def read_text(path):
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8-sig", errors="replace")


B13C_VALIDATION = first_match([
    "phase2e3b13c_geometry_validation.txt",
    "phase2e3b13c_geometry_validation*.txt",
])

B13B_V03_SUMMARY = first_match([
    "phase2e3b13b_v03_summary.txt",
    "*phase2e3b13b*v03*summary*.txt",
])

B13B_V03_PY = first_match([
    "phase2e3b13b_v03_axial_thrust_flange_sizing.py",
])

B13B_BASE_PY = first_match([
    "phase2e3b13b_bushing_interface_sizing.py",
])

B13B_V02R1_PY = first_match([
    "phase2e3b13b_v02r1_interference_fit_min_ligament_correction.py",
])

B13B_V04_PY = first_match([
    "phase2e3b13b_v04_central_relief_trade.py",
])

RETENTION_PY = first_match([
    "phase2e3b10a_retention_architecture_closeout.py",
])

RETENTION_STRUCTURED = first_match([
    "phase2e3b10a*.csv",
    "*retention*architecture*.csv",
])

RETENTION_SUMMARY = first_match([
    "phase2e3b10a*.txt",
    "*retention*architecture*.txt",
])

B11_PY = first_match([
    "phase2e3b11_upper_head_local_screens.py",
])

B11_STRUCTURED = first_match([
    "phase2e3b11*.csv",
])

B11_SUMMARY = first_match([
    "phase2e3b11*.txt",
])

B2_PY = first_match([
    "phase2e3b2_trunnion_coupled_sizing_v01.py",
])

B2_STRUCTURED = first_match([
    "phase2e3b2*.csv",
])

B2_SUMMARY = first_match([
    "phase2e3b2*.txt",
])

B13C_TEXT = read_text(B13C_VALIDATION)
B13B_V03_TEXT = read_text(B13B_V03_SUMMARY)
RETENTION_TEXT = "\n".join([
    read_text(RETENTION_PY),
    read_text(RETENTION_STRUCTURED),
    read_text(RETENTION_SUMMARY),
])


# =============================================================================
# 2. PARSERS
# =============================================================================

def require_match(text, pattern, label):
    m = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
    if not m:
        raise ValueError(f"Could not parse required B13C geometry item: {label}")
    return m


if not B13C_VALIDATION:
    raise FileNotFoundError(
        "B13C geometry validation not found. Expected current_design/"
        "phase2e3b13c_geometry_validation.txt or equivalent."
    )

# Actual B13C geometry.
m = require_match(
    B13C_TEXT,
    r"Upper-head outer boss:\s*Ø?\s*([0-9.]+)\s*mm\s*x\s*([0-9.]+)\s*mm\s*high",
    "upper-head outer boss",
)
BOSS_D_MM = float(m.group(1))
BOSS_H_MM = float(m.group(2))

m = require_match(
    B13C_TEXT,
    r"Head passage:\s*Ø?\s*([0-9.]+)\s*mm\s*THROUGH",
    "head passage",
)
PASSAGE_D_MM = float(m.group(1))

m = require_match(
    B13C_TEXT,
    r"Continuous 300M shaft:\s*Ø?\s*([0-9.]+)\s*mm\s*x\s*([0-9.]+)\s*mm",
    "continuous shaft",
)
SHAFT_D_MM = float(m.group(1))
SHAFT_L_MM = float(m.group(2))

m = require_match(
    B13C_TEXT,
    r"Bronze sleeve,\s*each side:\s*Ø?\s*([0-9.]+)\s*/\s*Ø?\s*([0-9.]+)\s*x\s*([0-9.]+)\s*mm",
    "bronze sleeve",
)
SLEEVE_OD_MM = float(m.group(1))
SLEEVE_ID_MM = float(m.group(2))
SLEEVE_L_MM = float(m.group(3))

m = require_match(
    B13C_TEXT,
    r"Bronze flange,\s*each side:\s*Ø?\s*([0-9.]+)\s*/\s*Ø?\s*([0-9.]+)\s*x\s*([0-9.]+)\s*mm",
    "bronze flange",
)
FLANGE_OD_MM = float(m.group(1))
FLANGE_ID_MM = float(m.group(2))
FLANGE_T_MM = float(m.group(3))

m = require_match(
    B13C_TEXT,
    r"Full-Ø60 tangent-safe spotface plane:\s*X\s*=\s*±?\s*([0-9.]+)\s*mm",
    "spotface plane",
)
SPOTFACE_X_MM = float(m.group(1))

m = require_match(
    B13C_TEXT,
    r"Spotface depth at Y=0 from Ø106 tangent:\s*([0-9.]+)\s*mm",
    "spotface depth",
)
SPOTFACE_DEPTH_MM = float(m.group(1))

m = require_match(
    B13C_TEXT,
    r"Bushing sleeve inner ends:\s*X\s*=\s*±?\s*([0-9.]+)\s*mm",
    "bushing sleeve inner ends",
)
SLEEVE_INNER_X_MM = float(m.group(1))

m = require_match(
    B13C_TEXT,
    r"Unoccupied central Ø50 passage:\s*([0-9.]+)\s*mm",
    "central unoccupied passage",
)
CENTRAL_GAP_MM = float(m.group(1))

m = require_match(
    B13C_TEXT,
    r"Shaft-to-7075 radial clearance there:\s*([0-9.]+)\s*mm",
    "shaft-to-7075 radial clearance",
)
SHAFT_HEAD_RADIAL_CLEARANCE_MM = float(m.group(1))


# B13B V0.3 sizing source, if present.
def optional_float(text, pattern):
    m = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
    return float(m.group(1)) if m else None


SRC_SHAFT_D_MM = optional_float(
    B13B_V03_TEXT,
    r"Shaft\s*/\s*bushing nominal ID:\s*([0-9.]+)\s*mm",
)
SRC_SLEEVE_OD_MM = optional_float(
    B13B_V03_TEXT,
    r"Sleeve OD:\s*([0-9.]+)\s*mm",
)
SRC_SLEEVE_L_MM = optional_float(
    B13B_V03_TEXT,
    r"Sleeve length each side:\s*([0-9.]+)\s*mm",
)
SRC_FLANGE_OD_MM = optional_float(
    B13B_V03_TEXT,
    r"Flange OD:\s*([0-9.]+)\s*mm",
)
SRC_FLANGE_T_MM = optional_float(
    B13B_V03_TEXT,
    r"Flange thickness:\s*([0-9.]+)\s*mm",
)


# =============================================================================
# 3. DIMENSIONAL CONSISTENCY CHECKS
# =============================================================================

checks = []

def add_check(name, actual, expected, units="mm", source="", note=""):
    err = None if expected is None else actual - expected
    passed = None if expected is None else abs(err) <= ABS_TOL_MM

    checks.append({
        "check": name,
        "actual": actual,
        "expected": "" if expected is None else expected,
        "units": units,
        "difference": "" if err is None else err,
        "status": (
            "PASS"
            if passed is True
            else "FAIL"
            if passed is False
            else "SOURCE_NOT_RESOLVED"
        ),
        "source": source,
        "note": note,
    })


# Source-to-CAD checks where a prior sizing source is available.
add_check(
    "shaft_diameter_source_vs_B13C",
    SHAFT_D_MM,
    SRC_SHAFT_D_MM,
    source=str(B13B_V03_SUMMARY or ""),
)
add_check(
    "sleeve_OD_source_vs_B13C",
    SLEEVE_OD_MM,
    SRC_SLEEVE_OD_MM,
    source=str(B13B_V03_SUMMARY or ""),
)
add_check(
    "sleeve_length_source_vs_B13C",
    SLEEVE_L_MM,
    SRC_SLEEVE_L_MM,
    source=str(B13B_V03_SUMMARY or ""),
)
add_check(
    "flange_OD_source_vs_B13C",
    FLANGE_OD_MM,
    SRC_FLANGE_OD_MM,
    source=str(B13B_V03_SUMMARY or ""),
)
add_check(
    "flange_thickness_source_vs_B13C",
    FLANGE_T_MM,
    SRC_FLANGE_T_MM,
    source=str(B13B_V03_SUMMARY or ""),
)

# Internal interface consistency.
add_check(
    "sleeve_ID_matches_shaft_diameter",
    SLEEVE_ID_MM,
    SHAFT_D_MM,
    note="Nominally coincident bronze/shaft contact surface.",
)
add_check(
    "flange_ID_matches_shaft_diameter",
    FLANGE_ID_MM,
    SHAFT_D_MM,
    note="Nominal flange bore follows shaft diameter.",
)
add_check(
    "passage_diameter_matches_sleeve_OD",
    PASSAGE_D_MM,
    SLEEVE_OD_MM,
    note="Ø50 relief carries the bronze sleeve OD and prevents direct shaft/head contact.",
)

# Reconstruct the curved-head spotface geometry independently.
R_MM = BOSS_D_MM / 2.0
EXPECTED_SPOTFACE_X_MM = math.sqrt(
    R_MM**2 - (FLANGE_OD_MM/2.0)**2
)
EXPECTED_SPOTFACE_DEPTH_MM = R_MM - EXPECTED_SPOTFACE_X_MM
EXPECTED_INNER_END_MM = EXPECTED_SPOTFACE_X_MM - SLEEVE_L_MM
EXPECTED_CENTRAL_GAP_MM = 2.0 * EXPECTED_INNER_END_MM
EXPECTED_SHAFT_CLEARANCE_MM = (
    PASSAGE_D_MM - SHAFT_D_MM
) / 2.0

add_check(
    "spotface_plane_geometry",
    SPOTFACE_X_MM,
    EXPECTED_SPOTFACE_X_MM,
    note="Recomputed from Ø106 cylindrical head and Ø60 spotface/flange envelope.",
)
add_check(
    "spotface_depth_geometry",
    SPOTFACE_DEPTH_MM,
    EXPECTED_SPOTFACE_DEPTH_MM,
    note="Recomputed from head radius minus tangent-safe spotface plane.",
)
add_check(
    "sleeve_inner_end_geometry",
    SLEEVE_INNER_X_MM,
    EXPECTED_INNER_END_MM,
    note="Spotface plane minus 30 mm sleeve length.",
)
add_check(
    "central_unoccupied_gap_geometry",
    CENTRAL_GAP_MM,
    EXPECTED_CENTRAL_GAP_MM,
    note="Twice the positive inner-end station.",
)
add_check(
    "shaft_to_head_radial_clearance",
    SHAFT_HEAD_RADIAL_CLEARANCE_MM,
    EXPECTED_SHAFT_CLEARANCE_MM,
    note="(Ø50 passage - Ø38 shaft)/2.",
)

# Geometry sanity checks that do not require another source.
add_check(
    "shaft_length_from_validation_bbox",
    SHAFT_L_MM,
    175.0,
    note="B13C validation explicitly reports a 175 mm continuous shaft.",
)


# =============================================================================
# 4. TRACEABILITY MATRIX
# =============================================================================

def exists(path):
    return path is not None and path.exists()


def status(calc, geom, open_detail=False):
    if open_detail:
        return "OPEN_NOT_FROZEN"
    if calc and geom:
        return "CALC_AND_GEOMETRY_VERIFIED"
    if geom and not calc:
        return "GEOMETRY_VERIFIED_SOURCE_REVIEW"
    if calc and not geom:
        return "CALC_ONLY_NOT_GEOMETRY_VERIFIED"
    return "REVIEW_REQUIRED"


matrix = []

def add_feature(
    feature,
    structural_significance,
    calc_sources,
    geometry_verified,
    geometry_evidence,
    classification,
    note,
):
    calc_sources = [p for p in calc_sources if exists(p)]
    calc_present = bool(calc_sources)

    matrix.append({
        "feature": feature,
        "structural_significance": structural_significance,
        "calculation_source_present": calc_present,
        "calculation_sources": " | ".join(str(p.relative_to(HERE)) for p in calc_sources),
        "geometry_verified": geometry_verified,
        "geometry_evidence": geometry_evidence,
        "classification": classification,
        "status": status(
            calc_present,
            geometry_verified,
            open_detail=(classification == "OPEN_DETAIL"),
        ),
        "note": note,
    })


add_feature(
    "upper_head_outer_boss_106x78",
    "HIGH",
    [B11_PY, B11_STRUCTURED, B11_SUMMARY],
    True,
    f"Ø{BOSS_D_MM:.3f} x {BOSS_H_MM:.3f} mm in B13C validation",
    "MODELED_WORKING",
    "Existing upper-head structural envelope; later B14B reinforcement remains separate.",
)

add_feature(
    "continuous_300M_trunnion_shaft_38x175",
    "HIGH",
    [B2_PY, B2_STRUCTURED, B2_SUMMARY, B13B_V03_PY, B13B_V03_SUMMARY],
    True,
    f"Ø{SHAFT_D_MM:.3f} x {SHAFT_L_MM:.3f} mm in B13C validation",
    "MODELED_WORKING",
    "Diameter is source-traceable; total length is geometry/package-defined and must remain tied to airframe bearing package.",
)

add_feature(
    "bronze_sleeves_50_38x30",
    "HIGH",
    [B13B_BASE_PY, B13B_V02R1_PY, B13B_V03_PY, B13B_V03_SUMMARY],
    True,
    f"Ø{SLEEVE_OD_MM:.3f}/Ø{SLEEVE_ID_MM:.3f} x {SLEEVE_L_MM:.3f} mm each side",
    "MODELED_WORKING",
    "Radial load-transfer interface is physically represented.",
)

add_feature(
    "bronze_flanges_60_38x3",
    "HIGH",
    [B13B_V03_PY, B13B_V03_SUMMARY],
    True,
    f"Ø{FLANGE_OD_MM:.3f}/Ø{FLANGE_ID_MM:.3f} x {FLANGE_T_MM:.3f} mm each side",
    "MODELED_WORKING",
    "V0.3 explicitly treated thickness as provisional CAD/FEA packaging geometry, not a final fatigue/detail-design freeze.",
)

add_feature(
    "central_relief_passage_50",
    "HIGH",
    [B13B_V04_PY, B13B_V03_PY, B13B_V03_SUMMARY],
    True,
    f"Ø{PASSAGE_D_MM:.3f} mm through",
    "MODELED_WORKING",
    "Geometry prevents direct 300M shaft / 7075 head contact in the central region.",
)

add_feature(
    "curved_head_spotfaces_for_flange",
    "MEDIUM",
    [B13B_V03_PY, B13B_V03_SUMMARY],
    True,
    f"X=±{SPOTFACE_X_MM:.6f} mm, depth={SPOTFACE_DEPTH_MM:.6f} mm",
    "GEOMETRY_DERIVED",
    "These are geometry-derived corrections and do not require their own structural sizing calculation.",
)

# Retention architecture: intentionally distinguish architecture from physical hardware.
retention_keywords = [
    "shoulder",
    "thrust washer",
    "retention",
    "retainer",
    "collar",
    "locknut",
    "snap ring",
]
retention_mentions = [
    k for k in retention_keywords
    if k in RETENTION_TEXT.lower()
]

retention_geometry_words = [
    "washer",
    "shoulder",
    "collar",
    "retainer",
    "locknut",
]
retention_in_b13c = [
    k for k in retention_geometry_words
    if k in B13C_TEXT.lower()
]

add_feature(
    "shaft_axial_retention_shoulder_washer_collar_hardware",
    "HIGH",
    [RETENTION_PY, RETENTION_STRUCTURED, RETENTION_SUMMARY, B13B_V03_PY, B13B_V03_SUMMARY],
    bool(retention_in_b13c),
    (
        "B13C validation explicitly contains retention hardware terms: "
        + ", ".join(retention_in_b13c)
        if retention_in_b13c
        else "B13C validation contains only head + shaft + two bushings; no separate retention hardware is geometry-verified."
    ),
    "OPEN_DETAIL",
    (
        "Architecture is documented"
        + (f" ({', '.join(retention_mentions)})" if retention_mentions else "")
        + ", but final shoulder/thrust-washer/collar/positive-retention geometry should NOT be treated as frozen until physically modeled and checked."
    ),
)

add_feature(
    "airframe_bearings_and_external_retention_package",
    "HIGH",
    [B2_PY, B2_STRUCTURED, B2_SUMMARY, RETENTION_PY, RETENTION_STRUCTURED, RETENTION_SUMMARY],
    False,
    "Not represented as separate bodies in the four-solid B13C geometry validation.",
    "OPEN_DETAIL",
    "Support/bearing geometry belongs to the airframe-side attachment package and must be verified before final assembly freeze.",
)

add_feature(
    "spotface_root_edge_fillet",
    "MEDIUM",
    [B13B_V03_PY, B13B_V03_SUMMARY],
    False,
    "B13C validation states the spotface root/edge is intentionally sharp.",
    "OPEN_DETAIL",
    "Local fillet/contact stress is intentionally deferred to detail design / FEA.",
)


# =============================================================================
# 5. OPEN ITEMS / GATE
# =============================================================================

dimension_failures = [
    r for r in checks if r["status"] == "FAIL"
]

source_review_checks = [
    r for r in checks if r["status"] == "SOURCE_NOT_RESOLVED"
]

open_features = [
    r for r in matrix if r["classification"] == "OPEN_DETAIL"
]

# Strong gate:
# - no dimensional contradictions allowed
# - open details are acceptable only if explicitly labeled open
if dimension_failures:
    gate = "FAIL_DIMENSION_CONTRADICTION"
else:
    gate = "PASS_WITH_EXPLICIT_OPEN_DETAILS"

open_rows = []
for r in open_features:
    open_rows.append({
        "feature": r["feature"],
        "status": "OPEN_NOT_FROZEN",
        "reason": r["note"],
        "required_closure": (
            "Create/verify physical geometry and run the appropriate local structural/"
            "contact/packaging check before final assembly freeze."
        ),
    })

if source_review_checks:
    for r in source_review_checks:
        open_rows.append({
            "feature": r["check"],
            "status": "SOURCE_REVIEW",
            "reason": (
                "B13C geometry is present, but the expected prior sizing summary "
                "was not resolved automatically."
            ),
            "required_closure": (
                "Confirm the prior source filename/location; do not alter the CAD "
                "dimension unless a real conflict is found."
            ),
        })


# =============================================================================
# 6. WRITE OUTPUTS
# =============================================================================

def write_rows(path, rows):
    if not rows:
        rows = [{"status": "NONE"}]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


write_rows(OUT_MATRIX, matrix)
write_rows(OUT_CHECKS, checks)
write_rows(OUT_OPEN, open_rows)


# =============================================================================
# 7. SUMMARY
# =============================================================================

pass_count = sum(1 for r in checks if r["status"] == "PASS")
fail_count = sum(1 for r in checks if r["status"] == "FAIL")
review_count = sum(1 for r in checks if r["status"] == "SOURCE_NOT_RESOLVED")

lines = []
emit = lines.append

emit("=" * 132)
emit(" PHASE 2E3 — LEGACY UPPER-ATTACHMENT GEOMETRY / TRACEABILITY AUDIT V0.1")
emit("=" * 132)
emit("")
emit("PRIMARY SOURCES")
emit("-" * 132)
emit(f"B13C geometry validation: {B13C_VALIDATION}")
emit(f"B13B V0.3 summary:        {B13B_V03_SUMMARY or 'NOT FOUND'}")
emit(f"B13B V0.3 Python:         {B13B_V03_PY or 'NOT FOUND'}")
emit(f"B10A retention Python:    {RETENTION_PY or 'NOT FOUND'}")
emit(f"B11 local-screen Python:  {B11_PY or 'NOT FOUND'}")
emit(f"B2 trunnion Python:       {B2_PY or 'NOT FOUND'}")
emit("")
emit("B13C ACTUAL GEOMETRY")
emit("-" * 132)
emit(f"Upper-head boss:          Ø{BOSS_D_MM:.3f} x {BOSS_H_MM:.3f} mm high")
emit(f"Head passage:             Ø{PASSAGE_D_MM:.3f} mm through")
emit(f"Continuous shaft:         Ø{SHAFT_D_MM:.3f} x {SHAFT_L_MM:.3f} mm")
emit(f"Bronze sleeve, each side: Ø{SLEEVE_OD_MM:.3f}/Ø{SLEEVE_ID_MM:.3f} x {SLEEVE_L_MM:.3f} mm")
emit(f"Bronze flange, each side: Ø{FLANGE_OD_MM:.3f}/Ø{FLANGE_ID_MM:.3f} x {FLANGE_T_MM:.3f} mm")
emit("")
emit("DIMENSIONAL CONSISTENCY")
emit("-" * 132)
for r in checks:
    expected = r["expected"]
    expected_s = (
        "N/A"
        if expected == ""
        else f"{float(expected):.6f}"
    )
    actual_s = f"{float(r['actual']):.6f}"
    emit(
        f"{r['status']:20s} {r['check']:42s} "
        f"actual={actual_s:>12s} expected={expected_s:>12s} {r['units']}"
    )
emit("")
emit(f"PASS checks:              {pass_count}")
emit(f"FAIL checks:              {fail_count}")
emit(f"Source-review checks:     {review_count}")
emit("")
emit("FEATURE TRACEABILITY")
emit("-" * 132)
for r in matrix:
    emit(
        f"{r['status']:36s} {r['feature']}"
    )
emit("")
emit("RETENTION / COLLAR-TYPE HARDWARE INTERPRETATION")
emit("-" * 132)
if exists(RETENTION_PY):
    emit("Retention architecture source exists.")
else:
    emit("Retention architecture source was not found automatically.")
if retention_mentions:
    emit("Retention-source terms found: " + ", ".join(retention_mentions))
if retention_in_b13c:
    emit("B13C validation appears to include retention hardware terminology.")
else:
    emit("B13C validation verifies only four bodies: head, shaft, left bushing, right bushing.")
    emit("Therefore shoulder / thrust-washer / collar / positive-retention hardware must remain OPEN, not silently frozen.")
emit("")
emit("GATE")
emit("-" * 132)
emit(gate)
if gate == "PASS_WITH_EXPLICIT_OPEN_DETAILS":
    emit(
        "No contradictory legacy dimensions were found in the checks that could be resolved."
    )
    emit(
        "The modeled shaft/bushing/flange/relief geometry is acceptable to carry forward."
    )
    emit(
        "Unmodeled retention and airframe-side hardware is explicitly OPEN and must be closed before final assembly freeze."
    )
else:
    emit(
        "At least one legacy CAD dimension conflicts with its calculation/geometry reconstruction. Resolve before B14B-9."
    )
emit("")
emit("OUTPUTS")
emit("-" * 132)
for p in [OUT_MATRIX, OUT_CHECKS, OUT_OPEN, OUT_SUMMARY]:
    emit(str(p))
emit("=" * 132)

report = "\n".join(lines)
OUT_SUMMARY.write_text(report, encoding="utf-8")
print(report)
