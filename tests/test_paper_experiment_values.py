from __future__ import annotations

import copy

import pytest

from tools.paper_experiment_values import (
    ASSET_AUDIT_PATH,
    CONVERSION_SCALE_PATH,
    DROID_RERUN_PATH,
    EXPERIMENT_MANIFEST_PATH,
    MULTITRAJECTORY_TIMING_PATH,
    OUTPUT_PATH,
    POLICY_OFFLINE_REFERENCE_PATH,
    POLICY_OFFLINE_REPORT_PATH,
    ROOT,
    RESULTS_PATH,
    STATISTICS_PATH,
    PaperValueError,
    _offline_policy_macro_values,
    _read_json,
    _read_optional_json,
    generate_tex,
)


def _render() -> str:
    return generate_tex(
        _read_json(RESULTS_PATH),
        _read_json(STATISTICS_PATH),
        _read_json(DROID_RERUN_PATH),
        _read_json(CONVERSION_SCALE_PATH),
        _read_json(MULTITRAJECTORY_TIMING_PATH),
        _read_json(EXPERIMENT_MANIFEST_PATH),
        _read_json(ASSET_AUDIT_PATH),
        _read_optional_json(POLICY_OFFLINE_REPORT_PATH),
        _read_json(POLICY_OFFLINE_REFERENCE_PATH),
    )


def test_generated_values_match_committed_tex() -> None:
    assert OUTPUT_PATH.read_text(encoding="utf-8") == _render()


def test_generated_values_include_open_result_placeholder() -> None:
    rendered = _render()
    assert r"\newcommand{\ExpActDiffusionResult}{\PaperNotDefinedYet}" in rendered
    assert r"\newcommand{\ExpOfflinePolicyResult}{\PaperNotDefinedYet}" in rendered
    assert r"\newcommand{\ExpActRandomNrmse}{\PaperNotDefinedYet}" in rendered
    assert r"\newcommand{\ExpPolicyCompatibilityLeRobotVersion}{0.6.0}" in rendered
    assert r"\newcommand{\ExpPolicyCompatibilityTrainingStepCount}{0}" in rendered
    assert r"\newcommand{\ExpPolicyCompatibilityExpectedBlockerCount}{2}" in rendered
    assert r"\newcommand{\ExpPolicyVisionLeRobotVersion}{0.6.0}" in rendered
    assert r"\newcommand{\ExpPolicyVisionProbeCount}{2}" in rendered
    assert r"\newcommand{\ExpPolicyVisionTrainingStepCount}{2}" in rendered
    assert r"\newcommand{\ExpPolicyVisionAssetCount}{24}" in rendered
    assert r"\newcommand{\ExpPolicyVisionPackageCount}{4}" in rendered
    assert r"\newcommand{\ExpSceneOnlyLeakageResult}{\PaperNotDefinedYet}" in rendered
    assert r"\newcommand{\ExpTemporalNrmseDifference}" in rendered
    assert r"\newcommand{\ExpConversionScaleEpisodeCount}{271}" in rendered
    assert r"\newcommand{\ExpConversionScaleMaxError}{0.0}" in rendered
    assert r"\newcommand{\ExpTimingHeldoutEpisodes}{80}" in rendered
    assert r"\newcommand{\ExpTimingImprovementCiLow}{2.890}" in rendered


def test_missing_required_value_fails_closed() -> None:
    results = copy.deepcopy(_read_json(RESULTS_PATH))
    del results["lerobot_scene_leakage"]["splits"]["random_episode"]["bc"]["offline_bc_success_rate"]
    with pytest.raises(PaperValueError, match="offline_bc_success_rate"):
        generate_tex(
            results,
            _read_json(STATISTICS_PATH),
            _read_json(DROID_RERUN_PATH),
            _read_json(CONVERSION_SCALE_PATH),
            _read_json(MULTITRAJECTORY_TIMING_PATH),
            _read_json(EXPERIMENT_MANIFEST_PATH),
            _read_json(ASSET_AUDIT_PATH),
        )


def test_passing_offline_policy_report_defines_generated_metrics() -> None:
    def metric(estimate: float) -> dict[str, object]:
        return {
            "estimate": estimate,
            "ci_low": estimate - 0.1,
            "ci_high": estimate + 0.1,
            "confidence_level": 0.95,
            "resamples": 20_000,
            "seed_count": 5,
            "episode_count": 21,
            "seed_sample_std": 0.02,
        }

    report = {
        "profile": "worldepisode-lerobot-offline-policy-report-0.1",
        "status": "offline_policy_experiment_complete",
        "pass": True,
        "completed_job_count": 20,
        "required_job_count": 20,
        "analysis": {
            "metric": "episode_normalized_rmse_mean",
            "policies": {
                policy: {
                    "splits": {
                        "random_episode": metric(offset),
                        "task_confounded_lineage_holdout": metric(offset + 1.0),
                    },
                    "paired_effect": metric(1.0),
                }
                for policy, offset in (("act", 1.0), ("diffusion", 2.0))
            },
        },
        "compute": {
            "training_wall_time_seconds": 36_000.0,
            "evaluation_wall_time_seconds": 3_600.0,
        },
    }
    values, ready = _offline_policy_macro_values(
        report,
        _read_json(POLICY_OFFLINE_REFERENCE_PATH),
    )
    macros = dict(values)
    assert ready is True
    assert macros["ExpOfflinePolicyFrameCount"] == "4{,}085"
    assert macros["ExpOfflinePolicyTrainingHours"] == "10.0"
    assert macros["ExpActRandomNrmse"] == "1.0000"
    assert macros["ExpDiffusionHeldoutNrmseCiHigh"] == "3.1000"


def test_paper_sources_do_not_repeat_headline_measurements() -> None:
    source_paths = [
        ROOT / "paper/arxiv/main.tex",
        ROOT / "paper/arxiv/checklist.tex",
        *sorted((ROOT / "paper/arxiv/sections").glob("*.tex")),
    ]
    paper = "\n".join(path.read_text(encoding="utf-8") for path in source_paths)
    for stale_literal in (
        "0.850",
        "0.925",
        "4.732",
        "1.862",
        "3.425",
        "1.563",
        "1{,}935",
        "271",
        "43{,}601",
        "5.2",
        "48.24",
        "393.3",
        "17.5",
        "4.845",
        "1.934",
        "3.087",
        "2.890",
        "3.286",
        "32{,}768",
        "1{,}073{,}741{,}824",
        "ten public episodes",
        "five seeds remain",
        "yields a mean \\ExpMlpRandomSuccessRate{} thresholded offline imitation rate",
        "changes thresholded MLP imitation",
    ):
        assert stale_literal not in paper
