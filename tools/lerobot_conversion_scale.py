#!/usr/bin/env python3
"""Benchmark exact WorldEpisode round trips over complete pinned LeRobot shards."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import resource
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

try:
    from dataset_license_registry import license_record, source_license_payload
    from lerobot_worldepisode_roundtrip import (
        download_source_files,
        require_pyarrow,
        run_one_roundtrip,
        sha256_file,
    )
except ImportError:  # Imported as tools.lerobot_conversion_scale in tests.
    from tools.dataset_license_registry import license_record, source_license_payload
    from tools.lerobot_worldepisode_roundtrip import (
        download_source_files,
        require_pyarrow,
        run_one_roundtrip,
        sha256_file,
    )


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_DIR = ROOT / ".cache" / "worldepisode" / "lerobot"
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "experiments" / "lerobot_conversion_scale"
REPORT_PATH = DEFAULT_OUTPUT_DIR / "scale_report.json"
README_PATH = DEFAULT_OUTPUT_DIR / "README.md"
SCHEMA = "worldepisode_lerobot_conversion_scale_v1"
WORKER_SCHEMA = "worldepisode_lerobot_conversion_scale_worker_v1"

DATASETS: dict[str, dict[str, Any]] = {
    "svla_so101_pickplace": {
        "repo_id": "lerobot/svla_so101_pickplace",
        "revision": "f641879e22172be7e8161d5e6c1503c2d2feb657",
        "data_chunk_index": 0,
        "data_file_index": 0,
        "expected_episode_count": 50,
        "minimum_video_stream_count": 2,
    },
    "pusht": {
        "repo_id": "lerobot/pusht",
        "revision": "7628202a2180972f291ba1bc6723834921e72c19",
        "data_chunk_index": 0,
        "data_file_index": 0,
        "expected_episode_count": 206,
        "minimum_video_stream_count": 1,
    },
    "armnetbench_file_000": {
        "repo_id": "armnet/armnetbench_v01_lerobot_so101",
        "revision": "2e5e89aee0e7f081078d9d6ab3b279fc4b83ea84",
        "data_chunk_index": 0,
        "data_file_index": 0,
        "expected_episode_count": 15,
        "minimum_video_stream_count": 3,
    },
}

ERROR_KEYS = (
    "max_abs_action_error",
    "max_abs_state_error",
    "max_abs_timestamp_error",
    "max_abs_frame_index_error",
    "max_abs_episode_index_error",
    "max_abs_index_error",
    "max_abs_task_index_error",
    "max_abs_video_timestamp_error",
)


class ConversionScaleError(ValueError):
    """Raised when the pinned conversion-scale protocol is not satisfied."""


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def canonical_digest(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def max_rss_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value * 1024 if sys.platform.startswith("linux") else value)


def total_ram_bytes() -> int | None:
    try:
        return int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"))
    except (AttributeError, OSError, ValueError):
        return None


def git_commit() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    value = result.stdout.strip()
    return value if result.returncode == 0 and len(value) == 40 else None


def gpu_info() -> str | None:
    result = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=name,driver_version,memory.total",
            "--format=csv,noheader,nounits",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    value = result.stdout.strip()
    return value or None


def portable_sources(source_files: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        key: {
            "uri": value["uri"],
            "bytes": value["bytes"],
            "sha256": value["sha256"],
        }
        for key, value in sorted(source_files.items())
    }


def subset_episode_rows(
    episodes_path: Path,
    data_chunk_index: int,
    data_file_index: int,
) -> list[dict[str, Any]]:
    _, pq = require_pyarrow()
    columns = [
        "episode_index",
        "data/chunk_index",
        "data/file_index",
        "length",
    ]
    rows = pq.read_table(episodes_path, columns=columns).to_pylist()
    return [
        row
        for row in rows
        if int(row["data/chunk_index"]) == data_chunk_index
        and int(row["data/file_index"]) == data_file_index
    ]


def run_worker(dataset_id: str, cache_dir: Path, max_download_mb: int) -> dict[str, Any]:
    if dataset_id not in DATASETS:
        raise ConversionScaleError(f"unknown conversion-scale dataset: {dataset_id}")
    config = DATASETS[dataset_id]
    started = time.perf_counter()
    cpu_started = resource.getrusage(resource.RUSAGE_SELF)
    source_files = download_source_files(
        repo_id=config["repo_id"],
        revision=config["revision"],
        cache_dir=cache_dir,
        max_download_bytes=max_download_mb * 1024 * 1024,
    )
    episode_rows = subset_episode_rows(
        Path(source_files["meta/episodes/chunk-000/file-000.parquet"]["local_path"]),
        config["data_chunk_index"],
        config["data_file_index"],
    )
    episode_indices = tuple(int(row["episode_index"]) for row in episode_rows)
    if len(episode_indices) != config["expected_episode_count"]:
        raise ConversionScaleError(
            f"{dataset_id}: expected {config['expected_episode_count']} episodes in the "
            f"pinned source file, found {len(episode_indices)}"
        )
    if len(set(episode_indices)) != len(episode_indices):
        raise ConversionScaleError(f"{dataset_id}: duplicate episode indices")

    info = read_json(Path(source_files["meta/info.json"]["local_path"]))
    video_streams = sorted(
        key
        for key, descriptor in info.get("features", {}).items()
        if descriptor.get("dtype") == "video"
    )
    if len(video_streams) < config["minimum_video_stream_count"]:
        raise ConversionScaleError(
            f"{dataset_id}: expected at least {config['minimum_video_stream_count']} "
            f"video streams, found {len(video_streams)}"
        )

    data_key = (
        f"data/chunk-{config['data_chunk_index']:03d}/"
        f"file-{config['data_file_index']:03d}.parquet"
    )
    data_path = Path(source_files[data_key]["local_path"])
    _, pq = require_pyarrow()
    source_data_rows = int(pq.ParquetFile(data_path).metadata.num_rows)
    expected_rows = sum(int(row["length"]) for row in episode_rows)
    if source_data_rows != expected_rows:
        raise ConversionScaleError(
            f"{dataset_id}: source shard has {source_data_rows} rows but episode metadata "
            f"describes {expected_rows}"
        )

    reports: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix=f"worldepisode-scale-{dataset_id}-") as directory:
        temp_root = Path(directory)
        for episode_index in episode_indices:
            reports.append(
                run_one_roundtrip(
                    source_files=source_files,
                    output_dir=temp_root / f"episode_{episode_index:06d}",
                    repo_id=config["repo_id"],
                    revision=config["revision"],
                    episode_index=episode_index,
                )
            )
        output_bytes = sum(
            path.stat().st_size for path in temp_root.rglob("*") if path.is_file()
        )
        output_file_count = sum(1 for path in temp_root.rglob("*") if path.is_file())

    cpu_finished = resource.getrusage(resource.RUSAGE_SELF)
    wall_time = time.perf_counter() - started
    source_absent = sorted(
        {
            field
            for report in reports
            for field in report["explicitly_tracked_source_absent_fields"]
        }
    )
    max_errors = {
        key: max(float(report["metrics"][key]) for report in reports)
        for key in ERROR_KEYS
    }
    discarded_fields = sorted(
        {
            field
            for report in reports
            for field in report["metrics"]["discarded_fields"]
        }
    )
    row_count = sum(int(report["metrics"]["action_rows"]) for report in reports)
    passed = (
        len(reports) == config["expected_episode_count"]
        and row_count == source_data_rows
        and all(report["pass"] for report in reports)
        and all(value == 0.0 for value in max_errors.values())
        and not discarded_fields
    )
    license_payload = source_license_payload(
        license_record(config["repo_id"], config["revision"])
    )
    return {
        "schema": WORKER_SCHEMA,
        "dataset_id": dataset_id,
        "repo_id": config["repo_id"],
        "revision": config["revision"],
        "source_subset": {
            "data_chunk_index": config["data_chunk_index"],
            "data_file_index": config["data_file_index"],
            "episode_indices": list(episode_indices),
            "episode_index_sha256": canonical_digest(list(episode_indices)),
            "complete_source_file": True,
            "source_data_rows": source_data_rows,
            "source_files": portable_sources(source_files),
            "source_input_bytes": sum(
                int(descriptor["bytes"]) for descriptor in source_files.values()
            ),
            "source_license": license_payload,
        },
        "modality": {
            "video_stream_count": len(video_streams),
            "video_streams": video_streams,
            "source_video_payload_downloaded": False,
        },
        "conversion": {
            "episode_count": len(reports),
            "action_row_count": row_count,
            "state_row_count": sum(
                int(report["metrics"]["state_rows"]) for report in reports
            ),
            "max_errors": max_errors,
            "discarded_fields": discarded_fields,
            "semantic_loss_fields": source_absent,
            "semantic_loss_field_count": len(source_absent),
            "semantic_loss_occurrence_count": sum(
                len(report["explicitly_tracked_source_absent_fields"])
                for report in reports
            ),
            "temporary_output_file_count": output_file_count,
            "temporary_output_bytes": output_bytes,
            "temporary_outputs_retained": False,
        },
        "performance": {
            "wall_time_seconds": wall_time,
            "user_cpu_seconds": cpu_finished.ru_utime - cpu_started.ru_utime,
            "system_cpu_seconds": cpu_finished.ru_stime - cpu_started.ru_stime,
            "max_rss_bytes": max_rss_bytes(),
            "episodes_per_second": len(reports) / wall_time,
            "rows_per_second": row_count / wall_time,
        },
        "validation": {
            "passed": passed,
            "errors": [] if passed else [f"{dataset_id}: round-trip validation failed"],
        },
    }


def run_worker_subprocess(
    dataset_id: str,
    cache_dir: Path,
    max_download_mb: int,
    temp_dir: Path,
) -> dict[str, Any]:
    output_path = temp_dir / f"{dataset_id}.json"
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker",
        dataset_id,
        "--worker-output",
        str(output_path),
        "--cache-dir",
        str(cache_dir),
        "--max-download-mb",
        str(max_download_mb),
    ]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise ConversionScaleError(
            f"{dataset_id} worker failed with exit {result.returncode}: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    report = read_json(output_path)
    if report.get("schema") != WORKER_SCHEMA:
        raise ConversionScaleError(f"{dataset_id} worker returned the wrong schema")
    return report


def validate_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if report.get("schema") != SCHEMA:
        errors.append("wrong report schema")
    datasets = report.get("datasets")
    if not isinstance(datasets, list):
        return [*errors, "datasets must be a list"]
    if {item.get("dataset_id") for item in datasets} != set(DATASETS):
        errors.append("report does not cover the configured dataset set")
    for item in datasets:
        dataset_id = item.get("dataset_id", "unknown")
        if item.get("validation", {}).get("passed") is not True:
            errors.append(f"{dataset_id}: worker validation did not pass")
        if item.get("source_subset", {}).get("complete_source_file") is not True:
            errors.append(f"{dataset_id}: subset is not a complete source file")
        if item.get("modality", {}).get("source_video_payload_downloaded") is not False:
            errors.append(f"{dataset_id}: source video payload was downloaded")
        if item.get("conversion", {}).get("discarded_fields"):
            errors.append(f"{dataset_id}: fields were discarded")
        max_errors = item.get("conversion", {}).get("max_errors", {})
        if set(max_errors) != set(ERROR_KEYS) or any(
            value != 0.0 for value in max_errors.values()
        ):
            errors.append(f"{dataset_id}: numerical round-trip error is nonzero or incomplete")
        performance = item.get("performance", {})
        for field in (
            "wall_time_seconds",
            "user_cpu_seconds",
            "system_cpu_seconds",
            "max_rss_bytes",
            "episodes_per_second",
            "rows_per_second",
        ):
            if not isinstance(performance.get(field), (int, float)) or performance[field] <= 0:
                errors.append(f"{dataset_id}: invalid performance field {field}")
    aggregate = report.get("aggregate", {})
    if aggregate.get("dataset_count") != len(DATASETS):
        errors.append("aggregate dataset count is incorrect")
    if aggregate.get("multi_camera_dataset_count", 0) < 2:
        errors.append("fewer than two multi-camera datasets were measured")
    if aggregate.get("maximum_numerical_error") != 0.0:
        errors.append("aggregate maximum numerical error is nonzero")
    return errors


def build_report(cache_dir: Path, max_download_mb: int) -> dict[str, Any]:
    started = time.perf_counter()
    storage = shutil.disk_usage(ROOT)
    with tempfile.TemporaryDirectory(prefix="worldepisode-scale-workers-") as directory:
        temp_dir = Path(directory)
        datasets = [
            run_worker_subprocess(
                dataset_id,
                cache_dir=cache_dir,
                max_download_mb=max_download_mb,
                temp_dir=temp_dir,
            )
            for dataset_id in DATASETS
        ]
    errors: list[str] = []
    for dataset in datasets:
        errors.extend(dataset["validation"]["errors"])
    report = {
        "schema": SCHEMA,
        "protocol": {
            "selection": (
                "Every episode assigned to one immutable LeRobot v3 source Parquet file per "
                "dataset; no episode-level sampling."
            ),
            "source_media_policy": (
                "Video stream metadata is audited, but source video payloads are not downloaded "
                "or redistributed."
            ),
            "roundtrip": (
                "LeRobot source episode to WorldEpisode sidecar to exported LeRobot package, "
                "followed by exact action/state/index/timestamp comparison."
            ),
        },
        "datasets": datasets,
        "aggregate": {
            "dataset_count": len(datasets),
            "multi_camera_dataset_count": sum(
                item["modality"]["video_stream_count"] >= 2 for item in datasets
            ),
            "episode_count": sum(
                item["conversion"]["episode_count"] for item in datasets
            ),
            "action_row_count": sum(
                item["conversion"]["action_row_count"] for item in datasets
            ),
            "state_row_count": sum(
                item["conversion"]["state_row_count"] for item in datasets
            ),
            "source_input_bytes": sum(
                item["source_subset"]["source_input_bytes"] for item in datasets
            ),
            "temporary_output_bytes": sum(
                item["conversion"]["temporary_output_bytes"] for item in datasets
            ),
            "semantic_loss_field_count": len(
                {
                    field
                    for item in datasets
                    for field in item["conversion"]["semantic_loss_fields"]
                }
            ),
            "semantic_loss_occurrence_count": sum(
                item["conversion"]["semantic_loss_occurrence_count"]
                for item in datasets
            ),
            "maximum_numerical_error": max(
                value
                for item in datasets
                for value in item["conversion"]["max_errors"].values()
            ),
            "worker_wall_time_seconds": sum(
                item["performance"]["wall_time_seconds"] for item in datasets
            ),
            "orchestrator_wall_time_seconds": time.perf_counter() - started,
            "maximum_worker_rss_bytes": max(
                item["performance"]["max_rss_bytes"] for item in datasets
            ),
        },
        "execution": {
            "script": relative(Path(__file__)),
            "script_sha256": sha256_file(Path(__file__)),
            "command": (
                "uv run --with pyarrow --with requests python "
                "tools/lerobot_conversion_scale.py --required"
            ),
            "repository_commit": git_commit(),
            "host": {
                "uname": platform.platform(),
                "machine": platform.machine(),
                "cpu_logical_count": os.cpu_count(),
                "total_ram_bytes": total_ram_bytes(),
                "storage_total_bytes": storage.total,
                "storage_free_bytes": storage.free,
                "gpu_info": gpu_info(),
            },
            "software": {
                "python": platform.python_version(),
                "pyarrow": importlib.metadata.version("pyarrow"),
                "requests": importlib.metadata.version("requests"),
            },
        },
        "validation": {
            "passed": not errors,
            "errors": errors,
        },
        "claim_boundary": (
            "This measures exact low-dimensional LeRobot/WorldEpisode conversion over complete "
            "pinned Parquet shards. It does not convert video payload bytes, prove full-corpus "
            "throughput, or evaluate policy quality."
        ),
        "artifacts": {
            "json": relative(REPORT_PATH),
            "markdown": relative(README_PATH),
        },
    }
    validation_errors = validate_report(report)
    report["validation"] = {
        "passed": not validation_errors,
        "errors": validation_errors,
    }
    return report


def render_markdown(report: dict[str, Any]) -> str:
    rows = "\n".join(
        "| `{dataset_id}` | {episodes} | {rows} | {streams} | {wall:.3f} | "
        "{rss:.1f} | {error:.1f} |".format(
            dataset_id=item["dataset_id"],
            episodes=item["conversion"]["episode_count"],
            rows=item["conversion"]["action_row_count"],
            streams=item["modality"]["video_stream_count"],
            wall=item["performance"]["wall_time_seconds"],
            rss=item["performance"]["max_rss_bytes"] / (1024 * 1024),
            error=max(item["conversion"]["max_errors"].values()),
        )
        for item in report["datasets"]
    )
    errors = report["validation"]["errors"]
    error_text = "\n".join(f"- {error}" for error in errors) if errors else "- None"
    aggregate = report["aggregate"]
    return f"""# LeRobot Conversion Scale

Status: `{"pass" if report["validation"]["passed"] else "fail"}`.

{report["protocol"]["selection"]}

| Dataset subset | Episodes | State/action rows | Video streams | Wall time (s) | Peak RSS (MiB) | Max error |
|---|---:|---:|---:|---:|---:|---:|
{rows}

## Aggregate

- Datasets: {aggregate["dataset_count"]}
- Multi-camera datasets: {aggregate["multi_camera_dataset_count"]}
- Episodes: {aggregate["episode_count"]}
- State/action rows: {aggregate["action_row_count"]}
- Source input bytes: {aggregate["source_input_bytes"]}
- Temporary converted bytes: {aggregate["temporary_output_bytes"]}
- Maximum numerical error: {aggregate["maximum_numerical_error"]}
- Unique source-absent semantic fields: {aggregate["semantic_loss_field_count"]}
- Worker wall time: {aggregate["worker_wall_time_seconds"]:.3f} s
- Maximum worker RSS: {aggregate["maximum_worker_rss_bytes"] / (1024 * 1024):.1f} MiB

Video stream metadata is retained in the sidecar, but source video payloads are neither downloaded
nor redistributed. Temporary converted packages are deleted after exact comparison.

## Claim Boundary

{report["claim_boundary"]}

## Validation Errors

{error_text}
"""


def expected_outputs(report: dict[str, Any]) -> dict[Path, str]:
    return {
        REPORT_PATH: json.dumps(report, indent=2, sort_keys=True) + "\n",
        README_PATH: render_markdown(report),
    }


def write_outputs(report: dict[str, Any]) -> None:
    for path, content in expected_outputs(report).items():
        write_text(path, content)


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
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--max-download-mb", type=int, default=8)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--worker", choices=sorted(DATASETS))
    parser.add_argument("--worker-output", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--required", action="store_true")
    args = parser.parse_args()

    cache_dir = args.cache_dir if args.cache_dir.is_absolute() else ROOT / args.cache_dir
    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    global REPORT_PATH, README_PATH
    REPORT_PATH = output_dir / "scale_report.json"
    README_PATH = output_dir / "README.md"

    if args.worker:
        if args.worker_output is None:
            parser.error("--worker-output is required with --worker")
        try:
            report = run_worker(args.worker, cache_dir, args.max_download_mb)
        except Exception as exc:  # noqa: BLE001 - worker must report the exact failure.
            print(f"conversion-scale worker: {exc}", file=sys.stderr)
            return 1
        write_json(args.worker_output, report)
        return 0

    if args.check:
        try:
            report = read_json(REPORT_PATH)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"conversion scale: {exc}", file=sys.stderr)
            return 1
        errors = validate_report(report) + check_outputs(report)
    else:
        try:
            report = build_report(cache_dir, args.max_download_mb)
        except Exception as exc:  # noqa: BLE001 - emit an actionable required-run failure.
            print(f"conversion scale: {exc}", file=sys.stderr)
            return 1 if args.required else 0
        write_outputs(report)
        errors = report["validation"]["errors"]

    print(
        json.dumps(
            {
                "status": "pass" if not errors else "fail",
                "aggregate": report.get("aggregate", {}),
                "errors": errors,
                "artifacts": report.get("artifacts", {}),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 1 if args.required and errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
