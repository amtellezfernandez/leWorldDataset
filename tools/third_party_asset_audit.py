#!/usr/bin/env python3
"""Audit third-party datasets, redistributed rows, software, and paper assets."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from dataset_license_registry import (
        DATASET_LICENSE_RECORDS,
        license_record,
        source_license_payload,
    )
except ImportError:  # Imported as tools.third_party_asset_audit in tests.
    from tools.dataset_license_registry import (
        DATASET_LICENSE_RECORDS,
        license_record,
        source_license_payload,
    )


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT_MANIFEST = (
    ROOT / "docs" / "experiments" / "experiment_manifest" / "experiment_manifest.json"
)
EXPERIMENT_ROOT = ROOT / "docs" / "experiments"
OUTPUT_DIR = EXPERIMENT_ROOT / "third_party_asset_audit"
REPORT_PATH = OUTPUT_DIR / "asset_audit.json"
README_PATH = OUTPUT_DIR / "README.md"
NOTICE_PATH = ROOT / "THIRD_PARTY_ASSETS.md"
STYLE_PATH = ROOT / "paper" / "arxiv" / "neurips_2026.sty"
STYLE_SHA256 = "c3fc2894e83d2517ca18b66741d6c595986d97957dc08ec08bb2125a7ec4555a"
MIT_NOTICE_PATH = ROOT / "third_party_licenses" / "pusht-MIT.txt"
LICENSE_README_PATH = ROOT / "third_party_licenses" / "README.md"
SCHEMA = "worldepisode_third_party_asset_audit_v1"

MEDIA_SUFFIXES = {
    ".avi",
    ".jpeg",
    ".jpg",
    ".mkv",
    ".mov",
    ".mp4",
    ".png",
    ".webm",
}

AUTHORED_PARQUET_FIXTURES = {
    "docs/experiments/preflight/native_lerobot_without_sidecar/data/chunk-000/file-000.parquet": {
        "sha256": "fbc62d3b511368ee275ddc74117d8689b430e1427220e25d30816201d89ca7b6",
        "purpose": "four-byte PAR1 sentinel used to test fail-closed preflight",
        "license_expression": "CC0-1.0",
    }
}

EXTERNAL_SOFTWARE = (
    {
        "name": "LeRobot",
        "license_expression": "Apache-2.0",
        "source": "https://github.com/huggingface/lerobot",
        "use": "dataset conventions and public dataset mirrors; not vendored",
    },
    {
        "name": "MuJoCo",
        "license_expression": "Apache-2.0",
        "source": "https://github.com/google-deepmind/mujoco",
        "use": "runtime replay experiment; installed dependency, not vendored",
    },
    {
        "name": "Genesis",
        "license_expression": "Apache-2.0",
        "source": "https://github.com/Genesis-Embodied-AI/Genesis",
        "use": "runtime replay experiment; installed dependency, not vendored",
    },
    {
        "name": "PyArrow",
        "license_expression": "Apache-2.0",
        "source": "https://github.com/apache/arrow",
        "use": "Parquet experiment I/O; installed dependency, not vendored",
    },
    {
        "name": "scikit-learn",
        "license_expression": "BSD-3-Clause",
        "source": "https://github.com/scikit-learn/scikit-learn",
        "use": "controlled baselines; installed dependency, not vendored",
    },
    {
        "name": "PyTorch",
        "license_expression": "BSD-3-Clause",
        "source": "https://github.com/pytorch/pytorch",
        "use": "MLP experiment; installed dependency, not vendored",
    },
)

CONTEXT_ONLY_DATASETS = (
    {
        "name": "BridgeData V2",
        "license_expression": "CC-BY-4.0",
        "source": "https://rail-berkeley.github.io/bridgedata/",
        "use": "related-work and source-level audit only; no rows or media redistributed",
    },
    {
        "name": "Open X-Embodiment",
        "license_expression": "dataset-specific",
        "source": "https://robotics-transformer-x.github.io/",
        "use": "related-work and source-level audit only; no component dataset redistributed",
    },
    {
        "name": "LIBERO",
        "license_expression": "MIT (source code)",
        "source": "https://github.com/Lifelong-Robot-Learning/LIBERO",
        "use": "source-level benchmark audit only; no code, rows, or media redistributed",
    },
    {
        "name": "CALVIN",
        "license_expression": "MIT (source code)",
        "source": "https://github.com/mees/calvin",
        "use": "source-level benchmark audit only; no code, rows, or media redistributed",
    },
)


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def active_dataset_uses() -> dict[tuple[str, str], list[str]]:
    manifest = load_json(EXPERIMENT_MANIFEST)
    uses: dict[tuple[str, str], list[str]] = {}
    for experiment in manifest.get("experiments", []):
        for dataset in experiment.get("datasets", []):
            key = (dataset["repo_id"], dataset["revision"])
            uses.setdefault(key, []).append(experiment["experiment_id"])
    return {key: sorted(set(value)) for key, value in sorted(uses.items())}


def nearest_license_file(path: Path) -> Path | None:
    for parent in path.parents:
        if parent == EXPERIMENT_ROOT.parent:
            break
        candidate = parent / "SOURCE_LICENSE.json"
        if candidate.is_file():
            return candidate
    return None


def validate_source_payload(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    try:
        payload = load_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        return None, [f"{relative(path)}: invalid source-license JSON: {exc}"]
    try:
        expected = source_license_payload(
            license_record(payload["repo_id"], payload["revision"])
        )
    except (KeyError, ValueError) as exc:
        return payload, [f"{relative(path)}: {exc}"]
    if payload != expected:
        errors.append(f"{relative(path)}: source-license payload differs from registry")
    return payload, errors


def redistributed_artifacts() -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[str],
]:
    errors: list[str] = []
    rows = []
    authored_fixtures = []
    for path in sorted(EXPERIMENT_ROOT.rglob("*.parquet")):
        rel_path = relative(path)
        if rel_path in AUTHORED_PARQUET_FIXTURES:
            expected = AUTHORED_PARQUET_FIXTURES[rel_path]
            actual_sha256 = sha256_file(path)
            if actual_sha256 != expected["sha256"]:
                errors.append(
                    f"{rel_path}: authored fixture digest mismatch; "
                    f"expected {expected['sha256']}, got {actual_sha256}"
                )
            authored_fixtures.append(
                {
                    "path": rel_path,
                    "bytes": path.stat().st_size,
                    "sha256": actual_sha256,
                    "purpose": expected["purpose"],
                    "license_expression": expected["license_expression"],
                }
            )
            continue
        license_path = nearest_license_file(path)
        row: dict[str, Any] = {
            "path": rel_path,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "source_license_file": relative(license_path) if license_path else None,
        }
        if license_path is None:
            errors.append(f"{rel_path}: no enclosing SOURCE_LICENSE.json")
        else:
            payload, payload_errors = validate_source_payload(license_path)
            errors.extend(payload_errors)
            if payload is not None:
                row["repo_id"] = payload.get("repo_id")
                row["revision"] = payload.get("revision")
                row["license_expression"] = payload.get("license_expression")
        rows.append(row)
    missing_authored_fixtures = sorted(
        set(AUTHORED_PARQUET_FIXTURES)
        - {item["path"] for item in authored_fixtures}
    )
    errors.extend(
        f"missing authored Parquet fixture: {path}"
        for path in missing_authored_fixtures
    )
    return rows, authored_fixtures, errors


def source_license_files() -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    records = []
    for path in sorted(EXPERIMENT_ROOT.rglob("SOURCE_LICENSE.json")):
        payload, payload_errors = validate_source_payload(path)
        errors.extend(payload_errors)
        records.append(
            {
                "path": relative(path),
                "repo_id": payload.get("repo_id") if payload else None,
                "revision": payload.get("revision") if payload else None,
                "license_expression": (
                    payload.get("license_expression") if payload else None
                ),
            }
        )
    return records, errors


def build_report() -> dict[str, Any]:
    errors: list[str] = []
    uses = active_dataset_uses()
    datasets = []
    for repo_id, revision in uses:
        try:
            record = license_record(repo_id, revision)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        datasets.append(
            {
                **source_license_payload(record),
                "experiment_ids": uses[(repo_id, revision)],
            }
        )
    unused_registry_records = sorted(
        f"{repo_id}@{revision}"
        for repo_id, revision in set(DATASET_LICENSE_RECORDS) - set(uses)
    )
    if unused_registry_records:
        errors.extend(
            f"dataset license registry entry has no active experiment: {item}"
            for item in unused_registry_records
        )

    redistributed, authored_fixtures, redistributed_errors = redistributed_artifacts()
    errors.extend(redistributed_errors)
    source_licenses, source_license_errors = source_license_files()
    errors.extend(source_license_errors)
    if redistributed and not source_licenses:
        errors.append("redistributed source rows exist but no SOURCE_LICENSE.json files exist")

    media = [
        relative(path)
        for path in sorted(EXPERIMENT_ROOT.rglob("*"))
        if path.is_file() and path.suffix.lower() in MEDIA_SUFFIXES
    ]
    if media:
        errors.extend(f"source media is redistributed: {path}" for path in media)

    style_actual = sha256_file(STYLE_PATH) if STYLE_PATH.is_file() else None
    if style_actual != STYLE_SHA256:
        errors.append(
            "paper/arxiv/neurips_2026.sty: expected official author-kit digest "
            f"{STYLE_SHA256}, got {style_actual}"
        )
    if not MIT_NOTICE_PATH.is_file():
        errors.append(f"missing third-party license text: {relative(MIT_NOTICE_PATH)}")
    if not LICENSE_README_PATH.is_file():
        errors.append(f"missing third-party license index: {relative(LICENSE_README_PATH)}")

    return {
        "schema": SCHEMA,
        "scope": (
            "Third-party datasets named by the experiment manifest, source-derived Parquet "
            "files distributed under docs/experiments, directly used external software, "
            "context-only benchmark datasets, and the vendored NeurIPS style file. This is "
            "a provenance and notice audit, not legal advice or legal clearance."
        ),
        "active_datasets": datasets,
        "redistributed_source_rows": redistributed,
        "authored_parquet_fixtures": authored_fixtures,
        "source_license_files": source_licenses,
        "external_software": list(EXTERNAL_SOFTWARE),
        "context_only_datasets": list(CONTEXT_ONLY_DATASETS),
        "vendored_assets": [
            {
                "path": relative(STYLE_PATH),
                "sha256": style_actual,
                "expected_sha256": STYLE_SHA256,
                "source": "official NeurIPS 2026 author kit",
                "source_url": "https://neurips.cc/Conferences/2026/PaperInformation/StyleFiles",
                "license_expression": "NOASSERTION",
                "terms": (
                    "Conference-provided submission style required to compile the paper; "
                    "no separate SPDX or license statement was present in the distributed file."
                ),
            }
        ],
        "redistribution_policy": {
            "source_rows": (
                "Source-derived rows retain the source dataset license expression and an "
                "adjacent SOURCE_LICENSE.json."
            ),
            "worldepisode_metadata": (
                "WorldEpisode-authored manifests, diagnostics, and aggregate reports are "
                "CC0-1.0 unless a file says otherwise."
            ),
            "source_media_included": False,
        },
        "aggregate": {
            "active_dataset_count": len(datasets),
            "redistributed_parquet_count": len(redistributed),
            "redistributed_parquet_bytes": sum(item["bytes"] for item in redistributed),
            "authored_parquet_fixture_count": len(authored_fixtures),
            "source_license_file_count": len(source_licenses),
            "source_media_count": len(media),
            "external_software_count": len(EXTERNAL_SOFTWARE),
            "context_only_dataset_count": len(CONTEXT_ONLY_DATASETS),
            "error_count": len(errors),
        },
        "validation": {
            "passed": not errors,
            "errors": errors,
        },
        "artifacts": {
            "json": relative(REPORT_PATH),
            "markdown": relative(README_PATH),
            "notice": relative(NOTICE_PATH),
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    dataset_rows = "\n".join(
        "| `{repo_id}` | `{revision}` | `{license_expression}` | {uses} |".format(
            repo_id=item["repo_id"],
            revision=item["revision"],
            license_expression=item["license_expression"],
            uses=", ".join(f"`{value}`" for value in item["experiment_ids"]),
        )
        for item in report["active_datasets"]
    )
    software_rows = "\n".join(
        f"| {item['name']} | `{item['license_expression']}` | {item['use']} |"
        for item in report["external_software"]
    )
    context_rows = "\n".join(
        f"| {item['name']} | `{item['license_expression']}` | {item['use']} |"
        for item in report["context_only_datasets"]
    )
    errors = report["validation"]["errors"]
    error_text = "\n".join(f"- {error}" for error in errors) if errors else "- None"
    return f"""# Third-Party Asset Audit

Status: `{"pass" if report["validation"]["passed"] else "fail"}`.

{report["scope"]}

## Active Datasets

| Dataset | Pinned revision | License expression | Experiments |
|---|---|---|---|
{dataset_rows}

## Redistributed Rows

- Parquet files: {report["aggregate"]["redistributed_parquet_count"]}
- Parquet bytes: {report["aggregate"]["redistributed_parquet_bytes"]}
- First-party Parquet sentinels: {report["aggregate"]["authored_parquet_fixture_count"]}
- Source-license files: {report["aggregate"]["source_license_file_count"]}
- Source media files: {report["aggregate"]["source_media_count"]}

Source-derived rows retain their upstream license expression. Each redistributed Parquet package
must contain an adjacent `SOURCE_LICENSE.json`. WorldEpisode-authored manifests, diagnostics, and
aggregate reports are CC0-1.0 unless a file says otherwise.

## External Software

| Software | License | Use |
|---|---|---|
{software_rows}

These dependencies are installed from their upstream packages and are not vendored here.

## Context-Only Datasets

| Dataset | License | Use |
|---|---|---|
{context_rows}

## Vendored Submission Asset

`paper/arxiv/neurips_2026.sty` is the official NeurIPS 2026 author-kit style with pinned SHA-256
`{report["vendored_assets"][0]["expected_sha256"]}`. The distributed file contains no separate
SPDX or license statement, so the audit records `NOASSERTION` rather than inventing a license.

## Validation Errors

{error_text}
"""


def render_notice(report: dict[str, Any]) -> str:
    dataset_sections = "\n\n".join(
        "### `{repo_id}@{revision}`\n\n"
        "- License expression: `{license_expression}`\n"
        "- Attribution: {attribution}\n"
        "- Immutable card: {card_url}\n"
        "- Card SHA-256: `{card_sha256}`".format(
            repo_id=item["repo_id"],
            revision=item["revision"],
            license_expression=item["license_expression"],
            attribution=item["attribution"],
            card_url=item["evidence"]["dataset_card"]["url"],
            card_sha256=item["evidence"]["dataset_card"]["sha256"],
        )
        for item in report["active_datasets"]
    )
    software_lines = "\n".join(
        f"- [{item['name']}]({item['source']}): `{item['license_expression']}`; {item['use']}."
        for item in report["external_software"]
    )
    context_lines = "\n".join(
        f"- [{item['name']}]({item['source']}): `{item['license_expression']}`; {item['use']}."
        for item in report["context_only_datasets"]
    )
    return f"""# Third-Party Assets

This file records the provenance, attribution, and redistribution treatment of third-party assets
used by the WorldEpisode paper and experiments. It is generated by
`tools/third_party_asset_audit.py`. It is not legal advice.

## Experiment Datasets

{dataset_sections}

Source-derived rows retain the listed source license expression. Redistributed LeRobot-style
packages carry `SOURCE_LICENSE.json`. WorldEpisode-authored manifests, diagnostics, and aggregate
reports are CC0-1.0 unless a file says otherwise. No source videos or images are redistributed.
The Apache-2.0 text is in `LICENSE-APACHE`; the PushT MIT notice is in
`third_party_licenses/pusht-MIT.txt`. DROID attribution and CC-BY-4.0 evidence are retained even
though the supplement distributes aggregate rerun results rather than DROID rows.

## External Software

{software_lines}

These packages are installed dependencies and are not vendored in the supplement.

## Context-Only Datasets

{context_lines}

## Submission Style

`paper/arxiv/neurips_2026.sty` comes from the official NeurIPS 2026 author kit and is required to
compile the submission. Its pinned SHA-256 is
`{report["vendored_assets"][0]["expected_sha256"]}`. The distributed style file has no separate
SPDX or license statement, so its license expression is recorded as `NOASSERTION`.
"""


def canonical_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True) + "\n"


def expected_outputs(report: dict[str, Any]) -> dict[Path, str]:
    return {
        REPORT_PATH: canonical_json(report),
        README_PATH: render_markdown(report),
        NOTICE_PATH: render_notice(report),
    }


def write_outputs(report: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path, content in expected_outputs(report).items():
        path.write_text(content, encoding="utf-8")


def check_outputs(report: dict[str, Any]) -> list[str]:
    errors = []
    for path, content in expected_outputs(report).items():
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
    freshness_errors = check_outputs(report) if args.check else []
    if not args.check:
        write_outputs(report)
    print(
        json.dumps(
            {
                "status": "pass" if report["validation"]["passed"] else "fail",
                "aggregate": report["aggregate"],
                "freshness_errors": freshness_errors,
            },
            indent=2,
            sort_keys=True,
        )
    )
    failed = bool(freshness_errors) or not report["validation"]["passed"]
    return 1 if args.strict and failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
