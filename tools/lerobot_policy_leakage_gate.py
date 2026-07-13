#!/usr/bin/env python3
"""Prepare the ACT/Diffusion leakage gate from a WorldEpisode split manifest.

This tool does not pretend that a generated plan is a result. It turns the committed
WorldEpisode split manifest into concrete LeRobot-native training/evaluation jobs and records the
exact artifacts required before the paper can claim ACT/Diffusion or rollout evidence.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SPLIT_MANIFEST = ROOT / "docs" / "experiments" / "lerobot_scene_leakage" / "split_manifest.json"
DEFAULT_LEAKAGE_REPORT = ROOT / "docs" / "experiments" / "lerobot_scene_leakage" / "leakage_report.json"
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "experiments" / "lerobot_policy_gate"
DEFAULT_POLICIES = ("act", "diffusion")
DEFAULT_DEVICE = "cuda"
DEFAULT_STEPS = 20000
DEFAULT_SEED = 17


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


def sanitize(value: str) -> str:
    return value.replace("/", "__").replace(":", "_").replace("@", "_").replace("-", "_")


def shell_join(command: list[str]) -> str:
    return " ".join(subprocess.list2cmdline([part]) for part in command)


def detect_environment() -> dict[str, Any]:
    return {
        "lerobot_importable": importlib.util.find_spec("lerobot") is not None,
        "lerobot_train": shutil.which("lerobot-train"),
        "lerobot_eval": shutil.which("lerobot-eval"),
        "lerobot_rollout": shutil.which("lerobot-rollout"),
        "python": shutil.which("python3") or shutil.which("python"),
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
    }


def split_counts(split: dict[str, Any]) -> dict[str, Any]:
    return {
        "train_count": int(split["train_count"]),
        "test_count": int(split["test_count"]),
        "train_world_lineage_count": int(split["train_world_lineage_count"]),
        "test_world_lineage_count": int(split["test_world_lineage_count"]),
        "test_leaked_episode_count": int(split["test_leaked_episode_count"]),
        "leakage_rate": float(split["leakage_rate"]),
        "heldout_task_indices": split.get("heldout_task_indices", []),
    }


def write_allowlists(output_dir: Path, split_name: str, split: dict[str, Any]) -> dict[str, str]:
    split_dir = output_dir / "episode_allowlists" / split_name
    train_path = split_dir / "train_episodes.json"
    test_path = split_dir / "test_episodes.json"
    both_path = split_dir / "split_episodes.json"
    train_payload = {
        "split": split_name,
        "partition": "train",
        "episode_indices": split["train_episodes"],
        "episode_count": split["train_count"],
    }
    test_payload = {
        "split": split_name,
        "partition": "test",
        "episode_indices": split["test_episodes"],
        "episode_count": split["test_count"],
    }
    write_json(train_path, train_payload)
    write_json(test_path, test_payload)
    write_json(
        both_path,
        {
            "split": split_name,
            "profile": "worldepisode-policy-leakage-episodes-0.1",
            "train": train_payload,
            "test": test_payload,
            "leakage": split_counts(split),
        },
    )
    return {
        "train": rel(train_path),
        "test": rel(test_path),
        "combined": rel(both_path),
    }


def materialized_repo_id(source_repo_id: str, split_name: str, partition: str) -> str:
    source_name = source_repo_id.split("/")[-1].lower()
    return f"worldepisode/{source_name}_{split_name}_{partition}"


def train_command(
    policy: str,
    dataset_repo_id: str,
    output_dir: str,
    job_name: str,
    device: str,
    steps: int,
    seed: int,
    wandb: bool,
) -> list[str]:
    return [
        "lerobot-train",
        f"--dataset.repo_id={dataset_repo_id}",
        f"--policy.type={policy}",
        f"--output_dir={output_dir}",
        f"--job_name={job_name}",
        f"--policy.device={device}",
        f"--steps={steps}",
        f"--seed={seed}",
        f"--wandb.enable={str(wandb).lower()}",
    ]


def eval_command(policy_path: str, env_type: str, env_task: str, device: str, n_episodes: int) -> list[str]:
    return [
        "lerobot-eval",
        f"--policy.path={policy_path}",
        f"--env.type={env_type}",
        f"--env.task={env_task}",
        f"--policy.device={device}",
        f"--eval.n_episodes={n_episodes}",
    ]


def rollout_command(policy_path: str, robot_type: str, n_episodes: int) -> list[str]:
    return [
        "lerobot-rollout",
        f"--policy.path={policy_path}",
        f"--robot.type={robot_type}",
        f"--eval.n_episodes={n_episodes}",
    ]


def make_jobs(
    split_manifest: dict[str, Any],
    output_dir: Path,
    policies: list[str],
    device: str,
    steps: int,
    seed: int,
    wandb: bool,
    rollout_episodes: int,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, str]]:
    repo_id = split_manifest["repo_id"]
    revision = split_manifest["revision"]
    split_artifacts: dict[str, str] = {}
    jobs: list[dict[str, Any]] = []
    run_lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        "# Materialize each split dataset first; see policy_gate_report.json for allowlists.",
        "",
    ]

    for split_name, split in sorted(split_manifest["splits"].items()):
        split_artifacts.update({f"{split_name}_{key}": value for key, value in write_allowlists(output_dir, split_name, split).items()})
        train_repo = materialized_repo_id(repo_id, split_name, "train")
        test_repo = materialized_repo_id(repo_id, split_name, "test")
        for policy in policies:
            job_name = f"{policy}_{split_name}_worldepisode_leakage"
            policy_output = f"outputs/policy_leakage/{job_name}"
            policy_path = f"{policy_output}/checkpoints/last/pretrained_model"
            train = train_command(
                policy=policy,
                dataset_repo_id=train_repo,
                output_dir=policy_output,
                job_name=job_name,
                device=device,
                steps=steps,
                seed=seed,
                wandb=wandb,
            )
            offline_eval = {
                "required_report": f"docs/experiments/lerobot_policy_gate/results/{job_name}/offline_action_eval.json",
                "dataset_repo_id": test_repo,
                "episode_allowlist": rel(output_dir / "episode_allowlists" / split_name / "test_episodes.json"),
                "metrics": [
                    "episode_normalized_rmse_mean",
                    "episode_normalized_rmse_median",
                    "episode_success_rate_at_declared_threshold",
                    "per_world_lineage_success_rate",
                ],
                "note": (
                    "Run policy inference over the materialized held-out test split and write this report. "
                    "The repository does not claim this result until the report exists."
                ),
            }
            sim_eval = eval_command(
                policy_path=policy_path,
                env_type="isaaclab_arena_or_registered_worldepisode_env",
                env_task="MATCH_WORLD_LINEAGE_HELDOUT_TASK",
                device=device,
                n_episodes=rollout_episodes,
            )
            physical_rollout = rollout_command(
                policy_path=policy_path,
                robot_type="so101",
                n_episodes=rollout_episodes,
            )
            run_lines.extend(
                [
                    f"# {policy} on {split_name}",
                    shell_join(train),
                    "",
                ]
            )
            jobs.append(
                {
                    "job_id": job_name,
                    "policy_type": policy,
                    "split": split_name,
                    "source_dataset": {
                        "repo_id": repo_id,
                        "revision": revision,
                    },
                    "materialized_datasets_required": {
                        "train_repo_id": train_repo,
                        "test_repo_id": test_repo,
                        "train_allowlist": rel(output_dir / "episode_allowlists" / split_name / "train_episodes.json"),
                        "test_allowlist": rel(output_dir / "episode_allowlists" / split_name / "test_episodes.json"),
                    },
                    "train": {
                        "command": train,
                        "shell": shell_join(train),
                        "expected_checkpoint": policy_path,
                    },
                    "offline_action_eval": offline_eval,
                    "high_fidelity_sim_eval": {
                        "command_template": sim_eval,
                        "shell_template": shell_join(sim_eval),
                        "requires_env_binding": True,
                        "required": True,
                    },
                    "physical_rollout": {
                        "command_template": physical_rollout,
                        "shell_template": shell_join(physical_rollout),
                        "requires_robot_binding": True,
                        "required_for_full_claim": True,
                    },
                    "required_result_files": [
                        f"docs/experiments/lerobot_policy_gate/results/{job_name}/train_metrics.json",
                        f"docs/experiments/lerobot_policy_gate/results/{job_name}/offline_action_eval.json",
                        f"docs/experiments/lerobot_policy_gate/results/{job_name}/rollout_report.json",
                    ],
                }
            )

    script_path = output_dir / "run_lerobot_policy_jobs.sh"
    write_text(script_path, "\n".join(run_lines) + "\n")
    script_path.chmod(0o755)
    rollout_contract = {
        "profile": "worldepisode-policy-rollout-gate-0.1",
        "minimum_rollout_episodes_per_policy_split": rollout_episodes,
        "required_policy_types": policies,
        "required_splits": sorted(split_manifest["splits"].keys()),
        "required_metrics": [
            "train_loss_curve",
            "offline_action_nrmse_by_episode",
            "success_rate_by_split",
            "success_rate_by_world_lineage",
            "failure_modes",
            "video_or_trace_uris_with_sha256",
            "simulator_or_robot_runtime_manifest",
        ],
        "acceptance_rule": (
            "The leakage claim is closed only when ACT or Diffusion reports exist for both random_episode "
            "and scene_disjoint splits, and at least one high-fidelity simulator or physical rollout report "
            "is available with the same split manifest."
        ),
        "sim_ready_but_not_executed_here": True,
    }
    return jobs, rollout_contract, {"run_script": rel(script_path), **split_artifacts}


def existing_result_files(jobs: list[dict[str, Any]]) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for job in jobs:
        present = [path for path in job["required_result_files"] if (ROOT / path).exists()]
        found[job["job_id"]] = present
    return found


def gate_satisfied(jobs: list[dict[str, Any]], result_files: dict[str, list[str]]) -> bool:
    if not jobs:
        return False
    return all(len(result_files[job["job_id"]]) == len(job["required_result_files"]) for job in jobs)


def execute_jobs(jobs: list[dict[str, Any]], dry_run: bool) -> list[dict[str, Any]]:
    executions: list[dict[str, Any]] = []
    if dry_run:
        return executions
    for job in jobs:
        command = job["train"]["command"]
        completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
        executions.append(
            {
                "job_id": job["job_id"],
                "command": command,
                "returncode": completed.returncode,
                "stdout_tail": completed.stdout[-4000:],
                "stderr_tail": completed.stderr[-4000:],
            }
        )
        if completed.returncode != 0:
            break
    return executions


def build_policy_gate(
    split_manifest_path: Path,
    leakage_report_path: Path,
    output_dir: Path,
    policies: list[str],
    device: str,
    steps: int,
    seed: int,
    wandb: bool,
    rollout_episodes: int,
    execute: bool,
) -> dict[str, Any]:
    split_manifest = load_json(split_manifest_path)
    leakage_report = load_json(leakage_report_path) if leakage_report_path.exists() else {}
    output_dir.mkdir(parents=True, exist_ok=True)
    jobs, rollout_contract, artifacts = make_jobs(
        split_manifest=split_manifest,
        output_dir=output_dir,
        policies=policies,
        device=device,
        steps=steps,
        seed=seed,
        wandb=wandb,
        rollout_episodes=rollout_episodes,
    )
    environment = detect_environment()
    result_files = existing_result_files(jobs)
    ready_to_execute = bool(environment["lerobot_train"]) and environment["lerobot_importable"]
    executions = execute_jobs(jobs, dry_run=not execute)
    if execute:
        result_files = existing_result_files(jobs)

    split_summary = {
        name: split_counts(split)
        for name, split in sorted(split_manifest["splits"].items())
    }
    report = {
        "profile": "worldepisode-act-diffusion-leakage-gate-0.1",
        "available": True,
        "pass": gate_satisfied(jobs, result_files),
        "status": "closed" if gate_satisfied(jobs, result_files) else "ready_not_executed",
        "source_split_manifest": rel(split_manifest_path),
        "source_leakage_report": rel(leakage_report_path),
        "source_dataset": {
            "repo_id": split_manifest["repo_id"],
            "revision": split_manifest["revision"],
            "teleoperated_reference_episodes": leakage_report.get("dataset", {}).get("teleoperated_reference_episodes"),
            "robot_type": leakage_report.get("dataset", {}).get("robot_type", "so101"),
        },
        "splits": split_summary,
        "policies": policies,
        "environment": environment,
        "ready_to_execute": ready_to_execute,
        "jobs": jobs,
        "rollout_contract": rollout_contract,
        "result_files_present": result_files,
        "executions": executions,
        "closure_required": [
            "materialize train/test LeRobot datasets from the allowlists without changing episode membership",
            "train ACT and Diffusion Policy on random_episode and scene_disjoint train datasets",
            "evaluate each checkpoint on the corresponding test split with action-error metrics",
            "run at least one high-fidelity simulator or physical rollout using the same split manifest",
            "commit train metrics, offline action metrics, rollout reports, and digest-verified videos/traces",
        ],
        "artifacts": {
            "report": rel(output_dir / "policy_gate_report.json"),
            "jobs": rel(output_dir / "train_eval_jobs.json"),
            "rollout_contract": rel(output_dir / "rollout_contract.json"),
            **artifacts,
        },
    }
    write_json(output_dir / "train_eval_jobs.json", jobs)
    write_json(output_dir / "rollout_contract.json", rollout_contract)
    write_json(output_dir / "policy_gate_report.json", report)
    write_text(
        output_dir / "README.md",
        render_readme(report),
    )
    return report


def render_readme(report: dict[str, Any]) -> str:
    job_rows = "\n".join(
        f"| `{job['job_id']}` | `{job['policy_type']}` | `{job['split']}` | `{job['materialized_datasets_required']['train_repo_id']}` |"
        for job in report["jobs"]
    )
    return f"""# LeRobot ACT/Diffusion Leakage Gate

Status: {report["status"]}

This directory is the executable gate for the reviewer concern that the leakage result must be
tested with stronger LeRobot-native policies. It is intentionally not marked closed until ACT or
Diffusion checkpoints, offline action-evaluation reports, and rollout reports are present.

Source split manifest: `{report["source_split_manifest"]}`

## Jobs

| Job | Policy | Split | Materialized train dataset |
|---|---|---|---|
{job_rows}

## Run

1. Materialize the train/test datasets listed in `train_eval_jobs.json` from the episode allowlists.
2. Run `bash {report["artifacts"]["run_script"]}` in an environment with LeRobot installed.
3. Evaluate each checkpoint with the offline action-evaluation contract.
4. Run `lerobot-eval` in a high-fidelity environment or `lerobot-rollout` on hardware.
5. Save the required result files listed per job.

The gate remains open while `policy_gate_report.json` has `"pass": false`.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split-manifest", type=Path, default=DEFAULT_SPLIT_MANIFEST)
    parser.add_argument("--leakage-report", type=Path, default=DEFAULT_LEAKAGE_REPORT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--policies", default=",".join(DEFAULT_POLICIES))
    parser.add_argument("--device", default=DEFAULT_DEVICE)
    parser.add_argument("--steps", type=int, default=DEFAULT_STEPS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--wandb", action="store_true")
    parser.add_argument("--rollout-episodes", type=int, default=20)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--required", action="store_true")
    args = parser.parse_args()

    policies = [policy.strip() for policy in args.policies.split(",") if policy.strip()]
    report = build_policy_gate(
        split_manifest_path=args.split_manifest,
        leakage_report_path=args.leakage_report,
        output_dir=args.output_dir,
        policies=policies,
        device=args.device,
        steps=args.steps,
        seed=args.seed,
        wandb=args.wandb,
        rollout_episodes=args.rollout_episodes,
        execute=args.execute,
    )
    print(json.dumps({key: report[key] for key in ("status", "pass", "ready_to_execute", "artifacts")}, indent=2))
    return 1 if args.required and not report["pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
