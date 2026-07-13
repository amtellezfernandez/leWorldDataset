#!/usr/bin/env python3
"""Audit public-facing release language for evidence-gated RFC maturity.

This does not ban the JSON Schema Draft 2020-12 metaschema or `Draft202012Validator`.
It catches project-facing wording that would make the repository look like only a paper plan instead
of an executable RFC release with explicit open gates.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "experiments" / "public_maturity"
SCHEMA = "worldepisode_public_maturity_audit_v1"
AUDIT_DATE = "2026-07-13"


SCAN_PATHS = [
    "README.md",
    "GOVERNANCE.md",
    "spec/worldepisode-v0.1.md",
    "spec/le-world-layout-v0.1.md",
    "paper/le-world-layout.md",
    "paper/outline.md",
    "conformance/requirements.md",
    "conformance/profiles.md",
    "conformance/fixtures/README.md",
    "conformance/projections/uss-core-23.v0.json",
    "docs/benchmark-callout-audit.md",
    "docs/bindings.md",
    "docs/meta-simulator-contract.md",
    "docs/policy-leakage-gate.md",
    "docs/production-scale.md",
    "docs/real-to-sim-contract-drift.md",
    "docs/reference-release.md",
    "docs/research-plan.md",
    "docs/reviewer-concern-matrix.md",
    "docs/sdk.md",
    "docs/universal-spatial-state.md",
    "docs/experiments/results.json",
    "docs/experiments/paper_claim_audit/README.md",
    "docs/experiments/paper_claim_audit/paper_claim_audit_report.json",
    "docs/experiments/open_reproduction_gates/README.md",
    "docs/experiments/open_reproduction_gates/open_reproduction_gates.json",
    "docs/submission_packet/README.md",
    "docs/submission_packet/submission_packet.json",
    "paper/arxiv/main.tex",
    "paper/arxiv/sections/evaluation.tex",
    "paper/arxiv/sections/introduction.tex",
    "paper/arxiv/sections/limitations.tex",
    "schemas/conformance-requirements-v0.schema.json",
    "schemas/le-world-layout-v0.schema.json",
    "schemas/worldepisode-core-v0.schema.json",
    "schemas/worldepisode-dataset-v0.schema.json",
    "tools/open_reproduction_gates.py",
    "tools/paper_claim_audit.py",
    "tools/run_experiments.py",
    "tools/validate_examples.py",
    "worldepisode/schemas/conformance-requirements-v0.schema.json",
    "worldepisode/schemas/le-world-layout-v0.schema.json",
    "worldepisode/schemas/worldepisode-core-v0.schema.json",
    "worldepisode/schemas/worldepisode-dataset-v0.schema.json",
]


_DRAFT = "draft"
_CURRENT_DRAFTS = "Current " + "Drafts"


BANNED_PATTERNS = [
    _CURRENT_DRAFTS,
    f"Status: {_DRAFT}",
    f"paper {_DRAFT}",
    f"{_DRAFT} spec",
    f"{_DRAFT} specification",
    f"{_DRAFT} schema",
    f"{_DRAFT} schemas",
    f"WorldEpisode {_DRAFT}",
    f"USS / WorldEpisode {_DRAFT}",
    f"WorldEpisode Core v0 {_DRAFT}",
    f"WorldEpisode Dataset Manifest v0 {_DRAFT}",
    f"WorldEpisode Conformance Requirements v0 {_DRAFT}",
    f"leWorldLayout v0 {_DRAFT}",
    f"results not claimed in this {_DRAFT}",
    f"zero inflation claims in this {_DRAFT}",
    f"in this {_DRAFT}",
    f'"status": "{_DRAFT}"',
]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def line_matches(path: Path, pattern: str) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    matches = []
    pattern_lower = pattern.lower()
    for index, line in enumerate(text.splitlines(), start=1):
        if pattern_lower in line.lower():
            matches.append(
                {
                    "path": rel(path),
                    "line": index,
                    "pattern": pattern,
                    "text": line.strip(),
                }
            )
    return matches


def build_report(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    missing = [path for path in SCAN_PATHS if not (ROOT / path).is_file()]
    violations: list[dict[str, Any]] = []
    for relative_path in SCAN_PATHS:
        path = ROOT / relative_path
        if not path.is_file():
            continue
        for pattern in BANNED_PATTERNS:
            violations.extend(line_matches(path, pattern))

    report = {
        "schema": SCHEMA,
        "audit_date": AUDIT_DATE,
        "status": "pass" if not missing and not violations else "fail",
        "claim_boundary": (
            "The repository may call itself an evidence-gated RFC release with open reproduction "
            "gates. It must not present the public surface as only a paper plan. JSON Schema Draft "
            "2020-12 terminology is allowed and is not part of this audit."
        ),
        "scan_paths": SCAN_PATHS,
        "missing_paths": missing,
        "violations": violations,
        "aggregate": {
            "scanned_path_count": len(SCAN_PATHS),
            "missing_path_count": len(missing),
            "banned_pattern_count": len(BANNED_PATTERNS),
            "violation_count": len(violations),
        },
        "artifacts": {
            "json": rel(output_dir / "public_maturity_report.json"),
            "markdown": rel(output_dir / "README.md"),
        },
    }
    write_json(output_dir / "public_maturity_report.json", report)
    write_text(output_dir / "README.md", render_markdown(report))
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Public Maturity Audit",
        "",
        f"Status: `{report['status']}`.",
        "",
        report["claim_boundary"],
        "",
        "## Summary",
        "",
        f"- Scanned paths: {report['aggregate']['scanned_path_count']}",
        f"- Banned patterns: {report['aggregate']['banned_pattern_count']}",
        f"- Missing paths: {report['aggregate']['missing_path_count']}",
        f"- Violations: {report['aggregate']['violation_count']}",
        "",
    ]
    if report["violations"]:
        lines.extend(["## Violations", ""])
        for violation in report["violations"]:
            lines.append(
                f"- `{violation['path']}:{violation['line']}` matched "
                f"`{violation['pattern']}`: {violation['text']}"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--strict", action="store_true", help="exit non-zero if public maturity checks fail")
    args = parser.parse_args()
    report = build_report(args.output_dir)
    print(
        json.dumps(
            {
                "status": report["status"],
                "aggregate": report["aggregate"],
                "artifacts": report["artifacts"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if args.strict and report["status"] != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
