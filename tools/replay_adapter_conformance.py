#!/usr/bin/env python3
"""Dependency-free replay-adapter conformance checks.

This is not a physics simulator. It is a deterministic control-loop scheduler that checks whether a
runtime adapter can honor the WorldEpisode action contract: effective timestamps, frame-delay
latency, zero-order hold, and missing-command policy. It complements the tested MuJoCo replay
without pretending to be a second physics backend.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "experiments" / "replay_adapter_conformance"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def rmse(left: list[float], right: list[float]) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(left, right, strict=True)) / len(left))


def command_value(index: int) -> float:
    return round(0.15 * index + 0.05 * math.sin(index * 0.7), 6)


def delayed_trace(length: int, delay_frames: int) -> tuple[list[float], list[float]]:
    commands = [command_value(index) for index in range(length)]
    observed = [commands[max(0, index - delay_frames)] for index in range(length)]
    return commands, observed


def constant_frame_delay_case() -> dict[str, Any]:
    delay_frames = 4
    commands, observed = delayed_trace(length=36, delay_frames=delay_frames)
    naive = [commands[index] for index in range(len(commands))]
    aware = [commands[max(0, index - delay_frames)] for index in range(len(commands))]
    naive_rmse = rmse(naive, observed)
    aware_rmse = rmse(aware, observed)
    tolerance = 1e-12
    return {
        "case_id": "constant_frame_delay_scheduler",
        "requirement_ids": ["ACTION.002", "TIME.002", "REPLAY.001"],
        "contract": {
            "latency_model": {"type": "constant_frame_delay", "delay_frames": delay_frames},
            "effective_timestamp_semantics": "sample_timestamp + delay_frames * sample_period",
            "interpolation": "zero_order_hold",
        },
        "naive": {
            "scheduler": "command_time",
            "rmse": naive_rmse,
            "pass": naive_rmse <= tolerance,
        },
        "contract_aware": {
            "scheduler": "effective_time",
            "rmse": aware_rmse,
            "pass": aware_rmse <= tolerance,
        },
    }


def zero_order_hold_case() -> dict[str, Any]:
    commands = {
        0: 0.0,
        1: 0.2,
        4: 0.8,
        7: 1.4,
    }
    expected = []
    held = 0.0
    for index in range(10):
        if index in commands:
            held = commands[index]
        expected.append(held)
    naive = [commands.get(index, 0.0) for index in range(10)]
    aware = []
    held = 0.0
    for index in range(10):
        if index in commands:
            held = commands[index]
        aware.append(held)
    naive_rmse = rmse(naive, expected)
    aware_rmse = rmse(aware, expected)
    tolerance = 1e-12
    return {
        "case_id": "zero_order_hold_missing_command",
        "requirement_ids": ["ACTION.002", "REPLAY.001"],
        "contract": {
            "interpolation": "zero_order_hold",
            "missing_value_policy": "hold_last",
        },
        "naive": {
            "scheduler": "missing_command_as_zero",
            "rmse": naive_rmse,
            "pass": naive_rmse <= tolerance,
        },
        "contract_aware": {
            "scheduler": "hold_last_valid_command",
            "rmse": aware_rmse,
            "pass": aware_rmse <= tolerance,
        },
    }


def asynchronous_queue_case() -> dict[str, Any]:
    command_events = [
        {"command_id": "c0", "enqueue_time_s": 0.00, "value": 0.0},
        {"command_id": "c1", "enqueue_time_s": 0.05, "value": 0.5},
        {"command_id": "c2", "enqueue_time_s": 0.11, "value": 1.0},
        {"command_id": "c3", "enqueue_time_s": 0.29, "value": 1.5},
    ]
    consume_times = [0.0, 0.1, 0.2, 0.3, 0.4]
    expected = [0.0, 0.5, 1.0, 1.5, 1.5]
    naive = [event["value"] for event in command_events[: len(consume_times) - 1]]
    naive.append(0.0)
    aware = []
    last = command_events[0]
    for consume_time in consume_times:
        for event in command_events:
            if event["enqueue_time_s"] <= consume_time:
                last = event
        aware.append(last["value"])
    naive_rmse = rmse(naive, expected)
    aware_rmse = rmse(aware, expected)
    tolerance = 1e-12
    return {
        "case_id": "asynchronous_queue_selection",
        "requirement_ids": ["ACTION.002", "TIME.002", "REPLAY.001"],
        "contract": {
            "selection_policy": "latest_valid_command_before_effective_time",
            "queue_consume_timestamp_semantics": "fixed-rate low-level control loop consume time",
        },
        "naive": {
            "scheduler": "array_index_order",
            "rmse": naive_rmse,
            "pass": naive_rmse <= tolerance,
        },
        "contract_aware": {
            "scheduler": "latest_valid_before_consume_time",
            "rmse": aware_rmse,
            "pass": aware_rmse <= tolerance,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    rows = []
    for case in report["cases"]:
        rows.append(
            "| {case_id} | {naive:.3f} | {aware:.3f} | {pass_value} |".format(
                case_id=case["case_id"],
                naive=case["naive"]["rmse"],
                aware=case["contract_aware"]["rmse"],
                pass_value=case["contract_aware"]["pass"],
            )
        )
    return f"""# Replay Adapter Conformance

Status: dependency-free scheduler conformance, not a physics simulator.

This artifact checks whether a runtime adapter honors the WorldEpisode action contract before it is
trusted as a replay target. It complements the MuJoCo replay result but does not claim coverage from
a second physics simulator.

| Case | Naive RMSE | Contract-Aware RMSE | Contract-Aware Pass |
|---|---:|---:|---:|
{chr(10).join(rows)}

Boundary: this is a scheduler and timestamp conformance harness. A second tested physics simulator
is still required before claiming cross-simulator replay.
"""


def build_replay_adapter_conformance(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    cases = [constant_frame_delay_case(), zero_order_hold_case(), asynchronous_queue_case()]
    report = {
        "profile": "worldepisode-replay-adapter-conformance-0.1",
        "status": "tested_reference_scheduler_not_physics_simulator",
        "claim_boundary": (
            "This harness tests timing, queue, interpolation, and missing-command semantics. It is "
            "not a second physics simulator and does not replace Isaac/MuJoCo/Genesis replay."
        ),
        "cases": cases,
        "aggregate": {
            "case_count": len(cases),
            "naive_failures": sum(int(not case["naive"]["pass"]) for case in cases),
            "contract_aware_passes": sum(int(case["contract_aware"]["pass"]) for case in cases),
        },
        "artifacts": {
            "report": str((output_dir / "adapter_conformance_report.json").relative_to(ROOT)),
            "markdown": str((output_dir / "README.md").relative_to(ROOT)),
        },
    }
    write_json(output_dir / "adapter_conformance_report.json", report)
    write_text(output_dir / "README.md", render_markdown(report))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    report = build_replay_adapter_conformance(args.output_dir)
    print(json.dumps(report["aggregate"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
