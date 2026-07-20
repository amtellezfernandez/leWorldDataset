from __future__ import annotations

import math

from tools.experiment_statistics import (
    crossed_seed_episode_bootstrap_ci,
    independent_bootstrap_difference_ci,
    paired_seed_independent_episode_difference_ci,
    percentile_bootstrap_ci,
    quantile,
    wilson_interval,
)


def test_quantile_interpolates() -> None:
    assert quantile([0.0, 10.0], 0.25) == 2.5


def test_bootstrap_is_reproducible() -> None:
    first = percentile_bootstrap_ci([1.0, 2.0, 3.0], lambda rows: sum(rows) / len(rows), resamples=200, seed=9)
    second = percentile_bootstrap_ci([1.0, 2.0, 3.0], lambda rows: sum(rows) / len(rows), resamples=200, seed=9)
    assert first == second
    assert first["ci_low"] <= first["estimate"] <= first["ci_high"]


def test_wilson_interval_is_non_degenerate_at_zero() -> None:
    interval = wilson_interval(0, 100)
    assert interval["estimate"] == 0.0
    assert interval["ci_low"] == 0.0
    assert 0.0 < interval["ci_high"] < 0.05


def test_difference_direction() -> None:
    result = independent_bootstrap_difference_ci(
        [1.0, 1.0],
        [0.0, 0.0],
        lambda rows: sum(rows) / len(rows),
        resamples=20,
        seed=4,
        direction="baseline_minus_heldout",
    )
    assert math.isclose(result["estimate"], 1.0)
    assert math.isclose(result["ci_low"], 1.0)
    assert math.isclose(result["ci_high"], 1.0)


def test_crossed_seed_episode_bootstrap_is_reproducible() -> None:
    values = [[0.1, 0.2], [0.2, 0.3]]
    first = crossed_seed_episode_bootstrap_ci(
        values,
        resamples=200,
        seed=11,
    )
    second = crossed_seed_episode_bootstrap_ci(
        values,
        resamples=200,
        seed=11,
    )
    assert first == second
    assert math.isclose(first["estimate"], 0.2)
    assert first["training_seed_count"] == 2
    assert first["sample_size_episodes"] == 2


def test_paired_seed_difference_preserves_direction() -> None:
    result = paired_seed_independent_episode_difference_ci(
        [[1.0, 1.0], [1.0, 1.0]],
        [[0.0, 0.0], [0.0, 0.0]],
        resamples=50,
        seed=5,
        direction="baseline_minus_heldout",
    )
    assert result["estimate"] == 1.0
    assert result["ci_low"] == 1.0
    assert result["ci_high"] == 1.0
