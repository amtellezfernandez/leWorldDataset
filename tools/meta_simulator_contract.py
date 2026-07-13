#!/usr/bin/env python3
"""Generate the WorldEpisode meta-simulator adapter contract report.

The report defines the runtime-neutral compliance layers a simulator adapter must implement. It does
not certify simulator physical accuracy. It certifies whether an adapter exposes enough
WorldEpisode semantics to make replay, conversion loss, and cross-runtime drift auditable.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "experiments" / "meta_simulator_contract"
CONTROL_REPLAY_REPORT = ROOT / "docs" / "experiments" / "lerobot_control_replay" / "control_replay_report.json"


URDF_STUDIO_EVIDENCE = {
    "source": "URDF Studio sibling implementation",
    "repository": "amtellezfernandez/urdf-studio",
    "local_branch": "paper/cross-sim-benchmark",
    "observed_commit": "99f1bf0",
    "observed_on": "2026-07-13",
    "code_paths": [
        "backend/services/sim_backends/base.py",
        "backend/services/sim_backends/mujoco_backend.py",
        "backend/services/sim_backends/genesis_backend.py",
        "backend/scripts/scenario_run.py",
        "backend/tests/test_sim_backend_conformance.py",
    ],
    "conformance_smoke": {
        "command": (
            ".venv/bin/python3 -m pytest backend/tests/test_sim_backend_conformance.py "
            "backend/tests/test_scenario_run_orchestrator.py "
            "backend/tests/test_scenario_runner_mujoco.py "
            "backend/tests/test_world_layout_transfer_check_script.py"
        ),
        "result": "24 passed, 12 warnings in 27.22s",
        "covered_backends": ["fake", "mujoco", "genesis"],
    },
    "cross_sim_smoke": {
        "command": (
            ".venv/bin/python3 -m backend.scripts.scenario_run "
            "scenarios/carton_sorting_0001 --sim mujoco --sim genesis "
            "--out /tmp/urdf-studio-cross-sim-smoke --episodes 1"
        ),
        "schema": "scenario_comparison_report.v1",
        "scenario_id": "carton_sorting_0001",
        "backends": ["genesis", "mujoco"],
        "episodes": 1,
        "success_agreement_rate": 1.0,
        "mujoco_success_rate": 1.0,
        "genesis_success_rate": 1.0,
        "mean_time_to_success_s": {
            "mujoco": 4.999999999999671,
            "genesis": 5.0,
        },
        "final_object_pose_delta_m": {
            "carton_1": 0.059700834823395076,
        },
        "final_joint_rmse_rad": 0.050246577859076866,
        "trajectory_split": {
            "t_ms": 60,
            "metric": "joint_rmse_rad",
            "value": 0.06762661282092075,
            "threshold": 0.05,
        },
    },
    "claim_boundary": (
        "URDF Studio proves a shared episode-backend contract and one MuJoCo/Genesis scenario "
        "comparison. It does not prove Isaac or SAPIEN replay, and it is not the same as running "
        "the LeRobot control-replay trace through Genesis."
    ),
}


LAYERS = [
    {
        "layer_id": "META-SIM.001",
        "name": "invariant_interface",
        "description": (
            "Adapter ingests immutable world revisions, frame/clock graphs, entity identity, "
            "representation roles, action channels, asset digests, and quality records."
        ),
        "requirement_ids": [
            "WORLD.001",
            "TRACE.001",
            "FRAME.001",
            "FRAME.002",
            "TIME.001",
            "TIME.002",
            "ENTITY.001",
            "REP.001",
            "ACTION.001",
            "ACTION.002",
            "ASSET.001",
            "QUALITY.001",
        ],
    },
    {
        "layer_id": "META-SIM.002",
        "name": "asynchronous_schema_extension",
        "description": (
            "Adapter may register runtime-specific roles, events, material models, deformable "
            "metrics, or fluid/container states without weakening the core sidecar contract."
        ),
        "requirement_ids": ["REP.001", "ENTITY.001", "PROV.001", "CONVERT.001"],
    },
    {
        "layer_id": "META-SIM.003",
        "name": "deterministic_replay_accountability",
        "description": (
            "Adapter declares runtime, version, solver, timestep, actuator parameters, command and "
            "effective timestamps, latency model, initialization state, and tolerance envelope."
        ),
        "requirement_ids": ["REPLAY.001", "ACTION.002", "ACTION.004", "TIME.002", "CONVERT.001"],
    },
]


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def replay_evidence() -> dict[str, Any]:
    if not CONTROL_REPLAY_REPORT.exists():
        return {"available": False}
    report = load_json(CONTROL_REPLAY_REPORT)
    mujoco = report.get("simulators", {}).get("mujoco", {})
    isaac = report.get("simulators", {}).get("isaac", {})
    return {
        "available": bool(report.get("available")),
        "artifact": str(CONTROL_REPLAY_REPORT.relative_to(ROOT)),
        "mujoco": {
            "tested": bool(mujoco.get("tested")),
            "rmse_improvement_over_naive": mujoco.get("rmse_improvement_over_naive"),
            "adapter_contract": mujoco.get("adapter_contract", {}),
        },
        "isaac": {
            "ready": bool(isaac.get("ready")),
            "tested": bool(isaac.get("tested")),
            "reason": isaac.get("reason"),
            "adapter_contract": isaac.get("adapter_contract", {}),
        },
    }


def urdf_studio_evidence() -> dict[str, Any]:
    return URDF_STUDIO_EVIDENCE


def target_rows(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    mujoco_evidence = evidence.get("mujoco", {})
    isaac_evidence = evidence.get("isaac", {})
    urdf_evidence = evidence.get("urdf_studio", {})
    return [
        {
            "runtime_id": "mujoco",
            "runtime_family": "contact_dynamics",
            "adapter_status": (
                "tested_replay_and_urdf_studio_episode_backend"
                if mujoco_evidence.get("tested")
                else "urdf_studio_episode_backend_only"
            ),
            "implemented_layers": ["META-SIM.001", "META-SIM.003"] if mujoco_evidence.get("tested") else [],
            "extension_policy": "core rigid-body replay only in current artifact",
            "evidence": {
                "artifact": evidence.get("artifact"),
                "tested": mujoco_evidence.get("tested", False),
                "rmse_improvement_over_naive": mujoco_evidence.get("rmse_improvement_over_naive"),
                "urdf_studio": {
                    "source": urdf_evidence.get("source"),
                    "observed_commit": urdf_evidence.get("observed_commit"),
                    "conformance_smoke": urdf_evidence.get("conformance_smoke"),
                    "cross_sim_smoke": urdf_evidence.get("cross_sim_smoke"),
                },
            },
            "claim_boundary": (
                "WorldEpisode has one minimal six-joint MuJoCo replay adapter; URDF Studio also "
                "tests MuJoCo as an episode backend in the shared scenario runner."
            ),
        },
        {
            "runtime_id": "isaac_sim",
            "runtime_family": "gpu_parallel_simulation",
            "adapter_status": "adapter_contract_ready_untested" if isaac_evidence.get("ready") else "adapter_required",
            "implemented_layers": ["META-SIM.001", "META-SIM.003"] if isaac_evidence.get("ready") else [],
            "extension_policy": "ready mapping emitted; runtime execution not available in this environment",
            "evidence": {
                "artifact": evidence.get("artifact"),
                "ready": isaac_evidence.get("ready", False),
                "tested": isaac_evidence.get("tested", False),
                "reason": isaac_evidence.get("reason"),
            },
            "claim_boundary": "Adapter mapping only; no Isaac runtime result is claimed.",
        },
        {
            "runtime_id": "genesis",
            "runtime_family": "parallel_robotics_simulation",
            "adapter_status": "tested_urdf_studio_episode_backend",
            "implemented_layers": ["META-SIM.001", "META-SIM.003"],
            "extension_policy": (
                "URDF Studio compiles the same scenario scene, action interface, episode manifest, "
                "and trace/comparison report against Genesis. A WorldEpisode-native Genesis replay "
                "of the LeRobot control trace is still future work."
            ),
            "evidence": {
                "tested": True,
                "ready": True,
                "urdf_studio": {
                    "source": urdf_evidence.get("source"),
                    "observed_commit": urdf_evidence.get("observed_commit"),
                    "code_paths": urdf_evidence.get("code_paths"),
                    "conformance_smoke": urdf_evidence.get("conformance_smoke"),
                    "cross_sim_smoke": urdf_evidence.get("cross_sim_smoke"),
                },
            },
            "claim_boundary": (
                "Genesis is tested as a URDF Studio episode backend and in a one-episode "
                "MuJoCo/Genesis comparison; no LeRobot control-replay or Isaac/SAPIEN result is "
                "claimed."
            ),
        },
        {
            "runtime_id": "sapien",
            "runtime_family": "interactive_articulation_and_rendering",
            "adapter_status": "adapter_required",
            "implemented_layers": [],
            "extension_policy": (
                "Adapter should register articulation, contact, rendering, and optional soft-body "
                "extensions without changing the WorldEpisode core."
            ),
            "evidence": {"tested": False, "ready": False},
            "claim_boundary": "No SAPIEN adapter or runtime result is claimed.",
        },
    ]


def render_markdown(report: dict[str, Any]) -> str:
    rows = []
    for target in report["runtime_targets"]:
        rows.append(
            "| {runtime} | {status} | {layers} | {boundary} |".format(
                runtime=target["runtime_id"],
                status=target["adapter_status"],
                layers=", ".join(target["implemented_layers"]) or "none",
                boundary=target["claim_boundary"],
            )
        )
    layer_rows = []
    for layer in report["layers"]:
        layer_rows.append(
            f"| `{layer['layer_id']}` | {layer['name']} | {', '.join(layer['requirement_ids'])} |"
        )
    return f"""# Meta-Simulator Contract

Status: runtime-neutral adapter contract.

WorldEpisode does not privilege MuJoCo, Isaac Sim, Genesis, SAPIEN, or any future simulator. A
simulator becomes a trusted target only through an adapter that preserves the same sidecar
invariants and emits replay/loss evidence.

## Compliance Layers

| Layer | Name | Requirement IDs |
|---|---|---|
{chr(10).join(layer_rows)}

## Runtime Targets

| Runtime | Adapter Status | Implemented Layers | Claim Boundary |
|---|---|---|---|
{chr(10).join(rows)}

## Rule

WorldEpisode certifies adapter conformance, not simulator quality in the abstract. If a simulator
cannot ingest the invariant interface, declare extensions, and report deterministic replay
assumptions, then its dataset export is not replay-safe under the WorldEpisode profile.
"""


def build_meta_simulator_contract(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    evidence = replay_evidence()
    evidence["urdf_studio"] = urdf_studio_evidence()
    targets = target_rows(evidence)
    tested = sum(1 for target in targets if target["adapter_status"].startswith("tested"))
    ready_untested = sum(1 for target in targets if target["adapter_status"] == "adapter_contract_ready_untested")
    report = {
        "profile": "worldepisode-meta-simulator-contract-0.1",
        "status": "runtime_neutral_adapter_contract",
        "claim_boundary": (
            "The report defines adapter compliance. It does not claim equivalent physics or tested "
            "runtime results for every simulator."
        ),
        "urdf_studio_evidence": evidence["urdf_studio"],
        "layers": LAYERS,
        "runtime_targets": targets,
        "aggregate": {
            "runtime_target_count": len(targets),
            "tested_adapter_count": tested,
            "ready_untested_adapter_count": ready_untested,
            "adapter_required_count": len(targets) - tested - ready_untested,
            "compliance_layer_count": len(LAYERS),
        },
        "artifacts": {
            "report": str((output_dir / "adapter_contract_report.json").relative_to(ROOT)),
            "markdown": str((output_dir / "README.md").relative_to(ROOT)),
        },
    }
    write_json(output_dir / "adapter_contract_report.json", report)
    write_text(output_dir / "README.md", render_markdown(report))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    report = build_meta_simulator_contract(output_dir=args.output_dir)
    print(
        json.dumps(
            {
                "status": report["status"],
                "runtime_target_count": report["aggregate"]["runtime_target_count"],
                "tested_adapter_count": report["aggregate"]["tested_adapter_count"],
                "ready_untested_adapter_count": report["aggregate"]["ready_untested_adapter_count"],
                "adapter_required_count": report["aggregate"]["adapter_required_count"],
                "artifacts": report["artifacts"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
