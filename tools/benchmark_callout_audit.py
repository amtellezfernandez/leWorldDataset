#!/usr/bin/env python3
"""Audit famous robot-learning benchmarks for WorldEpisode leakage/timing controls.

This is a source-level call-out audit. It is intentionally conservative: it flags missing public
evidence for controls such as world-lineage-disjoint splits and action latency models, but it does
not claim that a benchmark score is inflated unless a measured experiment exists.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "experiments" / "benchmark_callout_audit"
AUDIT_DATE = "2026-07-13"


CHECKS = [
    {
        "check_id": "WE-CALLOUT.001",
        "requirement_ids": ["SPLIT.001", "DATASET.003"],
        "question": "Does the public benchmark expose world/scene lineage IDs and lineage-disjoint splits?",
        "risk_if_missing": "Random or task-level splits may evaluate on scenes, assets, or capture lineages already seen in training.",
    },
    {
        "check_id": "WE-CALLOUT.002",
        "requirement_ids": ["WORLD.001", "TRACE.001"],
        "question": "Does each episode bind to an immutable, content-addressed world or environment revision?",
        "risk_if_missing": "A policy result cannot prove whether train and test referenced the same reconstructed or simulated world revision.",
    },
    {
        "check_id": "WE-CALLOUT.003",
        "requirement_ids": ["ENTITY.001", "REP.001"],
        "question": "Are persistent physical entity IDs carried across observations, assets, simulator actors, and annotations?",
        "risk_if_missing": "Object, asset, and annotation leakage cannot be audited across representations.",
    },
    {
        "check_id": "WE-CALLOUT.004",
        "requirement_ids": ["ACTION.001", "ACTION.002", "ACTION.004"],
        "question": "Are action units, reference frames, absolute/delta semantics, command time, effective time, and latency model explicit?",
        "risk_if_missing": "Replay and cross-dataset conversion may silently reinterpret an action vector or apply it at the wrong time.",
    },
    {
        "check_id": "WE-CALLOUT.005",
        "requirement_ids": ["FRAME.001", "FRAME.002", "TIME.001", "TIME.002"],
        "question": "Are frames, transform directions, clock domains, and cross-clock mappings explicit enough for replay?",
        "risk_if_missing": "Camera/robot alignment and asynchronous sensor streams may be valid tensors but invalid physical records.",
    },
    {
        "check_id": "WE-CALLOUT.006",
        "requirement_ids": ["REPLAY.001", "CONVERT.001"],
        "question": "Are simulator/runtime assumptions and conversion-loss reports available for published policy scores?",
        "risk_if_missing": "A benchmark score may be hard to reproduce or compare across policy stacks and simulators.",
    },
]


BENCHMARKS = [
    {
        "rank": 1,
        "benchmark_id": "open_x_embodiment",
        "name": "Open X-Embodiment / RT-X",
        "domain": "real_robot_multi_embodiment",
        "source_url": "https://robotics-transformer-x.github.io/",
        "code_or_data_url": "https://github.com/google-deepmind/open_x_embodiment",
        "selection_reason": "large multi-institution, multi-robot generalist policy dataset and model benchmark",
        "scale_public_claim": "22 robots, 21 institutions, hundreds of skills/tasks in a standardized cross-embodiment release",
        "known_strengths": [
            "cross-robot dataset aggregation",
            "standardized action/observation loading through Open X-Embodiment tooling",
            "generalist RT-X policy evaluation"
        ],
        "audit_findings": {
            "WE-CALLOUT.001": "missing_public_world_lineage_split_evidence",
            "WE-CALLOUT.002": "missing_public_content_addressed_world_revision_evidence",
            "WE-CALLOUT.003": "missing_public_cross_representation_entity_identity_evidence",
            "WE-CALLOUT.004": "partial_action_semantics_public_evidence_but_latency_not_normative",
            "WE-CALLOUT.005": "partial_dataset_specific_frame_time_evidence",
            "WE-CALLOUT.006": "missing_public_loss_report_and_replay_tolerance_evidence"
        },
    },
    {
        "rank": 2,
        "benchmark_id": "droid",
        "name": "DROID",
        "domain": "real_robot_in_the_wild_manipulation",
        "source_url": "https://droid-dataset.github.io/",
        "code_or_data_url": "https://github.com/droid-dataset/droid",
        "selection_reason": "large in-the-wild robot manipulation dataset with public RLDS/raw releases",
        "scale_public_claim": "76k demonstration trajectories, 350h of interaction data, hundreds of scenes, dozens of tasks",
        "known_strengths": [
            "large real-world scene diversity",
            "public robot platform and data collection stack",
            "raw and RLDS dataset formats"
        ],
        "audit_findings": {
            "WE-CALLOUT.001": "partial_scene_metadata_expected_but_lineage_disjoint_split_evidence_missing",
            "WE-CALLOUT.002": "missing_public_content_addressed_world_revision_evidence",
            "WE-CALLOUT.003": "missing_public_cross_representation_entity_identity_evidence",
            "WE-CALLOUT.004": "missing_public_command_effective_latency_contract_evidence",
            "WE-CALLOUT.005": "partial_raw_sensor_calibration_evidence_expected",
            "WE-CALLOUT.006": "missing_public_loss_report_and_replay_tolerance_evidence"
        },
    },
    {
        "rank": 3,
        "benchmark_id": "bridgedata_v2",
        "name": "BridgeData V2",
        "domain": "real_robot_low_cost_manipulation",
        "source_url": "https://rail-berkeley.github.io/bridgedata/",
        "code_or_data_url": "https://github.com/rail-berkeley/bridge_data_v2",
        "selection_reason": "large real-world manipulation dataset used for scalable imitation and offline RL",
        "scale_public_claim": "60,096 trajectories across 24 environments on a publicly available low-cost robot",
        "known_strengths": [
            "large real robot trajectory corpus",
            "environment and task diversity",
            "goal-image and language-conditioned learning support"
        ],
        "audit_findings": {
            "WE-CALLOUT.001": "environment_metadata_exists_but_lineage_disjoint_split_evidence_missing",
            "WE-CALLOUT.002": "missing_public_content_addressed_world_revision_evidence",
            "WE-CALLOUT.003": "missing_public_cross_representation_entity_identity_evidence",
            "WE-CALLOUT.004": "missing_public_command_effective_latency_contract_evidence",
            "WE-CALLOUT.005": "partial_dataset_specific_frame_time_evidence",
            "WE-CALLOUT.006": "missing_public_loss_report_and_replay_tolerance_evidence"
        },
    },
    {
        "rank": 4,
        "benchmark_id": "libero",
        "name": "LIBERO",
        "domain": "simulated_lifelong_robot_manipulation",
        "source_url": "https://libero-project.github.io/main.html",
        "code_or_data_url": "https://github.com/Lifelong-Robot-Learning/LIBERO",
        "selection_reason": "widely used lifelong robot learning and VLA evaluation benchmark",
        "scale_public_claim": "130 tasks across four suites for spatial, object, goal, and mixed transfer",
        "known_strengths": [
            "controlled distribution-shift suites",
            "language-conditioned manipulation tasks",
            "simulated reproducibility"
        ],
        "audit_findings": {
            "WE-CALLOUT.001": "controlled_task_splits_exist_but_world_lineage_split_evidence_missing",
            "WE-CALLOUT.002": "sim_environment_defined_but_content_addressed_world_revision_evidence_missing",
            "WE-CALLOUT.003": "partial_sim_object_identity_evidence_expected",
            "WE-CALLOUT.004": "sim_action_contract_expected_but_command_effective_latency_not_normative",
            "WE-CALLOUT.005": "sim_frame_time_evidence_expected",
            "WE-CALLOUT.006": "partial_runtime_evidence_but_loss_report_missing"
        },
    },
    {
        "rank": 5,
        "benchmark_id": "calvin",
        "name": "CALVIN",
        "domain": "simulated_language_conditioned_long_horizon_manipulation",
        "source_url": "https://calvin.cs.uni-freiburg.de/",
        "code_or_data_url": "https://github.com/mees/calvin",
        "selection_reason": "canonical long-horizon language-conditioned manipulation benchmark",
        "scale_public_claim": "open-source simulated benchmark for long-horizon language-conditioned manipulation",
        "known_strengths": [
            "long-horizon task chaining",
            "language-conditioned policy evaluation",
            "controlled simulated environments"
        ],
        "audit_findings": {
            "WE-CALLOUT.001": "environment_splits_exist_but_asset_lineage_split_evidence_missing",
            "WE-CALLOUT.002": "sim_environment_defined_but_content_addressed_world_revision_evidence_missing",
            "WE-CALLOUT.003": "partial_sim_object_identity_evidence_expected",
            "WE-CALLOUT.004": "sim_action_contract_expected_but_command_effective_latency_not_normative",
            "WE-CALLOUT.005": "sim_frame_time_evidence_expected",
            "WE-CALLOUT.006": "partial_runtime_evidence_but_loss_report_missing"
        },
    },
]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_source(url: str) -> dict[str, Any]:
    try:
        response = requests.get(url, timeout=20)
        body = response.content[:200000]
        return {
            "available": True,
            "status_code": response.status_code,
            "content_type": response.headers.get("content-type"),
            "bytes_sampled": len(body),
            "sample_sha256": sha256_bytes(body),
        }
    except requests.RequestException as exc:
        return {
            "available": False,
            "error": str(exc),
        }


def severity_for_finding(finding: str) -> str:
    if finding.startswith("missing_public"):
        return "high"
    if (
        "lineage_disjoint_split_evidence_missing" in finding
        or "asset_lineage_split_evidence_missing" in finding
        or "content_addressed_world_revision_evidence_missing" in finding
        or "latency" in finding
    ):
        return "high"
    if finding.startswith("partial") or "expected" in finding:
        return "medium"
    return "info"


def status_for_finding(finding: str) -> str:
    if finding.startswith("missing_public"):
        return "public_evidence_missing"
    if "missing" in finding:
        return "needs_targeted_audit"
    if finding.startswith("partial") or "expected" in finding:
        return "partial_public_evidence"
    return "unknown"


def benchmark_rows(refresh_sources: bool) -> list[dict[str, Any]]:
    rows = []
    for benchmark in BENCHMARKS:
        findings = []
        for check in CHECKS:
            finding = benchmark["audit_findings"][check["check_id"]]
            findings.append(
                {
                    "check_id": check["check_id"],
                    "requirement_ids": check["requirement_ids"],
                    "question": check["question"],
                    "finding": finding,
                    "status": status_for_finding(finding),
                    "severity": severity_for_finding(finding),
                    "risk_if_missing": check["risk_if_missing"],
                    "measured_in_this_repo": False,
                }
            )
        source_check = None
        if refresh_sources:
            source_check = {
                "source_url": fetch_source(benchmark["source_url"]),
                "code_or_data_url": fetch_source(benchmark["code_or_data_url"]),
            }
        high_count = sum(1 for finding in findings if finding["severity"] == "high")
        rows.append(
            {
                **{key: value for key, value in benchmark.items() if key != "audit_findings"},
                "findings": findings,
                "summary": {
                    "high_severity_open_controls": high_count,
                    "measured_leakage_or_delay_in_this_repo": False,
                    "callout_level": "requires_worldepisode_audit_before_generalization_claim",
                },
                "source_check": source_check,
            }
        )
    return rows


def aggregate_findings(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_check = {}
    for check in CHECKS:
        statuses: dict[str, int] = {}
        severities: dict[str, int] = {}
        for row in rows:
            finding = next(item for item in row["findings"] if item["check_id"] == check["check_id"])
            statuses[finding["status"]] = statuses.get(finding["status"], 0) + 1
            severities[finding["severity"]] = severities.get(finding["severity"], 0) + 1
        by_check[check["check_id"]] = {
            "question": check["question"],
            "requirement_ids": check["requirement_ids"],
            "statuses": statuses,
            "severities": severities,
        }
    return {
        "benchmark_count": len(rows),
        "checks": by_check,
        "benchmarks_with_high_severity_open_controls": sum(
            1 for row in rows if row["summary"]["high_severity_open_controls"] > 0
        ),
        "measured_inflation_claims": 0,
    }


def render_markdown(report: dict[str, Any]) -> str:
    rows = []
    for benchmark in report["benchmarks"]:
        rows.append(
            "| {rank} | {name} | {domain} | {high} | {level} |".format(
                rank=benchmark["rank"],
                name=benchmark["name"],
                domain=benchmark["domain"],
                high=benchmark["summary"]["high_severity_open_controls"],
                level=benchmark["summary"]["callout_level"],
            )
        )
    check_rows = []
    for check_id, check in report["aggregate"]["checks"].items():
        high = check["severities"].get("high", 0)
        medium = check["severities"].get("medium", 0)
        check_rows.append(f"| `{check_id}` | {check['question']} | {high} | {medium} |")
    return f"""# Famous Benchmark Call-Out Audit

Status: source-level audit, not a completed leakage/replay experiment.

This artifact audits five famous public robot-learning benchmarks for the controls needed to make
world-lineage leakage, asset/entity leakage, action timing, and replay assumptions auditable. It
does not claim that a published score is inflated unless a measured experiment exists.

## Benchmarks

| Rank | Benchmark | Domain | High-Severity Open Controls | Call-Out Level |
|---:|---|---|---:|---|
{chr(10).join(rows)}

## Checks

| Check | Question | High | Medium |
|---|---|---:|---:|
{chr(10).join(check_rows)}

## Interpretation

The explosive ArmnetBench result remains the measured leakage case in this repository. This
five-benchmark audit is the next target list: each benchmark should be converted into a
WorldEpisode manifest, validated for the checks above, and rerun under lineage-disjoint splits or
timestamp-aware replay before making any stronger claim.

The stronger claim is enforced by `tools/benchmark_inflation_gate.py`. Until
`docs/experiments/benchmark_inflation_gate/gate_report.json` contains a valid rerun report, the
paper must treat these benchmarks as unaudited rather than inflated.

The first targeted rerun harness is `tools/famous_benchmark_policy_rerun.py --benchmark droid_100`.
It is allowed to fail closed when the pinned public shards cannot be fetched, when only proxy
lineage is available, or when the policy protocol is not a published-protocol reproduction.
"""


def build_callout_audit(output_dir: Path = DEFAULT_OUTPUT_DIR, refresh_sources: bool = False) -> dict[str, Any]:
    rows = benchmark_rows(refresh_sources=refresh_sources)
    report = {
        "profile": "worldepisode-famous-benchmark-callout-0.1",
        "audit_date": AUDIT_DATE,
        "scope": "source_level_public_metadata_audit",
        "status": "prepared_not_measured",
        "claim_boundary": (
            "Findings identify missing or unverified public evidence for WorldEpisode controls. "
            "They are not claims that benchmark scores are inflated."
        ),
        "checks": CHECKS,
        "benchmarks": rows,
        "aggregate": aggregate_findings(rows),
        "required_next_steps": [
            "run tools/famous_benchmark_policy_rerun.py --benchmark droid_100 with working Hugging Face access",
            "pass tools/benchmark_inflation_gate.py --required before claiming score inflation",
            "convert each benchmark into a WorldEpisode dataset manifest or sidecar",
            "derive or import world_lineage identifiers from scene, environment, asset, or capture metadata",
            "audit official train/eval splits for world, entity, source-capture, and asset-lineage leakage",
            "extract action units, frames, absolute/delta semantics, command timestamps, effective timestamps, and latency models",
            "rerun at least one published policy protocol under lineage-disjoint splits or timestamp-aware replay",
        ],
        "contrast_measured_case": {
            "artifact": "docs/experiments/lerobot_scene_leakage/leakage_report.json",
            "dataset": "armnet/armnetbench_v01_lerobot_so101",
            "random_split_leakage": 1.0,
            "scene_disjoint_leakage": 0.0,
            "random_offline_bc_success": 0.85,
            "scene_disjoint_offline_bc_success": 0.0,
        },
        "artifacts": {
            "report": str((output_dir / "benchmark_callout_report.json").relative_to(ROOT)),
            "markdown": str((output_dir / "README.md").relative_to(ROOT)),
        },
    }
    write_json(output_dir / "benchmark_callout_report.json", report)
    write_text(output_dir / "README.md", render_markdown(report))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--refresh-sources", action="store_true")
    args = parser.parse_args()
    report = build_callout_audit(output_dir=args.output_dir, refresh_sources=args.refresh_sources)
    print(
        json.dumps(
            {
                "status": report["status"],
                "benchmark_count": report["aggregate"]["benchmark_count"],
                "benchmarks_with_high_severity_open_controls": report["aggregate"][
                    "benchmarks_with_high_severity_open_controls"
                ],
                "measured_inflation_claims": report["aggregate"]["measured_inflation_claims"],
                "artifacts": report["artifacts"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
