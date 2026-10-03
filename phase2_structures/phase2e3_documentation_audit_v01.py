"""
Landing_Gear_Design_Project
PHASE 2E3 — CALCULATION / DOCUMENTATION AUDIT V0.1

PURPOSE
-------
Audit the local Landing_Gear_Project Python calculation chain so we can verify that
engineering calculations are not living only in chat or console output.

The audit checks every phase*.py script below this file's directory and reports:
    - Python source exists
    - persisted machine-readable output exists (CSV/JSON/XLSX/NPZ/NPY)
    - persisted human-readable summary exists (TXT/MD)
    - output files declared by the source but currently missing
    - scripts that appear to print results but do not persist a narrative summary
    - explicit B14A source/output presence and frozen-result markers

IMPORTANT
---------
This audit does NOT validate the engineering mathematics. It validates calculation
traceability/documentation on disk.

Recommended project rule going forward:
    Every engineering calculation step should have:
        1) a Python source file,
        2) at least one machine-readable result artifact, and
        3) a human-readable TXT/MD summary.

Run this script from the phase2_structures folder (or place it there and run it).
It writes:
    phase2e3_documentation_audit_v01.csv
    phase2e3_documentation_audit_v01.txt
"""

from __future__ import annotations

import ast
import csv
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple


HERE = Path(__file__).resolve().parent
AUDIT_SCRIPT_NAME = Path(__file__).name

STRUCTURED_EXTS = {".csv", ".json", ".xlsx", ".xls", ".npz", ".npy"}
NARRATIVE_EXTS = {".txt", ".md"}
OTHER_RESULT_EXTS = {".png", ".pdf"}
ALL_RESULT_EXTS = STRUCTURED_EXTS | NARRATIVE_EXTS | OTHER_RESULT_EXTS

SKIP_DIR_NAMES = {
    ".git", ".idea", ".vscode", "__pycache__", ".pytest_cache",
    "venv", ".venv", "env", "site-packages"
}

# Frozen B14A markers supplied by the validated B14A step.
# These are used ONLY as an audit cross-check; they are not used to generate B14B loads.
B14A_MARKERS = {
    "SUP_BRACE_RX": None,
    "16.856": "governing combined ultimate Mx [kN*m]",
    "3.9128": "force-only contribution [kN*m]",
    "12.943": "moment-only contribution [kN*m]",
}


@dataclass
class ScriptAudit:
    script: str
    phase_tag: str
    declared_outputs: str
    existing_declared_outputs: str
    missing_declared_outputs: str
    inferred_sibling_outputs: str
    structured_output_exists: bool
    narrative_output_exists: bool
    prints_results: bool
    status: str
    notes: str


def is_skipped(path: Path) -> bool:
    return any(part in SKIP_DIR_NAMES for part in path.parts)


def phase_tag_from_name(name: str) -> str:
    stem = Path(name).stem.lower()
    m = re.search(r"(phase\d+(?:e\d+)?(?:[_-]?b\d+[a-z]?)?)", stem)
    if m:
        return m.group(1).upper().replace("_", "-")
    m = re.search(r"(phase\d+[a-z]?)", stem)
    if m:
        return m.group(1).upper()
    return "UNCLASSIFIED"


def normalize_candidate_path(raw: str, script_path: Path) -> Path:
    p = Path(raw)
    if p.is_absolute():
        return p
    return (script_path.parent / p).resolve()


def path_string_from_ast(
    node: ast.AST,
    assignments: Dict[str, ast.AST],
    script_path: Path,
    _depth: int = 0,
) -> Optional[str]:
    """Resolve simple path expressions used by this project."""
    if _depth > 8:
        return None

    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value

    if isinstance(node, ast.Name):
        if node.id in {"here", "HERE"}:
            return "."
        rhs = assignments.get(node.id)
        if rhs is not None:
            return path_string_from_ast(rhs, assignments, script_path, _depth + 1)
        return None

    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left = path_string_from_ast(node.left, assignments, script_path, _depth + 1)
        right = path_string_from_ast(node.right, assignments, script_path, _depth + 1)
        if left is not None and right is not None:
            if left == ".":
                return right
            return str(Path(left) / right)
        return None

    if isinstance(node, ast.Call):
        # Path("file"), str(...)
        if isinstance(node.func, ast.Name) and node.func.id in {"Path", "str"} and node.args:
            return path_string_from_ast(node.args[0], assignments, script_path, _depth + 1)

        # Something.resolve(), .parent etc. are usually base-directory plumbing.
        if isinstance(node.func, ast.Attribute):
            base = path_string_from_ast(node.func.value, assignments, script_path, _depth + 1)
            if base is not None:
                return base

    if isinstance(node, ast.Attribute):
        # HERE / ..., or a variable's .parent; retain the base if resolvable.
        return path_string_from_ast(node.value, assignments, script_path, _depth + 1)

    return None


def collect_assignments(tree: ast.AST) -> Dict[str, ast.AST]:
    out: Dict[str, ast.AST] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    out[target.id] = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            out[node.target.id] = node.value
    return out


def add_output_from_node(
    node: ast.AST,
    assignments: Dict[str, ast.AST],
    script_path: Path,
    outputs: Set[Path],
) -> None:
    raw = path_string_from_ast(node, assignments, script_path)
    if not raw:
        return
    suffix = Path(raw).suffix.lower()
    if suffix in ALL_RESULT_EXTS:
        outputs.add(normalize_candidate_path(raw, script_path))


def declared_outputs_from_ast(script_path: Path, source: str) -> Set[Path]:
    outputs: Set[Path] = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return outputs

    assignments = collect_assignments(tree)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        # object.to_csv(path), to_json, to_excel, write_text, write_bytes, savefig
        if isinstance(node.func, ast.Attribute):
            method = node.func.attr
            if method in {
                "to_csv", "to_json", "to_excel",
                "write_text", "write_bytes", "savefig",
                "savetxt"
            } and node.args:
                add_output_from_node(node.args[0], assignments, script_path, outputs)

            # Path(...).open("w") or output_path.open("w")
            if method == "open":
                mode = None
                if node.args and isinstance(node.args[0], ast.Constant):
                    mode = node.args[0].value
                for kw in node.keywords:
                    if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                        mode = kw.value.value
                if mode and any(ch in str(mode) for ch in "wax"):
                    add_output_from_node(node.func.value, assignments, script_path, outputs)

        # built-in open(path, "w")
        elif isinstance(node.func, ast.Name) and node.func.id == "open" and node.args:
            mode = "r"
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                mode = str(node.args[1].value)
            for kw in node.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                    mode = str(kw.value.value)
            if any(ch in mode for ch in "wax"):
                add_output_from_node(node.args[0], assignments, script_path, outputs)

    # Fallback: capture obvious output/result/summary filename literals near write verbs.
    lines = source.splitlines()
    literal_re = re.compile(r"""["']([^"']+\.(?:csv|txt|json|md|xlsx|xls|npz|npy|png|pdf))["']""", re.I)
    write_words = ("output", "summary", "report", "result", "to_csv", "write_text", "savefig", "open(")
    for i, line in enumerate(lines):
        window = " ".join(lines[max(0, i - 2): min(len(lines), i + 3)]).lower()
        if not any(w in window for w in write_words):
            continue
        for m in literal_re.finditer(line):
            outputs.add(normalize_candidate_path(m.group(1), script_path))

    return outputs


def inferred_sibling_outputs(script_path: Path) -> List[Path]:
    """
    Find likely output artifacts not discoverable by AST because their paths are built
    dynamically. Uses filename-token overlap, not engineering-value matching.
    """
    stem = script_path.stem.lower()
    tokens = [t for t in re.split(r"[_\-\s]+", stem) if len(t) >= 3]
    phase_tokens = [t for t in tokens if t.startswith("phase") or re.fullmatch(r"b\d+[a-z]?", t)]
    important = set(phase_tokens + tokens[-3:])

    candidates: List[Tuple[int, Path]] = []
    for p in script_path.parent.iterdir():
        if not p.is_file() or p.suffix.lower() not in ALL_RESULT_EXTS:
            continue
        low = p.stem.lower()
        score = sum(1 for t in important if t and t in low)
        if score >= 2:
            candidates.append((score, p.resolve()))

    candidates.sort(key=lambda x: (-x[0], x[1].name.lower()))
    return [p for _, p in candidates]


def join_paths(paths: Iterable[Path], base: Path) -> str:
    items = []
    for p in sorted(set(paths), key=lambda q: str(q).lower()):
        try:
            items.append(str(p.relative_to(base)))
        except ValueError:
            items.append(str(p))
    return " | ".join(items)


def status_for(
    structured: bool,
    narrative: bool,
    declared_missing: bool,
    prints_results: bool,
) -> Tuple[str, str]:
    if declared_missing:
        return "DECLARED_MISSING", "At least one source-declared output file is missing."
    if structured and narrative:
        return "FULL", "Source + structured results + narrative summary present."
    if structured and not narrative:
        note = "Structured results exist, but no persisted TXT/MD summary was found."
        if prints_results:
            note += " Script prints results; console output may never have been saved."
        return "STRUCTURED_ONLY", note
    if narrative and not structured:
        return "NARRATIVE_ONLY", "Narrative summary exists, but no machine-readable result artifact was found."
    if prints_results:
        return "CONSOLE_ONLY", "Script prints results but no persisted structured/narrative artifact was found."
    return "CODE_ONLY", "No persisted result artifact was found."


def audit_script(script_path: Path) -> ScriptAudit:
    source = script_path.read_text(encoding="utf-8", errors="ignore")
    declared = declared_outputs_from_ast(script_path, source)
    existing_declared = {p for p in declared if p.exists()}
    missing_declared = declared - existing_declared

    inferred = inferred_sibling_outputs(script_path)
    all_existing = set(existing_declared) | set(inferred)

    structured = any(p.suffix.lower() in STRUCTURED_EXTS for p in all_existing)
    narrative = any(p.suffix.lower() in NARRATIVE_EXTS for p in all_existing)

    try:
        tree = ast.parse(source)
        prints_results = any(
            isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "print"
            for n in ast.walk(tree)
        )
    except SyntaxError:
        prints_results = "print(" in source

    status, notes = status_for(
        structured=structured,
        narrative=narrative,
        declared_missing=bool(missing_declared),
        prints_results=prints_results,
    )

    return ScriptAudit(
        script=str(script_path.relative_to(HERE)),
        phase_tag=phase_tag_from_name(script_path.name),
        declared_outputs=join_paths(declared, HERE),
        existing_declared_outputs=join_paths(existing_declared, HERE),
        missing_declared_outputs=join_paths(missing_declared, HERE),
        inferred_sibling_outputs=join_paths(inferred, HERE),
        structured_output_exists=structured,
        narrative_output_exists=narrative,
        prints_results=prints_results,
        status=status,
        notes=notes,
    )


def discover_phase_scripts() -> List[Path]:
    scripts = []
    for p in HERE.rglob("*.py"):
        if is_skipped(p.relative_to(HERE)):
            continue
        if p.name == AUDIT_SCRIPT_NAME:
            continue

        low = p.name.lower()
        # Keep the audit focused on engineering phase calculations.
        if low.startswith("phase") or "landing_gear" in low:
            scripts.append(p.resolve())

    return sorted(scripts, key=lambda p: str(p).lower())


def scan_b14a() -> Dict[str, object]:
    """
    Confirm that B14A exists locally and that its frozen result is documented.
    This is a documentation/source check, not a recalculation.
    """
    all_files = [
        p for p in HERE.rglob("*")
        if p.is_file()
        and not is_skipped(p.relative_to(HERE))
        and p.name != AUDIT_SCRIPT_NAME
    ]

    named = [p for p in all_files if "b14a" in p.name.lower()]

    # If naming differs, also include files whose text explicitly contains SUP_BRACE_RX.
    content_matches = []
    for p in all_files:
        if p.suffix.lower() not in {".py", ".csv", ".txt", ".md", ".json"}:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "SUP_BRACE_RX" in text:
            content_matches.append(p)

    candidates = sorted(set(named + content_matches), key=lambda p: str(p).lower())

    source_files = [p for p in candidates if p.suffix.lower() == ".py"]
    structured_files = [p for p in candidates if p.suffix.lower() in STRUCTURED_EXTS]
    narrative_files = [p for p in candidates if p.suffix.lower() in NARRATIVE_EXTS]

    marker_hits = {k: [] for k in B14A_MARKERS}
    for p in candidates:
        if p.suffix.lower() not in {".py", ".csv", ".txt", ".md", ".json"}:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for marker in B14A_MARKERS:
            if marker in text:
                marker_hits[marker].append(str(p.relative_to(HERE)))

    return {
        "candidate_files": candidates,
        "source_files": source_files,
        "structured_files": structured_files,
        "narrative_files": narrative_files,
        "marker_hits": marker_hits,
    }


def write_csv(rows: List[ScriptAudit], path: Path) -> None:
    fieldnames = list(asdict(rows[0]).keys()) if rows else [
        "script", "phase_tag", "declared_outputs", "existing_declared_outputs",
        "missing_declared_outputs", "inferred_sibling_outputs",
        "structured_output_exists", "narrative_output_exists",
        "prints_results", "status", "notes"
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def make_report(rows: List[ScriptAudit], b14a: Dict[str, object]) -> str:
    counts: Dict[str, int] = {}
    for r in rows:
        counts[r.status] = counts.get(r.status, 0) + 1

    lines: List[str] = []
    emit = lines.append

    emit("=" * 124)
    emit(" LANDING GEAR PROJECT — PYTHON CALCULATION / DOCUMENTATION AUDIT V0.1")
    emit("=" * 124)
    emit("")
    emit(f"Audit root: {HERE}")
    emit(f"Engineering Python scripts audited: {len(rows)}")
    emit("")
    emit("PROJECT DOCUMENTATION RULE")
    emit("-" * 124)
    emit("Every engineering calculation step should retain:")
    emit("  1) Python source")
    emit("  2) machine-readable results (CSV/JSON/XLSX/NPZ/NPY)")
    emit("  3) human-readable summary (TXT/MD)")
    emit("Console-only calculations are NOT treated as fully documented.")
    emit("")

    emit("STATUS COUNTS")
    emit("-" * 124)
    for status in [
        "FULL", "STRUCTURED_ONLY", "NARRATIVE_ONLY",
        "CONSOLE_ONLY", "CODE_ONLY", "DECLARED_MISSING"
    ]:
        emit(f"{status:22s}: {counts.get(status, 0):4d}")
    emit("")

    emit("PER-SCRIPT AUDIT")
    emit("-" * 124)
    emit(f"{'STATUS':20s} {'PHASE':18s} SCRIPT")
    emit("-" * 124)
    for r in rows:
        emit(f"{r.status:20s} {r.phase_tag:18s} {r.script}")
        if r.status != "FULL":
            emit(f"    -> {r.notes}")
            if r.missing_declared_outputs:
                emit(f"       missing: {r.missing_declared_outputs}")
            if r.inferred_sibling_outputs:
                emit(f"       nearby artifacts: {r.inferred_sibling_outputs}")
    emit("")

    emit("B14A SOURCE / DOCUMENTATION GATE")
    emit("-" * 124)
    source_files = b14a["source_files"]
    structured_files = b14a["structured_files"]
    narrative_files = b14a["narrative_files"]
    marker_hits = b14a["marker_hits"]

    emit(f"B14A Python source found:          {'YES' if source_files else 'NO'}")
    for p in source_files:
        emit(f"    source: {p.relative_to(HERE)}")

    emit(f"B14A structured result found:      {'YES' if structured_files else 'NO'}")
    for p in structured_files:
        emit(f"    data:   {p.relative_to(HERE)}")

    emit(f"B14A narrative summary found:      {'YES' if narrative_files else 'NO'}")
    for p in narrative_files:
        emit(f"    summary:{p.relative_to(HERE)}")

    emit("")
    emit("Frozen-marker trace:")
    for marker, meaning in B14A_MARKERS.items():
        hits = marker_hits.get(marker, [])
        label = meaning or "brace support identifier"
        emit(f"  {marker:12s} ({label}): {'FOUND' if hits else 'NOT FOUND'}")
        for h in hits[:8]:
            emit(f"      {h}")
    emit("")

    b14a_full = bool(source_files and structured_files and narrative_files)
    marker_complete = all(marker_hits.get(m) for m in B14A_MARKERS)

    if b14a_full and marker_complete:
        emit("B14A DOCUMENTATION GATE: PASS")
        emit("The frozen B14A calculation appears to have source code, structured results,")
        emit("a narrative summary, and all expected frozen-result markers on disk.")
    else:
        emit("B14A DOCUMENTATION GATE: REVIEW REQUIRED")
        emit("Do NOT make B14B source-connected by copying B14A result numbers from chat.")
        emit("First identify/restore the missing B14A source/result/summary artifact(s).")
    emit("")

    emit("RECOMMENDED CLEANUP ORDER")
    emit("-" * 124)
    priority = [
        r for r in rows
        if r.status in {"DECLARED_MISSING", "CONSOLE_ONLY", "CODE_ONLY",
                        "STRUCTURED_ONLY", "NARRATIVE_ONLY"}
    ]
    if not priority:
        emit("No documentation gaps detected by this audit.")
    else:
        for i, r in enumerate(priority, 1):
            emit(f"{i:3d}. [{r.status}] {r.script}")
            emit(f"     {r.notes}")

    emit("")
    emit("NOTE")
    emit("-" * 124)
    emit("This is a filesystem/documentation audit only. A FULL status means the calculation")
    emit("has source + persisted result artifacts; it does not independently certify the math.")
    emit("=" * 124)

    return "\n".join(lines)


def main() -> None:
    scripts = discover_phase_scripts()
    rows = [audit_script(p) for p in scripts]
    b14a = scan_b14a()

    csv_path = HERE / "phase2e3_documentation_audit_v01.csv"
    txt_path = HERE / "phase2e3_documentation_audit_v01.txt"

    write_csv(rows, csv_path)
    report = make_report(rows, b14a)
    txt_path.write_text(report, encoding="utf-8")

    print(report)
    print()
    print("OUTPUT FILES")
    print(f"CSV: {csv_path}")
    print(f"TXT: {txt_path}")


if __name__ == "__main__":
    main()
