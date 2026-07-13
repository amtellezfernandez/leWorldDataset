#!/usr/bin/env python3
"""Generate a digest manifest for public evidence and release scripts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "release_manifest"
SCHEMA = "worldepisode_release_manifest_v1"
AUDIT_DATE = "2026-07-13"


PUBLIC_EVIDENCE_ARTIFACTS = [
    "WorldEpisode.pdf",
    "README.md",
    "paper/arxiv/main.tex",
    "paper/arxiv/sections/evaluation.tex",
    "paper/arxiv/sections/limitations.tex",
    "schemas/worldepisode-core-v0.schema.json",
    "schemas/worldepisode-dataset-v0.schema.json",
    "schemas/conformance-requirements-v0.schema.json",
    "conformance/requirements.v0.json",
    "conformance/projections/uss-core-23.v0.json",
    "docs/experiments/RESULTS.md",
    "docs/experiments/results.json",
    "docs/experiments/dataset_scale_performance/README.md",
    "docs/experiments/dataset_scale_performance/performance_report.json",
    "docs/experiments/paper_claim_audit/paper_claim_audit_report.json",
    "docs/experiments/public_maturity/public_maturity_report.json",
    "docs/experiments/open_reproduction_gates/open_reproduction_gates.json",
    "docs/experiments/benchmark_inflation_gate/gate_report.json",
    "docs/experiments/lerobot_scene_leakage/leakage_report.json",
    "docs/experiments/lerobot_worldepisode_roundtrip/conversion_report.json",
    "docs/experiments/lerobot_worldepisode_roundtrip_pusht/batch_roundtrip_report.json",
    "docs/experiments/lerobot_control_replay/control_replay_report.json",
    "docs/experiments/meta_simulator_contract/adapter_contract_report.json",
    "docs/experiments/realtosim_contract_drift/contract_drift_report.json",
    "docs/experiments/cleanroom_reader/cleanroom_reader_report.json",
    "docs/experiments/preflight/preflight_report.json",
    "docs/experiments/natural_failure_corpus/manifest.json",
    "docs/reviewer-concern-matrix.md",
    "docs/reference-release.md",
    "GOVERNANCE.md",
    "CITATION.cff",
]

RELEASE_SCRIPTS = [
    ".github/workflows/ci.yml",
    "Makefile",
    "tools/run_experiments.py",
    "tools/open_reproduction_gates.py",
    "tools/paper_claim_audit.py",
    "tools/public_maturity_audit.py",
    "tools/release_manifest.py",
    "tools/submission_packet.py",
    "tools/release_readiness.py",
    "tools/artifact_freshness.py",
]

TIMING = r"[0-9]+(?:\.[0-9]+)?"
TIMING_KEYS = (
    "catalog_open_parse_and_index",
    "digest_cache_resolution",
    "partition_pruning_queries",
    "resolver_routing",
)
TIMING_KEY_PATTERN = re.compile(rf'("({"|".join(TIMING_KEYS)})": ){TIMING}')

NORMALIZERS: dict[str, list[tuple[re.Pattern[str], str]]] = {
    "docs/experiments/results.json": [(TIMING_KEY_PATTERN, r"\g<1>0.0")],
    "docs/experiments/dataset_scale_performance/performance_report.json": [
        (TIMING_KEY_PATTERN, r"\g<1>0.0")
    ],
    "docs/experiments/RESULTS.md": [
        (re.compile(rf"(Catalog open, parse, and index: ){TIMING}( ms)"), r"\g<1>0.000\2"),
        (re.compile(rf"(Partition-pruning query time: ){TIMING}( ms)"), r"\g<1>0.000\2"),
    ],
    "docs/experiments/dataset_scale_performance/README.md": [
        (
            re.compile(
                rf"(\| (Catalog open, parse, and index|Partition-pruning queries|"
                rf"Digest-cache resolution|Resolver routing) \| ){TIMING}( \|)"
            ),
            r"\g<1>0.000\3",
        ),
    ],
}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_content(path: str) -> tuple[str, bytes, list[str]]:
    target = ROOT / path
    normalizers = NORMALIZERS.get(path, [])
    if not normalizers:
        return "exact", target.read_bytes(), []
    text = target.read_text(encoding="utf-8")
    applied: list[str] = []
    for pattern, replacement in normalizers:
        text, count = pattern.subn(replacement, text)
        if count:
            applied.append(pattern.pattern)
    return "normalized", text.encode("utf-8"), applied


def build_entry(path: str, category: str) -> dict[str, Any]:
    target = ROOT / path
    exists = target.is_file()
    entry: dict[str, Any] = {
        "path": path,
        "category": category,
        "exists": exists,
        "nonempty": exists and target.stat().st_size > 0,
    }
    if exists:
        mode, data, applied = canonical_content(path)
        entry.update(
            {
                "digest_mode": mode,
                "sha256": digest_bytes(data),
                "normalizers_applied": applied,
            }
        )
    return entry


def build_manifest(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    manifest = compute_manifest(output_dir)
    write_json(output_dir / "release_manifest.json", manifest)
    write_text(output_dir / "README.md", render_markdown(manifest))
    return manifest


def compute_manifest(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    entries = [
        *[build_entry(path, "public_evidence") for path in PUBLIC_EVIDENCE_ARTIFACTS],
        *[build_entry(path, "release_script") for path in RELEASE_SCRIPTS],
    ]
    missing = [entry["path"] for entry in entries if not entry["exists"]]
    empty = [entry["path"] for entry in entries if entry["exists"] and not entry["nonempty"]]
    normalized = [entry["path"] for entry in entries if entry.get("digest_mode") == "normalized"]
    duplicate_paths = sorted(
        path for path in {entry["path"] for entry in entries} if sum(1 for item in entries if item["path"] == path) > 1
    )
    passed = not missing and not empty and not duplicate_paths

    manifest = {
        "schema": SCHEMA,
        "audit_date": AUDIT_DATE,
        "status": "pass" if passed else "fail",
        "hash_algorithm": "sha256",
        "claim_boundary": (
            "Exact digests are used for stable artifacts. Timing-jitter reports are hashed after "
            "normalizing only wall-clock benchmark timing values."
        ),
        "commands": {
            "generate": "python3 tools/release_manifest.py --strict",
            "verify": "python3 tools/release_manifest.py --verify --strict",
        },
        "entries": entries,
        "aggregate": {
            "entry_count": len(entries),
            "public_evidence_count": len(PUBLIC_EVIDENCE_ARTIFACTS),
            "release_script_count": len(RELEASE_SCRIPTS),
            "normalized_digest_count": len(normalized),
            "missing_count": len(missing),
            "empty_count": len(empty),
        },
        "validation": {
            "passed": passed,
            "missing": missing,
            "empty": empty,
            "duplicate_paths": duplicate_paths,
            "normalized_paths": normalized,
        },
        "artifacts": {
            "json": rel(output_dir / "release_manifest.json"),
            "markdown": rel(output_dir / "README.md"),
        },
    }
    return manifest


def comparable_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        key: manifest.get(key)
        for key in (
            "schema",
            "audit_date",
            "status",
            "hash_algorithm",
            "claim_boundary",
            "entries",
            "aggregate",
            "validation",
            "artifacts",
        )
    }


def verification_details(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    expected_entries = {entry.get("path"): entry for entry in expected.get("entries", [])}
    actual_entries = {entry.get("path"): entry for entry in actual.get("entries", [])}
    expected_paths = set(expected_entries)
    actual_paths = set(actual_entries)
    digest_mismatches = []
    mode_mismatches = []
    for path in sorted(expected_paths & actual_paths):
        expected_entry = expected_entries[path]
        actual_entry = actual_entries[path]
        if expected_entry.get("sha256") != actual_entry.get("sha256"):
            digest_mismatches.append(
                {
                    "path": path,
                    "expected": expected_entry.get("sha256"),
                    "actual": actual_entry.get("sha256"),
                }
            )
        if expected_entry.get("digest_mode") != actual_entry.get("digest_mode"):
            mode_mismatches.append(
                {
                    "path": path,
                    "expected": expected_entry.get("digest_mode"),
                    "actual": actual_entry.get("digest_mode"),
                }
            )

    expected_top = comparable_manifest(expected)
    actual_top = comparable_manifest(actual)
    metadata_mismatches = [
        key
        for key in expected_top
        if key != "entries" and expected_top.get(key) != actual_top.get(key)
    ]
    return {
        "missing_paths": sorted(expected_paths - actual_paths),
        "unexpected_paths": sorted(actual_paths - expected_paths),
        "digest_mismatches": digest_mismatches,
        "mode_mismatches": mode_mismatches,
        "metadata_mismatches": metadata_mismatches,
    }


def verify_manifest(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    manifest_path = output_dir / "release_manifest.json"
    expected = compute_manifest(output_dir)
    if not manifest_path.exists():
        return {
            "schema": "worldepisode_release_manifest_verification_v1",
            "status": "fail",
            "manifest": rel(manifest_path),
            "validation": {
                "passed": False,
                "error": "release manifest is missing",
            },
        }
    actual = json.loads(manifest_path.read_text(encoding="utf-8"))
    details = verification_details(expected, actual)
    passed = comparable_manifest(expected) == comparable_manifest(actual)
    return {
        "schema": "worldepisode_release_manifest_verification_v1",
        "status": "pass" if passed else "fail",
        "manifest": rel(manifest_path),
        "aggregate": {
            "expected_entry_count": len(expected.get("entries", [])),
            "actual_entry_count": len(actual.get("entries", [])),
            "digest_mismatch_count": len(details["digest_mismatches"]),
            "metadata_mismatch_count": len(details["metadata_mismatches"]),
        },
        "validation": {
            "passed": passed,
            **details,
        },
    }


def render_markdown(manifest: dict[str, Any]) -> str:
    rows = [
        (
            f"| `{entry['path']}` | {entry['category']} | {entry['digest_mode']} | "
            f"`{entry['sha256'][:16] if entry.get('sha256') else ''}` |"
        )
        for entry in manifest["entries"]
    ]
    return f"""# Release Manifest

Status: `{manifest["status"]}`.

{manifest["claim_boundary"]}

## Summary

- Entries: {manifest["aggregate"]["entry_count"]}
- Public evidence artifacts: {manifest["aggregate"]["public_evidence_count"]}
- Release scripts: {manifest["aggregate"]["release_script_count"]}
- Normalized timing digests: {manifest["aggregate"]["normalized_digest_count"]}
- Missing artifacts: {manifest["aggregate"]["missing_count"]}
- Empty artifacts: {manifest["aggregate"]["empty_count"]}
- Generate: `{manifest["commands"]["generate"]}`
- Verify without rewriting: `{manifest["commands"]["verify"]}`

## Entries

| Path | Category | Digest Mode | SHA-256 Prefix |
|---|---|---|---|
{chr(10).join(rows)}

## Validation

- Passed: `{manifest["validation"]["passed"]}`
- Missing: `{manifest["validation"]["missing"]}`
- Empty: `{manifest["validation"]["empty"]}`
- Duplicate paths: `{manifest["validation"]["duplicate_paths"]}`
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--verify", action="store_true", help="verify the committed manifest without rewriting it")
    parser.add_argument("--strict", action="store_true", help="exit non-zero unless manifest validates")
    args = parser.parse_args()
    if args.verify:
        verification = verify_manifest(args.output_dir)
        print(json.dumps(verification, indent=2, sort_keys=True))
        if args.strict and verification["status"] != "pass":
            return 1
        return 0

    manifest = build_manifest(args.output_dir)
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "aggregate": manifest["aggregate"],
                "validation": manifest["validation"],
                "artifacts": manifest["artifacts"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if args.strict and manifest["status"] != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
