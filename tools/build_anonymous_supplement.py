#!/usr/bin/env python3
"""Build and audit a deterministic anonymous NeurIPS supplementary archive."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "WorldEpisode-supplement.zip"
REPORT_DIR = ROOT / "docs" / "anonymous_supplement"
REPORT_PATH = REPORT_DIR / "supplement_report.json"
README_PATH = REPORT_DIR / "README.md"
ARCHIVE_ROOT = "WorldEpisode-anonymous-supplement"
SCHEMA = "worldepisode_anonymous_supplement_v1"

TOP_LEVEL_FILES = {
    ".gitignore",
    "CITATION.cff",
    "GOVERNANCE.md",
    "LICENSE",
    "LICENSE-APACHE",
    "Makefile",
    "README.md",
    "THIRD_PARTY_ASSETS.md",
    "TODO.md",
    "WorldEpisode.pdf",
    "pyproject.toml",
    "requirements-experiments.txt",
    "uv.lock",
}
INCLUDED_PREFIXES = (
    ".github/workflows/",
    "conformance/",
    "docs/experiments/",
    "examples/",
    "paper/arxiv/",
    "paper/le-world-layout.md",
    "schemas/",
    "spec/",
    "tests/",
    "third_party_licenses/",
    "tools/",
    "worldepisode/",
)
EXCLUDED_PATHS = {
    "tests/test_anonymous_supplement.py",
    "tools/build_anonymous_supplement.py",
}
EXCLUDED_SUFFIXES = {
    ".aux",
    ".bbl",
    ".blg",
    ".fdb_latexmk",
    ".fls",
    ".log",
    ".out",
    ".pyc",
    ".run.xml",
    ".synctex.gz",
}

# These substitutions apply only to the archive payload, never to the source worktree.
REPLACEMENTS = (
    ("Alba Tellez Fernandez", "Anonymous Author"),
    ("Tellez Fernandez", "Anonymous Author"),
    ("URDF Studio maintainers", "Anonymous WorldEpisode contributors"),
    ("URDF Studio", "Anonymous reference implementation"),
    ("amtellezfernandez", "anonymous"),
    ("atellez", "anonymous"),
    ("amdev", "anonymous"),
    ("golden-apple", "anonymous-host"),
    ("100.78.242.49", "anonymous-host"),
)
FORBIDDEN_PATTERNS = tuple(
    re.compile(re.escape(source), flags=re.IGNORECASE) for source, _replacement in REPLACEMENTS
)
TEXT_NAMES = {
    ".gitignore",
    "LICENSE",
    "LICENSE-APACHE",
    "Makefile",
}
TEXT_SUFFIXES = {
    ".bib",
    ".cff",
    ".csv",
    ".json",
    ".lock",
    ".md",
    ".py",
    ".sty",
    ".tex",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}


class SupplementError(ValueError):
    """Raised when the supplementary artifact cannot be anonymized safely."""


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def should_include(path: Path) -> bool:
    rel = relative(path)
    if rel in EXCLUDED_PATHS:
        return False
    if rel.startswith("docs/experiments/anonymity_audit/"):
        return False
    if any(part in {".git", ".venv", ".pytest_cache", "__pycache__", "worldepisode.egg-info"} for part in path.parts):
        return False
    if any(rel.endswith(suffix) for suffix in EXCLUDED_SUFFIXES):
        return False
    if rel == "paper/arxiv/main.pdf":
        return False
    return rel in TOP_LEVEL_FILES or rel.startswith(INCLUDED_PREFIXES)


def source_paths() -> list[Path]:
    return sorted(
        (path for path in ROOT.rglob("*") if path.is_file() and should_include(path)),
        key=relative,
    )


def is_text(path: Path) -> bool:
    return path.name in TEXT_NAMES or path.suffix.lower() in TEXT_SUFFIXES


def anonymize_text(text: str) -> str:
    transformed = text
    for source, replacement in REPLACEMENTS:
        transformed = re.sub(re.escape(source), replacement, transformed, flags=re.IGNORECASE)
    return transformed


def scan_forbidden(data: bytes, path: str) -> list[str]:
    decoded = data.decode("utf-8", errors="ignore")
    return [
        f"{path}: forbidden identity pattern remained"
        for pattern in FORBIDDEN_PATTERNS
        if pattern.search(decoded)
    ]


def transformed_payload(path: Path) -> bytes:
    data = path.read_bytes()
    if is_text(path):
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SupplementError(f"text allowlist file is not UTF-8: {relative(path)}") from exc
        data = anonymize_text(text).encode("utf-8")
    violations = scan_forbidden(data, relative(path))
    if violations:
        raise SupplementError("; ".join(violations))
    return data


def zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    info.create_system = 3
    return info


def build_archive() -> tuple[bytes, dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    payloads: list[tuple[str, bytes]] = []
    for path in source_paths():
        rel = relative(path)
        data = transformed_payload(path)
        archive_path = f"{ARCHIVE_ROOT}/{rel}"
        payloads.append((archive_path, data))
        entries.append(
            {
                "path": rel,
                "sha256": sha256_bytes(data),
                "bytes": len(data),
                "text_transformed": is_text(path),
            }
        )

    anonymity_text = """# Anonymous Supplement

This archive was built from an explicit allowlist. Source-control history, caches, local
environments, author metadata, personal repository namespaces, local usernames, hostnames, and
machine addresses are not distributed. Text payloads are transformed before hashing; binary
payloads are copied only after a byte-level identity scan.

The authoritative entry digests are in `SUPPLEMENT_MANIFEST.json`.
"""
    anonymity_data = anonymity_text.encode("utf-8")
    payloads.append((f"{ARCHIVE_ROOT}/ANONYMITY.md", anonymity_data))
    entries.append(
        {
            "path": "ANONYMITY.md",
            "sha256": sha256_bytes(anonymity_data),
            "bytes": len(anonymity_data),
            "text_transformed": False,
        }
    )

    internal_manifest = {
        "schema": SCHEMA,
        "archive_root": ARCHIVE_ROOT,
        "entry_count": len(entries),
        "entries": entries,
        "validation": {
            "identity_pattern_matches": 0,
            "passed": True,
        },
    }
    manifest_data = (
        json.dumps(internal_manifest, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    payloads.append((f"{ARCHIVE_ROOT}/SUPPLEMENT_MANIFEST.json", manifest_data))

    output = io.BytesIO()
    with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(payloads):
            archive.writestr(zip_info(name), data)
    archive_bytes = output.getvalue()
    return archive_bytes, internal_manifest


def validate_archive(archive_bytes: bytes, internal_manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    with zipfile.ZipFile(io.BytesIO(archive_bytes), mode="r") as archive:
        names = archive.namelist()
        if names != sorted(names):
            errors.append("archive entries are not sorted")
        expected_names = {
            f"{ARCHIVE_ROOT}/{entry['path']}" for entry in internal_manifest["entries"]
        }
        expected_names.add(f"{ARCHIVE_ROOT}/SUPPLEMENT_MANIFEST.json")
        if set(names) != expected_names:
            errors.append("archive entry set differs from the internal manifest")
        for name in names:
            data = archive.read(name)
            errors.extend(scan_forbidden(data, name))
        for entry in internal_manifest["entries"]:
            name = f"{ARCHIVE_ROOT}/{entry['path']}"
            if name not in names:
                continue
            data = archive.read(name)
            if sha256_bytes(data) != entry["sha256"]:
                errors.append(f"{entry['path']}: digest mismatch")
            if len(data) != entry["bytes"]:
                errors.append(f"{entry['path']}: byte count mismatch")
    return errors


def build_report(archive_bytes: bytes, internal_manifest: dict[str, Any]) -> dict[str, Any]:
    errors = validate_archive(archive_bytes, internal_manifest)
    return {
        "schema": SCHEMA,
        "status": "pass" if not errors else "fail",
        "archive": {
            "path": relative(OUTPUT_PATH),
            "sha256": sha256_bytes(archive_bytes),
            "bytes": len(archive_bytes),
            "entry_count": internal_manifest["entry_count"] + 1,
        },
        "policy": {
            "source_selection": "explicit allowlist",
            "text_payloads_transformed_before_hashing": True,
            "binary_payloads_identity_scanned": True,
            "source_control_history_included": False,
            "local_environment_included": False,
        },
        "validation": {
            "passed": not errors,
            "errors": errors,
            "identity_pattern_matches": len(
                [error for error in errors if "identity pattern" in error]
            ),
        },
        "artifacts": {
            "json": relative(REPORT_PATH),
            "markdown": relative(README_PATH),
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    errors = report["validation"]["errors"]
    error_text = "\n".join(f"- {error}" for error in errors) if errors else "- None"
    return f"""# Anonymous Supplement

Status: `{report["status"]}`.

- Archive: `{report["archive"]["path"]}`
- SHA-256: `{report["archive"]["sha256"]}`
- Bytes: `{report["archive"]["bytes"]}`
- ZIP entries: `{report["archive"]["entry_count"]}`
- Identity-pattern matches: `{report["validation"]["identity_pattern_matches"]}`
- Source-control history included: `{report["policy"]["source_control_history_included"]}`
- Local environment included: `{report["policy"]["local_environment_included"]}`

## Validation Errors

{error_text}
"""


def write_outputs(
    archive_bytes: bytes,
    report: dict[str, Any],
) -> None:
    OUTPUT_PATH.write_bytes(archive_bytes)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    README_PATH.write_text(render_markdown(report), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if the committed archive or report differs from the current allowlisted sources",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="return nonzero when anonymity validation fails",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    archive_bytes, internal_manifest = build_archive()
    report = build_report(archive_bytes, internal_manifest)
    report_json = json.dumps(report, indent=2, sort_keys=True) + "\n"
    report_markdown = render_markdown(report)

    if args.check:
        current = (
            OUTPUT_PATH.is_file()
            and REPORT_PATH.is_file()
            and README_PATH.is_file()
            and OUTPUT_PATH.read_bytes() == archive_bytes
            and REPORT_PATH.read_text(encoding="utf-8") == report_json
            and README_PATH.read_text(encoding="utf-8") == report_markdown
        )
        print(f"anonymous supplement: {'current' if current else 'stale'}")
        if not current:
            return 1
    else:
        write_outputs(archive_bytes, report)
        print(
            json.dumps(
                {
                    "archive": report["archive"],
                    "status": report["status"],
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
