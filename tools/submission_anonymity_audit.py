#!/usr/bin/env python3
"""Audit the anonymous paper PDF and supplementary ZIP for identifying text."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Any

try:
    from tools.build_anonymous_supplement import FORBIDDEN_PATTERNS
except ModuleNotFoundError:  # Direct execution adds tools/ rather than the repository root.
    from build_anonymous_supplement import FORBIDDEN_PATTERNS


ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = ROOT / "WorldEpisode.pdf"
SUPPLEMENT_PATH = ROOT / "WorldEpisode-supplement.zip"
SUPPLEMENT_REPORT_PATH = (
    ROOT / "docs" / "anonymous_supplement" / "supplement_report.json"
)
OUTPUT_DIR = ROOT / "docs" / "experiments" / "anonymity_audit"
OUTPUT_PATH = OUTPUT_DIR / "anonymity_report.json"
README_PATH = OUTPUT_DIR / "README.md"
SCHEMA = "worldepisode_submission_anonymity_audit_v1"


class AnonymityAuditError(RuntimeError):
    """Raised when required PDF inspection tooling is unavailable."""


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AnonymityAuditError(f"expected JSON object in {relative(path)}")
    return payload


def command_output(command: list[str]) -> str:
    if shutil.which(command[0]) is None:
        raise AnonymityAuditError(f"required command is unavailable: {command[0]}")
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise AnonymityAuditError(
            f"{command[0]} exited {result.returncode}: {(result.stderr or result.stdout).strip()}"
        )
    return result.stdout


def identity_match_count(text: str) -> int:
    return sum(len(pattern.findall(text)) for pattern in FORBIDDEN_PATTERNS)


def build_report() -> dict[str, Any]:
    if not PDF_PATH.is_file():
        raise AnonymityAuditError(f"paper PDF is missing: {relative(PDF_PATH)}")
    if not SUPPLEMENT_PATH.is_file():
        raise AnonymityAuditError(
            f"supplement archive is missing: {relative(SUPPLEMENT_PATH)}"
        )

    pdf_info = command_output(["pdfinfo", str(PDF_PATH)])
    pdf_text = command_output(["pdftotext", str(PDF_PATH), "-"])
    metadata: dict[str, str] = {}
    for line in pdf_info.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            metadata[key.strip()] = value.strip()

    pdf_identity_matches = identity_match_count(pdf_info + "\n" + pdf_text)
    author_metadata = metadata.get("Author", "")
    supplement_report = load_json(SUPPLEMENT_REPORT_PATH)
    zip_identity_matches = 0
    unsafe_names: list[str] = []
    with zipfile.ZipFile(SUPPLEMENT_PATH, mode="r") as archive:
        for name in archive.namelist():
            matches = identity_match_count(name)
            if matches:
                unsafe_names.append(name)
                zip_identity_matches += matches
            zip_identity_matches += identity_match_count(
                archive.read(name).decode("utf-8", errors="ignore")
            )

    errors: list[str] = []
    if author_metadata:
        errors.append("PDF Author metadata is non-empty")
    if pdf_identity_matches:
        errors.append("identifying text appears in extracted PDF text or metadata")
    if zip_identity_matches:
        errors.append("identifying text appears in supplementary ZIP paths or payloads")
    if supplement_report.get("status") != "pass":
        errors.append("supplement builder report did not pass")
    if supplement_report.get("archive", {}).get("path") != relative(SUPPLEMENT_PATH):
        errors.append("supplement builder report points to a different archive")

    return {
        "schema": SCHEMA,
        "status": "pass" if not errors else "fail",
        "paper": {
            "path": relative(PDF_PATH),
            "pages": int(metadata.get("Pages", "0")),
            "author_metadata_empty": not author_metadata,
            "identity_pattern_matches": pdf_identity_matches,
            "javascript": metadata.get("JavaScript"),
            "encrypted": metadata.get("Encrypted"),
        },
        "supplement": {
            "path": relative(SUPPLEMENT_PATH),
            "builder_report": relative(SUPPLEMENT_REPORT_PATH),
            "identity_pattern_matches": zip_identity_matches,
            "unsafe_names": unsafe_names,
            "source_control_history_included": supplement_report.get("policy", {}).get(
                "source_control_history_included"
            ),
            "local_environment_included": supplement_report.get("policy", {}).get(
                "local_environment_included"
            ),
        },
        "validation": {
            "passed": not errors,
            "errors": errors,
            "pdfinfo_used": True,
            "pdftotext_used": True,
        },
        "artifacts": {
            "json": relative(OUTPUT_PATH),
            "markdown": relative(README_PATH),
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    errors = report["validation"]["errors"]
    error_text = "\n".join(f"- {error}" for error in errors) if errors else "- None"
    return f"""# Submission Anonymity Audit

Status: `{report["status"]}`.

- PDF pages: `{report["paper"]["pages"]}`
- PDF Author metadata empty: `{report["paper"]["author_metadata_empty"]}`
- PDF identity-pattern matches: `{report["paper"]["identity_pattern_matches"]}`
- Supplement identity-pattern matches: `{report["supplement"]["identity_pattern_matches"]}`
- Git history included: `{report["supplement"]["source_control_history_included"]}`
- Local environment included: `{report["supplement"]["local_environment_included"]}`

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
        help="fail when committed audit outputs differ from the current PDF and ZIP",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="return nonzero when anonymity validation fails",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = build_report()
    except (OSError, json.JSONDecodeError, zipfile.BadZipFile, AnonymityAuditError) as exc:
        print(f"submission anonymity audit: ERROR: {exc}")
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
        print(f"submission anonymity audit: {'current' if current else 'stale'}")
        if not current:
            return 1
    else:
        write_outputs(report)
        print(
            json.dumps(
                {
                    "status": report["status"],
                    "paper": report["paper"],
                    "supplement": report["supplement"],
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
