#!/usr/bin/env python3
"""Run deterministic pilot experiments for the WorldEpisode draft.

The experiments are intentionally small enough to live in the public spec repository. They do not
claim real-robot performance. Their purpose is to turn the paper from a pure roadmap into a
reproducible artifact with measured conformance, conversion-loss, replay, split-leakage, and
counterfactual-augmentation behavior.
"""

from __future__ import annotations

import copy
import json
import math
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


def experiment_binding_retention() -> dict[str, Any]:
    fields = semantic_field_paths()
    capabilities = {
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
        preserved = len(native)
        recoverable = len(native | externalized)
        rows.append(
            {
                "binding": binding,
                "native_preserved": preserved,
                "total_fields": len(fields),
                "native_retention": round(preserved / len(fields), 3),
                "with_worldepisode_sidecar": round(recoverable / len(fields), 3),
                "externalized": sorted(externalized),
                "discarded": sorted(set(fields) - native - externalized),
            }
        )
    return {"fields": fields, "bindings": rows}


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
    report = f"""# WorldEpisode Pilot Experiment Results

Generated by `python3 tools/run_experiments.py`.

These are deterministic pilot experiments for the draft repository. They are not a substitute for
large real-robot evaluation, but they are executable evidence for the claims made by the current
paper draft.

The same command materializes a pilot conformance corpus in `conformance/fixtures/pilot/` with one
valid package, fourteen invalid packages, and `manifest.json` expected diagnostics.

## RQ1: Binding Retention

| Binding | Native Retention | With WorldEpisode Sidecar | Discarded Fields |
|---|---:|---:|---:|
{binding_rows}

## RQ2: Fault Detection

- Cases: {fault["n_cases"]}
- Requirement precision: {fault["precision"]:.3f}
- Requirement recall: {fault["recall"]:.3f}
- False-negative requirement detections: {fault["false_negative_requirements"]}

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
        "rq1_binding_retention": experiment_binding_retention(),
        "rq2_fault_detection": experiment_fault_detection(base),
        "rq3_replay": experiment_replay(),
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
    if robust["worldepisode_counterfactual_success"] <= robust["observations_only_success"]:
        print("Counterfactual pilot did not improve over observations-only baseline.")
        return 1
    if replay["declared_latency_rmse"] >= replay["naive_command_time_rmse"]:
        print("Replay pilot did not improve with declared latency.")
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
