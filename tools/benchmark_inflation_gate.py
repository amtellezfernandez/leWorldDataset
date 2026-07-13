#!/usr/bin/env python3
"""Gate famous-benchmark score-inflation claims on measured reruns.

The source-level call-out audit identifies missing public controls. This gate is stricter: a
benchmark score can only be called inflated when a benchmark-specific WorldEpisode conversion and
policy rerun report exists and passes the evidence contract below.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "experiments" / "benchmark_inflation_gate"
DEFAULT_RERUN_DIR = ROOT / "docs" / "experiments" / "benchmark_reruns"
CALLOUT_REPORT = ROOT / "docs" / "experiments" / "benchmark_callout_audit" / "benchmark_callout_report.json"

PROFILE = "worldepisode-famous-benchmark-inflation-gate-0.1"
RERUN_SCHEMA = "worldepisode_benchmark_rerun_report.v1"
AUDIT_DATE = "2026-07-13"
MIN_SCORE_DROP_FOR_INFLATION = 0.05


REQUIRED_TESTS = [
    {
        "test_id": "BENCH-INFLATE.001",
        "name": "benchmark_specific_worldepisode_conversion",
        "evidence": (
            "A WorldEpisode manifest/sidecar for the benchmark subset, plus conversion report with "
            "loss accounting and source data revision."
        ),
    },
    {
        "test_id": "BENCH-INFLATE.002",
        "name": "lineage_or_timing_audit",
        "evidence": (
            "A split or replay audit showing the original protocol leaks world/entity/source lineage "
            "or omits timing semantics, and the corrected protocol removes that failure."
        ),
    },
    {
        "test_id": "BENCH-INFLATE.003",
        "name": "published_protocol_rerun",
        "evidence": (
            "A rerun of a published policy protocol or faithful reproduction, with policy code, "
            "configuration, seeds, and evaluation command recorded."
        ),
    },
    {
        "test_id": "BENCH-INFLATE.004",
        "name": "paired_corrected_evaluation",
        "evidence": (
            "The same policy evaluated under the corrected lineage-disjoint split or timestamp-aware "
            "replay with the same metric and tolerance envelope."
        ),
    },
    {
        "test_id": "BENCH-INFLATE.005",
        "name": "measured_score_delta",
        "evidence": (
            "A positive baseline-minus-corrected score drop with enough seeds or paired episodes to "
            "support the claim being made."
        ),
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


def benchmark_ids_from_callout() -> list[str]:
    if not CALLOUT_REPORT.exists():
        return []
    report = load_json(CALLOUT_REPORT)
    return [str(item["benchmark_id"]) for item in report.get("benchmarks", [])]


def discover_rerun_reports(rerun_dir: Path) -> list[Path]:
    if not rerun_dir.exists():
        return []
    return sorted(path for path in rerun_dir.glob("*/rerun_report.json") if path.is_file())


def _get_number(payload: dict[str, Any], path: tuple[str, ...]) -> float | None:
    cursor: Any = payload
    for key in path:
        if not isinstance(cursor, dict) or key not in cursor:
            return None
        cursor = cursor[key]
    if isinstance(cursor, (int, float)):
        return float(cursor)
    return None


def validate_rerun_report(path: Path, benchmark_ids: set[str]) -> dict[str, Any]:
    errors: list[str] = []
    try:
        payload = load_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "path": str(path.relative_to(ROOT)),
            "valid": False,
            "errors": [f"cannot read JSON report: {exc}"],
        }

    benchmark_id = str(payload.get("benchmark_id", ""))
    if payload.get("schema") != RERUN_SCHEMA:
        errors.append(f"schema must be {RERUN_SCHEMA}")
    if benchmark_id not in benchmark_ids:
        errors.append("benchmark_id must match a benchmark in the call-out audit")

    conversion = payload.get("worldepisode_conversion", {})
    if not isinstance(conversion, dict) or conversion.get("pass") is not True:
        errors.append("worldepisode_conversion.pass must be true")
    if not conversion.get("manifest") or not conversion.get("conversion_report"):
        errors.append("worldepisode_conversion must name manifest and conversion_report artifacts")

    split_audit = payload.get("split_or_timing_audit", {})
    if not isinstance(split_audit, dict) or split_audit.get("pass") is not True:
        errors.append("split_or_timing_audit.pass must be true")
    baseline_overlap = _get_number(payload, ("split_or_timing_audit", "baseline_lineage_overlap"))
    corrected_overlap = _get_number(payload, ("split_or_timing_audit", "corrected_lineage_overlap"))
    timing_fixed = payload.get("split_or_timing_audit", {}).get("timestamp_or_latency_fixed") is True
    if baseline_overlap is None and not timing_fixed:
        errors.append("split_or_timing_audit must report baseline_lineage_overlap or timestamp_or_latency_fixed")
    if corrected_overlap is not None and corrected_overlap > 0:
        errors.append("corrected_lineage_overlap must be zero when provided")
    lineage_source = payload.get("split_or_timing_audit", {}).get("lineage_source", {})
    lineage_sufficient = isinstance(lineage_source, dict) and (
        lineage_source.get("sufficient_for_score_inflation_claim") is True
    )
    if baseline_overlap is not None and not timing_fixed and not lineage_sufficient:
        errors.append(
            "lineage_source.sufficient_for_score_inflation_claim must be true for split-leakage "
            "inflation claims"
        )

    protocol = payload.get("published_protocol", {})
    if not isinstance(protocol, dict) or not protocol.get("name") or not protocol.get("source"):
        errors.append("published_protocol must name the protocol and source")
    protocol_sufficient = isinstance(protocol, dict) and (
        protocol.get("published_leaderboard_reproduction") is True
        or protocol.get("faithful_published_protocol_reproduction") is True
    )
    if not protocol_sufficient:
        errors.append(
            "published_protocol must mark published_leaderboard_reproduction or "
            "faithful_published_protocol_reproduction true"
        )

    policy = payload.get("policy", {})
    if not isinstance(policy, dict) or not policy.get("name") or not policy.get("implementation"):
        errors.append("policy must name the policy and implementation")

    evaluation = payload.get("evaluation", {})
    baseline_score = _get_number(payload, ("evaluation", "baseline_score"))
    corrected_score = _get_number(payload, ("evaluation", "corrected_score"))
    seed_count = _get_number(payload, ("evaluation", "seed_count"))
    if baseline_score is None or corrected_score is None:
        errors.append("evaluation must include numeric baseline_score and corrected_score")
    if seed_count is None or seed_count < 1:
        errors.append("evaluation.seed_count must be at least 1")

    score_drop = None
    if baseline_score is not None and corrected_score is not None:
        score_drop = baseline_score - corrected_score
        if score_drop <= 0:
            errors.append("baseline_score must be greater than corrected_score for inflation")

    measured_inflation = (
        not errors
        and score_drop is not None
        and score_drop >= MIN_SCORE_DROP_FOR_INFLATION
        and (baseline_overlap is None or baseline_overlap > 0 or timing_fixed)
    )
    return {
        "path": str(path.relative_to(ROOT)),
        "benchmark_id": benchmark_id,
        "valid": not errors,
        "errors": errors,
        "baseline_score": baseline_score,
        "corrected_score": corrected_score,
        "score_drop": score_drop,
        "measured_inflation": measured_inflation,
        "lineage_source_sufficient": lineage_sufficient,
        "published_protocol_sufficient": protocol_sufficient,
        "claim_boundary": (
            "Valid rerun evidence can support an inflation claim only for this benchmark, policy, "
            "protocol, subset, metric, and seed set."
        ),
    }


def build_benchmark_inflation_gate(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    rerun_dir: Path = DEFAULT_RERUN_DIR,
) -> dict[str, Any]:
    benchmark_ids = benchmark_ids_from_callout()
    rerun_paths = discover_rerun_reports(rerun_dir)
    reruns = [validate_rerun_report(path, set(benchmark_ids)) for path in rerun_paths]
    measured = [item for item in reruns if item.get("measured_inflation")]
    valid = [item for item in reruns if item.get("valid")]
    report = {
        "profile": PROFILE,
        "audit_date": AUDIT_DATE,
        "status": "measured_famous_benchmark_inflation_not_proven" if not measured else "measured_inflation_claims_available",
        "claim_boundary": (
            "This gate only counts benchmark-score inflation when a benchmark-specific conversion, "
            "split/timing audit, and policy rerun report pass. Source-level metadata gaps do not "
            "count as score-inflation evidence."
        ),
        "callout_report": str(CALLOUT_REPORT.relative_to(ROOT)),
        "rerun_dir": str(rerun_dir.relative_to(ROOT)),
        "required_tests": REQUIRED_TESTS,
        "audited_benchmark_ids": benchmark_ids,
        "rerun_reports": reruns,
        "aggregate": {
            "audited_benchmark_count": len(benchmark_ids),
            "rerun_report_count": len(reruns),
            "valid_rerun_report_count": len(valid),
            "measured_inflation_claims": len(measured),
            "ready_for_inflation_claim": bool(measured),
            "minimum_score_drop_for_inflation": MIN_SCORE_DROP_FOR_INFLATION,
        },
        "current_claim_policy": (
            "The paper may call famous benchmarks unaudited with respect to WorldEpisode controls, "
            "but must not call their scores inflated until this gate has at least one measured "
            "inflation claim."
        ),
        "artifacts": {
            "report": str((output_dir / "gate_report.json").relative_to(ROOT)),
            "markdown": str((output_dir / "README.md").relative_to(ROOT)),
        },
    }
    write_json(output_dir / "gate_report.json", report)
    write_text(output_dir / "README.md", render_markdown(report))
    return report


def render_markdown(report: dict[str, Any]) -> str:
    test_rows = [
        f"| `{item['test_id']}` | {item['name']} | {item['evidence']} |"
        for item in report["required_tests"]
    ]
    rerun_rows = []
    for rerun in report["rerun_reports"]:
        rerun_rows.append(
            "| {benchmark} | {valid} | {drop} | {inflation} | {path} |".format(
                benchmark=rerun.get("benchmark_id", "unknown"),
                valid=rerun.get("valid"),
                drop=rerun.get("score_drop"),
                inflation=rerun.get("measured_inflation"),
                path=rerun.get("path"),
            )
        )
    if not rerun_rows:
        rerun_rows.append("| none | false | n/a | false | no rerun reports committed |")
    return f"""# Famous Benchmark Inflation Proof Gate

Status: {report["status"]}.

This is the hard evidence gate for claims that a famous benchmark score is inflated. The source
call-out audit is not enough. A claim needs a benchmark-specific WorldEpisode conversion, a
split/timing audit, and a policy rerun under the corrected protocol.

## Required Tests

| Test | Name | Required Evidence |
|---|---|---|
{chr(10).join(test_rows)}

## Rerun Reports

| Benchmark | Valid | Score Drop | Measured Inflation | Report |
|---|---:|---:|---:|---|
{chr(10).join(rerun_rows)}

## Current Policy

{report["current_claim_policy"]}

Measured inflation claims: {report["aggregate"]["measured_inflation_claims"]}.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--rerun-dir", type=Path, default=DEFAULT_RERUN_DIR)
    parser.add_argument(
        "--required",
        action="store_true",
        help="return non-zero unless at least one measured famous-benchmark inflation claim exists",
    )
    args = parser.parse_args()
    report = build_benchmark_inflation_gate(output_dir=args.output_dir, rerun_dir=args.rerun_dir)
    print(
        json.dumps(
            {
                "status": report["status"],
                "audited_benchmark_count": report["aggregate"]["audited_benchmark_count"],
                "rerun_report_count": report["aggregate"]["rerun_report_count"],
                "valid_rerun_report_count": report["aggregate"]["valid_rerun_report_count"],
                "measured_inflation_claims": report["aggregate"]["measured_inflation_claims"],
                "artifacts": report["artifacts"],
            },
            indent=2,
        )
    )
    if args.required and not report["aggregate"]["ready_for_inflation_claim"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
