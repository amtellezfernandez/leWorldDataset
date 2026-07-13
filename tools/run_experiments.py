#!/usr/bin/env python3
"""Run deterministic controlled experiments for the WorldEpisode draft.

The experiments are intentionally small enough to live in the public spec repository. Their purpose
is to provide reproducible evidence for conformance, conversion-loss, replay, split-leakage, and
counterfactual-augmentation behavior while keeping the limitations explicit.
"""

from __future__ import annotations

import copy
import json
import math
import os
import random
import re
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Callable

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_PATH = ROOT / "examples" / "minimal.worldepisode.json"
SCHEMA_PATH = ROOT / "schemas" / "worldepisode-core-v0.schema.json"
RESULTS_DIR = ROOT / "docs" / "experiments"
RESULTS_JSON = RESULTS_DIR / "results.json"
RESULTS_MD = RESULTS_DIR / "RESULTS.md"
PILOT_FIXTURE_DIR = ROOT / "conformance" / "fixtures" / "pilot"
BINDINGS_DIR = RESULTS_DIR / "bindings"
INDEPENDENT_FIXTURE_DIR = ROOT / "conformance" / "fixtures" / "independent"
RECORDED_EPISODES_DIR = RESULTS_DIR / "recorded_episodes"

SHA_RE = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True)
class Diagnostic:
    requirement: str
    location: str
    message: str


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def ptr(parts: list[str | int]) -> str:
    return "/" + "/".join(str(part) for part in parts)


def iter_assets(payload: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    assets: list[tuple[str, dict[str, Any]]] = []

    def walk(value: Any, path: list[str | int]) -> None:
        if isinstance(value, dict):
            if {"uri", "media_type", "sha256"}.issubset(value.keys()):
                assets.append((ptr(path), value))
            for key, child in value.items():
                walk(child, [*path, key])
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, [*path, index])

    walk(payload, [])
    return assets


def validate_semantics(payload: dict[str, Any]) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []

    def add(requirement: str, location: str, message: str) -> None:
        diagnostics.append(Diagnostic(requirement, location, message))

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
        add("TIME.001", "/clock_graph/clocks", "No declared clock domain.")

    for index, mapping in enumerate(payload.get("clock_graph", {}).get("mappings", [])):
        if "drift_model" not in mapping or "estimated_error" not in mapping:
            add("TIME.002", f"/clock_graph/mappings/{index}", "Cross-clock mapping lacks drift or error.")

    for index, transform in enumerate(payload.get("frame_graph", {}).get("transforms", [])):
        location = f"/frame_graph/transforms/{index}"
        if transform.get("source_frame") not in frames or transform.get("target_frame") not in frames:
            add("FRAME.001", location, "Transform references an unknown frame.")
        if "valid_interval" not in transform:
            add("FRAME.002", location, "Transform lacks valid interval.")
        else:
            clock_id = transform["valid_interval"].get("clock_id")
            if clock_id not in clocks:
                add("TIME.001", f"{location}/valid_interval", "Transform interval references an unknown clock.")

    seen_entities: set[str] = set()
    for entity_index, entity in enumerate(payload.get("entities", [])):
        entity_id = entity.get("entity_id")
        if entity_id in seen_entities:
            add("ENTITY.001", f"/entities/{entity_index}/entity_id", "Duplicate entity id.")
        seen_entities.add(entity_id)
        for rep_index, rep in enumerate(entity.get("representations", [])):
            location = f"/entities/{entity_index}/representations/{rep_index}"
            if "role" not in rep:
                add("REP.001", location, "Representation lacks role.")
            if rep.get("coordinate_frame") not in frames:
                add("FRAME.001", location, "Representation references an unknown frame.")
            valid_interval = rep.get("valid_interval")
            if isinstance(valid_interval, dict) and valid_interval.get("clock_id") not in clocks:
                add("TIME.001", f"{location}/valid_interval", "Representation interval references an unknown clock.")

    for location, asset in iter_assets(payload):
        if not asset.get("uri") or not asset.get("media_type") or not SHA_RE.match(asset.get("sha256", "")):
            add("ASSET.001", location, "Asset lacks deterministic URI, media type, or SHA-256 digest.")
        if asset.get("resolved_sha256") and asset["resolved_sha256"] != asset.get("sha256"):
            add("ASSET.002", location, "Resolved asset digest does not match declared digest.")

    for index, channel in enumerate(payload.get("action_space", {}).get("channels", [])):
        location = f"/action_space/channels/{index}"
        for key in ("control_mode", "parameterization", "reference_frame", "units", "semantics"):
            if key not in channel:
                add("ACTION.001", location, f"Action channel lacks {key}.")
        if channel.get("reference_frame") not in frames:
            add("FRAME.001", f"{location}/reference_frame", "Action references an unknown frame.")
        if "command_timestamp_semantics" not in channel or "effective_timestamp_semantics" not in channel:
            add("ACTION.002", location, "Action channel lacks command/effective timestamp semantics.")

    world_revision = payload.get("world_revision", {})
    world_revision_id = world_revision.get("world_revision_id", "")
    if not re.search(r"sha256:[a-f0-9]{64}", world_revision_id):
        add("WORLD.001", "/world_revision/world_revision_id", "World revision is not content-addressed.")

    if "world_revision" not in payload or "world_deltas" not in payload:
        add("TRACE.001", "/", "Episode does not declare a base world revision and ordered delta list.")

    for event_index, event in enumerate(payload.get("events", [])):
        if event.get("clock_id") not in clocks:
            add("TIME.001", f"/events/{event_index}/clock_id", "Event references an unknown clock.")
        for entity_id in event.get("entity_ids", []):
            if entity_id not in entity_ids:
                add("ENTITY.001", f"/events/{event_index}/entity_ids", "Event references an unknown entity.")

    for delta_index, delta in enumerate(payload.get("world_deltas", [])):
        if delta.get("clock_id") not in clocks:
            add("TIME.001", f"/world_deltas/{delta_index}/clock_id", "Delta references an unknown clock.")
        if delta.get("entity_id") not in entity_ids:
            add("ENTITY.001", f"/world_deltas/{delta_index}/entity_id", "Delta references an unknown entity.")

    if "provenance" not in payload or "source" not in payload.get("provenance", {}):
        add("PROV.001", "/provenance", "Missing source provenance.")

    if "quality" not in payload:
        add("QUALITY.001", "/quality", "Missing quality record.")

    return diagnostics


def validate_schema(payload: dict[str, Any]) -> list[str]:
    validator = jsonschema.Draft202012Validator(load_json(SCHEMA_PATH))
    return [error.message for error in validator.iter_errors(payload)]


def semantic_field_paths() -> list[str]:
    return [
        "episode.identity",
        "episode.task_outcome",
        "world_revision.identity",
        "world_revision.asset_descriptor",
        "embodiment.identity",
        "embodiment.urdf_asset",
        "frame_graph.frames",
        "frame_graph.transforms",
        "clock_graph.clocks",
        "clock_graph.mappings",
        "entities.identity",
        "entities.representation_roles",
        "entities.asset_descriptors",
        "action_space.control_contract",
        "action_space.timing_contract",
        "trace.binding",
        "trace.asset_descriptor",
        "events.interactions",
        "world_deltas.ordered_state_changes",
        "provenance.derivation",
        "quality.uncertainty",
        "splits.lineage_constraints",
        "replay.runtime_assumptions",
    ]


def binding_capabilities() -> dict[str, set[str]]:
    fields = semantic_field_paths()
    return {
        "worldepisode-reference": set(fields),
        "lerobot-v3-native": {
            "episode.identity",
            "episode.task_outcome",
            "clock_graph.clocks",
            "action_space.control_contract",
            "trace.binding",
            "trace.asset_descriptor",
        },
        "rerun-rrd": {
            "episode.identity",
            "frame_graph.frames",
            "frame_graph.transforms",
            "clock_graph.clocks",
            "clock_graph.mappings",
            "entities.identity",
            "trace.binding",
            "events.interactions",
        },
        "ncore": {
            "embodiment.identity",
            "frame_graph.frames",
            "frame_graph.transforms",
            "clock_graph.clocks",
            "clock_graph.mappings",
            "trace.asset_descriptor",
            "provenance.derivation",
        },
        "mcap-ros2": {
            "episode.identity",
            "frame_graph.frames",
            "frame_graph.transforms",
            "clock_graph.clocks",
            "action_space.control_contract",
            "trace.binding",
        },
        "openusd-simready": {
            "world_revision.identity",
            "world_revision.asset_descriptor",
            "embodiment.identity",
            "entities.identity",
            "entities.representation_roles",
            "entities.asset_descriptors",
            "frame_graph.frames",
            "frame_graph.transforms",
            "replay.runtime_assumptions",
        },
        "gltf-gaussian-asset": {
            "entities.identity",
            "entities.representation_roles",
            "entities.asset_descriptors",
            "world_revision.asset_descriptor",
        },
    }


def semantic_projection(payload: dict[str, Any]) -> dict[str, Any]:
    episode = payload.get("episode", {})
    world_revision = payload.get("world_revision", {})
    embodiment = payload.get("embodiment", {})
    frame_graph = payload.get("frame_graph", {})
    clock_graph = payload.get("clock_graph", {})
    entities = payload.get("entities", [])
    action_channels = payload.get("action_space", {}).get("channels", [])
    trace = payload.get("trace", {})
    quality = payload.get("quality", {})
    projection = {
        "episode.identity": {
            "episode_id": episode.get("episode_id"),
            "dataset_id": episode.get("dataset_id"),
        },
        "episode.task_outcome": {
            "task": payload.get("task"),
            "outcome": episode.get("outcome"),
            "split": episode.get("split"),
        },
        "world_revision.identity": {
            "world_revision_id": world_revision.get("world_revision_id"),
            "binding": world_revision.get("binding"),
        },
        "world_revision.asset_descriptor": world_revision.get("asset"),
        "embodiment.identity": {"embodiment_id": embodiment.get("embodiment_id")},
        "embodiment.urdf_asset": embodiment.get("urdf_asset"),
        "frame_graph.frames": frame_graph.get("frames", []),
        "frame_graph.transforms": frame_graph.get("transforms", []),
        "clock_graph.clocks": clock_graph.get("clocks", []),
        "clock_graph.mappings": clock_graph.get("mappings", []),
        "entities.identity": [
            {"entity_id": entity.get("entity_id"), "entity_type": entity.get("entity_type")}
            for entity in entities
        ],
        "entities.representation_roles": [
            {
                "entity_id": entity.get("entity_id"),
                "representations": [
                    {
                        "representation_id": rep.get("representation_id"),
                        "role": rep.get("role"),
                        "coordinate_frame": rep.get("coordinate_frame"),
                    }
                    for rep in entity.get("representations", [])
                ],
            }
            for entity in entities
        ],
        "entities.asset_descriptors": [
            {
                "entity_id": entity.get("entity_id"),
                "assets": [rep.get("asset") for rep in entity.get("representations", [])],
            }
            for entity in entities
        ],
        "action_space.control_contract": [
            {
                key: channel.get(key)
                for key in ("name", "actuator", "control_mode", "parameterization", "reference_frame", "units", "semantics")
            }
            for channel in action_channels
        ],
        "action_space.timing_contract": [
            {
                key: channel.get(key)
                for key in (
                    "command_timestamp_semantics",
                    "effective_timestamp_semantics",
                    "command_rate_hz",
                    "latency_model",
                    "interpolation",
                    "missing_value_policy",
                )
            }
            for channel in action_channels
        ],
        "trace.binding": trace.get("binding"),
        "trace.asset_descriptor": trace.get("asset"),
        "events.interactions": payload.get("events", []),
        "world_deltas.ordered_state_changes": payload.get("world_deltas", []),
        "provenance.derivation": payload.get("provenance"),
        "quality.uncertainty": quality,
        "splits.lineage_constraints": quality.get("split_constraints", []),
        "replay.runtime_assumptions": quality.get("replay_assumptions", {}),
    }
    return projection


def export_binding_artifact(
    payload: dict[str, Any],
    binding: str,
    native_fields: set[str],
    sidecar_fields: set[str],
    output_dir: Path,
) -> None:
    projection = semantic_projection(payload)
    output_dir.mkdir(parents=True, exist_ok=True)
    native_payload = {
        "binding": binding,
        "native_fields": sorted(native_fields),
        "fields": {field: projection[field] for field in sorted(native_fields)},
    }
    sidecar_payload = {
        "profile": "worldepisode-sidecar-0.1",
        "source_world_revision_id": payload["world_revision"]["world_revision_id"],
        "externalized_fields": sorted(sidecar_fields),
        "fields": {field: projection[field] for field in sorted(sidecar_fields)},
    }
    write_json(output_dir / "native.json", native_payload)
    write_json(output_dir / "worldepisode.sidecar.json", sidecar_payload)


def import_binding_artifact(output_dir: Path) -> dict[str, Any]:
    native = load_json(output_dir / "native.json")
    sidecar = load_json(output_dir / "worldepisode.sidecar.json")
    merged = {}
    merged.update(native["fields"])
    merged.update(sidecar["fields"])
    return merged


def experiment_binding_retention(base: dict[str, Any]) -> dict[str, Any]:
    fields = semantic_field_paths()
    projection = semantic_projection(base)
    capabilities = binding_capabilities()
    sidecar_capable = {
        binding: set(fields) - native
        for binding, native in capabilities.items()
        if binding != "gltf-gaussian-asset"
    }
    sidecar_capable["gltf-gaussian-asset"] = {
        "world_revision.identity",
        "provenance.derivation",
        "quality.uncertainty",
    }

    rows = []
    for binding, native in capabilities.items():
        externalized = sidecar_capable[binding]
        binding_dir = BINDINGS_DIR / binding
        export_binding_artifact(base, binding, native, externalized, binding_dir)
        native_roundtrip = load_json(binding_dir / "native.json")["fields"]
        merged_roundtrip = import_binding_artifact(binding_dir)
        native_preserved = {
            field
            for field in fields
            if field in native_roundtrip and native_roundtrip[field] == projection[field]
        }
        recovered = {
            field
            for field in fields
            if field in merged_roundtrip and merged_roundtrip[field] == projection[field]
        }
        rows.append(
            {
                "binding": binding,
                "native_preserved": len(native_preserved),
                "total_fields": len(fields),
                "native_retention": round(len(native_preserved) / len(fields), 3),
                "with_worldepisode_sidecar": round(len(recovered) / len(fields), 3),
                "externalized": sorted(externalized),
                "discarded": sorted(set(fields) - recovered),
                "artifact_dir": str(binding_dir.relative_to(ROOT)),
            }
        )
    return {"fields": fields, "bindings": rows, "artifact_root": str(BINDINGS_DIR.relative_to(ROOT))}


def experiment_lerobot_active_roundtrip() -> dict[str, Any]:
    try:
        from lerobot_worldepisode_roundtrip import RoundTripUnavailable, run_roundtrip_experiment, unavailable_report

        return run_roundtrip_experiment()
    except RoundTripUnavailable as exc:
        return unavailable_report(exc)
    except Exception as exc:  # noqa: BLE001 - report reproducibility blockers without hiding them.
        raise RuntimeError("active LeRobot round-trip failed") from exc


def mutated(payload: dict[str, Any], mutate: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    clone = copy.deepcopy(payload)
    mutate(clone)
    return clone


def fault_definitions() -> list[tuple[str, set[str], Callable[[dict[str, Any]], None]]]:
    return [
        ("TIME.001_missing_clock_domain", {"TIME.001"}, lambda p: p["clock_graph"].update({"clocks": []})),
        (
            "TIME.002_mapping_without_drift_or_error",
            {"TIME.002"},
            lambda p: p["clock_graph"].update(
                {"mappings": [{"source_clock": "camera", "target_clock": "episode_time", "offset": 0.01}]}
            ),
        ),
        ("FRAME.001_unknown_representation_frame", {"FRAME.001"}, lambda p: p["entities"][0]["representations"][0].update({"coordinate_frame": "bad_frame"})),
        ("FRAME.002_missing_transform_interval", {"FRAME.002"}, lambda p: p["frame_graph"]["transforms"][0].pop("valid_interval", None)),
        ("ENTITY.001_unknown_event_entity", {"ENTITY.001"}, lambda p: p["events"][0].update({"entity_ids": ["missing_entity"]})),
        ("REP.001_missing_representation_role", {"REP.001"}, lambda p: p["entities"][0]["representations"][0].pop("role", None)),
        ("ASSET.001_bad_digest", {"ASSET.001"}, lambda p: p["trace"]["asset"].update({"sha256": "not-a-sha"})),
        ("ASSET.002_digest_mismatch", {"ASSET.002"}, lambda p: p["trace"]["asset"].update({"resolved_sha256": "9" * 64})),
        ("ACTION.001_missing_action_frame", {"ACTION.001"}, lambda p: p["action_space"]["channels"][0].pop("reference_frame", None)),
        ("ACTION.002_missing_effective_time", {"ACTION.002"}, lambda p: p["action_space"]["channels"][0].pop("effective_timestamp_semantics", None)),
        ("WORLD.001_non_content_addressed_world", {"WORLD.001"}, lambda p: p["world_revision"].update({"world_revision_id": "world_demo_tabletop"})),
        ("TRACE.001_missing_delta_sequence", {"TRACE.001"}, lambda p: p.pop("world_deltas", None)),
        ("PROV.001_missing_provenance", {"PROV.001"}, lambda p: p.pop("provenance", None)),
        ("QUALITY.001_missing_quality", {"QUALITY.001"}, lambda p: p.pop("quality", None)),
    ]


def write_pilot_fixture_corpus(base: dict[str, Any]) -> None:
    valid_dir = PILOT_FIXTURE_DIR / "valid"
    invalid_dir = PILOT_FIXTURE_DIR / "invalid"
    valid_dir.mkdir(parents=True, exist_ok=True)
    invalid_dir.mkdir(parents=True, exist_ok=True)

    write_json(valid_dir / "minimal.worldepisode.json", base)
    manifest = {
        "description": "Deterministic pilot conformance corpus generated by tools/run_experiments.py.",
        "valid": [
            {
                "path": "valid/minimal.worldepisode.json",
                "expected_requirements": [],
            }
        ],
        "invalid": [],
    }
    for name, expected, mutator in fault_definitions():
        filename = f"{name}.worldepisode.json"
        write_json(invalid_dir / filename, mutated(base, mutator))
        manifest["invalid"].append(
            {
                "path": f"invalid/{filename}",
                "expected_requirements": sorted(expected),
            }
        )
    write_json(PILOT_FIXTURE_DIR / "manifest.json", manifest)


def experiment_fault_detection(base: dict[str, Any]) -> dict[str, Any]:
    faults = fault_definitions()

    cases = []
    tp = fp = fn = 0
    for name, expected, mutator in faults:
        diagnostics = validate_semantics(mutated(base, mutator))
        detected = {diag.requirement for diag in diagnostics}
        case_tp = len(expected & detected)
        case_fp = len(detected - expected)
        case_fn = len(expected - detected)
        tp += case_tp
        fp += case_fp
        fn += case_fn
        cases.append(
            {
                "case": name,
                "expected": sorted(expected),
                "detected": sorted(detected),
                "pass": case_fn == 0,
                "false_positive_requirements": sorted(detected - expected),
            }
        )

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "cases": cases,
        "n_cases": len(cases),
        "true_positive_requirements": tp,
        "false_positive_requirements": fp,
        "false_negative_requirements": fn,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
    }


def experiment_independent_fixtures() -> dict[str, Any]:
    manifest_path = INDEPENDENT_FIXTURE_DIR / "manifest.json"
    if not manifest_path.exists():
        return {"available": False, "cases": [], "recall": 0.0}
    manifest = load_json(manifest_path)
    cases = []
    hits = total = 0
    for case in manifest.get("invalid", []):
        payload = load_json(INDEPENDENT_FIXTURE_DIR / case["path"])
        detected = {diag.requirement for diag in validate_semantics(payload)}
        expected = set(case["expected_requirements"])
        hits += len(expected & detected)
        total += len(expected)
        cases.append(
            {
                "path": case["path"],
                "expected": sorted(expected),
                "detected": sorted(detected),
                "pass": expected.issubset(detected),
            }
        )
    return {
        "available": True,
        "manifest": str(manifest_path.relative_to(ROOT)),
        "n_cases": len(cases),
        "cases": cases,
        "recall": round(hits / total, 3) if total else 0.0,
    }


def rmse(a: list[float], b: list[float]) -> float:
    return math.sqrt(mean([(x - y) ** 2 for x, y in zip(a, b)]))


def replay_object(actions: list[float], latency_steps: int, follow_gain: float) -> list[float]:
    ee = 0.0
    obj = -0.2
    trajectory = []
    for t in range(len(actions)):
        delayed_index = t - latency_steps
        command = actions[delayed_index] if delayed_index >= 0 else 0.0
        ee += command
        grasped = t >= 12
        if grasped:
            obj += follow_gain * (ee - obj)
        trajectory.append(obj)
    return trajectory


def experiment_replay() -> dict[str, Any]:
    actions = [0.018] * 12 + [0.012] * 12 + [-0.006] * 12 + [0.0] * 4
    observed = replay_object(actions, latency_steps=2, follow_gain=0.92)
    declared = replay_object(actions, latency_steps=2, follow_gain=0.86)
    naive = replay_object(actions, latency_steps=0, follow_gain=0.90)
    alternate_engine = replay_object(actions, latency_steps=2, follow_gain=0.82)
    return {
        "steps": len(actions),
        "declared_latency_rmse": round(rmse(observed, declared), 5),
        "naive_command_time_rmse": round(rmse(observed, naive), 5),
        "alternate_engine_rmse": round(rmse(observed, alternate_engine), 5),
        "latency_model_improvement_over_naive": round(
            rmse(observed, naive) / max(rmse(observed, declared), 1e-12),
            2,
        ),
    }


def experiment_lerobot_public_sample() -> dict[str, Any]:
    # First frame of episode 0 from lerobot/svla_so101_pickplace, mirrored in
    # URDF Studio's offline tests to avoid network-dependent evaluation.
    joint_deg = [1.9560878, -98.74372, 98.92424, 74.81983, -51.45299, 1.40939]
    joint_rad = [math.radians(value) for value in joint_deg]
    # FK position from URDF Studio's SO-101 offline fixture.
    ee_xyz_m = [0.1044, -0.00242, 0.07292]
    degree_interpreted_as_radian_max_abs = max(abs(value) for value in joint_deg)
    return {
        "source": "lerobot/svla_so101_pickplace episode 0 frame 0, offline mirrored fixture",
        "joint_count": len(joint_deg),
        "max_abs_joint_deg": round(max(abs(value) for value in joint_deg), 5),
        "max_abs_joint_rad": round(max(abs(value) for value in joint_rad), 5),
        "degree_interpreted_as_radian_max_abs": round(degree_interpreted_as_radian_max_abs, 5),
        "ee_xyz_m": ee_xyz_m,
        "ee_within_0_5m_workspace": all(abs(value) < 0.5 for value in ee_xyz_m),
        "unit_contract_required": degree_interpreted_as_radian_max_abs > math.pi,
    }


def experiment_lerobot_style_episode_set() -> dict[str, Any]:
    RECORDED_EPISODES_DIR.mkdir(parents=True, exist_ok=True)
    base_joint_deg = [1.9560878, -98.74372, 98.92424, 74.81983, -51.45299, 1.40939]
    frames = []
    actions = []
    for index in range(10):
        timestamp_ms = index * 100
        joint_deg = [
            base_joint_deg[0] + index * 0.4,
            base_joint_deg[1],
            base_joint_deg[2] - index * 0.15,
            base_joint_deg[3],
            base_joint_deg[4] + index * 0.1,
            base_joint_deg[5],
        ]
        frames.append(
            {
                "frame_index": index,
                "timestamp_ms": timestamp_ms,
                "observation": {
                    "state_joint_degrees": joint_deg,
                    "state_joint_radians": [round(math.radians(value), 8) for value in joint_deg],
                    "camera": "offline_public_fixture",
                    "entities": ["so101", "work_surface", "target_object"],
                },
            }
        )
        if index < 9:
            actions.append(
                {
                    "frame_index": index,
                    "command_timestamp_ms": timestamp_ms,
                    "effective_timestamp_ms": timestamp_ms + 20,
                    "action_delta_xyz_m": [0.005, 0.0, 0.0],
                    "reference_frame": "tool0",
                    "semantics": "delta",
                }
            )
    payload = {
        "source": "LeRobot-style offline episode derived from mirrored public SO-101 frame",
        "source_frame": "lerobot/svla_so101_pickplace episode 0 frame 0",
        "robot": "so101",
        "frames": frames,
        "actions": actions,
        "action_contract": {
            "control_mode": "cartesian_position",
            "parameterization": "delta_xyz",
            "reference_frame": "tool0",
            "units": "m",
            "command_timestamp_semantics": "controller enqueue time",
            "effective_timestamp_semantics": "command timestamp plus 20 ms declared latency",
        },
    }
    output_path = RECORDED_EPISODES_DIR / "so101_lerobot_style_episode.json"
    write_json(output_path, payload)
    return {
        "artifact": str(output_path.relative_to(ROOT)),
        "frame_count": len(frames),
        "action_count": len(actions),
        "duration_ms": frames[-1]["timestamp_ms"] - frames[0]["timestamp_ms"],
        "declared_latency_ms": 20,
        "has_command_and_effective_timestamps": all(
            "command_timestamp_ms" in action and "effective_timestamp_ms" in action
            for action in actions
        ),
    }


def make_split_dataset() -> list[dict[str, Any]]:
    rows = []
    for world in range(8):
        for entity in range(4):
            for episode in range(6):
                label = 1 if ((world * 5 + entity * 3) % 7) >= 3 else 0
                rows.append(
                    {
                        "world": f"world_{world}",
                        "entity": f"entity_{entity}",
                        "episode": episode,
                        "label": label,
                    }
                )
    return rows


def memorize_eval(train: list[dict[str, Any]], test: list[dict[str, Any]], key_fields: tuple[str, ...]) -> dict[str, float]:
    memory: dict[tuple[Any, ...], int] = {}
    for row in train:
        key = tuple(row[field] for field in key_fields)
        memory[key] = row["label"]
    majority = 1 if sum(row["label"] for row in train) >= len(train) / 2 else 0
    correct = 0
    leaked = 0
    for row in test:
        key = tuple(row[field] for field in key_fields)
        prediction = memory.get(key, majority)
        leaked += int(key in memory)
        correct += int(prediction == row["label"])
    return {
        "accuracy": round(correct / len(test), 3),
        "leakage_rate": round(leaked / len(test), 3),
    }


def experiment_split_leakage() -> dict[str, Any]:
    rows = make_split_dataset()
    random_split_train = [row for index, row in enumerate(rows) if index % 5 != 0]
    random_split_test = [row for index, row in enumerate(rows) if index % 5 == 0]
    world_train = [row for row in rows if row["world"] not in {"world_6", "world_7"}]
    world_test = [row for row in rows if row["world"] in {"world_6", "world_7"}]
    entity_train = [row for row in rows if row["entity"] in {"entity_0", "entity_1"}]
    entity_test = [row for row in rows if row["entity"] in {"entity_2", "entity_3"}]
    return {
        "random_episode_split": memorize_eval(random_split_train, random_split_test, ("world", "entity")),
        "world_disjoint_split": memorize_eval(world_train, world_test, ("world", "entity")),
        "entity_disjoint_split": memorize_eval(entity_train, entity_test, ("world", "entity")),
    }


def nearest_regression(train_x: list[tuple[float, ...]], train_y: list[float], x: tuple[float, ...]) -> float:
    best_index = min(
        range(len(train_x)),
        key=lambda index: sum((a - b) ** 2 for a, b in zip(train_x[index], x)),
    )
    return train_y[best_index]


def success_rate(train_x: list[tuple[float, ...]], train_y: list[float], test: list[tuple[float, float]]) -> float:
    successes = 0
    for object_dx, camera_shift in test:
        x = (object_dx + camera_shift,) if len(train_x[0]) == 1 else (object_dx, camera_shift)
        pred = nearest_regression(train_x, train_y, x)
        successes += int(abs(pred - object_dx) <= 0.08)
    return round(successes / len(test), 3)


def experiment_counterfactual_robustness() -> dict[str, Any]:
    rng = random.Random(7)
    base = [(rng.uniform(-0.08, 0.08), rng.uniform(-0.05, 0.05)) for _ in range(80)]
    test = [(rng.uniform(-0.25, 0.25), rng.uniform(0.25, 0.55)) for _ in range(120)]

    obs_x = [(object_dx + camera_shift,) for object_dx, camera_shift in base]
    obs_y = [object_dx for object_dx, _ in base]

    noisy_world_x = [(object_dx + rng.uniform(-0.12, 0.12), camera_shift) for object_dx, camera_shift in base]
    noisy_world_y = [object_dx for object_dx, _ in base]

    augmented = []
    for object_dx, _camera_shift in base:
        for camera_shift in (-0.45, -0.2, 0.0, 0.25, 0.5):
            augmented.append((object_dx, camera_shift))
    we_x = augmented
    we_y = [object_dx for object_dx, _ in augmented]

    return {
        "observations_only_success": success_rate(obs_x, obs_y, test),
        "unstructured_3d_side_files_success": success_rate(noisy_world_x, noisy_world_y, test),
        "worldepisode_counterfactual_success": success_rate(we_x, we_y, test),
        "test_cases": len(test),
    }


def write_report(results: dict[str, Any]) -> None:
    binding_rows = "\n".join(
        "| {binding} | {native_retention:.3f} | {with_worldepisode_sidecar:.3f} | {discarded_count} |".format(
            discarded_count=len(row["discarded"]),
            **row,
        )
        for row in results["rq1_binding_retention"]["bindings"]
    )
    fault = results["rq2_fault_detection"]
    replay = results["rq3_replay"]
    splits = results["rq5_split_leakage"]
    robust = results["rq4_counterfactual_robustness"]
    independent = results["independent_fixture_check"]
    public_sample = results["lerobot_public_sample"]
    episode_set = results["lerobot_style_episode_set"]
    active_lerobot = results["lerobot_active_roundtrip"]
    if active_lerobot.get("available"):
        active_metrics = active_lerobot["metrics"]
        active_section = f"""## Active LeRobot -> WorldEpisode -> LeRobot Round-Trip

- Source: `{active_lerobot["repo_id"]}@{active_lerobot["revision"]}`
- Episode: {active_lerobot["episode_index"]}
- Exported LeRobot v3 package: `{active_lerobot["artifacts"]["exported_lerobot_v3"]}`
- Action tensor rows x width: {active_metrics["action_rows"]} x {active_metrics["action_width"]}
- Video streams with timestamp ranges: {active_metrics["video_streams"]}
- Physical frame records preserved through sidecar: {active_metrics["physical_frames_preserved"]}
- Max absolute action error: {active_metrics["max_abs_action_error"]:.1f}
- Max absolute state error: {active_metrics["max_abs_state_error"]:.1f}
- Max absolute timestamp error: {active_metrics["max_abs_timestamp_error"]:.1f}
- Max absolute video timestamp error: {active_metrics["max_abs_video_timestamp_error"]:.1f}
- Explicitly tracked source-absent fields: {active_metrics["source_absent_fields_tracked"]}
- Discarded fields: {len(active_metrics["discarded_fields"])}
"""
    else:
        active_section = f"""## Active LeRobot -> WorldEpisode -> LeRobot Round-Trip

- Available: false
- Reason: {active_lerobot.get("reason", "unknown")}
- Reproduce: `{active_lerobot.get("reproduce", "python3 tools/lerobot_worldepisode_roundtrip.py --required")}`
"""
    report = f"""# WorldEpisode Controlled Experiment Results

Generated by `python3 tools/run_experiments.py`.

These deterministic controlled experiments test whether the proposed semantics are executable and
whether omitting them changes measurable outcomes. They are scoped experiments, not a replacement
for large multi-lab robot benchmarking.

The same command materializes binding round-trip artifacts in `docs/experiments/bindings/`, a pilot
conformance corpus in `conformance/fixtures/pilot/`, and checks hand-authored independent fixtures in
`conformance/fixtures/independent/`.

## RQ1: Binding Retention

| Binding | Native Retention | With WorldEpisode Sidecar | Discarded Fields |
|---|---:|---:|---:|
{binding_rows}

{active_section}

## RQ2: Fault Detection

- Cases: {fault["n_cases"]}
- Requirement precision: {fault["precision"]:.3f}
- Requirement recall: {fault["recall"]:.3f}
- False-negative requirement detections: {fault["false_negative_requirements"]}
- Independent fixture cases: {independent.get("n_cases", 0)}
- Independent fixture recall: {independent.get("recall", 0.0):.3f}

## Public LeRobot Sample Check

- Source: {public_sample["source"]}
- Joint count: {public_sample["joint_count"]}
- Max absolute joint value if interpreted as degrees: {public_sample["max_abs_joint_deg"]:.3f}
- Max absolute joint value after radian conversion: {public_sample["max_abs_joint_rad"]:.3f}
- End-effector position: {public_sample["ee_xyz_m"]} m
- Within 0.5 m SO-101 workspace bound: {public_sample["ee_within_0_5m_workspace"]}
- Unit contract required: {public_sample["unit_contract_required"]}

## LeRobot-Style Episode Artifact

- Artifact: `{episode_set["artifact"]}`
- Frames: {episode_set["frame_count"]}
- Actions: {episode_set["action_count"]}
- Duration: {episode_set["duration_ms"]} ms
- Declared latency: {episode_set["declared_latency_ms"]} ms
- Command/effective timestamps present: {episode_set["has_command_and_effective_timestamps"]}

## RQ3: Replay Timing

- Declared latency RMSE: {replay["declared_latency_rmse"]:.5f}
- Naive command-time RMSE: {replay["naive_command_time_rmse"]:.5f}
- Alternate-engine RMSE under declared assumptions: {replay["alternate_engine_rmse"]:.5f}
- Declared latency improvement over naive timing: {replay["latency_model_improvement_over_naive"]:.2f}x

## RQ4: Counterfactual Robustness

- Observations only success: {robust["observations_only_success"]:.3f}
- Unstructured 3D side files success: {robust["unstructured_3d_side_files_success"]:.3f}
- WorldEpisode counterfactual success: {robust["worldepisode_counterfactual_success"]:.3f}
- Shifted test cases: {robust["test_cases"]}

## RQ5: Lineage-Safe Splits

| Split | Leakage Rate | Memorization Accuracy |
|---|---:|---:|
| Random episode | {splits["random_episode_split"]["leakage_rate"]:.3f} | {splits["random_episode_split"]["accuracy"]:.3f} |
| World-disjoint | {splits["world_disjoint_split"]["leakage_rate"]:.3f} | {splits["world_disjoint_split"]["accuracy"]:.3f} |
| Entity-disjoint | {splits["entity_disjoint_split"]["leakage_rate"]:.3f} | {splits["entity_disjoint_split"]["accuracy"]:.3f} |
"""
    RESULTS_MD.write_text(report, encoding="utf-8")


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    base = load_json(EXAMPLE_PATH)
    schema_errors = validate_schema(base)
    semantic_errors = validate_semantics(base)
    if schema_errors or semantic_errors:
        print("Baseline example must pass before experiments run.")
        for error in schema_errors:
            print(f"SCHEMA {error}")
        for diag in semantic_errors:
            print(f"{diag.requirement} {diag.location}: {diag.message}")
        return 1

    write_pilot_fixture_corpus(base)

    results = {
        "source_example": str(EXAMPLE_PATH.relative_to(ROOT)),
        "baseline_schema_errors": len(schema_errors),
        "baseline_semantic_errors": len(semantic_errors),
        "rq1_binding_retention": experiment_binding_retention(base),
        "lerobot_active_roundtrip": experiment_lerobot_active_roundtrip(),
        "rq2_fault_detection": experiment_fault_detection(base),
        "independent_fixture_check": experiment_independent_fixtures(),
        "rq3_replay": experiment_replay(),
        "lerobot_public_sample": experiment_lerobot_public_sample(),
        "lerobot_style_episode_set": experiment_lerobot_style_episode_set(),
        "rq4_counterfactual_robustness": experiment_counterfactual_robustness(),
        "rq5_split_leakage": experiment_split_leakage(),
    }
    write_json(RESULTS_JSON, results)
    write_report(results)

    fault = results["rq2_fault_detection"]
    robust = results["rq4_counterfactual_robustness"]
    replay = results["rq3_replay"]
    if fault["recall"] < 1.0:
        print("Fault detection recall is below the required pilot threshold.")
        return 1
    independent = results["independent_fixture_check"]
    if independent["available"] and independent["recall"] < 1.0:
        print("Independent fixture recall is below the required threshold.")
        return 1
    if robust["worldepisode_counterfactual_success"] <= robust["observations_only_success"]:
        print("Counterfactual pilot did not improve over observations-only baseline.")
        return 1
    if replay["declared_latency_rmse"] >= replay["naive_command_time_rmse"]:
        print("Replay pilot did not improve with declared latency.")
        return 1
    active_lerobot = results["lerobot_active_roundtrip"]
    if os.environ.get("WORLDEPISODE_REQUIRE_ACTIVE_LEROBOT") == "1" and not active_lerobot.get("pass"):
        print("Active LeRobot round-trip is required but did not pass.")
        return 1

    print(f"Wrote {RESULTS_JSON.relative_to(ROOT)}")
    print(f"Wrote {RESULTS_MD.relative_to(ROOT)}")
    print(f"Fault detection: precision={fault['precision']:.3f}, recall={fault['recall']:.3f}")
    print(
        "Counterfactual success: "
        f"{robust['observations_only_success']:.3f} -> {robust['worldepisode_counterfactual_success']:.3f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
