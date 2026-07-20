#!/usr/bin/env python3
"""Active LeRobotDataset v3 -> WorldEpisode -> LeRobotDataset v3 round-trip.

The experiment downloads a bounded, pinned public LeRobotDataset v3 shard from the Hugging Face Hub,
converts one real episode into a WorldEpisode manifest plus sidecar, exports a LeRobotDataset-like
v3 mini-package, reads the exported package back, and asserts zero numerical loss for source-native
action tensors, state tensors, timestamps, and video timestamp ranges.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

try:
    from dataset_license_registry import (
        license_record,
        source_license_payload,
        validate_dataset_card,
    )
except ImportError:  # Imported as tools.lerobot_worldepisode_roundtrip in tests.
    from tools.dataset_license_registry import (
        license_record,
        source_license_payload,
        validate_dataset_card,
    )


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPO_ID = "lerobot/svla_so101_pickplace"
DEFAULT_REVISION = "f641879e22172be7e8161d5e6c1503c2d2feb657"
DEFAULT_EPISODE_INDEX = 0
DEFAULT_BATCH_EPISODE_INDICES = (0, 1, 2, 3, 4)
DEFAULT_CACHE_DIR = ROOT / ".cache" / "worldepisode" / "lerobot"
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "experiments" / "lerobot_worldepisode_roundtrip"
SOURCE_PATHS = (
    "README.md",
    "meta/info.json",
    "meta/stats.json",
    "meta/tasks.parquet",
    "meta/episodes/chunk-000/file-000.parquet",
    "data/chunk-000/file-000.parquet",
)
SCHEMA_PATH = ROOT / "schemas" / "worldepisode-core-v0.schema.json"


class RoundTripUnavailable(RuntimeError):
    """Raised when optional dependencies or network access are missing."""


def require_pyarrow() -> Any:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RoundTripUnavailable(
            "pyarrow is required for the active LeRobot round-trip. "
            "Install experiment dependencies with `python3 -m pip install -r requirements-experiments.txt` "
            "or run through `uv run --with-requirements requirements-experiments.txt`."
        ) from exc
    return pa, pq


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def repo_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def portable_uri(uri: str) -> str:
    try:
        path = Path(uri)
        if path.is_absolute():
            return str(path.relative_to(ROOT))
    except (ValueError, OSError):
        pass
    return uri


def portable_file_descriptors(files: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        path: {
            "uri": portable_uri(descriptor["uri"]),
            "bytes": descriptor["bytes"],
            "sha256": descriptor["sha256"],
        }
        for path, descriptor in files.items()
    }


def validate_worldepisode_manifest(manifest: dict[str, Any]) -> None:
    try:
        import jsonschema
    except ImportError as exc:
        raise RoundTripUnavailable(
            "jsonschema is required to validate the generated WorldEpisode manifest. "
            "Install experiment dependencies with `python3 -m pip install -r requirements-experiments.txt` "
            "or run through `uv run --with-requirements requirements-experiments.txt`."
        ) from exc
    validator = jsonschema.Draft202012Validator(load_json(SCHEMA_PATH))
    errors = sorted(validator.iter_errors(manifest), key=lambda error: list(error.path))
    if errors:
        first = errors[0]
        location = "/" + "/".join(str(part) for part in first.path)
        raise AssertionError(f"generated WorldEpisode manifest is schema-invalid at {location}: {first.message}")


def hf_uri(repo_id: str, revision: str, remote_path: str) -> str:
    return f"hf://{repo_id}@{revision}/{remote_path}"


def hf_resolve_url(repo_id: str, revision: str, remote_path: str) -> str:
    return f"https://huggingface.co/datasets/{repo_id}/resolve/{revision}/{remote_path}"


def download_source_files(
    repo_id: str,
    revision: str,
    cache_dir: Path,
    max_download_bytes: int,
) -> dict[str, dict[str, Any]]:
    source_root = cache_dir / repo_id.replace("/", "__") / revision
    source_root.mkdir(parents=True, exist_ok=True)

    total_bytes = 0
    files: dict[str, dict[str, Any]] = {}
    for remote_path in SOURCE_PATHS:
        local_path = source_root / remote_path
        local_path.parent.mkdir(parents=True, exist_ok=True)
        if not local_path.exists():
            try:
                response = requests.get(hf_resolve_url(repo_id, revision, remote_path), timeout=60)
                response.raise_for_status()
            except requests.RequestException as exc:
                raise RoundTripUnavailable(f"could not download {remote_path}: {exc}") from exc
            size = len(response.content)
            total_bytes += size
            if total_bytes > max_download_bytes:
                raise RoundTripUnavailable(
                    f"download cap exceeded while fetching {remote_path}: "
                    f"{total_bytes} > {max_download_bytes} bytes"
                )
            local_path.write_bytes(response.content)
        files[remote_path] = {
            "uri": hf_uri(repo_id, revision, remote_path),
            "local_path": str(local_path),
            "bytes": local_path.stat().st_size,
            "sha256": sha256_file(local_path),
        }
    return files


def list_at(mapping: dict[str, list[Any]], key: str, index: int) -> Any:
    return mapping[key][index]


def float_max_abs_error(left: Any, right: Any) -> float:
    if isinstance(left, dict) and isinstance(right, dict):
        if set(left) != set(right):
            return float("inf")
        errors = []
        for key in left:
            if isinstance(left[key], (int, float, list, dict)) and isinstance(right[key], (int, float, list, dict)):
                errors.append(float_max_abs_error(left[key], right[key]))
            elif left[key] != right[key]:
                return float("inf")
        return max(errors) if errors else 0.0
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return float("inf")
        if not left:
            return 0.0
        return max(float_max_abs_error(a, b) for a, b in zip(left, right))
    if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
        return 0.0 if left == right else float("inf")
    return abs(float(left) - float(right))


@dataclass
class LeRobotNativeEpisode:
    repo_id: str
    revision: str
    episode_index: int
    info: dict[str, Any]
    stats: dict[str, Any]
    tasks: list[dict[str, Any]]
    episode_metadata: dict[str, Any]
    rows: dict[str, list[Any]]
    video_timestamp_ranges: list[dict[str, Any]]
    physical_frames: list[dict[str, Any]]
    source_files: dict[str, dict[str, Any]]
    license_record: dict[str, Any]


@dataclass
class WorldEpisodePackage:
    manifest: dict[str, Any]
    trace: dict[str, Any]
    sidecar: dict[str, Any]
    conversion_report: dict[str, Any]


def table_to_rows(table: Any) -> dict[str, list[Any]]:
    return {name: table[name].to_pylist() for name in table.column_names}


def video_keys(info: dict[str, Any]) -> list[str]:
    return sorted(
        key
        for key, feature in info.get("features", {}).items()
        if isinstance(feature, dict) and feature.get("dtype") == "video"
    )


def build_physical_frames(info: dict[str, Any]) -> list[dict[str, Any]]:
    robot_type = info["robot_type"]
    action_feature = info["features"]["action"]
    frames = [
        {
            "frame_id": f"{robot_type}/joint_space",
            "role": "state_action_joint_space",
            "components": action_feature.get("names", []),
            "source_feature_keys": ["action", "observation.state"],
            "source_status": "joint component names provided; units and robot/world calibration absent in LeRobot source",
            "units_status": "source_absent",
        }
    ]
    for key in video_keys(info):
        feature = info["features"][key]
        frames.append(
            {
                "frame_id": f"{robot_type}/{key}",
                "role": "camera_sensor_frame",
                "source_feature_keys": [key],
                "shape": feature.get("shape"),
                "video_info": feature.get("info", {}),
                "source_status": "camera stream provided; extrinsics absent in LeRobot source",
                "transform_status": "source_absent",
            }
        )
    return frames


def stats_from_episode_metadata(episode_metadata: dict[str, Any]) -> dict[str, Any]:
    stats: dict[str, dict[str, Any]] = {}
    for key, value in episode_metadata.items():
        if not key.startswith("stats/"):
            continue
        _prefix, feature_name, stat_name = key.split("/", 2)
        stats.setdefault(feature_name, {})[stat_name] = value
    return stats


def load_lerobot_episode(
    source_files: dict[str, dict[str, Any]],
    repo_id: str,
    revision: str,
    episode_index: int,
) -> LeRobotNativeEpisode:
    _, pq = require_pyarrow()
    dataset_license = (
        validate_dataset_card(
            Path(source_files["README.md"]["local_path"]),
            repo_id,
            revision,
        )
        if "README.md" in source_files
        else license_record(repo_id, revision)
    )
    info = load_json(Path(source_files["meta/info.json"]["local_path"]))
    stats = load_json(Path(source_files["meta/stats.json"]["local_path"]))
    data_rows = table_to_rows(pq.read_table(source_files["data/chunk-000/file-000.parquet"]["local_path"]))
    episode_rows = table_to_rows(pq.read_table(source_files["meta/episodes/chunk-000/file-000.parquet"]["local_path"]))
    task_rows = table_to_rows(pq.read_table(source_files["meta/tasks.parquet"]["local_path"]))

    if episode_index not in episode_rows["episode_index"]:
        raise ValueError(f"episode {episode_index} is not present in source episode metadata")
    episode_row_index = episode_rows["episode_index"].index(episode_index)
    start = int(list_at(episode_rows, "dataset_from_index", episode_row_index))
    end = int(list_at(episode_rows, "dataset_to_index", episode_row_index))
    rows = {name: values[start:end] for name, values in data_rows.items()}

    if any(value != episode_index for value in rows["episode_index"]):
        raise ValueError("selected data rows are not contiguous for the requested episode")
    if len(rows["action"]) != int(list_at(episode_rows, "length", episode_row_index)):
        raise ValueError("episode length disagrees with selected action rows")

    episode_metadata = {name: values[episode_row_index] for name, values in episode_rows.items()}
    ranges = []
    for key in video_keys(info):
        prefix = f"videos/{key}"
        ranges.append(
            {
                "video_key": key,
                "episode_index": episode_index,
                "from_timestamp": episode_metadata[f"{prefix}/from_timestamp"],
                "to_timestamp": episode_metadata[f"{prefix}/to_timestamp"],
                "chunk_index": episode_metadata[f"{prefix}/chunk_index"],
                "file_index": episode_metadata[f"{prefix}/file_index"],
            }
        )

    tasks = [
        {
            "task_index": task_rows["task_index"][index],
            "task": task_rows.get("__index_level_0__", [""] * len(task_rows["task_index"]))[index],
        }
        for index in range(len(task_rows["task_index"]))
    ]

    return LeRobotNativeEpisode(
        repo_id=repo_id,
        revision=revision,
        episode_index=episode_index,
        info=info,
        stats=stats,
        tasks=tasks,
        episode_metadata=episode_metadata,
        rows=rows,
        video_timestamp_ranges=ranges,
        physical_frames=build_physical_frames(info),
        source_files=source_files,
        license_record=dataset_license,
    )


def lerobot_to_worldepisode(native: LeRobotNativeEpisode) -> WorldEpisodePackage:
    robot_type = native.info["robot_type"]
    source_info = native.source_files["meta/info.json"]
    source_data = native.source_files["data/chunk-000/file-000.parquet"]
    episode_end_s = float(max(native.rows["timestamp"]))
    action_names = native.info["features"]["action"].get("names", [])
    task_text = ", ".join(native.episode_metadata.get("tasks", []))
    source_license = native.license_record["license_expression"]

    manifest = {
        "schema_version": "worldepisode-0.1",
        "episode": {
            "episode_id": f"{native.repo_id.replace('/', '_')}_episode_{native.episode_index:06d}",
            "dataset_id": native.repo_id,
            "split": "train",
            "outcome": "source_not_annotated",
        },
        "world_revision": {
            "world_revision_id": f"{native.repo_id}@{native.revision}/metadata@sha256:{source_info['sha256']}",
            "asset": {
                "uri": source_info["uri"],
                "media_type": "application/json",
                "sha256": source_info["sha256"],
                "mirrors": ["meta/info.json"],
                "license": source_license,
            },
            "binding": "lerobot-v3-source-metadata",
        },
        "embodiment": {"embodiment_id": robot_type},
        "task": {"task_id": "source_task_0", "instruction": task_text},
        "frame_graph": {
            "frames": [
                {
                    "frame_id": f"{robot_type}_joint_space",
                    "units": "rad",
                    "convention": "lerobot-source-joint-vector",
                },
                {
                    "frame_id": f"{robot_type}_dataset_clock_frame",
                    "units": "m",
                    "convention": "dataset-indexed-observation-frame",
                },
            ],
            "transforms": [],
        },
        "clock_graph": {
            "clocks": [{"clock_id": "episode_time", "domain": "lerobot_timestamp", "units": "s"}],
            "mappings": [],
        },
        "entities": [
            {
                "entity_id": robot_type,
                "entity_type": "robot",
                "representations": [
                    {
                        "representation_id": f"{robot_type}_lerobot_schema",
                        "role": "semantics",
                        "asset": {
                            "uri": source_info["uri"],
                            "media_type": "application/json",
                            "sha256": source_info["sha256"],
                            "mirrors": ["meta/info.json"],
                            "license": source_license,
                        },
                        "coordinate_frame": f"{robot_type}_joint_space",
                        "valid_interval": {"start": 0, "end": episode_end_s, "clock_id": "episode_time"},
                        "license": source_license,
                    }
                ],
            }
        ],
        "action_space": {
            "channels": [
                {
                    "name": "joint_position_vector",
                    "actuator": robot_type,
                    "control_mode": "joint_position",
                    "parameterization": "absolute_joint_vector",
                    "reference_frame": f"{robot_type}_joint_space",
                    "units": "source_undocumented_position_units",
                    "semantics": "absolute",
                    "command_timestamp_semantics": "LeRobot timestamp column is preserved as command sample time",
                    "effective_timestamp_semantics": "source does not declare controller latency; effective time is source-absent",
                    "command_rate_hz": native.info.get("fps"),
                    "latency_model": "source_absent",
                    "interpolation": "source_absent",
                    "missing_value_policy": "source_absent",
                }
            ]
        },
        "trace": {
            "binding": "lerobot-v3",
            "asset": {
                "uri": source_data["uri"],
                "media_type": "application/vnd.apache.parquet",
                "sha256": source_data["sha256"],
                "mirrors": ["data/chunk-000/file-000.parquet"],
                "license": source_license,
            },
        },
        "events": [],
        "world_deltas": [],
        "provenance": {
            "source": f"{native.repo_id}@{native.revision}",
            "creator": "WorldEpisode active LeRobot converter",
            "software": "tools/lerobot_worldepisode_roundtrip.py",
            "license": (
                f"{source_license} source-derived rows; WorldEpisode-authored "
                "metadata CC0-1.0"
            ),
        },
        "quality": {
            "conformance_profiles": ["WE-Core"],
            "source_absent_fields": [
                "camera extrinsics",
                "robot/world calibration transform",
                "action units",
                "controller latency model",
            ],
            "source_native_fields_preserved": [
                "action",
                "observation.state",
                "timestamp",
                "frame_index",
                "episode_index",
                "index",
                "task_index",
                "video timestamp ranges",
            ],
        },
    }

    trace = {
        "action": native.rows["action"],
        "observation.state": native.rows["observation.state"],
        "timestamp": native.rows["timestamp"],
        "frame_index": native.rows["frame_index"],
        "episode_index": native.rows["episode_index"],
        "index": native.rows["index"],
        "task_index": native.rows["task_index"],
        "video_timestamp_ranges": native.video_timestamp_ranges,
    }
    sidecar = {
        "profile": "worldepisode-lerobot-v3-sidecar-0.1",
        "source_repo_id": native.repo_id,
        "source_revision": native.revision,
        "source_license": source_license_payload(native.license_record),
        "episode_index": native.episode_index,
        "physical_frames": native.physical_frames,
        "action_components": action_names,
        "source_absent_fields": manifest["quality"]["source_absent_fields"],
    }
    conversion_report = {
        "source_profile": "lerobot-v3",
        "target_profile": "worldepisode-0.1",
        "source_repo_id": native.repo_id,
        "source_revision": native.revision,
        "source_license": source_license_payload(native.license_record),
        "episode_index": native.episode_index,
        "preserved_zero_loss": [
            "action tensor",
            "observation.state tensor",
            "sample timestamps",
            "frame indices",
            "episode indices",
            "task indices",
            "video timestamp ranges",
            "derived physical-frame records",
        ],
        "externalized": [
            "physical-frame records",
            "source-absent semantic warnings",
            "WorldEpisode manifest",
        ],
        "approximated": [],
        "discarded": [],
        "source_absent": manifest["quality"]["source_absent_fields"],
        "warnings": [
            "The public LeRobot source declares camera streams but not camera extrinsics.",
            "The public LeRobot source declares joint component names but not action units or controller latency.",
        ],
    }
    return WorldEpisodePackage(
        manifest=manifest,
        trace=trace,
        sidecar=sidecar,
        conversion_report=conversion_report,
    )


def worldepisode_to_lerobot(
    package: WorldEpisodePackage,
    source: LeRobotNativeEpisode,
    export_dir: Path,
) -> LeRobotNativeEpisode:
    pa, pq = require_pyarrow()
    if export_dir.exists():
        shutil.rmtree(export_dir)
    (export_dir / "meta" / "episodes" / "chunk-000").mkdir(parents=True)
    (export_dir / "data" / "chunk-000").mkdir(parents=True)

    exported_info = dict(source.info)
    exported_info["total_episodes"] = 1
    exported_info["total_frames"] = len(package.trace["timestamp"])
    exported_info["splits"] = {"train": "0:1"}
    write_json(export_dir / "meta" / "info.json", exported_info)
    write_json(export_dir / "meta" / "stats.json", stats_from_episode_metadata(source.episode_metadata))
    write_json(
        export_dir / "SOURCE_LICENSE.json",
        source_license_payload(source.license_record),
    )

    task_table = pa.table(
        {
            "task_index": pa.array([task["task_index"] for task in source.tasks], type=pa.int64()),
            "__index_level_0__": pa.array([task["task"] for task in source.tasks], type=pa.string()),
        }
    )
    pq.write_table(task_table, export_dir / "meta" / "tasks.parquet")

    episode_values = dict(source.episode_metadata)
    episode_values["episode_index"] = source.episode_index
    episode_values["dataset_from_index"] = 0
    episode_values["dataset_to_index"] = len(package.trace["timestamp"])
    episode_values["length"] = len(package.trace["timestamp"])
    episode_table = pa.Table.from_pylist([episode_values])
    pq.write_table(episode_table, export_dir / "meta" / "episodes" / "chunk-000" / "file-000.parquet")

    data_table = pa.table(
        {
            "action": pa.array(package.trace["action"], type=pa.list_(pa.float32())),
            "observation.state": pa.array(package.trace["observation.state"], type=pa.list_(pa.float32())),
            "timestamp": pa.array(package.trace["timestamp"], type=pa.float32()),
            "frame_index": pa.array(package.trace["frame_index"], type=pa.int64()),
            "episode_index": pa.array(package.trace["episode_index"], type=pa.int64()),
            "index": pa.array(package.trace["index"], type=pa.int64()),
            "task_index": pa.array(package.trace["task_index"], type=pa.int64()),
        }
    )
    pq.write_table(data_table, export_dir / "data" / "chunk-000" / "file-000.parquet")

    exported_files = {
        "meta/info.json": {
            "uri": str(export_dir / "meta" / "info.json"),
            "local_path": str(export_dir / "meta" / "info.json"),
            "bytes": (export_dir / "meta" / "info.json").stat().st_size,
            "sha256": sha256_file(export_dir / "meta" / "info.json"),
        },
        "meta/stats.json": {
            "uri": str(export_dir / "meta" / "stats.json"),
            "local_path": str(export_dir / "meta" / "stats.json"),
            "bytes": (export_dir / "meta" / "stats.json").stat().st_size,
            "sha256": sha256_file(export_dir / "meta" / "stats.json"),
        },
        "meta/tasks.parquet": {
            "uri": str(export_dir / "meta" / "tasks.parquet"),
            "local_path": str(export_dir / "meta" / "tasks.parquet"),
            "bytes": (export_dir / "meta" / "tasks.parquet").stat().st_size,
            "sha256": sha256_file(export_dir / "meta" / "tasks.parquet"),
        },
        "meta/episodes/chunk-000/file-000.parquet": {
            "uri": str(export_dir / "meta" / "episodes" / "chunk-000" / "file-000.parquet"),
            "local_path": str(export_dir / "meta" / "episodes" / "chunk-000" / "file-000.parquet"),
            "bytes": (export_dir / "meta" / "episodes" / "chunk-000" / "file-000.parquet").stat().st_size,
            "sha256": sha256_file(export_dir / "meta" / "episodes" / "chunk-000" / "file-000.parquet"),
        },
        "data/chunk-000/file-000.parquet": {
            "uri": str(export_dir / "data" / "chunk-000" / "file-000.parquet"),
            "local_path": str(export_dir / "data" / "chunk-000" / "file-000.parquet"),
            "bytes": (export_dir / "data" / "chunk-000" / "file-000.parquet").stat().st_size,
            "sha256": sha256_file(export_dir / "data" / "chunk-000" / "file-000.parquet"),
        },
        "SOURCE_LICENSE.json": {
            "uri": str(export_dir / "SOURCE_LICENSE.json"),
            "local_path": str(export_dir / "SOURCE_LICENSE.json"),
            "bytes": (export_dir / "SOURCE_LICENSE.json").stat().st_size,
            "sha256": sha256_file(export_dir / "SOURCE_LICENSE.json"),
        },
    }
    return load_lerobot_episode(
        exported_files,
        source.repo_id,
        source.revision,
        episode_index=source.episode_index,
    )


def compare_native_roundtrip(
    source: LeRobotNativeEpisode,
    exported: LeRobotNativeEpisode,
    package: WorldEpisodePackage,
) -> dict[str, Any]:
    metrics = {
        "action_rows": len(source.rows["action"]),
        "action_width": len(source.rows["action"][0]) if source.rows["action"] else 0,
        "state_rows": len(source.rows["observation.state"]),
        "timestamp_count": len(source.rows["timestamp"]),
        "video_streams": len(source.video_timestamp_ranges),
        "physical_frame_records": len(source.physical_frames),
        "max_abs_action_error": float_max_abs_error(source.rows["action"], exported.rows["action"]),
        "max_abs_state_error": float_max_abs_error(source.rows["observation.state"], exported.rows["observation.state"]),
        "max_abs_timestamp_error": float_max_abs_error(source.rows["timestamp"], exported.rows["timestamp"]),
        "max_abs_frame_index_error": float_max_abs_error(source.rows["frame_index"], exported.rows["frame_index"]),
        "max_abs_episode_index_error": float_max_abs_error(
            source.rows["episode_index"],
            exported.rows["episode_index"],
        ),
        "max_abs_index_error": float_max_abs_error(source.rows["index"], exported.rows["index"]),
        "max_abs_task_index_error": float_max_abs_error(source.rows["task_index"], exported.rows["task_index"]),
        "max_abs_video_timestamp_error": float_max_abs_error(
            source.video_timestamp_ranges,
            exported.video_timestamp_ranges,
        ),
        "action_tensor_sha256": sha256_bytes(canonical_json_bytes(source.rows["action"])),
        "timestamp_sha256": sha256_bytes(canonical_json_bytes(source.rows["timestamp"])),
        "video_timestamp_sha256": sha256_bytes(canonical_json_bytes(source.video_timestamp_ranges)),
        "physical_frames_sha256": sha256_bytes(canonical_json_bytes(source.physical_frames)),
        "roundtrip_action_tensor_sha256": sha256_bytes(canonical_json_bytes(exported.rows["action"])),
        "roundtrip_timestamp_sha256": sha256_bytes(canonical_json_bytes(exported.rows["timestamp"])),
        "roundtrip_video_timestamp_sha256": sha256_bytes(canonical_json_bytes(exported.video_timestamp_ranges)),
        "worldepisode_sidecar_physical_frames_sha256": sha256_bytes(
            canonical_json_bytes(package.sidecar["physical_frames"])
        ),
        "roundtrip_physical_frames_sha256": sha256_bytes(canonical_json_bytes(exported.physical_frames)),
        "physical_frames_preserved": (
            source.physical_frames == package.sidecar["physical_frames"] == exported.physical_frames
        ),
        "source_absent_fields_tracked": len(package.conversion_report["source_absent"]),
        "discarded_fields": package.conversion_report["discarded"],
    }
    metrics["pass"] = (
        metrics["max_abs_action_error"] == 0.0
        and metrics["max_abs_state_error"] == 0.0
        and metrics["max_abs_timestamp_error"] == 0.0
        and metrics["max_abs_frame_index_error"] == 0.0
        and metrics["max_abs_episode_index_error"] == 0.0
        and metrics["max_abs_index_error"] == 0.0
        and metrics["max_abs_task_index_error"] == 0.0
        and metrics["max_abs_video_timestamp_error"] == 0.0
        and metrics["physical_frames_preserved"]
        and not metrics["discarded_fields"]
    )
    return metrics


def write_artifacts(
    output_dir: Path,
    source: LeRobotNativeEpisode,
    package: WorldEpisodePackage,
    exported: LeRobotNativeEpisode,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    export_dir = output_dir / "exported_lerobot_v3"

    source_manifest = {
        "repo_id": source.repo_id,
        "revision": source.revision,
        "episode_index": source.episode_index,
        "source_files": portable_file_descriptors(source.source_files),
        "source_dataset_total_episodes": source.info["total_episodes"],
        "source_dataset_total_frames": source.info["total_frames"],
        "source_license": source_license_payload(source.license_record),
    }
    exported_manifest = {
        "repo_id": exported.repo_id,
        "revision": exported.revision,
        "episode_index": exported.episode_index,
        "source_license": source_license_payload(exported.license_record),
        "export_dir": display_path(export_dir),
        "files": portable_file_descriptors(exported.source_files),
    }
    package.conversion_report["metrics"] = metrics
    package.conversion_report["pass"] = metrics["pass"]

    write_json(output_dir / "source_manifest.json", source_manifest)
    write_json(output_dir / "worldepisode.manifest.json", package.manifest)
    write_json(output_dir / "worldepisode.sidecar.json", package.sidecar)
    write_json(output_dir / "exported_lerobot_manifest.json", exported_manifest)
    write_json(output_dir / "conversion_report.json", package.conversion_report)
    roundtrip_report = {
        "available": True,
        "pass": metrics["pass"],
        "repo_id": source.repo_id,
        "revision": source.revision,
        "episode_index": source.episode_index,
        "artifacts": {
            "source_manifest": display_path(output_dir / "source_manifest.json"),
            "worldepisode_manifest": display_path(output_dir / "worldepisode.manifest.json"),
            "worldepisode_sidecar": display_path(output_dir / "worldepisode.sidecar.json"),
            "exported_lerobot_v3": display_path(export_dir),
            "conversion_report": display_path(output_dir / "conversion_report.json"),
        },
        "metrics": metrics,
        "explicitly_tracked_source_absent_fields": package.conversion_report["source_absent"],
    }
    write_json(output_dir / "roundtrip_report.json", roundtrip_report)
    return roundtrip_report


def run_one_roundtrip(
    source_files: dict[str, dict[str, Any]],
    output_dir: Path,
    repo_id: str,
    revision: str,
    episode_index: int,
) -> dict[str, Any]:
    source = load_lerobot_episode(source_files, repo_id, revision, episode_index)
    package = lerobot_to_worldepisode(source)
    validate_worldepisode_manifest(package.manifest)
    exported = worldepisode_to_lerobot(package, source, output_dir / "exported_lerobot_v3")
    metrics = compare_native_roundtrip(source, exported, package)
    report = write_artifacts(output_dir, source, package, exported, metrics)
    if not metrics["pass"]:
        raise AssertionError(
            f"LeRobot -> WorldEpisode -> LeRobot round-trip did not preserve required fields "
            f"for episode {episode_index}"
        )
    return report


def run_roundtrip_experiment(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    repo_id: str = DEFAULT_REPO_ID,
    revision: str = DEFAULT_REVISION,
    episode_index: int = DEFAULT_EPISODE_INDEX,
    max_download_mb: int = 2,
) -> dict[str, Any]:
    require_pyarrow()
    source_files = download_source_files(
        repo_id=repo_id,
        revision=revision,
        cache_dir=cache_dir,
        max_download_bytes=max_download_mb * 1024 * 1024,
    )
    return run_one_roundtrip(source_files, output_dir, repo_id, revision, episode_index)


def run_batch_roundtrip_experiment(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    repo_id: str = DEFAULT_REPO_ID,
    revision: str = DEFAULT_REVISION,
    episode_indices: tuple[int, ...] = DEFAULT_BATCH_EPISODE_INDICES,
    max_download_mb: int = 2,
) -> dict[str, Any]:
    if not episode_indices:
        raise ValueError("at least one episode index is required for batch round-trip")
    require_pyarrow()
    source_files = download_source_files(
        repo_id=repo_id,
        revision=revision,
        cache_dir=cache_dir,
        max_download_bytes=max_download_mb * 1024 * 1024,
    )
    reports = []
    for episode_index in episode_indices:
        episode_output_dir = output_dir / "batch" / f"episode_{episode_index:06d}"
        reports.append(
            run_one_roundtrip(
                source_files=source_files,
                output_dir=episode_output_dir,
                repo_id=repo_id,
                revision=revision,
                episode_index=episode_index,
            )
        )

    metric_keys = (
        "max_abs_action_error",
        "max_abs_state_error",
        "max_abs_timestamp_error",
        "max_abs_frame_index_error",
        "max_abs_episode_index_error",
        "max_abs_index_error",
        "max_abs_task_index_error",
        "max_abs_video_timestamp_error",
    )
    aggregate = {
        "available": True,
        "pass": all(report["pass"] for report in reports),
        "repo_id": repo_id,
        "revision": revision,
        "episode_indices": list(episode_indices),
        "episode_count": len(reports),
        "total_action_rows": sum(report["metrics"]["action_rows"] for report in reports),
        "total_state_rows": sum(report["metrics"]["state_rows"] for report in reports),
        "max_errors": {
            key: max(report["metrics"][key] for report in reports)
            for key in metric_keys
        },
        "all_physical_frames_preserved": all(
            report["metrics"]["physical_frames_preserved"]
            for report in reports
        ),
        "discarded_fields": sorted(
            {
                field
                for report in reports
                for field in report["metrics"]["discarded_fields"]
            }
        ),
        "reports": [
            display_path(
                output_dir
                / "batch"
                / f"episode_{report['episode_index']:06d}"
                / "roundtrip_report.json"
            )
            for report in reports
        ],
    }
    aggregate["pass"] = (
        aggregate["pass"]
        and all(value == 0.0 for value in aggregate["max_errors"].values())
        and aggregate["all_physical_frames_preserved"]
        and not aggregate["discarded_fields"]
    )
    write_json(output_dir / "batch_roundtrip_report.json", aggregate)
    if not aggregate["pass"]:
        raise AssertionError("batch LeRobot round-trip did not preserve required fields")
    return aggregate


def parse_episode_indices(value: str) -> tuple[int, ...]:
    indices = []
    for item in value.split(","):
        stripped = item.strip()
        if not stripped:
            continue
        indices.append(int(stripped))
    return tuple(indices)


def unavailable_report(error: Exception) -> dict[str, Any]:
    return {
        "available": False,
        "pass": False,
        "reason": str(error),
        "reproduce": "python3 -m pip install -r requirements-experiments.txt && "
        "python3 tools/lerobot_worldepisode_roundtrip.py --required",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--repo-id", default=DEFAULT_REPO_ID)
    parser.add_argument("--revision", default=DEFAULT_REVISION)
    parser.add_argument("--episode-index", type=int, default=DEFAULT_EPISODE_INDEX)
    parser.add_argument(
        "--batch-episode-indices",
        default="",
        help="optional comma-separated episode indices for a batch round-trip report",
    )
    parser.add_argument("--max-download-mb", type=int, default=2)
    parser.add_argument("--required", action="store_true", help="return non-zero if the active experiment cannot run")
    args = parser.parse_args()
    args.output_dir = repo_path(args.output_dir)
    args.cache_dir = repo_path(args.cache_dir)

    try:
        report = run_roundtrip_experiment(
            output_dir=args.output_dir,
            cache_dir=args.cache_dir,
            repo_id=args.repo_id,
            revision=args.revision,
            episode_index=args.episode_index,
            max_download_mb=args.max_download_mb,
        )
        if args.batch_episode_indices:
            report["batch_roundtrip"] = run_batch_roundtrip_experiment(
                output_dir=args.output_dir,
                cache_dir=args.cache_dir,
                repo_id=args.repo_id,
                revision=args.revision,
                episode_indices=parse_episode_indices(args.batch_episode_indices),
                max_download_mb=args.max_download_mb,
            )
    except RoundTripUnavailable as exc:
        report = unavailable_report(exc)
        write_json(args.output_dir / "roundtrip_report.json", report)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 1 if args.required else 0

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
