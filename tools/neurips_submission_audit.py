#!/usr/bin/env python3
"""Audit the paper against the configured NeurIPS submission-format baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "paper" / "arxiv" / "submission_config.json"
MAIN_TEX_PATH = ROOT / "paper" / "arxiv" / "main.tex"
PDF_PATH = ROOT / "WorldEpisode.pdf"
ANONYMITY_REPORT_PATH = (
    ROOT / "docs" / "experiments" / "anonymity_audit" / "anonymity_report.json"
)
OUTPUT_DIR = ROOT / "docs" / "experiments" / "neurips_submission"
OUTPUT_PATH = OUTPUT_DIR / "submission_format_report.json"
README_PATH = OUTPUT_DIR / "README.md"
SCHEMA = "worldepisode_neurips_submission_audit_v1"
CONFIG_SCHEMA = "worldepisode_neurips_submission_config_v1"


class SubmissionAuditError(RuntimeError):
    """Raised when a required input or inspection command is unavailable."""


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SubmissionAuditError(f"required input is missing: {relative(path)}") from exc
    if not isinstance(payload, dict):
        raise SubmissionAuditError(f"expected a JSON object in {relative(path)}")
    return payload


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_source_tree(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(relative(path).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def command_output(command: list[str]) -> str:
    if shutil.which(command[0]) is None:
        raise SubmissionAuditError(f"required command is unavailable: {command[0]}")
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise SubmissionAuditError(f"{command[0]} exited {result.returncode}: {detail}")
    return result.stdout


def parse_pdf_info(text: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()
    return metadata


def first_page_matching(pages: list[str], pattern: str) -> int | None:
    compiled = re.compile(pattern, flags=re.IGNORECASE | re.MULTILINE)
    for page_number, text in enumerate(pages, start=1):
        if compiled.search(text):
            return page_number
    return None


def main_content_last_page(pages: list[str], references_page: int | None) -> int | None:
    if references_page is None:
        return None
    page_text = pages[references_page - 1]
    match = re.search(r"\bReferences\b", page_text, flags=re.IGNORECASE)
    if match is None:
        return None
    visible_prefix: list[str] = []
    for line in page_text[: match.start()].splitlines():
        cleaned = re.sub(r"^\s*\d+\s*", "", line).strip()
        if cleaned and not cleaned.isdigit():
            visible_prefix.append(cleaned)
    return references_page if visible_prefix else references_page - 1


def build_report() -> dict[str, Any]:
    config = load_json(CONFIG_PATH)
    anonymity = load_json(ANONYMITY_REPORT_PATH)
    if not MAIN_TEX_PATH.is_file():
        raise SubmissionAuditError(f"paper source is missing: {relative(MAIN_TEX_PATH)}")
    if not PDF_PATH.is_file():
        raise SubmissionAuditError(f"paper PDF is missing: {relative(PDF_PATH)}")

    baseline = config.get("provisional_baseline", {})
    style_rel = str(baseline.get("style_file", ""))
    style_path = ROOT / style_rel
    if not style_path.is_file():
        raise SubmissionAuditError(f"configured style is missing: {style_rel}")

    main_tex = MAIN_TEX_PATH.read_text(encoding="utf-8")
    format_source_paths = [
        MAIN_TEX_PATH,
        ROOT / "paper" / "arxiv" / "checklist.tex",
        *sorted((ROOT / "paper" / "arxiv" / "sections").glob("*.tex")),
    ]
    pdf_info = parse_pdf_info(command_output(["pdfinfo", str(PDF_PATH)]))
    raw_pdf_text = command_output(["pdftotext", "-layout", str(PDF_PATH), "-"])
    pages = [page for page in raw_pdf_text.split("\f") if page.strip()]

    headings = {
        "conclusion": first_page_matching(
            pages, r"^\s*(?:\d+\s+)?7\s+Conclusion\s*$"
        ),
        "references": first_page_matching(
            pages, r"^\s*(?:\d+\s+)?References\s*$"
        ),
        "appendix": first_page_matching(
            pages, r"^\s*(?:\d+\s+)?A\s+Evidence Boundaries\s*$"
        ),
        "checklist": first_page_matching(
            pages, r"^\s*(?:\d+\s+)?NeurIPS Paper Checklist\s*$"
        ),
    }
    body_last_page = main_content_last_page(pages, headings["references"])
    page_limit = int(baseline.get("main_content_page_limit", 0))

    style_stem = Path(style_rel).stem
    package_options = ",".join(str(item) for item in baseline.get("package_options", []))
    expected_submission_directive = rf"\usepackage[{package_options}]{{{style_stem}}}"
    source_markers = [
        r"\bibliography{references}",
        r"\input{sections/appendix}",
        r"\input{checklist}",
        r"\end{document}",
    ]
    source_positions = [main_tex.find(marker) for marker in source_markers]
    prohibited_format_overrides = (
        r"\geometry",
        r"\newgeometry",
        r"\textwidth",
        r"\textheight",
        r"\topmargin",
        r"\oddsidemargin",
        r"\evensidemargin",
        r"\linespread",
        r"\fontsize",
    )
    format_override_hits = {
        relative(path): [
            token
            for token in prohibited_format_overrides
            if token in path.read_text(encoding="utf-8")
        ]
        for path in format_source_paths
    }
    format_override_hits = {
        path: tokens for path, tokens in format_override_hits.items() if tokens
    }

    checklist_on_last_page = bool(
        pages
        and headings["checklist"] is not None
        and re.search(r"Declaration of LLM usage", pages[-1], flags=re.IGNORECASE)
    )
    checks = {
        "configuration_schema_valid": config.get("schema") == CONFIG_SCHEMA,
        "configured_style_digest_matches": (
            sha256_file(style_path) == baseline.get("style_sha256")
        ),
        "default_build_uses_configured_double_blind_style": (
            config.get("review_mode") == "double_blind"
            and expected_submission_directive in main_tex
        ),
        "manual_margin_and_font_overrides_absent": not format_override_hits,
        "paper_source_order_is_body_references_appendix_checklist": (
            all(position >= 0 for position in source_positions)
            and source_positions == sorted(source_positions)
        ),
        "paper_pdf_is_letter_sized": "(letter)" in pdf_info.get("Page size", ""),
        "paper_pdf_author_metadata_is_empty": not pdf_info.get("Author", ""),
        "paper_and_supplement_anonymity_audit_passes": (
            anonymity.get("schema") == "worldepisode_submission_anonymity_audit_v1"
            and anonymity.get("status") == "pass"
            and anonymity.get("validation", {}).get("passed") is True
        ),
        "required_pdf_boundaries_are_detected": all(
            page is not None for page in headings.values()
        )
        and body_last_page is not None,
        "main_content_fits_provisional_page_limit": (
            body_last_page is not None and 0 < body_last_page <= page_limit
        ),
        "conclusion_precedes_references": (
            headings["conclusion"] is not None
            and headings["references"] is not None
            and headings["conclusion"] <= headings["references"]
        ),
        "references_precede_appendix": (
            headings["references"] is not None
            and headings["appendix"] is not None
            and headings["references"] < headings["appendix"]
        ),
        "appendix_precedes_checklist": (
            headings["appendix"] is not None
            and headings["checklist"] is not None
            and headings["appendix"] <= headings["checklist"]
        ),
        "checklist_is_last": checklist_on_last_page,
    }
    errors = [name for name, passed in checks.items() if not passed]

    target_author_kit = config.get("target_author_kit", {})
    target_requirements_final = bool(
        target_author_kit.get("instructions_published")
        and target_author_kit.get("style_available")
        and baseline.get("year") == config.get("target_year")
    )
    if errors:
        status = "fail"
    elif target_requirements_final:
        status = "target_ready"
    else:
        status = "provisional_ready_pending_target_author_kit"

    return {
        "schema": SCHEMA,
        "status": status,
        "target": {
            "venue": config.get("venue"),
            "year": config.get("target_year"),
            "track": config.get("track"),
            "review_mode": config.get("review_mode"),
            "author_kit": target_author_kit,
            "requirements_final": target_requirements_final,
        },
        "baseline": {
            **baseline,
            "style_actual_sha256": sha256_file(style_path),
            "migration_required": not target_requirements_final,
        },
        "paper": {
            "path": relative(PDF_PATH),
            "sha256": sha256_file(PDF_PATH),
            "pages": int(pdf_info.get("Pages", "0")),
            "page_size": pdf_info.get("Page size"),
            "source_path": relative(MAIN_TEX_PATH),
            "source_sha256": sha256_file(MAIN_TEX_PATH),
            "format_source_paths": [relative(path) for path in format_source_paths],
            "format_source_tree_sha256": sha256_source_tree(format_source_paths),
            "manual_format_override_hits": format_override_hits,
            "heading_pages": headings,
            "main_content_last_page": body_last_page,
            "main_content_page_limit": page_limit,
        },
        "submission_classification": config.get("submission_classification", {}),
        "external_tasks": config.get("external_tasks", []),
        "validation": {
            "passed": not errors,
            "checks": checks,
            "errors": errors,
        },
        "artifacts": {
            "json": relative(OUTPUT_PATH),
            "markdown": relative(README_PATH),
            "configuration": relative(CONFIG_PATH),
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    checks = report["validation"]["checks"]
    check_rows = [
        f"| `{name}` | {passed} |" for name, passed in checks.items()
    ]
    task_rows = [
        f"| `{task['id']}` | `{task['status']}` | {task['requirement']} |"
        for task in report["external_tasks"]
    ]
    errors = report["validation"]["errors"]
    error_text = "\n".join(f"- `{error}`" for error in errors) if errors else "- None"
    target = report["target"]
    baseline = report["baseline"]
    paper = report["paper"]
    return f"""# NeurIPS Submission Format Audit

Status: `{report["status"]}`.

The NeurIPS {target["year"]} author kit is not treated as final until both its instructions and
style are recorded in `paper/arxiv/submission_config.json`. The current checks use the official
NeurIPS {baseline["year"]} {target["track"]} requirements as a provisional baseline.

## Format Boundary

- Review mode: `{target["review_mode"]}`
- Configured style: `{baseline["style_file"]}`
- Target requirements final: `{target["requirements_final"]}`
- Style migration required: `{baseline["migration_required"]}`
- Main-content last page: `{paper["main_content_last_page"]}`
- Provisional main-content page limit: `{paper["main_content_page_limit"]}`
- References page: `{paper["heading_pages"]["references"]}`
- Appendix page: `{paper["heading_pages"]["appendix"]}`
- Checklist page: `{paper["heading_pages"]["checklist"]}`
- Total PDF pages: `{paper["pages"]}`

## Automated Checks

| Check | Pass |
|---|---:|
{chr(10).join(check_rows)}

## External Tasks

| Task | Status | Requirement |
|---|---|---|
{chr(10).join(task_rows)}

## Validation Errors

{error_text}
"""


def write_outputs(report: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    README_PATH.write_text(render_markdown(report), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail when the committed report differs from the current paper and configuration",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="return nonzero when the configured format validation fails",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = build_report()
    except (OSError, json.JSONDecodeError, SubmissionAuditError) as exc:
        print(f"NeurIPS submission audit: ERROR: {exc}")
        return 1

    report_json = json.dumps(report, indent=2, sort_keys=True) + "\n"
    report_markdown = render_markdown(report)
    if args.check:
        current = (
            OUTPUT_PATH.is_file()
            and README_PATH.is_file()
            and OUTPUT_PATH.read_text(encoding="utf-8") == report_json
            and README_PATH.read_text(encoding="utf-8") == report_markdown
        )
        print(f"NeurIPS submission audit: {'current' if current else 'stale'}")
        if not current:
            return 1
    else:
        write_outputs(report)
        print(
            json.dumps(
                {
                    "status": report["status"],
                    "target": report["target"],
                    "paper": report["paper"],
                    "validation": report["validation"],
                },
                indent=2,
                sort_keys=True,
            )
        )

    if args.strict and not report["validation"]["passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
