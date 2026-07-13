#!/usr/bin/env python3
"""Generate a reviewer-facing submission packet from tracked evidence artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "submission_packet"
CLAIM_AUDIT_JSON = ROOT / "docs" / "experiments" / "paper_claim_audit" / "paper_claim_audit_report.json"
OPEN_GATES_JSON = ROOT / "docs" / "experiments" / "open_reproduction_gates" / "open_reproduction_gates.json"
RESULTS_JSON = ROOT / "docs" / "experiments" / "results.json"
SCHEMA = "worldepisode_submission_packet_v1"
AUDIT_DATE = "2026-07-13"


REQUIRED_PUBLIC_ARTIFACTS = [
    "WorldEpisode.pdf",
    "README.md",
    "spec/worldepisode-v0.1.md",
    "spec/le-world-layout-v0.1.md",
    "paper/le-world-layout.md",
    "paper/arxiv/main.tex",
    "schemas/worldepisode-core-v0.schema.json",
    "schemas/worldepisode-dataset-v0.schema.json",
    "conformance/requirements.v0.json",
    "conformance/projections/uss-core-23.v0.json",
    "docs/experiments/results.json",
    "docs/experiments/paper_claim_audit/paper_claim_audit_report.json",
    "docs/experiments/package_install_smoke/package_install_smoke_report.json",
    "docs/experiments/open_reproduction_gates/open_reproduction_gates.json",
    "docs/release_manifest/release_manifest.json",
    "docs/release_manifest/README.md",
    "docs/experiments/release_readiness/release_readiness_report.json",
    "docs/reviewer-concern-matrix.md",
    "GOVERNANCE.md",
    "CITATION.cff",
]

REPRODUCTION_COMMANDS = [
    {
        "name": "validate schemas, examples, and Python tools",
        "command": "make validate",
    },
    {
        "name": "regenerate controlled experiment evidence",
        "command": "python3 tools/run_experiments.py",
    },
    {
        "name": "validate open unclaimed-result gates",
        "command": "python3 tools/open_reproduction_gates.py --strict",
    },
    {
        "name": "audit paper claims against evidence",
        "command": "python3 tools/paper_claim_audit.py --strict",
    },
    {
        "name": "generate this submission packet",
        "command": "python3 tools/submission_packet.py --strict",
    },
    {
        "name": "audit public maturity language",
        "command": "python3 tools/public_maturity_audit.py --strict",
    },
    {
        "name": "smoke-test wheel install",
        "command": "python3 tools/package_install_smoke.py --strict",
    },
    {
        "name": "build digest release manifest",
        "command": "python3 tools/release_manifest.py --strict",
    },
    {
        "name": "verify committed release manifest",
        "command": "python3 tools/release_manifest.py --verify --strict",
    },
    {
        "name": "check RFC release readiness",
        "command": "python3 tools/release_readiness.py --strict-rfc",
    },
    {
        "name": "reject stale generated artifacts",
        "command": "python3 tools/artifact_freshness.py --strict",
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


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def artifact_status(path: str) -> dict[str, Any]:
    target = ROOT / path
    return {
        "path": path,
        "exists": target.exists(),
        "nonempty": target.is_file() and target.stat().st_size > 0,
    }


def build_packet(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    claim_audit = load_json(CLAIM_AUDIT_JSON)
    open_gates = load_json(OPEN_GATES_JSON)
    results = load_json(RESULTS_JSON)

    claims = [
        {
            "claim_id": claim["claim_id"],
            "claim": claim["claim"],
            "passed": claim["passed"],
            "boundary": claim.get("boundary", ""),
            "evidence_artifacts": claim.get("evidence_artifacts", []),
        }
        for claim in claim_audit.get("claims", [])
    ]
    open_results = [
        {
            "blocker_id": gate["blocker_id"],
            "claim": gate["claim"],
            "status": gate["status"],
            "boundary": gate.get("paper_boundary", ""),
            "commands": gate.get("commands", []),
            "required_artifacts": gate.get("required_artifacts", []),
            "acceptance_rule": gate.get("acceptance_rule", ""),
        }
        for gate in open_gates.get("gates", [])
    ]
    required_artifacts = [artifact_status(path) for path in REQUIRED_PUBLIC_ARTIFACTS]
    missing_artifacts = [item["path"] for item in required_artifacts if not item["exists"]]
    failed_claims = [claim["claim_id"] for claim in claims if not claim["passed"]]
    invalid_open_gates = [
        gate["blocker_id"]
        for gate in open_results
        if gate["status"] != "open_not_claimed" or not gate["commands"] or not gate["acceptance_rule"]
    ]

    pass_status = (
        claim_audit.get("status") == "pass"
        and not failed_claims
        and open_gates.get("schema") == "worldepisode_open_reproduction_gates_v1"
        and open_gates.get("validation", {}).get("passed") is True
        and not invalid_open_gates
        and not missing_artifacts
        and len(claims) >= 10
        and len(open_results) >= 4
    )

    packet = {
        "schema": SCHEMA,
        "audit_date": AUDIT_DATE,
        "status": "pass" if pass_status else "fail",
        "claim_policy": (
            "Only claims listed as passed in the paper claim audit are treated as measured. "
            "Open reproduction gates are executable reviewer tasks, not paper results."
        ),
        "summary": {
            "paper_claim_count": len(claims),
            "failed_claim_count": len(failed_claims),
            "open_result_gate_count": len(open_results),
            "missing_required_artifact_count": len(missing_artifacts),
            "results_sections": sorted(results.keys()),
        },
        "required_public_artifacts": required_artifacts,
        "measured_claims": claims,
        "open_results_not_claimed": open_results,
        "reproduction_commands": REPRODUCTION_COMMANDS,
        "release_gate": {
            "command": "python3 tools/release_readiness.py --strict-rfc",
            "artifact": "docs/experiments/release_readiness/release_readiness_report.json",
        },
        "validation": {
            "passed": pass_status,
            "missing_required_artifacts": missing_artifacts,
            "failed_claims": failed_claims,
            "invalid_open_gates": invalid_open_gates,
        },
        "artifacts": {
            "json": rel(output_dir / "submission_packet.json"),
            "markdown": rel(output_dir / "README.md"),
        },
    }
    write_json(output_dir / "submission_packet.json", packet)
    write_text(output_dir / "README.md", render_markdown(packet))
    return packet


def render_markdown(packet: dict[str, Any]) -> str:
    artifact_rows = [f"| `{item['path']}` | {item['exists']} | {item['nonempty']} |" for item in packet["required_public_artifacts"]]
    claim_rows = [
        f"| `{claim['claim_id']}` | {claim['passed']} | {claim['claim']} | {claim['boundary']} |"
        for claim in packet["measured_claims"]
    ]
    open_rows = [
        f"| `{gate['blocker_id']}` | {gate['claim']} | {gate['status']} | {gate['acceptance_rule']} |"
        for gate in packet["open_results_not_claimed"]
    ]
    command_rows = [
        f"| {command['name']} | `{command['command']}` |"
        for command in packet["reproduction_commands"]
    ]
    validation = packet["validation"]
    return f"""# Submission Packet

Status: `{packet["status"]}`.

{packet["claim_policy"]}

## Summary

- Paper claims checked: {packet["summary"]["paper_claim_count"]}
- Failed checked claims: {packet["summary"]["failed_claim_count"]}
- Open results not claimed: {packet["summary"]["open_result_gate_count"]}
- Missing required public artifacts: {packet["summary"]["missing_required_artifact_count"]}
- Release gate: `{packet["release_gate"]["command"]}`

## Required Public Artifacts

| Artifact | Exists | Nonempty |
|---|---:|---:|
{chr(10).join(artifact_rows)}

## Measured Claims

| Claim | Pass | Text | Boundary |
|---|---:|---|---|
{chr(10).join(claim_rows)}

## Open Results Not Claimed

| Gate | Claim | Status | Acceptance Rule |
|---|---|---|---|
{chr(10).join(open_rows)}

## Reproduction Commands

| Step | Command |
|---|---|
{chr(10).join(command_rows)}

## Validation

- Passed: `{validation["passed"]}`
- Missing artifacts: `{validation["missing_required_artifacts"]}`
- Failed claims: `{validation["failed_claims"]}`
- Invalid open gates: `{validation["invalid_open_gates"]}`
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--strict", action="store_true", help="exit non-zero unless packet validates")
    args = parser.parse_args()
    packet = build_packet(args.output_dir)
    print(
        json.dumps(
            {
                "status": packet["status"],
                "summary": packet["summary"],
                "validation": packet["validation"],
                "artifacts": packet["artifacts"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if args.strict and packet["status"] != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
