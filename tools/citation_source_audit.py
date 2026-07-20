#!/usr/bin/env python3
"""Audit every paper citation and require archival sources where they exist."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BIB_PATH = ROOT / "paper" / "arxiv" / "references.bib"
TEX_PATHS = (
    ROOT / "paper" / "arxiv" / "main.tex",
    *(ROOT / "paper" / "arxiv" / "sections").glob("*.tex"),
)
OUTPUT_DIR = ROOT / "docs" / "experiments" / "citation_source_audit"
REPORT_PATH = OUTPUT_DIR / "citation_source_audit.json"
README_PATH = OUTPUT_DIR / "README.md"
SCHEMA = "worldepisode_citation_source_audit_v1"

SOURCE_POLICY = {
    "armnetbench_lerobot_so101": "pinned_dataset_card",
    "bridgedata": "archival_paper",
    "calvin": "archival_paper",
    "croissant2024": "archival_paper",
    "droid": "archival_paper",
    "gebru2021datasheets": "archival_paper",
    "genesis": "versioned_software_documentation",
    "gltf_gs": "normative_specification",
    "kapoor2023leakage": "archival_paper",
    "lerobot": "archival_paper",
    "lerobot_pusht": "pinned_dataset_card",
    "lerobot_svla_so101_pickplace": "pinned_dataset_card",
    "lerobot_v3": "versioned_software_documentation",
    "libero": "archival_paper",
    "mitchell2019modelcards": "archival_paper",
    "mujoco": "archival_paper",
    "ncore": "normative_specification",
    "openx": "archival_paper",
    "rerun": "versioned_software_documentation",
    "rosrep103": "normative_specification",
    "usd": "normative_specification",
}

ARCHIVAL_REQUIRED = {
    "bridgedata",
    "calvin",
    "croissant2024",
    "droid",
    "libero",
    "mujoco",
    "openx",
}

CITE_PATTERN = re.compile(r"\\cite[pt]?\{([^}]+)\}")
ENTRY_PATTERN = re.compile(r"@([A-Za-z]+)\s*\{\s*([^,\s]+)\s*,")
FIELD_PATTERN = re.compile(r"(?m)^\s*([A-Za-z][A-Za-z0-9_-]*)\s*=\s*\{(.*)\}\s*,?\s*$")


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def parse_bibliography(text: str) -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    position = 0
    while match := ENTRY_PATTERN.search(text, position):
        entry_type = match.group(1).lower()
        key = match.group(2)
        depth = 1
        cursor = match.end()
        while cursor < len(text) and depth:
            if text[cursor] == "{":
                depth += 1
            elif text[cursor] == "}":
                depth -= 1
            cursor += 1
        if depth:
            raise ValueError(f"unclosed bibliography entry: {key}")
        body = text[match.end() : cursor - 1]
        fields = {
            field.lower(): value.strip()
            for field, value in FIELD_PATTERN.findall(body)
        }
        if key in entries:
            raise ValueError(f"duplicate bibliography key: {key}")
        entries[key] = {
            "entry_type": entry_type,
            "fields": fields,
        }
        position = cursor
    return entries


def collect_citations() -> dict[str, list[dict[str, Any]]]:
    citations: dict[str, list[dict[str, Any]]] = {}
    for path in sorted(TEX_PATHS):
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            for match in CITE_PATTERN.finditer(line):
                for key in (item.strip() for item in match.group(1).split(",")):
                    if key:
                        citations.setdefault(key, []).append(
                            {
                                "path": relative(path),
                                "line": line_number,
                            }
                        )
    return citations


def locator(fields: dict[str, str]) -> str | None:
    if fields.get("doi"):
        return f"https://doi.org/{fields['doi']}"
    value = fields.get("url") or fields.get("howpublished")
    if not value:
        return None
    match = re.search(r"https?://[^}\\\s]+", value)
    return match.group(0) if match else value


def audit_reference(
    key: str,
    entry: dict[str, Any],
    occurrences: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    entry_type = entry["entry_type"]
    fields = entry["fields"]
    source_class = SOURCE_POLICY.get(key)
    if source_class is None:
        errors.append(f"{key}: no source-class decision")
        source_class = "unclassified"
    for required in ("author", "title", "year"):
        if not fields.get(required):
            errors.append(f"{key}: missing {required}")
    source_locator = locator(fields)
    if source_locator is None:
        errors.append(f"{key}: missing DOI or URL")
    if key in ARCHIVAL_REQUIRED and entry_type not in {"article", "inproceedings"}:
        errors.append(f"{key}: archival paper exists but entry type is {entry_type}")
    if source_class == "archival_paper":
        venue_field = "journal" if entry_type == "article" else "booktitle"
        if not fields.get(venue_field):
            errors.append(f"{key}: archival entry missing {venue_field}")
    if source_class == "pinned_dataset_card":
        if "pinned revision" not in fields.get("note", "").lower():
            errors.append(f"{key}: dataset card does not record a pinned revision")
    if entry_type == "misc" and not fields.get("note"):
        errors.append(f"{key}: web/specification entry missing access or version note")
    return (
        {
            "key": key,
            "entry_type": entry_type,
            "source_class": source_class,
            "title": fields.get("title"),
            "year": fields.get("year"),
            "locator": source_locator,
            "occurrence_count": len(occurrences),
            "occurrences": occurrences,
            "validation": {
                "passed": not errors,
                "errors": errors,
            },
        },
        errors,
    )


def build_report() -> dict[str, Any]:
    bibliography = parse_bibliography(BIB_PATH.read_text(encoding="utf-8"))
    citations = collect_citations()
    errors: list[str] = []
    undefined = sorted(set(citations) - set(bibliography))
    unused = sorted(set(bibliography) - set(citations))
    policy_missing = sorted(set(citations) - set(SOURCE_POLICY))
    policy_extra = sorted(set(SOURCE_POLICY) - set(citations))
    errors.extend(f"undefined citation: {key}" for key in undefined)
    errors.extend(f"unused bibliography entry: {key}" for key in unused)
    errors.extend(f"citation missing source policy: {key}" for key in policy_missing)
    errors.extend(f"source policy has no citation: {key}" for key in policy_extra)

    references = []
    for key in sorted(set(citations) & set(bibliography)):
        reference, reference_errors = audit_reference(
            key,
            bibliography[key],
            citations[key],
        )
        references.append(reference)
        errors.extend(reference_errors)

    return {
        "schema": SCHEMA,
        "scope": (
            "Every citation in the anonymous LaTeX paper. Archival papers replace project pages "
            "where available; normative specifications, pinned dataset cards, and versioned "
            "software documentation remain primary web sources."
        ),
        "references": references,
        "aggregate": {
            "reference_count": len(references),
            "citation_occurrence_count": sum(
                len(occurrences) for occurrences in citations.values()
            ),
            "archival_reference_count": sum(
                reference["source_class"] == "archival_paper"
                for reference in references
            ),
            "undefined_count": len(undefined),
            "unused_count": len(unused),
            "error_count": len(errors),
        },
        "validation": {
            "passed": not errors,
            "errors": errors,
            "undefined_citations": undefined,
            "unused_bibliography_entries": unused,
        },
        "artifacts": {
            "json": relative(REPORT_PATH),
            "markdown": relative(README_PATH),
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    rows = []
    for reference in report["references"]:
        rows.append(
            "| `{key}` | {source_class} | {entry_type} | {occurrences} | {passed} |".format(
                key=reference["key"],
                source_class=reference["source_class"],
                entry_type=reference["entry_type"],
                occurrences=reference["occurrence_count"],
                passed=reference["validation"]["passed"],
            )
        )
    errors = report["validation"]["errors"]
    error_text = "\n".join(f"- {error}" for error in errors) if errors else "- None"
    return f"""# Citation Source Audit

Status: `{"pass" if report["validation"]["passed"] else "fail"}`.

{report["scope"]}

| Key | Source class | BibTeX type | Uses | Pass |
|---|---|---|---:|---:|
{chr(10).join(rows)}

## Validation

- References: {report["aggregate"]["reference_count"]}
- Citation occurrences: {report["aggregate"]["citation_occurrence_count"]}
- Archival references: {report["aggregate"]["archival_reference_count"]}
- Undefined citations: {report["aggregate"]["undefined_count"]}
- Unused bibliography entries: {report["aggregate"]["unused_count"]}

Errors:

{error_text}
"""


def canonical_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True) + "\n"


def write_report(report: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(canonical_json(report), encoding="utf-8")
    README_PATH.write_text(render_markdown(report), encoding="utf-8")


def check_report(report: dict[str, Any]) -> list[str]:
    errors = []
    expected = {
        REPORT_PATH: canonical_json(report),
        README_PATH: render_markdown(report),
    }
    for path, content in expected.items():
        if not path.is_file():
            errors.append(f"missing generated artifact: {relative(path)}")
        elif path.read_text(encoding="utf-8") != content:
            errors.append(f"stale generated artifact: {relative(path)}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    report = build_report()
    freshness_errors = check_report(report) if args.check else []
    if not args.check:
        write_report(report)
    if args.check:
        print("citation source audit: current" if not freshness_errors else "\n".join(freshness_errors))
    else:
        print(
            json.dumps(
                {
                    "status": "pass" if report["validation"]["passed"] else "fail",
                    "aggregate": report["aggregate"],
                    "artifacts": report["artifacts"],
                },
                indent=2,
                sort_keys=True,
            )
        )
    failed = bool(freshness_errors) or not report["validation"]["passed"]
    return 1 if args.strict and failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
