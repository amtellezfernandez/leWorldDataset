#!/usr/bin/env python3
"""Run a deterministic temporal state-action baseline on the committed LeRobot split packages.

This is a measured offline policy baseline, not an ACT/Diffusion or rollout result. It exists to
prove that the WorldEpisode split manifests and compact LeRobot packages are executable end to end:
load the train/test packages, fit a temporal state-history policy, evaluate the same metric on both
split protocols, and write a claim-bounded report.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACKAGE_ROOT = ROOT / "docs" / "experiments" / "lerobot_policy_gate" / "physical_splits"
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "experiments" / "lerobot_temporal_policy_baseline"
DEFAULT_HISTORY_FRAMES = 3
DEFAULT_RIDGE_LAMBDA = 1e-2
DEFAULT_SUCCESS_NRMSE_THRESHOLD = 0.25


def require_pyarrow() -> Any:
    try:
        import pyarrow.parquet as pq  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "pyarrow is required. Run through "
            "`uv run --with pyarrow --with numpy python tools/lerobot_temporal_policy_baseline.py`."
        ) from exc
    return pq


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


def column_array(table: Any, name: str) -> np.ndarray:
    if name not in table.column_names:
        raise ValueError(f"{name!r} column missing from {table.schema}")
    return np.asarray(table[name].to_pylist(), dtype=np.float64)


def load_split_table(package_root: Path, split_name: str, partition: str) -> dict[str, np.ndarray]:
    pq = require_pyarrow()
    data_path = package_root / f"{split_name}_{partition}" / "data" / "chunk-000" / "file-000.parquet"
    table = pq.read_table(data_path)
    return {
        "states": column_array(table, "observation.state"),
        "actions": column_array(table, "action"),
        "episode_index": np.asarray(table["episode_index"].to_pylist(), dtype=np.int64),
        "frame_index": np.asarray(table["frame_index"].to_pylist(), dtype=np.int64),
    }


def temporal_features(states: np.ndarray, episode_index: np.ndarray, history_frames: int) -> np.ndarray:
    rows, state_dim = states.shape
    features = np.empty((rows, state_dim * (history_frames + 1)), dtype=np.float64)
    for row in range(rows):
        parts = []
        for lag in range(history_frames, -1, -1):
            source = row - lag
            if source < 0 or episode_index[source] != episode_index[row]:
                parts.append(states[row])
            else:
                parts.append(states[source])
        features[row] = np.concatenate(parts)
    return features


def fit_ridge_policy(features: np.ndarray, actions: np.ndarray, ridge_lambda: float) -> dict[str, np.ndarray]:
    feature_mean = features.mean(axis=0)
    feature_std = features.std(axis=0)
    feature_std[feature_std < 1e-6] = 1.0
    action_mean = actions.mean(axis=0)
    action_std = actions.std(axis=0)
    action_std[action_std < 1e-6] = 1.0

    normalized_features = (features - feature_mean) / feature_std
    normalized_actions = (actions - action_mean) / action_std
    design = np.concatenate([normalized_features, np.ones((len(normalized_features), 1))], axis=1)
    regularizer = ridge_lambda * np.eye(design.shape[1], dtype=np.float64)
    regularizer[-1, -1] = 0.0
    weights = np.linalg.solve(design.T @ design + regularizer, design.T @ normalized_actions)
    return {
        "feature_mean": feature_mean,
        "feature_std": feature_std,
        "action_mean": action_mean,
        "action_std": action_std,
        "weights": weights,
    }


def predict(policy: dict[str, np.ndarray], features: np.ndarray) -> np.ndarray:
    normalized = (features - policy["feature_mean"]) / policy["feature_std"]
    design = np.concatenate([normalized, np.ones((len(normalized), 1))], axis=1)
    return (design @ policy["weights"]) * policy["action_std"] + policy["action_mean"]


def rmse(values: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(values))))


def evaluate_predictions(
    predicted: np.ndarray,
    target: np.ndarray,
    episode_index: np.ndarray,
    action_std: np.ndarray,
    success_threshold: float,
) -> dict[str, Any]:
    error = predicted - target
    normalized_error = error / action_std
    per_episode = []
    for episode in sorted(set(int(value) for value in episode_index.tolist())):
        mask = episode_index == episode
        per_episode.append(
            {
                "episode_index": episode,
                "normalized_rmse": rmse(normalized_error[mask]),
                "frame_count": int(mask.sum()),
            }
        )
    per_episode_values = np.asarray([row["normalized_rmse"] for row in per_episode], dtype=np.float64)
    success_count = int(np.sum(per_episode_values < success_threshold))
    return {
        "frame_rmse": rmse(error),
        "frame_normalized_rmse": rmse(normalized_error),
        "episode_normalized_rmse_mean": float(per_episode_values.mean()),
        "episode_normalized_rmse_median": float(np.median(per_episode_values)),
        "episode_normalized_rmse_p75": float(np.quantile(per_episode_values, 0.75)),
        "offline_success_threshold": success_threshold,
        "offline_success_count": success_count,
        "offline_success_rate": float(success_count / len(per_episode_values)),
        "episode_count": int(len(per_episode_values)),
        "frame_count": int(len(target)),
        "per_episode": per_episode,
    }


def run_split(
    package_root: Path,
    split_name: str,
    history_frames: int,
    ridge_lambda: float,
    success_threshold: float,
) -> dict[str, Any]:
    train = load_split_table(package_root, split_name, "train")
    test = load_split_table(package_root, split_name, "test")
    train_features = temporal_features(train["states"], train["episode_index"], history_frames)
    test_features = temporal_features(test["states"], test["episode_index"], history_frames)
    policy = fit_ridge_policy(train_features, train["actions"], ridge_lambda)
    predicted = predict(policy, test_features)
    metrics = evaluate_predictions(
        predicted=predicted,
        target=test["actions"],
        episode_index=test["episode_index"],
        action_std=policy["action_std"],
        success_threshold=success_threshold,
    )
    return {
        "split": split_name,
        "train_package": rel(package_root / f"{split_name}_train"),
        "test_package": rel(package_root / f"{split_name}_test"),
        "train_frames": int(len(train["actions"])),
        "test_frames": int(len(test["actions"])),
        "policy": {
            "family": "closed_form_temporal_ridge_state_action",
            "history_frames": history_frames,
            "ridge_lambda": ridge_lambda,
            "feature_dim": int(train_features.shape[1]),
            "state_dim": int(train["states"].shape[1]),
            "action_dim": int(train["actions"].shape[1]),
            "uses_video": False,
            "uses_previous_ground_truth_actions": False,
        },
        "metrics": metrics,
    }


def build_report(
    package_root: Path = DEFAULT_PACKAGE_ROOT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    history_frames: int = DEFAULT_HISTORY_FRAMES,
    ridge_lambda: float = DEFAULT_RIDGE_LAMBDA,
    success_threshold: float = DEFAULT_SUCCESS_NRMSE_THRESHOLD,
) -> dict[str, Any]:
    package_manifest = load_json(package_root / "manifest.json")
    expected_splits = ["random_episode", "scene_disjoint"]
    results = [
        run_split(
            package_root=package_root,
            split_name=split_name,
            history_frames=history_frames,
            ridge_lambda=ridge_lambda,
            success_threshold=success_threshold,
        )
        for split_name in expected_splits
    ]
    by_split = {row["split"]: row for row in results}
    random_success = by_split["random_episode"]["metrics"]["offline_success_rate"]
    scene_success = by_split["scene_disjoint"]["metrics"]["offline_success_rate"]
    random_nrmse = by_split["random_episode"]["metrics"]["episode_normalized_rmse_mean"]
    scene_nrmse = by_split["scene_disjoint"]["metrics"]["episode_normalized_rmse_mean"]
    report = {
        "profile": "worldepisode-temporal-policy-baseline-0.1",
        "status": "measured_offline_temporal_baseline",
        "source": {
            "physical_split_manifest": rel(package_root / "manifest.json"),
            "package_count": package_manifest.get("package_count"),
            "total_output_frames": package_manifest.get("total_output_frames"),
            "source_files_verified": package_manifest.get("source_files_verified"),
        },
        "splits": by_split,
        "aggregate": {
            "random_episode_success_rate": random_success,
            "scene_disjoint_success_rate": scene_success,
            "success_rate_drop": float(random_success - scene_success),
            "random_episode_nrmse_mean": random_nrmse,
            "scene_disjoint_nrmse_mean": scene_nrmse,
            "episode_nrmse_ratio_scene_over_random": float(scene_nrmse / max(random_nrmse, 1e-12)),
        },
        "claim_boundary": (
            "Measured offline temporal state/action baseline over committed compact LeRobot split "
            "packages. This is not ACT, Diffusion Policy, a vision-policy result, a simulator "
            "rollout, or a physical-robot rollout."
        ),
        "artifacts": {
            "json": rel(output_dir / "temporal_policy_report.json"),
            "markdown": rel(output_dir / "README.md"),
        },
    }
    write_json(output_dir / "temporal_policy_report.json", report)
    write_text(output_dir / "README.md", render_markdown(report))
    return report


def render_markdown(report: dict[str, Any]) -> str:
    rows = []
    for split_name in ("random_episode", "scene_disjoint"):
        split = report["splits"][split_name]
        metrics = split["metrics"]
        rows.append(
            "| {split} | {train_frames} | {test_frames} | {nrmse:.3f} | {success:.3f} |".format(
                split=split_name,
                train_frames=split["train_frames"],
                test_frames=split["test_frames"],
                nrmse=metrics["episode_normalized_rmse_mean"],
                success=metrics["offline_success_rate"],
            )
        )
    return f"""# Temporal Policy Baseline

Status: `{report["status"]}`.

{report["claim_boundary"]}

| Split | Train Frames | Test Frames | Episode nRMSE Mean | Thresholded Imitation Rate |
|---|---:|---:|---:|---:|
{chr(10).join(rows)}

Primary task--scene proxy holdout/random nRMSE ratio:
`{report["aggregate"]["episode_nrmse_ratio_scene_over_random"]:.2f}x`.

Secondary thresholded imitation-rate drop: `{report["aggregate"]["success_rate_drop"]:.3f}`.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", type=Path, default=DEFAULT_PACKAGE_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--history-frames", type=int, default=DEFAULT_HISTORY_FRAMES)
    parser.add_argument("--ridge-lambda", type=float, default=DEFAULT_RIDGE_LAMBDA)
    parser.add_argument("--success-threshold", type=float, default=DEFAULT_SUCCESS_NRMSE_THRESHOLD)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    report = build_report(
        package_root=args.package_root,
        output_dir=args.output_dir,
        history_frames=args.history_frames,
        ridge_lambda=args.ridge_lambda,
        success_threshold=args.success_threshold,
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "aggregate": report["aggregate"],
                "artifacts": report["artifacts"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if args.strict and report["aggregate"]["success_rate_drop"] <= 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
