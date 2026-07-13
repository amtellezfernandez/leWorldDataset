#!/usr/bin/env python3
"""Deterministic non-robotics state-drift pilots for Universal Spatial State.

The robotics experiments are the deep evidence in this repository. These pilots keep the broader
Universal Spatial State (USS) framing honest by showing that the same invariant classes also catch
silent state drift in two adjacent spatial-computing domains:

1. a game-engine collision patch where the client asset remains loadable but no longer matches the
   authoritative collision state;
2. an autonomous-driving clock-domain offset where local camera/lidar logs are structurally valid
   but produce an invalid fused spatial state.

They are deterministic toy pilots, not measured Epic, Unity, or autonomous-vehicle fleet results.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "experiments" / "uss_state_drift_pilots"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def digest(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def point_in_rect(point: tuple[float, float], rect: dict[str, float]) -> bool:
    x, y = point
    return rect["xmin"] <= x <= rect["xmax"] and rect["ymin"] <= y <= rect["ymax"]


def sample_segment(
    start: tuple[float, float],
    end: tuple[float, float],
    steps: int = 60,
) -> list[tuple[float, float]]:
    return [
        (
            start[0] * (1.0 - index / steps) + end[0] * (index / steps),
            start[1] * (1.0 - index / steps) + end[1] * (index / steps),
        )
        for index in range(steps + 1)
    ]


def collides(path: list[tuple[float, float]], rect: dict[str, float]) -> bool:
    return any(point_in_rect(point, rect) for point in path)


def game_engine_collision_patch_case() -> dict[str, Any]:
    """A loadable client asset drifts from the authoritative server collision state."""

    client_collision = {"xmin": 0.78, "xmax": 0.88, "ymin": 0.20, "ymax": 0.40}
    authoritative_collision = {"xmin": 0.48, "xmax": 0.62, "ymin": -0.08, "ymax": 0.08}
    stale_client_asset = {
        "uri": "oci://example.invalid/game/arena@sha256:client-stale",
        "media_type": "model/vnd.engine-collision+json",
        "role": "collision",
        "collision_proxy": client_collision,
    }
    authoritative_asset = {
        "uri": "oci://example.invalid/game/arena@sha256:authoritative-patch",
        "media_type": "model/vnd.engine-collision+json",
        "role": "collision",
        "collision_proxy": authoritative_collision,
    }

    stale_hash = digest(stale_client_asset)
    authoritative_hash = digest(authoritative_asset)
    path = sample_segment((0.0, 0.0), (1.0, 0.0))
    detour = sample_segment((0.0, 0.0), (0.46, 0.20)) + sample_segment((0.46, 0.20), (1.0, 0.0))

    local_file_valid = "uri" in stale_client_asset and "media_type" in stale_client_asset
    stale_client_success = not collides(path, client_collision)
    authoritative_success = not collides(path, authoritative_collision)
    corrected_success = not collides(detour, authoritative_collision)
    detected = stale_hash != authoritative_hash

    return {
        "case_id": "game_engine_collision_patch_drift",
        "domain": "virtual_agent_telemetry",
        "failure_story": (
            "A client can load an old arena collision asset after a game patch, but the server's "
            "authoritative collision state has moved the obstacle into the avatar path."
        ),
        "local_file_valid": local_file_valid,
        "drifted_behavior": {
            "client_asset_sha256": stale_hash,
            "authoritative_asset_sha256": authoritative_hash,
            "client_reports_path_success": stale_client_success,
            "authoritative_path_success": authoritative_success,
        },
        "uss_contract": {
            "state_revision_id": f"uss-state-{authoritative_hash[:16]}",
            "state_ancestry": ["arena_v17", "patch_collision_proxy_v18"],
            "required_asset_descriptor": {
                "uri": authoritative_asset["uri"],
                "media_type": authoritative_asset["media_type"],
                "sha256": authoritative_hash,
                "mirrors": ["assets/game/arena_collision_v18.json"],
            },
            "detected": detected,
            "diagnostics": ["ASSET.002", "WORLD.001", "REP.001"],
            "corrected_behavior_success": corrected_success,
        },
        "claim_boundary": "Deterministic collision-state pilot; not measured on a production game engine.",
    }


def autonomous_vehicle_clock_drift_case() -> dict[str, Any]:
    """A camera/lidar clock-domain offset creates a valid file with invalid spatial fusion."""

    ego_speed_mps = 15.0
    true_clock_offset_s = 0.050
    tolerance_m = 0.20
    camera_observed_range_m = 18.0
    lidar_observed_range_m = camera_observed_range_m - ego_speed_mps * true_clock_offset_s

    naive_fusion_error_m = abs(camera_observed_range_m - lidar_observed_range_m)
    corrected_range_m = lidar_observed_range_m + ego_speed_mps * true_clock_offset_s
    corrected_error_m = abs(camera_observed_range_m - corrected_range_m)

    return {
        "case_id": "autonomous_vehicle_clock_domain_drift",
        "domain": "autonomous_driving_log",
        "failure_story": (
            "A camera stream and a lidar stream both deserialize correctly, but the cloud replay "
            "assumes one clock domain and fuses samples separated by 50 ms."
        ),
        "local_file_valid": True,
        "drifted_behavior": {
            "ego_speed_mps": ego_speed_mps,
            "undeclared_clock_offset_s": true_clock_offset_s,
            "camera_range_m": camera_observed_range_m,
            "lidar_range_m": lidar_observed_range_m,
            "naive_fusion_error_m": naive_fusion_error_m,
            "tolerance_m": tolerance_m,
            "behavior_valid": naive_fusion_error_m <= tolerance_m,
        },
        "uss_contract": {
            "clock_mapping": {
                "source_clock": "lidar_device_time",
                "target_clock": "camera_exposure_midpoint",
                "offset_s": true_clock_offset_s,
                "drift_model": "constant_offset",
                "estimated_error_s": 0.002,
            },
            "state_transition_invariant": {
                "max_fused_range_error_m": tolerance_m,
                "requires_clock_domain_mapping": True,
            },
            "corrected_fusion_error_m": corrected_error_m,
            "detected": naive_fusion_error_m > tolerance_m,
            "diagnostics": ["TIME.001", "TIME.002", "FRAME.001"],
            "corrected_behavior_success": corrected_error_m <= tolerance_m,
        },
        "claim_boundary": "Deterministic clock-offset pilot; not measured on a public AV dataset.",
    }


def render_markdown(report: dict[str, Any]) -> str:
    rows = []
    for case in report["cases"]:
        rows.append(
            "| {case_id} | {domain} | {valid} | {detected} | {corrected} | {diagnostics} |".format(
                case_id=case["case_id"],
                domain=case["domain"],
                valid=case["local_file_valid"],
                detected=case["uss_contract"]["detected"],
                corrected=case["uss_contract"]["corrected_behavior_success"],
                diagnostics=", ".join(case["uss_contract"]["diagnostics"]),
            )
        )
    return f"""# USS State Drift Pilots

Status: deterministic non-robotics pilots.

Universal Spatial State (USS) is the umbrella state-integrity contract. WorldEpisode is the
robotics-heavy reference profile evaluated in depth elsewhere in this repository. These pilots test
whether the same invariant vocabulary also catches silent drift in adjacent spatial domains.

| Case | Domain | Local File Valid | USS Detected Drift | USS Corrected Behavior | Diagnostics |
|---|---|---:|---:|---:|---|
{chr(10).join(rows)}

## Boundary

These cases are deliberately small. They support the paper's vocabulary claim that state ancestry,
asset digests, representation roles, frame/clock mappings, and transition invariants generalize
beyond robot episodes. They do not support claims about production game engines, autonomous-driving
fleets, or public AV benchmark prevalence.
"""


def build_uss_state_drift_pilots(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    cases = [game_engine_collision_patch_case(), autonomous_vehicle_clock_drift_case()]
    report = {
        "profile": "uss-state-drift-pilots-0.1",
        "status": "deterministic_non_robotics_pilots",
        "claim_boundary": (
            "The cases test the USS vocabulary outside robotics. They are not measured production "
            "game-engine or autonomous-driving dataset results."
        ),
        "cases": cases,
        "aggregate": {
            "case_count": len(cases),
            "local_file_valid_count": sum(int(case["local_file_valid"]) for case in cases),
            "drifted_behavior_successes": sum(
                int(case["drifted_behavior"].get("behavior_valid", case["drifted_behavior"].get("authoritative_path_success", False)))
                for case in cases
            ),
            "uss_detections": sum(int(case["uss_contract"]["detected"]) for case in cases),
            "uss_corrected_successes": sum(
                int(case["uss_contract"]["corrected_behavior_success"]) for case in cases
            ),
        },
        "artifacts": {
            "report": str((output_dir / "state_drift_report.json").relative_to(ROOT)),
            "markdown": str((output_dir / "README.md").relative_to(ROOT)),
        },
    }
    write_json(output_dir / "state_drift_report.json", report)
    write_text(output_dir / "README.md", render_markdown(report))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    report = build_uss_state_drift_pilots(args.output_dir)
    print(f"Wrote {report['artifacts']['report']}")
    print(f"Wrote {report['artifacts']['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
