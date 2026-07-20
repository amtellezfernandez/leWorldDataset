#!/usr/bin/env python3
"""Audit held-out action/state telemetry lag across ArmnetBench trajectories."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = (
    ROOT / "docs" / "experiments" / "lerobot_policy_gate" / "physical_splits"
)
DEFAULT_CALIBRATION_PACKAGE = PACKAGE_ROOT / "random_episode_train"
DEFAULT_EVALUATION_PACKAGE = PACKAGE_ROOT / "random_episode_test"
DEFAULT_OUTPUT_DIR = (
    ROOT / "docs" / "experiments" / "lerobot_multitrajectory_timing"
)
REPORT_PATH = DEFAULT_OUTPUT_DIR / "timing_report.json"
README_PATH = DEFAULT_OUTPUT_DIR / "README.md"

SCHEMA = "worldepisode_lerobot_multitrajectory_timing_v1"
MAX_DELAY_FRAMES = 8
BOOTSTRAP_RESAMPLES = 20_000
BOOTSTRAP_SEED = 2027
MISSING_COMMAND_PERIOD = 10
MISSING_COMMAND_PHASE = 5
CONFIDENCE_LEVEL = 0.95


class TimingAuditError(ValueError):
    """Raised when source packages cannot support the timing audit."""


@dataclass(frozen=True)
class Episode:
    local_episode_index: int
    source_episode_index: int
    task_index: int
    task: str
    frame_indices: np.ndarray
    timestamps: np.ndarray
    actions: np.ndarray
    states: np.ndarray


@dataclass(frozen=True)
class Partition:
    root: Path
    info: dict[str, Any]
    manifest: dict[str, Any]
    episodes: tuple[Episode, ...]
    action_names: tuple[str, ...]
    state_names: tuple[str, ...]
    source_columns: tuple[str, ...]


def require_pyarrow() -> Any:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise TimingAuditError(
            "pyarrow is required; run with `uv run --with pyarrow --with numpy`"
        ) from exc
    return pq


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise TimingAuditError(f"required file is missing: {relative(path)}") from exc
    except json.JSONDecodeError as exc:
        raise TimingAuditError(f"invalid JSON in {relative(path)}: {exc}") from exc
    if not isinstance(value, dict):
        raise TimingAuditError(f"expected a JSON object in {relative(path)}")
    return value


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def paired_episode_bootstrap(values: list[float], resamples: int, seed: int) -> dict[str, Any]:
    rng = random.Random(seed)
    sample_size = len(values)
    estimates = [
        statistics.fmean(values[rng.randrange(sample_size)] for _ in range(sample_size))
        for _ in range(resamples)
    ]
    alpha = 1.0 - CONFIDENCE_LEVEL
    return {
        "estimate": statistics.fmean(values),
        "ci_low": quantile(estimates, alpha / 2.0),
        "ci_high": quantile(estimates, 1.0 - alpha / 2.0),
        "confidence_level": CONFIDENCE_LEVEL,
        "method": "paired_percentile_episode_bootstrap",
        "resamples": resamples,
        "seed": seed,
        "sample_size_episodes": sample_size,
        "direction": "zero_delay_rmse_minus_frozen_delay_rmse",
    }


def feature_names(info: dict[str, Any], field: str) -> tuple[str, ...]:
    feature = info.get("features", {}).get(field)
    if not isinstance(feature, dict):
        raise TimingAuditError(f"source package has no {field} feature")
    names = feature.get("names")
    if not isinstance(names, list) or not names or not all(isinstance(v, str) for v in names):
        raise TimingAuditError(f"source package has no named channels for {field}")
    return tuple(names)


def load_partition(path: Path) -> Partition:
    pq = require_pyarrow()
    info_path = path / "meta" / "info.json"
    tasks_path = path / "meta" / "tasks.parquet"
    data_path = path / "data" / "chunk-000" / "file-000.parquet"
    manifest_path = path / "worldepisode_split_package.json"
    info = read_json(info_path)
    manifest = read_json(manifest_path)

    action_names = feature_names(info, "action")
    state_names = feature_names(info, "observation.state")
    schema_names = tuple(pq.ParquetFile(data_path).schema_arrow.names)
    required_columns = (
        "episode_index",
        "frame_index",
        "timestamp",
        "task_index",
        "action",
        "observation.state",
    )
    missing = sorted(set(required_columns) - set(schema_names))
    if missing:
        raise TimingAuditError(f"{relative(data_path)} is missing columns: {', '.join(missing)}")

    task_table = pq.read_table(tasks_path).to_pydict()
    task_map = {
        int(index): str(task)
        for index, task in zip(task_table["task_index"], task_table["task"])
    }
    rows = pq.read_table(data_path, columns=list(required_columns)).to_pydict()
    local_indices = np.asarray(rows["episode_index"], dtype=np.int64)
    frame_indices = np.asarray(rows["frame_index"], dtype=np.int64)
    timestamps = np.asarray(rows["timestamp"], dtype=np.float64)
    task_indices = np.asarray(rows["task_index"], dtype=np.int64)
    actions = np.asarray(rows["action"], dtype=np.float64)
    states = np.asarray(rows["observation.state"], dtype=np.float64)

    mapping_rows = manifest.get("episode_filter", {}).get("local_episode_map")
    if not isinstance(mapping_rows, list):
        raise TimingAuditError(f"{relative(manifest_path)} has no local episode map")
    source_by_local = {
        int(item["local_episode_index"]): int(item["source_episode_index"])
        for item in mapping_rows
    }

    episodes: list[Episode] = []
    for local_index in sorted(np.unique(local_indices).tolist()):
        mask = local_indices == local_index
        local_frames = frame_indices[mask]
        local_tasks = np.unique(task_indices[mask])
        if len(local_tasks) != 1:
            raise TimingAuditError(f"episode {local_index} contains multiple task indices")
        task_index = int(local_tasks[0])
        if task_index not in task_map:
            raise TimingAuditError(f"episode {local_index} references unknown task {task_index}")
        if local_index not in source_by_local:
            raise TimingAuditError(f"episode {local_index} has no source episode mapping")
        if not np.array_equal(local_frames, np.arange(len(local_frames), dtype=np.int64)):
            raise TimingAuditError(f"episode {local_index} frame indices are not contiguous")
        local_timestamps = timestamps[mask]
        if len(local_timestamps) < 2 or np.any(np.diff(local_timestamps) <= 0):
            raise TimingAuditError(f"episode {local_index} timestamps are not strictly increasing")
        local_actions = actions[mask]
        local_states = states[mask]
        if local_actions.shape != local_states.shape:
            raise TimingAuditError(f"episode {local_index} action/state shapes differ")
        if not np.isfinite(local_actions).all() or not np.isfinite(local_states).all():
            raise TimingAuditError(f"episode {local_index} has non-finite action/state values")
        episodes.append(
            Episode(
                local_episode_index=int(local_index),
                source_episode_index=source_by_local[int(local_index)],
                task_index=task_index,
                task=task_map[task_index],
                frame_indices=local_frames,
                timestamps=local_timestamps,
                actions=local_actions,
                states=local_states,
            )
        )

    expected_episodes = int(info.get("total_episodes", -1))
    expected_frames = int(info.get("total_frames", -1))
    if len(episodes) != expected_episodes or len(local_indices) != expected_frames:
        raise TimingAuditError(f"{relative(path)} counts do not match meta/info.json")
    if len(source_by_local) != len(episodes):
        raise TimingAuditError(f"{relative(manifest_path)} episode map count differs from data")

    return Partition(
        root=path,
        info=info,
        manifest=manifest,
        episodes=tuple(episodes),
        action_names=action_names,
        state_names=state_names,
        source_columns=schema_names,
    )


def shifted_errors(episode: Episode, delay_frames: int) -> tuple[np.ndarray, np.ndarray]:
    if delay_frames < 0 or delay_frames >= len(episode.actions):
        raise TimingAuditError("delay must leave at least one comparable frame")
    if delay_frames == 0:
        zero = episode.actions - episode.states
        return zero, zero.copy()
    targets = episode.states[delay_frames:]
    zero = episode.actions[delay_frames:] - targets
    frozen = episode.actions[:-delay_frames] - targets
    return zero, frozen


def rmse(errors: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(errors))))


def aggregate_delay(episodes: tuple[Episode, ...], delay_frames: int) -> dict[str, Any]:
    errors = [shifted_errors(episode, delay_frames)[1] for episode in episodes]
    episode_rmse = [rmse(value) for value in errors]
    combined = np.concatenate(errors, axis=0)
    return {
        "delay_frames": delay_frames,
        "compared_rows": int(sum(len(value) for value in errors)),
        "pooled_joint_rmse": rmse(combined),
        "episode_rmse_mean": statistics.fmean(episode_rmse),
        "episode_rmse_median": statistics.median(episode_rmse),
        "per_joint_rmse": [rmse(combined[:, index]) for index in range(combined.shape[1])],
    }


def schedule_actions(
    episode: Episode,
    delay_s: float,
    *,
    interpolation: str,
    remove_commands: bool,
) -> tuple[np.ndarray, np.ndarray]:
    timestamps = episode.timestamps
    keep = np.ones(len(timestamps), dtype=bool)
    if remove_commands:
        keep = (episode.frame_indices % MISSING_COMMAND_PERIOD) != MISSING_COMMAND_PHASE
        keep[0] = True
    command_timestamps = timestamps[keep]
    command_actions = episode.actions[keep]
    target_mask = timestamps >= timestamps[0] + delay_s - 1e-9
    target_timestamps = timestamps[target_mask]
    query_timestamps = target_timestamps - delay_s
    if interpolation == "zero_order_hold":
        indices = np.searchsorted(command_timestamps, query_timestamps + 1e-7, side="right") - 1
        indices = np.clip(indices, 0, len(command_timestamps) - 1)
        scheduled = command_actions[indices]
    elif interpolation == "linear":
        scheduled = np.column_stack(
            [
                np.interp(query_timestamps, command_timestamps, command_actions[:, joint])
                for joint in range(command_actions.shape[1])
            ]
        )
    else:
        raise TimingAuditError(f"unknown interpolation policy: {interpolation}")
    return scheduled, episode.states[target_mask]


def scheduler_summary(
    episodes: tuple[Episode, ...],
    delay_s: float,
    *,
    interpolation: str,
    remove_commands: bool,
) -> dict[str, Any]:
    errors = []
    episode_values = []
    for episode in episodes:
        scheduled, targets = schedule_actions(
            episode,
            delay_s,
            interpolation=interpolation,
            remove_commands=remove_commands,
        )
        error = scheduled - targets
        errors.append(error)
        episode_values.append(rmse(error))
    combined = np.concatenate(errors, axis=0)
    return {
        "interpolation": interpolation,
        "source_commands_removed": remove_commands,
        "pooled_joint_rmse": rmse(combined),
        "episode_rmse_mean": statistics.fmean(episode_values),
        "compared_rows": int(sum(len(value) for value in errors)),
    }


def partition_descriptor(partition: Partition) -> dict[str, Any]:
    data_path = partition.root / "data" / "chunk-000" / "file-000.parquet"
    manifest_path = partition.root / "worldepisode_split_package.json"
    source_dataset = partition.manifest.get("source_dataset", {})
    return {
        "path": relative(partition.root),
        "partition": partition.manifest.get("target_dataset", {}).get("partition"),
        "episode_count": len(partition.episodes),
        "frame_count": int(sum(len(episode.actions) for episode in partition.episodes)),
        "task_count": len({episode.task_index for episode in partition.episodes}),
        "source_episode_count": len(
            {episode.source_episode_index for episode in partition.episodes}
        ),
        "source_dataset": {
            "repo_id": source_dataset.get("repo_id"),
            "revision": source_dataset.get("revision"),
        },
        "artifacts": {
            "data": {
                "path": relative(data_path),
                "sha256": sha256_file(data_path),
                "bytes": data_path.stat().st_size,
            },
            "package_manifest": {
                "path": relative(manifest_path),
                "sha256": sha256_file(manifest_path),
                "bytes": manifest_path.stat().st_size,
            },
        },
    }


def evaluate(
    episodes: tuple[Episode, ...],
    delay_frames: int,
    delay_s: float,
    resamples: int,
    seed: int,
) -> dict[str, Any]:
    zero_errors = []
    frozen_errors = []
    rows = []
    for episode in episodes:
        zero, frozen = shifted_errors(episode, delay_frames)
        zero_value = rmse(zero)
        frozen_value = rmse(frozen)
        zero_errors.append(zero)
        frozen_errors.append(frozen)
        rows.append(
            {
                "local_episode_index": episode.local_episode_index,
                "source_episode_index": episode.source_episode_index,
                "task_index": episode.task_index,
                "task": episode.task,
                "compared_rows": len(frozen),
                "zero_delay_rmse": zero_value,
                "frozen_delay_rmse": frozen_value,
                "rmse_improvement": zero_value - frozen_value,
                "improved": frozen_value < zero_value,
            }
        )

    zero_combined = np.concatenate(zero_errors, axis=0)
    frozen_combined = np.concatenate(frozen_errors, axis=0)
    improvements = [float(row["rmse_improvement"]) for row in rows]
    task_rows = []
    for task_index in sorted({episode.task_index for episode in episodes}):
        selected = [row for row in rows if row["task_index"] == task_index]
        task_rows.append(
            {
                "task_index": task_index,
                "task": selected[0]["task"],
                "episode_count": len(selected),
                "improved_episode_count": sum(row["improved"] for row in selected),
                "zero_delay_rmse_mean": statistics.fmean(
                    row["zero_delay_rmse"] for row in selected
                ),
                "frozen_delay_rmse_mean": statistics.fmean(
                    row["frozen_delay_rmse"] for row in selected
                ),
                "rmse_improvement_mean": statistics.fmean(
                    row["rmse_improvement"] for row in selected
                ),
            }
        )

    source_missing_commands = sum(
        len(episode.frame_indices)
        - len(np.unique(episode.frame_indices))
        for episode in episodes
    )
    return {
        "episode_count": len(episodes),
        "task_count": len(task_rows),
        "frame_count": int(sum(len(episode.actions) for episode in episodes)),
        "compared_row_count": int(sum(len(value) for value in frozen_errors)),
        "zero_delay": {
            "pooled_joint_rmse": rmse(zero_combined),
            "episode_rmse_mean": statistics.fmean(row["zero_delay_rmse"] for row in rows),
            "episode_rmse_median": statistics.median(row["zero_delay_rmse"] for row in rows),
            "per_joint_rmse": [
                rmse(zero_combined[:, index]) for index in range(zero_combined.shape[1])
            ],
        },
        "frozen_frame_delay": {
            "delay_frames": delay_frames,
            "delay_s": delay_s,
            "pooled_joint_rmse": rmse(frozen_combined),
            "episode_rmse_mean": statistics.fmean(
                row["frozen_delay_rmse"] for row in rows
            ),
            "episode_rmse_median": statistics.median(
                row["frozen_delay_rmse"] for row in rows
            ),
            "per_joint_rmse": [
                rmse(frozen_combined[:, index])
                for index in range(frozen_combined.shape[1])
            ],
        },
        "paired_episode_improvement": {
            **paired_episode_bootstrap(improvements, resamples, seed),
            "improved_episode_count": sum(row["improved"] for row in rows),
            "non_improved_episode_count": sum(not row["improved"] for row in rows),
        },
        "by_task": task_rows,
        "per_episode": rows,
        "scheduler_sensitivity": {
            "source_missing_command_count": source_missing_commands,
            "timestamp_zero_order_hold": scheduler_summary(
                episodes,
                delay_s,
                interpolation="zero_order_hold",
                remove_commands=False,
            ),
            "timestamp_linear": scheduler_summary(
                episodes,
                delay_s,
                interpolation="linear",
                remove_commands=False,
            ),
            "synthetic_missing_command_protocol": {
                "description": (
                    "Remove frames whose within-episode index modulo the period equals the phase; "
                    "retain frame zero."
                ),
                "period_frames": MISSING_COMMAND_PERIOD,
                "phase": MISSING_COMMAND_PHASE,
                "zero_order_hold": scheduler_summary(
                    episodes,
                    delay_s,
                    interpolation="zero_order_hold",
                    remove_commands=True,
                ),
                "linear": scheduler_summary(
                    episodes,
                    delay_s,
                    interpolation="linear",
                    remove_commands=True,
                ),
            },
        },
    }


def validate_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    source = report.get("source", {})
    calibration = report.get("calibration", {})
    evaluation = report.get("evaluation", {})
    improvement = evaluation.get("paired_episode_improvement", {})
    by_task = evaluation.get("by_task", [])
    if report.get("schema") != SCHEMA:
        errors.append("unexpected report schema")
    if source.get("source_episode_overlap_count") != 0:
        errors.append("calibration and evaluation source episodes overlap")
    if source.get("action_state_channel_names_match") is not True:
        errors.append("action and state channel names differ")
    if source.get("effective_motor_timestamp_available") is not False:
        errors.append("motor timestamp availability must reflect the source boundary")
    if int(calibration.get("episode_count", 0)) < 20:
        errors.append("fewer than 20 calibration episodes")
    if int(evaluation.get("episode_count", 0)) < 20:
        errors.append("fewer than 20 held-out episodes")
    if int(evaluation.get("task_count", 0)) < 2:
        errors.append("fewer than two held-out tasks")
    delay = int(calibration.get("selected_delay_frames", 0))
    if delay <= 0 or delay >= int(report.get("protocol", {}).get("max_delay_frames", 0)):
        errors.append("selected delay is zero or on the search boundary")
    if float(improvement.get("ci_low", 0.0)) <= 0:
        errors.append("held-out paired improvement CI includes zero")
    if int(improvement.get("improved_episode_count", 0)) != int(
        evaluation.get("episode_count", -1)
    ):
        errors.append("not every held-out episode improves")
    if not by_task or any(float(row.get("rmse_improvement_mean", 0.0)) <= 0 for row in by_task):
        errors.append("at least one held-out task does not improve")
    if float(evaluation.get("frozen_frame_delay", {}).get("pooled_joint_rmse", math.inf)) >= float(
        evaluation.get("zero_delay", {}).get("pooled_joint_rmse", 0.0)
    ):
        errors.append("frozen delay does not improve pooled held-out RMSE")
    timestamp_linear = (
        evaluation.get("scheduler_sensitivity", {})
        .get("timestamp_linear", {})
        .get("pooled_joint_rmse", math.inf)
    )
    frozen = evaluation.get("frozen_frame_delay", {}).get("pooled_joint_rmse", 0.0)
    if not math.isclose(
        float(timestamp_linear),
        float(frozen),
        rel_tol=0.0,
        abs_tol=1e-6,
    ):
        errors.append(
            "timestamp-linear and frozen frame delay disagree on the regular source grid"
        )
    return errors


def build_report(
    calibration_path: Path,
    evaluation_path: Path,
    max_delay_frames: int,
    resamples: int,
    seed: int,
) -> dict[str, Any]:
    calibration_partition = load_partition(calibration_path)
    evaluation_partition = load_partition(evaluation_path)
    if calibration_partition.action_names != calibration_partition.state_names:
        raise TimingAuditError("calibration action/state channel names differ")
    if evaluation_partition.action_names != evaluation_partition.state_names:
        raise TimingAuditError("evaluation action/state channel names differ")
    if calibration_partition.action_names != evaluation_partition.action_names:
        raise TimingAuditError("calibration/evaluation channel names differ")
    if calibration_partition.info.get("fps") != evaluation_partition.info.get("fps"):
        raise TimingAuditError("calibration/evaluation frame rates differ")

    calibration_source = {
        episode.source_episode_index for episode in calibration_partition.episodes
    }
    evaluation_source = {
        episode.source_episode_index for episode in evaluation_partition.episodes
    }
    overlap = sorted(calibration_source & evaluation_source)
    calibration_tasks = {episode.task_index for episode in calibration_partition.episodes}
    evaluation_tasks = {episode.task_index for episode in evaluation_partition.episodes}
    if calibration_tasks != evaluation_tasks:
        raise TimingAuditError("calibration/evaluation task support differs")

    by_delay = [
        aggregate_delay(calibration_partition.episodes, delay)
        for delay in range(max_delay_frames + 1)
    ]
    selected = min(by_delay, key=lambda row: (row["pooled_joint_rmse"], row["delay_frames"]))
    macro_selected = min(
        by_delay,
        key=lambda row: (row["episode_rmse_mean"], row["delay_frames"]),
    )
    delay_frames = int(selected["delay_frames"])
    sample_period_s = 1.0 / float(calibration_partition.info["fps"])
    delay_s = delay_frames * sample_period_s
    evaluation = evaluate(
        evaluation_partition.episodes,
        delay_frames,
        delay_s,
        resamples,
        seed,
    )

    timestamp_like_columns = [
        column
        for column in calibration_partition.source_columns
        if any(token in column.lower() for token in ("timestamp", "enqueue", "consume", "motor"))
    ]
    effective_motor_columns = [
        column
        for column in timestamp_like_columns
        if any(token in column.lower() for token in ("effective", "receive", "motor"))
    ]
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "measured_telemetry_lag_proxy",
        "claim_boundary": (
            "The audit measures lag between same-named action targets and observed joint-state "
            "telemetry on one SO-101 dataset. The source has one frame timestamp and no command-"
            "enqueue, queue-consume, or motor-effective timestamps, so this is not measured motor "
            "latency or evidence across robot/controller configurations. Timestamp scheduling uses "
            "the same sampled frame timestamps rather than independent queue observations; its "
            "result is interpolation-sensitive under float32 timestamp quantization."
        ),
        "source": {
            "dataset": {
                "repo_id": calibration_partition.manifest.get("source_dataset", {}).get(
                    "repo_id"
                ),
                "revision": calibration_partition.manifest.get("source_dataset", {}).get(
                    "revision"
                ),
            },
            "calibration_package": partition_descriptor(calibration_partition),
            "evaluation_package": partition_descriptor(evaluation_partition),
            "source_episode_overlap_count": len(overlap),
            "source_episode_overlap": overlap,
            "action_names": list(calibration_partition.action_names),
            "state_names": list(calibration_partition.state_names),
            "action_state_channel_names_match": True,
            "position_unit_declared_by_source": False,
            "metric_unit": "source_position_units",
            "timestamp_columns": timestamp_like_columns,
            "effective_motor_timestamp_columns": effective_motor_columns,
            "effective_motor_timestamp_available": bool(effective_motor_columns),
            "controller_configuration_count": 1,
            "robot_type_count": 1,
        },
        "protocol": {
            "selection": (
                "Choose the integer delay minimizing sample-weighted joint RMSE over calibration "
                "episodes; freeze it before reading held-out metrics."
            ),
            "comparison": (
                "For delay d, compare action[t] and action[t-d] against state[t] on the identical "
                "within-episode target rows t >= d; no cross-episode padding."
            ),
            "calibration_partition": relative(calibration_path),
            "evaluation_partition": relative(evaluation_path),
            "max_delay_frames": max_delay_frames,
            "bootstrap_resamples": resamples,
            "bootstrap_seed": seed,
            "confidence_level": CONFIDENCE_LEVEL,
            "timestamp_scheduler": "latest command at or before state_timestamp - frozen_delay",
            "source_interpolation_policy": "not declared",
            "source_missing_command_policy": "not declared",
        },
        "calibration": {
            "episode_count": len(calibration_partition.episodes),
            "task_count": len(calibration_tasks),
            "frame_count": int(
                sum(len(episode.actions) for episode in calibration_partition.episodes)
            ),
            "sample_period_s": sample_period_s,
            "sample_rate_hz": 1.0 / sample_period_s,
            "selected_delay_frames": delay_frames,
            "selected_delay_s": delay_s,
            "sample_weighted_selection": selected,
            "episode_macro_selected_delay_frames": int(macro_selected["delay_frames"]),
            "by_delay": by_delay,
        },
        "evaluation": evaluation,
        "acceptance": {
            "heldout_multiple_trajectories": True,
            "heldout_multiple_tasks": True,
            "paired_ci_excludes_zero": (
                evaluation["paired_episode_improvement"]["ci_low"] > 0
            ),
            "not_driven_by_one_trajectory": (
                evaluation["paired_episode_improvement"]["improved_episode_count"]
                == evaluation["episode_count"]
            ),
            "motor_timestamp_error_measured": False,
            "second_robot_or_controller_measured": False,
            "action_002_fully_satisfied": False,
            "remaining_gates": [
                "motor-effective timestamps or an independently instrumented latency target",
                "a second robot or controller configuration",
                "an independently distinguishable queue-aware scheduler comparison",
            ],
        },
        "execution": {
            "script": relative(Path(__file__)),
            "script_sha256": sha256_file(Path(__file__)),
        },
        "artifacts": {
            "json": relative(REPORT_PATH),
            "readme": relative(README_PATH),
        },
        "reproduce": (
            "uv run --with pyarrow --with numpy python "
            "tools/lerobot_multitrajectory_timing_audit.py --required"
        ),
    }
    errors = validate_report(report)
    report["validation"] = {"passed": not errors, "errors": errors}
    return report


def render_markdown(report: dict[str, Any]) -> str:
    calibration = report["calibration"]
    evaluation = report["evaluation"]
    improvement = evaluation["paired_episode_improvement"]
    frozen = evaluation["frozen_frame_delay"]
    zero = evaluation["zero_delay"]
    task_rows = "\n".join(
        (
            f"| {row['task_index']} | {row['episode_count']} | "
            f"{row['zero_delay_rmse_mean']:.6f} | "
            f"{row['frozen_delay_rmse_mean']:.6f} | "
            f"{row['rmse_improvement_mean']:.6f} |"
        )
        for row in evaluation["by_task"]
    )
    return f"""# Multi-Trajectory SO-101 Telemetry-Lag Audit

This generated report freezes an integer action/state lag using the calibration package, then
evaluates it on source-episode-disjoint trajectories.

- Calibration: {calibration["episode_count"]} episodes across {calibration["task_count"]} tasks.
- Held out: {evaluation["episode_count"]} episodes across {evaluation["task_count"]} tasks.
- Frozen lag: {calibration["selected_delay_frames"]} frames ({1000 * calibration["selected_delay_s"]:.1f} ms at the source frame rate).
- Held-out zero-delay pooled RMSE: {zero["pooled_joint_rmse"]:.6f} source position units.
- Held-out frozen-delay pooled RMSE: {frozen["pooled_joint_rmse"]:.6f} source position units.
- Mean paired episode improvement: {improvement["estimate"]:.6f}
  (95% CI {improvement["ci_low"]:.6f} to {improvement["ci_high"]:.6f}).
- Improved held-out episodes: {improvement["improved_episode_count"]}/{evaluation["episode_count"]}.

| Task index | Episodes | Zero-delay mean RMSE | Frozen-delay mean RMSE | Mean improvement |
|---:|---:|---:|---:|---:|
{task_rows}

## Boundary

{report["claim_boundary"]}

`ACTION.002` remains open because motor-effective timestamps, a second controller configuration,
and an independently distinguishable queue-aware scheduler comparison are not available.

## Reproduce

```bash
{report["reproduce"]}
```
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
    parser.add_argument("--calibration-package", type=Path, default=DEFAULT_CALIBRATION_PACKAGE)
    parser.add_argument("--evaluation-package", type=Path, default=DEFAULT_EVALUATION_PACKAGE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-delay-frames", type=int, default=MAX_DELAY_FRAMES)
    parser.add_argument("--bootstrap-resamples", type=int, default=BOOTSTRAP_RESAMPLES)
    parser.add_argument("--bootstrap-seed", type=int, default=BOOTSTRAP_SEED)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--required", action="store_true")
    args = parser.parse_args()

    calibration_path = (
        args.calibration_package
        if args.calibration_package.is_absolute()
        else ROOT / args.calibration_package
    )
    evaluation_path = (
        args.evaluation_package
        if args.evaluation_package.is_absolute()
        else ROOT / args.evaluation_package
    )
    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    global REPORT_PATH, README_PATH
    REPORT_PATH = output_dir / "timing_report.json"
    README_PATH = output_dir / "README.md"

    try:
        report = build_report(
            calibration_path,
            evaluation_path,
            args.max_delay_frames,
            args.bootstrap_resamples,
            args.bootstrap_seed,
        )
    except (OSError, TimingAuditError, ValueError) as exc:
        print(f"multi-trajectory timing audit: {exc}", file=sys.stderr)
        return 1 if args.required else 0

    errors = list(report["validation"]["errors"])
    if args.check:
        errors.extend(check_outputs(report))
    else:
        write_outputs(report)
    print(
        json.dumps(
            {
                "status": "pass" if not errors else "fail",
                "calibration": {
                    "episodes": report["calibration"]["episode_count"],
                    "selected_delay_frames": report["calibration"]["selected_delay_frames"],
                },
                "evaluation": {
                    "episodes": report["evaluation"]["episode_count"],
                    "tasks": report["evaluation"]["task_count"],
                    "improvement": report["evaluation"]["paired_episode_improvement"],
                },
                "errors": errors,
                "artifacts": report["artifacts"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 1 if args.required and errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
