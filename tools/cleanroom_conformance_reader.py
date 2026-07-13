#!/usr/bin/env python3
"""Clean-room WorldEpisode reader and conformance check.

This script deliberately does not import the `worldepisode` package. It is an internal clean-room
reader that parses the public schema, extracts a small semantic summary, and checks the committed
pilot/independent fixtures with separately implemented requirement logic. It is not an external
implementation or adoption claim.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "worldepisode-core-v0.schema.json"
MINIMAL_EXAMPLE = ROOT / "examples" / "minimal.worldepisode.json"
PILOT_FIXTURE_DIR = ROOT / "conformance" / "fixtures" / "pilot"
INDEPENDENT_FIXTURE_DIR = ROOT / "conformance" / "fixtures" / "independent"
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "experiments" / "cleanroom_reader"

SHA_RE = re.compile(r"^[a-f0-9]{64}$")
WORLD_REVISION_RE = re.compile(r"sha256:[a-f0-9]{64}")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def pointer(parts: list[str | int]) -> str:
    if not parts:
        return "/"
    return "/" + "/".join(str(part).replace("~", "~0").replace("/", "~1") for part in parts)


def walk_assets(value: Any, path: list[str | int] | None = None) -> list[tuple[str, dict[str, Any]]]:
    selected_path = [] if path is None else path
    assets: list[tuple[str, dict[str, Any]]] = []
    if isinstance(value, dict):
        if {"uri", "media_type", "sha256"}.issubset(value.keys()):
            assets.append((pointer(selected_path), value))
        for key, child in value.items():
            assets.extend(walk_assets(child, [*selected_path, key]))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            assets.extend(walk_assets(child, [*selected_path, index]))
    return assets


def schema_requirements(payload: dict[str, Any]) -> set[str]:
    validator = jsonschema.Draft202012Validator(load_json(SCHEMA_PATH))
    return {"SCHEMA.001" for _ in validator.iter_errors(payload)}


def cleanroom_requirements(payload: dict[str, Any]) -> set[str]:
    detected = set(schema_requirements(payload))
    clocks = {
        clock.get("clock_id")
        for clock in payload.get("clock_graph", {}).get("clocks", [])
        if isinstance(clock, dict)
    }
    frames = {
        frame.get("frame_id")
        for frame in payload.get("frame_graph", {}).get("frames", [])
        if isinstance(frame, dict)
    }
    entity_ids = {
        entity.get("entity_id")
        for entity in payload.get("entities", [])
        if isinstance(entity, dict)
    }

    if not clocks:
        detected.add("TIME.001")

    for mapping in payload.get("clock_graph", {}).get("mappings", []):
        if "drift_model" not in mapping or "estimated_error" not in mapping:
            detected.add("TIME.002")

    for transform in payload.get("frame_graph", {}).get("transforms", []):
        if transform.get("source_frame") not in frames or transform.get("target_frame") not in frames:
            detected.add("FRAME.001")
        if "valid_interval" not in transform:
            detected.add("FRAME.002")
        elif transform["valid_interval"].get("clock_id") not in clocks:
            detected.add("TIME.001")

    seen_entities: set[str] = set()
    for entity in payload.get("entities", []):
        entity_id = entity.get("entity_id")
        if entity_id in seen_entities:
            detected.add("ENTITY.001")
        seen_entities.add(entity_id)
        for rep in entity.get("representations", []):
            if "role" not in rep:
                detected.add("REP.001")
            if rep.get("coordinate_frame") not in frames:
                detected.add("FRAME.001")
            valid_interval = rep.get("valid_interval")
            if isinstance(valid_interval, dict) and valid_interval.get("clock_id") not in clocks:
                detected.add("TIME.001")

    for _, asset in walk_assets(payload):
        if not asset.get("uri") or not asset.get("media_type") or not SHA_RE.match(asset.get("sha256", "")):
            detected.add("ASSET.001")
        if asset.get("resolved_sha256") and asset["resolved_sha256"] != asset.get("sha256"):
            detected.add("ASSET.002")

    for channel in payload.get("action_space", {}).get("channels", []):
        for key in ("control_mode", "parameterization", "reference_frame", "units", "semantics"):
            if key not in channel:
                detected.add("ACTION.001")
        if channel.get("reference_frame") not in frames:
            detected.add("FRAME.001")
        if "command_timestamp_semantics" not in channel or "effective_timestamp_semantics" not in channel:
            detected.add("ACTION.002")

    world_revision_id = payload.get("world_revision", {}).get("world_revision_id", "")
    if not WORLD_REVISION_RE.search(world_revision_id):
        detected.add("WORLD.001")

    if "world_revision" not in payload or "world_deltas" not in payload:
        detected.add("TRACE.001")

    for event in payload.get("events", []):
        if event.get("clock_id") not in clocks:
            detected.add("TIME.001")
        for entity_id in event.get("entity_ids", []):
            if entity_id not in entity_ids:
                detected.add("ENTITY.001")

    for delta in payload.get("world_deltas", []):
        if delta.get("clock_id") not in clocks:
            detected.add("TIME.001")
        if delta.get("entity_id") not in entity_ids:
            detected.add("ENTITY.001")

    if "provenance" not in payload or "source" not in payload.get("provenance", {}):
        detected.add("PROV.001")
    if "quality" not in payload:
        detected.add("QUALITY.001")
    return detected


def semantic_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "episode_id": payload.get("episode", {}).get("episode_id"),
        "dataset_id": payload.get("episode", {}).get("dataset_id"),
        "world_revision_id": payload.get("world_revision", {}).get("world_revision_id"),
        "entity_count": len(payload.get("entities", [])),
        "action_channel_count": len(payload.get("action_space", {}).get("channels", [])),
        "clock_count": len(payload.get("clock_graph", {}).get("clocks", [])),
        "frame_count": len(payload.get("frame_graph", {}).get("frames", [])),
        "event_count": len(payload.get("events", [])),
        "delta_count": len(payload.get("world_deltas", [])),
        "asset_count": len(walk_assets(payload)),
    }


def evaluate_fixture_manifest(fixture_dir: Path) -> dict[str, Any]:
    manifest_path = fixture_dir / "manifest.json"
    manifest = load_json(manifest_path)
    cases = []
    expected_total = 0
    hit_total = 0
    false_positive_total = 0

    for section in ("valid", "invalid"):
        for case in manifest.get(section, []):
            payload = load_json(fixture_dir / case["path"])
            detected = cleanroom_requirements(payload)
            expected = set(case.get("expected_requirements", []))
            expected_total += len(expected)
            hit_total += len(expected & detected)
            false_positive_total += len(detected - expected)
            if section == "valid":
                passed = not detected
            else:
                passed = expected.issubset(detected)
            cases.append(
                {
                    "fixture_set": fixture_dir.name,
                    "section": section,
                    "path": case["path"],
                    "expected": sorted(expected),
                    "detected": sorted(detected),
                    "pass": passed,
                    "false_positive_requirements": sorted(detected - expected),
                }
            )

    return {
        "manifest": str(manifest_path.relative_to(ROOT)),
        "case_count": len(cases),
        "cases": cases,
        "expected_requirement_count": expected_total,
        "hit_requirement_count": hit_total,
        "false_positive_requirement_count": false_positive_total,
        "recall": round(hit_total / expected_total, 3) if expected_total else 1.0,
        "pass": all(case["pass"] for case in cases),
    }


def render_markdown(report: dict[str, Any]) -> str:
    rows = []
    for fixture_set in report["fixture_sets"]:
        rows.append(
            "| {manifest} | {case_count} | {recall:.3f} | {passed} | {false_positive_requirement_count} |".format(
                manifest=fixture_set["manifest"],
                case_count=fixture_set["case_count"],
                recall=fixture_set["recall"],
                passed=fixture_set["pass"],
                false_positive_requirement_count=fixture_set["false_positive_requirement_count"],
            )
        )
    return f"""# Clean-Room Reader Check

Status: {report["status"]}

This artifact is generated by a reader that does not import the `worldepisode` package. It parses
the public JSON Schema, extracts a semantic summary, and checks fixture requirement IDs with
separately implemented logic.

- Minimal example episode: `{report["minimal_summary"]["episode_id"]}`
- Minimal example world revision: `{report["minimal_summary"]["world_revision_id"]}`
- Minimal example assets: {report["minimal_summary"]["asset_count"]}
- Fixture sets: {report["aggregate"]["fixture_set_count"]}
- Cases: {report["aggregate"]["case_count"]}
- Recall: {report["aggregate"]["recall"]:.3f}

| Fixture manifest | Cases | Recall | Pass | False-positive requirements |
|---|---:|---:|---:|---:|
{chr(10).join(rows)}

Boundary: {report["claim_boundary"]}
"""


def build_cleanroom_reader_report(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    minimal_payload = load_json(MINIMAL_EXAMPLE)
    fixture_sets = [
        evaluate_fixture_manifest(PILOT_FIXTURE_DIR),
        evaluate_fixture_manifest(INDEPENDENT_FIXTURE_DIR),
    ]
    expected_total = sum(item["expected_requirement_count"] for item in fixture_sets)
    hit_total = sum(item["hit_requirement_count"] for item in fixture_sets)
    case_count = sum(item["case_count"] for item in fixture_sets)
    report = {
        "profile": "worldepisode-cleanroom-reader-0.1",
        "status": "pass" if all(item["pass"] for item in fixture_sets) else "fail",
        "pass": all(item["pass"] for item in fixture_sets),
        "schema": str(SCHEMA_PATH.relative_to(ROOT)),
        "minimal_example": str(MINIMAL_EXAMPLE.relative_to(ROOT)),
        "minimal_summary": semantic_summary(minimal_payload),
        "fixture_sets": fixture_sets,
        "aggregate": {
            "fixture_set_count": len(fixture_sets),
            "case_count": case_count,
            "expected_requirement_count": expected_total,
            "hit_requirement_count": hit_total,
            "false_positive_requirement_count": sum(item["false_positive_requirement_count"] for item in fixture_sets),
            "recall": round(hit_total / expected_total, 3) if expected_total else 1.0,
        },
        "claim_boundary": (
            "This is an internal clean-room reader check. It demonstrates that the public schema "
            "and fixtures can be consumed without the reference SDK, but it is not an external "
            "implementation or independent adoption."
        ),
        "artifacts": {
            "report": str((output_dir / "cleanroom_reader_report.json").relative_to(ROOT)),
            "markdown": str((output_dir / "README.md").relative_to(ROOT)),
        },
    }
    write_json(output_dir / "cleanroom_reader_report.json", report)
    write_text(output_dir / "README.md", render_markdown(report))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    report = build_cleanroom_reader_report(args.output_dir)
    print(json.dumps({"pass": report["pass"], **report["aggregate"]}, indent=2, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
