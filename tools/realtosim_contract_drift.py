#!/usr/bin/env python3
"""Controlled real-to-sim contract-drift ablations for WorldEpisode.

This is not a physical robot rollout. It is a deterministic proxy that isolates two common
real-to-sim failure mechanisms:

1. an action vector that succeeds in a simulator because it is interpreted as absolute radians, but
   fails when deployed to hardware whose controller expects delta degrees;
2. an appearance-only reconstructed scene that succeeds in simulation because collision proxies are
   missing, but fails against the real collision geometry.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "experiments" / "realtosim_contract_drift"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def norm(values: list[float]) -> float:
    return math.sqrt(sum(value * value for value in values))


def vec_sub(left: list[float], right: list[float]) -> list[float]:
    return [a - b for a, b in zip(left, right, strict=True)]


def vec_add(left: list[float], right: list[float]) -> list[float]:
    return [a + b for a, b in zip(left, right, strict=True)]


def rad_to_deg(values: list[float]) -> list[float]:
    return [math.degrees(value) for value in values]


def deg_to_rad(values: list[float]) -> list[float]:
    return [math.radians(value) for value in values]


def action_contract_ablation() -> dict[str, Any]:
    start_rad = [0.0, -0.4, 0.7, 0.1, -0.2, 0.0]
    target_rad = [0.12, -0.25, 0.55, 0.22, -0.1, 0.08]
    tolerance_rad = 0.035

    # The simulator-only policy is trained and evaluated under an absolute-radian action interface.
    drifted_policy_output = target_rad
    drifted_sim_final = drifted_policy_output
    drifted_sim_error = norm(vec_sub(drifted_sim_final, target_rad))

    # The real controller for the source trajectory expects delta-degree commands. Deploying the
    # absolute-radian vector without the action contract therefore produces a tiny degree delta.
    drifted_real_delta_rad = deg_to_rad(drifted_policy_output)
    drifted_real_final = vec_add(start_rad, drifted_real_delta_rad)
    drifted_real_error = norm(vec_sub(drifted_real_final, target_rad))

    # With the WorldEpisode contract, the adapter knows the simulator policy output is an absolute
    # joint-radian target and converts it into the hardware delta-degree command.
    we_hardware_command_deg = rad_to_deg(vec_sub(target_rad, start_rad))
    we_real_final = vec_add(start_rad, deg_to_rad(we_hardware_command_deg))
    we_real_error = norm(vec_sub(we_real_final, target_rad))

    drifted_sim_success = drifted_sim_error <= tolerance_rad
    drifted_real_success = drifted_real_error <= tolerance_rad
    we_real_success = we_real_error <= tolerance_rad
    return {
        "name": "action_contract_drift",
        "failure_mode": (
            "A policy that succeeds in a simulator with absolute-radian actions is deployed to a "
            "controller whose source contract expects delta-degree commands."
        ),
        "worldepisode_requirement_ids": ["ACTION.001", "ACTION.002", "REPLAY.001", "CONVERT.001"],
        "start_rad": start_rad,
        "target_rad": target_rad,
        "tolerance_rad": tolerance_rad,
        "drifted": {
            "sim_action_interpretation": "absolute_joint_target_rad",
            "hardware_interpretation": "delta_joint_command_deg",
            "policy_output": drifted_policy_output,
            "sim_error_rad": drifted_sim_error,
            "sim_success": drifted_sim_success,
            "deployment_error_rad": drifted_real_error,
            "deployment_success": drifted_real_success,
            "failure_at_first_control_cycle": not drifted_real_success,
        },
        "worldepisode": {
            "action_contract": {
                "policy_output_units": "rad",
                "policy_output_semantics": "absolute",
                "hardware_command_units": "deg",
                "hardware_command_semantics": "delta",
                "reference_frame": "joint_space",
                "command_timestamp_semantics": "policy_sample_time",
                "effective_timestamp_semantics": "motor_apply_time",
            },
            "converted_hardware_command_deg": we_hardware_command_deg,
            "deployment_error_rad": we_real_error,
            "deployment_success": we_real_success,
        },
        "success_gap_sim_to_deployment": int(drifted_sim_success) - int(drifted_real_success),
    }


def point_in_rect(point: tuple[float, float], rect: dict[str, float]) -> bool:
    x, y = point
    return rect["xmin"] <= x <= rect["xmax"] and rect["ymin"] <= y <= rect["ymax"]


def interpolate_path(points: list[tuple[float, float]], samples_per_segment: int = 25) -> list[tuple[float, float]]:
    samples: list[tuple[float, float]] = []
    for start, end in zip(points, points[1:]):
        for step in range(samples_per_segment):
            alpha = step / samples_per_segment
            samples.append(
                (
                    start[0] * (1.0 - alpha) + end[0] * alpha,
                    start[1] * (1.0 - alpha) + end[1] * alpha,
                )
            )
    samples.append(points[-1])
    return samples


def first_collision(path: list[tuple[float, float]], rect: dict[str, float]) -> int | None:
    for index, point in enumerate(path):
        if point_in_rect(point, rect):
            return index
    return None


def representation_role_ablation() -> dict[str, Any]:
    start = (0.0, 0.0)
    target = (1.0, 0.0)
    collision_proxy = {"xmin": 0.43, "xmax": 0.57, "ymin": -0.08, "ymax": 0.08}

    straight_path = interpolate_path([start, target])
    detour_path = interpolate_path([start, (0.42, 0.22), (0.58, 0.22), target])
    straight_collision = first_collision(straight_path, collision_proxy)
    detour_collision = first_collision(detour_path, collision_proxy)

    drifted_sim_success = True  # collision proxy was dropped, so the simulator reports no contact.
    drifted_real_success = straight_collision is None
    worldepisode_success = detour_collision is None
    return {
        "name": "representation_role_drift",
        "failure_mode": (
            "A real-to-sim export keeps the Gaussian visual layer but drops the collision role, so "
            "a straight-line policy succeeds in simulation and collides with the real foreground object."
        ),
        "worldepisode_requirement_ids": ["REP.001", "ENTITY.001", "WORLD.001", "REPLAY.001"],
        "roles": {
            "appearance": "gaussian_splat_visual_context",
            "collision": "box_collision_proxy",
            "semantics": "foreground_obstacle",
        },
        "collision_proxy": collision_proxy,
        "drifted": {
            "exported_roles": ["appearance"],
            "sim_collision_proxy_present": False,
            "planned_path": "straight_line",
            "sim_success": drifted_sim_success,
            "real_collision_step": straight_collision,
            "deployment_success": drifted_real_success,
        },
        "worldepisode": {
            "exported_roles": ["appearance", "collision", "semantics"],
            "sim_collision_proxy_present": True,
            "planned_path": "role_aware_detour",
            "real_collision_step": detour_collision,
            "deployment_success": worldepisode_success,
        },
        "success_gap_sim_to_deployment": int(drifted_sim_success) - int(drifted_real_success),
    }


def render_markdown(report: dict[str, Any]) -> str:
    action = report["ablations"]["action_contract_drift"]
    roles = report["ablations"]["representation_role_drift"]
    return f"""# Real-to-Sim Contract Drift

Status: controlled proxy experiment, not a physical hardware rollout.

This artifact positions WorldEpisode as the contract layer for real-to-sim pipelines such as
Gaussian-splat/OpenUSD reconstruction systems. The question is not whether splats are visually
useful; the question is whether the reconstructed world, action interface, physical roles, and
deployment assumptions remain bound to the robot episode.

## Results

| Ablation | Sim Success With Drifted Contract | Deployment Success With Drifted Contract | Deployment Success With WorldEpisode Contract |
|---|---:|---:|---:|
| Action contract drift | {action["drifted"]["sim_success"]} | {action["drifted"]["deployment_success"]} | {action["worldepisode"]["deployment_success"]} |
| Representation-role drift | {roles["drifted"]["sim_success"]} | {roles["drifted"]["deployment_success"]} | {roles["worldepisode"]["deployment_success"]} |

## Interpretation

The action ablation shows a simulated policy that succeeds when actions are interpreted as absolute
radian joint targets. The same vector fails immediately under the deployment controller because the
source hardware contract expects delta-degree commands. WorldEpisode prevents that drift by making
the policy-side and hardware-side action contracts explicit.

The representation ablation shows an appearance-only real-to-sim export that drops the collision
role. The straight-line policy succeeds in simulation because the collision proxy is absent, then
collides with the real foreground geometry. WorldEpisode prevents that drift by requiring the same
entity to carry explicit appearance, collision, and semantic roles.
"""


def build_realtosim_contract_drift(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    action = action_contract_ablation()
    roles = representation_role_ablation()
    report = {
        "profile": "worldepisode-realtosim-contract-drift-0.1",
        "status": "controlled_proxy_not_hardware_rollout",
        "claim_boundary": (
            "This deterministic experiment isolates contract drift mechanisms. It does not claim a "
            "measured real-robot deployment result."
        ),
        "hype_cycle_positioning": (
            "Real-to-sim systems can reconstruct visually faithful and physically useful scenes. "
            "WorldEpisode defines the cross-container contract that keeps those scenes tied to the "
            "episode, action interface, physical roles, and replay assumptions."
        ),
        "ablations": {
            "action_contract_drift": action,
            "representation_role_drift": roles,
        },
        "aggregate": {
            "ablation_count": 2,
            "drifted_sim_successes": sum(int(item["drifted"]["sim_success"]) for item in (action, roles)),
            "drifted_deployment_successes": sum(
                int(item["drifted"]["deployment_success"]) for item in (action, roles)
            ),
            "worldepisode_deployment_successes": sum(
                int(item["worldepisode"]["deployment_success"]) for item in (action, roles)
            ),
        },
        "artifacts": {
            "report": str((output_dir / "contract_drift_report.json").relative_to(ROOT)),
            "markdown": str((output_dir / "README.md").relative_to(ROOT)),
        },
    }
    write_json(output_dir / "contract_drift_report.json", report)
    write_text(output_dir / "README.md", render_markdown(report))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    report = build_realtosim_contract_drift(output_dir=args.output_dir)
    print(
        json.dumps(
            {
                "status": report["status"],
                "ablation_count": report["aggregate"]["ablation_count"],
                "drifted_sim_successes": report["aggregate"]["drifted_sim_successes"],
                "drifted_deployment_successes": report["aggregate"]["drifted_deployment_successes"],
                "worldepisode_deployment_successes": report["aggregate"]["worldepisode_deployment_successes"],
                "artifacts": report["artifacts"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
