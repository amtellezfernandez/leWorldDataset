#!/usr/bin/env python3
"""Probe whether committed low-dimensional splits can train pinned LeRobot policies."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import re
import resource
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET_ROOT = (
    ROOT
    / "docs"
    / "experiments"
    / "lerobot_policy_gate"
    / "physical_splits"
    / "random_episode_train"
)
DEFAULT_REPORT = (
    ROOT
    / "docs"
    / "experiments"
    / "lerobot_policy_gate"
    / "policy_compatibility_report.json"
)
DEFAULT_LOG = (
    ROOT
    / "docs"
    / "experiments"
    / "run_logs"
    / "lerobot_policy_compatibility_dgx_spark.log"
)
DATASET_REPO_ID = "worldepisode/armnetbench_v01_lerobot_so101_random_episode_train"
LEROBOT_VERSION = "0.6.0"
POLICIES = ("act", "diffusion")
EXPECTED_MODALITY_ERROR = "You must provide at least one image or the environment state among the inputs."
PACKAGE_FILES = (
    "data/chunk-000/file-000.parquet",
    "meta/episodes/chunk-000/file-000.parquet",
    "meta/info.json",
    "meta/stats.json",
    "meta/tasks.parquet",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_files(dataset_root: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": relative_path,
            "bytes": (dataset_root / relative_path).stat().st_size,
            "sha256": sha256_file(dataset_root / relative_path),
        }
        for relative_path in PACKAGE_FILES
    ]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def normalized_traceback(output: str, dataset_root: Path, work_dir: Path) -> str:
    traceback_start = output.rfind("Traceback (most recent call last):")
    traceback = output[traceback_start:] if traceback_start >= 0 else output
    traceback = traceback.replace(str(dataset_root), "$DATASET_ROOT")
    traceback = traceback.replace(str(work_dir), "$WORK_DIR")
    traceback = re.sub(r"/home/[^/]+/\.cache/uv/(?:archive|builds)-v0/[^/]+", "$UV_ENV", traceback)
    return traceback.strip()


def train_command(policy: str, dataset_root: Path, output_dir: Path) -> list[str]:
    return [
        sys.executable,
        "-m",
        "lerobot.scripts.lerobot_train",
        f"--dataset.repo_id={DATASET_REPO_ID}",
        f"--dataset.root={dataset_root}",
        f"--policy.type={policy}",
        "--policy.push_to_hub=false",
        f"--output_dir={output_dir}",
        f"--job_name={policy}_compatibility_smoke",
        "--policy.device=cuda",
        "--steps=1",
        "--batch_size=2",
        "--num_workers=0",
        "--save_checkpoint=false",
        "--wandb.enable=false",
        "--seed=17",
    ]


def command_template(policy: str) -> list[str]:
    return [
        "python",
        "-m",
        "lerobot.scripts.lerobot_train",
        f"--dataset.repo_id={DATASET_REPO_ID}",
        "--dataset.root=$DATASET_ROOT",
        f"--policy.type={policy}",
        "--policy.push_to_hub=false",
        f"--output_dir=$WORK_DIR/{policy}",
        f"--job_name={policy}_compatibility_smoke",
        "--policy.device=cuda",
        "--steps=1",
        "--batch_size=2",
        "--num_workers=0",
        "--save_checkpoint=false",
        "--wandb.enable=false",
        "--seed=17",
    ]


def probe_policy(policy: str, dataset_root: Path, work_dir: Path) -> tuple[dict[str, Any], str]:
    command = train_command(policy, dataset_root, work_dir / policy)
    start = time.perf_counter()
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    duration_seconds = round(time.perf_counter() - start, 6)
    output = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
    traceback = normalized_traceback(output, dataset_root, work_dir)
    terminal_error = next(
        (
            line.strip()
            for line in reversed(traceback.splitlines())
            if line.strip().startswith(("ValueError:", "RuntimeError:", "ImportError:"))
        ),
        "",
    )
    expected_error_observed = EXPECTED_MODALITY_ERROR in output
    result = {
        "policy": policy,
        "command_template": command_template(policy),
        "return_code": completed.returncode,
        "duration_seconds": duration_seconds,
        "training_step_completed": completed.returncode == 0,
        "expected_modality_error_observed": expected_error_observed,
        "terminal_error": terminal_error,
        "normalized_traceback_sha256": hashlib.sha256(traceback.encode("utf-8")).hexdigest(),
        "status": (
            "blocked_missing_required_observation_modality"
            if expected_error_observed
            else "completed" if completed.returncode == 0 else "failed_unexpectedly"
        ),
    }
    return result, traceback


def environment_payload(torch: Any, lerobot: Any) -> dict[str, Any]:
    cuda_available = bool(torch.cuda.is_available())
    devices = []
    if cuda_available:
        for index in range(torch.cuda.device_count()):
            properties = torch.cuda.get_device_properties(index)
            devices.append(
                {
                    "index": index,
                    "name": properties.name,
                    "total_memory_bytes": int(properties.total_memory),
                    "compute_capability": f"{properties.major}.{properties.minor}",
                }
            )
    return {
        "hostname": socket.gethostname(),
        "machine": platform.machine(),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "lerobot_version": lerobot.__version__,
        "torch_version": torch.__version__,
        "cuda_available": cuda_available,
        "cuda_device_count": len(devices),
        "cuda_devices": devices,
    }


def run_probe(
    dataset_root: Path,
    work_dir: Path,
    repository_commit: str,
) -> tuple[dict[str, Any], dict[str, str]]:
    started_utc = dt.datetime.now(dt.timezone.utc).isoformat()
    probe_start = time.perf_counter()
    self_usage_before = resource.getrusage(resource.RUSAGE_SELF)
    child_usage_before = resource.getrusage(resource.RUSAGE_CHILDREN)
    import lerobot
    import torch
    from lerobot.datasets import LeRobotDataset

    if lerobot.__version__ != LEROBOT_VERSION:
        raise RuntimeError(f"expected LeRobot {LEROBOT_VERSION}, found {lerobot.__version__}")

    dataset = LeRobotDataset(DATASET_REPO_ID, root=dataset_root)
    sample = dataset[0]
    loader = {
        "success": True,
        "episode_count": dataset.num_episodes,
        "frame_count": dataset.num_frames,
        "feature_keys": sorted(dataset.features),
        "stats_feature_keys": sorted(dataset.meta.stats or {}),
        "sample_shapes": {
            key: list(value.shape)
            for key, value in sorted(sample.items())
            if hasattr(value, "shape")
        },
    }
    policy_results = []
    tracebacks: dict[str, str] = {}
    for policy in POLICIES:
        result, traceback = probe_policy(policy, dataset_root, work_dir)
        policy_results.append(result)
        tracebacks[policy] = traceback

    all_blocked_for_expected_reason = all(
        result["expected_modality_error_observed"] and not result["training_step_completed"]
        for result in policy_results
    )
    self_usage = resource.getrusage(resource.RUSAGE_SELF)
    child_usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    wall_time_seconds = time.perf_counter() - probe_start
    user_cpu_seconds = (
        self_usage.ru_utime
        - self_usage_before.ru_utime
        + child_usage.ru_utime
        - child_usage_before.ru_utime
    )
    system_cpu_seconds = (
        self_usage.ru_stime
        - self_usage_before.ru_stime
        + child_usage.ru_stime
        - child_usage_before.ru_stime
    )
    max_rss_bytes = int(max(self_usage.ru_maxrss, child_usage.ru_maxrss) * 1024)
    disk_usage = shutil.disk_usage(dataset_root)
    environment = environment_payload(torch, lerobot)
    report = {
        "profile": "worldepisode-lerobot-policy-compatibility-audit-0.1",
        "status": (
            "blocked_missing_required_observation_modality"
            if all_blocked_for_expected_reason
            else "unexpected_probe_result"
        ),
        "pass": False,
        "audit_valid": all_blocked_for_expected_reason,
        "lerobot_policy_requirements_version": LEROBOT_VERSION,
        "script": "tools/lerobot_policy_compatibility_audit.py",
        "script_sha256": sha256_file(Path(__file__)),
        "dataset": {
            "repo_id": DATASET_REPO_ID,
            "package_role": "random_episode_train_smoke_representative",
            "package_files": package_files(dataset_root),
            "loader": loader,
        },
        "environment": environment,
        "execution": {
            "started_utc": started_utc,
            "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "command": (
                "uv run --isolated --with 'lerobot[training,diffusion]==0.6.0' "
                "python tools/lerobot_policy_compatibility_audit.py --strict"
            ),
            "repository_commit": repository_commit,
            "host": {
                "uname": " ".join(platform.uname()),
                "machine": platform.machine(),
                "cpu_logical_count": os.cpu_count(),
                "total_ram_bytes": int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")),
                "storage_total_bytes": disk_usage.total,
                "storage_free_bytes": disk_usage.free,
                "gpu_info": ", ".join(
                    device["name"] for device in environment["cuda_devices"]
                ),
            },
            "compute": {
                "wall_time_seconds": round(wall_time_seconds, 6),
                "user_cpu_seconds": round(user_cpu_seconds, 6),
                "system_cpu_seconds": round(system_cpu_seconds, 6),
                "cpu_utilization_percent": round(
                    100.0 * (user_cpu_seconds + system_cpu_seconds) / wall_time_seconds,
                    6,
                ),
                "max_rss_bytes": max_rss_bytes,
            },
            "exit_status": 0 if all_blocked_for_expected_reason else 1,
            "runner": "remote_dgx_spark_uv_isolated",
        },
        "policy_probes": policy_results,
        "all_policy_probes_completed_training_step": all(
            result["training_step_completed"] for result in policy_results
        ),
        "all_policy_probes_blocked_for_expected_reason": all_blocked_for_expected_reason,
        "required_missing_modality": "observation image or semantically valid observation.environment_state",
        "claim_boundary": (
            "This probe validates the committed low-dimensional package loader and the pinned LeRobot "
            "ACT/Diffusion model-construction path. It is not a policy result. Both policies stop before "
            "training because joint proprioception alone does not satisfy their observation contract. "
            "Source videos were not mirrored, and joint positions must not be relabeled as environment state."
        ),
        "upstream_requirement_sources": {
            "act": (
                "https://github.com/huggingface/lerobot/blob/v0.6.0/"
                "src/lerobot/policies/act/configuration_act.py"
            ),
            "diffusion": (
                "https://github.com/huggingface/lerobot/blob/v0.6.0/"
                "src/lerobot/policies/diffusion/configuration_diffusion.py"
            ),
        },
        "artifacts": {
            "report": "docs/experiments/lerobot_policy_gate/policy_compatibility_report.json",
            "run_log": "docs/experiments/run_logs/lerobot_policy_compatibility_dgx_spark.log",
        },
    }
    return report, tracebacks


def render_log(report: dict[str, Any], tracebacks: dict[str, str]) -> str:
    environment = report["environment"]
    loader = report["dataset"]["loader"]
    lines = [
        "WorldEpisode LeRobot policy compatibility audit",
        f"status={report['status']}",
        f"host={environment['hostname']}",
        f"machine={environment['machine']}",
        f"python={environment['python_version']}",
        f"lerobot={environment['lerobot_version']}",
        f"torch={environment['torch_version']}",
        f"cuda_available={str(environment['cuda_available']).lower()}",
        f"cuda_devices={json.dumps(environment['cuda_devices'], sort_keys=True)}",
        f"dataset_episodes={loader['episode_count']}",
        f"dataset_frames={loader['frame_count']}",
        f"dataset_features={json.dumps(loader['feature_keys'])}",
        f"dataset_stats_features={json.dumps(loader['stats_feature_keys'])}",
        "",
    ]
    for result in report["policy_probes"]:
        policy = result["policy"]
        lines.extend(
            [
                f"[{policy}]",
                f"status={result['status']}",
                f"return_code={result['return_code']}",
                f"duration_seconds={result['duration_seconds']}",
                f"command={json.dumps(result['command_template'])}",
                tracebacks[policy],
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def validate_existing_report(report_path: Path, dataset_root: Path) -> list[str]:
    errors = []
    if not report_path.exists():
        return [f"missing report: {report_path}"]
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("profile") != "worldepisode-lerobot-policy-compatibility-audit-0.1":
        errors.append("unexpected report profile")
    if not report.get("audit_valid"):
        errors.append("compatibility audit is not valid")
    if report.get("lerobot_policy_requirements_version") != LEROBOT_VERSION:
        errors.append("LeRobot requirement version does not match the pinned audit version")
    if not report.get("all_policy_probes_blocked_for_expected_reason"):
        errors.append("policy probes did not all record the expected modality blocker")
    probes = report.get("policy_probes", [])
    if [probe.get("policy") for probe in probes] != list(POLICIES):
        errors.append("policy probe set does not match ACT and Diffusion")
    if report.get("dataset", {}).get("package_files") != package_files(dataset_root):
        errors.append("dataset package descriptors are stale")
    info = json.loads((dataset_root / "meta" / "info.json").read_text(encoding="utf-8"))
    loader = report.get("dataset", {}).get("loader", {})
    if loader.get("episode_count") != info.get("total_episodes"):
        errors.append("loader episode count does not match package metadata")
    if loader.get("frame_count") != info.get("total_frames"):
        errors.append("loader frame count does not match package metadata")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET_ROOT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--repository-commit", default="not_available")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    if args.check:
        errors = validate_existing_report(args.report, args.dataset_root)
        print(json.dumps({"valid": not errors, "errors": errors}, indent=2))
        return 1 if errors and args.strict else 0

    if args.work_dir is None:
        with tempfile.TemporaryDirectory(prefix="worldepisode-lerobot-policy-") as temporary:
            report, tracebacks = run_probe(
                args.dataset_root.resolve(),
                Path(temporary),
                args.repository_commit,
            )
    else:
        args.work_dir.mkdir(parents=True, exist_ok=True)
        report, tracebacks = run_probe(
            args.dataset_root.resolve(),
            args.work_dir.resolve(),
            args.repository_commit,
        )
    write_json(args.report, report)
    args.log.parent.mkdir(parents=True, exist_ok=True)
    args.log.write_text(render_log(report, tracebacks), encoding="utf-8")
    print(json.dumps({"status": report["status"], "audit_valid": report["audit_valid"]}, indent=2))
    return 1 if args.strict and not report["audit_valid"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
