#!/usr/bin/env python3
"""Run one pinned ACT and Diffusion training step on a video-materialized split."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import resource
import shutil
import socket
import tempfile
import time
from pathlib import Path
from typing import Any

from tools.lerobot_policy_compatibility_audit import (
    DATASET_REPO_ID,
    LEROBOT_VERSION,
    POLICIES,
    environment_payload,
    package_files,
    probe_policy,
    sha256_file,
    write_json,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET_ROOT = (
    ROOT
    / "docs"
    / "experiments"
    / "lerobot_policy_gate"
    / "physical_splits"
    / "random_episode_train"
)
DEFAULT_ASSET_PLAN = (
    ROOT
    / "docs"
    / "experiments"
    / "lerobot_policy_gate"
    / "front_camera_asset_manifest.json"
)
DEFAULT_MATERIALIZATION_REPORT = (
    ROOT
    / "docs"
    / "experiments"
    / "lerobot_policy_gate"
    / "front_camera_materialization_report.json"
)
DEFAULT_REPORT = (
    ROOT
    / "docs"
    / "experiments"
    / "lerobot_policy_gate"
    / "policy_vision_smoke_report.json"
)
DEFAULT_LOG = (
    ROOT
    / "docs"
    / "experiments"
    / "run_logs"
    / "lerobot_policy_vision_smoke_dgx_spark.log"
)
PROFILE = "worldepisode-lerobot-policy-vision-smoke-0.1"


def file_descriptor(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(ROOT)),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def run_probe(
    dataset_root: Path,
    work_dir: Path,
    repository_commit: str,
    asset_plan_path: Path,
    materialization_report_path: Path,
) -> tuple[dict[str, Any], dict[str, str]]:
    started_utc = dt.datetime.now(dt.timezone.utc).isoformat()
    started = time.perf_counter()
    self_before = resource.getrusage(resource.RUSAGE_SELF)
    children_before = resource.getrusage(resource.RUSAGE_CHILDREN)

    import lerobot
    import torch
    from lerobot.datasets import LeRobotDataset

    if lerobot.__version__ != LEROBOT_VERSION:
        raise RuntimeError(f"expected LeRobot {LEROBOT_VERSION}, found {lerobot.__version__}")

    dataset = LeRobotDataset(DATASET_REPO_ID, root=dataset_root)
    sample = dataset[0]
    image_keys = sorted(
        key
        for key in dataset.features
        if key.startswith("observation.images.")
    )
    loader = {
        "success": True,
        "episode_count": dataset.num_episodes,
        "frame_count": dataset.num_frames,
        "feature_keys": sorted(dataset.features),
        "image_feature_keys": image_keys,
        "stats_feature_keys": sorted(dataset.meta.stats or {}),
        "sample_shapes": {
            key: list(value.shape)
            for key, value in sorted(sample.items())
            if hasattr(value, "shape")
        },
    }

    results = []
    traces: dict[str, str] = {}
    for policy in POLICIES:
        result, trace = probe_policy(policy, dataset_root, work_dir)
        results.append(result)
        traces[policy] = trace
    all_completed = bool(image_keys) and all(
        result["training_step_completed"] for result in results
    )

    self_after = resource.getrusage(resource.RUSAGE_SELF)
    children_after = resource.getrusage(resource.RUSAGE_CHILDREN)
    wall_time = time.perf_counter() - started
    user_cpu = (
        self_after.ru_utime
        - self_before.ru_utime
        + children_after.ru_utime
        - children_before.ru_utime
    )
    system_cpu = (
        self_after.ru_stime
        - self_before.ru_stime
        + children_after.ru_stime
        - children_before.ru_stime
    )
    disk = shutil.disk_usage(dataset_root)
    environment = environment_payload(torch, lerobot)
    report = {
        "profile": PROFILE,
        "status": "training_step_smoke_passed" if all_completed else "vision_smoke_failed",
        "pass": all_completed,
        "lerobot_version": LEROBOT_VERSION,
        "script": "tools/lerobot_policy_vision_smoke.py",
        "script_sha256": sha256_file(Path(__file__)),
        "dataset": {
            "repo_id": DATASET_REPO_ID,
            "package_role": "front_camera_random_episode_train_smoke",
            "package_files": package_files(dataset_root),
            "loader": loader,
        },
        "media_integrity": {
            "asset_plan": file_descriptor(asset_plan_path),
            "materialization_report": file_descriptor(materialization_report_path),
        },
        "environment": environment,
        "execution": {
            "started_utc": started_utc,
            "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "repository_commit": repository_commit,
            "command": (
                "uv run --isolated --with 'lerobot[training,diffusion]==0.6.0' "
                "python tools/lerobot_policy_vision_smoke.py --strict"
            ),
            "host": {
                "hostname": socket.gethostname(),
                "uname": " ".join(platform.uname()),
                "machine": platform.machine(),
                "cpu_logical_count": os.cpu_count(),
                "total_ram_bytes": int(
                    os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
                ),
                "storage_total_bytes": disk.total,
                "storage_free_bytes": disk.free,
                "gpu_info": ", ".join(
                    device["name"] for device in environment["cuda_devices"]
                ),
            },
            "compute": {
                "wall_time_seconds": round(wall_time, 6),
                "user_cpu_seconds": round(user_cpu, 6),
                "system_cpu_seconds": round(system_cpu, 6),
                "cpu_utilization_percent": round(
                    100.0 * (user_cpu + system_cpu) / wall_time,
                    6,
                ),
                "max_rss_bytes": int(
                    max(self_after.ru_maxrss, children_after.ru_maxrss) * 1024
                ),
            },
            "exit_status": 0 if all_completed else 1,
            "runner": "remote_dgx_spark_uv_isolated",
        },
        "policy_probes": results,
        "all_policy_probes_completed_training_step": all_completed,
        "claim_boundary": (
            "This one-step probe validates source-image decoding and pinned ACT/Diffusion "
            "training-input compatibility. A completed optimization step is not a policy-quality "
            "or rollout result."
        ),
        "artifacts": {
            "report": "docs/experiments/lerobot_policy_gate/policy_vision_smoke_report.json",
            "run_log": "docs/experiments/run_logs/lerobot_policy_vision_smoke_dgx_spark.log",
        },
    }
    return report, traces


def render_log(report: dict[str, Any], traces: dict[str, str]) -> str:
    loader = report["dataset"]["loader"]
    environment = report["environment"]
    lines = [
        "WorldEpisode LeRobot front-camera policy vision smoke",
        f"status={report['status']}",
        f"host={environment['hostname']}",
        f"python={environment['python_version']}",
        f"lerobot={environment['lerobot_version']}",
        f"torch={environment['torch_version']}",
        f"cuda_available={str(environment['cuda_available']).lower()}",
        f"image_features={json.dumps(loader['image_feature_keys'])}",
        f"sample_shapes={json.dumps(loader['sample_shapes'], sort_keys=True)}",
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
                traces[policy],
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def validate_report(report_path: Path, asset_plan_path: Path) -> list[str]:
    if not report_path.exists():
        return [f"missing vision smoke report: {report_path}"]
    report = json.loads(report_path.read_text(encoding="utf-8"))
    errors = []
    if report.get("profile") != PROFILE:
        errors.append("unexpected vision smoke profile")
    if not report.get("pass"):
        errors.append("vision smoke did not pass")
    if report.get("script_sha256") != sha256_file(Path(__file__)):
        errors.append("vision smoke report script digest is stale")
    if [item.get("policy") for item in report.get("policy_probes", [])] != list(POLICIES):
        errors.append("vision smoke policy set is not ACT and Diffusion")
    if not report.get("all_policy_probes_completed_training_step"):
        errors.append("not every policy completed a training step")
    expected_plan = file_descriptor(asset_plan_path)
    if report.get("media_integrity", {}).get("asset_plan") != expected_plan:
        errors.append("vision smoke asset-plan descriptor is stale")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET_ROOT)
    parser.add_argument("--asset-plan", type=Path, default=DEFAULT_ASSET_PLAN)
    parser.add_argument(
        "--materialization-report",
        type=Path,
        default=DEFAULT_MATERIALIZATION_REPORT,
    )
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--repository-commit", default="not_available")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    if args.check:
        errors = validate_report(args.report, args.asset_plan)
        print(json.dumps({"valid": not errors, "errors": errors}, indent=2))
        return 1 if args.strict and errors else 0

    if args.work_dir is None:
        with tempfile.TemporaryDirectory(prefix="worldepisode-lerobot-vision-") as temporary:
            report, traces = run_probe(
                args.dataset_root.resolve(),
                Path(temporary),
                args.repository_commit,
                args.asset_plan.resolve(),
                args.materialization_report.resolve(),
            )
    else:
        args.work_dir.mkdir(parents=True, exist_ok=True)
        report, traces = run_probe(
            args.dataset_root.resolve(),
            args.work_dir.resolve(),
            args.repository_commit,
            args.asset_plan.resolve(),
            args.materialization_report.resolve(),
        )
    write_json(args.report, report)
    args.log.parent.mkdir(parents=True, exist_ok=True)
    args.log.write_text(render_log(report, traces), encoding="utf-8")
    print(json.dumps({"status": report["status"], "pass": report["pass"]}, indent=2))
    return 1 if args.strict and not report["pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
