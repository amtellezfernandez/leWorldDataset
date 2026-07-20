#!/usr/bin/env python3
"""Prepare the ACT/Diffusion leakage gate from a WorldEpisode split manifest.

This tool does not pretend that a generated plan is a result. It turns the committed
WorldEpisode split manifest into concrete LeRobot-native training/evaluation jobs and records the
exact artifacts required before the paper can claim ACT/Diffusion or rollout evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

try:
    from dataset_license_registry import license_record, source_license_payload
except ImportError:  # Imported as tools.lerobot_policy_leakage_gate in tests.
    from tools.dataset_license_registry import license_record, source_license_payload


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SPLIT_MANIFEST = ROOT / "docs" / "experiments" / "lerobot_scene_leakage" / "split_manifest.json"
DEFAULT_LEAKAGE_REPORT = ROOT / "docs" / "experiments" / "lerobot_scene_leakage" / "leakage_report.json"
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "experiments" / "lerobot_policy_gate"
DEFAULT_POLICY_COMPATIBILITY_REPORT = DEFAULT_OUTPUT_DIR / "policy_compatibility_report.json"
DEFAULT_POLICIES = ("act", "diffusion")
DEFAULT_DEVICE = "cuda"
DEFAULT_STEPS = 20000
DEFAULT_SEED = 17
LEROBOT_POLICY_REQUIREMENTS_VERSION = "0.6.0"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def sanitize(value: str) -> str:
    return value.replace("/", "__").replace(":", "_").replace("@", "_").replace("-", "_")


def shell_join(command: list[str]) -> str:
    return " ".join(subprocess.list2cmdline([part]) for part in command)


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sha256_payload(payload: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def output_file_descriptor(path: Path, media_type: str) -> dict[str, Any]:
    return {
        "path": rel(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "media_type": media_type,
    }


def compatibility_report_fresh(report: dict[str, Any], dataset_root: Path) -> tuple[bool, list[str]]:
    errors = []
    descriptors = report.get("dataset", {}).get("package_files", [])
    if not descriptors:
        return False, ["compatibility report has no package descriptors"]
    for descriptor in descriptors:
        path = dataset_root / descriptor["path"]
        if not path.exists():
            errors.append(f"missing compatibility input: {descriptor['path']}")
            continue
        if path.stat().st_size != descriptor.get("bytes"):
            errors.append(f"byte count changed: {descriptor['path']}")
        if sha256_file(path) != descriptor.get("sha256"):
            errors.append(f"digest changed: {descriptor['path']}")
    return not errors, errors


def detect_environment() -> dict[str, Any]:
    return {
        "lerobot_importable": importlib.util.find_spec("lerobot") is not None,
        "lerobot_train": shutil.which("lerobot-train"),
        "lerobot_eval": shutil.which("lerobot-eval"),
        "lerobot_rollout": shutil.which("lerobot-rollout"),
        "python": shutil.which("python3") or shutil.which("python"),
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
    }


def source_cache_root(split_manifest: dict[str, Any]) -> Path:
    repo_cache = split_manifest["repo_id"].replace("/", "__")
    return ROOT / ".cache" / "worldepisode" / "lerobot_scene_leakage" / repo_cache / split_manifest["revision"]


def physical_package_path(output_dir: Path, split_name: str, partition: str) -> Path:
    return output_dir / "physical_splits" / f"{split_name}_{partition}"


def split_counts(split: dict[str, Any]) -> dict[str, Any]:
    return {
        "train_count": int(split["train_count"]),
        "test_count": int(split["test_count"]),
        "train_world_lineage_count": int(split["train_world_lineage_count"]),
        "test_world_lineage_count": int(split["test_world_lineage_count"]),
        "test_leaked_episode_count": int(split["test_leaked_episode_count"]),
        "leakage_rate": float(split["leakage_rate"]),
        "heldout_task_indices": split.get("heldout_task_indices", []),
    }


def write_allowlists(output_dir: Path, split_name: str, split: dict[str, Any]) -> dict[str, str]:
    split_dir = output_dir / "episode_allowlists" / split_name
    train_path = split_dir / "train_episodes.json"
    test_path = split_dir / "test_episodes.json"
    both_path = split_dir / "split_episodes.json"
    train_payload = {
        "split": split_name,
        "partition": "train",
        "episode_indices": split["train_episodes"],
        "episode_count": split["train_count"],
    }
    test_payload = {
        "split": split_name,
        "partition": "test",
        "episode_indices": split["test_episodes"],
        "episode_count": split["test_count"],
    }
    write_json(train_path, train_payload)
    write_json(test_path, test_payload)
    write_json(
        both_path,
        {
            "split": split_name,
            "profile": "worldepisode-policy-leakage-episodes-0.1",
            "train": train_payload,
            "test": test_payload,
            "leakage": split_counts(split),
        },
    )
    return {
        "train": rel(train_path),
        "test": rel(test_path),
        "combined": rel(both_path),
    }


def split_partition_manifest(
    split_manifest: dict[str, Any],
    leakage_report: dict[str, Any],
    split_name: str,
    split: dict[str, Any],
    partition: str,
) -> dict[str, Any]:
    episode_indices = split[f"{partition}_episodes"]
    source_files = leakage_report.get("source_files", {})
    total_source_bytes = sum(int(descriptor.get("bytes", 0)) for descriptor in source_files.values())
    source_license = source_license_payload(
        license_record(split_manifest["repo_id"], split_manifest["revision"])
    )
    return {
        "profile": "worldepisode-virtual-lerobot-split-0.1",
        "status": "virtual_materialization_manifest",
        "source_dataset": {
            "repo_id": split_manifest["repo_id"],
            "revision": split_manifest["revision"],
            "source_license": source_license,
        },
        "target_dataset": {
            "repo_id": materialized_repo_id(split_manifest["repo_id"], split_name, partition),
            "split_name": split_name,
            "partition": partition,
        },
        "episode_filter": {
            "field": "episode_index",
            "episode_count": len(episode_indices),
            "episode_indices": episode_indices,
            "episode_indices_sha256": sha256_payload(episode_indices),
        },
        "lineage_controls": {
            "world_lineage_field": split_manifest.get("world_lineage_field", "world_lineage"),
            "leakage_rate": split["leakage_rate"],
            "train_world_lineage_count": split["train_world_lineage_count"],
            "test_world_lineage_count": split["test_world_lineage_count"],
            "test_leaked_episode_count": split["test_leaked_episode_count"],
            "heldout_task_indices": split.get("heldout_task_indices", []),
        },
        "source_files": source_files,
        "source_file_count": len(source_files),
        "source_total_bytes": total_source_bytes,
        "construction": {
            "mode": "filter_source_lerobot_v3_by_episode_index",
            "preserve_fields": [
                "action",
                "observation.state",
                "timestamp",
                "frame_index",
                "episode_index",
                "task_index",
                "video timestamp ranges",
            ],
            "copy_policy": (
                "Copy LeRobot v3 rows whose episode_index is listed in episode_filter. Preserve "
                "native tensors, timestamps, metadata, and video references without augmentation."
            ),
            "integrity_policy": (
                "Verify every source file against its declared sha256 before copying or linking. "
                "The split membership digest must match episode_indices_sha256."
            ),
        },
        "claim_boundary": (
            "This is a virtual materialization manifest. It fixes split membership and source "
            "integrity for ACT/Diffusion jobs, but it is not a committed physical copy of all "
            "LeRobot payload shards and videos."
        ),
    }


def write_materialized_split_manifests(
    output_dir: Path,
    split_manifest_path: Path,
    split_manifest: dict[str, Any],
    leakage_report: dict[str, Any],
) -> dict[str, Any]:
    materialized_dir = output_dir / "materialized_splits"
    manifests: list[dict[str, Any]] = []
    artifacts: dict[str, str] = {}
    for split_name, split in sorted(split_manifest["splits"].items()):
        train_episodes = set(split["train_episodes"])
        test_episodes = set(split["test_episodes"])
        overlap = sorted(train_episodes & test_episodes)
        for partition in ("train", "test"):
            manifest = split_partition_manifest(
                split_manifest=split_manifest,
                leakage_report=leakage_report,
                split_name=split_name,
                split=split,
                partition=partition,
            )
            manifest["membership_invariants"] = {
                "train_test_overlap_count": len(overlap),
                "train_test_overlap": overlap,
                "split_episode_count_matches": manifest["episode_filter"]["episode_count"]
                == int(split[f"{partition}_count"]),
            }
            path = materialized_dir / f"{split_name}_{partition}.lerobot_split_manifest.json"
            write_json(path, manifest)
            artifacts[f"{split_name}_{partition}_materialization"] = rel(path)
            manifests.append(manifest)

    summary = {
        "profile": "worldepisode-lerobot-split-materialization-0.1",
        "status": "virtual_materialization_manifests_ready",
        "source_split_manifest": rel(split_manifest_path),
        "manifest_count": len(manifests),
        "source_file_count": len(leakage_report.get("source_files", {})),
        "target_datasets": [manifest["target_dataset"] for manifest in manifests],
        "all_membership_counts_match": all(
            manifest["membership_invariants"]["split_episode_count_matches"] for manifest in manifests
        ),
        "all_train_test_overlaps_zero": all(
            manifest["membership_invariants"]["train_test_overlap_count"] == 0 for manifest in manifests
        ),
        "claim_boundary": (
            "Virtual manifests make split materialization deterministic for LeRobot-native policy "
            "jobs. They do not replace committed train/eval metrics or physical rollout reports."
        ),
    }
    summary_path = materialized_dir / "manifest.json"
    write_json(summary_path, summary)
    artifacts["materialized_split_manifest"] = rel(summary_path)
    return {
        "summary": summary,
        "artifacts": artifacts,
    }


def import_pyarrow() -> Any:
    try:
        import pyarrow as pa  # type: ignore[import-not-found]
        import pyarrow.compute as pc  # type: ignore[import-not-found]
        import pyarrow.parquet as pq  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:
        raise RuntimeError("pyarrow is required to materialize physical LeRobot split packages") from exc
    return pa, pc, pq


def verified_source_descriptors(source_root: Path, source_files: dict[str, Any]) -> list[dict[str, Any]]:
    verified = []
    for relative_path, descriptor in sorted(source_files.items()):
        path = source_root / relative_path
        if not path.exists():
            raise FileNotFoundError(f"missing cached source file: {path}")
        actual_sha256 = sha256_file(path)
        expected_sha256 = descriptor.get("sha256")
        if expected_sha256 and actual_sha256 != expected_sha256:
            raise ValueError(
                f"sha256 mismatch for {relative_path}: expected {expected_sha256}, got {actual_sha256}"
            )
        expected_bytes = descriptor.get("bytes")
        actual_bytes = path.stat().st_size
        if expected_bytes is not None and int(expected_bytes) != actual_bytes:
            raise ValueError(
                f"byte-size mismatch for {relative_path}: expected {expected_bytes}, got {actual_bytes}"
            )
        verified.append(
            {
                "path": relative_path,
                "uri": descriptor.get("uri"),
                "sha256": actual_sha256,
                "bytes": actual_bytes,
                "media_type": "application/vnd.apache.parquet"
                if relative_path.endswith(".parquet")
                else "application/json",
                "local_mirror": rel(path),
            }
        )
    return verified


def filter_table_by_episode(pa: Any, pc: Any, pq: Any, path: Path, episode_indices: set[int]) -> Any:
    table = pq.read_table(path)
    if "episode_index" not in table.column_names:
        raise ValueError(f"{path} has no episode_index column")
    field_type = table.schema.field("episode_index").type
    mask = pc.is_in(table["episode_index"], value_set=pa.array(sorted(episode_indices), type=field_type))
    return table.filter(mask)


def replace_column(pa: Any, table: Any, name: str, values: list[Any]) -> Any:
    if name not in table.column_names:
        return table
    index = table.schema.get_field_index(name)
    field = table.schema.field(name)
    if pa.types.is_list(field.type):
        values = [value if isinstance(value, list) else [value] for value in values]
    return table.set_column(index, name, pa.array(values, type=field.type))


def replace_constant_column(pa: Any, table: Any, name: str, value: Any) -> Any:
    if name not in table.column_names:
        return table
    return replace_column(pa, table, name, [value] * table.num_rows)


def drop_video_only_columns(table: Any) -> Any:
    drop_columns = [
        name
        for name in table.column_names
        if name.startswith("videos/") or name.startswith("stats/observation.images.")
    ]
    return table.drop(drop_columns) if drop_columns else table


def update_episode_stats(pa: Any, table: Any, lengths: list[int]) -> Any:
    dataset_from: list[int] = []
    dataset_to: list[int] = []
    offset = 0
    for length in lengths:
        dataset_from.append(offset)
        offset += int(length)
        dataset_to.append(offset)

    local_episode_indices = list(range(len(lengths)))
    table = replace_column(pa, table, "dataset_from_index", dataset_from)
    table = replace_column(pa, table, "dataset_to_index", dataset_to)
    table = replace_column(pa, table, "episode_index", local_episode_indices)
    table = replace_constant_column(pa, table, "data/chunk_index", 0)
    table = replace_constant_column(pa, table, "data/file_index", 0)
    table = replace_constant_column(pa, table, "meta/episodes/chunk_index", 0)
    table = replace_constant_column(pa, table, "meta/episodes/file_index", 0)

    episode_stat_values = {
        "min": local_episode_indices,
        "max": local_episode_indices,
        "mean": [float(value) for value in local_episode_indices],
        "std": [0.0] * len(lengths),
        "count": lengths,
        "q01": [float(value) for value in local_episode_indices],
        "q10": [float(value) for value in local_episode_indices],
        "q50": [float(value) for value in local_episode_indices],
        "q90": [float(value) for value in local_episode_indices],
        "q99": [float(value) for value in local_episode_indices],
    }
    index_stat_values = {
        "min": dataset_from,
        "max": [end - 1 for end in dataset_to],
        "mean": [(start + end - 1) / 2.0 for start, end in zip(dataset_from, dataset_to, strict=True)],
        "std": [((length * length - 1) / 12.0) ** 0.5 if length > 1 else 0.0 for length in lengths],
        "count": lengths,
        "q01": [start + 0.01 * (length - 1) for start, length in zip(dataset_from, lengths, strict=True)],
        "q10": [start + 0.10 * (length - 1) for start, length in zip(dataset_from, lengths, strict=True)],
        "q50": [start + 0.50 * (length - 1) for start, length in zip(dataset_from, lengths, strict=True)],
        "q90": [start + 0.90 * (length - 1) for start, length in zip(dataset_from, lengths, strict=True)],
        "q99": [start + 0.99 * (length - 1) for start, length in zip(dataset_from, lengths, strict=True)],
    }
    for feature_name, stat_values in (("episode_index", episode_stat_values), ("index", index_stat_values)):
        for stat_name, values in stat_values.items():
            table = replace_column(pa, table, f"stats/{feature_name}/{stat_name}", values)
    return table


def aggregate_episode_feature_stats(table: Any, feature_names: list[str]) -> dict[str, Any]:
    import numpy as np

    aggregate: dict[str, Any] = {}
    stat_names = ("min", "max", "mean", "std", "count", "q01", "q10", "q50", "q90", "q99")
    for feature_name in feature_names:
        columns = {stat: f"stats/{feature_name}/{stat}" for stat in stat_names}
        if any(column not in table.column_names for column in columns.values()):
            continue

        values = {
            stat: np.asarray(table[column].to_pylist(), dtype=np.float64)
            for stat, column in columns.items()
        }
        counts = values["count"]
        means = values["mean"]
        while counts.ndim < means.ndim:
            counts = np.expand_dims(counts, axis=-1)
        total_count = counts.sum(axis=0)
        total_mean = (means * counts).sum(axis=0) / total_count
        total_variance = (((values["std"] ** 2) + (means - total_mean) ** 2) * counts).sum(
            axis=0
        ) / total_count

        feature_stats = {
            "min": values["min"].min(axis=0),
            "max": values["max"].max(axis=0),
            "mean": total_mean,
            "std": np.sqrt(total_variance),
            "count": total_count,
        }
        for quantile in ("q01", "q10", "q50", "q90", "q99"):
            feature_stats[quantile] = (values[quantile] * counts).sum(axis=0) / total_count
        aggregate[feature_name] = {
            stat: np.atleast_1d(value).tolist()
            for stat, value in feature_stats.items()
        }
    return aggregate


def compact_info_payload(
    source_info: dict[str, Any],
    split_name: str,
    partition: str,
    episode_count: int,
    frame_count: int,
) -> dict[str, Any]:
    info = dict(source_info)
    features = {
        name: feature
        for name, feature in source_info.get("features", {}).items()
        if not (isinstance(feature, dict) and feature.get("dtype") == "video")
    }
    info["features"] = features
    info["total_episodes"] = episode_count
    info["total_frames"] = frame_count
    info["splits"] = {"train": f"0:{episode_count}"}
    info.pop("video_path", None)
    info["video_path"] = None
    return info


def write_physical_split_package(
    pa: Any,
    pc: Any,
    pq: Any,
    output_dir: Path,
    split_manifest: dict[str, Any],
    leakage_report: dict[str, Any],
    source_root: Path,
    split_name: str,
    split: dict[str, Any],
    partition: str,
    verified_sources: list[dict[str, Any]],
) -> dict[str, Any]:
    split_manifest_episode_indices = [int(value) for value in split[f"{partition}_episodes"]]
    episode_indices = sorted(split_manifest_episode_indices)
    episode_set = set(episode_indices)
    target_dir = physical_package_path(output_dir, split_name, partition)
    if target_dir.exists():
        shutil.rmtree(target_dir)
    (target_dir / "data" / "chunk-000").mkdir(parents=True, exist_ok=True)
    (target_dir / "meta" / "episodes" / "chunk-000").mkdir(parents=True, exist_ok=True)

    source_files = leakage_report.get("source_files", {})
    data_paths = [
        source_root / relative_path
        for relative_path in sorted(source_files)
        if relative_path.startswith("data/") and relative_path.endswith(".parquet")
    ]
    filtered_data_tables = [
        table
        for table in (filter_table_by_episode(pa, pc, pq, path, episode_set) for path in data_paths)
        if table.num_rows > 0
    ]
    if not filtered_data_tables:
        raise ValueError(f"split {split_name}/{partition} produced no data rows")
    data_table = pa.concat_tables(filtered_data_tables, promote_options="default")
    data_table = data_table.sort_by([("episode_index", "ascending"), ("frame_index", "ascending")])

    original_episode_by_row = [int(value) for value in data_table["episode_index"].to_pylist()]
    local_episode_by_source = {episode_index: local_index for local_index, episode_index in enumerate(episode_indices)}
    local_episode_by_row = [local_episode_by_source[value] for value in original_episode_by_row]
    data_table = replace_column(pa, data_table, "episode_index", local_episode_by_row)
    data_table = replace_column(pa, data_table, "index", list(range(data_table.num_rows)))

    data_path = target_dir / "data" / "chunk-000" / "file-000.parquet"
    pq.write_table(data_table, data_path, compression="zstd")

    source_episode_path = source_root / "meta" / "episodes" / "chunk-000" / "file-000.parquet"
    meta_table = filter_table_by_episode(pa, pc, pq, source_episode_path, episode_set)
    meta_table = meta_table.sort_by([("episode_index", "ascending")])
    lengths = [int(value) for value in meta_table["length"].to_pylist()]
    if sum(lengths) != data_table.num_rows:
        raise ValueError(
            f"split {split_name}/{partition} metadata length sum {sum(lengths)} "
            f"does not equal data rows {data_table.num_rows}"
        )
    meta_table = drop_video_only_columns(meta_table)
    meta_table = update_episode_stats(pa, meta_table, lengths)
    meta_path = target_dir / "meta" / "episodes" / "chunk-000" / "file-000.parquet"
    pq.write_table(meta_table, meta_path, compression="zstd")

    feature_stats = aggregate_episode_feature_stats(
        meta_table,
        ["action", "observation.state"],
    )
    stats_path = target_dir / "meta" / "stats.json"
    write_json(stats_path, feature_stats)

    tasks_source = source_root / "meta" / "tasks.parquet"
    tasks_path = target_dir / "meta" / "tasks.parquet"
    shutil.copy2(tasks_source, tasks_path)

    source_info = load_json(source_root / "meta" / "info.json")
    info_payload = compact_info_payload(
        source_info=source_info,
        split_name=split_name,
        partition=partition,
        episode_count=len(episode_indices),
        frame_count=data_table.num_rows,
    )
    info_path = target_dir / "meta" / "info.json"
    write_json(info_path, info_payload)
    source_license = source_license_payload(
        license_record(split_manifest["repo_id"], split_manifest["revision"])
    )
    source_license_path = target_dir / "SOURCE_LICENSE.json"
    write_json(source_license_path, source_license)

    local_episode_map = [
        {"local_episode_index": local_index, "source_episode_index": source_index}
        for local_index, source_index in enumerate(episode_indices)
    ]
    package_manifest = {
        "profile": "worldepisode-physical-lerobot-split-package-0.1",
        "status": "physical_split_package_ready",
        "source_dataset": {
            "repo_id": split_manifest["repo_id"],
            "revision": split_manifest["revision"],
            "local_cache_root": rel(source_root),
            "source_license": source_license,
        },
        "target_dataset": {
            "repo_id": materialized_repo_id(split_manifest["repo_id"], split_name, partition),
            "local_path": rel(target_dir),
            "split_name": split_name,
            "partition": partition,
            "lerobot_split_alias": "train",
        },
        "episode_filter": {
            "field": "episode_index",
            "source_episode_count": len(episode_indices),
            "source_episode_indices": episode_indices,
            "source_episode_indices_sha256": sha256_payload(episode_indices),
            "split_manifest_episode_indices_sha256": sha256_payload(split_manifest_episode_indices),
            "local_episode_map": local_episode_map,
            "local_episode_map_sha256": sha256_payload(local_episode_map),
        },
        "row_counts": {
            "episodes": len(episode_indices),
            "frames": data_table.num_rows,
            "metadata_episode_rows": meta_table.num_rows,
        },
        "source_integrity": {
            "verified": True,
            "verified_file_count": len(verified_sources),
            "verified_total_bytes": sum(int(source["bytes"]) for source in verified_sources),
            "source_files_sha256": sha256_payload(verified_sources),
            "source_files": verified_sources,
        },
        "outputs": {
            "data": output_file_descriptor(data_path, "application/vnd.apache.parquet"),
            "episodes": output_file_descriptor(meta_path, "application/vnd.apache.parquet"),
            "tasks": output_file_descriptor(tasks_path, "application/vnd.apache.parquet"),
            "stats": output_file_descriptor(stats_path, "application/json"),
            "info": output_file_descriptor(info_path, "application/json"),
            "source_license": output_file_descriptor(
                source_license_path,
                "application/json",
            ),
        },
        "preserved_without_numeric_change": [
            "action",
            "observation.state",
            "timestamp",
            "frame_index",
            "task_index",
            "next.reward",
            "next.done",
        ],
        "explicitly_remapped": [
            "episode_index",
            "index",
            "meta/episodes dataset_from_index",
            "meta/episodes dataset_to_index",
        ],
        "not_materialized": [
            "video payload files",
            "observation.images.* feature payloads",
        ],
        "claim_boundary": (
            "This is a compact low-dimensional LeRobot split package for state/action policy reruns. "
            "It is digest-verified against the cached public source Parquet files and preserves "
            "action, state, timestamp, frame, task, reward, and done values. It deliberately does "
            "not claim to be a full vision dataset because the source video files were not part of "
            "the committed leakage audit cache."
        ),
    }
    package_manifest_path = target_dir / "worldepisode_split_package.json"
    package_manifest["manifest"] = {
        "path": rel(package_manifest_path),
        "media_type": "application/json",
    }
    write_json(package_manifest_path, package_manifest)
    return package_manifest


def existing_physical_summary(output_dir: Path) -> dict[str, Any] | None:
    summary_path = output_dir / "physical_splits" / "manifest.json"
    return load_json(summary_path) if summary_path.exists() else None


def write_physical_split_packages(
    output_dir: Path,
    split_manifest_path: Path,
    split_manifest: dict[str, Any],
    leakage_report: dict[str, Any],
) -> dict[str, Any]:
    physical_dir = output_dir / "physical_splits"
    summary_path = physical_dir / "manifest.json"
    artifacts = {"physical_split_manifest": rel(summary_path)}
    try:
        pa, pc, pq = import_pyarrow()
        source_root = source_cache_root(split_manifest)
        if not source_root.exists():
            raise FileNotFoundError(f"cached source root does not exist: {source_root}")
        source_files = leakage_report.get("source_files", {})
        if not source_files:
            raise ValueError("leakage report has no source_files descriptors")
        verified_sources = verified_source_descriptors(source_root, source_files)
        packages = []
        for split_name, split in sorted(split_manifest["splits"].items()):
            train_episodes = set(split["train_episodes"])
            test_episodes = set(split["test_episodes"])
            overlap = sorted(train_episodes & test_episodes)
            for partition in ("train", "test"):
                package = write_physical_split_package(
                    pa=pa,
                    pc=pc,
                    pq=pq,
                    output_dir=output_dir,
                    split_manifest=split_manifest,
                    leakage_report=leakage_report,
                    source_root=source_root,
                    split_name=split_name,
                    split=split,
                    partition=partition,
                    verified_sources=verified_sources,
                )
                package["membership_invariants"] = {
                    "train_test_overlap_count": len(overlap),
                    "train_test_overlap": overlap,
                    "split_episode_count_matches": package["row_counts"]["episodes"]
                    == int(split[f"{partition}_count"]),
                }
                packages.append(package)

        package_output_bytes = sum(
            int(output["bytes"])
            for package in packages
            for output in package["outputs"].values()
        )
        summary = {
            "profile": "worldepisode-physical-lerobot-split-packages-0.1",
            "status": "physical_split_packages_ready",
            "source_split_manifest": rel(split_manifest_path),
            "source_cache_root": rel(source_root),
            "package_root": rel(physical_dir),
            "package_count": len(packages),
            "source_file_count": len(verified_sources),
            "source_files_verified": True,
            "all_membership_counts_match": all(
                package["membership_invariants"]["split_episode_count_matches"] for package in packages
            ),
            "all_train_test_overlaps_zero": all(
                package["membership_invariants"]["train_test_overlap_count"] == 0 for package in packages
            ),
            "total_output_frames": sum(int(package["row_counts"]["frames"]) for package in packages),
            "total_output_bytes": package_output_bytes,
            "packages": [
                {
                    "split_name": package["target_dataset"]["split_name"],
                    "partition": package["target_dataset"]["partition"],
                    "local_path": package["target_dataset"]["local_path"],
                    "repo_id": package["target_dataset"]["repo_id"],
                    "episodes": package["row_counts"]["episodes"],
                    "frames": package["row_counts"]["frames"],
                    "manifest": package["manifest"]["path"],
                }
                for package in packages
            ],
            "claim_boundary": (
                "Physical split packages are committed compact low-dimensional LeRobot folders. "
                "Their state/action rows are ready for policies that support proprioception-only input. "
                "LeRobot 0.6.0 ACT and Diffusion require an image or environment-state input, so source "
                "videos or a semantically valid environment-state feature must be materialized before "
                "those jobs can run."
            ),
        }
        write_json(summary_path, summary)
        return {"summary": summary, "artifacts": artifacts}
    except Exception as exc:  # noqa: BLE001 - keep normal report regeneration usable without pyarrow/cache.
        existing = existing_physical_summary(output_dir)
        if existing is not None:
            return {"summary": existing, "artifacts": artifacts}
        summary = {
            "profile": "worldepisode-physical-lerobot-split-packages-0.1",
            "status": "unavailable",
            "source_split_manifest": rel(split_manifest_path),
            "package_count": 0,
            "source_file_count": len(leakage_report.get("source_files", {})),
            "source_files_verified": False,
            "all_membership_counts_match": False,
            "all_train_test_overlaps_zero": False,
            "reason": str(exc),
            "claim_boundary": (
                "Physical split package generation requires pyarrow and the cached source files. "
                "Virtual manifests remain available, but policy reruns should not be claimed from "
                "this unavailable physical package state."
            ),
        }
        return {"summary": summary, "artifacts": artifacts}


def materialized_repo_id(source_repo_id: str, split_name: str, partition: str) -> str:
    source_name = source_repo_id.split("/")[-1].lower()
    return f"worldepisode/{source_name}_{split_name}_{partition}"


def train_command(
    policy: str,
    dataset_repo_id: str,
    dataset_root: str,
    output_dir: str,
    job_name: str,
    device: str,
    steps: int,
    seed: int,
    wandb: bool,
) -> list[str]:
    return [
        "lerobot-train",
        f"--dataset.repo_id={dataset_repo_id}",
        f"--dataset.root={dataset_root}",
        f"--policy.type={policy}",
        f"--output_dir={output_dir}",
        f"--job_name={job_name}",
        f"--policy.device={device}",
        "--policy.push_to_hub=false",
        f"--steps={steps}",
        f"--seed={seed}",
        f"--wandb.enable={str(wandb).lower()}",
    ]


def eval_command(policy_path: str, env_type: str, env_task: str, device: str, n_episodes: int) -> list[str]:
    return [
        "lerobot-eval",
        f"--policy.path={policy_path}",
        f"--env.type={env_type}",
        f"--env.task={env_task}",
        f"--policy.device={device}",
        f"--eval.n_episodes={n_episodes}",
    ]


def rollout_command(policy_path: str, robot_type: str, n_episodes: int) -> list[str]:
    return [
        "lerobot-rollout",
        f"--policy.path={policy_path}",
        f"--robot.type={robot_type}",
        f"--eval.n_episodes={n_episodes}",
    ]


def make_jobs(
    split_manifest: dict[str, Any],
    output_dir: Path,
    policies: list[str],
    device: str,
    steps: int,
    seed: int,
    wandb: bool,
    rollout_episodes: int,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, str]]:
    repo_id = split_manifest["repo_id"]
    revision = split_manifest["revision"]
    split_artifacts: dict[str, str] = {}
    jobs: list[dict[str, Any]] = []
    run_lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        "# Local compact split packages are under docs/experiments/lerobot_policy_gate/physical_splits.",
        "# LeRobot 0.6.0 ACT and Diffusion also require an image or environment-state input.",
        "# Do not run these jobs until a semantically valid required modality has been materialized.",
        "",
    ]

    for split_name, split in sorted(split_manifest["splits"].items()):
        split_artifacts.update(
            {
                f"{split_name}_{key}": value
                for key, value in write_allowlists(output_dir, split_name, split).items()
            }
        )
        train_repo = materialized_repo_id(repo_id, split_name, "train")
        test_repo = materialized_repo_id(repo_id, split_name, "test")
        train_local_path = rel(physical_package_path(output_dir, split_name, "train"))
        test_local_path = rel(physical_package_path(output_dir, split_name, "test"))
        for policy in policies:
            job_name = f"{policy}_{split_name}_worldepisode_leakage"
            policy_output = f"outputs/policy_leakage/{job_name}"
            policy_path = f"{policy_output}/checkpoints/last/pretrained_model"
            train = train_command(
                policy=policy,
                dataset_repo_id=train_repo,
                dataset_root=train_local_path,
                output_dir=policy_output,
                job_name=job_name,
                device=device,
                steps=steps,
                seed=seed,
                wandb=wandb,
            )
            offline_eval = {
                "required_report": f"docs/experiments/lerobot_policy_gate/results/{job_name}/offline_action_eval.json",
                "dataset_repo_id": test_repo,
                "dataset_local_path": test_local_path,
                "episode_allowlist": rel(output_dir / "episode_allowlists" / split_name / "test_episodes.json"),
                "metrics": [
                    "episode_normalized_rmse_mean",
                    "episode_normalized_rmse_median",
                    "episode_success_rate_at_declared_threshold",
                    "per_world_lineage_success_rate",
                ],
                "note": (
                    "Run policy inference over the materialized held-out test split and write this report. "
                    "The repository does not claim this result until the report exists."
                ),
            }
            sim_eval = eval_command(
                policy_path=policy_path,
                env_type="isaaclab_arena_or_registered_worldepisode_env",
                env_task="MATCH_WORLD_LINEAGE_HELDOUT_TASK",
                device=device,
                n_episodes=rollout_episodes,
            )
            physical_rollout = rollout_command(
                policy_path=policy_path,
                robot_type="so101",
                n_episodes=rollout_episodes,
            )
            run_lines.extend(
                [
                    f"# {policy} on {split_name}",
                    shell_join(train),
                    "",
                ]
            )
            jobs.append(
                {
                    "job_id": job_name,
                    "policy_type": policy,
                    "split": split_name,
                    "source_dataset": {
                        "repo_id": repo_id,
                        "revision": revision,
                        "source_license": source_license_payload(
                            license_record(repo_id, revision)
                        ),
                    },
                    "materialized_datasets_required": {
                        "train_repo_id": train_repo,
                        "test_repo_id": test_repo,
                        "train_local_path": train_local_path,
                        "test_local_path": test_local_path,
                        "train_allowlist": rel(output_dir / "episode_allowlists" / split_name / "train_episodes.json"),
                        "test_allowlist": rel(output_dir / "episode_allowlists" / split_name / "test_episodes.json"),
                    },
                    "train": {
                        "command": train,
                        "shell": shell_join(train),
                        "expected_checkpoint": policy_path,
                    },
                    "offline_action_eval": offline_eval,
                    "high_fidelity_sim_eval": {
                        "command_template": sim_eval,
                        "shell_template": shell_join(sim_eval),
                        "requires_env_binding": True,
                        "required": True,
                    },
                    "physical_rollout": {
                        "command_template": physical_rollout,
                        "shell_template": shell_join(physical_rollout),
                        "requires_robot_binding": True,
                        "required_for_full_claim": True,
                    },
                    "required_result_files": [
                        f"docs/experiments/lerobot_policy_gate/results/{job_name}/train_metrics.json",
                        f"docs/experiments/lerobot_policy_gate/results/{job_name}/offline_action_eval.json",
                        f"docs/experiments/lerobot_policy_gate/results/{job_name}/rollout_report.json",
                    ],
                }
            )

    script_path = output_dir / "run_lerobot_policy_jobs.sh"
    write_text(script_path, "\n".join(run_lines) + "\n")
    script_path.chmod(0o755)
    rollout_contract = {
        "profile": "worldepisode-policy-rollout-gate-0.1",
        "minimum_rollout_episodes_per_policy_split": rollout_episodes,
        "required_policy_types": policies,
        "required_splits": sorted(split_manifest["splits"].keys()),
        "required_metrics": [
            "train_loss_curve",
            "offline_action_nrmse_by_episode",
            "success_rate_by_split",
            "success_rate_by_world_lineage",
            "failure_modes",
            "video_or_trace_uris_with_sha256",
            "simulator_or_robot_runtime_manifest",
        ],
        "acceptance_rule": (
            "The leakage claim is closed only when ACT or Diffusion reports exist for both random_episode "
            "and scene_disjoint splits, and at least one high-fidelity simulator or physical rollout report "
            "is available with the same split manifest."
        ),
        "sim_ready_but_not_executed_here": True,
    }
    return jobs, rollout_contract, {"run_script": rel(script_path), **split_artifacts}


def existing_result_files(jobs: list[dict[str, Any]]) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for job in jobs:
        present = [path for path in job["required_result_files"] if (ROOT / path).exists()]
        found[job["job_id"]] = present
    return found


def gate_satisfied(jobs: list[dict[str, Any]], result_files: dict[str, list[str]]) -> bool:
    if not jobs:
        return False
    return all(len(result_files[job["job_id"]]) == len(job["required_result_files"]) for job in jobs)


def execute_jobs(jobs: list[dict[str, Any]], dry_run: bool) -> list[dict[str, Any]]:
    executions: list[dict[str, Any]] = []
    if dry_run:
        return executions
    for job in jobs:
        command = job["train"]["command"]
        completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
        executions.append(
            {
                "job_id": job["job_id"],
                "command": command,
                "returncode": completed.returncode,
                "stdout_tail": completed.stdout[-4000:],
                "stderr_tail": completed.stderr[-4000:],
            }
        )
        if completed.returncode != 0:
            break
    return executions


def build_policy_gate(
    split_manifest_path: Path,
    leakage_report_path: Path,
    output_dir: Path,
    policies: list[str],
    device: str,
    steps: int,
    seed: int,
    wandb: bool,
    rollout_episodes: int,
    execute: bool,
) -> dict[str, Any]:
    split_manifest = load_json(split_manifest_path)
    leakage_report = load_json(leakage_report_path) if leakage_report_path.exists() else {}
    output_dir.mkdir(parents=True, exist_ok=True)
    jobs, rollout_contract, artifacts = make_jobs(
        split_manifest=split_manifest,
        output_dir=output_dir,
        policies=policies,
        device=device,
        steps=steps,
        seed=seed,
        wandb=wandb,
        rollout_episodes=rollout_episodes,
    )
    materialization = write_materialized_split_manifests(
        output_dir=output_dir,
        split_manifest_path=split_manifest_path,
        split_manifest=split_manifest,
        leakage_report=leakage_report,
    )
    physical_packages = write_physical_split_packages(
        output_dir=output_dir,
        split_manifest_path=split_manifest_path,
        split_manifest=split_manifest,
        leakage_report=leakage_report,
    )
    artifacts.update(materialization["artifacts"])
    artifacts.update(physical_packages["artifacts"])
    environment = detect_environment()
    result_files = existing_result_files(jobs)
    compatibility_path = output_dir / DEFAULT_POLICY_COMPATIBILITY_REPORT.name
    if compatibility_path.exists():
        compatibility = load_json(compatibility_path)
        compatibility_fresh, compatibility_errors = compatibility_report_fresh(
            compatibility,
            physical_package_path(output_dir, "random_episode", "train"),
        )
    else:
        compatibility = {
            "status": "not_run",
            "audit_valid": False,
            "all_policy_probes_completed_training_step": False,
            "all_policy_probes_blocked_for_expected_reason": False,
        }
        compatibility_fresh = False
        compatibility_errors = ["compatibility report has not been generated"]
    compatibility_evidence = {
        **compatibility,
        "fresh_for_current_package": compatibility_fresh,
        "freshness_errors": compatibility_errors,
    }
    policy_inputs_ready = bool(
        compatibility_fresh
        and compatibility.get("all_policy_probes_completed_training_step")
    )
    known_modality_blocker = bool(
        compatibility_fresh
        and compatibility.get("audit_valid")
        and compatibility.get("all_policy_probes_blocked_for_expected_reason")
    )
    environment_ready = bool(environment["lerobot_train"]) and environment["lerobot_importable"]
    ready_to_execute = environment_ready and policy_inputs_ready
    if execute and not ready_to_execute:
        executions = [
            {
                "status": "blocked_by_preflight",
                "reason": compatibility_evidence.get(
                    "claim_boundary",
                    "Policy compatibility preflight did not pass.",
                ),
            }
        ]
    else:
        executions = execute_jobs(jobs, dry_run=not execute)
    if execute:
        result_files = existing_result_files(jobs)

    split_summary = {
        name: split_counts(split)
        for name, split in sorted(split_manifest["splits"].items())
    }
    gate_pass = gate_satisfied(jobs, result_files)
    status = (
        "closed"
        if gate_pass
        else "blocked_missing_required_observation_modality"
        if known_modality_blocker
        else "ready_not_executed"
    )
    report = {
        "profile": "worldepisode-act-diffusion-leakage-gate-0.1",
        "available": True,
        "pass": gate_pass,
        "status": status,
        "source_split_manifest": rel(split_manifest_path),
        "source_leakage_report": rel(leakage_report_path),
        "source_dataset": {
            "repo_id": split_manifest["repo_id"],
            "revision": split_manifest["revision"],
            "source_license": source_license_payload(
                license_record(
                    split_manifest["repo_id"],
                    split_manifest["revision"],
                )
            ),
            "teleoperated_reference_episodes": leakage_report.get("dataset", {}).get("teleoperated_reference_episodes"),
            "robot_type": leakage_report.get("dataset", {}).get("robot_type", "so101"),
        },
        "splits": split_summary,
        "policies": policies,
        "environment": environment,
        "environment_ready": environment_ready,
        "policy_inputs_ready": policy_inputs_ready,
        "ready_to_execute": ready_to_execute,
        "policy_compatibility": compatibility_evidence,
        "jobs": jobs,
        "materialized_split_manifests": materialization["summary"],
        "physical_split_packages": physical_packages["summary"],
        "rollout_contract": rollout_contract,
        "result_files_present": result_files,
        "executions": executions,
        "closure_required": [
            (
                "materialize source observation images or a semantically valid observation.environment_state "
                f"feature required by LeRobot {LEROBOT_POLICY_REQUIREMENTS_VERSION} ACT and Diffusion"
            ),
            "train ACT and Diffusion Policy on random_episode and scene_disjoint train datasets",
            "evaluate each checkpoint on the corresponding test split with action-error metrics",
            "run at least one high-fidelity simulator or physical rollout using the same split manifest",
            "commit train metrics, offline action metrics, rollout reports, and digest-verified videos/traces",
            "mirror source videos before claiming any vision-policy result from the compact split packages",
        ],
        "artifacts": {
            "report": rel(output_dir / "policy_gate_report.json"),
            "jobs": rel(output_dir / "train_eval_jobs.json"),
            "rollout_contract": rel(output_dir / "rollout_contract.json"),
            "policy_compatibility_report": rel(compatibility_path),
            "policy_compatibility_log": compatibility.get("artifacts", {}).get(
                "run_log",
                "docs/experiments/run_logs/lerobot_policy_compatibility_dgx_spark.log",
            ),
            **artifacts,
        },
    }
    write_json(output_dir / "train_eval_jobs.json", jobs)
    write_json(output_dir / "rollout_contract.json", rollout_contract)
    write_json(output_dir / "policy_gate_report.json", report)
    write_text(
        output_dir / "README.md",
        render_readme(report),
    )
    return report


def render_readme(report: dict[str, Any]) -> str:
    job_rows = "\n".join(
        f"| `{job['job_id']}` | `{job['policy_type']}` | `{job['split']}` | `{job['materialized_datasets_required']['train_local_path']}` |"
        for job in report["jobs"]
    )
    materialization = report["materialized_split_manifests"]
    physical = report.get("physical_split_packages", {})
    compatibility = report.get("policy_compatibility", {})
    return f"""# LeRobot ACT/Diffusion Leakage Gate

Status: {report["status"]}

This directory is the executable gate for the reviewer concern that the leakage result must be
tested with stronger LeRobot-native policies. It is intentionally not marked closed until ACT or
Diffusion checkpoints, offline action-evaluation reports, and rollout reports are present.

Source split manifest: `{report["source_split_manifest"]}`

## Split Materialization

- Manifest: `{report["artifacts"]["materialized_split_manifest"]}`
- Virtual split datasets: {materialization["manifest_count"]}
- Source files with digest descriptors: {materialization["source_file_count"]}
- Train/test overlaps are zero: {materialization["all_train_test_overlaps_zero"]}
- Episode counts match split manifest: {materialization["all_membership_counts_match"]}
- Physical split package manifest: `{report["artifacts"].get("physical_split_manifest", "")}`
- Physical split packages: {physical.get("package_count", 0)}
- Physical source files verified: {physical.get("source_files_verified", False)}
- Physical output frames: {physical.get("total_output_frames", 0)}

Boundary: {materialization["claim_boundary"]}

Physical package boundary: {physical.get("claim_boundary", "Unavailable.")}

## Policy Compatibility

- Pinned LeRobot requirement version: {compatibility.get("lerobot_policy_requirements_version", "not probed")}
- Compatibility report: `{report["artifacts"]["policy_compatibility_report"]}`
- Current package digests match the probe: {compatibility.get("fresh_for_current_package", False)}
- ACT/Diffusion completed a training step: {compatibility.get("all_policy_probes_completed_training_step", False)}
- Probe status: {compatibility.get("status", "not_run")}

{compatibility.get("claim_boundary", "No compatibility probe has been recorded.")}

## Jobs

| Job | Policy | Split | Local train package |
|---|---|---|---|
{job_rows}

## Run

1. Materialize source images or a semantically valid environment-state input and regenerate the split packages.
2. Rerun the compatibility audit until both policies complete the one-step smoke test.
3. Run `bash {report["artifacts"]["run_script"]}` in an environment with LeRobot installed.
4. Evaluate each checkpoint with the offline action-evaluation contract.
5. Run `lerobot-eval` in a high-fidelity environment or `lerobot-rollout` on hardware.
6. Save the required result files listed per job.

The gate remains open while `policy_gate_report.json` has `"pass": false`.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split-manifest", type=Path, default=DEFAULT_SPLIT_MANIFEST)
    parser.add_argument("--leakage-report", type=Path, default=DEFAULT_LEAKAGE_REPORT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--policies", default=",".join(DEFAULT_POLICIES))
    parser.add_argument("--device", default=DEFAULT_DEVICE)
    parser.add_argument("--steps", type=int, default=DEFAULT_STEPS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--wandb", action="store_true")
    parser.add_argument("--rollout-episodes", type=int, default=20)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--required", action="store_true")
    args = parser.parse_args()

    policies = [policy.strip() for policy in args.policies.split(",") if policy.strip()]
    report = build_policy_gate(
        split_manifest_path=args.split_manifest,
        leakage_report_path=args.leakage_report,
        output_dir=args.output_dir,
        policies=policies,
        device=args.device,
        steps=args.steps,
        seed=args.seed,
        wandb=args.wandb,
        rollout_episodes=args.rollout_episodes,
        execute=args.execute,
    )
    print(json.dumps({key: report[key] for key in ("status", "pass", "ready_to_execute", "artifacts")}, indent=2))
    return 1 if args.required and not report["pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
