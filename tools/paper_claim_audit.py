#!/usr/bin/env python3
"""Audit paper claims against committed evidence artifacts.

This is a fail-closed guard against the paper drifting back into proposal language. It checks that
the highest-risk quantitative and boundary claims in the LaTeX source are present and match
`docs/experiments/results.json` or the open-gate artifacts. It does not prove every sentence in the
paper, but it makes the main results auditable.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RESULTS_JSON = ROOT / "docs" / "experiments" / "results.json"
OPEN_GATES_JSON = ROOT / "docs" / "experiments" / "open_reproduction_gates" / "open_reproduction_gates.json"
STATISTICS_JSON = ROOT / "docs" / "experiments" / "statistical_analysis" / "statistical_report.json"
CONVERSION_SCALE_JSON = (
    ROOT / "docs" / "experiments" / "lerobot_conversion_scale" / "scale_report.json"
)
MULTITRAJECTORY_TIMING_JSON = (
    ROOT
    / "docs"
    / "experiments"
    / "lerobot_multitrajectory_timing"
    / "timing_report.json"
)
PAPER_VALUES_TEX = ROOT / "paper" / "arxiv" / "generated" / "experiment_values.tex"
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "experiments" / "paper_claim_audit"
SCHEMA = "worldepisode_paper_claim_audit_v1"
AUDIT_DATE = "2026-07-13"


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


def nested(payload: dict[str, Any], path: tuple[str, ...], default: Any = None) -> Any:
    cursor: Any = payload
    for key in path:
        if not isinstance(cursor, dict) or key not in cursor:
            return default
        cursor = cursor[key]
    return cursor


def paper_text() -> str:
    paths = [
        ROOT / "paper" / "arxiv" / "main.tex",
        ROOT / "paper" / "arxiv" / "checklist.tex",
        PAPER_VALUES_TEX,
    ]
    paths.extend(sorted((ROOT / "paper" / "arxiv" / "sections").glob("*.tex")))
    raw = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    return " ".join(raw.split())


def fmt3(value: float) -> str:
    return f"{value:.3f}"


def fmt2(value: float) -> str:
    return f"{value:.2f}"


def tex_int(value: int) -> str:
    return f"{value:,}".replace(",", "{,}")


def plain_int(value: int) -> str:
    return f"{value:,}"


def claim_result(
    *,
    claim_id: str,
    claim: str,
    evidence_artifacts: list[str],
    paper_patterns: list[str],
    evidence_passed: bool,
    evidence: dict[str, Any],
    text: str,
    boundary: str = "",
) -> dict[str, Any]:
    missing = [pattern for pattern in paper_patterns if pattern not in text]
    return {
        "claim_id": claim_id,
        "claim": claim,
        "passed": evidence_passed and not missing,
        "paper_patterns": paper_patterns,
        "missing_paper_patterns": missing,
        "evidence_passed": evidence_passed,
        "evidence": evidence,
        "evidence_artifacts": evidence_artifacts,
        "boundary": boundary,
    }


def build_claims(
    results: dict[str, Any],
    open_gates: dict[str, Any],
    statistics: dict[str, Any],
    conversion_scale: dict[str, Any],
    multitrajectory_timing: dict[str, Any],
    text: str,
) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []

    leakage = nested(results, ("lerobot_scene_leakage", "summary"), {})
    claims.append(
        claim_result(
            claim_id="CLAIM.LEAKAGE.001",
            claim=(
                "ArmnetBench random split overlaps task--scene proxy lineages; the task-confounded "
                "holdout changes offline imitation metrics."
            ),
            evidence_artifacts=[
                "docs/experiments/lerobot_scene_leakage/leakage_report.json",
                "docs/experiments/lerobot_scene_leakage/split_manifest.json",
                "docs/experiments/statistical_analysis/statistical_report.json",
            ],
            paper_patterns=[
                "\\ExpMlpRandomNrmse",
                "\\ExpMlpHeldoutNrmse",
                "\\ExpMlpNrmseDifference",
                "task--scene proxy",
                "also a task-disjoint shift",
                "does not establish scene-only leakage",
                "crossed seed--episode bootstrap CI",
            ],
            evidence_passed=(
                leakage.get("random_leakage_rate") == 1.0
                and leakage.get("scene_disjoint_leakage_rate") == 0.0
                and float(leakage.get("scene_disjoint_episode_nrmse_mean", 0))
                > float(leakage.get("random_episode_nrmse_mean", 0))
                and statistics.get("profile") == "worldepisode-statistical-analysis-0.2"
                and nested(
                    results,
                    (
                        "lerobot_scene_leakage",
                        "splits",
                        "random_episode",
                        "bc",
                        "policy",
                        "seed_count",
                    ),
                    0,
                )
                >= 5
                and nested(
                    statistics,
                    ("models", "torch_mlp_bc", "protocol_difference", "nrmse_increase_heldout_minus_random", "ci_low"),
                    0,
                )
                > 0
            ),
            evidence={
                "random_leakage_rate": leakage.get("random_leakage_rate"),
                "scene_disjoint_leakage_rate": leakage.get("scene_disjoint_leakage_rate"),
                "random_episode_nrmse_mean": leakage.get("random_episode_nrmse_mean"),
                "scene_disjoint_episode_nrmse_mean": leakage.get("scene_disjoint_episode_nrmse_mean"),
                "nrmse_difference_ci_low": nested(
                    statistics,
                    ("models", "torch_mlp_bc", "protocol_difference", "nrmse_increase_heldout_minus_random", "ci_low"),
                ),
                "optimization_seed_count": nested(
                    results,
                    (
                        "lerobot_scene_leakage",
                        "splits",
                        "random_episode",
                        "bc",
                        "policy",
                        "seed_count",
                    ),
                ),
            },
            text=text,
            boundary=(
                "Task--scene proxy shift confounded with task identity; offline action imitation "
                "only, not scene-only leakage, ACT/Diffusion, or rollout success."
            ),
        )
    )

    policy_gate = results.get("lerobot_policy_gate", {})
    vision_smoke = policy_gate.get("policy_vision_smoke", {})
    video_materialization = policy_gate.get("video_materialization", {})
    claims.append(
        claim_result(
            claim_id="CLAIM.POLICY_VISION_SMOKE.001",
            claim=(
                "Pinned LeRobot ACT and Diffusion paths decode the materialized source front camera "
                "and complete the CUDA smoke optimization step."
            ),
            evidence_artifacts=[
                "docs/experiments/lerobot_policy_gate/front_camera_asset_manifest.json",
                "docs/experiments/lerobot_policy_gate/front_camera_materialization_report.json",
                "docs/experiments/lerobot_policy_gate/policy_vision_smoke_report.json",
                "docs/experiments/run_logs/lerobot_policy_vision_smoke_dgx_spark.log",
            ],
            paper_patterns=[
                "\\ExpPolicyVisionAssetCount{} source front-camera files",
                "\\ExpPolicyVisionTrainingStepCount{}/\\ExpPolicyVisionProbeCount{} pinned",
                "closes input compatibility only",
                "no trained checkpoint",
            ],
            evidence_passed=(
                vision_smoke.get("status") == "training_step_smoke_passed"
                and vision_smoke.get("pass") is True
                and vision_smoke.get("all_policy_probes_completed_training_step") is True
                and video_materialization.get("pass") is True
                and int(video_materialization.get("verified_asset_count", 0)) > 0
                and policy_gate.get("pass") is False
            ),
            evidence={
                "vision_smoke_status": vision_smoke.get("status"),
                "training_step_count": sum(
                    bool(probe.get("training_step_completed"))
                    for probe in vision_smoke.get("policy_probes", [])
                ),
                "probe_count": len(vision_smoke.get("policy_probes", [])),
                "verified_asset_count": video_materialization.get("verified_asset_count"),
                "policy_gate_pass": policy_gate.get("pass"),
            },
            text=text,
            boundary=(
                "Input compatibility only; no trained checkpoint, held-out policy metric, "
                "simulator rollout, or physical rollout."
            ),
        )
    )

    timing_calibration = multitrajectory_timing.get("calibration", {})
    timing_evaluation = multitrajectory_timing.get("evaluation", {})
    timing_improvement = timing_evaluation.get("paired_episode_improvement", {})
    claims.append(
        claim_result(
            claim_id="CLAIM.TIMING.001",
            claim=(
                "A lag frozen on calibration trajectories improves held-out SO-101 action/state "
                "telemetry alignment across multiple tasks."
            ),
            evidence_artifacts=[
                "docs/experiments/lerobot_multitrajectory_timing/timing_report.json",
                "docs/experiments/lerobot_multitrajectory_timing/README.md",
                "docs/experiments/run_logs/lerobot_multitrajectory_timing_dgx_spark.log",
            ],
            paper_patterns=[
                "\\ExpTimingCalibrationEpisodes{} calibration trajectories",
                "\\ExpTimingHeldoutEpisodes{} source-episode-disjoint trajectories",
                "\\ExpTimingTaskCount{} tasks",
                "\\ExpTimingImprovementCiLow",
                "source position units",
                "no motor-effective timestamps",
                "\\ExpTimingControllerConfigurationCount{} controller configuration",
            ],
            evidence_passed=(
                multitrajectory_timing.get("schema")
                == "worldepisode_lerobot_multitrajectory_timing_v1"
                and nested(
                    multitrajectory_timing,
                    ("validation", "passed"),
                )
                is True
                and nested(
                    multitrajectory_timing,
                    ("source", "source_episode_overlap_count"),
                )
                == 0
                and int(timing_calibration.get("episode_count", 0)) >= 20
                and int(timing_evaluation.get("episode_count", 0)) >= 20
                and int(timing_evaluation.get("task_count", 0)) >= 2
                and float(timing_improvement.get("ci_low", 0)) > 0
                and timing_improvement.get("improved_episode_count")
                == timing_evaluation.get("episode_count")
                and nested(
                    multitrajectory_timing,
                    ("source", "effective_motor_timestamp_available"),
                )
                is False
                and nested(
                    multitrajectory_timing,
                    ("acceptance", "action_002_fully_satisfied"),
                )
                is False
            ),
            evidence={
                "calibration_episode_count": timing_calibration.get("episode_count"),
                "evaluation_episode_count": timing_evaluation.get("episode_count"),
                "task_count": timing_evaluation.get("task_count"),
                "selected_delay_frames": timing_calibration.get("selected_delay_frames"),
                "improvement_ci_low": timing_improvement.get("ci_low"),
                "improvement_ci_high": timing_improvement.get("ci_high"),
                "improved_episode_count": timing_improvement.get(
                    "improved_episode_count"
                ),
                "effective_motor_timestamp_available": nested(
                    multitrajectory_timing,
                    ("source", "effective_motor_timestamp_available"),
                ),
            },
            text=text,
            boundary=(
                "Action/state telemetry-lag proxy on one SO-101 dataset; no independently "
                "instrumented motor latency or second robot/controller."
            ),
        )
    )

    replay = results.get("rq3_replay", {})
    alignment = replay.get("alignment", {})
    mujoco = nested(replay, ("simulators", "mujoco"), {})
    genesis = nested(replay, ("simulators", "genesis"), {})
    claims.append(
        claim_result(
            claim_id="CLAIM.REPLAY.001",
            claim="Timestamp-aware LeRobot replay reduces joint RMSE in tested MuJoCo and Genesis adapters.",
            evidence_artifacts=["docs/experiments/lerobot_control_replay/control_replay_report.json"],
            paper_patterns=[
                "\\ExpReplayDelayFrames{} frames",
                "\\ExpReplayDelayMilliseconds{} ms",
                "\\ExpAlignmentNaiveRmse",
                "\\ExpAlignmentTimedRmse",
                "\\ExpMujocoNaiveRmse",
                "\\ExpMujocoTimedRmse",
                "Genesis same-trace replay",
                "\\ExpGenesisNaiveRmse",
                "\\ExpGenesisTimedRmse",
                "Isaac adapter is emitted as a ready mapping",
                "not tested in this environment",
            ],
            evidence_passed=(
                int(alignment.get("inferred_effective_delay_frames", 0)) > 0
                and float(alignment.get("inferred_effective_delay_s", 0)) > 0
                and float(alignment.get("validation_timestamp_aware_rmse_deg", float("inf")))
                < float(alignment.get("validation_naive_rmse_deg", 0))
                and mujoco.get("tested") is True
                and float(nested(mujoco, ("timestamp_aware", "joint_rmse_deg"), float("inf")))
                < float(nested(mujoco, ("naive_command_time", "joint_rmse_deg"), 0))
                and genesis.get("tested") is True
                and float(nested(genesis, ("timestamp_aware", "joint_rmse_deg"), float("inf")))
                < float(nested(genesis, ("naive_command_time", "joint_rmse_deg"), 0))
                and nested(replay, ("simulators", "isaac", "tested")) is False
            ),
            evidence={
                "delay_frames": alignment.get("inferred_effective_delay_frames"),
                "delay_s": alignment.get("inferred_effective_delay_s"),
                "validation_naive_rmse_deg": alignment.get("validation_naive_rmse_deg"),
                "validation_timestamp_aware_rmse_deg": alignment.get("validation_timestamp_aware_rmse_deg"),
                "mujoco_naive_rmse_deg": nested(mujoco, ("naive_command_time", "joint_rmse_deg")),
                "mujoco_timestamp_aware_rmse_deg": nested(mujoco, ("timestamp_aware", "joint_rmse_deg")),
                "genesis_naive_rmse_deg": nested(genesis, ("naive_command_time", "joint_rmse_deg")),
                "genesis_timestamp_aware_rmse_deg": nested(genesis, ("timestamp_aware", "joint_rmse_deg")),
                "isaac_tested": nested(replay, ("simulators", "isaac", "tested")),
            },
            text=text,
            boundary=(
                "One LeRobot trace with minimal MuJoCo and Genesis position-servo adapters; "
                "Isaac is not claimed tested and contact-rich rollout remains open."
            ),
        )
    )

    scale_aggregate = conversion_scale.get("aggregate", {})
    scale_datasets = conversion_scale.get("datasets", [])
    scale_max_error = scale_aggregate.get("maximum_numerical_error")
    claims.append(
        claim_result(
            claim_id="CLAIM.ROUNDTRIP.001",
            claim=(
                "Complete pinned source shards from multiple public LeRobotDatasets round-trip "
                "exactly through WorldEpisode."
            ),
            evidence_artifacts=[
                "docs/experiments/lerobot_conversion_scale/scale_report.json",
                "docs/experiments/experiment_manifest/experiment_manifest.json",
                "docs/experiments/run_logs/lerobot_conversion_scale_dgx_spark.log",
            ],
            paper_patterns=[
                "complete-shard round-trip audit",
                "\\ExpConversionScaleEpisodeCount",
                "\\ExpConversionScaleDatasetCount",
                "\\ExpConversionScaleRowCount",
                "maximum absolute error \\ExpConversionScaleMaxError",
                "Source video payloads are neither downloaded nor converted",
                "complete-selected-shard measurement, not full-corpus throughput",
                "conversion loss rather than guessed",
            ],
            evidence_passed=(
                conversion_scale.get("schema")
                == "worldepisode_lerobot_conversion_scale_v1"
                and nested(conversion_scale, ("validation", "passed")) is True
                and int(scale_aggregate.get("dataset_count", 0)) >= 3
                and int(scale_aggregate.get("multi_camera_dataset_count", 0)) >= 1
                and int(scale_aggregate.get("episode_count", 0)) > 10
                and int(scale_aggregate.get("action_row_count", 0)) > 0
                and scale_aggregate.get("action_row_count")
                == scale_aggregate.get("state_row_count")
                and float(scale_max_error if scale_max_error is not None else float("inf"))
                == 0.0
                and len(scale_datasets) == int(scale_aggregate.get("dataset_count", 0))
                and all(
                    nested(dataset, ("source_subset", "complete_source_file")) is True
                    and nested(
                        dataset, ("modality", "source_video_payload_downloaded")
                    )
                    is False
                    and nested(dataset, ("conversion", "discarded_fields")) == []
                    and nested(dataset, ("validation", "passed")) is True
                    for dataset in scale_datasets
                )
            ),
            evidence={
                "dataset_count": scale_aggregate.get("dataset_count"),
                "multi_camera_dataset_count": scale_aggregate.get(
                    "multi_camera_dataset_count"
                ),
                "episode_count": scale_aggregate.get("episode_count"),
                "paired_action_state_rows": scale_aggregate.get("action_row_count"),
                "max_error": scale_max_error,
                "datasets": [dataset.get("repo_id") for dataset in scale_datasets],
            },
            text=text,
            boundary=(
                "One complete pinned Parquet shard per dataset; not full corpora or source-video "
                "conversion throughput."
            ),
        )
    )

    temporal_policy = results.get("lerobot_temporal_policy_baseline", {})
    temporal_aggregate = temporal_policy.get("aggregate", {})
    claims.append(
        claim_result(
            claim_id="CLAIM.TEMPORAL_POLICY.001",
            claim="Temporal state/action baseline changes under the task--scene proxy holdout.",
            evidence_artifacts=[
                "docs/experiments/lerobot_temporal_policy_baseline/temporal_policy_report.json"
            ],
            paper_patterns=[
                "temporal ridge",
                "\\ExpTemporalRandomNrmse",
                "\\ExpTemporalHeldoutNrmse",
                "\\ExpTemporalNrmseDifference",
                "deterministic ridge policy",
                "task--scene holdout",
                "[\\ExpTemporalNrmseDifferenceCiLow, \\ExpTemporalNrmseDifferenceCiHigh]",
            ],
            evidence_passed=(
                temporal_policy.get("status") == "measured_offline_temporal_baseline"
                and float(temporal_aggregate.get("scene_disjoint_nrmse_mean", 0))
                > float(temporal_aggregate.get("random_episode_nrmse_mean", 0))
                and nested(
                    statistics,
                    ("models", "temporal_ridge", "protocol_difference", "nrmse_increase_heldout_minus_random", "ci_low"),
                    0,
                )
                > 0
            ),
            evidence={
                "random_episode_nrmse_mean": temporal_aggregate.get("random_episode_nrmse_mean"),
                "scene_disjoint_nrmse_mean": temporal_aggregate.get("scene_disjoint_nrmse_mean"),
                "nrmse_difference_ci_low": nested(
                    statistics,
                    ("models", "temporal_ridge", "protocol_difference", "nrmse_increase_heldout_minus_random", "ci_low"),
                ),
                "episode_nrmse_ratio_scene_over_random": temporal_aggregate.get(
                    "episode_nrmse_ratio_scene_over_random"
                ),
            },
            text=text,
            boundary=(
                "Task-confounded offline temporal state/action baseline; not a scene-only, vision-policy, "
                "ACT, Diffusion, or rollout result."
            ),
        )
    )

    bindings = results.get("rq1_binding_retention", {}).get("bindings", [])
    non_reference = [item for item in bindings if item.get("binding") != "worldepisode-reference"]
    min_native = min(float(item.get("native_retention", 0)) for item in non_reference)
    max_native = max(float(item.get("native_retention", 0)) for item in non_reference)
    dataset_log_world_sidecar_ok = all(
        float(item.get("with_worldepisode_sidecar", 0)) == 1.0
        for item in non_reference
        if item.get("binding") != "gltf-gaussian-asset"
    )
    claims.append(
        claim_result(
            claim_id="CLAIM.BINDING.001",
            claim="Pilot bindings inventory native and sidecar retention for a versioned projection.",
            evidence_artifacts=["docs/experiments/bindings"],
            paper_patterns=[
                "\\ExpBindingCount{} pilot bindings",
                "\\ExpBindingNativeMin{} to \\ExpBindingNativeMax",
                "sidecars recover \\ExpBindingLerobotSidecar",
                "not a universal format ranking",
            ],
            evidence_passed=(
                len(bindings) > 1
                and 0.0 <= min_native <= max_native < 1.0
                and dataset_log_world_sidecar_ok
            ),
            evidence={
                "binding_count": len(bindings),
                "native_retention_min": min_native,
                "native_retention_max": max_native,
                "dataset_log_world_sidecar_ok": dataset_log_world_sidecar_ok,
            },
            text=text,
            boundary="Pilot projection score, not a universal storage-format ranking.",
        )
    )

    fault = results.get("rq2_fault_detection", {})
    independent = results.get("independent_fixture_check", {})
    claims.append(
        claim_result(
            claim_id="CLAIM.VALIDATOR.001",
            claim="Validator detects all injected fault classes and independent fixture failures.",
            evidence_artifacts=[
                "docs/experiments/fault_detection/fault_detection_report.json",
                "conformance/fixtures/independent/manifest.json",
            ],
            paper_patterns=[
                "\\ExpFaultTruePositiveCount{} expected requirement failures",
                "\\ExpFaultRecall{} recall",
                "\\ExpFaultPrecision{} precision",
                "\\ExpIndependentFixtureCount{} hand-authored independent fixtures",
            ],
            evidence_passed=(
                int(fault.get("n_cases", 0)) > 0
                and fault.get("false_negative_requirements") == 0
                and fault.get("recall") == 1.0
                and float(fault.get("precision", 0)) > 0
                and int(independent.get("n_cases", 0)) > 0
                and independent.get("recall") == 1.0
            ),
            evidence={
                "fault_case_count": fault.get("n_cases"),
                "fault_recall": fault.get("recall"),
                "fault_precision": fault.get("precision"),
                "independent_case_count": independent.get("n_cases"),
                "independent_recall": independent.get("recall"),
            },
            text=text,
            boundary="Injected and hand-authored fixtures; natural prevalence remains open.",
        )
    )

    natural = results.get("natural_failure_corpus", {})
    claims.append(
        claim_result(
            claim_id="CLAIM.NATURAL.001",
            claim="Pilot natural-source audit records scoped cases across public dataset sources.",
            evidence_artifacts=["docs/experiments/natural_failure_corpus/manifest.json"],
            paper_patterns=[
                "records \\ExpNaturalFindingCount{} source omissions or evaluation risks",
                "\\ExpNaturalActiveDatasetCount{} active LeRobot artifacts",
                "not maintainer-confirmed bugs or prevalence estimates",
            ],
            evidence_passed=(
                int(natural.get("case_count", 0)) > 0
                and int(natural.get("dataset_count", 0)) > 0
                and natural.get("maintainer_feedback_satisfied") is False
            ),
            evidence={
                "case_count": natural.get("case_count"),
                "dataset_count": natural.get("dataset_count"),
                "maintainer_feedback_satisfied": natural.get("maintainer_feedback_satisfied"),
            },
            text=text,
            boundary="Scoped natural-source corpus, not maintainer-confirmed prevalence.",
        )
    )
    claims.append(
        claim_result(
            claim_id="CLAIM.NATURAL_DIAGNOSTICS.001",
            claim="Natural-source audit distinguishes active artifacts from source-level metadata reviews.",
            evidence_artifacts=[
                "docs/experiments/natural_failure_corpus/dataset_diagnostics.json",
                "docs/experiments/natural_failure_corpus/README.md",
            ],
            paper_patterns=[
                "source-level DROID and BridgeData V2 metadata",
                "not maintainer-confirmed bugs or prevalence estimates",
            ],
            evidence_passed=(
                natural.get("dataset_specific_diagnostics_ready") is True
                and natural.get("dataset_report_count") == natural.get("dataset_count")
                and int(natural.get("case_count", 0)) > 0
                and 0 < int(natural.get("source_level_only_report_count", 0))
                < int(natural.get("dataset_count", 0))
                and natural.get("maintainer_feedback_satisfied") is False
            ),
            evidence={
                "dataset_specific_diagnostics_ready": natural.get("dataset_specific_diagnostics_ready"),
                "dataset_report_count": natural.get("dataset_report_count"),
                "dataset_count": natural.get("dataset_count"),
                "case_count": natural.get("case_count"),
                "source_level_only_report_count": natural.get("source_level_only_report_count"),
                "maintainer_feedback_satisfied": natural.get("maintainer_feedback_satisfied"),
            },
            text=text,
            boundary="Dataset-specific diagnostics, not prevalence or maintainer-confirmed bug evidence.",
        )
    )

    state = results.get("uss_state_drift_pilots", {})
    state_agg = state.get("aggregate", {})
    claims.append(
        claim_result(
            claim_id="CLAIM.USS.001",
            claim="Deterministic non-robotics USS pilots demonstrate collision-patch and clock-domain drift.",
            evidence_artifacts=["docs/experiments/uss_state_drift_pilots/state_drift_report.json"],
            paper_patterns=[
                "\\ExpAvClockOffsetMilliseconds{} ms undeclared clock offset",
                "\\ExpAvFusionErrorMeters{} m fusion error",
                "\\ExpAvToleranceMeters{} m tolerance",
                "not production game-engine or AV benchmark results",
            ],
            evidence_passed=(
                int(state_agg.get("case_count", 0)) > 0
                and state_agg.get("local_file_valid_count") == state_agg.get("case_count")
                and state_agg.get("uss_detections") == state_agg.get("case_count")
                and state.get("status") == "deterministic_non_robotics_pilots"
            ),
            evidence={
                "case_count": state_agg.get("case_count"),
                "local_file_valid_count": state_agg.get("local_file_valid_count"),
                "uss_detections": state_agg.get("uss_detections"),
                "status": state.get("status"),
            },
            text=text,
            boundary="Deterministic pilots, not production game or AV dataset results.",
        )
    )

    realtosim = results.get("realtosim_contract_drift", {})
    rt_agg = realtosim.get("aggregate", {})
    claims.append(
        claim_result(
            claim_id="CLAIM.REALTOSIM.001",
            claim="Controlled real-to-sim contract drift ablations fail under drifted contracts and recover with WorldEpisode.",
            evidence_artifacts=["docs/experiments/realtosim_contract_drift/contract_drift_report.json"],
            paper_patterns=[
                "\\ExpDriftSimulationSuccessCount/\\ExpDriftAblationCount{} proxy simulation successes",
                "\\ExpDriftDeploymentSuccessCount/\\ExpDriftAblationCount{} deployment-proxy successes",
                "\\ExpDriftCorrectedSuccessCount/\\ExpDriftAblationCount",
                "mechanism check, not a hardware or RoboSnap rerun",
            ],
            evidence_passed=(
                int(rt_agg.get("ablation_count", 0)) > 0
                and rt_agg.get("drifted_sim_successes") == rt_agg.get("ablation_count")
                and rt_agg.get("drifted_deployment_successes") == 0
                and rt_agg.get("worldepisode_deployment_successes") == rt_agg.get("ablation_count")
                and realtosim.get("status") == "controlled_proxy_not_hardware_rollout"
            ),
            evidence={
                "ablation_count": rt_agg.get("ablation_count"),
                "drifted_sim_successes": rt_agg.get("drifted_sim_successes"),
                "drifted_deployment_successes": rt_agg.get("drifted_deployment_successes"),
                "worldepisode_deployment_successes": rt_agg.get("worldepisode_deployment_successes"),
                "status": realtosim.get("status"),
            },
            text=text,
            boundary="Controlled proxy; not a hardware or RoboSnap/DROID-Sim rerun.",
        )
    )

    scale = results.get("dataset_scale_performance", {})
    generated = scale.get("generated_catalog", {})
    claims.append(
        claim_result(
            claim_id="CLAIM.SCALE.001",
            claim="Generated catalog benchmark describes a large-capacity sharded corpus.",
            evidence_artifacts=["docs/experiments/dataset_scale_performance/performance_report.json"],
            paper_patterns=[
                "\\ExpScaleTraceShardCount",
                "\\ExpScaleEpisodeCapacity",
                "Catalog-side benchmark only",
            ],
            evidence_passed=(
                scale.get("status") == "pass"
                and int(generated.get("trace_shard_count", 0)) > 0
                and int(generated.get("described_episode_capacity", 0))
                >= int(generated.get("trace_shard_count", 0))
                and generated.get("episodes_materialized") == 0
            ),
            evidence={
                "trace_shard_count": generated.get("trace_shard_count"),
                "described_episode_capacity": generated.get("described_episode_capacity"),
                "episodes_materialized": generated.get("episodes_materialized"),
                "status": scale.get("status"),
            },
            text=text,
            boundary="Catalog-side evidence only; does not materialize a billion rows or payload bytes.",
        )
    )

    bench_gate = results.get("benchmark_inflation_gate", {})
    claims.append(
        claim_result(
            claim_id="CLAIM.BENCHMARK_BOUNDARY.001",
            claim="Famous benchmark audit is fail-closed and makes zero inflation claims in this release.",
            evidence_artifacts=["docs/experiments/benchmark_inflation_gate/gate_report.json"],
            paper_patterns=[
                "\\ExpDroidRerunEpisodes{}-episode DROID subset evidence",
                "\\ExpBenchmarkInflationClaimCount{} measured inflation claims",
                "provides no inflation evidence",
                "\\ExpBenchmarkInflationClaimCount{} famous-benchmark inflation claims",
            ],
            evidence_passed=(
                int(nested(bench_gate, ("aggregate", "audited_benchmark_count"), 0)) > 0
                and nested(bench_gate, ("aggregate", "executed_rerun_report_count")) >= 1
                and nested(bench_gate, ("aggregate", "valid_rerun_report_count")) == 0
                and nested(bench_gate, ("aggregate", "measured_inflation_claims")) == 0
                and nested(bench_gate, ("aggregate", "ready_for_inflation_claim")) is False
            ),
            evidence={
                "audited_benchmark_count": nested(bench_gate, ("aggregate", "audited_benchmark_count")),
                "executed_rerun_report_count": nested(bench_gate, ("aggregate", "executed_rerun_report_count")),
                "valid_rerun_report_count": nested(bench_gate, ("aggregate", "valid_rerun_report_count")),
                "measured_inflation_claims": nested(bench_gate, ("aggregate", "measured_inflation_claims")),
                "ready_for_inflation_claim": nested(bench_gate, ("aggregate", "ready_for_inflation_claim")),
            },
            text=text,
            boundary="Source-level call-out audit; no published-score inflation claim.",
        )
    )

    claims.append(
        claim_result(
            claim_id="CLAIM.OPEN_GATES.001",
            claim="Open results are visibly and machine-readably marked as not claimed.",
            evidence_artifacts=["docs/experiments/open_reproduction_gates/open_reproduction_gates.json"],
            paper_patterns=[
                "\\begin{openresult}{ACT/Diffusion and rollout impact}",
                "\\begin{openresult}{famous-benchmark score-inflation proof}",
                "\\begin{openresult}{results not claimed in this release}",
                "Open result, not claimed",
                "open_reproduction_gates.json",
                "\\newcommand{\\ExpActDiffusionResult}{\\PaperNotDefinedYet}",
                "\\newcommand{\\ExpBenchmarkInflationResult}{\\PaperNotDefinedYet}",
            ],
            evidence_passed=(
                open_gates.get("schema") == "worldepisode_open_reproduction_gates_v1"
                and nested(open_gates, ("validation", "passed")) is True
                and int(nested(open_gates, ("aggregate", "gate_count"), 0)) > 0
                and nested(open_gates, ("aggregate", "command_count"))
                >= nested(open_gates, ("aggregate", "gate_count"))
            ),
            evidence={
                "schema": open_gates.get("schema"),
                "validation": open_gates.get("validation"),
                "aggregate": open_gates.get("aggregate"),
            },
            text=text,
            boundary="Open gates are unclaimed results, not paper results.",
        )
    )

    return claims


def build_report(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    results = load_json(RESULTS_JSON)
    open_gates = load_json(OPEN_GATES_JSON)
    statistics = load_json(STATISTICS_JSON)
    conversion_scale = load_json(CONVERSION_SCALE_JSON)
    multitrajectory_timing = load_json(MULTITRAJECTORY_TIMING_JSON)
    text = paper_text()
    claims = build_claims(
        results,
        open_gates,
        statistics,
        conversion_scale,
        multitrajectory_timing,
        text,
    )
    failed = [claim for claim in claims if not claim["passed"]]
    report = {
        "schema": SCHEMA,
        "audit_date": AUDIT_DATE,
        "status": "pass" if not failed else "fail",
        "paper_sources": [
            rel(ROOT / "paper" / "arxiv" / "main.tex"),
            rel(ROOT / "paper" / "arxiv" / "checklist.tex"),
            rel(PAPER_VALUES_TEX),
            *[rel(path) for path in sorted((ROOT / "paper" / "arxiv" / "sections").glob("*.tex"))],
        ],
        "evidence_root": rel(RESULTS_JSON),
        "additional_evidence_roots": [
            rel(CONVERSION_SCALE_JSON),
            rel(MULTITRAJECTORY_TIMING_JSON),
        ],
        "claims": claims,
        "aggregate": {
            "claim_count": len(claims),
            "passed_count": sum(1 for claim in claims if claim["passed"]),
            "failed_count": len(failed),
            "missing_paper_pattern_count": sum(len(claim["missing_paper_patterns"]) for claim in claims),
            "failed_claim_ids": [claim["claim_id"] for claim in failed],
        },
        "artifacts": {
            "json": rel(output_dir / "paper_claim_audit_report.json"),
            "markdown": rel(output_dir / "README.md"),
        },
    }
    write_json(output_dir / "paper_claim_audit_report.json", report)
    write_text(output_dir / "README.md", render_markdown(report))
    return report


def render_markdown(report: dict[str, Any]) -> str:
    rows = [
        "| {claim_id} | {passed} | {claim} | {boundary} |".format(
            claim_id=claim["claim_id"],
            passed=claim["passed"],
            claim=claim["claim"],
            boundary=claim["boundary"],
        )
        for claim in report["claims"]
    ]
    lines = [
        "# Paper Claim Audit",
        "",
        f"Status: `{report['status']}`.",
        "",
        (
            "This report ties the main quantitative and boundary claims in the paper source to "
            "tracked experiment artifacts. It fails if a checked number or boundary disappears "
            "from the paper or is unsupported by the committed evidence."
        ),
        "",
        "## Summary",
        "",
        f"- Claims checked: {report['aggregate']['claim_count']}",
        f"- Passed: {report['aggregate']['passed_count']}",
        f"- Failed: {report['aggregate']['failed_count']}",
        "",
        "## Claims",
        "",
        "| Claim ID | Pass | Claim | Boundary |",
        "|---|---:|---|---|",
        *rows,
        "",
    ]
    if report["aggregate"]["failed_count"]:
        lines.extend(["## Failures", ""])
        for claim in report["claims"]:
            if claim["passed"]:
                continue
            lines.extend(
                [
                    f"### `{claim['claim_id']}`",
                    "",
                    f"Evidence passed: `{claim['evidence_passed']}`.",
                    "",
                    "Missing paper patterns:",
                    "",
                    *[f"- `{pattern}`" for pattern in claim["missing_paper_patterns"]],
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--strict", action="store_true", help="exit non-zero unless all audited claims pass")
    args = parser.parse_args()
    report = build_report(args.output_dir)
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
    if args.strict and report["status"] != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
