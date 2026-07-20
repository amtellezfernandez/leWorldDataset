#!/usr/bin/env python3
"""Generate a machine-readable manifest for the principal paper experiments."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "docs" / "experiments" / "experiment_manifest"
OUTPUT_PATH = OUTPUT_DIR / "experiment_manifest.json"
README_PATH = OUTPUT_DIR / "README.md"

RESULTS_PATH = ROOT / "docs" / "experiments" / "results.json"
LEAKAGE_REPORT_PATH = (
    ROOT / "docs" / "experiments" / "lerobot_scene_leakage" / "leakage_report.json"
)
TEMPORAL_REPORT_PATH = (
    ROOT
    / "docs"
    / "experiments"
    / "lerobot_temporal_policy_baseline"
    / "temporal_policy_report.json"
)
DROID_REPORT_PATH = (
    ROOT / "docs" / "experiments" / "benchmark_reruns" / "droid_100" / "rerun_report.json"
)
STATISTICS_PATH = (
    ROOT / "docs" / "experiments" / "statistical_analysis" / "statistical_report.json"
)
CONVERSION_SCALE_REPORT_PATH = (
    ROOT / "docs" / "experiments" / "lerobot_conversion_scale" / "scale_report.json"
)
CONVERSION_SCALE_README_PATH = (
    ROOT / "docs" / "experiments" / "lerobot_conversion_scale" / "README.md"
)
MULTITRAJECTORY_TIMING_REPORT_PATH = (
    ROOT
    / "docs"
    / "experiments"
    / "lerobot_multitrajectory_timing"
    / "timing_report.json"
)
MULTITRAJECTORY_TIMING_README_PATH = (
    ROOT / "docs" / "experiments" / "lerobot_multitrajectory_timing" / "README.md"
)
POLICY_COMPATIBILITY_REPORT_PATH = (
    ROOT / "docs" / "experiments" / "lerobot_policy_gate" / "policy_compatibility_report.json"
)
POLICY_GATE_REPORT_PATH = (
    ROOT / "docs" / "experiments" / "lerobot_policy_gate" / "policy_gate_report.json"
)
POLICY_PHYSICAL_SPLIT_MANIFEST_PATH = (
    ROOT / "docs" / "experiments" / "lerobot_policy_gate" / "physical_splits" / "manifest.json"
)

LEAKAGE_LOG_PATH = (
    ROOT / "docs" / "experiments" / "run_logs" / "lerobot_scene_leakage_dgx_spark.log"
)
DROID_LOG_PATH = ROOT / "docs" / "experiments" / "run_logs" / "droid_100_dgx_spark.log"
CONTROLLED_LOG_PATH = (
    ROOT / "docs" / "experiments" / "run_logs" / "controlled_suite_dgx_spark.log"
)
CONVERSION_SCALE_LOG_PATH = (
    ROOT / "docs" / "experiments" / "run_logs" / "lerobot_conversion_scale_dgx_spark.log"
)
MULTITRAJECTORY_TIMING_LOG_PATH = (
    ROOT
    / "docs"
    / "experiments"
    / "run_logs"
    / "lerobot_multitrajectory_timing_dgx_spark.log"
)
POLICY_COMPATIBILITY_LOG_PATH = (
    ROOT
    / "docs"
    / "experiments"
    / "run_logs"
    / "lerobot_policy_compatibility_dgx_spark.log"
)
CONVERSION_SCALE_FAILED_LOG_PATHS = (
    ROOT
    / "docs"
    / "experiments"
    / "run_logs"
    / "lerobot_conversion_scale_dgx_spark_failed_01.log",
    ROOT
    / "docs"
    / "experiments"
    / "run_logs"
    / "lerobot_conversion_scale_dgx_spark_failed_02.log",
)

SCHEMA = "worldepisode_experiment_manifest_v1"
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")


class ExperimentManifestError(ValueError):
    """Raised when required experiment provenance is missing or inconsistent."""


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ExperimentManifestError(f"required JSON artifact is missing: {relative(path)}") from exc
    except json.JSONDecodeError as exc:
        raise ExperimentManifestError(f"invalid JSON in {relative(path)}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ExperimentManifestError(f"expected JSON object in {relative(path)}")
    return payload


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ExperimentManifestError(f"required artifact is missing: {relative(path)}")
    return {
        "path": relative(path),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }


def artifact_from_relative(path: str) -> dict[str, Any]:
    return artifact(ROOT / path)


def parse_elapsed(value: str) -> float:
    parts = value.strip().split(":")
    try:
        numbers = [float(part) for part in parts]
    except ValueError as exc:
        raise ExperimentManifestError(f"invalid GNU time elapsed value: {value!r}") from exc
    if len(numbers) == 2:
        minutes, seconds = numbers
        return 60 * minutes + seconds
    if len(numbers) == 3:
        hours, minutes, seconds = numbers
        return 3600 * hours + 60 * minutes + seconds
    raise ExperimentManifestError(f"invalid GNU time elapsed value: {value!r}")


def first_value(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, flags=re.MULTILINE)
    return match.group(1).strip() if match else None


def parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ExperimentManifestError(f"expected integer provenance value, got {value!r}") from exc


def parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise ExperimentManifestError(f"expected numeric provenance value, got {value!r}") from exc


def parse_run_log(path: Path, runtime_fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    lines = [line.strip() for line in text.splitlines()]

    repository_commit = first_value(text, r"^git_commit=(.+)$")
    if repository_commit is None:
        repository_commit = next((line for line in lines if COMMIT_PATTERN.fullmatch(line)), None)

    host_uname = first_value(text, r"^host_uname=(.+)$")
    if host_uname is None:
        host_uname = next((line for line in lines if line.startswith("Linux ")), None)

    gpu_info = first_value(text, r"^gpu_info=(.+)$")
    if gpu_info is None:
        gpu_info = next((line for line in lines if line.startswith("NVIDIA ")), None)

    elapsed = first_value(text, r"^\s*Elapsed \(wall clock\) time .*: (.+)$")
    max_rss_kib = parse_int(
        first_value(text, r"^\s*Maximum resident set size \(kbytes\): ([0-9]+)$")
    )
    fallback = runtime_fallback or {}
    provenance = {
        "log": artifact(path),
        "started_utc": first_value(text, r"^started_utc=(.+)$"),
        "finished_utc": first_value(text, r"^finished_utc=(.+)$"),
        "command": first_value(text, r"^command=(.+)$"),
        "repository_commit": repository_commit,
        "host": {
            "uname": host_uname,
            "machine": first_value(text, r"^machine=(.+)$") or fallback.get("machine"),
            "cpu_logical_count": parse_int(first_value(text, r"^cpu_logical_count=([0-9]+)$"))
            or fallback.get("cpu_logical_count"),
            "total_ram_bytes": parse_int(first_value(text, r"^total_ram_bytes=([0-9]+)$"))
            or fallback.get("total_ram_bytes"),
            "storage_total_bytes": parse_int(
                first_value(text, r"^storage_total_bytes=([0-9]+)$")
            )
            or fallback.get("storage_total_bytes"),
            "storage_free_bytes": parse_int(
                first_value(text, r"^storage_free_bytes=([0-9]+)$")
            )
            or fallback.get("storage_free_bytes"),
            "gpu_info": gpu_info,
        },
        "compute": {
            "wall_time_seconds": parse_elapsed(elapsed) if elapsed else None,
            "user_cpu_seconds": parse_float(
                first_value(text, r"^\s*User time \(seconds\): ([0-9.]+)$")
            ),
            "system_cpu_seconds": parse_float(
                first_value(text, r"^\s*System time \(seconds\): ([0-9.]+)$")
            ),
            "cpu_utilization_percent": parse_float(
                first_value(text, r"^\s*Percent of CPU this job got: ([0-9.]+)%$")
            ),
            "max_rss_bytes": max_rss_kib * 1024 if max_rss_kib is not None else None,
        },
        "exit_status": parse_int(first_value(text, r"^\s*Exit status: ([0-9]+)$")),
    }
    return provenance


def code_artifact(path: str, reported_sha256: str | None = None) -> dict[str, Any]:
    descriptor = artifact_from_relative(path)
    if reported_sha256 is not None and descriptor["sha256"] != reported_sha256:
        raise ExperimentManifestError(
            f"current code digest for {path} does not match the executed report"
        )
    return descriptor


def dataset(repo_id: str, revision: str, source_digest: str | None = None) -> dict[str, Any]:
    value = {
        "repo_id": repo_id,
        "revision": revision,
    }
    if source_digest is not None:
        value["source_digest"] = source_digest
    return value


def build_manifest() -> dict[str, Any]:
    results = read_json(RESULTS_PATH)
    leakage = read_json(LEAKAGE_REPORT_PATH)
    temporal = read_json(TEMPORAL_REPORT_PATH)
    droid = read_json(DROID_REPORT_PATH)
    conversion_scale = read_json(CONVERSION_SCALE_REPORT_PATH)
    multitrajectory_timing = read_json(MULTITRAJECTORY_TIMING_REPORT_PATH)
    policy_compatibility = read_json(POLICY_COMPATIBILITY_REPORT_PATH)

    leakage_run = parse_run_log(LEAKAGE_LOG_PATH, leakage.get("runtime", {}))
    droid_run = parse_run_log(DROID_LOG_PATH)
    controlled_run = parse_run_log(CONTROLLED_LOG_PATH)
    conversion_scale_log_text = CONVERSION_SCALE_LOG_PATH.read_text(encoding="utf-8")
    conversion_scale_run = parse_run_log(
        CONVERSION_SCALE_LOG_PATH,
        conversion_scale.get("execution", {}).get("host", {}),
    )
    multitrajectory_timing_run = parse_run_log(MULTITRAJECTORY_TIMING_LOG_PATH)
    conversion_scale_run["preliminary_runs"] = [
        {
            **parse_run_log(path),
            "status": "failed_preliminary",
        }
        for path in CONVERSION_SCALE_FAILED_LOG_PATHS
    ]
    conversion_converter_sha256 = first_value(
        conversion_scale_log_text,
        r"^converter_code_sha256=(.+)$",
    )
    if conversion_converter_sha256 is None:
        raise ExperimentManifestError(
            "conversion-scale run log is missing converter_code_sha256"
        )

    leakage_split = artifact_from_relative(leakage["artifacts"]["split_manifest"])
    temporal_split = artifact_from_relative(temporal["source"]["physical_split_manifest"])
    droid_split = artifact_from_relative(droid["worldepisode_conversion"]["split_manifest"])

    random_policy = leakage["splits"]["random_episode"]["bc"]["policy"]
    temporal_policy = temporal["splits"]["random_episode"]["policy"]
    roundtrip = results["lerobot_active_roundtrip"]
    controlled_datasets = [
        dataset(
            roundtrip["batch_roundtrip"]["repo_id"],
            roundtrip["batch_roundtrip"]["revision"],
        ),
        *[
            dataset(item["repo_id"], item["revision"])
            for item in roundtrip["secondary_batch_roundtrips"]
        ],
        dataset(leakage["repo_id"], leakage["revision"]),
    ]
    policy_probe_seeds = sorted(
        {
            int(argument.split("=", 1)[1])
            for probe in policy_compatibility["policy_probes"]
            for argument in probe["command_template"]
            if argument.startswith("--seed=")
        }
    )
    policy_compatibility_execution = {
        **policy_compatibility["execution"],
        "log": artifact(POLICY_COMPATIBILITY_LOG_PATH),
    }

    experiments = [
        {
            "experiment_id": "armnet_task_scene_proxy_mlp",
            "status": "measured",
            "claim_boundary": (
                "Task identity is part of the proxy lineage; this is offline imitation evidence, "
                "not scene-only leakage or rollout success."
            ),
            "datasets": [dataset(leakage["repo_id"], leakage["revision"])],
            "split": leakage_split,
            "configuration": leakage["experiment"]["config"],
            "seed_policy": {
                "kind": "optimization_seeds",
                "values": leakage["bc_seeds"],
            },
            "code": [
                code_artifact(
                    leakage["experiment"]["script"],
                    leakage["experiment"]["script_sha256"],
                )
            ],
            "execution": leakage_run,
            "outputs": [
                artifact(LEAKAGE_REPORT_PATH),
                artifact_from_relative(leakage["artifacts"]["bc_episode_errors"]),
                leakage_split,
                artifact_from_relative(leakage["artifacts"]["world_lineage"]),
                artifact(STATISTICS_PATH),
            ],
        },
        {
            "experiment_id": "armnet_task_scene_proxy_temporal_ridge",
            "status": "measured",
            "claim_boundary": temporal["claim_boundary"],
            "datasets": [dataset(leakage["repo_id"], leakage["revision"])],
            "split": temporal_split,
            "configuration": {
                "policy": temporal_policy,
                "success_threshold": temporal["splits"]["random_episode"]["metrics"][
                    "offline_success_threshold"
                ],
            },
            "seed_policy": {
                "kind": "not_applicable",
                "reason": "deterministic closed-form ridge estimator",
                "values": [],
            },
            "code": [code_artifact("tools/lerobot_temporal_policy_baseline.py")],
            "execution": {
                **controlled_run,
                "accounting_scope": "shared controlled-suite process",
            },
            "outputs": [
                artifact(TEMPORAL_REPORT_PATH),
                artifact(STATISTICS_PATH),
            ],
        },
        {
            "experiment_id": "droid_100_proxy_ridge_rerun",
            "status": "measured_no_inflation_evidence",
            "claim_boundary": droid["claim_boundary"],
            "datasets": [
                dataset(
                    droid["benchmark_subset"]["repo_id"],
                    droid["benchmark_subset"]["revision"],
                    droid["benchmark_subset"]["source_files_sha256"],
                )
            ],
            "split": droid_split,
            "configuration": {
                "policy": droid["policy"],
                "metric": droid["evaluation"]["metric"],
                "baseline_split": droid["evaluation"]["baseline_split"],
                "corrected_split": droid["evaluation"]["corrected_split"],
            },
            "seed_policy": {
                "kind": "fixed_random_seed",
                "values": [droid["policy"]["random_seed"]],
            },
            "code": [code_artifact(droid["policy"]["implementation"])],
            "execution": droid_run,
            "outputs": [
                artifact(DROID_REPORT_PATH),
                droid_split,
                artifact_from_relative(droid["worldepisode_conversion"]["conversion_report"]),
                artifact_from_relative(droid["worldepisode_conversion"]["lineage_manifest"]),
            ],
        },
        {
            "experiment_id": "controlled_contract_suite",
            "status": "measured",
            "claim_boundary": (
                "Shared deterministic suite covering contract checks, conversions, replay, "
                "controlled proxies, and report generation; individual boundaries remain in "
                "docs/experiments/results.json."
            ),
            "datasets": controlled_datasets,
            "split": {
                "kind": "multiple_committed_manifests",
                "artifacts": [
                    leakage_split,
                    temporal_split,
                ],
            },
            "configuration": {
                "environment": {
                    "WORLDEPISODE_RUN_TEMPORAL_POLICY_BASELINE": "1",
                },
                "contained_result_sections": sorted(results),
            },
            "seed_policy": {
                "kind": "mixed_declared_in_contained_reports",
                "values": sorted(
                    {
                        *leakage["bc_seeds"],
                        int(leakage["experiment"]["config"]["random_split_seed"]),
                        int(droid["policy"]["random_seed"]),
                    }
                ),
            },
            "code": [code_artifact("tools/run_experiments.py")],
            "execution": controlled_run,
            "outputs": [
                artifact(RESULTS_PATH),
                artifact(ROOT / "docs" / "experiments" / "RESULTS.md"),
            ],
        },
        {
            "experiment_id": "lerobot_conversion_scale",
            "status": "measured",
            "claim_boundary": conversion_scale["claim_boundary"],
            "datasets": [
                dataset(
                    item["repo_id"],
                    item["revision"],
                    item["source_subset"]["source_files"][
                        "data/chunk-000/file-000.parquet"
                    ]["sha256"],
                )
                for item in conversion_scale["datasets"]
            ],
            "split": {
                "kind": "complete_pinned_source_parquet_files",
                "subsets": [
                    {
                        "dataset_id": item["dataset_id"],
                        "data_chunk_index": item["source_subset"]["data_chunk_index"],
                        "data_file_index": item["source_subset"]["data_file_index"],
                        "episode_count": item["conversion"]["episode_count"],
                        "episode_index_sha256": item["source_subset"][
                            "episode_index_sha256"
                        ],
                    }
                    for item in conversion_scale["datasets"]
                ],
            },
            "configuration": {
                "protocol": conversion_scale["protocol"],
                "software": conversion_scale["execution"]["software"],
            },
            "seed_policy": {
                "kind": "not_applicable",
                "reason": "deterministic exact conversion and comparison",
                "values": [],
            },
            "code": [
                code_artifact(
                    conversion_scale["execution"]["script"],
                    conversion_scale["execution"]["script_sha256"],
                ),
                code_artifact(
                    "tools/lerobot_worldepisode_roundtrip.py",
                    conversion_converter_sha256,
                ),
            ],
            "execution": conversion_scale_run,
            "outputs": [
                artifact(CONVERSION_SCALE_REPORT_PATH),
                artifact(CONVERSION_SCALE_README_PATH),
                *[
                    artifact(path)
                    for path in CONVERSION_SCALE_FAILED_LOG_PATHS
                ],
            ],
        },
        {
            "experiment_id": "lerobot_multitrajectory_timing",
            "status": "measured_partial_action_002",
            "claim_boundary": multitrajectory_timing["claim_boundary"],
            "datasets": [
                dataset(
                    multitrajectory_timing["source"]["dataset"]["repo_id"],
                    multitrajectory_timing["source"]["dataset"]["revision"],
                    multitrajectory_timing["source"]["calibration_package"]["artifacts"][
                        "data"
                    ]["sha256"],
                )
            ],
            "split": {
                "kind": "source_episode_disjoint_calibration_evaluation",
                "source_episode_overlap_count": multitrajectory_timing["source"][
                    "source_episode_overlap_count"
                ],
                "calibration": multitrajectory_timing["source"]["calibration_package"],
                "evaluation": multitrajectory_timing["source"]["evaluation_package"],
            },
            "configuration": {
                "protocol": multitrajectory_timing["protocol"],
                "metric_unit": multitrajectory_timing["source"]["metric_unit"],
                "effective_motor_timestamp_available": multitrajectory_timing["source"][
                    "effective_motor_timestamp_available"
                ],
            },
            "seed_policy": {
                "kind": "fixed_analysis_seed",
                "reason": "deterministic paired episode bootstrap",
                "values": [
                    multitrajectory_timing["protocol"]["bootstrap_seed"],
                ],
            },
            "code": [
                code_artifact(
                    multitrajectory_timing["execution"]["script"],
                    multitrajectory_timing["execution"]["script_sha256"],
                )
            ],
            "execution": multitrajectory_timing_run,
            "outputs": [
                artifact(MULTITRAJECTORY_TIMING_REPORT_PATH),
                artifact(MULTITRAJECTORY_TIMING_README_PATH),
            ],
        },
        {
            "experiment_id": "lerobot_act_diffusion_compatibility_preflight",
            "status": policy_compatibility["status"],
            "claim_boundary": policy_compatibility["claim_boundary"],
            "datasets": [dataset(leakage["repo_id"], leakage["revision"])],
            "split": {
                "kind": "representative_random_episode_train_package",
                "source_split": leakage_split,
                "physical_split_manifest": artifact(POLICY_PHYSICAL_SPLIT_MANIFEST_PATH),
                "package_role": policy_compatibility["dataset"]["package_role"],
            },
            "configuration": {
                "lerobot_version": policy_compatibility[
                    "lerobot_policy_requirements_version"
                ],
                "required_missing_modality": policy_compatibility[
                    "required_missing_modality"
                ],
                "policy_probes": [
                    {
                        "policy": probe["policy"],
                        "command_template": probe["command_template"],
                    }
                    for probe in policy_compatibility["policy_probes"]
                ],
            },
            "seed_policy": {
                "kind": "fixed_compatibility_smoke_seed",
                "values": policy_probe_seeds,
            },
            "code": [
                code_artifact(
                    policy_compatibility["script"],
                    policy_compatibility["script_sha256"],
                )
            ],
            "execution": policy_compatibility_execution,
            "outputs": [
                artifact(POLICY_COMPATIBILITY_REPORT_PATH),
                artifact(POLICY_GATE_REPORT_PATH),
            ],
        },
    ]

    errors: list[str] = []
    for experiment in experiments:
        experiment_id = experiment["experiment_id"]
        execution = experiment["execution"]
        host = execution["host"]
        compute = execution["compute"]
        if not experiment["datasets"]:
            errors.append(f"{experiment_id}: no dataset revision")
        if not experiment["configuration"]:
            errors.append(f"{experiment_id}: no effective configuration")
        if not experiment["code"]:
            errors.append(f"{experiment_id}: no exact code digest")
        if not experiment["outputs"]:
            errors.append(f"{experiment_id}: no output artifacts")
        if execution.get("exit_status") != 0:
            errors.append(f"{experiment_id}: execution did not exit successfully")
        for preliminary in execution.get("preliminary_runs", []):
            if preliminary.get("exit_status") in (None, 0):
                errors.append(
                    f"{experiment_id}: preliminary run must record a nonzero exit status"
                )
        for field in ("started_utc", "finished_utc", "command", "repository_commit"):
            if not execution.get(field):
                errors.append(f"{experiment_id}: execution missing {field}")
        for field in (
            "uname",
            "cpu_logical_count",
            "total_ram_bytes",
            "storage_total_bytes",
            "storage_free_bytes",
            "gpu_info",
        ):
            if host.get(field) in (None, ""):
                errors.append(f"{experiment_id}: host provenance missing {field}")
        for field in (
            "wall_time_seconds",
            "user_cpu_seconds",
            "system_cpu_seconds",
            "cpu_utilization_percent",
            "max_rss_bytes",
        ):
            if compute.get(field) is None:
                errors.append(f"{experiment_id}: compute provenance missing {field}")

    generated_from = [
        artifact(path)
        for path in (
            RESULTS_PATH,
            LEAKAGE_REPORT_PATH,
            TEMPORAL_REPORT_PATH,
            DROID_REPORT_PATH,
            STATISTICS_PATH,
            LEAKAGE_LOG_PATH,
            DROID_LOG_PATH,
            CONTROLLED_LOG_PATH,
            CONVERSION_SCALE_REPORT_PATH,
            CONVERSION_SCALE_README_PATH,
            CONVERSION_SCALE_LOG_PATH,
            MULTITRAJECTORY_TIMING_REPORT_PATH,
            MULTITRAJECTORY_TIMING_README_PATH,
            MULTITRAJECTORY_TIMING_LOG_PATH,
            POLICY_COMPATIBILITY_REPORT_PATH,
            POLICY_GATE_REPORT_PATH,
            POLICY_PHYSICAL_SPLIT_MANIFEST_PATH,
            POLICY_COMPATIBILITY_LOG_PATH,
            *CONVERSION_SCALE_FAILED_LOG_PATHS,
        )
    ]
    return {
        "schema": SCHEMA,
        "scope": (
            "Principal paper experiments and the shared controlled suite. Derived paper rendering "
            "is tracked separately by the release manifest."
        ),
        "generated_from": generated_from,
        "experiments": experiments,
        "aggregate": {
            "experiment_count": len(experiments),
            "measured_count": sum(
                1 for experiment in experiments if experiment["status"].startswith("measured")
            ),
            "remote_run_count": len(
                {experiment["execution"]["log"]["path"] for experiment in experiments}
            ),
        },
        "validation": {
            "passed": not errors,
            "errors": errors,
        },
    }


def render_markdown(manifest: dict[str, Any]) -> str:
    rows = []
    for experiment in manifest["experiments"]:
        execution = experiment["execution"]
        rows.append(
            "| `{id}` | {status} | {datasets} | {wall:.2f} | {rss:.1f} | `{log}` |".format(
                id=experiment["experiment_id"],
                status=experiment["status"],
                datasets=", ".join(
                    f"{item['repo_id']}@{item['revision'][:12]}"
                    for item in experiment["datasets"]
                ),
                wall=execution["compute"]["wall_time_seconds"],
                rss=execution["compute"]["max_rss_bytes"] / (1024 * 1024),
                log=execution["log"]["path"],
            )
        )
    errors = manifest["validation"]["errors"]
    error_text = "\n".join(f"- {error}" for error in errors) if errors else "- None"
    return f"""# Experiment Provenance Manifest

Schema: `{manifest["schema"]}`.

{manifest["scope"]}

| Experiment | Status | Pinned datasets | Wall time (s) | Max RSS (MiB) | Run log |
|---|---|---|---:|---:|---|
{chr(10).join(rows)}

## Validation

Passed: `{manifest["validation"]["passed"]}`.

{error_text}
"""


def write_outputs(manifest: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    README_PATH.write_text(render_markdown(manifest), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if committed outputs differ from current reports and logs",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="return nonzero when required provenance is incomplete",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = build_manifest()
    rendered_json = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    rendered_markdown = render_markdown(manifest)
    if args.check:
        current = (
            OUTPUT_PATH.is_file()
            and README_PATH.is_file()
            and OUTPUT_PATH.read_text(encoding="utf-8") == rendered_json
            and README_PATH.read_text(encoding="utf-8") == rendered_markdown
        )
        print(f"experiment manifest: {'current' if current else 'stale'}")
        if not current:
            return 1
    else:
        write_outputs(manifest)
        print(
            json.dumps(
                {
                    "output": relative(OUTPUT_PATH),
                    "experiment_count": manifest["aggregate"]["experiment_count"],
                    "validation": manifest["validation"],
                },
                indent=2,
                sort_keys=True,
            )
        )
    if args.strict and not manifest["validation"]["passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
