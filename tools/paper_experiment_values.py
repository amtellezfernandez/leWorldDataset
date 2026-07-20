#!/usr/bin/env python3
"""Generate paper-facing TeX values from committed experiment reports."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RESULTS_PATH = ROOT / "docs/experiments/results.json"
STATISTICS_PATH = ROOT / "docs/experiments/statistical_analysis/statistical_report.json"
DROID_RERUN_PATH = ROOT / "docs/experiments/benchmark_reruns/droid_100/rerun_report.json"
CONVERSION_SCALE_PATH = (
    ROOT / "docs/experiments/lerobot_conversion_scale/scale_report.json"
)
MULTITRAJECTORY_TIMING_PATH = (
    ROOT / "docs/experiments/lerobot_multitrajectory_timing/timing_report.json"
)
EXPERIMENT_MANIFEST_PATH = (
    ROOT / "docs/experiments/experiment_manifest/experiment_manifest.json"
)
ASSET_AUDIT_PATH = (
    ROOT / "docs/experiments/third_party_asset_audit/asset_audit.json"
)
OUTPUT_PATH = ROOT / "paper/arxiv/generated/experiment_values.tex"
VOLATILE_RESULT_KEYS = {
    "catalog_open_parse_and_index",
    "digest_cache_resolution",
    "partition_pruning_queries",
    "resolver_routing",
}


class PaperValueError(ValueError):
    """Raised when a paper value cannot be derived from the experiment reports."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PaperValueError(f"required experiment report is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PaperValueError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PaperValueError(f"expected a JSON object in {path}")
    return value


def _get(document: dict[str, Any], path: str) -> Any:
    value: Any = document
    for component in path.split("."):
        if not isinstance(value, dict) or component not in value:
            raise PaperValueError(f"required paper value is missing: {path}")
        value = value[component]
    if value is None:
        raise PaperValueError(f"required paper value is null: {path}")
    return value


def _as_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PaperValueError(f"{name} must be numeric, got {value!r}")
    if not math.isfinite(float(value)):
        raise PaperValueError(f"{name} must be finite, got {value!r}")
    return float(value)


def _as_int(value: Any, name: str) -> int:
    number = _as_number(value, name)
    if not number.is_integer():
        raise PaperValueError(f"{name} must be an integer, got {value!r}")
    return int(number)


def _tex_int(value: Any, name: str) -> str:
    return f"{_as_int(value, name):,}".replace(",", "{,}")


def _fixed(value: Any, digits: int, name: str) -> str:
    return f"{_as_number(value, name):.{digits}f}"


def _percent_integer(value: Any, name: str) -> str:
    return str(round(100 * _as_number(value, name)))


def _macro(name: str, value: str) -> str:
    if not name.isalpha():
        raise PaperValueError(f"TeX macro names must contain letters only: {name}")
    return rf"\newcommand{{\{name}}}{{{value}}}"


def _binding(results: dict[str, Any], binding_id: str) -> dict[str, Any]:
    bindings = _get(results, "rq1_binding_retention.bindings")
    if not isinstance(bindings, list):
        raise PaperValueError("rq1_binding_retention.bindings must be a list")
    for binding in bindings:
        if isinstance(binding, dict) and binding.get("binding") == binding_id:
            return binding
    raise PaperValueError(f"required binding is missing: {binding_id}")


def _experiment(manifest: dict[str, Any], experiment_id: str) -> dict[str, Any]:
    experiments = _get(manifest, "experiments")
    if not isinstance(experiments, list):
        raise PaperValueError("experiment manifest experiments must be a list")
    for experiment in experiments:
        if isinstance(experiment, dict) and experiment.get("experiment_id") == experiment_id:
            return experiment
    raise PaperValueError(f"required experiment provenance is missing: {experiment_id}")


def _dataset_license(asset_audit: dict[str, Any], repo_id: str) -> str:
    datasets = _get(asset_audit, "active_datasets")
    if not isinstance(datasets, list):
        raise PaperValueError("asset audit active_datasets must be a list")
    for dataset in datasets:
        if isinstance(dataset, dict) and dataset.get("repo_id") == repo_id:
            license_expression = dataset.get("license_expression")
            if not isinstance(license_expression, str) or not license_expression:
                raise PaperValueError(
                    f"asset audit has no license expression for {repo_id}"
                )
            return license_expression.replace(" AND ", " and ")
    raise PaperValueError(f"asset audit has no active dataset record for {repo_id}")


def _maximum_roundtrip_error(results: dict[str, Any]) -> float:
    roundtrip = _get(results, "lerobot_active_roundtrip")
    reports = [_get(roundtrip, "batch_roundtrip")]
    secondary = _get(roundtrip, "secondary_batch_roundtrips")
    if not isinstance(secondary, list):
        raise PaperValueError("secondary_batch_roundtrips must be a list")
    reports.extend(secondary)
    errors: list[float] = []
    for report in reports:
        if not isinstance(report, dict) or not isinstance(report.get("max_errors"), dict):
            raise PaperValueError("each batch round-trip must provide max_errors")
        errors.extend(
            _as_number(value, f"roundtrip max error {key}")
            for key, value in report["max_errors"].items()
        )
    if not errors:
        raise PaperValueError("round-trip reports contain no numerical errors")
    return max(errors)


def _source_digest(path: Path) -> str:
    if path != RESULTS_PATH:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def normalize(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: 0.0 if key in VOLATILE_RESULT_KEYS else normalize(child)
                for key, child in value.items()
            }
        if isinstance(value, list):
            return [normalize(child) for child in value]
        return value

    canonical = json.dumps(
        normalize(_read_json(path)),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def generate_tex(
    results: dict[str, Any],
    statistics: dict[str, Any],
    droid_rerun: dict[str, Any],
    conversion_scale: dict[str, Any],
    multitrajectory_timing: dict[str, Any],
    experiment_manifest: dict[str, Any],
    asset_audit: dict[str, Any],
) -> str:
    """Render all experiment-derived values used by the paper."""

    scene = _get(results, "lerobot_scene_leakage")
    random_split = _get(scene, "splits.random_episode")
    heldout_split = _get(scene, "splits.scene_disjoint")
    random_bc = _get(random_split, "bc")
    heldout_bc = _get(heldout_split, "bc")
    mlp_policy = _get(random_bc, "policy")
    heldout_mlp_policy = _get(heldout_bc, "policy")
    hidden_units = _get(mlp_policy, "hidden_units")
    if not isinstance(hidden_units, list) or not hidden_units:
        raise PaperValueError("MLP hidden_units must be a non-empty list")
    if len({_as_int(unit, "MLP hidden unit") for unit in hidden_units}) != 1:
        raise PaperValueError("paper prose requires equal hidden-unit counts in every MLP layer")
    mlp_seeds = _get(mlp_policy, "seeds")
    if not isinstance(mlp_seeds, list) or not mlp_seeds:
        raise PaperValueError("MLP seeds must be a non-empty list")
    if mlp_seeds != _get(heldout_mlp_policy, "seeds"):
        raise PaperValueError("random and held-out MLP protocols must use identical seeds")
    if len(set(_as_int(seed, "MLP seed") for seed in mlp_seeds)) != len(mlp_seeds):
        raise PaperValueError("MLP seeds must be unique")
    if _as_int(_get(mlp_policy, "seed_count"), "MLP seed count") != len(mlp_seeds):
        raise PaperValueError("MLP seed_count does not match the seed list")
    if _get(statistics, "profile") != "worldepisode-statistical-analysis-0.2":
        raise PaperValueError("paper requires the multi-seed statistical analysis profile")
    if _get(experiment_manifest, "schema") != "worldepisode_experiment_manifest_v1":
        raise PaperValueError("paper requires the validated experiment provenance manifest")
    if _get(experiment_manifest, "validation.passed") is not True:
        raise PaperValueError("experiment provenance manifest validation did not pass")
    if _get(conversion_scale, "schema") != "worldepisode_lerobot_conversion_scale_v1":
        raise PaperValueError("paper requires the validated LeRobot conversion-scale report")
    if _get(conversion_scale, "validation.passed") is not True:
        raise PaperValueError("LeRobot conversion-scale report validation did not pass")
    if (
        _get(multitrajectory_timing, "schema")
        != "worldepisode_lerobot_multitrajectory_timing_v1"
    ):
        raise PaperValueError("paper requires the multi-trajectory timing report")
    if _get(multitrajectory_timing, "validation.passed") is not True:
        raise PaperValueError("multi-trajectory timing report validation did not pass")
    if _get(asset_audit, "schema") != "worldepisode_third_party_asset_audit_v1":
        raise PaperValueError("paper requires the validated third-party asset audit")
    if _get(asset_audit, "validation.passed") is not True:
        raise PaperValueError("third-party asset audit validation did not pass")

    mlp_provenance = _experiment(experiment_manifest, "armnet_task_scene_proxy_mlp")
    droid_provenance = _experiment(experiment_manifest, "droid_100_proxy_ridge_rerun")
    controlled_provenance = _experiment(experiment_manifest, "controlled_contract_suite")
    conversion_scale_provenance = _experiment(
        experiment_manifest, "lerobot_conversion_scale"
    )
    multitrajectory_timing_provenance = _experiment(
        experiment_manifest, "lerobot_multitrajectory_timing"
    )
    gpu_info = str(_get(mlp_provenance, "execution.host.gpu_info"))
    accelerator_name = gpu_info.split(",", 1)[0].strip()
    if not accelerator_name:
        raise PaperValueError("experiment provenance GPU name is empty")

    heldout_task_indices = _get(scene, "heldout_scene_task_indices")
    if not isinstance(heldout_task_indices, list) or not heldout_task_indices:
        raise PaperValueError("heldout_scene_task_indices must be a non-empty list")
    heldout_task_text = " and ".join(str(_as_int(v, "held-out task index")) for v in heldout_task_indices)

    random_train = _as_int(_get(random_split, "train_count"), "random train count")
    random_test = _as_int(_get(random_split, "test_count"), "random test count")
    random_total = random_train + random_test
    random_train_percent = round(100 * random_train / random_total)
    random_test_percent = 100 - random_train_percent

    stats_mlp = _get(statistics, "models.torch_mlp_bc")
    stats_temporal = _get(statistics, "models.temporal_ridge")
    temporal = _get(results, "lerobot_temporal_policy_baseline")
    temporal_random = _get(temporal, "splits.random_episode")
    temporal_heldout = _get(temporal, "splits.scene_disjoint")
    policy_compatibility = _get(results, "lerobot_policy_gate.policy_compatibility")
    policy_probes = _get(policy_compatibility, "policy_probes")
    policy_probe_count = len(policy_probes)
    policy_training_step_count = sum(
        bool(probe.get("training_step_completed"))
        for probe in policy_probes
    )
    policy_expected_blocker_count = sum(
        bool(probe.get("expected_modality_error_observed"))
        for probe in policy_probes
    )

    replay = _get(results, "rq3_replay")
    alignment = _get(replay, "alignment")
    mujoco = _get(replay, "simulators.mujoco")
    genesis = _get(replay, "simulators.genesis")
    replay_simulators = _get(replay, "simulators")
    if not isinstance(replay_simulators, dict):
        raise PaperValueError("rq3_replay.simulators must be an object")
    tested_replay_simulator_count = sum(
        1
        for simulator in replay_simulators.values()
        if isinstance(simulator, dict) and simulator.get("tested") is True
    )
    replay_trace_count = len({_get(replay, "source_trace")})
    timing_calibration = _get(multitrajectory_timing, "calibration")
    timing_evaluation = _get(multitrajectory_timing, "evaluation")
    timing_improvement = _get(timing_evaluation, "paired_episode_improvement")
    if _get(multitrajectory_timing, "source.source_episode_overlap_count") != 0:
        raise PaperValueError("timing calibration and evaluation source episodes overlap")
    if _get(multitrajectory_timing, "source.effective_motor_timestamp_available") is not False:
        raise PaperValueError("timing source boundary unexpectedly claims motor timestamps")
    if _as_number(_get(timing_improvement, "ci_low"), "timing improvement CI low") <= 0:
        raise PaperValueError("timing held-out improvement CI must exclude zero")
    if _as_int(
        _get(timing_improvement, "improved_episode_count"),
        "timing improved episode count",
    ) != _as_int(_get(timing_evaluation, "episode_count"), "timing episode count"):
        raise PaperValueError("paper prose requires every timing evaluation episode to improve")

    roundtrip = _get(results, "lerobot_active_roundtrip")
    roundtrip_reports = [_get(roundtrip, "batch_roundtrip")]
    secondary_roundtrips = _get(roundtrip, "secondary_batch_roundtrips")
    if not isinstance(secondary_roundtrips, list):
        raise PaperValueError("secondary_batch_roundtrips must be a list")
    roundtrip_reports.extend(secondary_roundtrips)
    roundtrip_episode_count = sum(
        _as_int(_get(report, "episode_count"), "round-trip episode count")
        for report in roundtrip_reports
    )
    roundtrip_action_rows = sum(
        _as_int(_get(report, "total_action_rows"), "round-trip action rows")
        for report in roundtrip_reports
    )
    roundtrip_state_rows = sum(
        _as_int(_get(report, "total_state_rows"), "round-trip state rows")
        for report in roundtrip_reports
    )
    conversion_scale_action_rows = _as_int(
        _get(conversion_scale, "aggregate.action_row_count"),
        "conversion-scale action rows",
    )
    conversion_scale_state_rows = _as_int(
        _get(conversion_scale, "aggregate.state_row_count"),
        "conversion-scale state rows",
    )
    if conversion_scale_action_rows != conversion_scale_state_rows:
        raise PaperValueError(
            "paper prose requires equal conversion-scale action and state row counts"
        )
    if _get(conversion_scale, "protocol.source_media_policy") != (
        "Video stream metadata is audited, but source video payloads are not "
        "downloaded or redistributed."
    ):
        raise PaperValueError("conversion-scale source-media boundary changed")
    preliminary_scale_runs = _get(
        conversion_scale_provenance, "execution.preliminary_runs"
    )
    if not isinstance(preliminary_scale_runs, list):
        raise PaperValueError("conversion-scale preliminary_runs must be a list")

    bindings = _get(results, "rq1_binding_retention")
    non_reference_bindings = [
        item
        for item in _get(bindings, "bindings")
        if isinstance(item, dict) and item.get("binding") != "worldepisode-reference"
    ]
    native_retentions = [
        _as_number(_get(item, "native_retention"), "binding native retention")
        for item in non_reference_bindings
    ]

    benchmark_gate = _get(results, "benchmark_inflation_gate")
    if _get(droid_rerun, "benchmark_id") != "droid":
        raise PaperValueError("DROID rerun report has the wrong benchmark_id")

    scale_audit = _get(results, "dataset_scale_audit.aggregate")
    scale_performance = _get(results, "dataset_scale_performance")
    generated_catalog = _get(scale_performance, "generated_catalog")
    av_pilot = next(
        (
            case
            for case in _get(results, "uss_state_drift_pilots.cases")
            if isinstance(case, dict) and case.get("case_id") == "autonomous_vehicle_clock_domain_drift"
        ),
        None,
    )
    if av_pilot is None:
        raise PaperValueError("autonomous-driving clock-domain pilot is missing")

    confidence_percent = _percent_integer(
        _get(statistics, "confidence_level"), "confidence level"
    )
    resamples = _get(
        stats_mlp,
        "splits.random_episode.episode_nrmse_mean.resamples",
    )

    values: list[tuple[str, str]] = [
        ("ExpConfidencePercent", confidence_percent),
        ("ExpBootstrapResamples", _tex_int(resamples, "bootstrap resamples")),
        ("ExpProvenanceExperimentCount", _tex_int(_get(experiment_manifest, "aggregate.experiment_count"), "provenance experiment count")),
        ("ExpComputeAccelerator", accelerator_name),
        ("ExpComputeCpuCount", _tex_int(_get(mlp_provenance, "execution.host.cpu_logical_count"), "compute CPU count")),
        ("ExpComputeRamGiB", _fixed(_as_number(_get(mlp_provenance, "execution.host.total_ram_bytes"), "compute RAM bytes") / (1024**3), 1, "compute RAM GiB")),
        ("ExpMlpWallSeconds", _fixed(_get(mlp_provenance, "execution.compute.wall_time_seconds"), 2, "MLP wall time")),
        ("ExpMlpPeakMemoryMiB", _fixed(_as_number(_get(mlp_provenance, "execution.compute.max_rss_bytes"), "MLP max RSS bytes") / (1024**2), 1, "MLP max RSS MiB")),
        ("ExpDroidWallSeconds", _fixed(_get(droid_provenance, "execution.compute.wall_time_seconds"), 2, "DROID wall time")),
        ("ExpControlledWallSeconds", _fixed(_get(controlled_provenance, "execution.compute.wall_time_seconds"), 2, "controlled-suite wall time")),
        ("ExpConversionScaleWallSeconds", _fixed(_get(conversion_scale_provenance, "execution.compute.wall_time_seconds"), 2, "conversion-scale wall time")),
        ("ExpConversionScalePeakMemoryMiB", _fixed(_as_number(_get(conversion_scale_provenance, "execution.compute.max_rss_bytes"), "conversion-scale max RSS bytes") / (1024**2), 1, "conversion-scale max RSS MiB")),
        ("ExpConversionScaleFailedRunCount", _tex_int(len(preliminary_scale_runs), "conversion-scale failed preliminary run count")),
        ("ExpTimingWallSeconds", _fixed(_get(multitrajectory_timing_provenance, "execution.compute.wall_time_seconds"), 2, "timing wall time")),
        ("ExpTimingPeakMemoryMiB", _fixed(_as_number(_get(multitrajectory_timing_provenance, "execution.compute.max_rss_bytes"), "timing max RSS bytes") / (1024**2), 1, "timing max RSS MiB")),
        ("ExpAssetActiveDatasetCount", _tex_int(_get(asset_audit, "aggregate.active_dataset_count"), "asset active dataset count")),
        ("ExpAssetRedistributedParquetCount", _tex_int(_get(asset_audit, "aggregate.redistributed_parquet_count"), "redistributed Parquet count")),
        ("ExpAssetSourceLicenseFileCount", _tex_int(_get(asset_audit, "aggregate.source_license_file_count"), "source license file count")),
        ("ExpAssetSourceMediaCount", _tex_int(_get(asset_audit, "aggregate.source_media_count"), "source media count")),
        ("ExpAssetArmnetLicense", _dataset_license(asset_audit, "armnet/armnetbench_v01_lerobot_so101")),
        ("ExpAssetSvlaLicense", _dataset_license(asset_audit, "lerobot/svla_so101_pickplace")),
        ("ExpAssetPushtLicense", _dataset_license(asset_audit, "lerobot/pusht")),
        ("ExpAssetDroidLicense", _dataset_license(asset_audit, "lerobot/droid_100")),
        ("ExpSceneEpisodeCount", _tex_int(_get(scene, "dataset.teleoperated_reference_episodes"), "scene episode count")),
        ("ExpSceneLineageCount", _tex_int(_get(scene, "lineage_count"), "scene lineage count")),
        ("ExpSceneHeldoutGroupCount", _tex_int(len(heldout_task_indices), "held-out group count")),
        ("ExpSceneHeldoutTaskIndices", heldout_task_text),
        ("ExpSceneRandomTrainPercent", str(random_train_percent)),
        ("ExpSceneRandomTestPercent", str(random_test_percent)),
        ("ExpSceneRandomTrainEpisodes", _tex_int(random_train, "random train count")),
        ("ExpSceneRandomTestEpisodes", _tex_int(random_test, "random test count")),
        ("ExpSceneHeldoutTrainEpisodes", _tex_int(_get(heldout_split, "train_count"), "held-out train count")),
        ("ExpSceneHeldoutTestEpisodes", _tex_int(_get(heldout_split, "test_count"), "held-out test count")),
        ("ExpSceneRandomOverlap", _fixed(_get(random_split, "leakage_rate"), 3, "random proxy overlap")),
        ("ExpSceneHeldoutOverlap", _fixed(_get(heldout_split, "leakage_rate"), 3, "held-out proxy overlap")),
        ("ExpSceneRandomOverlapPlot", _fixed(_get(random_split, "leakage_rate"), 2, "random proxy overlap plot")),
        ("ExpSceneHeldoutOverlapPlot", _fixed(_get(heldout_split, "leakage_rate"), 2, "held-out proxy overlap plot")),
        ("ExpMlpLayerCount", _tex_int(len(hidden_units), "MLP layer count")),
        ("ExpMlpHiddenUnits", _tex_int(hidden_units[0], "MLP hidden units")),
        ("ExpMlpEpochCount", _tex_int(_get(mlp_policy, "epochs"), "MLP epoch count")),
        ("ExpMlpSeedCount", _tex_int(len(mlp_seeds), "MLP seed count")),
        ("ExpOfflineSuccessThreshold", _fixed(_get(random_bc, "offline_bc_success_threshold"), 2, "offline success threshold")),
        ("ExpMlpRandomSuccessRate", _fixed(_get(random_bc, "offline_bc_success_rate"), 3, "MLP random success rate")),
        ("ExpMlpRandomSuccessSeedStd", _fixed(_get(random_bc, "seed_variation.offline_bc_success_rate.sample_std"), 3, "MLP random success seed standard deviation")),
        ("ExpMlpHeldoutSuccessRate", _fixed(_get(heldout_bc, "offline_bc_success_rate"), 3, "MLP held-out success rate")),
        ("ExpMlpHeldoutSuccessSeedStd", _fixed(_get(heldout_bc, "seed_variation.offline_bc_success_rate.sample_std"), 3, "MLP held-out success seed standard deviation")),
        ("ExpMlpRandomSuccessCiLow", _fixed(_get(stats_mlp, "splits.random_episode.offline_success_rate.ci_low"), 3, "MLP random success CI low")),
        ("ExpMlpRandomSuccessCiHigh", _fixed(_get(stats_mlp, "splits.random_episode.offline_success_rate.ci_high"), 3, "MLP random success CI high")),
        ("ExpMlpHeldoutSuccessCiLow", _fixed(_get(stats_mlp, "splits.scene_disjoint.offline_success_rate.ci_low"), 3, "MLP held-out success CI low")),
        ("ExpMlpHeldoutSuccessCiHigh", _fixed(_get(stats_mlp, "splits.scene_disjoint.offline_success_rate.ci_high"), 3, "MLP held-out success CI high")),
        ("ExpMlpSuccessDifference", _fixed(_get(stats_mlp, "protocol_difference.success_drop_random_minus_heldout.estimate"), 3, "MLP success-rate difference")),
        ("ExpMlpSuccessDifferenceCiLow", _fixed(_get(stats_mlp, "protocol_difference.success_drop_random_minus_heldout.ci_low"), 3, "MLP success-rate difference CI low")),
        ("ExpMlpSuccessDifferenceCiHigh", _fixed(_get(stats_mlp, "protocol_difference.success_drop_random_minus_heldout.ci_high"), 3, "MLP success-rate difference CI high")),
        ("ExpMlpRandomNrmse", _fixed(_get(random_bc, "episode_normalized_rmse_mean"), 3, "MLP random nRMSE")),
        ("ExpMlpRandomNrmseSeedStd", _fixed(_get(random_bc, "seed_variation.episode_normalized_rmse_mean.sample_std"), 3, "MLP random nRMSE seed standard deviation")),
        ("ExpMlpHeldoutNrmse", _fixed(_get(heldout_bc, "episode_normalized_rmse_mean"), 3, "MLP held-out nRMSE")),
        ("ExpMlpHeldoutNrmseSeedStd", _fixed(_get(heldout_bc, "seed_variation.episode_normalized_rmse_mean.sample_std"), 3, "MLP held-out nRMSE seed standard deviation")),
        ("ExpMlpRandomNrmseCiLow", _fixed(_get(stats_mlp, "splits.random_episode.episode_nrmse_mean.ci_low"), 3, "MLP random nRMSE CI low")),
        ("ExpMlpRandomNrmseCiHigh", _fixed(_get(stats_mlp, "splits.random_episode.episode_nrmse_mean.ci_high"), 3, "MLP random nRMSE CI high")),
        ("ExpMlpHeldoutNrmseCiLow", _fixed(_get(stats_mlp, "splits.scene_disjoint.episode_nrmse_mean.ci_low"), 3, "MLP held-out nRMSE CI low")),
        ("ExpMlpHeldoutNrmseCiHigh", _fixed(_get(stats_mlp, "splits.scene_disjoint.episode_nrmse_mean.ci_high"), 3, "MLP held-out nRMSE CI high")),
        ("ExpMlpNrmseDifference", _fixed(_get(stats_mlp, "protocol_difference.nrmse_increase_heldout_minus_random.estimate"), 3, "MLP nRMSE difference")),
        ("ExpMlpNrmseDifferenceCiLow", _fixed(_get(stats_mlp, "protocol_difference.nrmse_increase_heldout_minus_random.ci_low"), 3, "MLP nRMSE difference CI low")),
        ("ExpMlpNrmseDifferenceCiHigh", _fixed(_get(stats_mlp, "protocol_difference.nrmse_increase_heldout_minus_random.ci_high"), 3, "MLP nRMSE difference CI high")),
        ("ExpTemporalHistoryFrames", _tex_int(_get(temporal_random, "policy.history_frames"), "temporal history frames")),
        ("ExpTemporalRandomNrmse", _fixed(_get(temporal_random, "metrics.episode_normalized_rmse_mean"), 3, "temporal random nRMSE")),
        ("ExpTemporalHeldoutNrmse", _fixed(_get(temporal_heldout, "metrics.episode_normalized_rmse_mean"), 3, "temporal held-out nRMSE")),
        ("ExpTemporalRandomNrmseCiLow", _fixed(_get(stats_temporal, "splits.random_episode.episode_nrmse_mean.ci_low"), 3, "temporal random nRMSE CI low")),
        ("ExpTemporalRandomNrmseCiHigh", _fixed(_get(stats_temporal, "splits.random_episode.episode_nrmse_mean.ci_high"), 3, "temporal random nRMSE CI high")),
        ("ExpTemporalHeldoutNrmseCiLow", _fixed(_get(stats_temporal, "splits.scene_disjoint.episode_nrmse_mean.ci_low"), 3, "temporal held-out nRMSE CI low")),
        ("ExpTemporalHeldoutNrmseCiHigh", _fixed(_get(stats_temporal, "splits.scene_disjoint.episode_nrmse_mean.ci_high"), 3, "temporal held-out nRMSE CI high")),
        ("ExpTemporalNrmseDifference", _fixed(_get(stats_temporal, "protocol_difference.nrmse_increase_heldout_minus_random.estimate"), 3, "temporal nRMSE difference")),
        ("ExpTemporalNrmseDifferenceCiLow", _fixed(_get(stats_temporal, "protocol_difference.nrmse_increase_heldout_minus_random.ci_low"), 3, "temporal nRMSE difference CI low")),
        ("ExpTemporalNrmseDifferenceCiHigh", _fixed(_get(stats_temporal, "protocol_difference.nrmse_increase_heldout_minus_random.ci_high"), 3, "temporal nRMSE difference CI high")),
        ("ExpTemporalRandomSuccessRate", _fixed(_get(temporal_random, "metrics.offline_success_rate"), 3, "temporal random success rate")),
        ("ExpTemporalRandomSuccessCount", _tex_int(_get(temporal_random, "metrics.offline_success_count"), "temporal random success count")),
        ("ExpTemporalHeldoutSuccessRate", _fixed(_get(temporal_heldout, "metrics.offline_success_rate"), 3, "temporal held-out success rate")),
        ("ExpTemporalHeldoutSuccessCount", _tex_int(_get(temporal_heldout, "metrics.offline_success_count"), "temporal held-out success count")),
        ("ExpTemporalRandomSuccessCiLow", _fixed(_get(stats_temporal, "splits.random_episode.offline_success_rate.ci_low"), 3, "temporal random success CI low")),
        ("ExpTemporalRandomSuccessCiHigh", _fixed(_get(stats_temporal, "splits.random_episode.offline_success_rate.ci_high"), 3, "temporal random success CI high")),
        ("ExpTemporalHeldoutSuccessCiLow", _fixed(_get(stats_temporal, "splits.scene_disjoint.offline_success_rate.ci_low"), 3, "temporal held-out success CI low")),
        ("ExpTemporalHeldoutSuccessCiHigh", _fixed(_get(stats_temporal, "splits.scene_disjoint.offline_success_rate.ci_high"), 3, "temporal held-out success CI high")),
        ("ExpTemporalSuccessDifference", _fixed(_get(stats_temporal, "protocol_difference.success_drop_random_minus_heldout.estimate"), 3, "temporal success difference")),
        ("ExpTemporalSuccessDifferenceCiLow", _fixed(_get(stats_temporal, "protocol_difference.success_drop_random_minus_heldout.ci_low"), 3, "temporal difference CI low")),
        ("ExpTemporalSuccessDifferenceCiHigh", _fixed(_get(stats_temporal, "protocol_difference.success_drop_random_minus_heldout.ci_high"), 3, "temporal difference CI high")),
        ("ExpPolicySplitPackageCount", _tex_int(_get(temporal, "source.package_count"), "policy split package count")),
        ("ExpPolicySplitFrameCount", _tex_int(_get(temporal, "source.total_output_frames"), "policy split frame count")),
        ("ExpPolicyCompatibilityLeRobotVersion", str(_get(policy_compatibility, "lerobot_policy_requirements_version"))),
        ("ExpPolicyCompatibilityProbeCount", _tex_int(policy_probe_count, "policy compatibility probe count")),
        ("ExpPolicyCompatibilityTrainingStepCount", _tex_int(policy_training_step_count, "policy compatibility training-step count")),
        ("ExpPolicyCompatibilityExpectedBlockerCount", _tex_int(policy_expected_blocker_count, "policy compatibility expected-blocker count")),
        ("ExpReplaySampleCount", _tex_int(_get(replay, "sample_count"), "replay sample count")),
        ("ExpReplayTraceCount", _tex_int(replay_trace_count, "replay trace count")),
        ("ExpReplayTraceNoun", "trajectory" if replay_trace_count == 1 else "trajectories"),
        ("ExpReplayTestedSimulatorCount", _tex_int(tested_replay_simulator_count, "tested replay simulator count")),
        ("ExpReplayJointCount", _tex_int(_get(replay, "joint_count"), "replay joint count")),
        ("ExpReplayRateHz", _tex_int(round(_as_number(_get(replay, "sample_rate_hz"), "replay rate")), "replay rate")),
        ("ExpReplayCalibrationSamples", _tex_int(_get(replay, "calibration_samples"), "replay calibration samples")),
        ("ExpReplayValidationSamples", _tex_int(_get(replay, "validation_samples"), "replay validation samples")),
        ("ExpReplayDelayFrames", _tex_int(_get(alignment, "inferred_effective_delay_frames"), "replay delay frames")),
        ("ExpReplayDelayMilliseconds", _tex_int(round(1000 * _as_number(_get(alignment, "inferred_effective_delay_s"), "replay delay seconds")), "replay delay milliseconds")),
        ("ExpTimingCalibrationEpisodes", _tex_int(_get(timing_calibration, "episode_count"), "timing calibration episodes")),
        ("ExpTimingHeldoutEpisodes", _tex_int(_get(timing_evaluation, "episode_count"), "timing held-out episodes")),
        ("ExpTimingTaskCount", _tex_int(_get(timing_evaluation, "task_count"), "timing held-out task count")),
        ("ExpTimingSourceEpisodeOverlap", _tex_int(_get(multitrajectory_timing, "source.source_episode_overlap_count"), "timing source episode overlap")),
        ("ExpTimingTimestampColumnCount", _tex_int(len(_get(multitrajectory_timing, "source.timestamp_columns")), "timing timestamp column count")),
        ("ExpTimingRobotTypeCount", _tex_int(_get(multitrajectory_timing, "source.robot_type_count"), "timing robot type count")),
        ("ExpTimingControllerConfigurationCount", _tex_int(_get(multitrajectory_timing, "source.controller_configuration_count"), "timing controller configuration count")),
        ("ExpTimingDelayFrames", _tex_int(_get(timing_calibration, "selected_delay_frames"), "timing selected delay frames")),
        ("ExpTimingDelayMilliseconds", _tex_int(round(1000 * _as_number(_get(timing_calibration, "selected_delay_s"), "timing selected delay seconds")), "timing selected delay milliseconds")),
        ("ExpTimingZeroRmse", _fixed(_get(timing_evaluation, "zero_delay.pooled_joint_rmse"), 3, "timing zero-delay RMSE")),
        ("ExpTimingFrozenRmse", _fixed(_get(timing_evaluation, "frozen_frame_delay.pooled_joint_rmse"), 3, "timing frozen-delay RMSE")),
        ("ExpTimingImprovement", _fixed(_get(timing_improvement, "estimate"), 3, "timing paired episode improvement")),
        ("ExpTimingImprovementCiLow", _fixed(_get(timing_improvement, "ci_low"), 3, "timing paired episode improvement CI low")),
        ("ExpTimingImprovementCiHigh", _fixed(_get(timing_improvement, "ci_high"), 3, "timing paired episode improvement CI high")),
        ("ExpTimingImprovedEpisodeCount", _tex_int(_get(timing_improvement, "improved_episode_count"), "timing improved episode count")),
        ("ExpTimingTimestampZohRmse", _fixed(_get(timing_evaluation, "scheduler_sensitivity.timestamp_zero_order_hold.pooled_joint_rmse"), 3, "timing timestamp ZOH RMSE")),
        ("ExpTimingTimestampLinearRmse", _fixed(_get(timing_evaluation, "scheduler_sensitivity.timestamp_linear.pooled_joint_rmse"), 3, "timing timestamp linear RMSE")),
        ("ExpAlignmentNaiveRmse", _fixed(_get(alignment, "validation_naive_rmse_deg"), 3, "alignment naive RMSE")),
        ("ExpAlignmentTimedRmse", _fixed(_get(alignment, "validation_timestamp_aware_rmse_deg"), 3, "alignment timed RMSE")),
        ("ExpAlignmentImprovement", _fixed(_get(alignment, "validation_improvement_over_naive"), 2, "alignment improvement")),
        ("ExpAlignmentNaiveRmsePlot", _fixed(_get(alignment, "validation_naive_rmse_deg"), 2, "alignment naive RMSE plot")),
        ("ExpAlignmentTimedRmsePlot", _fixed(_get(alignment, "validation_timestamp_aware_rmse_deg"), 2, "alignment timed RMSE plot")),
        ("ExpMujocoNaiveRmse", _fixed(_get(mujoco, "naive_command_time.joint_rmse_deg"), 3, "MuJoCo naive RMSE")),
        ("ExpMujocoTimedRmse", _fixed(_get(mujoco, "timestamp_aware.joint_rmse_deg"), 3, "MuJoCo timed RMSE")),
        ("ExpMujocoImprovement", _fixed(_get(mujoco, "rmse_improvement_over_naive"), 2, "MuJoCo improvement")),
        ("ExpMujocoNaiveRmsePrecise", _fixed(_get(mujoco, "naive_command_time.joint_rmse_deg"), 7, "MuJoCo precise RMSE")),
        ("ExpGenesisNaiveRmse", _fixed(_get(genesis, "naive_command_time.joint_rmse_deg"), 3, "Genesis naive RMSE")),
        ("ExpGenesisTimedRmse", _fixed(_get(genesis, "timestamp_aware.joint_rmse_deg"), 3, "Genesis timed RMSE")),
        ("ExpGenesisImprovement", _fixed(_get(genesis, "rmse_improvement_over_naive"), 2, "Genesis improvement")),
        ("ExpGenesisNaiveRmsePrecise", _fixed(_get(genesis, "naive_command_time.joint_rmse_deg"), 7, "Genesis precise RMSE")),
        ("ExpAdapterConformanceCaseCount", _tex_int(_get(results, "replay_adapter_conformance.aggregate.case_count"), "adapter conformance case count")),
        ("ExpAdapterConformanceMaxError", _fixed(max(_as_number(_get(case, "contract_aware.rmse"), "adapter conformance RMSE") for case in _get(results, "replay_adapter_conformance.cases")), 1, "adapter conformance max error")),
        ("ExpDriftAblationCount", _tex_int(_get(results, "realtosim_contract_drift.aggregate.ablation_count"), "drift ablation count")),
        ("ExpDriftSimulationSuccessCount", _tex_int(_get(results, "realtosim_contract_drift.aggregate.drifted_sim_successes"), "drift simulation successes")),
        ("ExpDriftDeploymentSuccessCount", _tex_int(_get(results, "realtosim_contract_drift.aggregate.drifted_deployment_successes"), "drift deployment successes")),
        ("ExpDriftCorrectedSuccessCount", _tex_int(_get(results, "realtosim_contract_drift.aggregate.worldepisode_deployment_successes"), "corrected deployment successes")),
        ("ExpFaultCaseCount", _tex_int(_get(results, "rq2_fault_detection.n_cases"), "fault case count")),
        ("ExpFaultTruePositiveCount", _tex_int(_get(results, "rq2_fault_detection.true_positive_requirements"), "fault true positive count")),
        ("ExpFaultRecall", _fixed(_get(results, "rq2_fault_detection.recall"), 3, "fault recall")),
        ("ExpFaultPrecision", _fixed(_get(results, "rq2_fault_detection.precision"), 3, "fault precision")),
        ("ExpIndependentFixtureCount", _tex_int(_get(results, "independent_fixture_check.n_cases"), "independent fixture count")),
        ("ExpJointSampleCount", _tex_int(_get(results, "lerobot_public_sample.joint_count"), "joint sample count")),
        ("ExpJointSampleMaxDegrees", _fixed(_get(results, "lerobot_public_sample.max_abs_joint_deg"), 3, "joint sample max degrees")),
        ("ExpJointSampleMaxRadians", _fixed(_get(results, "lerobot_public_sample.max_abs_joint_rad"), 3, "joint sample max radians")),
        ("ExpNaturalFindingCount", _tex_int(_get(results, "natural_failure_corpus.case_count"), "natural finding count")),
        ("ExpNaturalDatasetCount", _tex_int(_get(results, "natural_failure_corpus.dataset_count"), "natural dataset count")),
        ("ExpNaturalActiveDatasetCount", _tex_int(_get(results, "natural_failure_corpus.active_dataset_report_count"), "active natural dataset count")),
        ("ExpNaturalSourceLevelDatasetCount", _tex_int(_get(results, "natural_failure_corpus.source_level_only_report_count"), "source-level natural dataset count")),
        ("ExpPreflightCaseCount", _tex_int(len(_get(results, "preflight_validator.cases")), "preflight case count")),
        ("ExpCleanroomRequirementCount", _tex_int(_get(results, "cleanroom_reader.aggregate.expected_requirement_count"), "clean-room requirement count")),
        ("ExpCleanroomFixtureCount", _tex_int(_get(results, "cleanroom_reader.aggregate.case_count"), "clean-room fixture count")),
        ("ExpRoundtripDatasetCount", _tex_int(len(roundtrip_reports), "round-trip dataset count")),
        ("ExpRoundtripBatchEpisodes", _tex_int(_get(roundtrip, "batch_roundtrip.episode_count"), "round-trip batch episodes")),
        ("ExpRoundtripEpisodeCount", _tex_int(roundtrip_episode_count, "round-trip episode count")),
        ("ExpRoundtripActionRows", _tex_int(roundtrip_action_rows, "round-trip action rows")),
        ("ExpRoundtripStateRows", _tex_int(roundtrip_state_rows, "round-trip state rows")),
        ("ExpRoundtripMaxError", _fixed(_maximum_roundtrip_error(results), 1, "round-trip maximum error")),
        ("ExpConversionScaleDatasetCount", _tex_int(_get(conversion_scale, "aggregate.dataset_count"), "conversion-scale dataset count")),
        ("ExpConversionScaleMultiCameraDatasetCount", _tex_int(_get(conversion_scale, "aggregate.multi_camera_dataset_count"), "conversion-scale multi-camera dataset count")),
        ("ExpConversionScaleEpisodeCount", _tex_int(_get(conversion_scale, "aggregate.episode_count"), "conversion-scale episode count")),
        ("ExpConversionScaleRowCount", _tex_int(conversion_scale_action_rows, "conversion-scale paired row count")),
        ("ExpConversionScaleSourceInputMiB", _fixed(_as_number(_get(conversion_scale, "aggregate.source_input_bytes"), "conversion-scale source input bytes") / (1024**2), 1, "conversion-scale source input MiB")),
        ("ExpConversionScaleTemporaryOutputMiB", _fixed(_as_number(_get(conversion_scale, "aggregate.temporary_output_bytes"), "conversion-scale temporary output bytes") / (1024**2), 1, "conversion-scale temporary output MiB")),
        ("ExpConversionScaleMaxError", _fixed(_get(conversion_scale, "aggregate.maximum_numerical_error"), 1, "conversion-scale maximum error")),
        ("ExpConversionScaleSemanticLossFieldCount", _tex_int(_get(conversion_scale, "aggregate.semantic_loss_field_count"), "conversion-scale semantic loss field count")),
        ("ExpConversionScaleSemanticLossOccurrenceCount", _tex_int(_get(conversion_scale, "aggregate.semantic_loss_occurrence_count"), "conversion-scale semantic loss occurrence count")),
        ("ExpBindingCount", _tex_int(_get(bindings, "projection_profile.binding_model_count"), "binding count")),
        ("ExpBindingFieldCount", _tex_int(_get(bindings, "projection_profile.field_count"), "binding field count")),
        ("ExpBindingNativeMin", _fixed(min(native_retentions), 3, "minimum native retention")),
        ("ExpBindingNativeMax", _fixed(max(native_retentions), 3, "maximum native retention")),
        ("ExpBindingReferenceNative", _fixed(_get(_binding(results, "worldepisode-reference"), "native_retention"), 3, "reference native retention")),
        ("ExpBindingLerobotNative", _fixed(_get(_binding(results, "lerobot-v3-native"), "native_retention"), 3, "LeRobot native retention")),
        ("ExpBindingLerobotSidecar", _fixed(_get(_binding(results, "lerobot-v3-native"), "with_worldepisode_sidecar"), 3, "LeRobot sidecar retention")),
        ("ExpBindingRerunNative", _fixed(_get(_binding(results, "rerun-rrd"), "native_retention"), 3, "Rerun native retention")),
        ("ExpBindingRerunSidecar", _fixed(_get(_binding(results, "rerun-rrd"), "with_worldepisode_sidecar"), 3, "Rerun sidecar retention")),
        ("ExpBindingNcoreNative", _fixed(_get(_binding(results, "ncore"), "native_retention"), 3, "NCore native retention")),
        ("ExpBindingNcoreSidecar", _fixed(_get(_binding(results, "ncore"), "with_worldepisode_sidecar"), 3, "NCore sidecar retention")),
        ("ExpBindingMcapNative", _fixed(_get(_binding(results, "mcap-ros2"), "native_retention"), 3, "MCAP native retention")),
        ("ExpBindingMcapSidecar", _fixed(_get(_binding(results, "mcap-ros2"), "with_worldepisode_sidecar"), 3, "MCAP sidecar retention")),
        ("ExpBindingOpenusdNative", _fixed(_get(_binding(results, "openusd-simready"), "native_retention"), 3, "OpenUSD native retention")),
        ("ExpBindingOpenusdSidecar", _fixed(_get(_binding(results, "openusd-simready"), "with_worldepisode_sidecar"), 3, "OpenUSD sidecar retention")),
        ("ExpBindingGltfNative", _fixed(_get(_binding(results, "gltf-gaussian-asset"), "native_retention"), 3, "glTF native retention")),
        ("ExpBindingGltfSidecar", _fixed(_get(_binding(results, "gltf-gaussian-asset"), "with_worldepisode_sidecar"), 3, "glTF sidecar retention")),
        ("ExpBenchmarkCount", _tex_int(_get(results, "benchmark_callout_audit.aggregate.benchmark_count"), "benchmark count")),
        ("ExpBenchmarkHighSeverityCount", _tex_int(_get(results, "benchmark_callout_audit.aggregate.benchmarks_with_high_severity_open_controls"), "high-severity benchmark count")),
        ("ExpDroidRerunEpisodes", _tex_int(_get(droid_rerun, "benchmark_subset.episode_count"), "DROID rerun episode count")),
        ("ExpDroidRerunFrames", _tex_int(_get(droid_rerun, "benchmark_subset.frame_count"), "DROID rerun frame count")),
        ("ExpDroidCorrectedScore", _fixed(_get(droid_rerun, "evaluation.corrected_score"), 3, "DROID corrected score")),
        ("ExpDroidRandomScore", _fixed(_get(droid_rerun, "evaluation.baseline_score"), 3, "DROID random score")),
        ("ExpBenchmarkInflationClaimCount", _tex_int(_get(benchmark_gate, "aggregate.measured_inflation_claims"), "benchmark inflation claim count")),
        ("ExpScaleNamespaceCount", _tex_int(_get(scale_audit, "namespace_count"), "scale namespace count")),
        ("ExpScaleResolverCount", _tex_int(_get(scale_audit, "resolver_count"), "scale resolver count")),
        ("ExpScaleRegistryCount", _tex_int(_get(scale_audit, "registry_count"), "scale registry count")),
        ("ExpScaleShardCount", _tex_int(_get(scale_audit, "shard_count"), "scale shard count")),
        ("ExpScaleIndexCount", _tex_int(_get(scale_audit, "index_count"), "scale index count")),
        ("ExpScaleVersionCount", _tex_int(_get(scale_audit, "version_count"), "scale version count")),
        ("ExpScaleAssetCount", _tex_int(_get(scale_audit, "asset_descriptor_count"), "scale asset count")),
        ("ExpScaleTraceShardCount", _tex_int(_get(generated_catalog, "trace_shard_count"), "scale trace shard count")),
        ("ExpScaleEpisodeCapacity", _tex_int(_get(generated_catalog, "described_episode_capacity"), "scale episode capacity")),
        ("ExpScaleQueryCount", _tex_int(_get(scale_performance, "partition_pruning.query_count"), "scale query count")),
        ("ExpAvClockOffsetMilliseconds", _tex_int(round(1000 * _as_number(_get(av_pilot, "drifted_behavior.undeclared_clock_offset_s"), "AV clock offset")), "AV clock offset milliseconds")),
        ("ExpAvSpeedMetersPerSecond", _fixed(_get(av_pilot, "drifted_behavior.ego_speed_mps"), 0, "AV speed")),
        ("ExpAvFusionErrorMeters", _fixed(_get(av_pilot, "drifted_behavior.naive_fusion_error_m"), 2, "AV fusion error")),
        ("ExpAvToleranceMeters", _fixed(_get(av_pilot, "drifted_behavior.tolerance_m"), 2, "AV tolerance")),
        ("ExpAvCorrectedErrorMeters", _fixed(_get(av_pilot, "uss_contract.corrected_fusion_error_m"), 1, "AV corrected error")),
        ("ExpNonrobotPilotCount", _tex_int(_get(results, "uss_state_drift_pilots.aggregate.case_count"), "non-robotics pilot count")),
    ]

    policy_ready = bool(_get(results, "lerobot_policy_gate.pass"))
    benchmark_ready = bool(_get(benchmark_gate, "aggregate.ready_for_inflation_claim"))
    maintainer_ready = bool(_get(results, "natural_failure_corpus.maintainer_feedback_satisfied"))
    open_values = [
        ("ExpSceneOnlyLeakageResult", policy_ready),
        ("ExpActDiffusionResult", policy_ready),
        ("ExpRolloutImpactResult", policy_ready),
        ("ExpBenchmarkInflationResult", benchmark_ready),
        ("ExpMaintainerValidationResult", maintainer_ready),
    ]

    lines = [
        "% Generated by tools/paper_experiment_values.py. Do not edit manually.",
        f"% Source: {RESULTS_PATH.relative_to(ROOT)} sha256={_source_digest(RESULTS_PATH)}",
        f"% Source: {STATISTICS_PATH.relative_to(ROOT)} sha256={_source_digest(STATISTICS_PATH)}",
        f"% Source: {DROID_RERUN_PATH.relative_to(ROOT)} sha256={_source_digest(DROID_RERUN_PATH)}",
        f"% Source: {CONVERSION_SCALE_PATH.relative_to(ROOT)} sha256={_source_digest(CONVERSION_SCALE_PATH)}",
        f"% Source: {MULTITRAJECTORY_TIMING_PATH.relative_to(ROOT)} sha256={_source_digest(MULTITRAJECTORY_TIMING_PATH)}",
        f"% Source: {EXPERIMENT_MANIFEST_PATH.relative_to(ROOT)} sha256={_source_digest(EXPERIMENT_MANIFEST_PATH)}",
        f"% Source: {ASSET_AUDIT_PATH.relative_to(ROOT)} sha256={_source_digest(ASSET_AUDIT_PATH)}",
        r"\providecommand{\PaperNotDefinedYet}{\textit{Not defined yet}}",
    ]
    lines.extend(_macro(name, value) for name, value in values)
    lines.extend(
        _macro(name, r"\PaperNotDefinedYet" if not ready else r"\textit{Defined in current reports}")
        for name, ready in open_values
    )
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if the committed TeX file differs from the experiment reports",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_PATH,
        help="generated TeX output path",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        rendered = generate_tex(
            _read_json(RESULTS_PATH),
            _read_json(STATISTICS_PATH),
            _read_json(DROID_RERUN_PATH),
            _read_json(CONVERSION_SCALE_PATH),
            _read_json(MULTITRAJECTORY_TIMING_PATH),
            _read_json(EXPERIMENT_MANIFEST_PATH),
            _read_json(ASSET_AUDIT_PATH),
        )
    except PaperValueError as exc:
        print(f"paper experiment values: ERROR: {exc}", file=sys.stderr)
        return 1

    output = args.output if args.output.is_absolute() else ROOT / args.output
    if args.check:
        try:
            current = output.read_text(encoding="utf-8")
        except FileNotFoundError:
            print(f"paper experiment values: ERROR: generated file is missing: {output}", file=sys.stderr)
            return 1
        if current != rendered:
            print(
                "paper experiment values: ERROR: generated file is stale; "
                "run `python3 tools/paper_experiment_values.py`",
                file=sys.stderr,
            )
            return 1
        print(f"paper experiment values: current ({output.relative_to(ROOT)})")
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(f"paper experiment values: wrote {output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
