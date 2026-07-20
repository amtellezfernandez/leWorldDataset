#!/usr/bin/env python3
"""Run and verify preregistered ACT/Diffusion offline policy experiments.

The required run consists of 20 training jobs (two policies, two split
conditions, and five matched seeds) plus sequential teacher-observation
evaluation on the exact source episodes shared by both test packages.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import platform
import re
import resource
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = (
    ROOT / "docs" / "experiments" / "lerobot_policy_full_training"
)
DEFAULT_PROTOCOL = DEFAULT_OUTPUT_DIR / "protocol.json"
DEFAULT_JOBS = DEFAULT_OUTPUT_DIR / "jobs.json"
DEFAULT_REFERENCE = DEFAULT_OUTPUT_DIR / "evaluation_reference.json"
DEFAULT_REPORT = DEFAULT_OUTPUT_DIR / "offline_policy_report.json"
DEFAULT_WORK_ROOT = ROOT / "outputs" / "lerobot_policy_full_training"
PROFILE = "worldepisode-lerobot-offline-policy-protocol-0.1"
JOBS_PROFILE = "worldepisode-lerobot-offline-policy-jobs-0.1"
REFERENCE_PROFILE = "worldepisode-lerobot-offline-policy-evaluation-reference-0.1"
TRAIN_REPORT_PROFILE = "worldepisode-lerobot-offline-policy-training-report-0.1"
EVAL_REPORT_PROFILE = "worldepisode-lerobot-offline-policy-evaluation-report-0.1"
REPORT_PROFILE = "worldepisode-lerobot-offline-policy-report-0.1"


class PolicyExperimentError(RuntimeError):
    """Raised when an experiment invariant is not satisfied."""


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PolicyExperimentError(f"missing required file: {relative(path)}") from exc
    except json.JSONDecodeError as exc:
        raise PolicyExperimentError(f"invalid JSON in {relative(path)}: {exc}") from exc


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def sha256_payload(payload: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def file_descriptor(path: Path) -> dict[str, Any]:
    return {
        "path": relative(path),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def tree_descriptor(path: Path) -> dict[str, Any]:
    if not path.is_dir():
        raise PolicyExperimentError(f"missing artifact directory: {relative(path)}")
    files = []
    for child in sorted(path.rglob("*")):
        if child.is_symlink() or not child.is_file():
            continue
        files.append(
            {
                "path": str(child.relative_to(path)),
                "size_bytes": child.stat().st_size,
                "sha256": sha256_file(child),
            }
        )
    if not files:
        raise PolicyExperimentError(f"artifact directory is empty: {relative(path)}")
    return {
        "path": relative(path),
        "file_count": len(files),
        "total_size_bytes": sum(item["size_bytes"] for item in files),
        "tree_sha256": sha256_payload(files),
        "files": files,
    }


def git_output(*args: str) -> str | None:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        return None
    value = completed.stdout.strip()
    return value or None


def protocol_preregistration(protocol_path: Path) -> dict[str, Any]:
    path = relative(protocol_path)
    history = git_output("log", "--diff-filter=A", "--format=%H", "--", path)
    first_commit = history.splitlines()[-1] if history else None
    current_commit = git_output("rev-parse", "HEAD")
    committed_before = False
    if first_commit and current_commit:
        committed_before = (
            subprocess.run(
                ["git", "merge-base", "--is-ancestor", first_commit, current_commit],
                cwd=ROOT,
                check=False,
            ).returncode
            == 0
        )
    return {
        "path": path,
        "sha256": sha256_file(protocol_path),
        "git_blob_oid": git_output("hash-object", path),
        "first_committed_revision": first_commit,
        "execution_source_revision": current_commit,
        "committed_before_required_execution": committed_before,
    }


def validate_protocol(protocol: dict[str, Any]) -> None:
    if protocol.get("profile") != PROFILE:
        raise PolicyExperimentError("unexpected policy protocol profile")
    if protocol.get("protocol_id") != "POLICY.OFFLINE.001.armnet.v1":
        raise PolicyExperimentError("unexpected policy protocol id")

    training = protocol.get("training", {})
    policies = training.get("policies")
    if policies != ["act", "diffusion"]:
        raise PolicyExperimentError("protocol policies must be ACT and Diffusion")
    seeds = training.get("seeds")
    if (
        not isinstance(seeds, list)
        or len(seeds) < 5
        or len(seeds) != len(set(seeds))
        or any(isinstance(seed, bool) or not isinstance(seed, int) for seed in seeds)
    ):
        raise PolicyExperimentError("protocol requires at least five unique integer seeds")
    splits = training.get("split_conditions")
    if not isinstance(splits, list) or [item.get("id") for item in splits] != [
        "random_episode",
        "task_confounded_lineage_holdout",
    ]:
        raise PolicyExperimentError("protocol split conditions changed")
    if [item.get("package_split_name") for item in splits] != [
        "random_episode",
        "scene_disjoint",
    ]:
        raise PolicyExperimentError("protocol split package mapping changed")
    expected_jobs = len(policies) * len(splits) * len(seeds)
    if protocol.get("acceptance", {}).get("required_job_count") != expected_jobs:
        raise PolicyExperimentError("required job count does not match the training grid")
    if expected_jobs != 20:
        raise PolicyExperimentError("required policy grid must contain exactly 20 jobs")
    if training.get("steps") != 20000:
        raise PolicyExperimentError("required training run must use 20,000 optimizer steps")
    if training.get("save_frequency") <= 0 or (
        training["steps"] % training["save_frequency"]
    ):
        raise PolicyExperimentError("checkpoint frequency must divide training steps")
    if training.get("environment_evaluation_frequency") != 0:
        raise PolicyExperimentError("offline protocol must disable environment evaluation")
    if training.get("evaluation_steps") != 0:
        raise PolicyExperimentError("offline protocol must not add an unregistered loss split")
    if training.get("cudnn_deterministic") is not True:
        raise PolicyExperimentError("deterministic cuDNN mode must be enabled")

    evaluation = protocol.get("evaluation", {})
    selection = evaluation.get("episode_selection", {})
    episodes = selection.get("expected_source_episode_indices")
    if not isinstance(episodes, list) or episodes != sorted(set(episodes)):
        raise PolicyExperimentError("evaluation source episodes must be sorted and unique")
    if len(episodes) != selection.get("expected_episode_count"):
        raise PolicyExperimentError("evaluation episode count does not match its list")
    if sha256_payload(episodes) != selection.get(
        "expected_source_episode_indices_sha256"
    ):
        raise PolicyExperimentError("evaluation episode-list digest is stale")
    if evaluation.get("metrics", {}).get("success_threshold") is not None:
        raise PolicyExperimentError("offline protocol must not define a success threshold")
    if evaluation.get("mode") != (
        "sequential_teacher_observation_native_action_queue"
    ):
        raise PolicyExperimentError("unsupported evaluation mode")
    if protocol.get("runtime", {}).get("lerobot_version") != "0.6.0":
        raise PolicyExperimentError("LeRobot runtime must remain pinned to 0.6.0")
    boundary = protocol.get("claim_boundary", {})
    excluded = set(boundary.get("does_not_establish", []))
    for claim in (
        "closed_loop_task_success",
        "scene_only_leakage",
        "physical_robot_rollout_impact",
    ):
        if claim not in excluded:
            raise PolicyExperimentError(f"claim boundary must exclude {claim}")


def protocol_descriptor(protocol_path: Path) -> dict[str, Any]:
    return {
        "path": relative(protocol_path),
        "sha256": sha256_file(protocol_path),
    }


def split_by_id(protocol: dict[str, Any], split_id: str) -> dict[str, Any]:
    for split in protocol["training"]["split_conditions"]:
        if split["id"] == split_id:
            return split
    raise PolicyExperimentError(f"unknown split id: {split_id}")


def package_root(
    protocol: dict[str, Any],
    split_id: str,
    partition: str,
) -> Path:
    split = split_by_id(protocol, split_id)
    return (
        ROOT
        / protocol["source"]["physical_split_root"]
        / f"{split['package_split_name']}_{partition}"
    )


def make_job(
    protocol: dict[str, Any],
    policy: str,
    split: dict[str, Any],
    seed: int,
) -> dict[str, Any]:
    job_id = f"{policy}__{split['id']}__seed{seed:02d}"
    train_root = package_root(protocol, split["id"], "train")
    test_root = package_root(protocol, split["id"], "test")
    work_dir = DEFAULT_WORK_ROOT / job_id
    train = protocol["training"]
    command = [
        "python",
        "-m",
        "lerobot.scripts.lerobot_train",
        (
            "--dataset.repo_id="
            f"worldepisode/armnetbench_v01_lerobot_so101_{split['package_split_name']}_train"
        ),
        f"--dataset.root={relative(train_root)}",
        f"--policy.type={policy}",
        "--policy.push_to_hub=false",
        f"--output_dir={relative(work_dir / 'training')}",
        f"--job_name={job_id}",
        "--policy.device=cuda",
        f"--steps={train['steps']}",
        f"--batch_size={train['batch_size']}",
        f"--num_workers={train['num_workers']}",
        f"--save_checkpoint={str(train['save_checkpoint']).lower()}",
        f"--save_freq={train['save_frequency']}",
        f"--env_eval_freq={train['environment_evaluation_frequency']}",
        f"--eval_steps={train['evaluation_steps']}",
        f"--log_freq={train['log_frequency']}",
        f"--cudnn_deterministic={str(train['cudnn_deterministic']).lower()}",
        f"--wandb.enable={str(train['wandb']).lower()}",
        f"--seed={seed}",
    ]
    job = {
        "job_id": job_id,
        "policy": policy,
        "split_id": split["id"],
        "package_split_name": split["package_split_name"],
        "seed": seed,
        "train_dataset_root": relative(train_root),
        "test_dataset_root": relative(test_root),
        "work_dir": relative(work_dir),
        "training_command_template": command,
        "final_checkpoint": relative(
            work_dir
            / "training"
            / "checkpoints"
            / f"{train['steps']:06d}"
            / "pretrained_model"
        ),
        "training_report": relative(
            DEFAULT_OUTPUT_DIR / "jobs" / job_id / "training_report.json"
        ),
        "evaluation_report": relative(
            DEFAULT_OUTPUT_DIR / "jobs" / job_id / "evaluation_report.json"
        ),
        "raw_predictions": relative(work_dir / "evaluation_predictions.npz"),
    }
    job["job_definition_sha256"] = sha256_payload(job)
    return job


def make_jobs_payload(
    protocol: dict[str, Any],
    protocol_path: Path = DEFAULT_PROTOCOL,
) -> dict[str, Any]:
    validate_protocol(protocol)
    jobs = [
        make_job(protocol, policy, split, seed)
        for policy in protocol["training"]["policies"]
        for split in protocol["training"]["split_conditions"]
        for seed in protocol["training"]["seeds"]
    ]
    if len({job["job_id"] for job in jobs}) != len(jobs):
        raise PolicyExperimentError("generated job ids are not unique")
    return {
        "profile": JOBS_PROFILE,
        "protocol": protocol_descriptor(protocol_path),
        "job_count": len(jobs),
        "jobs": jobs,
        "jobs_sha256": sha256_payload(jobs),
    }


def shell_quote(value: str) -> str:
    return subprocess.list2cmdline([value])


def render_run_script(jobs_payload: dict[str, Any]) -> str:
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        "# Run inside the protocol's pinned uv environment after camera materialization.",
        "python tools/lerobot_policy_full_training.py --check-inputs",
        "",
    ]
    for job in jobs_payload["jobs"]:
        lines.extend(
            [
                f"python tools/lerobot_policy_full_training.py --run-job {shell_quote(job['job_id'])}",
                f"python tools/lerobot_policy_full_training.py --evaluate-job {shell_quote(job['job_id'])}",
                "",
            ]
        )
    lines.extend(
        [
            "python tools/lerobot_policy_full_training.py --aggregate",
            "python tools/lerobot_policy_full_training.py --check --required",
            "",
        ]
    )
    return "\n".join(lines)


def jobs_by_id(jobs_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {job["job_id"]: job for job in jobs_payload["jobs"]}


def package_episode_map(path: Path) -> dict[int, int]:
    package = load_json(path / "worldepisode_split_package.json")
    mapping = package.get("episode_filter", {}).get("local_episode_map", [])
    result = {
        int(item["source_episode_index"]): int(item["local_episode_index"])
        for item in mapping
    }
    if len(result) != len(mapping):
        raise PolicyExperimentError(f"duplicate source episode in {relative(path)}")
    return result


def _import_data_dependencies() -> tuple[Any, Any]:
    try:
        import numpy as np
        import pyarrow.parquet as pq
    except ModuleNotFoundError as exc:
        raise PolicyExperimentError(
            "numpy and pyarrow are required; run in the pinned uv environment"
        ) from exc
    return np, pq


def _task_map(pq: Any, path: Path) -> dict[int, str]:
    table = pq.read_table(path / "meta" / "tasks.parquet")
    columns = set(table.column_names)
    if not {"task_index", "task"}.issubset(columns):
        raise PolicyExperimentError(f"unexpected tasks schema in {relative(path)}")
    return {
        int(index): str(task)
        for index, task in zip(
            table["task_index"].to_pylist(),
            table["task"].to_pylist(),
            strict=True,
        )
    }


def _episode_data(
    np: Any,
    pq: Any,
    path: Path,
    source_to_local: dict[int, int],
    source_episodes: list[int],
) -> dict[int, dict[str, Any]]:
    table = pq.read_table(
        path / "data" / "chunk-000" / "file-000.parquet",
        columns=[
            "action",
            "episode_index",
            "frame_index",
            "timestamp",
            "task_index",
        ],
    )
    local_column = np.asarray(table["episode_index"].to_pylist(), dtype=np.int64)
    frame_column = np.asarray(table["frame_index"].to_pylist(), dtype=np.int64)
    action_column = table["action"].to_pylist()
    timestamp_column = np.asarray(table["timestamp"].to_pylist(), dtype=np.float64)
    task_column = np.asarray(table["task_index"].to_pylist(), dtype=np.int64)
    tasks = _task_map(pq, path)
    result = {}
    for source_episode in source_episodes:
        local_episode = source_to_local[source_episode]
        indices = np.flatnonzero(local_column == local_episode)
        indices = indices[np.argsort(frame_column[indices], kind="stable")]
        if len(indices) == 0:
            raise PolicyExperimentError(
                f"source episode {source_episode} has no rows in {relative(path)}"
            )
        task_indices = sorted(set(int(task_column[index]) for index in indices))
        if len(task_indices) != 1 or task_indices[0] not in tasks:
            raise PolicyExperimentError(
                f"source episode {source_episode} has inconsistent task metadata"
            )
        actions = np.asarray(
            [action_column[index] for index in indices],
            dtype=np.float32,
        )
        result[source_episode] = {
            "source_episode_index": source_episode,
            "local_episode_index": local_episode,
            "frame_index": frame_column[indices],
            "timestamps": timestamp_column[indices],
            "actions": actions,
            "task_index": task_indices[0],
            "task": tasks[task_indices[0]],
        }
    return result


def array_sha256(np: Any, value: Any, dtype: str) -> str:
    array = np.asarray(value, dtype=dtype)
    return hashlib.sha256(array.tobytes(order="C")).hexdigest()


def build_evaluation_reference(
    protocol: dict[str, Any],
    protocol_path: Path = DEFAULT_PROTOCOL,
) -> dict[str, Any]:
    validate_protocol(protocol)
    np, pq = _import_data_dependencies()
    random_path = package_root(protocol, "random_episode", "test")
    heldout_path = package_root(
        protocol,
        "task_confounded_lineage_holdout",
        "test",
    )
    random_map = package_episode_map(random_path)
    heldout_map = package_episode_map(heldout_path)
    shared = sorted(set(random_map) & set(heldout_map))
    expected = protocol["evaluation"]["episode_selection"]
    if shared != expected["expected_source_episode_indices"]:
        raise PolicyExperimentError(
            "actual shared source episodes differ from the preregistered episode set"
        )
    random_data = _episode_data(np, pq, random_path, random_map, shared)
    heldout_data = _episode_data(np, pq, heldout_path, heldout_map, shared)
    task_counts: dict[str, int] = {}
    episode_rows = []
    all_actions = []
    for source_episode in shared:
        left = random_data[source_episode]
        right = heldout_data[source_episode]
        for key in ("frame_index", "timestamps", "actions"):
            if not np.array_equal(left[key], right[key]):
                raise PolicyExperimentError(
                    f"paired source episode {source_episode} differs for {key}"
                )
        if left["task"] != right["task"]:
            raise PolicyExperimentError(
                f"paired source episode {source_episode} differs in task text"
            )
        actions = left["actions"]
        all_actions.append(actions)
        task_counts[left["task"]] = task_counts.get(left["task"], 0) + 1
        episode_rows.append(
            {
                "source_episode_index": source_episode,
                "random_local_episode_index": left["local_episode_index"],
                "task_confounded_lineage_holdout_local_episode_index": right[
                    "local_episode_index"
                ],
                "task_index": left["task_index"],
                "task": left["task"],
                "frame_count": int(len(actions)),
                "frame_index_sha256": array_sha256(
                    np, left["frame_index"], "<i8"
                ),
                "timestamp_sha256": array_sha256(
                    np, left["timestamps"], "<f8"
                ),
                "target_action_sha256": array_sha256(np, actions, "<f4"),
            }
        )
    if task_counts != expected["expected_task_counts"]:
        raise PolicyExperimentError(
            f"shared task counts changed: expected {expected['expected_task_counts']}, got {task_counts}"
        )
    action_array = np.concatenate(all_actions, axis=0).astype(np.float64)
    epsilon = float(protocol["evaluation"]["action_scale"]["epsilon"])
    action_std = action_array.std(axis=0, ddof=0)
    action_scale = np.maximum(action_std, epsilon)
    if not np.isfinite(action_scale).all() or np.any(action_scale <= 0):
        raise PolicyExperimentError("evaluation action scale is not finite and positive")
    reference = {
        "profile": REFERENCE_PROFILE,
        "protocol": protocol_descriptor(protocol_path),
        "selection_rule": expected["rule"],
        "source_episode_count": len(shared),
        "source_episode_indices": shared,
        "source_episode_indices_sha256": sha256_payload(shared),
        "task_counts": task_counts,
        "frame_count": int(len(action_array)),
        "action_dimension": int(action_array.shape[1]),
        "normalization": {
            "formula": protocol["evaluation"]["action_scale"]["formula"],
            "epsilon": epsilon,
            "ground_truth_population_std": action_std.tolist(),
            "action_scale": action_scale.tolist(),
        },
        "episodes": episode_rows,
        "paired_target_stream_sha256": sha256_payload(
            [
                {
                    "source_episode_index": row["source_episode_index"],
                    "frame_count": row["frame_count"],
                    "target_action_sha256": row["target_action_sha256"],
                }
                for row in episode_rows
            ]
        ),
        "checks": {
            "source_episode_set_matches_protocol": True,
            "paired_frame_indices_exact": True,
            "paired_timestamps_exact": True,
            "paired_actions_exact": True,
            "task_counts_match_protocol": True,
            "normalization_finite_and_positive": True,
        },
        "pass": True,
    }
    return reference


def validate_reference(
    reference: dict[str, Any],
    protocol: dict[str, Any],
    protocol_path: Path = DEFAULT_PROTOCOL,
) -> list[str]:
    errors = []
    expected = protocol["evaluation"]["episode_selection"]
    if reference.get("profile") != REFERENCE_PROFILE:
        errors.append("unexpected evaluation-reference profile")
    if reference.get("protocol") != protocol_descriptor(protocol_path):
        errors.append("evaluation-reference protocol descriptor is stale")
    if reference.get("source_episode_indices") != expected[
        "expected_source_episode_indices"
    ]:
        errors.append("evaluation-reference source episodes changed")
    if reference.get("source_episode_indices_sha256") != expected[
        "expected_source_episode_indices_sha256"
    ]:
        errors.append("evaluation-reference source episode digest changed")
    if reference.get("task_counts") != expected["expected_task_counts"]:
        errors.append("evaluation-reference task counts changed")
    scales = reference.get("normalization", {}).get("action_scale", [])
    if not scales or any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) <= 0
        for value in scales
    ):
        errors.append("evaluation-reference action scales are invalid")
    if reference.get("pass") is not True:
        errors.append("evaluation-reference does not pass")
    if not all(reference.get("checks", {}).values()):
        errors.append("evaluation-reference contains a failed check")
    return errors


def materialized_input_errors(
    protocol: dict[str, Any],
    reference: dict[str, Any],
) -> list[str]:
    errors = validate_reference(reference, protocol)
    camera_key = protocol["source"]["camera_key"]
    for split in protocol["training"]["split_conditions"]:
        for partition in ("train", "test"):
            path = package_root(protocol, split["id"], partition)
            info_path = path / "meta" / "info.json"
            if not info_path.is_file():
                errors.append(f"missing package info: {relative(info_path)}")
                continue
            info = load_json(info_path)
            feature = info.get("features", {}).get(camera_key)
            if not isinstance(feature, dict) or feature.get("dtype") != "video":
                errors.append(f"{relative(path)} does not expose {camera_key}")
            video_root = path / "videos" / camera_key
            if not video_root.is_dir() or not any(video_root.rglob("*.mp4")):
                errors.append(f"{relative(path)} has no materialized camera video")
    return errors


def environment_payload() -> dict[str, Any]:
    import lerobot
    import torch

    devices = []
    if torch.cuda.is_available():
        for index in range(torch.cuda.device_count()):
            props = torch.cuda.get_device_properties(index)
            devices.append(
                {
                    "index": index,
                    "name": props.name,
                    "total_memory_bytes": int(props.total_memory),
                    "compute_capability": f"{props.major}.{props.minor}",
                }
            )
    return {
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python_version": platform.python_version(),
        "lerobot_version": lerobot.__version__,
        "torch_version": torch.__version__,
        "cuda_available": bool(torch.cuda.is_available()),
        "cuda_devices": devices,
    }


def host_payload(path: Path, environment: dict[str, Any]) -> dict[str, Any]:
    disk = shutil.disk_usage(path)
    return {
        "hostname": socket.gethostname(),
        "uname": " ".join(platform.uname()),
        "machine": platform.machine(),
        "cpu_logical_count": os.cpu_count(),
        "total_ram_bytes": int(
            os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        ),
        "storage_total_bytes": disk.total,
        "storage_free_bytes_at_start": disk.free,
        "gpu_info": ", ".join(
            device["name"] for device in environment["cuda_devices"]
        ),
        "gpu_total_memory_bytes": sum(
            int(device["total_memory_bytes"])
            for device in environment["cuda_devices"]
        ),
    }


ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
LOSS_LINE = re.compile(
    r"\bstep:(?P<step>[0-9.]+[KMB]?)\b.*?\bloss:"
    r"(?P<loss>[-+]?(?:(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)"
    r"(?:[eE][-+]?[0-9]+)?|nan|inf))",
    re.IGNORECASE,
)


def parse_big_number(value: str) -> int:
    suffixes = {"K": 1000, "M": 1000000, "B": 1000000000}
    suffix = value[-1]
    if suffix in suffixes:
        return int(round(float(value[:-1]) * suffixes[suffix]))
    return int(value)


def parse_loss_curve(log_path: Path) -> list[dict[str, Any]]:
    text = ANSI_ESCAPE.sub("", log_path.read_text(encoding="utf-8", errors="replace"))
    rows = []
    for line in text.splitlines():
        match = LOSS_LINE.search(line)
        if not match:
            continue
        loss = float(match.group("loss"))
        if not math.isfinite(loss):
            raise PolicyExperimentError("training log contains a non-finite loss")
        rows.append(
            {
                "step": parse_big_number(match.group("step")),
                "loss": loss,
            }
        )
    return rows


def actual_training_command(job: dict[str, Any], work_root: Path) -> list[str]:
    job_work = work_root / job["job_id"]
    train_root = ROOT / job["train_dataset_root"]
    command = list(job["training_command_template"])
    command[0] = sys.executable
    command = [
        (
            f"--dataset.root={train_root.resolve()}"
            if value.startswith("--dataset.root=")
            else f"--output_dir={(job_work / 'training').resolve()}"
            if value.startswith("--output_dir=")
            else value
        )
        for value in command
    ]
    return command


def concrete_checkpoint(
    protocol: dict[str, Any],
    job: dict[str, Any],
    work_root: Path,
) -> Path:
    return (
        work_root
        / job["job_id"]
        / "training"
        / "checkpoints"
        / f"{protocol['training']['steps']:06d}"
        / "pretrained_model"
    )


def training_report_path(output_dir: Path, job_id: str) -> Path:
    return output_dir / "jobs" / job_id / "training_report.json"


def evaluation_report_path(output_dir: Path, job_id: str) -> Path:
    return output_dir / "jobs" / job_id / "evaluation_report.json"


def report_matches_job(
    report: dict[str, Any],
    profile: str,
    job: dict[str, Any],
    protocol_path: Path,
) -> bool:
    return bool(
        report.get("profile") == profile
        and report.get("status") in {
            "training_complete",
            "evaluation_complete",
        }
        and report.get("protocol", {}).get("sha256") == sha256_file(protocol_path)
        and report.get("job", {}).get("job_definition_sha256")
        == job["job_definition_sha256"]
    )


def run_training_job(
    protocol: dict[str, Any],
    protocol_path: Path,
    job: dict[str, Any],
    output_dir: Path,
    work_root: Path,
    *,
    force: bool,
) -> dict[str, Any]:
    preregistration = protocol_preregistration(protocol_path)
    if not preregistration["committed_before_required_execution"]:
        raise PolicyExperimentError(
            "protocol is not committed before this required execution"
        )
    reference = load_json(output_dir / DEFAULT_REFERENCE.name)
    errors = materialized_input_errors(protocol, reference)
    if errors:
        raise PolicyExperimentError("; ".join(errors))

    report_path = training_report_path(output_dir, job["job_id"])
    if report_path.is_file() and not force:
        existing = load_json(report_path)
        if report_matches_job(existing, TRAIN_REPORT_PROFILE, job, protocol_path):
            checkpoint_path = Path(existing["artifacts"]["final_checkpoint"]["path"])
            if not checkpoint_path.is_absolute():
                checkpoint_path = ROOT / checkpoint_path
            if checkpoint_path.is_dir():
                print(f"{job['job_id']}: training already complete")
                return existing
        raise PolicyExperimentError(
            f"existing training report is incomplete or stale: {relative(report_path)}"
        )

    job_work = work_root / job["job_id"]
    if job_work.exists():
        if not force:
            raise PolicyExperimentError(
                f"job work directory already exists: {relative(job_work)}"
            )
        shutil.rmtree(job_work)
    job_work.mkdir(parents=True)
    log_path = job_work / "training.log"
    command = actual_training_command(job, work_root)
    environment = environment_payload()
    expected_version = protocol["runtime"]["lerobot_version"]
    if environment["lerobot_version"] != expected_version:
        raise PolicyExperimentError(
            f"expected LeRobot {expected_version}, found {environment['lerobot_version']}"
        )
    if not environment["cuda_available"]:
        raise PolicyExperimentError("required training run has no CUDA device")

    started_utc = dt.datetime.now(dt.timezone.utc).isoformat()
    started = time.perf_counter()
    child_before = resource.getrusage(resource.RUSAGE_CHILDREN)
    host = host_payload(job_work, environment)
    with log_path.open("w", encoding="utf-8") as log:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    child_after = resource.getrusage(resource.RUSAGE_CHILDREN)
    wall_time = time.perf_counter() - started
    loss_curve = parse_loss_curve(log_path)
    checkpoint_path = concrete_checkpoint(protocol, job, work_root)
    status = (
        "training_complete"
        if completed.returncode == 0 and checkpoint_path.is_dir()
        else "training_failed"
    )
    artifacts: dict[str, Any] = {
        "training_log": file_descriptor(log_path),
    }
    if checkpoint_path.is_dir():
        artifacts["final_checkpoint"] = tree_descriptor(checkpoint_path)
        artifacts["all_checkpoints"] = tree_descriptor(
            checkpoint_path.parents[1]
        )
    report = {
        "profile": TRAIN_REPORT_PROFILE,
        "status": status,
        "protocol": preregistration,
        "job": job,
        "source_repository_commit": preregistration["execution_source_revision"],
        "command": command,
        "environment": environment,
        "execution": {
            "started_utc": started_utc,
            "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "return_code": completed.returncode,
            "host": host,
            "compute": {
                "wall_time_seconds": wall_time,
                "user_cpu_seconds": (
                    child_after.ru_utime - child_before.ru_utime
                ),
                "system_cpu_seconds": (
                    child_after.ru_stime - child_before.ru_stime
                ),
                "max_rss_bytes": int(child_after.ru_maxrss * 1024),
            },
        },
        "training": {
            "expected_steps": protocol["training"]["steps"],
            "loss_curve": loss_curve,
            "loss_curve_point_count": len(loss_curve),
            "last_logged_step": loss_curve[-1]["step"] if loss_curve else None,
        },
        "artifacts": artifacts,
        "checks": {
            "return_code_zero": completed.returncode == 0,
            "final_checkpoint_exists": checkpoint_path.is_dir(),
            "loss_curve_nonempty": bool(loss_curve),
            "last_logged_step_matches_protocol": bool(loss_curve)
            and loss_curve[-1]["step"] == protocol["training"]["steps"],
            "protocol_committed_before_execution": preregistration[
                "committed_before_required_execution"
            ],
        },
    }
    report["pass"] = all(report["checks"].values())
    write_json(report_path, report)
    if not report["pass"]:
        raise PolicyExperimentError(
            f"{job['job_id']} training failed; inspect {relative(log_path)}"
        )
    return report


def _checkpoint_from_report(report: dict[str, Any]) -> Path:
    value = report.get("artifacts", {}).get("final_checkpoint", {}).get("path")
    if not isinstance(value, str) or not value:
        raise PolicyExperimentError("training report has no final checkpoint path")
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _evaluation_dependencies() -> tuple[Any, ...]:
    try:
        import lerobot
        import numpy as np
        import torch
        from lerobot.configs.policies import PreTrainedConfig
        from lerobot.datasets import LeRobotDataset
        from lerobot.policies.factory import make_policy, make_pre_post_processors
        from torch.utils.data._utils.collate import default_collate
    except ModuleNotFoundError as exc:
        raise PolicyExperimentError(
            "evaluation requires the pinned LeRobot training environment"
        ) from exc
    return (
        lerobot,
        np,
        torch,
        PreTrainedConfig,
        LeRobotDataset,
        make_policy,
        make_pre_post_processors,
        default_collate,
    )


def _dataset_episode_bounds(dataset: Any, local_episode: int) -> tuple[int, int]:
    episodes = dataset.meta.episodes
    raw_start = episodes["dataset_from_index"][local_episode]
    raw_end = episodes["dataset_to_index"][local_episode]
    start = int(raw_start.item() if hasattr(raw_start, "item") else raw_start)
    end = int(raw_end.item() if hasattr(raw_end, "item") else raw_end)
    if end <= start:
        raise PolicyExperimentError(
            f"local episode {local_episode} has invalid dataset bounds"
        )
    return start, end


def _target_digest(np: Any, targets: Any) -> str:
    return array_sha256(np, targets, "<f4")


def evaluate_job(
    protocol: dict[str, Any],
    protocol_path: Path,
    job: dict[str, Any],
    output_dir: Path,
    work_root: Path,
    *,
    force: bool,
) -> dict[str, Any]:
    preregistration = protocol_preregistration(protocol_path)
    if not preregistration["committed_before_required_execution"]:
        raise PolicyExperimentError(
            "protocol is not committed before this required evaluation"
        )
    train_path = training_report_path(output_dir, job["job_id"])
    train_report = load_json(train_path)
    if not report_matches_job(
        train_report,
        TRAIN_REPORT_PROFILE,
        job,
        protocol_path,
    ) or train_report.get("pass") is not True:
        raise PolicyExperimentError(
            f"training report is incomplete for {job['job_id']}"
        )
    report_path = evaluation_report_path(output_dir, job["job_id"])
    raw_path = work_root / job["job_id"] / "evaluation_predictions.npz"
    if report_path.is_file() and not force:
        existing = load_json(report_path)
        if (
            report_matches_job(
                existing,
                EVAL_REPORT_PROFILE,
                job,
                protocol_path,
            )
            and raw_path.is_file()
            and file_descriptor(raw_path)
            == existing.get("artifacts", {}).get("raw_predictions")
        ):
            print(f"{job['job_id']}: evaluation already complete")
            return existing
        raise PolicyExperimentError(
            f"existing evaluation report is incomplete or stale: {relative(report_path)}"
        )

    reference = load_json(output_dir / DEFAULT_REFERENCE.name)
    reference_errors = validate_reference(reference, protocol, protocol_path)
    if reference_errors:
        raise PolicyExperimentError("; ".join(reference_errors))
    reference_by_source = {
        int(row["source_episode_index"]): row
        for row in reference["episodes"]
    }
    split_id = job["split_id"]
    local_field = (
        "random_local_episode_index"
        if split_id == "random_episode"
        else "task_confounded_lineage_holdout_local_episode_index"
    )
    dataset_root = ROOT / job["test_dataset_root"]
    (
        lerobot,
        np,
        torch,
        PreTrainedConfig,
        LeRobotDataset,
        make_policy,
        make_pre_post_processors,
        default_collate,
    ) = _evaluation_dependencies()
    if lerobot.__version__ != protocol["runtime"]["lerobot_version"]:
        raise PolicyExperimentError(
            f"expected LeRobot {protocol['runtime']['lerobot_version']}, found {lerobot.__version__}"
        )
    device = protocol["runtime"]["device"]
    if device == "cuda" and not torch.cuda.is_available():
        raise PolicyExperimentError("required evaluation has no CUDA device")
    dataset = LeRobotDataset(
        (
            "worldepisode/armnetbench_v01_lerobot_so101_"
            f"{job['package_split_name']}_test"
        ),
        root=dataset_root,
    )
    checkpoint_path = _checkpoint_from_report(train_report)
    policy_cfg = PreTrainedConfig.from_pretrained(str(checkpoint_path))
    policy_cfg.pretrained_path = checkpoint_path
    policy_cfg.device = device
    policy = make_policy(policy_cfg, ds_meta=dataset.meta)
    preprocessor, postprocessor = make_pre_post_processors(
        policy_cfg,
        pretrained_path=str(checkpoint_path),
        dataset_meta=dataset.meta,
        preprocessor_overrides={"device_processor": {"device": device}},
    )
    policy.eval()

    started_utc = dt.datetime.now(dt.timezone.utc).isoformat()
    started = time.perf_counter()
    usage_before = resource.getrusage(resource.RUSAGE_SELF)
    predictions = []
    targets = []
    source_indices = []
    local_indices = []
    frame_indices = []
    episode_rows = []
    image_keys = sorted(dataset.meta.camera_keys)
    for source_episode in reference["source_episode_indices"]:
        reference_row = reference_by_source[source_episode]
        local_episode = int(reference_row[local_field])
        start, end = _dataset_episode_bounds(dataset, local_episode)
        policy.reset()
        episode_predictions = []
        episode_targets = []
        episode_started = time.perf_counter()
        for dataset_index in range(start, end):
            sample = dataset[dataset_index]
            target = sample["action"].detach().cpu().to(torch.float32).numpy()
            batch = default_collate([sample])
            batch.pop("action", None)
            for image_key in image_keys:
                if image_key in batch and batch[image_key].dtype == torch.uint8:
                    batch[image_key] = batch[image_key].to(torch.float32) / 255.0
            processed = preprocessor(batch)
            with torch.inference_mode():
                prediction = policy.select_action(processed)
                prediction = postprocessor(prediction)
            prediction_array = (
                prediction.detach().cpu().to(torch.float32).numpy()[0]
            )
            if prediction_array.shape != target.shape:
                raise PolicyExperimentError(
                    f"prediction shape {prediction_array.shape} differs from target {target.shape}"
                )
            episode_predictions.append(prediction_array)
            episode_targets.append(target)
            predictions.append(prediction_array)
            targets.append(target)
            source_indices.append(source_episode)
            local_indices.append(local_episode)
            frame_indices.append(int(sample["frame_index"]))
        episode_prediction_array = np.asarray(
            episode_predictions,
            dtype=np.float32,
        )
        episode_target_array = np.asarray(episode_targets, dtype=np.float32)
        target_digest = _target_digest(np, episode_target_array)
        if target_digest != reference_row["target_action_sha256"]:
            raise PolicyExperimentError(
                f"target action digest changed for source episode {source_episode}"
            )
        episode_rows.append(
            {
                "source_episode_index": source_episode,
                "local_episode_index": local_episode,
                "task": reference_row["task"],
                "frame_count": len(episode_target_array),
                "target_action_sha256": target_digest,
                "prediction_sha256": array_sha256(
                    np,
                    episode_prediction_array,
                    "<f4",
                ),
                "wall_time_seconds": time.perf_counter() - episode_started,
            }
        )

    prediction_array = np.asarray(predictions, dtype=np.float32)
    target_array = np.asarray(targets, dtype=np.float32)
    if not np.isfinite(prediction_array).all() or not np.isfinite(
        target_array
    ).all():
        raise PolicyExperimentError("evaluation produced non-finite values")
    action_scale = np.asarray(
        reference["normalization"]["action_scale"],
        dtype=np.float64,
    )
    error = prediction_array.astype(np.float64) - target_array.astype(np.float64)
    normalized_error = error / action_scale
    per_joint_rmse = np.sqrt(np.mean(np.square(error), axis=0))
    per_joint_nrmse = np.sqrt(np.mean(np.square(normalized_error), axis=0))
    source_index_array = np.asarray(source_indices, dtype=np.int64)
    per_episode = []
    for row in episode_rows:
        source_episode = row["source_episode_index"]
        mask = source_index_array == source_episode
        episode_error = error[mask]
        episode_normalized_error = normalized_error[mask]
        row["rmse"] = float(np.sqrt(np.mean(np.square(episode_error))))
        row["normalized_rmse"] = float(
            np.sqrt(np.mean(np.square(episode_normalized_error)))
        )
        row["per_joint_rmse"] = np.sqrt(
            np.mean(np.square(episode_error), axis=0)
        ).tolist()
        row["per_joint_normalized_rmse"] = np.sqrt(
            np.mean(np.square(episode_normalized_error), axis=0)
        ).tolist()
        per_episode.append(row)
    episode_nrmse = np.asarray(
        [row["normalized_rmse"] for row in per_episode],
        dtype=np.float64,
    )
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        raw_path,
        predictions=prediction_array,
        targets=target_array,
        normalized_errors=normalized_error.astype(np.float32),
        source_episode_index=source_index_array,
        local_episode_index=np.asarray(local_indices, dtype=np.int64),
        frame_index=np.asarray(frame_indices, dtype=np.int64),
        action_scale=action_scale.astype(np.float32),
    )
    usage_after = resource.getrusage(resource.RUSAGE_SELF)
    wall_time = time.perf_counter() - started
    metrics = {
        "frame_count": int(len(target_array)),
        "episode_count": len(per_episode),
        "frame_rmse": float(np.sqrt(np.mean(np.square(error)))),
        "frame_normalized_rmse": float(
            np.sqrt(np.mean(np.square(normalized_error)))
        ),
        "episode_normalized_rmse_mean": float(episode_nrmse.mean()),
        "episode_normalized_rmse_median": float(np.median(episode_nrmse)),
        "per_joint_rmse": per_joint_rmse.tolist(),
        "per_joint_normalized_rmse": per_joint_nrmse.tolist(),
        "per_episode": per_episode,
    }
    environment = environment_payload()
    report = {
        "profile": EVAL_REPORT_PROFILE,
        "status": "evaluation_complete",
        "protocol": preregistration,
        "job": job,
        "evaluation_reference": file_descriptor(
            output_dir / DEFAULT_REFERENCE.name
        ),
        "checkpoint": train_report["artifacts"]["final_checkpoint"],
        "environment": environment,
        "execution": {
            "started_utc": started_utc,
            "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "host": host_payload(raw_path.parent, environment),
            "compute": {
                "wall_time_seconds": wall_time,
                "user_cpu_seconds": usage_after.ru_utime - usage_before.ru_utime,
                "system_cpu_seconds": (
                    usage_after.ru_stime - usage_before.ru_stime
                ),
                "max_rss_bytes": int(usage_after.ru_maxrss * 1024),
            },
        },
        "mode": protocol["evaluation"]["mode"],
        "native_policy_queue_preserved": True,
        "policy_reset_at_episode_boundary": True,
        "normalization": reference["normalization"],
        "metrics": metrics,
        "artifacts": {
            "raw_predictions": file_descriptor(raw_path),
            "training_report": file_descriptor(train_path),
        },
        "checks": {
            "all_predictions_finite": True,
            "all_targets_finite": True,
            "episode_set_matches_reference": [
                row["source_episode_index"] for row in per_episode
            ]
            == reference["source_episode_indices"],
            "episode_count_matches_reference": len(per_episode)
            == reference["source_episode_count"],
            "frame_count_matches_reference": len(target_array)
            == reference["frame_count"],
            "target_digests_match_reference": True,
            "protocol_committed_before_execution": preregistration[
                "committed_before_required_execution"
            ],
        },
        "claim_boundary": protocol["claim_boundary"]["statement"],
    }
    report["pass"] = all(report["checks"].values())
    write_json(report_path, report)
    if not report["pass"]:
        raise PolicyExperimentError(
            f"{job['job_id']} evaluation did not pass"
        )
    return report


def derived_seed(base_seed: int, label: str) -> int:
    digest = hashlib.sha256(f"{base_seed}:{label}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def percentile_interval(
    np: Any,
    samples: Any,
    confidence_level: float,
) -> tuple[float, float]:
    alpha = 1.0 - confidence_level
    return (
        float(np.quantile(samples, alpha / 2.0)),
        float(np.quantile(samples, 1.0 - alpha / 2.0)),
    )


def crossed_bootstrap(
    matrix: Any,
    *,
    resamples: int,
    confidence_level: float,
    seed: int,
) -> dict[str, Any]:
    import numpy as np

    matrix = np.asarray(matrix, dtype=np.float64)
    if matrix.ndim != 2:
        raise PolicyExperimentError("bootstrap matrix must be seed by episode")
    rng = np.random.default_rng(seed)
    samples = np.empty(resamples, dtype=np.float64)
    for index in range(resamples):
        seed_indices = rng.integers(0, matrix.shape[0], size=matrix.shape[0])
        episode_indices = rng.integers(
            0,
            matrix.shape[1],
            size=matrix.shape[1],
        )
        samples[index] = matrix[np.ix_(seed_indices, episode_indices)].mean()
    low, high = percentile_interval(np, samples, confidence_level)
    per_seed = matrix.mean(axis=1)
    return {
        "estimate": float(matrix.mean()),
        "ci_low": low,
        "ci_high": high,
        "confidence_level": confidence_level,
        "resamples": resamples,
        "bootstrap_seed": seed,
        "seed_count": int(matrix.shape[0]),
        "episode_count": int(matrix.shape[1]),
        "per_seed_estimates": per_seed.tolist(),
        "seed_sample_std": (
            float(per_seed.std(ddof=1)) if len(per_seed) > 1 else 0.0
        ),
    }


def paired_effect_bootstrap(
    heldout: Any,
    random: Any,
    *,
    resamples: int,
    confidence_level: float,
    seed: int,
) -> dict[str, Any]:
    import numpy as np

    heldout = np.asarray(heldout, dtype=np.float64)
    random = np.asarray(random, dtype=np.float64)
    if heldout.shape != random.shape or heldout.ndim != 2:
        raise PolicyExperimentError("paired effect matrices are not aligned")
    difference = heldout - random
    result = crossed_bootstrap(
        difference,
        resamples=resamples,
        confidence_level=confidence_level,
        seed=seed,
    )
    result["direction"] = (
        "task_confounded_lineage_holdout_minus_random_episode"
    )
    result["paired_by"] = ["training_seed", "source_episode"]
    return result


def _validated_job_reports(
    protocol: dict[str, Any],
    protocol_path: Path,
    jobs_payload: dict[str, Any],
    output_dir: Path,
    *,
    require_payloads: bool,
) -> tuple[dict[str, Any], list[str]]:
    reports: dict[str, Any] = {}
    errors = []
    expected_episodes = protocol["evaluation"]["episode_selection"][
        "expected_source_episode_indices"
    ]
    for job in jobs_payload["jobs"]:
        train_path = training_report_path(output_dir, job["job_id"])
        eval_path = evaluation_report_path(output_dir, job["job_id"])
        if not train_path.is_file():
            errors.append(f"missing training report for {job['job_id']}")
            continue
        if not eval_path.is_file():
            errors.append(f"missing evaluation report for {job['job_id']}")
            continue
        train_report = load_json(train_path)
        eval_report = load_json(eval_path)
        if not report_matches_job(
            train_report,
            TRAIN_REPORT_PROFILE,
            job,
            protocol_path,
        ):
            errors.append(f"stale training report for {job['job_id']}")
        if not report_matches_job(
            eval_report,
            EVAL_REPORT_PROFILE,
            job,
            protocol_path,
        ):
            errors.append(f"stale evaluation report for {job['job_id']}")
        if train_report.get("pass") is not True:
            errors.append(f"training report does not pass for {job['job_id']}")
        if eval_report.get("pass") is not True:
            errors.append(f"evaluation report does not pass for {job['job_id']}")
        episode_rows = eval_report.get("metrics", {}).get("per_episode", [])
        if [
            row.get("source_episode_index") for row in episode_rows
        ] != expected_episodes:
            errors.append(f"evaluation episode set changed for {job['job_id']}")
        values = [row.get("normalized_rmse") for row in episode_rows]
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            for value in values
        ):
            errors.append(f"non-finite evaluation metric for {job['job_id']}")
        if require_payloads:
            for report, artifact_name in (
                (train_report, "training_log"),
                (eval_report, "raw_predictions"),
            ):
                descriptor = report.get("artifacts", {}).get(artifact_name, {})
                path = Path(descriptor.get("path", ""))
                if not path.is_absolute():
                    path = ROOT / path
                if not path.is_file():
                    errors.append(
                        f"missing {artifact_name} payload for {job['job_id']}"
                    )
                elif file_descriptor(path) != descriptor:
                    errors.append(
                        f"stale {artifact_name} payload for {job['job_id']}"
                    )
            checkpoint = _checkpoint_from_report(train_report)
            if not checkpoint.is_dir():
                errors.append(f"missing checkpoint for {job['job_id']}")
            else:
                actual = tree_descriptor(checkpoint)
                if actual != train_report["artifacts"]["final_checkpoint"]:
                    errors.append(f"stale checkpoint for {job['job_id']}")
        reports[job["job_id"]] = {
            "training": train_report,
            "evaluation": eval_report,
        }
    return reports, errors


def analysis_from_reports(
    protocol: dict[str, Any],
    jobs_payload: dict[str, Any],
    reports: dict[str, Any],
) -> dict[str, Any]:
    import numpy as np

    seeds = protocol["training"]["seeds"]
    source_episodes = protocol["evaluation"]["episode_selection"][
        "expected_source_episode_indices"
    ]
    analysis_config = protocol["analysis"]
    output: dict[str, Any] = {"policies": {}}
    for policy in protocol["training"]["policies"]:
        matrices = {}
        split_results = {}
        for split in protocol["training"]["split_conditions"]:
            rows = []
            for seed in seeds:
                job_id = f"{policy}__{split['id']}__seed{seed:02d}"
                report = reports[job_id]["evaluation"]
                by_episode = {
                    int(row["source_episode_index"]): float(
                        row["normalized_rmse"]
                    )
                    for row in report["metrics"]["per_episode"]
                }
                rows.append([by_episode[index] for index in source_episodes])
            matrix = np.asarray(rows, dtype=np.float64)
            matrices[split["id"]] = matrix
            split_results[split["id"]] = crossed_bootstrap(
                matrix,
                resamples=int(analysis_config["bootstrap_resamples"]),
                confidence_level=float(analysis_config["confidence_level"]),
                seed=derived_seed(
                    int(analysis_config["bootstrap_seed"]),
                    f"{policy}:{split['id']}",
                ),
            )
        effect = paired_effect_bootstrap(
            matrices["task_confounded_lineage_holdout"],
            matrices["random_episode"],
            resamples=int(analysis_config["bootstrap_resamples"]),
            confidence_level=float(analysis_config["confidence_level"]),
            seed=derived_seed(
                int(analysis_config["bootstrap_seed"]),
                f"{policy}:paired-effect",
            ),
        )
        output["policies"][policy] = {
            "splits": split_results,
            "paired_effect": effect,
        }
    output["metric"] = "episode_normalized_rmse_mean"
    output["normalization_reference"] = (
        "common ground-truth action scale over all paired evaluation frames"
    )
    return output


def aggregate_report(
    protocol: dict[str, Any],
    protocol_path: Path,
    jobs_payload: dict[str, Any],
    reference_path: Path,
    output_dir: Path,
    *,
    require_payloads: bool,
) -> dict[str, Any]:
    reports, errors = _validated_job_reports(
        protocol,
        protocol_path,
        jobs_payload,
        output_dir,
        require_payloads=require_payloads,
    )
    complete = len(reports) == jobs_payload["job_count"] and not errors
    analysis = (
        analysis_from_reports(protocol, jobs_payload, reports)
        if complete
        else {}
    )
    preregistration = protocol_preregistration(protocol_path)
    checks = {
        "protocol_committed_before_required_execution": preregistration[
            "committed_before_required_execution"
        ],
        "required_job_count_complete": len(reports)
        == protocol["acceptance"]["required_job_count"],
        "all_job_reports_valid": not errors,
        "evaluation_reference_valid": not validate_reference(
            load_json(reference_path),
            protocol,
            protocol_path,
        ),
        "offline_analysis_complete": bool(analysis),
    }
    report = {
        "profile": REPORT_PROFILE,
        "status": (
            "offline_policy_experiment_complete"
            if all(checks.values())
            else "offline_policy_experiment_incomplete"
        ),
        "pass": all(checks.values()),
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "repository_commit": git_output("rev-parse", "HEAD"),
        "protocol": preregistration,
        "jobs": file_descriptor(DEFAULT_JOBS),
        "evaluation_reference": file_descriptor(reference_path),
        "completed_job_count": len(reports),
        "required_job_count": jobs_payload["job_count"],
        "analysis": analysis,
        "acceptance": {
            "checks": checks,
            "errors": errors,
            "pass": all(checks.values()),
        },
        "compute": {
            "training_wall_time_seconds": sum(
                item["training"]["execution"]["compute"]["wall_time_seconds"]
                for item in reports.values()
            ),
            "evaluation_wall_time_seconds": sum(
                item["evaluation"]["execution"]["compute"]["wall_time_seconds"]
                for item in reports.values()
            ),
        },
        "claim_boundary": protocol["claim_boundary"],
    }
    return report


def render_readme(
    protocol: dict[str, Any],
    jobs_payload: dict[str, Any],
    reference: dict[str, Any] | None,
    report: dict[str, Any] | None = None,
) -> str:
    status = (
        report["status"]
        if report is not None
        else "preregistered; required training not yet executed"
    )
    episode_count = (
        reference["source_episode_count"]
        if reference is not None
        else protocol["evaluation"]["episode_selection"][
            "expected_episode_count"
        ]
    )
    text = f"""# LeRobot ACT/Diffusion Offline Policy Experiment

Status: {status}

`{protocol["protocol_id"]}` fixes {jobs_payload["job_count"]} required jobs: ACT and
Diffusion Policy, the random-episode and task-confounded lineage-holdout packages,
and five matched seeds. Evaluation uses the exact {episode_count} source episodes
shared by both test packages.

The primary metric is mean per-episode action nRMSE. Every checkpoint is evaluated
sequentially with teacher observations while preserving the policy's native action
queue and resetting it only at episode boundaries. There is no success threshold.

## Required Runtime

```bash
uv run --isolated --python {protocol["runtime"]["python"]} \\
  --with '{protocol["runtime"]["lerobot_requirement"]}' \\
  --with pyarrow --with numpy --with huggingface-hub \\
  python tools/lerobot_policy_video_materialization.py --materialize --download

uv run --isolated --python {protocol["runtime"]["python"]} \\
  --with '{protocol["runtime"]["lerobot_requirement"]}' \\
  --with pyarrow --with numpy --with huggingface-hub \\
  bash docs/experiments/lerobot_policy_full_training/run_jobs.sh
```

## Claim Boundary

{protocol["claim_boundary"]["statement"]}
"""
    if report and report.get("pass"):
        text += "\n## Generated Results\n\n"
        for policy, values in report["analysis"]["policies"].items():
            random = values["splits"]["random_episode"]
            heldout = values["splits"]["task_confounded_lineage_holdout"]
            effect = values["paired_effect"]
            text += (
                f"- `{policy}`: random nRMSE {random['estimate']:.4f} "
                f"[{random['ci_low']:.4f}, {random['ci_high']:.4f}]; "
                f"task-confounded holdout {heldout['estimate']:.4f} "
                f"[{heldout['ci_low']:.4f}, {heldout['ci_high']:.4f}]; "
                f"paired increase {effect['estimate']:.4f} "
                f"[{effect['ci_low']:.4f}, {effect['ci_high']:.4f}].\n"
            )
    return text


def write_preregistered_artifacts(
    protocol_path: Path,
    jobs_path: Path,
    reference_path: Path,
    output_dir: Path,
    *,
    write_reference: bool,
) -> None:
    protocol = load_json(protocol_path)
    validate_protocol(protocol)
    jobs_payload = make_jobs_payload(protocol, protocol_path)
    write_json(jobs_path, jobs_payload)
    run_path = output_dir / "run_jobs.sh"
    write_text(run_path, render_run_script(jobs_payload))
    run_path.chmod(0o755)
    reference = None
    if write_reference:
        reference = build_evaluation_reference(protocol, protocol_path)
        write_json(reference_path, reference)
    elif reference_path.is_file():
        reference = load_json(reference_path)
    write_text(
        output_dir / "README.md",
        render_readme(protocol, jobs_payload, reference),
    )


def check_committed(
    protocol_path: Path,
    jobs_path: Path,
    reference_path: Path,
    report_path: Path,
    output_dir: Path,
    *,
    required: bool,
) -> list[str]:
    errors = []
    try:
        protocol = load_json(protocol_path)
        validate_protocol(protocol)
        expected_jobs = make_jobs_payload(protocol, protocol_path)
        actual_jobs = load_json(jobs_path)
        if actual_jobs != expected_jobs:
            errors.append("committed jobs file is stale")
        reference = load_json(reference_path)
        errors.extend(validate_reference(reference, protocol, protocol_path))
        run_path = output_dir / "run_jobs.sh"
        if not run_path.is_file() or run_path.read_text(
            encoding="utf-8"
        ) != render_run_script(expected_jobs):
            errors.append("committed run script is stale")
        if not report_path.is_file():
            if required:
                errors.append("required aggregate policy report is missing")
            return errors
        report = load_json(report_path)
        if report.get("profile") != REPORT_PROFILE:
            errors.append("unexpected aggregate policy report profile")
            return errors
        expected = aggregate_report(
            protocol,
            protocol_path,
            expected_jobs,
            reference_path,
            output_dir,
            require_payloads=False,
        )
        for key in (
            "status",
            "pass",
            "completed_job_count",
            "required_job_count",
            "analysis",
            "acceptance",
            "compute",
            "claim_boundary",
        ):
            if report.get(key) != expected.get(key):
                errors.append(f"aggregate policy report has stale {key}")
        if required and report.get("pass") is not True:
            errors.append("required aggregate policy report does not pass")
    except PolicyExperimentError as exc:
        errors.append(str(exc))
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--jobs", type=Path, default=DEFAULT_JOBS)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--work-root", type=Path, default=DEFAULT_WORK_ROOT)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--write-jobs", action="store_true")
    actions.add_argument("--write-reference", action="store_true")
    actions.add_argument("--check-inputs", action="store_true")
    actions.add_argument("--run-job")
    actions.add_argument("--evaluate-job")
    actions.add_argument("--aggregate", action="store_true")
    actions.add_argument("--check", action="store_true")
    parser.add_argument("--required", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        protocol = load_json(args.protocol)
        validate_protocol(protocol)
        if args.write_jobs or args.write_reference:
            write_preregistered_artifacts(
                args.protocol,
                args.jobs,
                args.reference,
                args.output_dir,
                write_reference=args.write_reference,
            )
            print(
                json.dumps(
                    {
                        "status": "preregistered_artifacts_written",
                        "jobs": len(make_jobs_payload(protocol, args.protocol)["jobs"]),
                        "reference_written": args.write_reference,
                    },
                    indent=2,
                )
            )
            return 0

        jobs_payload = load_json(args.jobs)
        expected_jobs = make_jobs_payload(protocol, args.protocol)
        if jobs_payload != expected_jobs:
            raise PolicyExperimentError("jobs file is stale; regenerate it")
        jobs = jobs_by_id(jobs_payload)
        if args.check_inputs:
            reference = load_json(args.reference)
            errors = materialized_input_errors(protocol, reference)
            print(json.dumps({"pass": not errors, "errors": errors}, indent=2))
            return 1 if errors else 0
        if args.run_job:
            if args.run_job not in jobs:
                raise PolicyExperimentError(f"unknown job id: {args.run_job}")
            report = run_training_job(
                protocol,
                args.protocol,
                jobs[args.run_job],
                args.output_dir,
                args.work_root,
                force=args.force,
            )
            print(
                json.dumps(
                    {
                        "job_id": args.run_job,
                        "status": report["status"],
                        "pass": report["pass"],
                    },
                    indent=2,
                )
            )
            return 0
        if args.evaluate_job:
            if args.evaluate_job not in jobs:
                raise PolicyExperimentError(
                    f"unknown job id: {args.evaluate_job}"
                )
            report = evaluate_job(
                protocol,
                args.protocol,
                jobs[args.evaluate_job],
                args.output_dir,
                args.work_root,
                force=args.force,
            )
            print(
                json.dumps(
                    {
                        "job_id": args.evaluate_job,
                        "status": report["status"],
                        "pass": report["pass"],
                    },
                    indent=2,
                )
            )
            return 0
        if args.aggregate:
            report = aggregate_report(
                protocol,
                args.protocol,
                jobs_payload,
                args.reference,
                args.output_dir,
                require_payloads=True,
            )
            write_json(args.report, report)
            write_text(
                args.output_dir / "README.md",
                render_readme(
                    protocol,
                    jobs_payload,
                    load_json(args.reference),
                    report,
                ),
            )
            print(
                json.dumps(
                    {
                        "status": report["status"],
                        "pass": report["pass"],
                        "completed_job_count": report["completed_job_count"],
                    },
                    indent=2,
                )
            )
            return 0 if report["pass"] else 1
        if args.check:
            errors = check_committed(
                args.protocol,
                args.jobs,
                args.reference,
                args.report,
                args.output_dir,
                required=args.required,
            )
            print(json.dumps({"valid": not errors, "errors": errors}, indent=2))
            return 1 if errors else 0
    except (PolicyExperimentError, OSError, ValueError) as exc:
        print(f"policy experiment error: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
