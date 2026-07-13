#!/usr/bin/env python3
"""Generate the open-result reproduction gate index.

The paper marks unfinished results in an amber callout. This artifact makes the same boundaries
machine-readable: every blocked stronger claim has a status, commands, expected evidence, and an
acceptance rule. It is intentionally fail-closed; an unclaimed result is not allowed to become a
paper claim until its gate records committed evidence.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "experiments" / "open_reproduction_gates"
PAPER_LIMITATIONS = ROOT / "paper" / "arxiv" / "sections" / "limitations.tex"
PAPER_EVALUATION = ROOT / "paper" / "arxiv" / "sections" / "evaluation.tex"
SCHEMA = "worldepisode_open_reproduction_gates_v1"
AUDIT_DATE = "2026-07-13"


GATES: list[dict[str, Any]] = [
    {
        "blocker_id": "POLICY.ROLL.001",
        "claim": "state-of-the-art policy or physical rollout impact",
        "status": "open_not_claimed",
        "paper_boundary": (
            "No ACT, Diffusion Policy, IsaacLab, or hardware success number is claimed until "
            "policy metrics and rollout evidence are committed."
        ),
        "commands": [
            {
                "purpose": "regenerate split packages and LeRobot job specs",
                "command": "python3 tools/lerobot_policy_leakage_gate.py",
                "expected_outputs": [
                    "docs/experiments/lerobot_policy_gate/policy_gate_report.json",
                    "docs/experiments/lerobot_policy_gate/train_eval_jobs.json",
                    "docs/experiments/lerobot_policy_gate/run_lerobot_policy_jobs.sh",
                ],
            },
            {
                "purpose": "run generated ACT/Diffusion jobs in a LeRobot environment",
                "command": "bash docs/experiments/lerobot_policy_gate/run_lerobot_policy_jobs.sh",
                "expected_outputs": [
                    "ACT and Diffusion train metrics for random_episode and scene_disjoint splits",
                    "offline action-evaluation reports",
                    "high-fidelity simulator or physical rollout reports",
                ],
            },
        ],
        "required_artifacts": [
            "policy checkpoints or immutable checkpoint digests",
            "train/eval configs and seeds",
            "offline action metrics for both splits",
            "rollout traces or videos with content digests",
            "updated docs/experiments/lerobot_policy_gate/policy_gate_report.json",
        ],
        "acceptance_rule": (
            "At least one ACT or Diffusion Policy run must report both random_episode and "
            "scene_disjoint metrics, and at least one rollout report must use the same split "
            "manifest before the stronger policy-impact claim can be made."
        ),
    },
    {
        "blocker_id": "BENCH.INFLATE.001",
        "claim": "famous benchmark published scores are inflated",
        "status": "open_not_claimed",
        "paper_boundary": (
            "The paper may call famous benchmarks unaudited with respect to USS controls, but it "
            "must not call published scores inflated until a benchmark-specific rerun passes."
        ),
        "commands": [
            {
                "purpose": "attempt a targeted DROID-100 subset rerun",
                "command": (
                    "uv run --with pyarrow --with requests --with numpy "
                    "python tools/famous_benchmark_policy_rerun.py --benchmark droid_100 --required"
                ),
                "expected_outputs": [
                    "docs/experiments/benchmark_reruns/droid_100/rerun_report.json",
                ],
            },
            {
                "purpose": "enforce the score-inflation proof contract",
                "command": "python3 tools/benchmark_inflation_gate.py --required",
                "expected_outputs": [
                    "docs/experiments/benchmark_inflation_gate/gate_report.json",
                ],
            },
        ],
        "required_artifacts": [
            "benchmark-specific WorldEpisode conversion",
            "lineage/timing audit proving the corrected protocol removes the failure",
            "published or faithful published-protocol policy rerun",
            "paired corrected evaluation under the same metric",
            "measured baseline-minus-corrected score drop",
        ],
        "acceptance_rule": (
            "The gate must contain at least one valid rerun report with measured_inflation=true. "
            "Source-level metadata gaps alone are not score-inflation evidence."
        ),
    },
    {
        "blocker_id": "NATURAL.001",
        "claim": "natural failure prevalence is maintainer-confirmed",
        "status": "open_not_claimed",
        "paper_boundary": (
            "The current natural-source corpus is a scoped evidence corpus, not a prevalence "
            "estimate and not maintainer-confirmed bug evidence."
        ),
        "commands": [
            {
                "purpose": "regenerate controlled and natural-source experiment reports",
                "command": "python3 tools/run_experiments.py",
                "expected_outputs": [
                    "docs/experiments/results.json",
                    "docs/experiments/natural_failure_corpus/manifest.json",
                ],
            }
        ],
        "required_artifacts": [
            "dataset-specific WorldEpisode manifests for source-level gaps",
            "false-positive review records",
            "maintainer agreement, disagreement, or no-response evidence",
            "updated natural failure corpus manifest",
        ],
        "acceptance_rule": (
            "A prevalence or maintainer-confirmed claim requires recorded maintainer feedback or "
            "dataset-specific conversion reports for representative diagnostics."
        ),
    },
    {
        "blocker_id": "SIM.001",
        "claim": "runtime-neutral replay equivalence across simulators",
        "status": "open_not_claimed",
        "paper_boundary": (
            "MuJoCo replay and URDF Studio MuJoCo/Genesis companion evidence are reported, but "
            "the same LeRobot replay trace has not yet been rerun through Genesis, Isaac, or "
            "another second WorldEpisode-native simulator adapter."
        ),
        "commands": [
            {
                "purpose": "regenerate the current meta-simulator contract report",
                "command": "python3 tools/meta_simulator_contract.py",
                "expected_outputs": [
                    "docs/experiments/meta_simulator_contract/adapter_contract_report.json",
                ],
            },
            {
                "purpose": "run the existing URDF Studio MuJoCo/Genesis companion smoke test",
                "command": (
                    "cd ../urdf-studio && .venv/bin/python3 -m backend.scripts.scenario_run "
                    "scenarios/carton_sorting_0001 --sim mujoco --sim genesis "
                    "--out /tmp/urdf-studio-cross-sim-smoke --episodes 1"
                ),
                "expected_outputs": [
                    "/tmp/urdf-studio-cross-sim-smoke comparison report",
                ],
            },
        ],
        "required_artifacts": [
            "same SO-101 LeRobot replay trace executed by a second simulator adapter",
            "simulator name, version, solver, timestep, and adapter commit",
            "trajectory RMSE and contact/event agreement",
            "declared tolerance envelope and conversion-loss report",
            "updated docs/experiments/meta_simulator_contract/adapter_contract_report.json",
        ],
        "acceptance_rule": (
            "Runtime-neutral replay evidence requires the same WorldEpisode LeRobot replay trace "
            "through at least one additional tested simulator adapter, not only a separate URDF "
            "Studio scenario."
        ),
    },
    {
        "blocker_id": "ADOPT.001",
        "claim": "mature external standard adoption",
        "status": "open_not_claimed",
        "paper_boundary": (
            "The repository contains an internal clean-room reader, but no external independent "
            "implementation or externally published compatible dataset is claimed."
        ),
        "commands": [
            {
                "purpose": "regenerate the internal clean-room reader evidence",
                "command": "python3 tools/cleanroom_conformance_reader.py",
                "expected_outputs": [
                    "docs/experiments/cleanroom_reader/cleanroom_reader_report.json",
                ],
            },
            {
                "purpose": "check RFC readiness after external evidence is added",
                "command": "python3 tools/release_readiness.py --strict-rfc",
                "expected_outputs": [
                    "docs/experiments/release_readiness/release_readiness_report.json",
                ],
            },
        ],
        "required_artifacts": [
            "external reader/exporter repository or archived release",
            "external dataset manifest or conversion report",
            "conformance-suite output from the external implementation",
            "license and citation metadata for the external artifact",
        ],
        "acceptance_rule": (
            "Mature-standard language requires at least one independently written implementation "
            "or externally published compatible dataset that passes the public conformance suite."
        ),
    },
]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def validate_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    gates = report.get("gates", [])
    if report.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA}")
    if len(gates) < 5:
        errors.append("at least five blocked-claim gates are required")
    seen: set[str] = set()
    for gate in gates:
        blocker_id = str(gate.get("blocker_id", ""))
        if not blocker_id:
            errors.append("gate missing blocker_id")
            continue
        if blocker_id in seen:
            errors.append(f"duplicate blocker_id {blocker_id}")
        seen.add(blocker_id)
        if gate.get("status") != "open_not_claimed":
            errors.append(f"{blocker_id} must remain open_not_claimed until evidence closes it")
        if not gate.get("paper_boundary"):
            errors.append(f"{blocker_id} lacks paper_boundary")
        if not gate.get("commands"):
            errors.append(f"{blocker_id} lacks reproduction commands")
        if not gate.get("required_artifacts"):
            errors.append(f"{blocker_id} lacks required artifacts")
        if not gate.get("acceptance_rule"):
            errors.append(f"{blocker_id} lacks acceptance rule")
    paper = PAPER_LIMITATIONS.read_text(encoding="utf-8") if PAPER_LIMITATIONS.exists() else ""
    if "\\begin{openresult}{results not claimed in this release}" not in paper:
        errors.append("paper limitations section must include the amber open-result callout")
    evaluation = PAPER_EVALUATION.read_text(encoding="utf-8") if PAPER_EVALUATION.exists() else ""
    for callout in (
        "\\begin{openresult}{ACT/Diffusion and rollout impact}",
        "\\begin{openresult}{same-trace second-runtime replay}",
        "\\begin{openresult}{famous-benchmark score-inflation proof}",
    ):
        if callout not in evaluation:
            errors.append(f"paper evaluation section must include {callout}")
    return errors


def build_report(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    report = {
        "schema": SCHEMA,
        "audit_date": AUDIT_DATE,
        "status": "open_gates_indexed",
        "color_policy": {
            "paper_callout": "amber",
            "meaning": "visible boundary for results that are executable but not claimed",
        },
        "paper_artifact": rel(PAPER_LIMITATIONS),
        "paper_artifacts": [rel(PAPER_EVALUATION), rel(PAPER_LIMITATIONS)],
        "gates": GATES,
        "aggregate": {
            "gate_count": len(GATES),
            "open_not_claimed_count": sum(1 for gate in GATES if gate["status"] == "open_not_claimed"),
            "command_count": sum(len(gate["commands"]) for gate in GATES),
        },
        "artifacts": {
            "json": rel(output_dir / "open_reproduction_gates.json"),
            "markdown": rel(output_dir / "README.md"),
        },
    }
    errors = validate_report(report)
    report["validation"] = {
        "passed": not errors,
        "errors": errors,
    }
    write_json(output_dir / "open_reproduction_gates.json", report)
    write_text(output_dir / "README.md", render_markdown(report))
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Open Reproduction Gates",
        "",
        f"Status: `{report['status']}`.",
        "",
        (
            "These are the results that remain executable but unclaimed. The paper renders the same "
            "boundary as amber callouts in the evaluation and limitations sections."
        ),
        "",
        "## Gates",
        "",
    ]
    for gate in report["gates"]:
        lines.extend(
            [
                f"### `{gate['blocker_id']}`",
                "",
                f"Claim: {gate['claim']}",
                "",
                f"Status: `{gate['status']}`.",
                "",
                f"Boundary: {gate['paper_boundary']}",
                "",
                "Commands:",
                "",
            ]
        )
        for command in gate["commands"]:
            lines.extend(
                [
                    f"- {command['purpose']}",
                    "",
                    "  ```bash",
                    f"  {command['command']}",
                    "  ```",
                    "",
                ]
            )
        lines.extend(["Required artifacts:", ""])
        lines.extend(f"- {artifact}" for artifact in gate["required_artifacts"])
        lines.extend(["", f"Acceptance rule: {gate['acceptance_rule']}", ""])
    lines.extend(
        [
            "## Validation",
            "",
            f"Passed: `{report['validation']['passed']}`.",
            "",
        ]
    )
    if report["validation"]["errors"]:
        lines.extend(f"- {error}" for error in report["validation"]["errors"])
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--strict", action="store_true", help="exit non-zero unless the gate index validates")
    args = parser.parse_args()
    report = build_report(args.output_dir)
    print(
        json.dumps(
            {
                "status": report["status"],
                "aggregate": report["aggregate"],
                "validation": report["validation"],
                "artifacts": report["artifacts"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if args.strict and not report["validation"]["passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
