from __future__ import annotations

import argparse
import math

import pytest

from tools.lerobot_scene_leakage_experiment import (
    LeakageExperimentUnavailable,
    aggregate_bc_runs,
    parse_seeds,
    resolve_torch_device,
)


def _run(seed: int, success_rate: float, nrmse: float) -> dict:
    return {
        "policy": {
            "policy_family": "torch_mlp_bc_state_action",
            "epochs": 12,
            "batch_size": 2048,
            "hidden_units": [64, 64],
            "optimizer": "AdamW",
            "seed": seed,
            "final_train_loss": 0.1 + 0.01 * seed,
            "target_std": [1.0, 2.0],
        },
        "train_frames": 20,
        "test_frames": 10,
        "frame_normalized_rmse": nrmse,
        "frame_rmse": nrmse * 2,
        "episode_normalized_rmse_mean": nrmse,
        "episode_normalized_rmse_median": nrmse,
        "episode_normalized_rmse_p75": nrmse,
        "offline_bc_success_threshold": 0.25,
        "offline_bc_success_count": int(2 * success_rate),
        "offline_bc_success_rate": success_rate,
        "episode_errors": [
            {"episode_index": 1, "normalized_rmse": nrmse},
            {"episode_index": 2, "normalized_rmse": nrmse},
        ],
    }


def test_aggregate_bc_runs_preserves_seed_variation() -> None:
    aggregate = aggregate_bc_runs(
        [
            _run(seed=0, success_rate=0.5, nrmse=0.2),
            _run(seed=1, success_rate=1.0, nrmse=0.3),
        ]
    )
    assert aggregate["policy"]["seeds"] == [0, 1]
    assert aggregate["policy"]["seed_count"] == 2
    assert math.isclose(aggregate["offline_bc_success_rate"], 0.75)
    assert math.isclose(aggregate["episode_normalized_rmse_mean"], 0.25)
    assert aggregate["offline_bc_evaluation_count_total"] == 4
    assert len(aggregate["seed_runs"]) == 2


def test_aggregate_bc_runs_rejects_mismatched_test_sets() -> None:
    first = _run(seed=0, success_rate=0.5, nrmse=0.2)
    second = _run(seed=1, success_rate=0.5, nrmse=0.2)
    second["test_frames"] = 11
    with pytest.raises(ValueError, match="test_frames"):
        aggregate_bc_runs([first, second])


def test_parse_seeds_requires_unique_integers() -> None:
    assert parse_seeds("0, 2,4") == (0, 2, 4)
    with pytest.raises(argparse.ArgumentTypeError, match="unique"):
        parse_seeds("1,1")


class _FakeCuda:
    def __init__(self, available: bool) -> None:
        self.available = available

    def is_available(self) -> bool:
        return self.available


class _FakeTorch:
    def __init__(self, cuda_available: bool) -> None:
        self.cuda = _FakeCuda(cuda_available)


def test_resolve_torch_device_auto_uses_available_accelerator() -> None:
    assert resolve_torch_device(_FakeTorch(cuda_available=True), "auto") == "cuda"
    assert resolve_torch_device(_FakeTorch(cuda_available=False), "auto") == "cpu"


def test_resolve_torch_device_rejects_unavailable_cuda() -> None:
    with pytest.raises(LeakageExperimentUnavailable, match="unavailable"):
        resolve_torch_device(_FakeTorch(cuda_available=False), "cuda")
