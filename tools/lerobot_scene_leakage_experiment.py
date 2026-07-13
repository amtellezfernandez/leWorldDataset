#!/usr/bin/env python3
"""Expose scene-lineage leakage in a public LeRobot v3 benchmark.

The experiment uses ArmnetBench's native LeRobot v3 release, derives WorldEpisode-style
world_lineage hashes for task-scene/camera-layout groups, compares a random episode split against a
scene-disjoint split, and trains the same lightweight state-action BC policy on both splits.

The committed artifact is intentionally an offline BC benchmark: it measures action imitation on
real LeRobot tensors. It does not claim physical rollout success for the newly trained policy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import requests


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPO_ID = "armnet/armnetbench_v01_lerobot_so101"
DEFAULT_REVISION = "2e5e89aee0e7f081078d9d6ab3b279fc4b83ea84"
DEFAULT_CACHE_DIR = ROOT / ".cache" / "worldepisode" / "lerobot_scene_leakage"
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "experiments" / "lerobot_scene_leakage"
SCENE_HOLDOUT_TASK_INDICES = {3, 4}
RANDOM_SEED = 17
BC_SEED = 0
SUCCESS_NRMSE_THRESHOLD = 0.25


class LeakageExperimentUnavailable(RuntimeError):
    """Raised when optional dependencies or network access are missing."""


@dataclass
class EpisodeRecord:
    episode_index: int
    task_index: int
    task: str
    policy_type: str
    success: int
    success_class: str
    length: int
    data_chunk_index: int
    data_file_index: int
    world_lineage: str


def require_pyarrow() -> Any:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise LeakageExperimentUnavailable(
            "pyarrow is required. Install experiment dependencies with "
            "`python3 -m pip install -r requirements-experiments.txt` or run through "
            "`uv run --with-requirements requirements-experiments.txt`."
        ) from exc
    return pq


def require_torch() -> Any:
    try:
        import torch
    except ImportError as exc:
        raise LeakageExperimentUnavailable(
            "torch is required for the BC leakage experiment. Install experiment dependencies with "
            "`python3 -m pip install -r requirements-experiments.txt` or run through "
            "`uv run --with-requirements requirements-experiments.txt`."
        ) from exc
    return torch


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


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


def hf_uri(repo_id: str, revision: str, remote_path: str) -> str:
    return f"hf://{repo_id}@{revision}/{remote_path}"


def hf_resolve_url(repo_id: str, revision: str, remote_path: str) -> str:
    return f"https://huggingface.co/datasets/{repo_id}/resolve/{revision}/{remote_path}"


def download_file(repo_id: str, revision: str, remote_path: str, cache_root: Path) -> dict[str, Any]:
    local_path = cache_root / remote_path
    local_path.parent.mkdir(parents=True, exist_ok=True)
    if not local_path.exists():
        try:
            response = requests.get(hf_resolve_url(repo_id, revision, remote_path), timeout=120)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise LeakageExperimentUnavailable(f"could not download {remote_path}: {exc}") from exc
        local_path.write_bytes(response.content)
    return {
        "uri": hf_uri(repo_id, revision, remote_path),
        "local_path": str(local_path),
        "bytes": local_path.stat().st_size,
        "sha256": sha256_file(local_path),
    }


def portable_file_descriptors(files: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        path: {
            "uri": descriptor["uri"],
            "bytes": descriptor["bytes"],
            "sha256": descriptor["sha256"],
        }
        for path, descriptor in files.items()
    }


def lineage_hash(payload: dict[str, Any]) -> str:
    return "sha256:" + sha256_bytes(canonical_json_bytes(payload))


def video_features(info: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        key: {
            "shape": feature.get("shape"),
            "info": feature.get("info", {}),
        }
        for key, feature in sorted(info.get("features", {}).items())
        if isinstance(feature, dict) and feature.get("dtype") == "video"
    }


def build_lineage_payload(
    repo_id: str,
    revision: str,
    info: dict[str, Any],
    task_index: int,
    task: str,
) -> dict[str, Any]:
    return {
        "profile": "worldepisode-world-lineage-0.1",
        "scope": "task_scene_camera_layout",
        "source_repo_id": repo_id,
        "source_revision": revision,
        "robot_type": info.get("robot_type"),
        "task_index": task_index,
        "task": task,
        "camera_features": video_features(info),
    }


def load_benchmark_metadata(
    repo_id: str,
    revision: str,
    cache_dir: Path,
) -> tuple[dict[str, Any], dict[int, str], list[EpisodeRecord], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    pq = require_pyarrow()
    cache_root = cache_dir / repo_id.replace("/", "__") / revision
    source_files = {
        remote_path: download_file(repo_id, revision, remote_path, cache_root)
        for remote_path in (
            "meta/info.json",
            "meta/tasks.parquet",
            "meta/episodes/chunk-000/file-000.parquet",
        )
    }
    info = load_json(Path(source_files["meta/info.json"]["local_path"]))
    tasks_table = pq.read_table(source_files["meta/tasks.parquet"]["local_path"]).to_pydict()
    task_by_index = {
        int(task_index): task
        for task_index, task in zip(tasks_table["task_index"], tasks_table["task"])
    }
    task_index_by_text = {task: index for index, task in task_by_index.items()}
    episodes_table = pq.read_table(source_files["meta/episodes/chunk-000/file-000.parquet"]["local_path"]).to_pydict()

    lineage_payloads: dict[str, dict[str, Any]] = {}
    lineage_by_task: dict[int, str] = {}
    records: list[EpisodeRecord] = []
    row_count = len(episodes_table["episode_index"])
    for index in range(row_count):
        task = episodes_table["tasks"][index][0]
        task_index = int(task_index_by_text[task])
        payload = build_lineage_payload(repo_id, revision, info, task_index, task)
        world_lineage = lineage_hash(payload)
        lineage_payloads[world_lineage] = payload
        lineage_by_task[task_index] = world_lineage
        records.append(
            EpisodeRecord(
                episode_index=int(episodes_table["episode_index"][index]),
                task_index=task_index,
                task=task,
                policy_type=episodes_table["policy_type"][index],
                success=int(episodes_table["success"][index]),
                success_class=episodes_table["success_class"][index],
                length=int(episodes_table["length"][index]),
                data_chunk_index=int(episodes_table["data/chunk_index"][index]),
                data_file_index=int(episodes_table["data/file_index"][index]),
                world_lineage=world_lineage,
            )
        )
    return info, task_by_index, records, lineage_payloads, source_files


def download_required_data_files(
    repo_id: str,
    revision: str,
    cache_dir: Path,
    records: list[EpisodeRecord],
) -> dict[str, dict[str, Any]]:
    cache_root = cache_dir / repo_id.replace("/", "__") / revision
    data_paths = sorted(
        {
            f"data/chunk-{record.data_chunk_index:03d}/file-{record.data_file_index:03d}.parquet"
            for record in records
        }
    )
    return {
        remote_path: download_file(repo_id, revision, remote_path, cache_root)
        for remote_path in data_paths
    }


def make_splits(records: list[EpisodeRecord]) -> dict[str, dict[str, Any]]:
    teleop = [record for record in records if record.policy_type == "teleoperated"]
    episode_ids = [record.episode_index for record in teleop]
    rng = random.Random(RANDOM_SEED)
    random_test = set(rng.sample(episode_ids, int(round(len(episode_ids) * 0.2))))
    random_train = set(episode_ids) - random_test

    scene_test = {
        record.episode_index
        for record in teleop
        if record.task_index in SCENE_HOLDOUT_TASK_INDICES
    }
    scene_train = set(episode_ids) - scene_test

    by_episode = {record.episode_index: record for record in teleop}

    def split_summary(name: str, train: set[int], test: set[int]) -> dict[str, Any]:
        train_lineages = {by_episode[episode_id].world_lineage for episode_id in train}
        test_lineages = {by_episode[episode_id].world_lineage for episode_id in test}
        leaked_test = [
            episode_id
            for episode_id in sorted(test)
            if by_episode[episode_id].world_lineage in train_lineages
        ]
        return {
            "name": name,
            "train_episodes": sorted(train),
            "test_episodes": sorted(test),
            "train_count": len(train),
            "test_count": len(test),
            "train_world_lineage_count": len(train_lineages),
            "test_world_lineage_count": len(test_lineages),
            "test_lineages_seen_in_train": sorted(test_lineages & train_lineages),
            "test_leaked_episode_count": len(leaked_test),
            "leakage_rate": len(leaked_test) / len(test) if test else 0.0,
            "heldout_task_indices": sorted(
                {
                    by_episode[episode_id].task_index
                    for episode_id in test
                    if by_episode[episode_id].world_lineage not in train_lineages
                }
            ),
        }

    return {
        "random_episode": split_summary("random_episode", random_train, random_test),
        "scene_disjoint": split_summary("scene_disjoint", scene_train, scene_test),
    }


def load_bc_tensors(
    data_files: dict[str, dict[str, Any]],
    records: list[EpisodeRecord],
    task_count: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    pq = require_pyarrow()
    teleop_records = {record.episode_index: record for record in records if record.policy_type == "teleoperated"}
    selected = set(teleop_records)
    features: list[list[float]] = []
    actions: list[list[float]] = []
    episode_ids: list[int] = []
    for descriptor in sorted(data_files.values(), key=lambda item: item["uri"]):
        table = pq.read_table(
            descriptor["local_path"],
            columns=[
                "observation.state",
                "action",
                "timestamp",
                "frame_index",
                "episode_index",
                "task_index",
            ],
        ).to_pydict()
        rows = zip(
            table["observation.state"],
            table["action"],
            table["timestamp"],
            table["frame_index"],
            table["episode_index"],
            table["task_index"],
        )
        for state, action, timestamp, frame_index, episode_index, task_index in rows:
            episode_index = int(episode_index)
            if episode_index not in selected:
                continue
            record = teleop_records[episode_index]
            one_hot = [0.0] * task_count
            one_hot[int(task_index)] = 1.0
            phase = float(frame_index) / max(record.length - 1, 1)
            features.append([*map(float, state), phase, float(timestamp), *one_hot])
            actions.append([*map(float, action)])
            episode_ids.append(episode_index)
    return (
        np.asarray(features, dtype=np.float32),
        np.asarray(actions, dtype=np.float32),
        np.asarray(episode_ids, dtype=np.int64),
    )


def train_torch_mlp_bc(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    epochs: int,
) -> tuple[np.ndarray, dict[str, Any]]:
    torch = require_torch()
    torch.manual_seed(BC_SEED)
    np.random.seed(BC_SEED)

    x_mean = x_train.mean(axis=0)
    x_std = x_train.std(axis=0)
    x_std[x_std < 1e-6] = 1.0
    y_mean = y_train.mean(axis=0)
    y_std = y_train.std(axis=0)
    y_std[y_std < 1e-6] = 1.0

    x_train_n = (x_train - x_mean) / x_std
    y_train_n = (y_train - y_mean) / y_std
    x_test_n = (x_test - x_mean) / x_std

    model = torch.nn.Sequential(
        torch.nn.Linear(x_train.shape[1], 64),
        torch.nn.ReLU(),
        torch.nn.Linear(64, 64),
        torch.nn.ReLU(),
        torch.nn.Linear(64, y_train.shape[1]),
    )
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    dataset = torch.utils.data.TensorDataset(torch.tensor(x_train_n), torch.tensor(y_train_n))
    loader = torch.utils.data.DataLoader(
        dataset,
        batch_size=2048,
        shuffle=True,
        generator=torch.Generator().manual_seed(BC_SEED),
    )

    epoch_losses = []
    model.train()
    for _epoch in range(epochs):
        losses = []
        for x_batch, y_batch in loader:
            optimizer.zero_grad()
            loss = torch.nn.functional.mse_loss(model(x_batch), y_batch)
            loss.backward()
            optimizer.step()
            losses.append(float(loss.detach().cpu().item()))
        epoch_losses.append(float(np.mean(losses)))

    model.eval()
    with torch.no_grad():
        pred_n = model(torch.tensor(x_test_n)).cpu().numpy()
    pred = pred_n * y_std + y_mean
    return pred.astype(np.float32), {
        "policy_family": "torch_mlp_bc_state_action",
        "epochs": epochs,
        "batch_size": 2048,
        "hidden_units": [64, 64],
        "optimizer": "AdamW(lr=1e-3, weight_decay=1e-4)",
        "seed": BC_SEED,
        "final_train_loss": epoch_losses[-1],
        "target_std": y_std.tolist(),
    }


def evaluate_bc_split(
    split: dict[str, Any],
    features: np.ndarray,
    actions: np.ndarray,
    episode_ids: np.ndarray,
    epochs: int,
) -> dict[str, Any]:
    train_ids = set(split["train_episodes"])
    test_ids = set(split["test_episodes"])
    train_mask = np.isin(episode_ids, list(train_ids))
    test_mask = np.isin(episode_ids, list(test_ids))
    x_train = features[train_mask]
    y_train = actions[train_mask]
    x_test = features[test_mask]
    y_test = actions[test_mask]
    test_episode_ids = episode_ids[test_mask]

    predictions, policy_info = train_torch_mlp_bc(x_train, y_train, x_test, epochs)
    target_std = np.asarray(policy_info["target_std"], dtype=np.float32)
    normalized_sq_error = ((predictions - y_test) / target_std) ** 2
    episode_errors = []
    for episode_id in sorted(set(test_episode_ids.tolist())):
        mask = test_episode_ids == episode_id
        episode_errors.append(
            {
                "episode_index": int(episode_id),
                "normalized_rmse": float(np.sqrt(normalized_sq_error[mask].mean())),
            }
        )
    episode_values = np.asarray([row["normalized_rmse"] for row in episode_errors], dtype=np.float32)
    success_count = int(np.sum(episode_values <= SUCCESS_NRMSE_THRESHOLD))
    return {
        "policy": policy_info,
        "train_frames": int(len(x_train)),
        "test_frames": int(len(x_test)),
        "frame_normalized_rmse": float(np.sqrt(normalized_sq_error.mean())),
        "frame_rmse": float(np.sqrt(((predictions - y_test) ** 2).mean())),
        "episode_normalized_rmse_mean": float(episode_values.mean()),
        "episode_normalized_rmse_median": float(np.median(episode_values)),
        "episode_normalized_rmse_p75": float(np.percentile(episode_values, 75)),
        "offline_bc_success_threshold": SUCCESS_NRMSE_THRESHOLD,
        "offline_bc_success_count": success_count,
        "offline_bc_success_rate": success_count / len(episode_values) if len(episode_values) else 0.0,
        "episode_errors": episode_errors,
    }


def lineage_records(
    records: list[EpisodeRecord],
    lineage_payloads: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    episode_counts: dict[str, int] = {}
    teleop_counts: dict[str, int] = {}
    for record in records:
        episode_counts[record.world_lineage] = episode_counts.get(record.world_lineage, 0) + 1
        if record.policy_type == "teleoperated":
            teleop_counts[record.world_lineage] = teleop_counts.get(record.world_lineage, 0) + 1
    return [
        {
            "world_lineage": world_lineage,
            "episode_count": episode_counts.get(world_lineage, 0),
            "teleoperated_episode_count": teleop_counts.get(world_lineage, 0),
            **payload,
        }
        for world_lineage, payload in sorted(
            lineage_payloads.items(),
            key=lambda item: item[1]["task_index"],
        )
    ]


def run_scene_leakage_experiment(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    repo_id: str = DEFAULT_REPO_ID,
    revision: str = DEFAULT_REVISION,
    epochs: int = 12,
) -> dict[str, Any]:
    require_pyarrow()
    require_torch()
    info, task_by_index, records, lineage_payloads, metadata_files = load_benchmark_metadata(
        repo_id,
        revision,
        cache_dir,
    )
    teleop_records = [record for record in records if record.policy_type == "teleoperated"]
    data_files = download_required_data_files(repo_id, revision, cache_dir, teleop_records)
    splits = make_splits(records)
    features, actions, episode_ids = load_bc_tensors(data_files, records, task_count=len(task_by_index))

    bc_random = evaluate_bc_split(splits["random_episode"], features, actions, episode_ids, epochs)
    bc_scene = evaluate_bc_split(splits["scene_disjoint"], features, actions, episode_ids, epochs)

    output_dir.mkdir(parents=True, exist_ok=True)
    lineages = lineage_records(records, lineage_payloads)
    split_manifest = {
        "profile": "worldepisode-split-audit-0.1",
        "repo_id": repo_id,
        "revision": revision,
        "random_seed": RANDOM_SEED,
        "world_lineage_field": "world_lineage",
        "splits": splits,
    }
    report = {
        "available": True,
        "pass": True,
        "repo_id": repo_id,
        "revision": revision,
        "dataset": {
            "robot_type": info.get("robot_type"),
            "total_episodes": info.get("total_episodes"),
            "total_frames": info.get("total_frames"),
            "total_tasks": info.get("total_tasks"),
            "teleoperated_reference_episodes": len(teleop_records),
            "policy_types": sorted({record.policy_type for record in records}),
        },
        "source_files": portable_file_descriptors({**metadata_files, **data_files}),
        "lineage_count": len(lineages),
        "heldout_scene_task_indices": sorted(SCENE_HOLDOUT_TASK_INDICES),
        "heldout_scene_tasks": [task_by_index[index] for index in sorted(SCENE_HOLDOUT_TASK_INDICES)],
        "native_lerobot_policy_training": {
            "available": False,
            "reason": "The native `lerobot` Python package is not installed in this execution environment; "
            "this artifact trains an executable Torch MLP BC baseline over LeRobot tensors instead.",
            "recommended_next_run": "Install LeRobot and repeat the split manifest with ACT or Diffusion Policy.",
        },
        "bc_policy_family": "torch_mlp_bc_state_action",
        "splits": {
            "random_episode": {
                **{key: value for key, value in splits["random_episode"].items() if not key.endswith("_episodes")},
                "bc": {key: value for key, value in bc_random.items() if key != "episode_errors"},
            },
            "scene_disjoint": {
                **{key: value for key, value in splits["scene_disjoint"].items() if not key.endswith("_episodes")},
                "bc": {key: value for key, value in bc_scene.items() if key != "episode_errors"},
            },
        },
        "summary": {
            "random_leakage_rate": splits["random_episode"]["leakage_rate"],
            "scene_disjoint_leakage_rate": splits["scene_disjoint"]["leakage_rate"],
            "random_offline_bc_success_rate": bc_random["offline_bc_success_rate"],
            "scene_disjoint_offline_bc_success_rate": bc_scene["offline_bc_success_rate"],
            "success_rate_drop": bc_random["offline_bc_success_rate"] - bc_scene["offline_bc_success_rate"],
            "random_episode_nrmse_mean": bc_random["episode_normalized_rmse_mean"],
            "scene_disjoint_episode_nrmse_mean": bc_scene["episode_normalized_rmse_mean"],
            "episode_nrmse_ratio_scene_over_random": (
                bc_scene["episode_normalized_rmse_mean"] / max(bc_random["episode_normalized_rmse_mean"], 1e-12)
            ),
        },
        "artifacts": {
            "report": str((output_dir / "leakage_report.json").relative_to(ROOT)),
            "world_lineage": str((output_dir / "world_lineage.json").relative_to(ROOT)),
            "split_manifest": str((output_dir / "split_manifest.json").relative_to(ROOT)),
            "bc_episode_errors": str((output_dir / "bc_episode_errors.json").relative_to(ROOT)),
        },
    }
    bc_episode_errors = {
        "random_episode": bc_random["episode_errors"],
        "scene_disjoint": bc_scene["episode_errors"],
    }
    write_json(output_dir / "world_lineage.json", lineages)
    write_json(output_dir / "split_manifest.json", split_manifest)
    write_json(output_dir / "bc_episode_errors.json", bc_episode_errors)
    write_json(output_dir / "leakage_report.json", report)
    return report


def unavailable_report(error: Exception) -> dict[str, Any]:
    return {
        "available": False,
        "pass": False,
        "reason": str(error),
        "reproduce": "python3 -m pip install -r requirements-experiments.txt && "
        "python3 tools/lerobot_scene_leakage_experiment.py --required",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--repo-id", default=DEFAULT_REPO_ID)
    parser.add_argument("--revision", default=DEFAULT_REVISION)
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--required", action="store_true")
    args = parser.parse_args()
    try:
        report = run_scene_leakage_experiment(
            output_dir=args.output_dir,
            cache_dir=args.cache_dir,
            repo_id=args.repo_id,
            revision=args.revision,
            epochs=args.epochs,
        )
    except LeakageExperimentUnavailable as exc:
        report = unavailable_report(exc)
        write_json(args.output_dir / "leakage_report.json", report)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 1 if args.required else 0

    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
