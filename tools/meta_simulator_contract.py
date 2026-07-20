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
CONTACT_RICH_REPLAY_REPORT = (
    ROOT
    / "docs"
    / "experiments"
    / "contact_rich_replay"
    / "contact_rich_replay_report.json"
)


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
    genesis = report.get("simulators", {}).get("genesis", {})
    isaac = report.get("simulators", {}).get("isaac", {})
    contact = {}
    if CONTACT_RICH_REPLAY_REPORT.exists():
        contact_report = load_json(CONTACT_RICH_REPLAY_REPORT)
        if (
            contact_report.get("analysis", {})
            .get("acceptance", {})
            .get("pass")
            is True
        ):
            contact = {
                "artifact": str(CONTACT_RICH_REPLAY_REPORT.relative_to(ROOT)),
                "task_count": len(contact_report["analysis"]["tasks"]),
                "scenario_count": contact_report["analysis"]["aggregate"][
                    "scenario_count"
                ],
                "contact_f1": contact_report["analysis"]["aggregate"][
                    "contact_f1"
                ]["estimate"],
                "task_outcome_agreement": contact_report["analysis"]["aggregate"][
                    "task_outcome_agreement"
                ]["estimate"],
                "final_orientation_error_deg": contact_report["analysis"][
                    "aggregate"
                ]["final_orientation_error_deg"]["estimate"],
                "claim_boundary": contact_report["claim_boundary"],
            }
    return {
        "available": bool(report.get("available")),
        "artifact": str(CONTROL_REPLAY_REPORT.relative_to(ROOT)),
        "contact_rich": contact,
        "mujoco": {
            "tested": bool(mujoco.get("tested")),
            "rmse_improvement_over_naive": mujoco.get("rmse_improvement_over_naive"),
            "adapter_contract": mujoco.get("adapter_contract", {}),
        },
        "genesis": {
            "tested": bool(genesis.get("tested")),
            "ready": bool(genesis.get("ready")),
            "runtime": genesis.get("runtime", {}),
            "rmse_improvement_over_naive": genesis.get("rmse_improvement_over_naive"),
            "naive_command_time": genesis.get("naive_command_time", {}),
            "timestamp_aware": genesis.get("timestamp_aware", {}),
            "claim_boundary": genesis.get("claim_boundary"),
        },
        "isaac": {
            "ready": bool(isaac.get("ready")),
            "tested": bool(isaac.get("tested")),
            "reason": isaac.get("reason"),
            "adapter_contract": isaac.get("adapter_contract", {}),
        },
    }


def target_rows(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    mujoco_evidence = evidence.get("mujoco", {})
    genesis_evidence = evidence.get("genesis", {})
    isaac_evidence = evidence.get("isaac", {})
    contact_evidence = evidence.get("contact_rich", {})
    return [
        {
            "runtime_id": "mujoco",
            "runtime_family": "contact_dynamics",
            "adapter_status": "tested_replay" if mujoco_evidence.get("tested") else "adapter_required",
            "implemented_layers": ["META-SIM.001", "META-SIM.003"] if mujoco_evidence.get("tested") else [],
            "extension_policy": "core rigid-body replay only in current artifact",
            "evidence": {
                "artifact": evidence.get("artifact"),
                "tested": mujoco_evidence.get("tested", False),
                "rmse_improvement_over_naive": mujoco_evidence.get("rmse_improvement_over_naive"),
                "contact_rich_replay": contact_evidence,
            },
            "claim_boundary": (
                "MuJoCo executes the LeRobot timing trace and a primitive contact protocol. "
                "Scripted actors and no hardware reference preclude a physical-accuracy claim."
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
            "adapter_status": (
                "tested_replay"
                if genesis_evidence.get("tested")
                else "adapter_contract_ready_untested"
                if genesis_evidence.get("ready")
                else "adapter_required"
            ),
            "implemented_layers": ["META-SIM.001", "META-SIM.003"] if genesis_evidence.get("tested") else [],
            "extension_policy": (
                "WorldEpisode executes the same LeRobot control-replay trace through a minimal "
                "Genesis MJCF position-servo adapter."
            ),
            "evidence": {
                "tested": bool(genesis_evidence.get("tested")),
                "ready": bool(genesis_evidence.get("ready")),
                "same_trace_replay": {
                    "artifact": evidence.get("artifact"),
                    "runtime": genesis_evidence.get("runtime", {}),
                    "naive_command_time": genesis_evidence.get("naive_command_time"),
                    "timestamp_aware": genesis_evidence.get("timestamp_aware"),
                    "rmse_improvement_over_naive": genesis_evidence.get("rmse_improvement_over_naive"),
                    "claim_boundary": genesis_evidence.get("claim_boundary"),
                },
                "contact_rich_replay": contact_evidence,
            },
            "claim_boundary": (
                "Genesis executes the LeRobot timing trace and primitive contact protocol. "
                "Observed orientation drift precludes equal physics and no Isaac/SAPIEN result is claimed."
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

## External Collaboration

Status: {report["external_collaboration"]["display"]}.

## Rule

WorldEpisode certifies adapter conformance, not simulator quality in the abstract. If a simulator
cannot ingest the invariant interface, declare extensions, and report deterministic replay
assumptions, then its dataset export is not replay-safe under the WorldEpisode profile.
"""


def build_meta_simulator_contract(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    evidence = replay_evidence()
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
        "external_collaboration": {
            "status": "not_defined_yet",
            "display": "Not defined yet",
        },
        "layers": LAYERS,
        "runtime_targets": targets,
        "aggregate": {
            "runtime_target_count": len(targets),
            "tested_adapter_count": tested,
            "ready_untested_adapter_count": ready_untested,
            "adapter_required_count": len(targets) - tested - ready_untested,
            "compliance_layer_count": len(LAYERS),
            "contact_rich_tested_runtime_count": (
                2 if evidence.get("contact_rich") else 0
            ),
            "contact_rich_task_count": evidence.get("contact_rich", {}).get(
                "task_count", 0
            ),
            "contact_rich_scenario_count": evidence.get("contact_rich", {}).get(
                "scenario_count", 0
            ),
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
