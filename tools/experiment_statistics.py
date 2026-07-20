#!/usr/bin/env python3
"""Add episode-level uncertainty intervals to the headline offline experiments."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MLP_ERRORS = ROOT / "docs" / "experiments" / "lerobot_scene_leakage" / "bc_episode_errors.json"
DEFAULT_MLP_REPORT = ROOT / "docs" / "experiments" / "lerobot_scene_leakage" / "leakage_report.json"
DEFAULT_TEMPORAL_REPORT = (
    ROOT / "docs" / "experiments" / "lerobot_temporal_policy_baseline" / "temporal_policy_report.json"
)
DEFAULT_OUTPUT = ROOT / "docs" / "experiments" / "statistical_analysis" / "statistical_report.json"
DEFAULT_RESAMPLES = 20_000
DEFAULT_SEED = 2027
CONFIDENCE_LEVEL = 0.95
Z_95 = 1.959963984540054


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def derived_seed(base_seed: int, label: str) -> int:
    digest = hashlib.sha256(f"{base_seed}:{label}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def quantile(values: list[float], probability: float) -> float:
    if not values:
        raise ValueError("cannot take a quantile of an empty sequence")
    ordered = sorted(values)
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def percentile_bootstrap_ci(
    values: list[float],
    statistic: Callable[[list[float]], float],
    *,
    resamples: int,
    seed: int,
) -> dict[str, Any]:
    if not values:
        raise ValueError("cannot bootstrap an empty sequence")
    rng = random.Random(seed)
    sample_size = len(values)
    estimates = [
        statistic([values[rng.randrange(sample_size)] for _ in range(sample_size)])
        for _ in range(resamples)
    ]
    alpha = 1.0 - CONFIDENCE_LEVEL
    return {
        "estimate": statistic(values),
        "ci_low": quantile(estimates, alpha / 2.0),
        "ci_high": quantile(estimates, 1.0 - alpha / 2.0),
        "confidence_level": CONFIDENCE_LEVEL,
        "method": "percentile_episode_bootstrap",
        "resamples": resamples,
        "seed": seed,
        "sample_size_episodes": sample_size,
    }


def independent_bootstrap_difference_ci(
    baseline: list[float],
    heldout: list[float],
    statistic: Callable[[list[float]], float],
    *,
    resamples: int,
    seed: int,
    direction: str,
) -> dict[str, Any]:
    if not baseline or not heldout:
        raise ValueError("cannot compare empty samples")
    rng = random.Random(seed)
    baseline_size = len(baseline)
    heldout_size = len(heldout)

    def difference(left: list[float], right: list[float]) -> float:
        if direction == "baseline_minus_heldout":
            return statistic(left) - statistic(right)
        if direction == "heldout_minus_baseline":
            return statistic(right) - statistic(left)
        raise ValueError(f"unknown direction: {direction}")

    estimates = []
    for _ in range(resamples):
        baseline_sample = [baseline[rng.randrange(baseline_size)] for _ in range(baseline_size)]
        heldout_sample = [heldout[rng.randrange(heldout_size)] for _ in range(heldout_size)]
        estimates.append(difference(baseline_sample, heldout_sample))
    alpha = 1.0 - CONFIDENCE_LEVEL
    return {
        "estimate": difference(baseline, heldout),
        "ci_low": quantile(estimates, alpha / 2.0),
        "ci_high": quantile(estimates, 1.0 - alpha / 2.0),
        "confidence_level": CONFIDENCE_LEVEL,
        "method": "independent_percentile_episode_bootstrap",
        "resamples": resamples,
        "seed": seed,
        "baseline_sample_size_episodes": baseline_size,
        "heldout_sample_size_episodes": heldout_size,
        "direction": direction,
    }


def wilson_interval(successes: int, sample_size: int) -> dict[str, Any]:
    if sample_size <= 0:
        raise ValueError("sample_size must be positive")
    proportion = successes / sample_size
    denominator = 1.0 + Z_95**2 / sample_size
    center = (proportion + Z_95**2 / (2.0 * sample_size)) / denominator
    half_width = (
        Z_95
        * math.sqrt(proportion * (1.0 - proportion) / sample_size + Z_95**2 / (4.0 * sample_size**2))
        / denominator
    )
    ci_low = 0.0 if successes == 0 else max(0.0, center - half_width)
    ci_high = 1.0 if successes == sample_size else min(1.0, center + half_width)
    return {
        "estimate": proportion,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "confidence_level": CONFIDENCE_LEVEL,
        "method": "wilson_score",
        "successes": successes,
        "sample_size_episodes": sample_size,
    }


def crossed_seed_episode_bootstrap_ci(
    values: list[list[float]],
    *,
    resamples: int,
    seed: int,
    threshold: float | None = None,
) -> dict[str, Any]:
    if not values or not values[0]:
        raise ValueError("cannot bootstrap an empty seed-by-episode matrix")
    episode_count = len(values[0])
    if any(len(row) != episode_count for row in values):
        raise ValueError("seed-by-episode matrix must be rectangular")

    def transform(value: float) -> float:
        return float(value <= threshold) if threshold is not None else value

    seed_count = len(values)
    estimate = statistics.fmean(
        transform(value)
        for seed_values in values
        for value in seed_values
    )
    rng = random.Random(seed)
    estimates = []
    for _ in range(resamples):
        sampled_seeds = [rng.randrange(seed_count) for _ in range(seed_count)]
        sampled_episodes = [rng.randrange(episode_count) for _ in range(episode_count)]
        estimates.append(
            statistics.fmean(
                transform(values[seed_index][episode_index])
                for seed_index in sampled_seeds
                for episode_index in sampled_episodes
            )
        )
    alpha = 1.0 - CONFIDENCE_LEVEL
    return {
        "estimate": estimate,
        "ci_low": quantile(estimates, alpha / 2.0),
        "ci_high": quantile(estimates, 1.0 - alpha / 2.0),
        "confidence_level": CONFIDENCE_LEVEL,
        "method": "crossed_training_seed_episode_percentile_bootstrap",
        "resamples": resamples,
        "seed": seed,
        "training_seed_count": seed_count,
        "sample_size_episodes": episode_count,
    }


def paired_seed_independent_episode_difference_ci(
    baseline: list[list[float]],
    heldout: list[list[float]],
    *,
    resamples: int,
    seed: int,
    direction: str,
    threshold: float | None = None,
) -> dict[str, Any]:
    if not baseline or not heldout or not baseline[0] or not heldout[0]:
        raise ValueError("cannot compare empty seed-by-episode matrices")
    if len(baseline) != len(heldout):
        raise ValueError("protocol matrices must use the same training seeds")
    baseline_episode_count = len(baseline[0])
    heldout_episode_count = len(heldout[0])
    if any(len(row) != baseline_episode_count for row in baseline):
        raise ValueError("baseline matrix must be rectangular")
    if any(len(row) != heldout_episode_count for row in heldout):
        raise ValueError("heldout matrix must be rectangular")

    def transform(value: float) -> float:
        return float(value <= threshold) if threshold is not None else value

    def difference(left: float, right: float) -> float:
        if direction == "baseline_minus_heldout":
            return left - right
        if direction == "heldout_minus_baseline":
            return right - left
        raise ValueError(f"unknown direction: {direction}")

    seed_count = len(baseline)
    baseline_estimate = statistics.fmean(
        transform(value)
        for seed_values in baseline
        for value in seed_values
    )
    heldout_estimate = statistics.fmean(
        transform(value)
        for seed_values in heldout
        for value in seed_values
    )
    estimate = difference(baseline_estimate, heldout_estimate)
    rng = random.Random(seed)
    estimates = []
    for _ in range(resamples):
        sampled_seeds = [rng.randrange(seed_count) for _ in range(seed_count)]
        baseline_episodes = [
            rng.randrange(baseline_episode_count)
            for _ in range(baseline_episode_count)
        ]
        heldout_episodes = [
            rng.randrange(heldout_episode_count)
            for _ in range(heldout_episode_count)
        ]
        baseline_sample = statistics.fmean(
            transform(baseline[seed_index][episode_index])
            for seed_index in sampled_seeds
            for episode_index in baseline_episodes
        )
        heldout_sample = statistics.fmean(
            transform(heldout[seed_index][episode_index])
            for seed_index in sampled_seeds
            for episode_index in heldout_episodes
        )
        estimates.append(difference(baseline_sample, heldout_sample))
    alpha = 1.0 - CONFIDENCE_LEVEL
    return {
        "estimate": estimate,
        "ci_low": quantile(estimates, alpha / 2.0),
        "ci_high": quantile(estimates, 1.0 - alpha / 2.0),
        "confidence_level": CONFIDENCE_LEVEL,
        "method": "paired_training_seed_independent_episode_percentile_bootstrap",
        "resamples": resamples,
        "seed": seed,
        "training_seed_count": seed_count,
        "baseline_sample_size_episodes": baseline_episode_count,
        "heldout_sample_size_episodes": heldout_episode_count,
        "direction": direction,
    }


def load_seed_episode_matrix(
    payload: dict[str, Any],
    split_name: str,
) -> dict[str, Any]:
    if "splits" not in payload:
        rows = payload[split_name]
        return {
            "seeds": [0],
            "episode_ids": [int(row["episode_index"]) for row in rows],
            "values": [[float(row["normalized_rmse"]) for row in rows]],
        }

    runs = payload["splits"][split_name]
    if not runs:
        raise ValueError(f"{split_name} has no seed runs")
    episode_ids = [
        int(row["episode_index"])
        for row in runs[0]["episode_errors"]
    ]
    values = []
    seeds = []
    for run in runs:
        run_ids = [
            int(row["episode_index"])
            for row in run["episode_errors"]
        ]
        if run_ids != episode_ids:
            raise ValueError(f"{split_name} seed runs use different episodes")
        seeds.append(int(run["seed"]))
        values.append(
            [float(row["normalized_rmse"]) for row in run["episode_errors"]]
        )
    if len(set(seeds)) != len(seeds):
        raise ValueError(f"{split_name} contains duplicate seeds")
    return {
        "seeds": seeds,
        "episode_ids": episode_ids,
        "values": values,
    }


def summarize_seeded_model(
    *,
    split_matrices: dict[str, list[list[float]]],
    threshold: float,
    resamples: int,
    base_seed: int,
    label: str,
) -> dict[str, Any]:
    split_summaries = {}
    for split_name, values in split_matrices.items():
        per_seed_nrmse = [statistics.fmean(row) for row in values]
        per_seed_success = [
            statistics.fmean(float(value <= threshold) for value in row)
            for row in values
        ]
        split_summaries[split_name] = {
            "episode_nrmse_mean": crossed_seed_episode_bootstrap_ci(
                values,
                resamples=resamples,
                seed=derived_seed(base_seed, f"{label}:{split_name}:nrmse"),
            ),
            "offline_success_rate": crossed_seed_episode_bootstrap_ci(
                values,
                resamples=resamples,
                seed=derived_seed(base_seed, f"{label}:{split_name}:success"),
                threshold=threshold,
            ),
            "seed_variation": {
                "episode_nrmse_mean_sample_std": (
                    statistics.stdev(per_seed_nrmse)
                    if len(per_seed_nrmse) > 1
                    else 0.0
                ),
                "offline_success_rate_sample_std": (
                    statistics.stdev(per_seed_success)
                    if len(per_seed_success) > 1
                    else 0.0
                ),
            },
        }

    random_values = split_matrices["random_episode"]
    heldout_values = split_matrices["scene_disjoint"]
    return {
        "success_threshold_nrmse": threshold,
        "splits": split_summaries,
        "protocol_difference": {
            "nrmse_increase_heldout_minus_random": (
                paired_seed_independent_episode_difference_ci(
                    random_values,
                    heldout_values,
                    resamples=resamples,
                    seed=derived_seed(base_seed, f"{label}:difference:nrmse"),
                    direction="heldout_minus_baseline",
                )
            ),
            "success_drop_random_minus_heldout": (
                paired_seed_independent_episode_difference_ci(
                    random_values,
                    heldout_values,
                    resamples=resamples,
                    seed=derived_seed(base_seed, f"{label}:difference:success"),
                    direction="baseline_minus_heldout",
                    threshold=threshold,
                )
            ),
        },
    }


def summarize_model(
    *,
    split_values: dict[str, list[float]],
    threshold: float,
    resamples: int,
    base_seed: int,
    label: str,
) -> dict[str, Any]:
    split_summaries: dict[str, Any] = {}
    success_values: dict[str, list[float]] = {}
    for split_name, nrmse_values in split_values.items():
        successes = [float(value <= threshold) for value in nrmse_values]
        success_values[split_name] = successes
        split_summaries[split_name] = {
            "episode_nrmse_mean": percentile_bootstrap_ci(
                nrmse_values,
                statistics.fmean,
                resamples=resamples,
                seed=derived_seed(base_seed, f"{label}:{split_name}:nrmse"),
            ),
            "offline_success_rate": wilson_interval(int(sum(successes)), len(successes)),
        }

    random_nrmse = split_values["random_episode"]
    heldout_nrmse = split_values["scene_disjoint"]
    return {
        "success_threshold_nrmse": threshold,
        "splits": split_summaries,
        "protocol_difference": {
            "nrmse_increase_heldout_minus_random": independent_bootstrap_difference_ci(
                random_nrmse,
                heldout_nrmse,
                statistics.fmean,
                resamples=resamples,
                seed=derived_seed(base_seed, f"{label}:difference:nrmse"),
                direction="heldout_minus_baseline",
            ),
            "success_drop_random_minus_heldout": independent_bootstrap_difference_ci(
                success_values["random_episode"],
                success_values["scene_disjoint"],
                statistics.fmean,
                resamples=resamples,
                seed=derived_seed(base_seed, f"{label}:difference:success"),
                direction="baseline_minus_heldout",
            ),
        },
    }


def build_report(
    *,
    mlp_errors_path: Path = DEFAULT_MLP_ERRORS,
    mlp_report_path: Path = DEFAULT_MLP_REPORT,
    temporal_report_path: Path = DEFAULT_TEMPORAL_REPORT,
    resamples: int = DEFAULT_RESAMPLES,
    seed: int = DEFAULT_SEED,
) -> dict[str, Any]:
    mlp_errors = load_json(mlp_errors_path)
    mlp_report = load_json(mlp_report_path)
    temporal_report = load_json(temporal_report_path)

    mlp_matrices = {
        split: load_seed_episode_matrix(mlp_errors, split)
        for split in ("random_episode", "scene_disjoint")
    }
    if mlp_matrices["random_episode"]["seeds"] != mlp_matrices["scene_disjoint"]["seeds"]:
        raise ValueError("MLP protocols use different optimization seeds")
    temporal_values = {
        split: [
            float(row["normalized_rmse"])
            for row in temporal_report["splits"][split]["metrics"]["per_episode"]
        ]
        for split in ("random_episode", "scene_disjoint")
    }
    mlp_threshold = float(
        mlp_report["splits"]["random_episode"]["bc"]["offline_bc_success_threshold"]
    )
    temporal_threshold = float(
        temporal_report["splits"]["random_episode"]["metrics"]["offline_success_threshold"]
    )

    return {
        "profile": "worldepisode-statistical-analysis-0.2",
        "generated_from": [
            relative(mlp_errors_path),
            relative(mlp_report_path),
            relative(temporal_report_path),
        ],
        "resampling_unit": (
            "crossed training seed and held-out episode for the MLP; "
            "held-out episode for deterministic temporal ridge"
        ),
        "confidence_level": CONFIDENCE_LEVEL,
        "models": {
            "torch_mlp_bc": summarize_seeded_model(
                split_matrices={
                    split: matrix["values"]
                    for split, matrix in mlp_matrices.items()
                },
                threshold=mlp_threshold,
                resamples=resamples,
                base_seed=seed,
                label="torch_mlp_bc",
            ),
            "temporal_ridge": summarize_model(
                split_values=temporal_values,
                threshold=temporal_threshold,
                resamples=resamples,
                base_seed=seed,
                label="temporal_ridge",
            ),
        },
        "claim_boundary": [
            "Torch MLP intervals use a crossed bootstrap over optimization seeds and held-out episodes.",
            "The same sampled MLP seeds are paired across protocols; random and held-out episodes are resampled independently.",
            "Five optimization seeds remain a small sample of training variability; the temporal ridge estimator is deterministic.",
            "The held-out protocol is task-scene-proxy-disjoint because task identity is part of the lineage key; it does not isolate scene overlap from task shift.",
            "Intervals quantify offline imitation only and are not rollout-success intervals.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mlp-errors", type=Path, default=DEFAULT_MLP_ERRORS)
    parser.add_argument("--mlp-report", type=Path, default=DEFAULT_MLP_REPORT)
    parser.add_argument("--temporal-report", type=Path, default=DEFAULT_TEMPORAL_REPORT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--resamples", type=int, default=DEFAULT_RESAMPLES)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()
    if args.resamples < 1:
        parser.error("--resamples must be positive")
    report = build_report(
        mlp_errors_path=args.mlp_errors,
        mlp_report_path=args.mlp_report,
        temporal_report_path=args.temporal_report,
        resamples=args.resamples,
        seed=args.seed,
    )
    write_json(args.output, report)
    print(json.dumps({"output": relative(args.output), "profile": report["profile"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
