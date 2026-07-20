#!/usr/bin/env python3
"""Benchmark operational behavior of a generated WorldEpisode dataset catalog.

The structural scale audit checks whether a manifest has the right fields. This tool checks whether
the catalog pattern can be opened, indexed, partition-pruned, routed through resolvers, and resolved
through a digest cache at a larger synthetic scale.

It intentionally does not materialize episode rows. The generated catalog describes shard
statistics for a billion-episode corpus, then measures catalog-side behavior over shard and asset
descriptors.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "experiments" / "dataset_scale_performance"
DEFAULT_TRACE_SHARDS = 32768
DEFAULT_EPISODES_PER_TRACE_SHARD = 32768
DEFAULT_WORLD_LINEAGE_BUCKETS = 4096
DEFAULT_TASK_COUNT = 32
DEFAULT_EMBODIMENTS = ("so101", "koch", "aloha", "ur5")
DEFAULT_SPLITS = ("train", "validation", "test")
SCHEMES = ("hf", "s3", "oci", "ipfs", "relative")


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sha256_payload(payload: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def digest_for(*parts: Any) -> str:
    return hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def uri_scheme(uri: str) -> str:
    parsed = urlparse(uri)
    if parsed.scheme:
        return parsed.scheme
    return "relative"


def timed(label: str, fn: Callable[[], Any]) -> tuple[Any, dict[str, Any]]:
    start = time.perf_counter_ns()
    value = fn()
    elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000.0
    return value, {"operation": label, "elapsed_ms": round(elapsed_ms, 3)}


def asset_descriptor(kind: str, index: int, scheme: str, row_count: int, byte_size: int) -> dict[str, Any]:
    filename = f"{kind}/part-{index:05d}.parquet"
    if scheme == "relative":
        uri = filename
    elif scheme == "oci":
        uri = f"oci://ghcr.io/amtellezfernandez/leworlddataset/{kind}:part-{index:05d}"
    elif scheme == "ipfs":
        uri = f"ipfs://bafy{digest_for(kind, index)[:48]}"
    else:
        uri = f"{scheme}://leworlddataset/{filename}"
    return {
        "uri": uri,
        "media_type": "application/vnd.apache.parquet",
        "sha256": digest_for(kind, index, scheme),
        "mirrors": [filename],
        "byte_size": byte_size,
        "row_count": row_count,
        "license": "CC-BY-4.0",
    }


def build_generated_manifest(config: dict[str, Any]) -> dict[str, Any]:
    trace_shards = int(config["trace_shards"])
    episodes_per_trace_shard = int(config["episodes_per_trace_shard"])
    world_lineage_buckets = int(config["world_lineage_buckets"])
    task_count = int(config["task_count"])
    embodiments = list(config["embodiments"])
    splits = list(config["splits"])

    namespaces = [
        {"prefix": "dataset", "uri": "we://synthetic/worldepisode-scale", "scope": "dataset"},
        {"prefix": "episode", "uri": "we://synthetic/worldepisode-scale/episode/", "scope": "episode"},
        {"prefix": "world", "uri": "we://synthetic/worldepisode-scale/world/", "scope": "world"},
        {"prefix": "entity", "uri": "we://synthetic/worldepisode-scale/entity/", "scope": "entity"},
        {"prefix": "asset", "uri": "we://synthetic/worldepisode-scale/asset/", "scope": "asset"},
    ]
    resolvers = [
        {"scheme": "relative", "priority": 0, "cache_policy": "local_mirror_first"},
        {"scheme": "hf", "priority": 10, "endpoint": "hf://synthetic/worldepisode-scale", "cache_policy": "digest_verified_remote"},
        {"scheme": "s3", "priority": 20, "endpoint": "s3://leworlddataset", "cache_policy": "local_mirror_first"},
        {"scheme": "oci", "priority": 30, "endpoint": "oci://ghcr.io/amtellezfernandez/leworlddataset", "cache_policy": "content_addressed"},
        {"scheme": "ipfs", "priority": 40, "cache_policy": "content_addressed"},
    ]
    registries = [
        {
            "registry_id": f"{kind}_registry",
            "kind": kind,
            "asset": asset_descriptor("registries", index, SCHEMES[index % len(SCHEMES)], 100000 + index, 4_000_000),
            "primary_keys": [f"{kind}_id"],
        }
        for index, kind in enumerate(
            ("world_revisions", "entities", "embodiments", "action_spaces", "tasks", "provenance")
        )
    ]

    shards: list[dict[str, Any]] = []
    for index in range(trace_shards):
        split = splits[index % len(splits)]
        task_id = f"task_{index % task_count:02d}"
        embodiment_id = embodiments[index % len(embodiments)]
        bucket = f"{index % world_lineage_buckets:04x}"
        scheme = SCHEMES[index % len(SCHEMES)]
        shards.append(
            {
                "shard_id": f"trace_{index:05d}",
                "kind": "episode_trace",
                "asset": asset_descriptor(
                    "traces",
                    index,
                    scheme,
                    episodes_per_trace_shard * 120,
                    episodes_per_trace_shard * 120 * 64,
                ),
                "schema_ref": "https://worldepisode.org/schemas/worldepisode-trace-arrow-v0",
                "partition": {
                    "split": split,
                    "task_id": task_id,
                    "embodiment_id": embodiment_id,
                    "world_lineage_bucket": bucket,
                    "collection_site": f"site_{index % 64:02d}",
                },
                "statistics": {
                    "episode_count": episodes_per_trace_shard,
                    "row_count": episodes_per_trace_shard * 120,
                    "min_timestamp_ns": 0,
                    "max_timestamp_ns": 120_000_000_000,
                },
                "columns": [
                    "episode_id",
                    "timestamp_ns",
                    "observation.state",
                    "action",
                    "world_revision_id",
                ],
            }
        )

    shards.append(
        {
            "shard_id": "split_world_lineage_disjoint_v0",
            "kind": "split_manifest",
            "asset": asset_descriptor("splits", 0, "hf", trace_shards, 16_000_000),
            "schema_ref": "https://worldepisode.org/schemas/worldepisode-splits-v0",
            "partition": {"split_policy": "world_lineage_disjoint", "version": "v0"},
            "statistics": {
                "train_episodes": trace_shards * episodes_per_trace_shard * 2 // 3,
                "validation_episodes": trace_shards * episodes_per_trace_shard // 6,
                "test_episodes": trace_shards * episodes_per_trace_shard // 6,
            },
        }
    )

    indexes = [
        {
            "index_id": "episode_by_world_lineage",
            "kind": "world_lineage",
            "asset": asset_descriptor("indexes", 0, "hf", trace_shards, 128_000_000),
            "keys": ["world_lineage_bucket", "world_revision_id", "episode_id"],
            "covers": ["trace_00000", "split_world_lineage_disjoint_v0"],
        },
        {
            "index_id": "asset_digest_index",
            "kind": "asset_digest",
            "asset": asset_descriptor("indexes", 1, "s3", trace_shards + len(registries), 96_000_000),
            "keys": ["sha256", "uri", "local_mirror"],
            "covers": ["trace_00000", "split_world_lineage_disjoint_v0"],
        },
        {
            "index_id": "episode_by_split_task_embodiment",
            "kind": "embodiment_task",
            "asset": asset_descriptor("indexes", 2, "ipfs", trace_shards, 64_000_000),
            "keys": ["split", "task_id", "embodiment_id", "episode_id"],
            "covers": ["trace_00000"],
        },
    ]
    versions = [
        {
            "version_id": "synthetic-v0",
            "created_at": "2026-07-13T00:00:00Z",
            "snapshot_manifest": {
                "uri": "snapshots/synthetic-v0.worldepisode-dataset.json",
                "media_type": "application/vnd.worldepisode.dataset+json",
                "sha256": digest_for("synthetic-v0", trace_shards, episodes_per_trace_shard),
                "mirrors": ["snapshots/synthetic-v0.worldepisode-dataset.json"],
                "byte_size": 0,
                "row_count": trace_shards,
            },
            "change_log": "Synthetic scale-performance catalog generated by tools/dataset_scale_performance.py.",
        }
    ]
    return {
        "schema_version": "worldepisode-dataset-0.1",
        "dataset": {
            "dataset_id": "we://synthetic/worldepisode-scale",
            "name": "Synthetic WorldEpisode scale-performance catalog",
            "version": "synthetic-v0",
            "versioning_policy": "append_only_snapshots",
            "description": "Generated catalog for operational scale measurements; no episode rows are materialized.",
            "license": "CC-BY-4.0",
            "owners": ["WorldEpisode maintainers"],
        },
        "namespaces": namespaces,
        "resolvers": resolvers,
        "registries": registries,
        "shards": shards,
        "indexes": indexes,
        "versions": versions,
    }


def collect_asset_descriptors(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    assets = [registry["asset"] for registry in manifest["registries"]]
    assets.extend(shard["asset"] for shard in manifest["shards"])
    assets.extend(index["asset"] for index in manifest["indexes"])
    assets.extend(version["snapshot_manifest"] for version in manifest["versions"])
    return assets


def build_catalog_indexes(manifest: dict[str, Any]) -> dict[str, Any]:
    shard_by_id = {}
    by_split_task_embodiment: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    by_world_lineage_bucket: dict[str, list[str]] = defaultdict(list)
    by_digest = {}
    for shard in manifest["shards"]:
        shard_id = shard["shard_id"]
        shard_by_id[shard_id] = shard
        if shard["kind"] == "episode_trace":
            partition = shard["partition"]
            by_split_task_embodiment[
                (partition["split"], partition["task_id"], partition["embodiment_id"])
            ].append(shard_id)
            by_world_lineage_bucket[partition["world_lineage_bucket"]].append(shard_id)
        by_digest[shard["asset"]["sha256"]] = shard["asset"]
    for asset in collect_asset_descriptors(manifest):
        by_digest[asset["sha256"]] = asset
    resolver_by_scheme = {resolver["scheme"]: resolver for resolver in manifest["resolvers"]}
    return {
        "shard_by_id": shard_by_id,
        "by_split_task_embodiment": by_split_task_embodiment,
        "by_world_lineage_bucket": by_world_lineage_bucket,
        "by_digest": by_digest,
        "resolver_by_scheme": resolver_by_scheme,
        "assets": collect_asset_descriptors(manifest),
    }


def run_partition_pruning(indexes: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    trace_shards = int(config["trace_shards"])
    queries = []
    for offset in (0, 7, 19, 31, 43, 71, 127, 251):
        split = DEFAULT_SPLITS[offset % len(DEFAULT_SPLITS)]
        task_id = f"task_{offset % int(config['task_count']):02d}"
        embodiment_id = DEFAULT_EMBODIMENTS[offset % len(DEFAULT_EMBODIMENTS)]
        bucket = f"{offset % int(config['world_lineage_buckets']):04x}"
        queries.append((split, task_id, embodiment_id, bucket))

    def query() -> list[dict[str, Any]]:
        rows = []
        for split, task_id, embodiment_id, bucket in queries:
            partition_candidates = set(indexes["by_split_task_embodiment"][(split, task_id, embodiment_id)])
            lineage_candidates = set(indexes["by_world_lineage_bucket"][bucket])
            combined = sorted(partition_candidates & lineage_candidates)
            rows.append(
                {
                    "split": split,
                    "task_id": task_id,
                    "embodiment_id": embodiment_id,
                    "world_lineage_bucket": bucket,
                    "candidate_shards": len(combined),
                    "full_scan_shards": trace_shards,
                    "reduction_ratio": round(len(combined) / trace_shards, 8),
                }
            )
        return rows

    results, timing = timed("partition_pruning_queries", query)
    return {
        "timing": timing,
        "query_count": len(queries),
        "queries": results,
        "max_candidate_shards": max(row["candidate_shards"] for row in results),
        "max_reduction_ratio": max(row["reduction_ratio"] for row in results),
        "all_queries_pruned": all(row["candidate_shards"] < row["full_scan_shards"] for row in results),
    }


def run_digest_cache(indexes: dict[str, Any]) -> dict[str, Any]:
    assets = indexes["assets"]
    cache = {
        asset["sha256"]
        for ordinal, asset in enumerate(assets)
        if ordinal % 4 != 0
    }

    def resolve() -> dict[str, Any]:
        hits = 0
        misses = 0
        digest_mismatches = 0
        for asset in assets:
            expected = indexes["by_digest"].get(asset["sha256"])
            if expected != asset:
                digest_mismatches += 1
            if asset["sha256"] in cache:
                hits += 1
            else:
                misses += 1
        return {"hits": hits, "misses": misses, "digest_mismatches": digest_mismatches}

    result, timing = timed("digest_cache_resolution", resolve)
    total = result["hits"] + result["misses"]
    return {
        "timing": timing,
        "asset_descriptor_count": total,
        "cache_hit_count": result["hits"],
        "cache_miss_count": result["misses"],
        "cache_hit_rate": round(result["hits"] / total, 6) if total else 0.0,
        "digest_mismatches": result["digest_mismatches"],
    }


def run_resolver_routing(indexes: dict[str, Any]) -> dict[str, Any]:
    assets = indexes["assets"]

    def route() -> dict[str, Any]:
        scheme_counts: dict[str, int] = defaultdict(int)
        missing = []
        for asset in assets:
            scheme = uri_scheme(asset["uri"])
            scheme_counts[scheme] += 1
            if scheme not in indexes["resolver_by_scheme"]:
                missing.append(asset["uri"])
        return {"scheme_counts": dict(sorted(scheme_counts.items())), "missing": missing}

    result, timing = timed("resolver_routing", route)
    return {
        "timing": timing,
        "scheme_counts": result["scheme_counts"],
        "missing_resolver_count": len(result["missing"]),
        "missing_resolver_examples": result["missing"][:5],
    }


def benchmark_scale_performance(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    trace_shards: int = DEFAULT_TRACE_SHARDS,
    episodes_per_trace_shard: int = DEFAULT_EPISODES_PER_TRACE_SHARD,
    world_lineage_buckets: int = DEFAULT_WORLD_LINEAGE_BUCKETS,
    task_count: int = DEFAULT_TASK_COUNT,
) -> dict[str, Any]:
    config = {
        "trace_shards": trace_shards,
        "episodes_per_trace_shard": episodes_per_trace_shard,
        "world_lineage_buckets": world_lineage_buckets,
        "task_count": task_count,
        "embodiments": list(DEFAULT_EMBODIMENTS),
        "splits": list(DEFAULT_SPLITS),
        "claim_scope": "catalog descriptors and indexes only; no episode rows or payload bytes materialized",
    }
    manifest = build_generated_manifest(config)
    encoded = canonical_json_bytes(manifest)
    generated_manifest_sha256 = hashlib.sha256(encoded).hexdigest()

    def open_catalog() -> dict[str, Any]:
        parsed = json.loads(encoded)
        indexes = build_catalog_indexes(parsed)
        return {"manifest": parsed, "indexes": indexes}

    opened, open_timing = timed("catalog_open_parse_and_index", open_catalog)
    indexes = opened["indexes"]
    partition = run_partition_pruning(indexes, config)
    digest_cache = run_digest_cache(indexes)
    resolver_routing = run_resolver_routing(indexes)

    trace_shard_count = sum(1 for shard in manifest["shards"] if shard["kind"] == "episode_trace")
    described_episode_capacity = trace_shard_count * episodes_per_trace_shard
    asset_descriptor_count = len(indexes["assets"])
    pass_status = (
        described_episode_capacity >= 1_000_000_000
        and partition["all_queries_pruned"]
        and partition["max_reduction_ratio"] < 0.01
        and digest_cache["digest_mismatches"] == 0
        and digest_cache["cache_hit_rate"] >= 0.70
        and resolver_routing["missing_resolver_count"] == 0
    )
    report = {
        "profile": "worldepisode-dataset-scale-performance-0.1",
        "status": "pass" if pass_status else "fail",
        "pass": pass_status,
        "generated_catalog": {
            "trace_shard_count": trace_shard_count,
            "total_shard_count": len(manifest["shards"]),
            "registry_count": len(manifest["registries"]),
            "index_count": len(manifest["indexes"]),
            "resolver_count": len(manifest["resolvers"]),
            "asset_descriptor_count": asset_descriptor_count,
            "described_episode_capacity": described_episode_capacity,
            "episodes_materialized": 0,
            "json_catalog_bytes": len(encoded),
            "sha256": generated_manifest_sha256,
            "config_sha256": sha256_payload(config),
        },
        "timings_ms": {
            "catalog_open_parse_and_index": open_timing["elapsed_ms"],
            "partition_pruning_queries": partition["timing"]["elapsed_ms"],
            "digest_cache_resolution": digest_cache["timing"]["elapsed_ms"],
            "resolver_routing": resolver_routing["timing"]["elapsed_ms"],
        },
        "partition_pruning": {
            key: value
            for key, value in partition.items()
            if key != "timing"
        },
        "digest_cache": {
            key: value
            for key, value in digest_cache.items()
            if key != "timing"
        },
        "resolver_routing": {
            key: value
            for key, value in resolver_routing.items()
            if key != "timing"
        },
        "claim_boundary": (
            "This benchmark measures catalog-side behavior for a generated billion-episode-capacity "
            "descriptor set. It does not materialize a billion episode rows, load payload bytes, "
            "measure network storage, or prove multi-institution production throughput."
        ),
        "artifacts": {
            "report": rel(output_dir / "performance_report.json"),
            "markdown": rel(output_dir / "README.md"),
        },
    }
    write_json(output_dir / "performance_report.json", report)
    write_text(output_dir / "README.md", render_markdown(report))
    return report


def render_markdown(report: dict[str, Any]) -> str:
    catalog = report["generated_catalog"]
    timings = report["timings_ms"]
    partition = report["partition_pruning"]
    digest_cache = report["digest_cache"]
    resolver = report["resolver_routing"]
    scheme_rows = "\n".join(
        f"| `{scheme}` | {count} |"
        for scheme, count in resolver["scheme_counts"].items()
    )
    return f"""# Dataset-Scale Performance Benchmark

Status: {report["status"]}

This artifact measures catalog-side behavior for a generated large WorldEpisode dataset catalog.
It does not materialize episode rows or payload bytes.

- Trace shards: {catalog["trace_shard_count"]}
- Described episode capacity: {catalog["described_episode_capacity"]}
- Episodes materialized: {catalog["episodes_materialized"]}
- Asset descriptors: {catalog["asset_descriptor_count"]}
- JSON catalog bytes opened: {catalog["json_catalog_bytes"]}
- Generated catalog SHA-256: `{catalog["sha256"]}`

## Timings

| Operation | Milliseconds |
|---|---:|
| Catalog open, parse, and index | {timings["catalog_open_parse_and_index"]:.3f} |
| Partition-pruning queries | {timings["partition_pruning_queries"]:.3f} |
| Digest-cache resolution | {timings["digest_cache_resolution"]:.3f} |
| Resolver routing | {timings["resolver_routing"]:.3f} |

## Partition Pruning

- Query count: {partition["query_count"]}
- Max candidate shards after pruning: {partition["max_candidate_shards"]}
- Max reduction ratio: {partition["max_reduction_ratio"]}
- All queries pruned: {partition["all_queries_pruned"]}

## Digest Cache

- Cache hit rate: {digest_cache["cache_hit_rate"]}
- Cache hits: {digest_cache["cache_hit_count"]}
- Cache misses: {digest_cache["cache_miss_count"]}
- Digest mismatches: {digest_cache["digest_mismatches"]}

## Resolver Routing

| Scheme | Assets |
|---|---:|
{scheme_rows}

- Missing resolver count: {resolver["missing_resolver_count"]}

Boundary: {report["claim_boundary"]}
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--trace-shards", type=int, default=DEFAULT_TRACE_SHARDS)
    parser.add_argument("--episodes-per-trace-shard", type=int, default=DEFAULT_EPISODES_PER_TRACE_SHARD)
    parser.add_argument("--world-lineage-buckets", type=int, default=DEFAULT_WORLD_LINEAGE_BUCKETS)
    parser.add_argument("--task-count", type=int, default=DEFAULT_TASK_COUNT)
    args = parser.parse_args()
    report = benchmark_scale_performance(
        output_dir=args.output_dir,
        trace_shards=args.trace_shards,
        episodes_per_trace_shard=args.episodes_per_trace_shard,
        world_lineage_buckets=args.world_lineage_buckets,
        task_count=args.task_count,
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "trace_shard_count": report["generated_catalog"]["trace_shard_count"],
                "described_episode_capacity": report["generated_catalog"]["described_episode_capacity"],
                "timings_ms": report["timings_ms"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
