#!/usr/bin/env python3
"""Generate a fail-closed public release readiness report.

This is the WorldEpisode equivalent of the evidence/status gates used in the existing
`~/sota/wayspan` work: a compact tracked artifact that says what is ready, what is only a scoped
RFC claim, and which stronger research claims are still blocked.
"""

from __future__ import annotations

import argparse
import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "experiments" / "release_readiness"
RESULTS_JSON = ROOT / "docs" / "experiments" / "results.json"
OPEN_GATES_JSON = ROOT / "docs" / "experiments" / "open_reproduction_gates" / "open_reproduction_gates.json"
PAPER_CLAIM_AUDIT_JSON = ROOT / "docs" / "experiments" / "paper_claim_audit" / "paper_claim_audit_report.json"
RELEASE_MANIFEST_JSON = ROOT / "docs" / "release_manifest" / "release_manifest.json"
SUBMISSION_PACKET_JSON = ROOT / "docs" / "submission_packet" / "submission_packet.json"
READINESS_SCHEMA = "worldepisode_release_readiness_v1"
AUDIT_DATE = "2026-07-13"


@dataclass(frozen=True)
class Check:
    check_id: str
    name: str
    passed: bool
    evidence: str
    severity: str = "error"
    boundary: str = ""


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


def file_check(check_id: str, name: str, path: str, *, min_bytes: int = 1) -> Check:
    target = ROOT / path
    passed = target.is_file() and target.stat().st_size >= min_bytes
    detail = f"{path} ({target.stat().st_size} bytes)" if target.exists() else f"{path} missing"
    return Check(check_id, name, passed, detail)


def package_checks() -> list[Check]:
    pyproject_path = ROOT / "pyproject.toml"
    checks = [file_check("PKG.001", "pyproject exists", "pyproject.toml")]
    try:
        pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - report the exact parse failure.
        checks.append(Check("PKG.002", "pyproject parses", False, str(exc)))
        return checks

    project = pyproject.get("project", {})
    scripts = project.get("scripts", {})
    checks.extend(
        [
            Check(
                "PKG.002",
                "package metadata parses",
                project.get("name") == "worldepisode" and bool(project.get("version")),
                f"name={project.get('name')!r}, version={project.get('version')!r}",
            ),
            Check(
                "PKG.003",
                "console script is exposed",
                scripts.get("worldepisode") == "worldepisode.cli:main",
                f"worldepisode={scripts.get('worldepisode')!r}",
            ),
            Check(
                "PKG.004",
                "license and authors are declared",
                bool(project.get("license")) and bool(project.get("authors")),
                "license and authors present in pyproject.toml",
            ),
        ]
    )
    return checks


def ci_checks() -> list[Check]:
    workflow = ROOT / ".github" / "workflows" / "ci.yml"
    if not workflow.exists():
        return [Check("CI.001", "CI workflow runs evidence gates", False, f"{rel(workflow)} missing")]
    text = workflow.read_text(encoding="utf-8")
    required_commands = [
        "python tools/run_experiments.py",
        "python tools/open_reproduction_gates.py --strict",
        "python tools/paper_claim_audit.py --strict",
        "python tools/release_manifest.py --strict",
        "python tools/submission_packet.py --strict",
        "python tools/release_readiness.py --strict-rfc",
        "python tools/artifact_freshness.py --strict",
    ]
    missing = [command for command in required_commands if command not in text]
    return [
        Check(
            "CI.001",
            "CI workflow runs evidence gates",
            not missing,
            f"missing={missing}",
        )
    ]


def experiment_checks(results: dict[str, Any]) -> list[Check]:
    active_roundtrip = nested(results, ("lerobot_active_roundtrip", "batch_roundtrip"), {})
    secondary = nested(results, ("lerobot_active_roundtrip", "secondary_batch_roundtrips"), [])
    leakage = nested(results, ("lerobot_scene_leakage", "summary"), {})
    policy_gate = results.get("lerobot_policy_gate", {})
    benchmark_inflation = results.get("benchmark_inflation_gate", {})
    natural = results.get("natural_failure_corpus", {})
    dataset_scale = results.get("dataset_scale_audit", {})
    dataset_perf = results.get("dataset_scale_performance", {})
    cleanroom = results.get("cleanroom_reader", {})
    replay = results.get("rq3_replay", {})
    replay_adapter = results.get("replay_adapter_conformance", {})
    realtosim = results.get("realtosim_contract_drift", {})
    meta_sim = results.get("meta_simulator_contract", {})

    checks = [
        Check(
            "EVID.001",
            "baseline manifest validates",
            results.get("baseline_schema_errors") == 0 and results.get("baseline_semantic_errors") == 0,
            "schema_errors=0 and semantic_errors=0",
        ),
        Check(
            "EVID.002",
            "active LeRobot round trips are exact",
            bool(active_roundtrip)
            and active_roundtrip.get("episode_count", 0) >= 5
            and nested(active_roundtrip, ("max_errors", "max_abs_action_error")) == 0.0
            and nested(active_roundtrip, ("max_errors", "max_abs_state_error")) == 0.0
            and nested(active_roundtrip, ("max_errors", "max_abs_timestamp_error")) == 0.0
            and bool(secondary),
            "two pinned public LeRobot batch reports with zero source-native errors",
        ),
        Check(
            "EVID.003",
            "scene leakage result is measured",
            leakage.get("random_leakage_rate") == 1.0
            and leakage.get("scene_disjoint_leakage_rate") == 0.0
            and leakage.get("success_rate_drop", 0) > 0,
            f"random={leakage.get('random_leakage_rate')}, disjoint={leakage.get('scene_disjoint_leakage_rate')}, drop={leakage.get('success_rate_drop')}",
        ),
        Check(
            "EVID.004",
            "ACT/Diffusion gate is explicit and not overclaimed",
            policy_gate.get("status") == "ready_not_executed"
            and not policy_gate.get("executions")
            and nested(policy_gate, ("physical_split_packages", "package_count"), 0) >= 4,
            "policy jobs and compact split packages exist; metrics are not claimed",
            severity="warning",
        ),
        Check(
            "EVID.005",
            "famous benchmark inflation gate is fail-closed",
            nested(benchmark_inflation, ("aggregate", "ready_for_inflation_claim")) is False
            and nested(benchmark_inflation, ("aggregate", "measured_inflation_claims")) == 0,
            f"reruns={nested(benchmark_inflation, ('aggregate', 'rerun_report_count'))}, valid={nested(benchmark_inflation, ('aggregate', 'valid_rerun_report_count'))}, claims=0",
        ),
        Check(
            "EVID.006",
            "dataset-scale manifest and generated catalog checks pass",
            dataset_scale.get("status") == "pass"
            and dataset_perf.get("status") == "pass"
            and nested(dataset_perf, ("generated_catalog", "described_episode_capacity"), 0) >= 1_000_000_000,
            "dataset manifest audit plus generated billion-episode-capacity catalog benchmark",
        ),
        Check(
            "EVID.007",
            "clean-room reader consumes public schema/fixtures",
            cleanroom.get("status") == "pass" and nested(cleanroom, ("aggregate", "recall")) == 1.0,
            f"status={cleanroom.get('status')}, recall={nested(cleanroom, ('aggregate', 'recall'))}",
        ),
        Check(
            "EVID.008",
            "replay timing evidence is executable",
            nested(replay, ("alignment", "validation_improvement_over_naive")) is not None
            and nested(replay, ("alignment", "validation_improvement_over_naive"), 0) > 1.0
            and replay_adapter.get("status") == "tested_reference_scheduler_not_physics_simulator",
            "LeRobot control replay plus adapter scheduler conformance",
        ),
        Check(
            "EVID.009",
            "real-to-sim and meta-simulator boundaries are explicit",
            realtosim.get("status") == "controlled_proxy_not_hardware_rollout"
            and meta_sim.get("status") == "runtime_neutral_adapter_contract",
            "controlled proxy and runtime-neutral contract, not hardware/Isaac claim",
        ),
        Check(
            "EVID.010",
            "natural failure corpus has scoped evidence",
            natural.get("dataset_count", 0) >= 5
            and natural.get("dataset_count_gate_satisfied") is True
            and natural.get("maintainer_feedback_satisfied") is False,
            "five-dataset count met; maintainer feedback still open",
            severity="warning",
        ),
    ]
    return checks


def open_gate_checks(blockers: list[dict[str, Any]]) -> list[Check]:
    if not OPEN_GATES_JSON.exists():
        return [
            Check(
                "GATE.001",
                "open reproduction gate index exists",
                False,
                f"{rel(OPEN_GATES_JSON)} missing",
            )
        ]

    try:
        gate_report = load_json(OPEN_GATES_JSON)
    except (OSError, json.JSONDecodeError) as exc:
        return [
            Check(
                "GATE.001",
                "open reproduction gate index parses",
                False,
                f"{rel(OPEN_GATES_JSON)}: {exc}",
            )
        ]

    gates = gate_report.get("gates", [])
    gate_ids = {str(gate.get("blocker_id", "")) for gate in gates}
    blocked_ids = {str(item["blocker_id"]) for item in blockers if item.get("blocked")}
    uncovered = sorted(blocked_ids - gate_ids)
    commandless = sorted(
        str(gate.get("blocker_id", ""))
        for gate in gates
        if not gate.get("commands") or not gate.get("required_artifacts") or not gate.get("acceptance_rule")
    )
    return [
        Check(
            "GATE.001",
            "open reproduction gate index validates",
            gate_report.get("schema") == "worldepisode_open_reproduction_gates_v1"
            and nested(gate_report, ("validation", "passed")) is True,
            f"{rel(OPEN_GATES_JSON)} gates={len(gates)}",
        ),
        Check(
            "GATE.002",
            "blocked claims have reproduction commands",
            not uncovered and not commandless,
            f"uncovered={uncovered}, commandless={commandless}",
        ),
    ]


def paper_claim_checks() -> list[Check]:
    if not PAPER_CLAIM_AUDIT_JSON.exists():
        return [
            Check(
                "CLAIM.001",
                "paper claim audit exists",
                False,
                f"{rel(PAPER_CLAIM_AUDIT_JSON)} missing",
            )
        ]

    try:
        report = load_json(PAPER_CLAIM_AUDIT_JSON)
    except (OSError, json.JSONDecodeError) as exc:
        return [
            Check(
                "CLAIM.001",
                "paper claim audit parses",
                False,
                f"{rel(PAPER_CLAIM_AUDIT_JSON)}: {exc}",
            )
        ]

    return [
        Check(
            "CLAIM.001",
            "paper claims are evidence-backed",
            report.get("schema") == "worldepisode_paper_claim_audit_v1"
            and report.get("status") == "pass"
            and nested(report, ("aggregate", "claim_count"), 0) >= 10
            and nested(report, ("aggregate", "failed_count")) == 0,
            (
                f"{rel(PAPER_CLAIM_AUDIT_JSON)} claims="
                f"{nested(report, ('aggregate', 'claim_count'))}, failed="
                f"{nested(report, ('aggregate', 'failed_count'))}"
            ),
        )
    ]


def submission_packet_checks() -> list[Check]:
    if not SUBMISSION_PACKET_JSON.exists():
        return [
            Check(
                "SUBMIT.001",
                "submission packet exists",
                False,
                f"{rel(SUBMISSION_PACKET_JSON)} missing",
            )
        ]
    try:
        packet = load_json(SUBMISSION_PACKET_JSON)
    except (OSError, json.JSONDecodeError) as exc:
        return [
            Check(
                "SUBMIT.001",
                "submission packet parses",
                False,
                f"{rel(SUBMISSION_PACKET_JSON)}: {exc}",
            )
        ]
    validation = packet.get("validation", {})
    return [
        Check(
            "SUBMIT.001",
            "submission packet validates",
            packet.get("schema") == "worldepisode_submission_packet_v1"
            and packet.get("status") == "pass"
            and validation.get("passed") is True
            and nested(packet, ("summary", "paper_claim_count"), 0) >= 10
            and nested(packet, ("summary", "open_result_gate_count"), 0) >= 5,
            (
                f"status={packet.get('status')}, "
                f"claims={nested(packet, ('summary', 'paper_claim_count'))}, "
                f"open_gates={nested(packet, ('summary', 'open_result_gate_count'))}"
            ),
        )
    ]


def release_manifest_checks() -> list[Check]:
    if not RELEASE_MANIFEST_JSON.exists():
        return [
            Check(
                "MANIFEST.001",
                "release manifest exists",
                False,
                f"{rel(RELEASE_MANIFEST_JSON)} missing",
            )
        ]
    try:
        manifest = load_json(RELEASE_MANIFEST_JSON)
    except (OSError, json.JSONDecodeError) as exc:
        return [
            Check(
                "MANIFEST.001",
                "release manifest parses",
                False,
                f"{rel(RELEASE_MANIFEST_JSON)}: {exc}",
            )
        ]
    validation = manifest.get("validation", {})
    return [
        Check(
            "MANIFEST.001",
            "release manifest validates",
            manifest.get("schema") == "worldepisode_release_manifest_v1"
            and manifest.get("status") == "pass"
            and validation.get("passed") is True
            and nested(manifest, ("aggregate", "entry_count"), 0) >= 30
            and nested(manifest, ("aggregate", "normalized_digest_count"), 0) >= 4,
            (
                f"status={manifest.get('status')}, "
                f"entries={nested(manifest, ('aggregate', 'entry_count'))}, "
                f"normalized={nested(manifest, ('aggregate', 'normalized_digest_count'))}"
            ),
        )
    ]


def claim_blockers(results: dict[str, Any]) -> list[dict[str, Any]]:
    benchmark_inflation = results.get("benchmark_inflation_gate", {})
    policy_gate = results.get("lerobot_policy_gate", {})
    natural = results.get("natural_failure_corpus", {})
    meta_sim = results.get("meta_simulator_contract", {})
    return [
        {
            "blocker_id": "POLICY.ROLL.001",
            "claim": "state-of-the-art policy or physical rollout impact",
            "blocked": policy_gate.get("gate_satisfied") is not True,
            "current_evidence": policy_gate.get("status"),
            "required_evidence": "ACT or Diffusion Policy metrics plus high-fidelity simulator or hardware rollout reports.",
        },
        {
            "blocker_id": "BENCH.INFLATE.001",
            "claim": "famous benchmark published scores are inflated",
            "blocked": nested(benchmark_inflation, ("aggregate", "ready_for_inflation_claim")) is not True,
            "current_evidence": nested(benchmark_inflation, ("aggregate",), {}),
            "required_evidence": "valid benchmark-specific conversion, lineage/timing audit, published-protocol rerun, corrected evaluation, and score delta.",
        },
        {
            "blocker_id": "NATURAL.001",
            "claim": "natural failure prevalence is maintainer-confirmed",
            "blocked": natural.get("maintainer_feedback_satisfied") is not True,
            "current_evidence": {
                "dataset_count": natural.get("dataset_count"),
                "maintainer_feedback_satisfied": natural.get("maintainer_feedback_satisfied"),
            },
            "required_evidence": "maintainer agreement/disagreement records or dataset-specific conversion reports.",
        },
        {
            "blocker_id": "SIM.001",
            "claim": "runtime-neutral replay equivalence across simulators",
            "blocked": nested(meta_sim, ("aggregate", "adapter_required_count"), 1) > 0,
            "current_evidence": meta_sim.get("aggregate", {}),
            "required_evidence": "same WorldEpisode LeRobot replay trace through at least one additional tested simulator adapter.",
        },
        {
            "blocker_id": "ADOPT.001",
            "claim": "mature external standard adoption",
            "blocked": True,
            "current_evidence": "internal clean-room reader only",
            "required_evidence": "external independent implementation or external compatible dataset release.",
        },
    ]


def build_report(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    results = load_json(RESULTS_JSON)
    checks = [
        file_check("DOC.001", "top-level README exists", "README.md", min_bytes=2_000),
        file_check("DOC.002", "license exists", "LICENSE", min_bytes=100),
        file_check("DOC.003", "governance exists", "GOVERNANCE.md", min_bytes=500),
        file_check("DOC.004", "paper PDF exists", "WorldEpisode.pdf", min_bytes=100_000),
        file_check("DOC.005", "paper source exists", "paper/arxiv/main.tex", min_bytes=1_000),
        file_check("DOC.006", "reviewer concern matrix exists", "docs/reviewer-concern-matrix.md", min_bytes=1_000),
        file_check("DOC.007", "controlled results exist", "docs/experiments/results.json", min_bytes=10_000),
        file_check("DOC.008", "public citation metadata exists", "CITATION.cff", min_bytes=100),
        file_check("DOC.009", "CI workflow exists", ".github/workflows/ci.yml", min_bytes=200),
        *ci_checks(),
        *package_checks(),
        *experiment_checks(results),
    ]
    blockers = claim_blockers(results)
    checks.extend(open_gate_checks(blockers))
    checks.extend(paper_claim_checks())
    checks.extend(release_manifest_checks())
    checks.extend(submission_packet_checks())
    open_gate_report = load_json(OPEN_GATES_JSON) if OPEN_GATES_JSON.exists() else {}
    paper_claim_report = load_json(PAPER_CLAIM_AUDIT_JSON) if PAPER_CLAIM_AUDIT_JSON.exists() else {}
    blocking_errors = [check for check in checks if check.severity == "error" and not check.passed]
    warning_failures = [check for check in checks if check.severity != "error" and not check.passed]
    rfc_release_ready = not blocking_errors
    full_standard_ready = rfc_release_ready and not any(item["blocked"] for item in blockers)
    report = {
        "schema": READINESS_SCHEMA,
        "audit_date": AUDIT_DATE,
        "status": "rfc_release_ready" if rfc_release_ready else "not_release_ready",
        "rfc_release_ready": rfc_release_ready,
        "full_standard_ready": full_standard_ready,
        "claim_boundary": (
            "A ready RFC release means the repository is executable and evidence-gated. It does "
            "not mean ACT/Diffusion, famous benchmark inflation, external adoption, or full "
            "simulator-neutral replay claims are complete."
        ),
        "checks": [check.__dict__ for check in checks],
        "aggregate": {
            "check_count": len(checks),
            "passed_count": sum(1 for check in checks if check.passed),
            "blocking_error_count": len(blocking_errors),
            "warning_failure_count": len(warning_failures),
            "blocked_stronger_claim_count": sum(1 for item in blockers if item["blocked"]),
        },
        "blocked_stronger_claims": blockers,
        "open_reproduction_gates": {
            "artifact": rel(OPEN_GATES_JSON),
            "aggregate": open_gate_report.get("aggregate", {}),
            "validation": open_gate_report.get("validation", {}),
        },
        "paper_claim_audit": {
            "artifact": rel(PAPER_CLAIM_AUDIT_JSON),
            "aggregate": paper_claim_report.get("aggregate", {}),
            "status": paper_claim_report.get("status"),
        },
        "wayspan_pattern_reused": {
            "source": "~/sota/wayspan/docs/benchmark_evidence_workflow.md",
            "adapted_principles": [
                "tracked compact evidence artifacts",
                "strict claim gate separated from status reports",
                "public-review commands separated from private/heavy runtime work",
                "claim-ready flags plus explicit remaining blockers",
            ],
        },
        "artifacts": {
            "report": rel(output_dir / "release_readiness_report.json"),
            "markdown": rel(output_dir / "README.md"),
        },
    }
    write_json(output_dir / "release_readiness_report.json", report)
    write_text(output_dir / "README.md", render_markdown(report))
    return report


def render_markdown(report: dict[str, Any]) -> str:
    check_rows = [
        "| {check_id} | {name} | {passed} | {severity} | {evidence} |".format(
            check_id=check["check_id"],
            name=check["name"],
            passed=check["passed"],
            severity=check["severity"],
            evidence=str(check["evidence"]).replace("\n", " "),
        )
        for check in report["checks"]
    ]
    blocker_rows = [
        f"| `{item['blocker_id']}` | {item['claim']} | {item['blocked']} | {item['required_evidence']} |"
        for item in report["blocked_stronger_claims"]
    ]
    open_gates = report.get("open_reproduction_gates", {})
    paper_claim_audit = report.get("paper_claim_audit", {})
    return f"""# Release Readiness

Status: {report["status"]}.

RFC release ready: `{report["rfc_release_ready"]}`.

Full standard ready: `{report["full_standard_ready"]}`.

{report["claim_boundary"]}

Open reproduction gate index: `{open_gates.get("artifact")}`.

Paper claim audit: `{paper_claim_audit.get("artifact")}`.

This gate adapts the evidence workflow pattern from `~/sota/wayspan`: compact tracked artifacts,
strict claim gates, and explicit blockers for claims that are not yet proven.

## Checks

| Check | Name | Pass | Severity | Evidence |
|---|---|---:|---|---|
{chr(10).join(check_rows)}

## Blocked Stronger Claims

| Blocker | Claim | Blocked | Required Evidence |
|---|---|---:|---|
{chr(10).join(blocker_rows)}
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--strict-rfc", action="store_true", help="exit non-zero unless the RFC release gate passes")
    parser.add_argument(
        "--strict-full",
        action="store_true",
        help="exit non-zero unless the full standard/benchmark gate passes",
    )
    args = parser.parse_args()
    report = build_report(output_dir=args.output_dir)
    print(
        json.dumps(
            {
                "status": report["status"],
                "rfc_release_ready": report["rfc_release_ready"],
                "full_standard_ready": report["full_standard_ready"],
                "aggregate": report["aggregate"],
                "artifacts": report["artifacts"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if args.strict_full and not report["full_standard_ready"]:
        return 1
    if args.strict_rfc and not report["rfc_release_ready"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
