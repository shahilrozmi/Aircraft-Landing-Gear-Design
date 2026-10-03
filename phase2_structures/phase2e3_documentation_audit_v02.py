"""
Landing_Gear_Design_Project
PHASE 2E3 — CALCULATION / DOCUMENTATION AUDIT V0.2

This is a stricter but smarter replacement for V0.1.

Changes from V0.1
-----------------
1) Separates ENGINEERING CALCULATION scripts from MODEL/GEOMETRY BUILDERS.
2) Does not treat wildcard/glob input patterns as missing output files.
3) Recognizes engineering artifacts such as STEP/STP/IGES/INP/DAT/WBPJ as builder outputs.
4) Allows explicit supersession of legacy scripts.
5) Keeps the B14A source/documentation gate.

Project rule
------------
Every engineering CALCULATION step should retain:
    - Python source
    - machine-readable result (CSV/JSON/XLSX/NPZ/NPY)
    - human-readable summary (TXT/MD)

MODEL/GEOMETRY BUILDERS should retain:
    - Python source
    - generated engineering artifact where applicable
    - validation/summary TXT/MD

Run from phase2_structures. Outputs:
    phase2e3_documentation_audit_v02.csv
    phase2e3_documentation_audit_v02.txt
"""

from __future__ import annotations

import ast
import csv
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple


HERE = Path(__file__).resolve().parent
SELF = Path(__file__).name

STRUCTURED_EXTS = {".csv", ".json", ".xlsx", ".xls", ".npz", ".npy"}
NARRATIVE_EXTS = {".txt", ".md"}
BUILDER_ARTIFACT_EXTS = {
    ".step", ".stp", ".iges", ".igs", ".inp", ".dat", ".mac",
    ".wbpj", ".mechdb", ".cdb"
}
ALL_OUTPUT_EXTS = STRUCTURED_EXTS | NARRATIVE_EXTS | BUILDER_ARTIFACT_EXTS

SKIP_DIR_NAMES = {
    ".git", ".idea", ".vscode", "__pycache__", ".pytest_cache",
    "venv", ".venv", "env", "site-packages"
}

# This older traceability script has been superseded by the frozen V1 update chain.
SUPERSEDED_SCRIPTS = {
    "phase2_traceability_audit_v04.py":
        "phase2_traceability_v1_freeze_update.py",
}

B14A_MARKERS = ("SUP_BRACE_RX",)


@dataclass
class AuditRow:
    script: str
    role: str
    status: str
    structured_output: bool
    narrative_output: bool
    builder_artifact: bool
    declared_existing: str
    declared_missing: str
    inferred_artifacts: str
    superseded_by: str
    notes: str


def skipped(p: Path) -> bool:
    return any(part in SKIP_DIR_NAMES for part in p.parts)


def role_for(p: Path) -> str:
    n = p.name.lower()
    builder_tokens = (
        "generate_integrated_model",
        "generate_primary106_submodel",
        "build_geometry",
        "portable",
    )
    if any(t in n for t in builder_tokens):
        return "BUILDER"
    return "CALCULATION"


def assignments(tree: ast.AST) -> Dict[str, ast.AST]:
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    out[t.id] = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            out[node.target.id] = node.value
    return out


def resolve_expr(node: ast.AST, assn: Dict[str, ast.AST], depth=0) -> Optional[str]:
    if depth > 10:
        return None

    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value

    if isinstance(node, ast.Name):
        if node.id.lower() in {"here", "root", "base_dir"}:
            return "."
        if node.id in assn:
            return resolve_expr(assn[node.id], assn, depth + 1)
        return None

    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        a = resolve_expr(node.left, assn, depth + 1)
        b = resolve_expr(node.right, assn, depth + 1)
        if a is not None and b is not None:
            return b if a == "." else str(Path(a) / b)
        return None

    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in {"Path", "str"} and node.args:
            return resolve_expr(node.args[0], assn, depth + 1)
        if isinstance(node.func, ast.Attribute):
            return resolve_expr(node.func.value, assn, depth + 1)

    if isinstance(node, ast.Attribute):
        return resolve_expr(node.value, assn, depth + 1)

    return None


def actual_write_outputs(p: Path, source: str) -> Set[Path]:
    """Only record paths used by actual write calls. No loose literal fallback."""
    out: Set[Path] = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return out

    assn = assignments(tree)

    def add(node: ast.AST):
        raw = resolve_expr(node, assn)
        if not raw:
            return
        # Glob/wildcard expressions are input discovery patterns, never outputs.
        if any(ch in raw for ch in "*?[]"):
            return
        if Path(raw).suffix.lower() not in ALL_OUTPUT_EXTS:
            return
        q = Path(raw)
        if not q.is_absolute():
            q = (p.parent / q).resolve()
        out.add(q)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        if isinstance(node.func, ast.Attribute):
            method = node.func.attr
            if method in {
                "to_csv", "to_json", "to_excel",
                "write_text", "write_bytes", "savefig", "savetxt"
            } and node.args:
                add(node.args[0])

            if method == "open":
                mode = ""
                if node.args and isinstance(node.args[0], ast.Constant):
                    mode = str(node.args[0].value)
                for kw in node.keywords:
                    if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                        mode = str(kw.value.value)
                if any(c in mode for c in "wax"):
                    add(node.func.value)

        elif isinstance(node.func, ast.Name) and node.func.id == "open" and node.args:
            mode = ""
            if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                mode = str(node.args[1].value)
            for kw in node.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                    mode = str(kw.value.value)
            if any(c in mode for c in "wax"):
                add(node.args[0])

    return out


def infer_nearby(p: Path) -> List[Path]:
    stem = p.stem.lower()
    tokens = [x for x in re.split(r"[_\-\s]+", stem) if len(x) >= 3]
    important = set(tokens[-4:] + [x for x in tokens if x.startswith("phase")])

    candidates = []
    for q in p.parent.iterdir():
        if not q.is_file() or q.suffix.lower() not in ALL_OUTPUT_EXTS:
            continue
        score = sum(1 for t in important if t in q.stem.lower())
        if score >= 2:
            candidates.append((score, q.resolve()))

    candidates.sort(key=lambda z: (-z[0], z[1].name.lower()))
    return [q for _, q in candidates[:12]]


def fmt(paths: Iterable[Path]) -> str:
    vals = []
    for p in sorted(set(paths), key=lambda x: str(x).lower()):
        try:
            vals.append(str(p.relative_to(HERE)))
        except ValueError:
            vals.append(str(p))
    return " | ".join(vals)


def classify(p: Path) -> AuditRow:
    source = p.read_text(encoding="utf-8", errors="ignore")
    role = role_for(p)

    if p.name in SUPERSEDED_SCRIPTS:
        successor = HERE / SUPERSEDED_SCRIPTS[p.name]
        return AuditRow(
            script=str(p.relative_to(HERE)),
            role=role,
            status="SUPERSEDED" if successor.exists() else "SUPERSESSION_MISSING",
            structured_output=False,
            narrative_output=False,
            builder_artifact=False,
            declared_existing="",
            declared_missing="",
            inferred_artifacts="",
            superseded_by=SUPERSEDED_SCRIPTS[p.name],
            notes="Legacy script intentionally superseded; do not repair old filenames."
                  if successor.exists()
                  else "Declared successor is missing."
        )

    declared = actual_write_outputs(p, source)
    existing = {q for q in declared if q.exists()}
    missing = declared - existing
    nearby = infer_nearby(p)
    all_present = set(existing) | set(nearby)

    structured = any(q.suffix.lower() in STRUCTURED_EXTS for q in all_present)
    narrative = any(q.suffix.lower() in NARRATIVE_EXTS for q in all_present)
    builder_artifact = any(q.suffix.lower() in BUILDER_ARTIFACT_EXTS for q in all_present)

    if missing:
        status = "DECLARED_OUTPUT_MISSING"
        notes = "A path used by an actual write call is missing on disk."
    elif role == "CALCULATION":
        if structured and narrative:
            status = "FULL"
            notes = "Python + structured result + narrative summary present."
        elif structured and not narrative:
            status = "NEEDS_SUMMARY"
            notes = "Structured calculation output exists; backfill a TXT/MD summary."
        elif narrative and not structured:
            status = "NEEDS_STRUCTURED_RESULT"
            notes = "Narrative exists but no structured calculation result was found."
        else:
            status = "CALCULATION_UNDOCUMENTED"
            notes = "Calculation script lacks the required persisted result pair."
    else:
        if narrative and builder_artifact:
            status = "FULL_BUILDER"
            notes = "Builder source + engineering artifact + validation/summary present."
        elif narrative:
            status = "BUILDER_REVIEW"
            notes = ("Narrative exists. No STEP/IGES/INP/DAT/WBPJ artifact was auto-detected; "
                     "this may still be valid if the artifact is written by an external API.")
        else:
            status = "BUILDER_NEEDS_SUMMARY"
            notes = "Builder has no persisted TXT/MD validation summary."

    return AuditRow(
        script=str(p.relative_to(HERE)),
        role=role,
        status=status,
        structured_output=structured,
        narrative_output=narrative,
        builder_artifact=builder_artifact,
        declared_existing=fmt(existing),
        declared_missing=fmt(missing),
        inferred_artifacts=fmt(nearby),
        superseded_by="",
        notes=notes,
    )


def discover() -> List[Path]:
    out = []
    for p in HERE.rglob("*.py"):
        if p.name == SELF or skipped(p.relative_to(HERE)):
            continue
        if p.name.lower().startswith("phase"):
            out.append(p.resolve())
    return sorted(out, key=lambda q: str(q).lower())


def b14a_gate() -> Tuple[str, List[Path]]:
    files = [
        p for p in HERE.rglob("*")
        if p.is_file() and not skipped(p.relative_to(HERE))
    ]
    candidates = [p for p in files if "b14a" in p.name.lower()]

    # Also discover files that explicitly contain the ANSYS brace support name.
    for p in files:
        if p.suffix.lower() not in {".py", ".csv", ".txt", ".md", ".json"}:
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if any(m in txt for m in B14A_MARKERS):
            candidates.append(p)

    candidates = sorted(set(candidates), key=lambda q: str(q).lower())
    py = any(p.suffix.lower() == ".py" for p in candidates)
    structured = any(p.suffix.lower() in STRUCTURED_EXTS for p in candidates)
    narrative = any(p.suffix.lower() in NARRATIVE_EXTS for p in candidates)

    if py and structured and narrative:
        return "PASS", candidates
    return "REVIEW_REQUIRED", candidates


def main():
    rows = [classify(p) for p in discover()]
    gate, b14a_files = b14a_gate()

    csv_path = HERE / "phase2e3_documentation_audit_v02.csv"
    txt_path = HERE / "phase2e3_documentation_audit_v02.txt"

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(asdict(rows[0]).keys()))
        w.writeheader()
        for r in rows:
            w.writerow(asdict(r))

    counts: Dict[str, int] = {}
    for r in rows:
        counts[r.status] = counts.get(r.status, 0) + 1

    lines = []
    emit = lines.append
    emit("=" * 122)
    emit(" LANDING GEAR PROJECT — CALCULATION / DOCUMENTATION AUDIT V0.2")
    emit("=" * 122)
    emit(f"Audit root: {HERE}")
    emit(f"Python phase scripts audited: {len(rows)}")
    emit("")
    emit("STATUS COUNTS")
    emit("-" * 122)
    for k in sorted(counts):
        emit(f"{k:30s}: {counts[k]:4d}")
    emit("")
    emit("NON-FULL ITEMS")
    emit("-" * 122)
    for r in rows:
        if r.status not in {"FULL", "FULL_BUILDER", "SUPERSEDED"}:
            emit(f"[{r.status}] {r.script}")
            emit(f"  {r.notes}")
            if r.declared_missing:
                emit(f"  actual missing write target(s): {r.declared_missing}")
    emit("")
    emit("B14A DOCUMENTATION GATE")
    emit("-" * 122)
    emit(f"Status: {gate}")
    if b14a_files:
        for p in b14a_files:
            emit(f"  {p.relative_to(HERE)}")
    else:
        emit("  No B14A source/result/summary artifact detected.")
    emit("")
    emit("Interpretation:")
    emit("- A calculation should not be frozen from chat-only arithmetic.")
    emit("- Model/geometry generators are not penalized for lacking CSV if their engineering artifact")
    emit("  and validation summary exist.")
    emit("- Wildcard input search patterns are not treated as declared output filenames.")
    emit("=" * 122)

    report = "\n".join(lines)
    txt_path.write_text(report, encoding="utf-8")
    print(report)
    print(f"\nCSV: {csv_path}")
    print(f"TXT: {txt_path}")


if __name__ == "__main__":
    main()
