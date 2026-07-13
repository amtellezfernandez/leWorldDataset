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
    paths = [ROOT / "paper" / "arxiv" / "main.tex"]
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


def build_claims(results: dict[str, Any], open_gates: dict[str, Any], text: str) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []

    leakage = nested(results, ("lerobot_scene_leakage", "summary"), {})
    claims.append(
        claim_result(
            claim_id="CLAIM.LEAKAGE.001",
            claim="ArmnetBench random split leaks lineages and offline BC drops under scene-disjoint split.",
            evidence_artifacts=[
                "docs/experiments/lerobot_scene_leakage/leakage_report.json",
                "docs/experiments/lerobot_scene_leakage/split_manifest.json",
            ],
            paper_patterns=[
                fmt3(float(leakage.get("random_offline_bc_success_rate", -1))),
                fmt3(float(leakage.get("scene_disjoint_offline_bc_success_rate", -1))),
                "leakage to zero",
                "offline BC success",
            ],
            evidence_passed=(
                leakage.get("random_leakage_rate") == 1.0
                and leakage.get("scene_disjoint_leakage_rate") == 0.0
                and leakage.get("random_offline_bc_success_rate") == 0.85
                and leakage.get("scene_disjoint_offline_bc_success_rate") == 0.0
            ),
            evidence={
                "random_leakage_rate": leakage.get("random_leakage_rate"),
                "scene_disjoint_leakage_rate": leakage.get("scene_disjoint_leakage_rate"),
                "random_offline_bc_success_rate": leakage.get("random_offline_bc_success_rate"),
                "scene_disjoint_offline_bc_success_rate": leakage.get("scene_disjoint_offline_bc_success_rate"),
            },
            text=text,
            boundary="Offline action-imitation result; not ACT/Diffusion or physical rollout success.",
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
                "four 30 Hz frames",
                "133 ms",
                fmt3(float(alignment.get("validation_naive_rmse_deg", -1))),
                fmt3(float(alignment.get("validation_timestamp_aware_rmse_deg", -1))),
                fmt3(float(nested(mujoco, ("naive_command_time", "joint_rmse_deg"), -1))),
                fmt3(float(nested(mujoco, ("timestamp_aware", "joint_rmse_deg"), -1))),
                "Genesis same-trace replay",
                fmt3(float(nested(genesis, ("naive_command_time", "joint_rmse_deg"), -1))),
                fmt3(float(nested(genesis, ("timestamp_aware", "joint_rmse_deg"), -1))),
                "Isaac adapter is emitted as a ready mapping",
                "not tested in this environment",
            ],
            evidence_passed=(
                alignment.get("inferred_effective_delay_frames") == 4
                and 0.132 <= float(alignment.get("inferred_effective_delay_s", 0)) <= 0.134
                and float(alignment.get("validation_improvement_over_naive", 0)) > 2.0
                and mujoco.get("tested") is True
                and float(mujoco.get("rmse_improvement_over_naive", 0)) > 2.0
                and genesis.get("tested") is True
                and float(genesis.get("rmse_improvement_over_naive", 0)) > 2.0
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

    roundtrip = results.get("lerobot_active_roundtrip", {})
    primary = roundtrip.get("batch_roundtrip", {})
    secondary = roundtrip.get("secondary_batch_roundtrips", [])
    total_episodes = int(primary.get("episode_count", 0)) + sum(int(item.get("episode_count", 0)) for item in secondary)
    total_rows = int(primary.get("total_action_rows", 0)) + sum(int(item.get("total_action_rows", 0)) for item in secondary)
    max_error_values = list(primary.get("max_errors", {}).values())
    for item in secondary:
        max_error_values.extend(item.get("max_errors", {}).values())
    claims.append(
        claim_result(
            claim_id="CLAIM.ROUNDTRIP.001",
            claim="Two public LeRobotDataset batches round-trip exactly through WorldEpisode.",
            evidence_artifacts=[
                "docs/experiments/lerobot_worldepisode_roundtrip/conversion_report.json",
                "docs/experiments/lerobot_worldepisode_roundtrip_pusht/batch_roundtrip_report.json",
            ],
            paper_patterns=[
                "Across ten episodes",
                plain_int(total_rows),
                "maximum absolute error 0.0",
                "source-absent rather than guessed",
            ],
            evidence_passed=(
                total_episodes == 10
                and total_rows == 1935
                and max_error_values
                and max(float(value) for value in max_error_values) == 0.0
                and len(secondary) >= 1
            ),
            evidence={
                "total_episodes": total_episodes,
                "total_action_rows": total_rows,
                "max_error": max(float(value) for value in max_error_values) if max_error_values else None,
                "datasets": [primary.get("repo_id"), *[item.get("repo_id") for item in secondary]],
            },
            text=text,
            boundary="Two five-episode batch audits; not full LeRobot coverage.",
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
            claim="Seven pilot bindings preserve 17--39% natively outside the reference binding, with sidecars recovering dataset/log/world projections.",
            evidence_artifacts=["docs/experiments/bindings"],
            paper_patterns=[
                "Across seven pilot bindings",
                "17--39\\%",
                "sidecars recover that projection",
            ],
            evidence_passed=(
                len(bindings) == 7
                and round(min_native * 100) == 17
                and round(max_native * 100) == 39
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
                "14 expected requirement failures",
                "1.000 recall",
                "0.933 precision",
                "Two hand-authored independent fixtures",
            ],
            evidence_passed=(
                fault.get("n_cases") == 14
                and fault.get("false_negative_requirements") == 0
                and fault.get("recall") == 1.0
                and fault.get("precision") == 0.933
                and independent.get("n_cases") == 2
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
            claim="Pilot natural-source corpus records 19 cases across five public robot-learning datasets.",
            evidence_artifacts=["docs/experiments/natural_failure_corpus/manifest.json"],
            paper_patterns=[
                "records 19 observed",
                "five public robot-learning datasets",
                "not claimed as maintainer-confirmed",
            ],
            evidence_passed=(
                natural.get("case_count") == 19
                and natural.get("dataset_count") == 5
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

    state = results.get("uss_state_drift_pilots", {})
    state_agg = state.get("aggregate", {})
    claims.append(
        claim_result(
            claim_id="CLAIM.USS.001",
            claim="Two deterministic non-robotics USS pilots demonstrate collision-patch and clock-domain drift.",
            evidence_artifacts=["docs/experiments/uss_state_drift_pilots/state_drift_report.json"],
            paper_patterns=[
                "50 ms undeclared clock offset",
                "0.75 m fusion error",
                "0.20 m tolerance",
                "not production game-engine or AV benchmark results",
            ],
            evidence_passed=(
                state_agg.get("case_count") == 2
                and state_agg.get("local_file_valid_count") == 2
                and state_agg.get("uss_detections") == 2
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
                "2/2 simulated successes",
                "0/2 deployment successes",
                "recovers 2/2 deployment successes",
                "controlled proxy, not a RoboSnap or hardware rerun",
            ],
            evidence_passed=(
                rt_agg.get("ablation_count") == 2
                and rt_agg.get("drifted_sim_successes") == 2
                and rt_agg.get("drifted_deployment_successes") == 0
                and rt_agg.get("worldepisode_deployment_successes") == 2
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
            claim="Generated catalog benchmark describes a billion-episode-capacity sharded corpus.",
            evidence_artifacts=["docs/experiments/dataset_scale_performance/performance_report.json"],
            paper_patterns=[
                tex_int(int(generated.get("trace_shard_count", 0))),
                tex_int(int(generated.get("described_episode_capacity", 0))),
                "Catalog-side benchmark only",
            ],
            evidence_passed=(
                scale.get("status") == "pass"
                and generated.get("trace_shard_count") == 32768
                and generated.get("described_episode_capacity") == 1_073_741_824
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
                "zero valid famous-benchmark rerun reports",
                "zero measured",
                "not a claim that their published scores are inflated",
            ],
            evidence_passed=(
                nested(bench_gate, ("aggregate", "audited_benchmark_count")) == 5
                and nested(bench_gate, ("aggregate", "measured_inflation_claims")) == 0
                and nested(bench_gate, ("aggregate", "ready_for_inflation_claim")) is False
            ),
            evidence={
                "audited_benchmark_count": nested(bench_gate, ("aggregate", "audited_benchmark_count")),
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
            ],
            evidence_passed=(
                open_gates.get("schema") == "worldepisode_open_reproduction_gates_v1"
                and nested(open_gates, ("validation", "passed")) is True
                and nested(open_gates, ("aggregate", "gate_count")) == 4
                and nested(open_gates, ("aggregate", "command_count")) >= 4
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
    text = paper_text()
    claims = build_claims(results, open_gates, text)
    failed = [claim for claim in claims if not claim["passed"]]
    report = {
        "schema": SCHEMA,
        "audit_date": AUDIT_DATE,
        "status": "pass" if not failed else "fail",
        "paper_sources": [
            rel(ROOT / "paper" / "arxiv" / "main.tex"),
            *[rel(path) for path in sorted((ROOT / "paper" / "arxiv" / "sections").glob("*.tex"))],
        ],
        "evidence_root": rel(RESULTS_JSON),
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
