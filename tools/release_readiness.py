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
PUBLIC_MATURITY_JSON = ROOT / "docs" / "experiments" / "public_maturity" / "public_maturity_report.json"
PACKAGE_INSTALL_SMOKE_JSON = (
    ROOT / "docs" / "experiments" / "package_install_smoke" / "package_install_smoke_report.json"
)
RELEASE_MANIFEST_JSON = ROOT / "docs" / "release_manifest" / "release_manifest.json"
SUBMISSION_PACKET_JSON = ROOT / "docs" / "submission_packet" / "submission_packet.json"
EXPERIMENT_MANIFEST_JSON = (
    ROOT / "docs" / "experiments" / "experiment_manifest" / "experiment_manifest.json"
)
CITATION_AUDIT_JSON = (
    ROOT / "docs" / "experiments" / "citation_source_audit" / "citation_source_audit.json"
)
ASSET_AUDIT_JSON = (
    ROOT / "docs" / "experiments" / "third_party_asset_audit" / "asset_audit.json"
)
SUPPLEMENT_REPORT_JSON = (
    ROOT / "docs" / "anonymous_supplement" / "supplement_report.json"
)
ANONYMITY_REPORT_JSON = (
    ROOT / "docs" / "experiments" / "anonymity_audit" / "anonymity_report.json"
)
NEURIPS_SUBMISSION_REPORT_JSON = (
    ROOT / "docs" / "experiments" / "neurips_submission" / "submission_format_report.json"
)
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
    if PACKAGE_INSTALL_SMOKE_JSON.exists():
        try:
            smoke = load_json(PACKAGE_INSTALL_SMOKE_JSON)
            checks.append(
                Check(
                    "PKG.005",
                    "wheel install smoke passes",
                    smoke.get("schema") == "worldepisode_package_install_smoke_v1"
                    and smoke.get("status") == "pass"
                    and nested(smoke, ("checks", "wheel_built")) is True
                    and nested(smoke, ("checks", "installed_non_editable")) is True
                    and nested(smoke, ("checks", "cli_preflight_passed")) is True
                    and nested(smoke, ("checks", "api_preflight_passed")) is True,
                    f"{rel(PACKAGE_INSTALL_SMOKE_JSON)} wheel={nested(smoke, ('wheel', 'filename'))}",
                )
            )
        except (OSError, json.JSONDecodeError) as exc:
            checks.append(
                Check(
                    "PKG.005",
                    "wheel install smoke parses",
                    False,
                    f"{rel(PACKAGE_INSTALL_SMOKE_JSON)}: {exc}",
                )
            )
    else:
        checks.append(
            Check(
                "PKG.005",
                "wheel install smoke exists",
                False,
                f"{rel(PACKAGE_INSTALL_SMOKE_JSON)} missing",
            )
        )
    return checks


def ci_checks() -> list[Check]:
    workflow = ROOT / ".github" / "workflows" / "ci.yml"
    makefile = ROOT / "Makefile"
    if not workflow.exists():
        return [Check("CI.001", "CI workflow runs evidence gates", False, f"{rel(workflow)} missing")]
    workflow_text = workflow.read_text(encoding="utf-8")
    delegated_readiness = "run: make readiness" in workflow_text
    makefile_text = (
        makefile.read_text(encoding="utf-8")
        if delegated_readiness and makefile.exists()
        else ""
    )
    command_text = (workflow_text + "\n" + makefile_text).replace("python3 ", "python ")
    required_commands = [
        "python tools/run_experiments.py",
        "python tools/open_reproduction_gates.py --strict",
        "python tools/paper_claim_audit.py --strict",
        "python tools/experiment_manifest.py --strict",
        "python tools/citation_source_audit.py --strict",
        "python tools/third_party_asset_audit.py --strict",
        "python tools/build_anonymous_supplement.py --strict",
        "python tools/submission_anonymity_audit.py --strict",
        "python tools/neurips_submission_audit.py --strict",
        "python tools/public_maturity_audit.py --strict",
        "python tools/package_install_smoke.py --strict",
        "python tools/release_manifest.py --verify --strict",
        "python tools/submission_packet.py --strict",
        "python tools/release_readiness.py --strict-rfc",
        "python tools/artifact_freshness.py --strict",
    ]
    missing = [command for command in required_commands if command not in command_text]
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
    leakage_report = results.get("lerobot_scene_leakage", {})
    leakage = nested(results, ("lerobot_scene_leakage", "summary"), {})
    policy_gate = results.get("lerobot_policy_gate", {})
    temporal_policy = results.get("lerobot_temporal_policy_baseline", {})
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
            "task--scene proxy holdout result is measured",
            leakage.get("random_leakage_rate") == 1.0
            and leakage.get("scene_disjoint_leakage_rate") == 0.0
            and leakage.get("scene_disjoint_episode_nrmse_mean", 0)
            > leakage.get("random_episode_nrmse_mean", 0)
            and nested(
                leakage_report,
                ("splits", "random_episode", "bc", "policy", "seed_count"),
                0,
            )
            >= 5,
            (
                f"random_proxy_overlap={leakage.get('random_leakage_rate')}, "
                f"holdout_proxy_overlap={leakage.get('scene_disjoint_leakage_rate')}, "
                f"random_nrmse={leakage.get('random_episode_nrmse_mean')}, "
                f"holdout_nrmse={leakage.get('scene_disjoint_episode_nrmse_mean')}, "
                f"seeds={nested(leakage_report, ('splits', 'random_episode', 'bc', 'policy', 'seed_count'))}; "
                "task-confounded"
            ),
        ),
        Check(
            "EVID.004",
            "ACT/Diffusion gate is explicit and not overclaimed",
            policy_gate.get("status") == "ready_for_policy_training"
            and policy_gate.get("policy_inputs_ready") is True
            and nested(
                policy_gate,
                ("policy_vision_smoke", "all_policy_probes_completed_training_step"),
            )
            is True
            and policy_gate.get("pass") is False
            and nested(policy_gate, ("physical_split_packages", "package_count"), 0) >= 4,
            "front-camera ACT/Diffusion smoke passes; policy metrics and rollouts are not claimed",
            severity="warning",
        ),
        Check(
            "EVID.011",
            "temporal policy baseline is measured",
            temporal_policy.get("status") == "measured_offline_temporal_baseline"
            and nested(temporal_policy, ("aggregate", "scene_disjoint_nrmse_mean"), 0)
            > nested(temporal_policy, ("aggregate", "random_episode_nrmse_mean"), 0),
            (
                f"random_nrmse={nested(temporal_policy, ('aggregate', 'random_episode_nrmse_mean'))}, "
                f"holdout_nrmse={nested(temporal_policy, ('aggregate', 'scene_disjoint_nrmse_mean'))}"
            ),
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
            and nested(dataset_perf, ("generated_catalog", "trace_shard_count"), 0) > 0
            and nested(dataset_perf, ("generated_catalog", "described_episode_capacity"), 0)
            >= nested(dataset_perf, ("generated_catalog", "trace_shard_count"), 0)
            and nested(dataset_perf, ("generated_catalog", "episodes_materialized")) == 0,
            "dataset manifest audit plus generated catalog-capacity benchmark",
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
            and nested(replay, ("simulators", "mujoco", "tested")) is True
            and nested(replay, ("simulators", "genesis", "tested")) is True
            and nested(replay, ("simulators", "genesis", "rmse_improvement_over_naive"), 0) > 2.0
            and replay_adapter.get("status") == "tested_reference_scheduler_not_physics_simulator",
            "LeRobot control replay through MuJoCo and Genesis plus adapter scheduler conformance",
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
            and natural.get("dataset_specific_diagnostics_ready") is True
            and natural.get("dataset_report_count") == natural.get("dataset_count")
            and natural.get("maintainer_feedback_satisfied") is False,
            (
                f"datasets={natural.get('dataset_count')}, reports={natural.get('dataset_report_count')}, "
                f"source_level_only={natural.get('source_level_only_report_count')}; "
                "maintainer feedback still open"
            ),
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


def experiment_manifest_checks() -> list[Check]:
    if not EXPERIMENT_MANIFEST_JSON.exists():
        return [
            Check(
                "PROV.001",
                "experiment provenance manifest exists",
                False,
                f"{rel(EXPERIMENT_MANIFEST_JSON)} missing",
            )
        ]
    try:
        report = load_json(EXPERIMENT_MANIFEST_JSON)
    except (OSError, json.JSONDecodeError) as exc:
        return [
            Check(
                "PROV.001",
                "experiment provenance manifest parses",
                False,
                f"{rel(EXPERIMENT_MANIFEST_JSON)}: {exc}",
            )
        ]
    experiments = report.get("experiments", [])
    complete = all(
        isinstance(experiment, dict)
        and experiment.get("datasets")
        and experiment.get("configuration")
        and experiment.get("seed_policy")
        and experiment.get("code")
        and experiment.get("outputs")
        and nested(experiment, ("execution", "exit_status")) == 0
        and nested(experiment, ("execution", "compute", "wall_time_seconds"), 0) > 0
        and nested(experiment, ("execution", "compute", "max_rss_bytes"), 0) > 0
        for experiment in experiments
    )
    return [
        Check(
            "PROV.001",
            "principal experiments have validated provenance",
            report.get("schema") == "worldepisode_experiment_manifest_v1"
            and nested(report, ("validation", "passed")) is True
            and len(experiments) >= 4
            and complete,
            (
                f"{rel(EXPERIMENT_MANIFEST_JSON)} experiments={len(experiments)}, "
                f"errors={nested(report, ('validation', 'errors'), [])}"
            ),
        )
    ]


def source_audit_checks() -> list[Check]:
    checks = []
    for check_id, name, path, schema in (
        (
            "SOURCE.001",
            "paper citations have audited primary sources",
            CITATION_AUDIT_JSON,
            "worldepisode_citation_source_audit_v1",
        ),
        (
            "SOURCE.002",
            "third-party assets and redistribution are audited",
            ASSET_AUDIT_JSON,
            "worldepisode_third_party_asset_audit_v1",
        ),
    ):
        if not path.exists():
            checks.append(Check(check_id, name, False, f"{rel(path)} missing"))
            continue
        try:
            report = load_json(path)
        except (OSError, json.JSONDecodeError) as exc:
            checks.append(Check(check_id, name, False, f"{rel(path)}: {exc}"))
            continue
        passed = (
            report.get("schema") == schema
            and nested(report, ("validation", "passed")) is True
            and nested(report, ("aggregate", "error_count")) == 0
        )
        if check_id == "SOURCE.001":
            passed = (
                passed
                and nested(report, ("aggregate", "reference_count"), 0) > 0
                and nested(report, ("aggregate", "undefined_count")) == 0
                and nested(report, ("aggregate", "unused_count")) == 0
            )
        else:
            passed = (
                passed
                and nested(report, ("aggregate", "active_dataset_count"), 0) >= 4
                and nested(report, ("aggregate", "redistributed_parquet_count"), 0) > 0
                and nested(report, ("aggregate", "source_license_file_count"), 0) > 0
                and nested(report, ("aggregate", "source_media_count")) == 0
            )
        checks.append(
            Check(
                check_id,
                name,
                passed,
                f"{rel(path)} aggregate={report.get('aggregate', {})}",
            )
        )
    return checks


def public_maturity_checks() -> list[Check]:
    if not PUBLIC_MATURITY_JSON.exists():
        return [
            Check(
                "PUBLIC.001",
                "public maturity language is audited",
                False,
                f"{rel(PUBLIC_MATURITY_JSON)} missing",
            )
        ]

    try:
        report = load_json(PUBLIC_MATURITY_JSON)
    except (OSError, json.JSONDecodeError) as exc:
        return [
            Check(
                "PUBLIC.001",
                "public maturity report parses",
                False,
                f"{rel(PUBLIC_MATURITY_JSON)}: {exc}",
            )
        ]

    return [
        Check(
            "PUBLIC.001",
            "public surface avoids draft-only framing",
            report.get("schema") == "worldepisode_public_maturity_audit_v1"
            and report.get("status") == "pass"
            and nested(report, ("aggregate", "violation_count")) == 0,
            (
                f"{rel(PUBLIC_MATURITY_JSON)} violations="
                f"{nested(report, ('aggregate', 'violation_count'))}"
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
            and nested(packet, ("summary", "open_result_gate_count"), 0) >= 4,
            (
                f"status={packet.get('status')}, "
                f"claims={nested(packet, ('summary', 'paper_claim_count'))}, "
                f"open_gates={nested(packet, ('summary', 'open_result_gate_count'))}"
            ),
        )
    ]


def anonymity_checks() -> list[Check]:
    if not SUPPLEMENT_REPORT_JSON.exists() or not ANONYMITY_REPORT_JSON.exists():
        missing = [
            rel(path)
            for path in (SUPPLEMENT_REPORT_JSON, ANONYMITY_REPORT_JSON)
            if not path.exists()
        ]
        return [
            Check(
                "ANON.001",
                "anonymous paper and supplement pass identity audit",
                False,
                f"missing={missing}",
            )
        ]
    try:
        supplement = load_json(SUPPLEMENT_REPORT_JSON)
        anonymity = load_json(ANONYMITY_REPORT_JSON)
    except (OSError, json.JSONDecodeError) as exc:
        return [
            Check(
                "ANON.001",
                "anonymous paper and supplement reports parse",
                False,
                str(exc),
            )
        ]
    supplement_path = ROOT / str(nested(supplement, ("archive", "path"), ""))
    return [
        Check(
            "ANON.001",
            "anonymous paper and supplement pass identity audit",
            supplement.get("schema") == "worldepisode_anonymous_supplement_v1"
            and supplement.get("status") == "pass"
            and nested(supplement, ("validation", "identity_pattern_matches")) == 0
            and supplement_path.is_file()
            and anonymity.get("schema") == "worldepisode_submission_anonymity_audit_v1"
            and anonymity.get("status") == "pass"
            and nested(anonymity, ("paper", "author_metadata_empty")) is True
            and nested(anonymity, ("paper", "identity_pattern_matches")) == 0
            and nested(anonymity, ("supplement", "identity_pattern_matches")) == 0,
            (
                f"supplement={rel(SUPPLEMENT_REPORT_JSON)}, "
                f"audit={rel(ANONYMITY_REPORT_JSON)}"
            ),
        )
    ]


def submission_format_checks() -> list[Check]:
    if not NEURIPS_SUBMISSION_REPORT_JSON.exists():
        return [
            Check(
                "FORMAT.001",
                "NeurIPS submission format is audited",
                False,
                f"{rel(NEURIPS_SUBMISSION_REPORT_JSON)} missing",
            )
        ]
    try:
        report = load_json(NEURIPS_SUBMISSION_REPORT_JSON)
    except (OSError, json.JSONDecodeError) as exc:
        return [
            Check(
                "FORMAT.001",
                "NeurIPS submission format report parses",
                False,
                f"{rel(NEURIPS_SUBMISSION_REPORT_JSON)}: {exc}",
            )
        ]
    target_final = nested(report, ("target", "requirements_final")) is True
    passed = (
        report.get("schema") == "worldepisode_neurips_submission_audit_v1"
        and report.get("status")
        in {"provisional_ready_pending_target_author_kit", "target_ready"}
        and nested(report, ("validation", "passed")) is True
        and nested(report, ("paper", "main_content_last_page"), 0)
        <= nested(report, ("paper", "main_content_page_limit"), -1)
    )
    return [
        Check(
            "FORMAT.001",
            "NeurIPS submission format is audited",
            passed,
            (
                f"status={report.get('status')}, "
                f"main_content_last_page={nested(report, ('paper', 'main_content_last_page'))}, "
                f"page_limit={nested(report, ('paper', 'main_content_page_limit'))}, "
                f"target_requirements_final={target_final}"
            ),
            boundary=(
                "The official NeurIPS 2027 instructions and style are not available; "
                "the official 2026 E&D author kit is the provisional baseline."
                if not target_final
                else ""
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
    temporal_policy = results.get("lerobot_temporal_policy_baseline", {})
    natural = results.get("natural_failure_corpus", {})
    replay = results.get("rq3_replay", {})
    meta_sim = results.get("meta_simulator_contract", {})
    genesis_tested = nested(replay, ("simulators", "genesis", "tested")) is True
    return [
        {
            "blocker_id": "POLICY.ROLL.001",
            "claim": "state-of-the-art policy or physical rollout impact",
            "blocked": policy_gate.get("gate_satisfied") is not True,
            "current_evidence": {
                "act_diffusion_gate": policy_gate.get("status"),
                "temporal_policy_baseline": temporal_policy.get("aggregate", {}),
            },
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
                "dataset_report_count": natural.get("dataset_report_count"),
                "dataset_specific_diagnostics_ready": natural.get("dataset_specific_diagnostics_ready"),
                "source_level_only_report_count": natural.get("source_level_only_report_count"),
                "maintainer_feedback_satisfied": natural.get("maintainer_feedback_satisfied"),
            },
            "required_evidence": "maintainer agreement/disagreement records for prevalence; pinned dataset-specific conversions for source-level benchmark gaps.",
        },
        {
            "blocker_id": "SIM.001",
            "claim": "runtime-neutral replay equivalence across contact-rich simulator rollouts",
            "blocked": not genesis_tested,
            "current_evidence": {
                "genesis_same_trace_tested": genesis_tested,
                "meta_simulator_aggregate": meta_sim.get("aggregate", {}),
            },
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
        file_check("DOC.004", "WorldEpisode RFC spec exists", "spec/worldepisode-v0.1.md", min_bytes=1_000),
        file_check("DOC.005", "world layout RFC spec exists", "spec/le-world-layout-v0.1.md", min_bytes=1_000),
        file_check("DOC.006", "paper PDF exists", "WorldEpisode.pdf", min_bytes=100_000),
        file_check("DOC.007", "paper source exists", "paper/arxiv/main.tex", min_bytes=1_000),
        file_check("DOC.008", "reviewer concern matrix exists", "docs/reviewer-concern-matrix.md", min_bytes=1_000),
        file_check("DOC.009", "controlled results exist", "docs/experiments/results.json", min_bytes=10_000),
        file_check("DOC.010", "public citation metadata exists", "CITATION.cff", min_bytes=100),
        file_check("DOC.011", "CI workflow exists", ".github/workflows/ci.yml", min_bytes=200),
        *ci_checks(),
        *package_checks(),
        *experiment_checks(results),
    ]
    blockers = claim_blockers(results)
    checks.extend(open_gate_checks(blockers))
    checks.extend(paper_claim_checks())
    checks.extend(experiment_manifest_checks())
    checks.extend(source_audit_checks())
    checks.extend(public_maturity_checks())
    checks.extend(anonymity_checks())
    checks.extend(submission_format_checks())
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
            "contact-rich simulator-neutral rollout claims are complete."
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
