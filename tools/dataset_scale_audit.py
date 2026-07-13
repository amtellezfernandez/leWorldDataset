#!/usr/bin/env python3
"""Audit production-scale WorldEpisode dataset manifest invariants.

This is not a distributed-systems benchmark. It checks whether a dataset-scale manifest has the
catalog structure needed for large corpora: globally scoped namespaces, resolver coverage for asset
URIs, digest-verified assets with optional local mirrors, shard/index references, split and lineage
indexes, and append-only release snapshots.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "examples" / "scalable-corpus.worldepisode-dataset.json"
SCHEMA_PATH = ROOT / "schemas" / "worldepisode-dataset-v0.schema.json"
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "experiments" / "dataset_scale_audit"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def uri_scheme(uri: str) -> str:
    parsed = urlparse(uri)
    if parsed.scheme:
        return parsed.scheme
    return "relative"


def collect_assets(manifest: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    assets: list[tuple[str, dict[str, Any]]] = []
    for collection_name in ("registries", "shards", "indexes"):
        for item in manifest.get(collection_name, []):
            item_id = (
                item.get("registry_id")
                or item.get("shard_id")
                or item.get("index_id")
                or "<unknown>"
            )
            assets.append((f"{collection_name}.{item_id}.asset", item["asset"]))
    for version in manifest.get("versions", []):
        location = f"versions.{version.get('version_id', '<unknown>')}.snapshot_manifest"
        assets.append((location, version["snapshot_manifest"]))
    return assets


def duplicate_values(values: list[str]) -> list[str]:
    return sorted({value for value in values if values.count(value) > 1})


def fail(check_id: str, message: str, severity: str = "error") -> dict[str, str]:
    return {"check_id": check_id, "severity": severity, "message": message}


def audit_dataset_manifest(
    manifest_path: Path = DEFAULT_MANIFEST,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    schema = load_json(SCHEMA_PATH)
    schema_validator = jsonschema.Draft202012Validator(schema)
    diagnostics: list[dict[str, str]] = []

    schema_errors = sorted(schema_validator.iter_errors(manifest), key=lambda error: list(error.path))
    for error in schema_errors:
        location = ".".join(str(part) for part in error.path) or "<root>"
        diagnostics.append(fail("SCALE.SCHEMA", f"{location}: {error.message}"))

    namespace_prefixes = [item["prefix"] for item in manifest.get("namespaces", [])]
    resolver_schemes = [item["scheme"] for item in manifest.get("resolvers", [])]
    registry_ids = [item["registry_id"] for item in manifest.get("registries", [])]
    shard_ids = [item["shard_id"] for item in manifest.get("shards", [])]
    index_ids = [item["index_id"] for item in manifest.get("indexes", [])]
    version_ids = [item["version_id"] for item in manifest.get("versions", [])]

    for label, values in (
        ("namespace prefix", namespace_prefixes),
        ("resolver scheme", resolver_schemes),
        ("registry id", registry_ids),
        ("shard id", shard_ids),
        ("index id", index_ids),
        ("version id", version_ids),
    ):
        duplicates = duplicate_values(values)
        if duplicates:
            diagnostics.append(fail("SCALE.ID.UNIQUE", f"duplicate {label}(s): {', '.join(duplicates)}"))

    resolver_set = set(resolver_schemes)
    asset_refs = collect_assets(manifest)
    asset_schemes = sorted({uri_scheme(asset["uri"]) for _, asset in asset_refs})
    assets_with_mirrors = [location for location, asset in asset_refs if asset.get("mirrors")]
    mirror_count = sum(len(asset.get("mirrors", [])) for _, asset in asset_refs)
    missing_resolvers = sorted(scheme for scheme in asset_schemes if scheme not in resolver_set)
    if missing_resolvers:
        diagnostics.append(
            fail(
                "SCALE.RESOLVER.COVERAGE",
                "asset URI scheme(s) without manifest resolver: " + ", ".join(missing_resolvers),
            )
        )

    assets_without_mirrors = [location for location, asset in asset_refs if not asset.get("mirrors")]
    if assets_without_mirrors:
        diagnostics.append(
            fail(
                "SCALE.ASSET.MIRROR",
                "asset(s) missing optional local mirror declaration: " + ", ".join(assets_without_mirrors),
                severity="warning",
            )
        )

    missing_digest_fields = [
        location
        for location, asset in asset_refs
        if not asset.get("uri") or not asset.get("media_type") or not asset.get("sha256")
    ]
    if missing_digest_fields:
        diagnostics.append(
            fail(
                "SCALE.ASSET.DESCRIPTOR",
                "asset(s) missing uri/media_type/sha256 descriptor: " + ", ".join(missing_digest_fields),
            )
        )

    addressable_ids = set(registry_ids) | set(shard_ids)
    bad_covers = []
    for index in manifest.get("indexes", []):
        for covered_id in index.get("covers", []):
            if covered_id not in addressable_ids:
                bad_covers.append(f"{index['index_id']}->{covered_id}")
    if bad_covers:
        diagnostics.append(
            fail(
                "SCALE.INDEX.COVERS",
                "index covers unknown registry/shard id(s): " + ", ".join(sorted(bad_covers)),
            )
        )

    index_kinds = {index["kind"] for index in manifest.get("indexes", [])}
    required_index_kinds = {"world_lineage", "asset_digest"}
    missing_index_kinds = sorted(required_index_kinds - index_kinds)
    if missing_index_kinds:
        diagnostics.append(
            fail("SCALE.INDEX.REQUIRED", "missing required index kind(s): " + ", ".join(missing_index_kinds))
        )

    shard_kinds = {shard["kind"] for shard in manifest.get("shards", [])}
    if "split_manifest" not in shard_kinds:
        diagnostics.append(fail("SCALE.SPLIT.MANIFEST", "missing split_manifest shard"))

    trace_partition_failures = []
    trace_column_failures = []
    for shard in manifest.get("shards", []):
        if shard["kind"] != "episode_trace":
            continue
        partition = shard.get("partition", {})
        if "split" not in partition or not ({"task_id", "embodiment_id"} & set(partition)):
            trace_partition_failures.append(shard["shard_id"])
        columns = set(shard.get("columns", []))
        if not {"episode_id", "world_revision_id"} <= columns:
            trace_column_failures.append(shard["shard_id"])
    if trace_partition_failures:
        diagnostics.append(
            fail(
                "SCALE.SHARD.PARTITION",
                "episode_trace shard(s) missing split plus task/embodiment partition: "
                + ", ".join(trace_partition_failures),
            )
        )
    if trace_column_failures:
        diagnostics.append(
            fail(
                "SCALE.SHARD.COLUMNS",
                "episode_trace shard(s) missing episode_id/world_revision_id columns: "
                + ", ".join(trace_column_failures),
            )
        )

    parent_failures = []
    known_versions: set[str] = set()
    root_versions = 0
    for version in manifest.get("versions", []):
        parent = version.get("parent_version_id")
        if parent:
            if parent not in known_versions:
                parent_failures.append(f"{version['version_id']}->{parent}")
        else:
            root_versions += 1
        known_versions.add(version["version_id"])
    if parent_failures:
        diagnostics.append(
            fail(
                "SCALE.VERSION.PARENT",
                "version parent must reference an earlier append-only snapshot: " + ", ".join(parent_failures),
            )
        )
    if root_versions != 1:
        diagnostics.append(
            fail("SCALE.VERSION.ROOT", f"expected exactly one root version, found {root_versions}")
        )

    errors = [diagnostic for diagnostic in diagnostics if diagnostic["severity"] == "error"]
    warnings = [diagnostic for diagnostic in diagnostics if diagnostic["severity"] == "warning"]
    report = {
        "profile": "worldepisode-dataset-scale-audit-0.1",
        "manifest": str(manifest_path.relative_to(ROOT)),
        "schema": str(SCHEMA_PATH.relative_to(ROOT)),
        "status": "pass" if not errors else "fail",
        "pass": not errors,
        "diagnostics": diagnostics,
        "aggregate": {
            "namespace_count": len(namespace_prefixes),
            "resolver_count": len(resolver_schemes),
            "registry_count": len(registry_ids),
            "shard_count": len(shard_ids),
            "index_count": len(index_ids),
            "version_count": len(version_ids),
            "asset_descriptor_count": len(asset_refs),
            "assets_with_local_mirrors": len(assets_with_mirrors),
            "local_mirror_count": mirror_count,
            "asset_uri_schemes": asset_schemes,
            "warning_count": len(warnings),
            "error_count": len(errors),
            "has_world_lineage_index": "world_lineage" in index_kinds,
            "has_asset_digest_index": "asset_digest" in index_kinds,
            "has_split_manifest_shard": "split_manifest" in shard_kinds,
        },
        "claim_boundary": (
            "This audit validates catalog invariants for scalable manifests. It is not a "
            "billion-episode latency, cache, or federation benchmark."
        ),
        "artifacts": {
            "report": str((output_dir / "scale_audit_report.json").relative_to(ROOT)),
            "markdown": str((output_dir / "README.md").relative_to(ROOT)),
        },
    }
    write_json(output_dir / "scale_audit_report.json", report)
    write_text(output_dir / "README.md", render_markdown(report))
    return report


def render_markdown(report: dict[str, Any]) -> str:
    aggregate = report["aggregate"]
    diagnostic_rows = []
    for diagnostic in report["diagnostics"]:
        diagnostic_rows.append(
            "| {check_id} | {severity} | {message} |".format(
                check_id=diagnostic["check_id"],
                severity=diagnostic["severity"],
                message=diagnostic["message"].replace("|", "\\|"),
            )
        )
    if not diagnostic_rows:
        diagnostic_rows.append("| none | none | no diagnostics |")
    schemes = ", ".join(aggregate["asset_uri_schemes"])
    return f"""# Dataset-Scale Manifest Audit

Status: {report["status"]}

This artifact checks the production-scale manifest structure. It proves only catalog invariants,
not distributed performance.

- Manifest: `{report["manifest"]}`
- Namespaces: {aggregate["namespace_count"]}
- Resolvers: {aggregate["resolver_count"]}
- Registries: {aggregate["registry_count"]}
- Shards: {aggregate["shard_count"]}
- Indexes: {aggregate["index_count"]}
- Versions: {aggregate["version_count"]}
- Asset descriptors: {aggregate["asset_descriptor_count"]}
- Assets with local mirrors: {aggregate["assets_with_local_mirrors"]}
- Local mirror entries: {aggregate["local_mirror_count"]}
- Asset URI schemes: {schemes}
- World-lineage index: {aggregate["has_world_lineage_index"]}
- Asset-digest index: {aggregate["has_asset_digest_index"]}
- Split manifest shard: {aggregate["has_split_manifest_shard"]}

| Check | Severity | Message |
|---|---|---|
{chr(10).join(diagnostic_rows)}

Boundary: {report["claim_boundary"]}
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    report = audit_dataset_manifest(args.manifest, args.output_dir)
    print(json.dumps({"pass": report["pass"], **report["aggregate"]}, indent=2, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
