#!/usr/bin/env python3
"""Run deterministic controlled experiments for the WorldEpisode v0 RFC.

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
import sys
from pathlib import Path
from typing import Any, Callable

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from worldepisode.validator import validate_semantics

EXAMPLE_PATH = ROOT / "examples" / "minimal.worldepisode.json"
SCHEMA_PATH = ROOT / "schemas" / "worldepisode-core-v0.schema.json"
CONFORMANCE_REQUIREMENTS_PATH = ROOT / "conformance" / "requirements.v0.json"
SEMANTIC_PROJECTION_SCHEMA_PATH = ROOT / "schemas" / "semantic-projection-v0.schema.json"
SEMANTIC_PROJECTION_PROFILE_PATH = ROOT / "conformance" / "projections" / "uss-core-23.v0.json"
RESULTS_DIR = ROOT / "docs" / "experiments"
RESULTS_JSON = RESULTS_DIR / "results.json"
RESULTS_MD = RESULTS_DIR / "RESULTS.md"
PILOT_FIXTURE_DIR = ROOT / "conformance" / "fixtures" / "pilot"
BINDINGS_DIR = RESULTS_DIR / "bindings"
INDEPENDENT_FIXTURE_DIR = ROOT / "conformance" / "fixtures" / "independent"
RECORDED_EPISODES_DIR = RESULTS_DIR / "recorded_episodes"
SCENE_LEAKAGE_REPORT = RESULTS_DIR / "lerobot_scene_leakage" / "leakage_report.json"
CONTROL_REPLAY_REPORT = RESULTS_DIR / "lerobot_control_replay" / "control_replay_report.json"
CONTACT_RICH_REPLAY_REPORT = RESULTS_DIR / "contact_rich_replay" / "contact_rich_replay_report.json"
CONTACT_RICH_REPLAY_PROTOCOL = RESULTS_DIR / "contact_rich_replay" / "protocol.json"
POLICY_GATE_REPORT = RESULTS_DIR / "lerobot_policy_gate" / "policy_gate_report.json"
TEMPORAL_POLICY_REPORT = RESULTS_DIR / "lerobot_temporal_policy_baseline" / "temporal_policy_report.json"
CONVERSION_SCALE_REPORT = RESULTS_DIR / "lerobot_conversion_scale" / "scale_report.json"
MULTITRAJECTORY_TIMING_REPORT = (
    RESULTS_DIR / "lerobot_multitrajectory_timing" / "timing_report.json"
)
BENCHMARK_CALLOUT_REPORT = RESULTS_DIR / "benchmark_callout_audit" / "benchmark_callout_report.json"
BENCHMARK_INFLATION_GATE_REPORT = RESULTS_DIR / "benchmark_inflation_gate" / "gate_report.json"
PREFLIGHT_REPORT = RESULTS_DIR / "preflight" / "preflight_report.json"
REALTOSIM_DRIFT_REPORT = RESULTS_DIR / "realtosim_contract_drift" / "contract_drift_report.json"
META_SIMULATOR_REPORT = RESULTS_DIR / "meta_simulator_contract" / "adapter_contract_report.json"
USS_STATE_DRIFT_REPORT = RESULTS_DIR / "uss_state_drift_pilots" / "state_drift_report.json"
REPLAY_ADAPTER_CONFORMANCE_REPORT = RESULTS_DIR / "replay_adapter_conformance" / "adapter_conformance_report.json"
DATASET_SCALE_AUDIT_REPORT = RESULTS_DIR / "dataset_scale_audit" / "scale_audit_report.json"
DATASET_SCALE_PERFORMANCE_REPORT = RESULTS_DIR / "dataset_scale_performance" / "performance_report.json"
CLEANROOM_READER_REPORT = RESULTS_DIR / "cleanroom_reader" / "cleanroom_reader_report.json"
ROUNDTRIP_BATCH_REPORT = RESULTS_DIR / "lerobot_worldepisode_roundtrip" / "batch_roundtrip_report.json"
SECONDARY_ROUNDTRIP_BATCH_REPORTS = (
    RESULTS_DIR / "lerobot_worldepisode_roundtrip_pusht" / "batch_roundtrip_report.json",
)
NATURAL_FAILURE_DIR = RESULTS_DIR / "natural_failure_corpus"
NATURAL_FAILURE_DATASET_DIR = NATURAL_FAILURE_DIR / "datasets"
NATURAL_FAILURE_DIAGNOSTICS = NATURAL_FAILURE_DIR / "dataset_diagnostics.json"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def validate_schema(payload: dict[str, Any]) -> list[str]:
    validator = jsonschema.Draft202012Validator(load_json(SCHEMA_PATH))
    return [error.message for error in validator.iter_errors(payload)]


def semantic_projection_profile() -> dict[str, Any]:
    profile = load_json(SEMANTIC_PROJECTION_PROFILE_PATH)
    schema_validator = jsonschema.Draft202012Validator(load_json(SEMANTIC_PROJECTION_SCHEMA_PATH))
    schema_errors = sorted(schema_validator.iter_errors(profile), key=lambda error: list(error.path))
    if schema_errors:
        messages = []
        for error in schema_errors:
            location = ".".join(str(part) for part in error.path) or "<root>"
            messages.append(f"{location}: {error.message}")
        raise ValueError("semantic projection profile failed schema validation: " + "; ".join(messages))

    fields = [field["path"] for field in profile["fields"]]
    duplicate_fields = sorted({field for field in fields if fields.count(field) > 1})
    if duplicate_fields:
        raise ValueError(f"semantic projection profile has duplicate field path(s): {duplicate_fields}")
    if profile["field_count"] != len(fields):
        raise ValueError(
            "semantic projection profile field_count does not match fields length: "
            f"{profile['field_count']} != {len(fields)}"
        )

    requirement_ids = {item["id"] for item in load_json(CONFORMANCE_REQUIREMENTS_PATH)["requirements"]}
    unknown_requirements = sorted(
        {
            requirement_id
            for field in profile["fields"]
            for requirement_id in field["requirement_ids"]
            if requirement_id not in requirement_ids
        }
    )
    if unknown_requirements:
        raise ValueError(
            "semantic projection profile references unknown requirement id(s): "
            + ", ".join(unknown_requirements)
        )

    field_set = set(fields)
    binding_names = [binding["binding"] for binding in profile["binding_models"]]
    duplicate_bindings = sorted({binding for binding in binding_names if binding_names.count(binding) > 1})
    if duplicate_bindings:
        raise ValueError(f"semantic projection profile has duplicate binding model(s): {duplicate_bindings}")

    bad_refs = []
    for binding in profile["binding_models"]:
        for field in [*binding.get("native_fields", []), *binding.get("sidecar_fields", [])]:
            if field not in field_set:
                bad_refs.append(f"{binding['binding']}:{field}")
        if binding["sidecar_policy"] == "listed_only" and "sidecar_fields" not in binding:
            bad_refs.append(f"{binding['binding']}:listed_only_without_sidecar_fields")
    if bad_refs:
        raise ValueError("semantic projection profile has unknown field reference(s): " + ", ".join(bad_refs))

    return profile


def semantic_field_paths(profile: dict[str, Any] | None = None) -> list[str]:
    selected = profile if profile is not None else semantic_projection_profile()
    return [field["path"] for field in selected["fields"]]


def binding_capabilities(profile: dict[str, Any] | None = None) -> dict[str, set[str]]:
    selected = profile if profile is not None else semantic_projection_profile()
    return {
        binding["binding"]: set(binding.get("native_fields", []))
        for binding in selected["binding_models"]
    }


def binding_sidecar_fields(profile: dict[str, Any] | None = None) -> dict[str, set[str]]:
    selected = profile if profile is not None else semantic_projection_profile()
    fields = set(semantic_field_paths(selected))
    sidecars = {}
    for binding in selected["binding_models"]:
        native = set(binding.get("native_fields", []))
        if binding["sidecar_policy"] == "all_missing":
            sidecars[binding["binding"]] = fields - native
        else:
            sidecars[binding["binding"]] = set(binding.get("sidecar_fields", []))
    return sidecars


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
    profile = semantic_projection_profile()
    fields = semantic_field_paths(profile)
    projection = semantic_projection(base)
    missing_projection_fields = sorted(set(fields) - set(projection))
    if missing_projection_fields:
        raise ValueError(
            "semantic projection profile contains field(s) not emitted by semantic_projection(): "
            + ", ".join(missing_projection_fields)
        )
    capabilities = binding_capabilities(profile)
    sidecar_capable = binding_sidecar_fields(profile)

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
    return {
        "projection_profile": {
            "profile_id": profile["profile_id"],
            "version": profile["version"],
            "status": profile["status"],
            "artifact": str(SEMANTIC_PROJECTION_PROFILE_PATH.relative_to(ROOT)),
            "schema": str(SEMANTIC_PROJECTION_SCHEMA_PATH.relative_to(ROOT)),
            "field_count": profile["field_count"],
            "binding_model_count": len(profile["binding_models"]),
            "claim_boundary": profile["claim_boundary"],
        },
        "fields": fields,
        "bindings": rows,
        "artifact_root": str(BINDINGS_DIR.relative_to(ROOT)),
    }


def committed_lerobot_roundtrip_report() -> dict[str, Any] | None:
    report_path = RESULTS_DIR / "lerobot_worldepisode_roundtrip" / "roundtrip_report.json"
    if not report_path.exists():
        return None
    report = load_json(report_path)
    if ROUNDTRIP_BATCH_REPORT.exists():
        report["batch_roundtrip"] = load_json(ROUNDTRIP_BATCH_REPORT)
    secondary_reports = []
    for path in SECONDARY_ROUNDTRIP_BATCH_REPORTS:
        if path.exists():
            secondary = load_json(path)
            secondary["artifact"] = str(path.relative_to(ROOT))
            secondary_reports.append(secondary)
    if secondary_reports:
        report["secondary_batch_roundtrips"] = secondary_reports
    return report


def experiment_lerobot_active_roundtrip() -> dict[str, Any]:
    try:
        from lerobot_worldepisode_roundtrip import RoundTripUnavailable, run_roundtrip_experiment, unavailable_report

        report = run_roundtrip_experiment()
        committed = committed_lerobot_roundtrip_report()
        if committed:
            report["batch_roundtrip"] = committed.get("batch_roundtrip")
            report["secondary_batch_roundtrips"] = committed.get("secondary_batch_roundtrips", [])
        return report
    except RoundTripUnavailable as exc:
        if os.environ.get("WORLDEPISODE_REQUIRE_ACTIVE_LEROBOT") != "1":
            committed = committed_lerobot_roundtrip_report()
            if committed:
                committed["reused_committed_artifact"] = True
                committed["active_rerun_unavailable"] = str(exc)
                return committed
        return unavailable_report(exc)
    except Exception as exc:  # noqa: BLE001 - report reproducibility blockers without hiding them.
        raise RuntimeError("active LeRobot round-trip failed") from exc


def experiment_lerobot_scene_leakage() -> dict[str, Any]:
    should_run = (
        os.environ.get("WORLDEPISODE_RUN_LEROBOT_LEAKAGE") == "1"
        or os.environ.get("WORLDEPISODE_REQUIRE_LEROBOT_LEAKAGE") == "1"
    )
    if should_run:
        try:
            from lerobot_scene_leakage_experiment import (
                LeakageExperimentUnavailable,
                run_scene_leakage_experiment,
                unavailable_report,
            )

            return run_scene_leakage_experiment()
        except LeakageExperimentUnavailable as exc:
            return unavailable_report(exc)
        except Exception as exc:  # noqa: BLE001 - preservation/training failures should stop required runs.
            raise RuntimeError("active LeRobot task--scene proxy holdout audit failed") from exc
    if SCENE_LEAKAGE_REPORT.exists():
        return load_json(SCENE_LEAKAGE_REPORT)
    return {
        "available": False,
        "pass": False,
        "reason": "No committed leakage report exists yet.",
        "reproduce": "WORLDEPISODE_RUN_LEROBOT_LEAKAGE=1 python3 tools/run_experiments.py",
    }


def experiment_lerobot_policy_gate() -> dict[str, Any]:
    try:
        from lerobot_policy_leakage_gate import build_policy_gate

        return build_policy_gate(
            split_manifest_path=RESULTS_DIR / "lerobot_scene_leakage" / "split_manifest.json",
            leakage_report_path=SCENE_LEAKAGE_REPORT,
            output_dir=RESULTS_DIR / "lerobot_policy_gate",
            policies=["act", "diffusion"],
            device="cuda",
            steps=20000,
            seed=17,
            wandb=False,
            rollout_episodes=20,
            execute=False,
        )
    except Exception as exc:
        report = {
            "available": False,
            "pass": False,
            "reason": str(exc),
            "reproduce": "python3 tools/lerobot_policy_leakage_gate.py",
        }
        write_json(POLICY_GATE_REPORT, report)
        return report


def experiment_lerobot_temporal_policy_baseline() -> dict[str, Any]:
    if os.environ.get("WORLDEPISODE_RUN_TEMPORAL_POLICY_BASELINE") == "1":
        try:
            from lerobot_temporal_policy_baseline import build_report

            return build_report(output_dir=RESULTS_DIR / "lerobot_temporal_policy_baseline")
        except Exception as exc:  # noqa: BLE001 - make required runs fail explicitly below.
            report = {
                "available": False,
                "pass": False,
                "reason": str(exc),
                "reproduce": (
                    "uv run --with pyarrow --with numpy python "
                    "tools/lerobot_temporal_policy_baseline.py --strict"
                ),
            }
            write_json(TEMPORAL_POLICY_REPORT, report)
            return report
    if TEMPORAL_POLICY_REPORT.exists():
        return load_json(TEMPORAL_POLICY_REPORT)
    return {
        "available": False,
        "pass": False,
        "reason": "No committed temporal policy baseline report exists yet.",
        "reproduce": "uv run --with pyarrow --with numpy python tools/lerobot_temporal_policy_baseline.py --strict",
    }


def experiment_benchmark_callout_audit() -> dict[str, Any]:
    try:
        from benchmark_callout_audit import build_callout_audit

        return build_callout_audit(output_dir=RESULTS_DIR / "benchmark_callout_audit", refresh_sources=False)
    except Exception as exc:
        report = {
            "available": False,
            "status": "unavailable",
            "reason": str(exc),
            "reproduce": "python3 tools/benchmark_callout_audit.py",
        }
        write_json(BENCHMARK_CALLOUT_REPORT, report)
        return report


def experiment_benchmark_inflation_gate() -> dict[str, Any]:
    try:
        from benchmark_inflation_gate import build_benchmark_inflation_gate

        return build_benchmark_inflation_gate(output_dir=RESULTS_DIR / "benchmark_inflation_gate")
    except Exception as exc:
        report = {
            "available": False,
            "status": "unavailable",
            "reason": str(exc),
            "reproduce": "python3 tools/benchmark_inflation_gate.py",
        }
        write_json(BENCHMARK_INFLATION_GATE_REPORT, report)
        return report


def experiment_preflight_validator() -> dict[str, Any]:
    from worldepisode import preflight

    output_dir = RESULTS_DIR / "preflight"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "README.md").write_text(
        "# Single-Line Preflight Fixture\n\n"
        "This directory is generated by `python3 tools/run_experiments.py`.\n\n"
        "It contains a small structural LeRobot v3 fixture and a small `.rrd` placeholder used only "
        "to test preflight behavior. The `.parquet` and `.rrd` files here are not training data; "
        "they are minimal sentinels that let the reference preflight detect native containers "
        "without a WorldEpisode sidecar.\n",
        encoding="utf-8",
    )

    native_lerobot = output_dir / "native_lerobot_without_sidecar"
    (native_lerobot / "meta").mkdir(parents=True, exist_ok=True)
    (native_lerobot / "data" / "chunk-000").mkdir(parents=True, exist_ok=True)
    write_json(
        native_lerobot / "meta" / "info.json",
        {
            "codebase_version": "v3.0",
            "features": {
                "timestamp": {"dtype": "float32", "shape": [1], "fps": 30.0},
                "action": {
                    "dtype": "float32",
                    "shape": [6],
                    "names": [
                        "shoulder_pan.pos",
                        "shoulder_lift.pos",
                        "elbow_flex.pos",
                        "wrist_flex.pos",
                        "wrist_roll.pos",
                        "gripper.pos",
                    ],
                    "fps": 30.0,
                },
                "observation.state": {"dtype": "float32", "shape": [6], "fps": 30.0},
            },
        },
    )
    (native_lerobot / "data" / "chunk-000" / "file-000.parquet").write_bytes(b"PAR1")

    rerun_recording = output_dir / "recording_without_sidecar.rrd"
    rerun_recording.write_bytes(b"worldepisode-preflight-placeholder")

    valid_manifest = str(EXAMPLE_PATH.relative_to(ROOT))
    invalid_manifest = str(
        (PILOT_FIXTURE_DIR / "invalid" / "ACTION.002_missing_effective_time.worldepisode.json").relative_to(ROOT)
    )
    native_lerobot_target = str(native_lerobot.relative_to(ROOT))
    rerun_target = str(rerun_recording.relative_to(ROOT))

    cases = [
        {
            "case": "valid_worldepisode_manifest",
            "report": preflight(valid_manifest, fail_on="warning").to_dict(),
            "expected_ok": True,
        },
        {
            "case": "invalid_worldepisode_fixture",
            "report": preflight(invalid_manifest, fail_on="warning").to_dict(),
            "expected_ok": False,
        },
        {
            "case": "native_lerobot_without_sidecar",
            "report": preflight(native_lerobot_target, kind="lerobot", fail_on="warning").to_dict(),
            "expected_ok": False,
        },
        {
            "case": "rerun_without_sidecar",
            "report": preflight(rerun_target, kind="rerun", fail_on="warning").to_dict(),
            "expected_ok": False,
        },
    ]
    failures = [
        case["case"]
        for case in cases
        if bool(case["report"]["ok"]) is not bool(case["expected_ok"])
    ]
    report = {
        "available": True,
        "pass": not failures,
        "profile": "worldepisode-preflight-0.1",
        "cases": cases,
        "failures": failures,
        "commands": [
            "python3 -m pip install -e .",
            "worldepisode preflight <dataset-or-manifest>",
            "python3 - <<'PY'\nfrom worldepisode import preflight_lerobot\npreflight_lerobot('/path/to/lerobot').raise_if_failed()\nPY",
        ],
        "artifact": str(PREFLIGHT_REPORT.relative_to(ROOT)),
    }
    write_json(PREFLIGHT_REPORT, report)
    return report


def experiment_lerobot_conversion_scale() -> dict[str, Any]:
    if CONVERSION_SCALE_REPORT.exists():
        return load_json(CONVERSION_SCALE_REPORT)
    return {
        "schema": "worldepisode_lerobot_conversion_scale_v1",
        "validation": {
            "passed": False,
            "errors": [f"missing report: {CONVERSION_SCALE_REPORT.relative_to(ROOT)}"],
        },
        "aggregate": {},
        "datasets": [],
        "reproduce": (
            "uv run --with pyarrow --with requests "
            "python tools/lerobot_conversion_scale.py --required"
        ),
    }


def experiment_lerobot_multitrajectory_timing() -> dict[str, Any]:
    if MULTITRAJECTORY_TIMING_REPORT.exists():
        return load_json(MULTITRAJECTORY_TIMING_REPORT)
    return {
        "schema": "worldepisode_lerobot_multitrajectory_timing_v1",
        "validation": {
            "passed": False,
            "errors": [f"missing report: {MULTITRAJECTORY_TIMING_REPORT.relative_to(ROOT)}"],
        },
        "calibration": {},
        "evaluation": {},
        "reproduce": (
            "uv run --with pyarrow --with numpy python "
            "tools/lerobot_multitrajectory_timing_audit.py --required"
        ),
    }


def experiment_realtosim_contract_drift() -> dict[str, Any]:
    try:
        from realtosim_contract_drift import build_realtosim_contract_drift

        return build_realtosim_contract_drift(output_dir=RESULTS_DIR / "realtosim_contract_drift")
    except Exception as exc:
        report = {
            "available": False,
            "status": "unavailable",
            "reason": str(exc),
            "reproduce": "python3 tools/realtosim_contract_drift.py",
        }
        write_json(REALTOSIM_DRIFT_REPORT, report)
        return report


def experiment_meta_simulator_contract() -> dict[str, Any]:
    try:
        from meta_simulator_contract import build_meta_simulator_contract

        return build_meta_simulator_contract(output_dir=RESULTS_DIR / "meta_simulator_contract")
    except Exception as exc:
        report = {
            "available": False,
            "status": "unavailable",
            "reason": str(exc),
            "reproduce": "python3 tools/meta_simulator_contract.py",
        }
        write_json(META_SIMULATOR_REPORT, report)
        return report


def experiment_uss_state_drift_pilots() -> dict[str, Any]:
    try:
        from uss_state_drift_pilots import build_uss_state_drift_pilots

        return build_uss_state_drift_pilots(output_dir=RESULTS_DIR / "uss_state_drift_pilots")
    except Exception as exc:
        report = {
            "available": False,
            "status": "unavailable",
            "reason": str(exc),
            "reproduce": "python3 tools/uss_state_drift_pilots.py",
        }
        write_json(USS_STATE_DRIFT_REPORT, report)
        return report


def experiment_replay_adapter_conformance() -> dict[str, Any]:
    try:
        from replay_adapter_conformance import build_replay_adapter_conformance

        return build_replay_adapter_conformance(output_dir=RESULTS_DIR / "replay_adapter_conformance")
    except Exception as exc:
        report = {
            "available": False,
            "status": "unavailable",
            "reason": str(exc),
            "reproduce": "python3 tools/replay_adapter_conformance.py",
        }
        write_json(REPLAY_ADAPTER_CONFORMANCE_REPORT, report)
        return report


def experiment_dataset_scale_audit() -> dict[str, Any]:
    try:
        from dataset_scale_audit import audit_dataset_manifest

        return audit_dataset_manifest(output_dir=RESULTS_DIR / "dataset_scale_audit")
    except Exception as exc:
        report = {
            "available": False,
            "status": "unavailable",
            "reason": str(exc),
            "reproduce": "python3 tools/dataset_scale_audit.py",
        }
        write_json(DATASET_SCALE_AUDIT_REPORT, report)
        return report


def experiment_dataset_scale_performance() -> dict[str, Any]:
    try:
        from dataset_scale_performance import benchmark_scale_performance

        return benchmark_scale_performance(output_dir=RESULTS_DIR / "dataset_scale_performance")
    except Exception as exc:
        report = {
            "available": False,
            "pass": False,
            "status": "unavailable",
            "reason": str(exc),
            "reproduce": "python3 tools/dataset_scale_performance.py",
        }
        write_json(DATASET_SCALE_PERFORMANCE_REPORT, report)
        return report


def experiment_cleanroom_reader() -> dict[str, Any]:
    try:
        from cleanroom_conformance_reader import build_cleanroom_reader_report

        return build_cleanroom_reader_report(output_dir=RESULTS_DIR / "cleanroom_reader")
    except Exception as exc:
        report = {
            "available": False,
            "status": "unavailable",
            "reason": str(exc),
            "reproduce": "python3 tools/cleanroom_conformance_reader.py",
        }
        write_json(CLEANROOM_READER_REPORT, report)
        return report


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


def natural_dataset_slug(repo_id: str, revision: str) -> str:
    base = f"{repo_id}__{revision[:12]}"
    slug = re.sub(r"[^A-Za-z0-9]+", "_", base).strip("_").lower()
    return slug or "dataset"


def count_case_requirements(cases: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in cases:
        for requirement in case.get("requirement_ids", []):
            counts[requirement] = counts.get(requirement, 0) + 1
    return dict(sorted(counts.items()))


def natural_evidence_status(evidence_type: str) -> tuple[str, str, list[str]]:
    if evidence_type == "active_lerobot_conversion_reports":
        return (
            "active_worldepisode_conversion_reports",
            "sampled episodes were converted through the active LeRobot-to-WorldEpisode pipeline",
            [
                "mirror more episodes if claiming full-dataset coverage",
                "request maintainer review of representative diagnostics",
            ],
        )
    if evidence_type == "active_lerobot_task_scene_proxy_audit":
        return (
            "active_task_scene_proxy_split_audit",
            "task--scene proxy split behavior was measured from the committed LeRobot audit artifact",
            [
                "run policy evaluations beyond the offline probes before making rollout claims",
                "obtain physical scene/source IDs while preserving task support",
                "request maintainer review of the proxy-lineage grouping",
            ],
        )
    if evidence_type == "source_level_public_metadata_audit":
        return (
            "source_level_public_metadata_only",
            "public materials were audited, but no benchmark-specific WorldEpisode conversion is committed",
            [
                "convert a pinned subset into a WorldEpisode manifest",
                "run false-positive review against source maintainers or dataset experts",
                "do not claim score inflation without a published-protocol rerun",
            ],
        )
    return (
        "unknown_evidence_tier",
        "evidence tier is not recognized by the natural failure diagnostics generator",
        ["classify this dataset evidence tier before using it in paper claims"],
    )


def write_natural_failure_dataset_diagnostics(manifest: dict[str, Any]) -> dict[str, Any]:
    cases_by_dataset: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for case in manifest.get("cases", []):
        key = (case["repo_id"], case["revision"])
        cases_by_dataset.setdefault(key, []).append(case)

    dataset_reports: list[dict[str, Any]] = []
    for dataset in sorted(manifest.get("datasets", []), key=lambda item: item["repo_id"]):
        repo_id = dataset["repo_id"]
        revision = dataset["revision"]
        key = (repo_id, revision)
        dataset_cases = sorted(cases_by_dataset.get(key, []), key=lambda item: item["case_id"])
        conversion_status, evidence_strength, next_steps = natural_evidence_status(dataset.get("evidence_type", ""))
        slug = natural_dataset_slug(repo_id, revision)
        report_path = NATURAL_FAILURE_DATASET_DIR / f"{slug}.json"
        relative_report_path = str(report_path.relative_to(ROOT))
        report = {
            "schema": "worldepisode_natural_failure_dataset_report_v1",
            "repo_id": repo_id,
            "revision": revision,
            "source_profile": dataset.get("source_profile"),
            "evidence_type": dataset.get("evidence_type"),
            "conversion_status": conversion_status,
            "evidence_strength": evidence_strength,
            "case_count": len(dataset_cases),
            "requirement_counts": count_case_requirements(dataset_cases),
            "source_absent_fields": dataset.get("source_absent_fields", {}),
            "observed_episode_indices": dataset.get("episode_indices", []),
            "observed_episode_count": len(dataset.get("episode_indices", [])),
            "action_rows": dataset.get("action_rows"),
            "state_rows": dataset.get("state_rows"),
            "evidence_files": dataset.get("evidence_files", []),
            "warnings": dataset.get("warnings", []),
            "cases": dataset_cases,
            "maintainer_feedback": {
                "status": "not_requested",
                "satisfied": False,
            },
            "claim_boundary": (
                "Dataset-specific diagnostic report, not maintainer-confirmed prevalence. "
                "Source-level-only reports are evidence of missing public controls, not measured "
                "benchmark score inflation."
            ),
            "next_steps": next_steps,
        }
        write_json(report_path, report)
        dataset_reports.append(
            {
                "repo_id": repo_id,
                "revision": revision,
                "report": relative_report_path,
                "evidence_type": dataset.get("evidence_type"),
                "conversion_status": conversion_status,
                "case_count": len(dataset_cases),
                "requirement_counts": report["requirement_counts"],
            }
        )

    active_report_count = sum(
        1
        for report in dataset_reports
        if report["conversion_status"] in {"active_worldepisode_conversion_reports", "active_lineage_split_audit"}
    )
    source_level_only_count = sum(
        1 for report in dataset_reports if report["conversion_status"] == "source_level_public_metadata_only"
    )
    total_cases = sum(report["case_count"] for report in dataset_reports)
    diagnostics_ready = (
        len(dataset_reports) == manifest.get("dataset_count")
        and total_cases == manifest.get("case_count")
        and len(dataset_reports) > 0
    )
    index = {
        "schema": "worldepisode_natural_failure_dataset_diagnostics_v1",
        "available": diagnostics_ready,
        "artifact": str(NATURAL_FAILURE_DIAGNOSTICS.relative_to(ROOT)),
        "generated_from": manifest.get("artifact"),
        "dataset_report_count": len(dataset_reports),
        "case_count": total_cases,
        "active_dataset_report_count": active_report_count,
        "source_level_only_report_count": source_level_only_count,
        "dataset_specific_diagnostics_ready": diagnostics_ready,
        "maintainer_feedback_satisfied": manifest.get("full_gate", {}).get("maintainer_feedback_satisfied") is True,
        "full_gate_satisfied": False,
        "claim_boundary": (
            "All five datasets have dataset-specific diagnostic reports. This improves auditability, "
            "but it is not a prevalence estimate and it is not maintainer-confirmed bug evidence."
        ),
        "remaining_for_prevalence_claim": [
            "record maintainer agreement, disagreement, or no-response evidence",
            "convert source-level DROID and BridgeData V2 gaps into pinned WorldEpisode manifests",
            "run false-positive review before using the corpus as prevalence evidence",
        ],
        "reports": dataset_reports,
    }
    write_json(NATURAL_FAILURE_DIAGNOSTICS, index)

    rows = "\n".join(
        "| {repo_id} | {conversion_status} | {case_count} | `{report}` |".format(**report)
        for report in dataset_reports
    )
    readme = f"""# Natural Failure Corpus Dataset Diagnostics

Status: `dataset_specific_diagnostics_ready`.

These reports materialize the pilot natural-source corpus by dataset. They are intended for
reviewer audit and maintainer follow-up. They are not prevalence estimates, maintainer-confirmed
bug records, or benchmark score-inflation evidence.

| Dataset | Evidence Status | Cases | Report |
| --- | --- | ---: | --- |
{rows}

Summary:

- Dataset reports: {index["dataset_report_count"]}
- Cases covered: {index["case_count"]}
- Active LeRobot reports: {index["active_dataset_report_count"]}
- Source-level-only reports: {index["source_level_only_report_count"]}
- Maintainer feedback satisfied: {index["maintainer_feedback_satisfied"]}

Remaining for stronger claims:

- Record maintainer agreement, disagreement, or no-response evidence.
- Convert source-level DROID and BridgeData V2 gaps into pinned WorldEpisode manifests.
- Run false-positive review before using the corpus as prevalence evidence.
"""
    write_text(NATURAL_FAILURE_DIR / "README.md", readme)
    return index


def experiment_natural_failure_corpus() -> dict[str, Any]:
    """Aggregate naturally observed source omissions from committed public-dataset artifacts.

    These cases are not synthetic mutations of a valid WorldEpisode package. They are source-absent
    semantics, split-lineage failures, and source-level public metadata gaps observed while auditing
    public robot-learning datasets.
    """

    field_requirements = {
        "camera extrinsics": ["FRAME.001", "FRAME.002"],
        "robot/world calibration transform": ["FRAME.001", "FRAME.002"],
        "action units": ["ACTION.001"],
        "controller latency model": ["ACTION.002", "ACTION.004"],
    }
    datasets: dict[tuple[str, str], dict[str, Any]] = {}

    conversion_paths = sorted(
        [
            *RESULTS_DIR.glob("lerobot_worldepisode_roundtrip/batch/episode_*/conversion_report.json"),
            *RESULTS_DIR.glob("lerobot_worldepisode_roundtrip_pusht/batch/episode_*/conversion_report.json"),
        ]
    )
    for path in conversion_paths:
        report = load_json(path)
        repo_id = report["source_repo_id"]
        revision = report["source_revision"]
        key = (repo_id, revision)
        dataset = datasets.setdefault(
            key,
            {
                "repo_id": repo_id,
                "revision": revision,
                "source_profile": report.get("source_profile"),
                "evidence_type": "active_lerobot_conversion_reports",
                "episode_indices": set(),
                "action_rows": 0,
                "state_rows": 0,
                "source_absent_fields": {},
                "warnings": set(),
                "evidence_files": [],
            },
        )
        dataset["episode_indices"].add(report["episode_index"])
        dataset["action_rows"] += report.get("metrics", {}).get("action_rows", 0)
        dataset["state_rows"] += report.get("metrics", {}).get("state_rows", 0)
        dataset["evidence_files"].append(str(path.relative_to(ROOT)))
        dataset["warnings"].update(report.get("warnings", []))
        for field in report.get("source_absent", []):
            dataset["source_absent_fields"].setdefault(field, set()).update(field_requirements.get(field, []))

    cases = []
    for dataset in datasets.values():
        for field, requirements in sorted(dataset["source_absent_fields"].items()):
            cases.append(
                {
                    "case_id": f"{dataset['repo_id'].replace('/', '__')}::{field.replace(' ', '_')}",
                    "repo_id": dataset["repo_id"],
                    "revision": dataset["revision"],
                    "observation": f"Native LeRobot source is missing {field}.",
                    "requirement_ids": sorted(requirements),
                    "evidence_type": "natural_source_absence",
                    "observed_episodes": len(dataset["episode_indices"]),
                    "evidence_files": dataset["evidence_files"],
                    "diagnostic_status": "source_absent_not_invented_by_converter",
                    "maintainer_feedback": "not_requested",
                }
            )

    leakage_path = SCENE_LEAKAGE_REPORT
    if leakage_path.exists():
        leakage = load_json(leakage_path)
        if leakage.get("available"):
            repo_id = leakage["repo_id"]
            revision = leakage["revision"]
            key = (repo_id, revision)
            datasets[key] = {
                "repo_id": repo_id,
                "revision": revision,
                "source_profile": "lerobot-v3",
                "evidence_type": "active_lerobot_task_scene_proxy_audit",
                "episode_indices": set(),
                "action_rows": None,
                "state_rows": None,
                "source_absent_fields": {},
                "warnings": set(),
                "evidence_files": [str(leakage_path.relative_to(ROOT))],
                "teleoperated_reference_episodes": leakage.get("dataset", {}).get("teleoperated_reference_episodes"),
            }
            random_split = leakage["splits"]["random_episode"]
            cases.append(
                {
                    "case_id": f"{repo_id.replace('/', '__')}::random_episode_proxy_lineage_overlap",
                    "repo_id": repo_id,
                    "revision": revision,
                    "observation": (
                        "A standard random episode split overlaps all tested task--scene proxy groups "
                        f"(proxy overlap rate {random_split['leakage_rate']:.3f})."
                    ),
                    "requirement_ids": ["SPLIT.001"],
                    "evidence_type": "natural_split_lineage_leakage",
                    "observed_episodes": leakage.get("dataset", {}).get("teleoperated_reference_episodes"),
                    "evidence_files": [str(leakage_path.relative_to(ROOT))],
                    "diagnostic_status": "lineage_disjoint_split_required_for_valid_evaluation",
                    "maintainer_feedback": "not_requested",
                }
            )

    benchmark_path = BENCHMARK_CALLOUT_REPORT
    if benchmark_path.exists():
        benchmark_report = load_json(benchmark_path)
        selected_benchmarks = {"droid", "bridgedata_v2"}
        for benchmark in benchmark_report.get("benchmarks", []):
            if benchmark.get("benchmark_id") not in selected_benchmarks:
                continue
            repo_id = f"benchmark/{benchmark['benchmark_id']}"
            revision = f"source-level-audit-{benchmark_report.get('audit_date', 'unknown')}"
            key = (repo_id, revision)
            evidence_file = str(benchmark_path.relative_to(ROOT))
            datasets[key] = {
                "repo_id": repo_id,
                "revision": revision,
                "source_profile": benchmark.get("domain"),
                "evidence_type": "source_level_public_metadata_audit",
                "episode_indices": set(),
                "action_rows": None,
                "state_rows": None,
                "source_absent_fields": {},
                "warnings": set(),
                "evidence_files": [evidence_file],
                "source_url": benchmark.get("source_url"),
                "code_or_data_url": benchmark.get("code_or_data_url"),
                "scale_public_claim": benchmark.get("scale_public_claim"),
                "selected_from": "famous_benchmark_callout_audit",
            }
            for finding in benchmark.get("findings", []):
                if finding.get("severity") != "high":
                    continue
                cases.append(
                    {
                        "case_id": f"{repo_id.replace('/', '__')}::{finding['check_id']}",
                        "repo_id": repo_id,
                        "revision": revision,
                        "observation": (
                            f"{benchmark['name']} public materials: {finding['finding']}."
                        ),
                        "requirement_ids": finding.get("requirement_ids", []),
                        "evidence_type": "source_level_public_metadata_gap",
                        "observed_episodes": benchmark.get("scale_public_claim"),
                        "evidence_files": [evidence_file],
                        "diagnostic_status": "requires_dataset_specific_worldepisode_audit",
                        "maintainer_feedback": "not_requested",
                        "claim_boundary": (
                            "Source-level public evidence gap, not a maintainer-confirmed bug and "
                            "not a measured score-inflation claim."
                        ),
                    }
                )

    normalized_datasets = []
    for dataset in datasets.values():
        normalized = dict(dataset)
        normalized["episode_indices"] = sorted(normalized.pop("episode_indices", []))
        normalized["warnings"] = sorted(normalized.pop("warnings", []))
        normalized["source_absent_fields"] = {
            field: sorted(requirements)
            for field, requirements in sorted(normalized["source_absent_fields"].items())
        }
        normalized_datasets.append(normalized)

    requirement_counts: dict[str, int] = {}
    for case in cases:
        for requirement in case["requirement_ids"]:
            requirement_counts[requirement] = requirement_counts.get(requirement, 0) + 1

    dataset_count_gate_satisfied = len(normalized_datasets) >= 5
    maintainer_feedback_satisfied = False
    manifest = {
        "available": bool(cases),
        "scope": (
            "pilot natural-source corpus from committed public LeRobot artifacts plus selected "
            "source-level public benchmark metadata audits"
        ),
        "artifact": str((NATURAL_FAILURE_DIR / "manifest.json").relative_to(ROOT)),
        "dataset_count": len(normalized_datasets),
        "case_count": len(cases),
        "requirement_counts": dict(sorted(requirement_counts.items())),
        "datasets": sorted(normalized_datasets, key=lambda item: item["repo_id"]),
        "cases": sorted(cases, key=lambda item: item["case_id"]),
        "evidence_tiers": {
            "active_lerobot_conversion_reports": sum(
                1 for dataset in normalized_datasets if dataset.get("evidence_type") == "active_lerobot_conversion_reports"
            ),
            "active_lerobot_task_scene_proxy_audit": sum(
                1
                for dataset in normalized_datasets
                if dataset.get("evidence_type") == "active_lerobot_task_scene_proxy_audit"
            ),
            "source_level_public_metadata_audit": sum(
                1 for dataset in normalized_datasets if dataset.get("evidence_type") == "source_level_public_metadata_audit"
            ),
        },
        "full_gate": {
            "required_public_datasets": 5,
            "requires_maintainer_feedback": True,
            "dataset_count_gate_satisfied": dataset_count_gate_satisfied,
            "maintainer_feedback_satisfied": maintainer_feedback_satisfied,
            "satisfied": dataset_count_gate_satisfied and maintainer_feedback_satisfied,
            "remaining": [
                "request or record maintainer agreement/disagreement for representative diagnostics",
                "convert source-level metadata-gap cases into dataset-specific manifests where stronger claims are needed",
            ],
        },
    }
    NATURAL_FAILURE_DIR.mkdir(parents=True, exist_ok=True)
    write_json(NATURAL_FAILURE_DIR / "manifest.json", manifest)
    diagnostics = write_natural_failure_dataset_diagnostics(manifest)
    return {
        "available": manifest["available"],
        "artifact": manifest["artifact"],
        "dataset_diagnostics_artifact": diagnostics["artifact"],
        "dataset_count": manifest["dataset_count"],
        "case_count": manifest["case_count"],
        "requirement_counts": manifest["requirement_counts"],
        "evidence_tiers": manifest["evidence_tiers"],
        "dataset_report_count": diagnostics["dataset_report_count"],
        "active_dataset_report_count": diagnostics["active_dataset_report_count"],
        "source_level_only_report_count": diagnostics["source_level_only_report_count"],
        "dataset_specific_diagnostics_ready": diagnostics["dataset_specific_diagnostics_ready"],
        "dataset_count_gate_satisfied": manifest["full_gate"]["dataset_count_gate_satisfied"],
        "maintainer_feedback_satisfied": manifest["full_gate"]["maintainer_feedback_satisfied"],
        "full_gate_satisfied": manifest["full_gate"]["satisfied"],
    }


def experiment_replay() -> dict[str, Any]:
    should_run = (
        os.environ.get("WORLDEPISODE_RUN_LEROBOT_REPLAY") == "1"
        or os.environ.get("WORLDEPISODE_REQUIRE_LEROBOT_REPLAY") == "1"
    )
    if should_run:
        try:
            from lerobot_control_replay_experiment import (
                ControlReplayUnavailable,
                run_control_replay_experiment,
                unavailable_report,
            )

            return run_control_replay_experiment()
        except ControlReplayUnavailable as exc:
            return unavailable_report(exc)
        except Exception as exc:  # noqa: BLE001 - timing/replay failures should stop required runs.
            raise RuntimeError("active LeRobot control replay experiment failed") from exc
    if CONTROL_REPLAY_REPORT.exists():
        return load_json(CONTROL_REPLAY_REPORT)
    return {
        "available": False,
        "pass": False,
        "reason": "No committed LeRobot control replay report exists yet.",
        "reproduce": "WORLDEPISODE_RUN_LEROBOT_REPLAY=1 python3 tools/run_experiments.py",
    }


def experiment_contact_rich_replay() -> dict[str, Any]:
    if not CONTACT_RICH_REPLAY_REPORT.exists():
        return {
            "status": "unavailable",
            "analysis": {"acceptance": {"pass": False}},
            "reason": "No committed contact-rich cross-simulator replay report exists.",
            "reproduce": (
                "UV_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu "
                "uv run --isolated --python 3.11 --index-strategy unsafe-best-match "
                "--with 'torch==2.8.0+cpu' --with 'numpy==2.4.6' "
                "--with 'mujoco==3.3.7' --with 'genesis-world==1.2.2' "
                "python tools/contact_rich_cross_sim_replay.py --required"
            ),
        }
    from contact_rich_cross_sim_replay import check_committed_report

    check_committed_report(
        CONTACT_RICH_REPLAY_PROTOCOL,
        CONTACT_RICH_REPLAY_REPORT,
        required=True,
    )
    return load_json(CONTACT_RICH_REPLAY_REPORT)


def experiment_lerobot_public_sample() -> dict[str, Any]:
    # First frame of episode 0 from lerobot/svla_so101_pickplace, mirrored in a
    # committed offline fixture to avoid network-dependent evaluation.
    joint_deg = [1.9560878, -98.74372, 98.92424, 74.81983, -51.45299, 1.40939]
    joint_rad = [math.radians(value) for value in joint_deg]
    # FK position from the committed SO-101 offline fixture.
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
    contact_replay = results["contact_rich_replay"]
    splits = results["rq5_split_leakage"]
    robust = results["rq4_counterfactual_robustness"]
    independent = results["independent_fixture_check"]
    natural = results["natural_failure_corpus"]
    public_sample = results["lerobot_public_sample"]
    episode_set = results["lerobot_style_episode_set"]
    active_lerobot = results["lerobot_active_roundtrip"]
    conversion_scale = results["lerobot_conversion_scale"]
    multitrajectory_timing = results["lerobot_multitrajectory_timing"]
    scene_leakage = results["lerobot_scene_leakage"]
    policy_gate = results["lerobot_policy_gate"]
    temporal_policy = results["lerobot_temporal_policy_baseline"]
    benchmark_callout = results["benchmark_callout_audit"]
    benchmark_inflation = results["benchmark_inflation_gate"]
    preflight_result = results["preflight_validator"]
    realtosim_drift = results["realtosim_contract_drift"]
    meta_sim = results["meta_simulator_contract"]
    uss_pilots = results["uss_state_drift_pilots"]
    replay_adapter = results["replay_adapter_conformance"]
    dataset_scale = results["dataset_scale_audit"]
    dataset_scale_perf = results["dataset_scale_performance"]
    cleanroom_reader = results["cleanroom_reader"]
    projection_profile = results["rq1_binding_retention"]["projection_profile"]
    natural_boundary = (
        "Five-dataset count is met through active LeRobot artifacts plus source-level public "
        "benchmark metadata. Dataset-specific diagnostic reports cover every case, but source-level "
        "benchmark cases still need pinned conversions and maintainer review before prevalence claims."
        if natural.get("dataset_count_gate_satisfied")
        else "Natural corpus is still below the five-dataset gate and has no maintainer feedback yet."
    )
    if active_lerobot.get("available"):
        active_metrics = active_lerobot["metrics"]
        batch = active_lerobot.get("batch_roundtrip")
        reuse_line = ""
        if active_lerobot.get("reused_committed_artifact"):
            reuse_line = (
                "- Artifact source: committed pinned active-run report reused by the default deterministic suite.\n"
            )
        batch_lines = ""
        if batch and batch.get("available"):
            batch_lines = (
                f"- Batch report: {batch['episode_count']} episodes, "
                f"{batch['total_action_rows']} action rows, "
                f"max action/state/timestamp/video errors = "
                f"{batch['max_errors']['max_abs_action_error']:.1f}/"
                f"{batch['max_errors']['max_abs_state_error']:.1f}/"
                f"{batch['max_errors']['max_abs_timestamp_error']:.1f}/"
                f"{batch['max_errors']['max_abs_video_timestamp_error']:.1f}\n"
                f"- Batch source-index errors: frame/episode/global/task = "
                f"{batch['max_errors']['max_abs_frame_index_error']:.1f}/"
                f"{batch['max_errors']['max_abs_episode_index_error']:.1f}/"
                f"{batch['max_errors']['max_abs_index_error']:.1f}/"
                f"{batch['max_errors']['max_abs_task_index_error']:.1f}\n"
            )
        secondary_lines = ""
        for secondary in active_lerobot.get("secondary_batch_roundtrips", []):
            if not secondary.get("available"):
                continue
            secondary_lines += (
                f"- Secondary batch: `{secondary['repo_id']}@{secondary['revision']}`; "
                f"{secondary['episode_count']} episodes, {secondary['total_action_rows']} action rows, "
                f"max source-native errors all zero: {secondary['pass']}\n"
            )
        active_section = f"""## Active LeRobot -> WorldEpisode -> LeRobot Round-Trip

- Source: `{active_lerobot["repo_id"]}@{active_lerobot["revision"]}`
- Episode: {active_lerobot["episode_index"]}
- Exported LeRobot v3 package: `{active_lerobot["artifacts"]["exported_lerobot_v3"]}`
{reuse_line}- Action tensor rows x width: {active_metrics["action_rows"]} x {active_metrics["action_width"]}
- Video streams with timestamp ranges: {active_metrics["video_streams"]}
- Physical frame records preserved through sidecar: {active_metrics["physical_frames_preserved"]}
- Max absolute action error: {active_metrics["max_abs_action_error"]:.1f}
- Max absolute state error: {active_metrics["max_abs_state_error"]:.1f}
- Max absolute timestamp error: {active_metrics["max_abs_timestamp_error"]:.1f}
- Max absolute video timestamp error: {active_metrics["max_abs_video_timestamp_error"]:.1f}
- Explicitly tracked source-absent fields: {active_metrics["source_absent_fields_tracked"]}
- Discarded fields: {len(active_metrics["discarded_fields"])}
{batch_lines}
{secondary_lines}
"""
    else:
        active_section = f"""## Active LeRobot -> WorldEpisode -> LeRobot Round-Trip

- Available: false
- Reason: {active_lerobot.get("reason", "unknown")}
- Reproduce: `{active_lerobot.get("reproduce", "python3 tools/lerobot_worldepisode_roundtrip.py --required")}`
"""
    conversion_scale_aggregate = conversion_scale.get("aggregate", {})
    if conversion_scale.get("validation", {}).get("passed") is True:
        conversion_scale_section = f"""## Complete-Shard LeRobot Conversion Scale

- Datasets: {conversion_scale_aggregate["dataset_count"]}
- Multi-camera datasets: {conversion_scale_aggregate["multi_camera_dataset_count"]}
- Episodes: {conversion_scale_aggregate["episode_count"]}
- Paired action/state rows: {conversion_scale_aggregate["action_row_count"]}
- Source input bytes: {conversion_scale_aggregate["source_input_bytes"]}
- Temporary output bytes: {conversion_scale_aggregate["temporary_output_bytes"]}
- Orchestrator wall time: {conversion_scale_aggregate["orchestrator_wall_time_seconds"]:.3f} s
- Maximum worker resident memory: {conversion_scale_aggregate["maximum_worker_rss_bytes"]} bytes
- Unique source-absent semantic fields: {conversion_scale_aggregate["semantic_loss_field_count"]}
- Maximum numerical error: {conversion_scale_aggregate["maximum_numerical_error"]:.1f}
- Boundary: {conversion_scale["claim_boundary"]}
"""
    else:
        conversion_scale_section = f"""## Complete-Shard LeRobot Conversion Scale

- Available: false
- Reproduce: `{conversion_scale.get("reproduce", "uv run --with pyarrow --with requests python tools/lerobot_conversion_scale.py --required")}`
"""
    if multitrajectory_timing.get("validation", {}).get("passed") is True:
        timing_calibration = multitrajectory_timing["calibration"]
        timing_evaluation = multitrajectory_timing["evaluation"]
        timing_improvement = timing_evaluation["paired_episode_improvement"]
        timing_section = f"""## Multi-Trajectory SO-101 Telemetry-Lag Audit

- Calibration episodes: {timing_calibration["episode_count"]}
- Held-out episodes: {timing_evaluation["episode_count"]}
- Held-out tasks: {timing_evaluation["task_count"]}
- Frozen lag: {timing_calibration["selected_delay_frames"]} frames
- Held-out zero-delay pooled RMSE: {timing_evaluation["zero_delay"]["pooled_joint_rmse"]:.6f} source position units
- Held-out frozen-delay pooled RMSE: {timing_evaluation["frozen_frame_delay"]["pooled_joint_rmse"]:.6f} source position units
- Mean paired episode improvement: {timing_improvement["estimate"]:.6f}
- Paired episode 95% CI: [{timing_improvement["ci_low"]:.6f}, {timing_improvement["ci_high"]:.6f}]
- Improved held-out episodes: {timing_improvement["improved_episode_count"]}/{timing_evaluation["episode_count"]}
- Boundary: {multitrajectory_timing["claim_boundary"]}
"""
    else:
        timing_section = f"""## Multi-Trajectory SO-101 Telemetry-Lag Audit

- Available: false
- Reproduce: `{multitrajectory_timing.get("reproduce", "uv run --with pyarrow --with numpy python tools/lerobot_multitrajectory_timing_audit.py --required")}`
"""
    if scene_leakage.get("available"):
        random_split = scene_leakage["splits"]["random_episode"]
        disjoint_split = scene_leakage["splits"]["scene_disjoint"]
        scene_summary = scene_leakage["summary"]
        scene_section = f"""## Active LeRobot Task--Scene Proxy Holdout Audit

- Source: `{scene_leakage["repo_id"]}@{scene_leakage["revision"]}`
- Teleoperated reference episodes: {scene_leakage["dataset"]["teleoperated_reference_episodes"]}
- Task--scene proxy groups: {scene_leakage["lineage_count"]}
- Held-out task groups: {", ".join(scene_leakage["heldout_scene_tasks"])}
- BC policy: {scene_leakage["bc_policy_family"]}
- BC optimization seeds: {random_split["bc"]["policy"]["seed_count"]}

| Split | Proxy Overlap Rate | Test Episodes | Episode nRMSE Mean | Secondary Thresholded Rate |
|---|---:|---:|---:|---:|
| Random episode | {random_split["leakage_rate"]:.3f} | {random_split["test_count"]} | {random_split["bc"]["episode_normalized_rmse_mean"]:.3f} | {random_split["bc"]["offline_bc_success_rate"]:.3f} |
| Task--scene proxy holdout (`scene_disjoint` key) | {disjoint_split["leakage_rate"]:.3f} | {disjoint_split["test_count"]} | {disjoint_split["bc"]["episode_normalized_rmse_mean"]:.3f} | {disjoint_split["bc"]["offline_bc_success_rate"]:.3f} |

- Primary holdout/random episode nRMSE ratio: {scene_summary["episode_nrmse_ratio_scene_over_random"]:.2f}x
- Secondary thresholded imitation-rate drop: {scene_summary["success_rate_drop"]:.3f}
- Boundary: task identity is part of the proxy key, so this holdout does not isolate scene leakage from task shift.
"""
    else:
        scene_section = f"""## Active LeRobot Task--Scene Proxy Holdout Audit

- Available: false
- Reason: {scene_leakage.get("reason", "unknown")}
- Reproduce: `{scene_leakage.get("reproduce", "python3 tools/lerobot_scene_leakage_experiment.py --required")}`
"""
    if replay.get("available"):
        alignment = replay["alignment"]
        mujoco = replay["simulators"]["mujoco"]
        genesis = replay["simulators"].get("genesis", {})
        isaac = replay["simulators"]["isaac"]
        genesis_lines = ""
        if genesis.get("tested"):
            genesis_lines = (
                f"- Genesis same-trace replay naive RMSE: "
                f"{genesis['naive_command_time']['joint_rmse_deg']:.3f} deg\n"
                f"- Genesis same-trace replay timestamp-aware RMSE: "
                f"{genesis['timestamp_aware']['joint_rmse_deg']:.3f} deg\n"
                f"- Genesis same-trace replay improvement: "
                f"{genesis['rmse_improvement_over_naive']:.2f}x\n"
            )
        replay_section = f"""## RQ3: LeRobot Control-Loop Replay

- Source trace: `{replay["source_trace"]}`
- Samples x joints: {replay["sample_count"]} x {replay["joint_count"]}
- Sample rate: {replay["sample_rate_hz"]:.2f} Hz
- Inferred effective delay: {alignment["inferred_effective_delay_frames"]} frames ({1000 * alignment["inferred_effective_delay_s"]:.1f} ms)
- Validation naive command-time RMSE: {alignment["validation_naive_rmse_deg"]:.3f} deg
- Validation timestamp-aware RMSE: {alignment["validation_timestamp_aware_rmse_deg"]:.3f} deg
- Validation alignment improvement: {alignment["validation_improvement_over_naive"]:.2f}x
- MuJoCo naive replay RMSE: {mujoco["naive_command_time"]["joint_rmse_deg"]:.3f} deg
- MuJoCo timestamp-aware replay RMSE: {mujoco["timestamp_aware"]["joint_rmse_deg"]:.3f} deg
- MuJoCo replay improvement: {mujoco["rmse_improvement_over_naive"]:.2f}x
{genesis_lines.rstrip()}
- Isaac adapter ready: {isaac["ready"]}; tested: {isaac["tested"]}
"""
    else:
        replay_section = f"""## RQ3: LeRobot Control-Loop Replay

- Available: false
- Reason: {replay.get("reason", "unknown")}
- Reproduce: `{replay.get("reproduce", "python3 tools/lerobot_control_replay_experiment.py --required")}`
"""
    contact_aggregate = contact_replay.get("analysis", {}).get("aggregate", {})
    if contact_replay.get("analysis", {}).get("acceptance", {}).get("pass"):
        contact_section = f"""## RQ3: Contact-Rich Cross-Simulator Replay

- Tasks / initial-state scenarios: {len(contact_replay["analysis"]["tasks"])} / {contact_aggregate["scenario_count"]}
- Object trajectory position RMSE: {1000 * contact_aggregate["trajectory_position_rmse_m"]["estimate"]:.3f} mm
- Contact precision / recall / F1: {contact_aggregate["contact_precision"]["estimate"]:.3f} / {contact_aggregate["contact_recall"]["estimate"]:.3f} / {contact_aggregate["contact_f1"]["estimate"]:.3f}
- Grasp-state agreement: {contact_aggregate["grasp_state_agreement"]["estimate"]:.3f}
- Final position / orientation error: {1000 * contact_aggregate["final_position_error_m"]["estimate"]:.3f} mm / {contact_aggregate["final_orientation_error_deg"]["estimate"]:.3f} deg
- Task-outcome agreement: {contact_aggregate["task_outcome_agreement"]["estimate"]:.3f}
- Boundary: {contact_replay["claim_boundary"]}
"""
    else:
        contact_section = f"""## RQ3: Contact-Rich Cross-Simulator Replay

- Available: false
- Reason: {contact_replay.get("reason", "unknown")}
- Reproduce: `{contact_replay.get("reproduce", "python3 tools/contact_rich_cross_sim_replay.py --required")}`
"""
    evidence_boundaries = f"""## Evidence Boundaries

| Claim Area | Current Evidence | Boundary |
|---|---|---|
| Leakage | Public ArmnetBench LeRobot audit with 400 teleoperated reference episodes, an executable Torch BC probe, a measured temporal ridge state/action baseline, and an ACT/Diffusion gate harness with compact physical state/action split packages. | ACT/Diffusion jobs and high-fidelity or physical rollouts are prepared but not executed; source videos must be mirrored before vision-policy claims. |
| Conversion | Complete pinned source Parquet shards from {conversion_scale_aggregate.get("dataset_count", 0)} public LeRobotDataset v3 datasets, covering {conversion_scale_aggregate.get("episode_count", 0)} episodes and {conversion_scale_aggregate.get("action_row_count", 0)} paired action/state rows with exact tensor, index, and timestamp equality. | Selected shards rather than full corpora; source video payloads are not converted. |
| Replay timing | A frozen action/state telemetry lag calibrated on {multitrajectory_timing.get("calibration", {}).get("episode_count", 0)} SO-101 trajectories and evaluated on {multitrajectory_timing.get("evaluation", {}).get("episode_count", 0)} source-episode-disjoint trajectories, plus tested same-trace MuJoCo and Genesis position-servo replay. | The multi-trajectory source has no motor-effective timestamps and covers one robot/controller configuration. |
| Contact-rich replay | Two preregistered primitive manipulation tasks over {contact_aggregate.get("scenario_count", 0)} initial-state scenarios in MuJoCo and Genesis, retaining object poses, contacts, grasp states, outcomes, and scenario-bootstrap intervals. | Scripted kinematic actors rather than an articulated robot; neither simulator is hardware ground truth, Isaac/SAPIEN remain untested, and equal physics is not claimed. |
| Replay adapter conformance | Dependency-free reference scheduler validates delay, zero-order hold, missing-command, and asynchronous queue semantics. | Scheduler conformance only; not a second physics simulator. |
| Validation | Fourteen injected requirement faults, two independent hand-authored fixtures, and a pilot natural-source corpus over {natural["dataset_count"]} public datasets. | {natural_boundary} |
| Preflight adoption | Installable `worldepisode` package, CLI entry point, Python one-liners, and four committed preflight cases. | Package metadata is ready for local/pip installation, but no PyPI release or upstream LeRobot/Rerun PR is merged yet. |
| Dataset scale | Executable dataset manifest audit plus a generated 32,768-shard catalog benchmark describing 1,073,741,824 episodes. | Catalog-side benchmark only; no billion episode rows, payload bytes, network storage, or multi-institution deployment are measured. |
| Clean-room reader | A separate reader script that does not import the `worldepisode` package parses the public schema and catches expected requirements across pilot and independent fixtures. | Internal clean-room artifact only; not an external implementation or adoption claim. |
| Real-to-sim drift | Controlled action-contract and representation-role ablations: drifted contracts succeed in sim and fail under deployment proxies; WorldEpisode contracts pass. | Deterministic proxy, not a physical hardware rollout or a RoboSnap/DROID-Sim rerun. |
| Meta-simulator contract | Runtime-neutral adapter matrix over MuJoCo, Isaac Sim, Genesis, and SAPIEN with three compliance layers and same-trace MuJoCo/Genesis replay evidence. | MuJoCo and Genesis are tested for the minimal LeRobot replay profile; external collaboration is Not defined yet, Isaac and SAPIEN are not replay-tested here, and equal physics is not claimed. |
| Generalization beyond robotics | Deterministic game-engine collision-patch and autonomous-driving clock-domain pilots using the same state-invariant vocabulary. | Not measured Epic/Unity/Waymo data, not a production game or AV benchmark result. |
| Binding retention | Versioned `{projection_profile["profile_id"]}` semantic projection checked by executable artifacts. | Pilot projection; not a universal score of each storage format. |
| Famous benchmark call-out | Source-level audit over Open X-Embodiment, DROID, BridgeData V2, LIBERO, and CALVIN, a targeted DROID subset rerun tool, and an executable inflation-proof gate. | One bounded DROID subset rerun executes, but it is not inflation-proof; `benchmark_inflation_gate` requires an inflation-proof valid benchmark-specific rerun report before any published score is accused of inflation. |
| Adoption | Public schema, validator, fixtures, and governance files. | No independent implementation or external dataset release yet. |
"""
    report = f"""# WorldEpisode Controlled Experiment Results

Generated by `python3 tools/run_experiments.py`.

These deterministic controlled experiments test whether WorldEpisode's proposed semantics are
executable and whether omitting them changes measurable outcomes. We call the general family of
these invariants Universal Spatial State (USS), but robotics is the profile evaluated in depth
here. The results are scoped experiments, not a replacement for large multi-lab robot, game-engine,
or autonomous-driving benchmarks.

The same command materializes binding round-trip artifacts in `docs/experiments/bindings/`, a pilot
conformance corpus in `conformance/fixtures/pilot/`, and checks hand-authored independent fixtures in
`conformance/fixtures/independent/`. It also writes the pilot natural-source corpus in
`docs/experiments/natural_failure_corpus/`.

{evidence_boundaries}

## RQ1: Binding Retention

- Projection profile: `{projection_profile["artifact"]}`
- Projection schema: `{projection_profile["schema"]}`
- Projection version: {projection_profile["version"]} ({projection_profile["field_count"]} fields, {projection_profile["binding_model_count"]} binding models)
- Boundary: {projection_profile["claim_boundary"]}

| Binding | Native Retention | With WorldEpisode Sidecar | Discarded Fields |
|---|---:|---:|---:|
{binding_rows}

{active_section}

{conversion_scale_section}

{timing_section}

{scene_section}

## ACT/Diffusion Policy Leakage Gate

- Gate artifact: `{policy_gate.get("artifacts", {}).get("report", "docs/experiments/lerobot_policy_gate/policy_gate_report.json")}`
- Status: {policy_gate.get("status", "unavailable")}
- Gate satisfied: {policy_gate.get("pass", False)}
- Policies: {", ".join(policy_gate.get("policies", []))}
- Jobs prepared: {len(policy_gate.get("jobs", []))}
- Virtual split datasets: {policy_gate.get("materialized_split_manifests", {}).get("manifest_count", 0)}
- Split source files with digests: {policy_gate.get("materialized_split_manifests", {}).get("source_file_count", 0)}
- Split train/test overlap zero: {policy_gate.get("materialized_split_manifests", {}).get("all_train_test_overlaps_zero", False)}
- Physical split packages: {policy_gate.get("physical_split_packages", {}).get("package_count", 0)}
- Physical source files verified: {policy_gate.get("physical_split_packages", {}).get("source_files_verified", False)}
- Physical package frames: {policy_gate.get("physical_split_packages", {}).get("total_output_frames", 0)}
- Compatibility probe: {policy_gate.get("policy_compatibility", {}).get("status", "not_run")}
- Compatibility probe matches current package: {policy_gate.get("policy_compatibility", {}).get("fresh_for_current_package", False)}
- ACT/Diffusion completed a smoke training step: {policy_gate.get("policy_compatibility", {}).get("all_policy_probes_completed_training_step", False)}
- Ready to execute in this environment: {policy_gate.get("ready_to_execute", False)}

## Temporal Policy Baseline on LeRobot Split Packages

- Artifact: `{temporal_policy.get("artifacts", {}).get("json", "docs/experiments/lerobot_temporal_policy_baseline/temporal_policy_report.json")}`
- Status: {temporal_policy.get("status", "unavailable")}
- Primary random episode nRMSE: {temporal_policy.get("aggregate", {}).get("random_episode_nrmse_mean", 0):.3f}
- Primary task--scene proxy holdout nRMSE: {temporal_policy.get("aggregate", {}).get("scene_disjoint_nrmse_mean", 0):.3f}
- Primary holdout/random nRMSE ratio: {temporal_policy.get("aggregate", {}).get("episode_nrmse_ratio_scene_over_random", 0):.2f}x
- Random episode thresholded imitation rate: {temporal_policy.get("aggregate", {}).get("random_episode_success_rate", 0):.3f}
- Task--scene proxy holdout imitation rate: {temporal_policy.get("aggregate", {}).get("scene_disjoint_success_rate", 0):.3f}
- Secondary thresholded imitation-rate drop: {temporal_policy.get("aggregate", {}).get("success_rate_drop", 0):.3f}
- Boundary: {temporal_policy.get("claim_boundary", "No temporal policy baseline result is available.")}

## Famous Benchmark Call-Out Audit

- Artifact: `{benchmark_callout.get("artifacts", {}).get("report", "docs/experiments/benchmark_callout_audit/benchmark_callout_report.json")}`
- Status: {benchmark_callout.get("status", "unavailable")}
- Benchmarks: {benchmark_callout.get("aggregate", {}).get("benchmark_count", 0)}
- Benchmarks with high-severity open controls: {benchmark_callout.get("aggregate", {}).get("benchmarks_with_high_severity_open_controls", 0)}
- Measured inflation claims in this audit: {benchmark_callout.get("aggregate", {}).get("measured_inflation_claims", 0)}

## Famous Benchmark Inflation Proof Gate

- Artifact: `{benchmark_inflation.get("artifacts", {}).get("report", "docs/experiments/benchmark_inflation_gate/gate_report.json")}`
- Status: {benchmark_inflation.get("status", "unavailable")}
- Required tests: {len(benchmark_inflation.get("required_tests", []))}
- Rerun reports committed: {benchmark_inflation.get("aggregate", {}).get("rerun_report_count", 0)}
- Executed rerun reports: {benchmark_inflation.get("aggregate", {}).get("executed_rerun_report_count", 0)}
- Inflation-proof valid rerun reports: {benchmark_inflation.get("aggregate", {}).get("valid_rerun_report_count", 0)}
- Measured famous-benchmark inflation claims: {benchmark_inflation.get("aggregate", {}).get("measured_inflation_claims", 0)}
- Ready for inflation claim: {benchmark_inflation.get("aggregate", {}).get("ready_for_inflation_claim", False)}

## Single-Line Preflight Validator

- Artifact: `{preflight_result.get("artifact", "docs/experiments/preflight/preflight_report.json")}`
- Package command: `python3 -m pip install -e .`
- CLI command: `worldepisode preflight <dataset-or-manifest>`
- Python API: `from worldepisode import preflight_lerobot; preflight_lerobot(path).raise_if_failed()`
- Cases: {len(preflight_result.get("cases", []))}
- Gate satisfied: {preflight_result.get("pass", False)}

## Dataset-Scale Manifest Audit

- Artifact: `{dataset_scale.get("artifacts", {}).get("report", "docs/experiments/dataset_scale_audit/scale_audit_report.json")}`
- Status: {dataset_scale.get("status", "unavailable")}
- Manifest: `{dataset_scale.get("manifest", "examples/scalable-corpus.worldepisode-dataset.json")}`
- Namespaces/resolvers/registries/shards/indexes/versions: {dataset_scale.get("aggregate", {}).get("namespace_count", 0)}/{dataset_scale.get("aggregate", {}).get("resolver_count", 0)}/{dataset_scale.get("aggregate", {}).get("registry_count", 0)}/{dataset_scale.get("aggregate", {}).get("shard_count", 0)}/{dataset_scale.get("aggregate", {}).get("index_count", 0)}/{dataset_scale.get("aggregate", {}).get("version_count", 0)}
- Asset descriptors: {dataset_scale.get("aggregate", {}).get("asset_descriptor_count", 0)}
- Assets with local mirrors: {dataset_scale.get("aggregate", {}).get("assets_with_local_mirrors", 0)}
- Local mirror entries: {dataset_scale.get("aggregate", {}).get("local_mirror_count", 0)}
- Asset URI schemes: {", ".join(dataset_scale.get("aggregate", {}).get("asset_uri_schemes", []))}
- World-lineage index: {dataset_scale.get("aggregate", {}).get("has_world_lineage_index", False)}
- Asset-digest index: {dataset_scale.get("aggregate", {}).get("has_asset_digest_index", False)}
- Split manifest shard: {dataset_scale.get("aggregate", {}).get("has_split_manifest_shard", False)}
- Boundary: {dataset_scale.get("claim_boundary", "Catalog invariant audit only; not a billion-episode performance benchmark.")}

## Dataset-Scale Performance Benchmark

- Artifact: `{dataset_scale_perf.get("artifacts", {}).get("report", "docs/experiments/dataset_scale_performance/performance_report.json")}`
- Status: {dataset_scale_perf.get("status", "unavailable")}
- Trace shards: {dataset_scale_perf.get("generated_catalog", {}).get("trace_shard_count", 0)}
- Described episode capacity: {dataset_scale_perf.get("generated_catalog", {}).get("described_episode_capacity", 0)}
- JSON catalog bytes opened: {dataset_scale_perf.get("generated_catalog", {}).get("json_catalog_bytes", 0)}
- Catalog open, parse, and index: {dataset_scale_perf.get("timings_ms", {}).get("catalog_open_parse_and_index", 0.0):.3f} ms
- Partition-pruning query time: {dataset_scale_perf.get("timings_ms", {}).get("partition_pruning_queries", 0.0):.3f} ms
- Max pruning reduction ratio: {dataset_scale_perf.get("partition_pruning", {}).get("max_reduction_ratio", 0.0)}
- Digest-cache hit rate: {dataset_scale_perf.get("digest_cache", {}).get("cache_hit_rate", 0.0)}
- Missing resolver count: {dataset_scale_perf.get("resolver_routing", {}).get("missing_resolver_count", 0)}
- Boundary: {dataset_scale_perf.get("claim_boundary", "Catalog-side benchmark only.")}

## Clean-Room Reader Check

- Artifact: `{cleanroom_reader.get("artifacts", {}).get("report", "docs/experiments/cleanroom_reader/cleanroom_reader_report.json")}`
- Status: {cleanroom_reader.get("status", "unavailable")}
- Fixture sets: {cleanroom_reader.get("aggregate", {}).get("fixture_set_count", 0)}
- Cases: {cleanroom_reader.get("aggregate", {}).get("case_count", 0)}
- Expected requirements: {cleanroom_reader.get("aggregate", {}).get("expected_requirement_count", 0)}
- Hit requirements: {cleanroom_reader.get("aggregate", {}).get("hit_requirement_count", 0)}
- Recall: {cleanroom_reader.get("aggregate", {}).get("recall", 0.0):.3f}
- False-positive requirements: {cleanroom_reader.get("aggregate", {}).get("false_positive_requirement_count", 0)}
- Boundary: {cleanroom_reader.get("claim_boundary", "Internal clean-room artifact only; not external adoption.")}

## Real-to-Sim Contract Drift

- Artifact: `{realtosim_drift.get("artifacts", {}).get("report", "docs/experiments/realtosim_contract_drift/contract_drift_report.json")}`
- Status: {realtosim_drift.get("status", "unavailable")}
- Ablations: {realtosim_drift.get("aggregate", {}).get("ablation_count", 0)}
- Drifted sim successes: {realtosim_drift.get("aggregate", {}).get("drifted_sim_successes", 0)}
- Drifted deployment successes: {realtosim_drift.get("aggregate", {}).get("drifted_deployment_successes", 0)}
- WorldEpisode deployment successes: {realtosim_drift.get("aggregate", {}).get("worldepisode_deployment_successes", 0)}

## Meta-Simulator Contract

- Artifact: `{meta_sim.get("artifacts", {}).get("report", "docs/experiments/meta_simulator_contract/adapter_contract_report.json")}`
- Status: {meta_sim.get("status", "unavailable")}
- Runtime targets: {meta_sim.get("aggregate", {}).get("runtime_target_count", 0)}
- Compliance layers: {meta_sim.get("aggregate", {}).get("compliance_layer_count", 0)}
- Tested adapters: {meta_sim.get("aggregate", {}).get("tested_adapter_count", 0)}
- Ready but untested adapters: {meta_sim.get("aggregate", {}).get("ready_untested_adapter_count", 0)}
- Adapters still required: {meta_sim.get("aggregate", {}).get("adapter_required_count", 0)}

## Generalization Beyond Robotics: State Drift Pilots

- Artifact: `{uss_pilots.get("artifacts", {}).get("report", "docs/experiments/uss_state_drift_pilots/state_drift_report.json")}`
- Status: {uss_pilots.get("status", "unavailable")}
- Cases: {uss_pilots.get("aggregate", {}).get("case_count", 0)}
- Locally valid files/logs: {uss_pilots.get("aggregate", {}).get("local_file_valid_count", 0)}
- Drifted behavior successes: {uss_pilots.get("aggregate", {}).get("drifted_behavior_successes", 0)}
- Non-robotics pilot detections: {uss_pilots.get("aggregate", {}).get("uss_detections", 0)}
- Non-robotics pilot corrected successes: {uss_pilots.get("aggregate", {}).get("uss_corrected_successes", 0)}

## RQ2: Fault Detection

- Cases: {fault["n_cases"]}
- Requirement precision: {fault["precision"]:.3f}
- Requirement recall: {fault["recall"]:.3f}
- False-negative requirement detections: {fault["false_negative_requirements"]}
- Independent fixture cases: {independent.get("n_cases", 0)}
- Independent fixture recall: {independent.get("recall", 0.0):.3f}
- Natural-source corpus: {natural["dataset_count"]} public datasets, {natural["case_count"]} cases
- Natural-source evidence tiers: {", ".join(f"{key}={value}" for key, value in natural.get("evidence_tiers", {}).items())}
- Natural-source artifact: `{natural["artifact"]}`
- Natural-source dataset diagnostics: `{natural.get("dataset_diagnostics_artifact", "docs/experiments/natural_failure_corpus/dataset_diagnostics.json")}`
- Natural-source dataset reports: {natural.get("dataset_report_count", 0)} reports covering {natural.get("case_count", 0)} cases
- Natural-source source-level-only reports: {natural.get("source_level_only_report_count", 0)}
- Natural-source dataset-specific diagnostics ready: {natural.get("dataset_specific_diagnostics_ready", False)}
- Natural-source dataset-count gate satisfied: {natural.get("dataset_count_gate_satisfied", False)}
- Natural-source maintainer-feedback gate satisfied: {natural.get("maintainer_feedback_satisfied", False)}
- Full natural-corpus gate satisfied: {natural["full_gate_satisfied"]}

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

{replay_section}

{contact_section}

## Replay Adapter Conformance

- Artifact: `{replay_adapter.get("artifacts", {}).get("report", "docs/experiments/replay_adapter_conformance/adapter_conformance_report.json")}`
- Status: {replay_adapter.get("status", "unavailable")}
- Cases: {replay_adapter.get("aggregate", {}).get("case_count", 0)}
- Naive scheduler failures: {replay_adapter.get("aggregate", {}).get("naive_failures", 0)}
- Contract-aware passes: {replay_adapter.get("aggregate", {}).get("contract_aware_passes", 0)}
- Boundary: {replay_adapter.get("claim_boundary", "Scheduler conformance only; not a second physics simulator.")}

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
        "lerobot_conversion_scale": experiment_lerobot_conversion_scale(),
        "lerobot_multitrajectory_timing": experiment_lerobot_multitrajectory_timing(),
        "lerobot_scene_leakage": experiment_lerobot_scene_leakage(),
        "lerobot_policy_gate": experiment_lerobot_policy_gate(),
        "lerobot_temporal_policy_baseline": experiment_lerobot_temporal_policy_baseline(),
        "benchmark_callout_audit": experiment_benchmark_callout_audit(),
        "benchmark_inflation_gate": experiment_benchmark_inflation_gate(),
        "preflight_validator": experiment_preflight_validator(),
        "realtosim_contract_drift": experiment_realtosim_contract_drift(),
        "meta_simulator_contract": experiment_meta_simulator_contract(),
        "uss_state_drift_pilots": experiment_uss_state_drift_pilots(),
        "replay_adapter_conformance": experiment_replay_adapter_conformance(),
        "contact_rich_replay": experiment_contact_rich_replay(),
        "dataset_scale_audit": experiment_dataset_scale_audit(),
        "dataset_scale_performance": experiment_dataset_scale_performance(),
        "cleanroom_reader": experiment_cleanroom_reader(),
        "rq2_fault_detection": experiment_fault_detection(base),
        "independent_fixture_check": experiment_independent_fixtures(),
        "natural_failure_corpus": experiment_natural_failure_corpus(),
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
    contact_replay = results["contact_rich_replay"]
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
    if replay.get("available"):
        alignment = replay["alignment"]
        if alignment["validation_timestamp_aware_rmse_deg"] >= alignment["validation_naive_rmse_deg"]:
            print("LeRobot timestamp-aware replay did not improve validation alignment.")
            return 1
        mujoco = replay["simulators"]["mujoco"]
        if mujoco["timestamp_aware"]["joint_rmse_deg"] >= mujoco["naive_command_time"]["joint_rmse_deg"]:
            print("MuJoCo timestamp-aware replay did not improve over naive command-time replay.")
            return 1
        genesis = replay["simulators"].get("genesis", {})
        if genesis.get("tested") and (
            genesis["timestamp_aware"]["joint_rmse_deg"] >= genesis["naive_command_time"]["joint_rmse_deg"]
        ):
            print("Genesis timestamp-aware replay did not improve over naive command-time replay.")
            return 1
    if os.environ.get("WORLDEPISODE_REQUIRE_LEROBOT_REPLAY") == "1" and not replay.get("pass"):
        print("Active LeRobot replay experiment is required but did not pass.")
        return 1
    if contact_replay.get("analysis", {}).get("acceptance", {}).get("pass") is not True:
        print("Committed contact-rich cross-simulator replay is missing or invalid.")
        return 1
    active_lerobot = results["lerobot_active_roundtrip"]
    if os.environ.get("WORLDEPISODE_REQUIRE_ACTIVE_LEROBOT") == "1" and not active_lerobot.get("pass"):
        print("Active LeRobot round-trip is required but did not pass.")
        return 1
    conversion_scale = results["lerobot_conversion_scale"]
    if conversion_scale.get("validation", {}).get("passed") is not True:
        print("Committed LeRobot conversion-scale report is missing or invalid.")
        return 1
    multitrajectory_timing = results["lerobot_multitrajectory_timing"]
    if multitrajectory_timing.get("validation", {}).get("passed") is not True:
        print("Committed multi-trajectory timing report is missing or invalid.")
        return 1
    scene_leakage = results["lerobot_scene_leakage"]
    if os.environ.get("WORLDEPISODE_REQUIRE_LEROBOT_LEAKAGE") == "1" and not scene_leakage.get("pass"):
        print("Active LeRobot task--scene proxy holdout audit is required but did not pass.")
        return 1
    benchmark_inflation = results["benchmark_inflation_gate"]
    if (
        os.environ.get("WORLDEPISODE_REQUIRE_BENCHMARK_INFLATION") == "1"
        and not benchmark_inflation.get("aggregate", {}).get("ready_for_inflation_claim")
    ):
        print("Famous-benchmark inflation evidence is required but no measured rerun claim exists.")
        return 1
    policy_gate = results["lerobot_policy_gate"]
    policy_materialization = policy_gate.get("materialized_split_manifests", {})
    physical_packages = policy_gate.get("physical_split_packages", {})
    if policy_gate.get("available") and (
        policy_materialization.get("manifest_count") != 4
        or policy_materialization.get("source_file_count", 0) < 1
        or not policy_materialization.get("all_train_test_overlaps_zero")
        or not policy_materialization.get("all_membership_counts_match")
    ):
        print("ACT/Diffusion policy gate split materialization manifests are incomplete.")
        return 1
    if policy_gate.get("available") and (
        physical_packages.get("status") != "physical_split_packages_ready"
        or physical_packages.get("package_count") != 4
        or not physical_packages.get("source_files_verified")
        or not physical_packages.get("all_train_test_overlaps_zero")
        or not physical_packages.get("all_membership_counts_match")
        or physical_packages.get("total_output_frames", 0) < 1
    ):
        print("ACT/Diffusion policy gate physical split packages are incomplete.")
        return 1
    if os.environ.get("WORLDEPISODE_REQUIRE_LEROBOT_POLICY_GATE") == "1" and not policy_gate.get("pass"):
        print("ACT/Diffusion policy leakage gate is required but did not pass.")
        return 1
    temporal_policy = results["lerobot_temporal_policy_baseline"]
    if (
        os.environ.get("WORLDEPISODE_REQUIRE_TEMPORAL_POLICY_BASELINE") == "1"
        and temporal_policy.get("status") != "measured_offline_temporal_baseline"
    ):
        print("Temporal policy baseline is required but unavailable.")
        return 1
    if temporal_policy.get("status") == "measured_offline_temporal_baseline":
        aggregate = temporal_policy.get("aggregate", {})
        if aggregate.get("success_rate_drop", 0) <= 0:
            print("Temporal policy baseline did not drop under the task--scene proxy holdout.")
            return 1
    preflight_result = results["preflight_validator"]
    if not preflight_result.get("pass"):
        print("Preflight validator regression failed.")
        return 1
    realtosim_drift = results["realtosim_contract_drift"]
    realtosim_aggregate = realtosim_drift.get("aggregate", {})
    if realtosim_aggregate.get("drifted_sim_successes") != 2:
        print("Real-to-sim drift ablation did not preserve simulated successes.")
        return 1
    if realtosim_aggregate.get("drifted_deployment_successes") != 0:
        print("Real-to-sim drift ablation did not expose deployment failures.")
        return 1
    if realtosim_aggregate.get("worldepisode_deployment_successes") != 2:
        print("WorldEpisode contract did not recover deployment successes in the drift ablation.")
        return 1
    meta_sim = results["meta_simulator_contract"]
    meta_aggregate = meta_sim.get("aggregate", {})
    if meta_aggregate.get("runtime_target_count") != 4 or meta_aggregate.get("compliance_layer_count") != 3:
        print("Meta-simulator contract matrix is incomplete.")
        return 1
    if (
        meta_aggregate.get("tested_adapter_count") != 2
        or meta_aggregate.get("ready_untested_adapter_count") != 1
        or meta_aggregate.get("adapter_required_count") != 1
    ):
        print("Meta-simulator contract evidence boundary changed unexpectedly.")
        return 1
    uss_pilots = results["uss_state_drift_pilots"]
    uss_aggregate = uss_pilots.get("aggregate", {})
    if uss_aggregate.get("case_count") != 2 or uss_aggregate.get("local_file_valid_count") != 2:
        print("Non-robotics state-drift pilots are incomplete.")
        return 1
    if uss_aggregate.get("uss_detections") != 2 or uss_aggregate.get("uss_corrected_successes") != 2:
        print("Non-robotics state-drift pilots did not detect and correct both drift cases.")
        return 1
    replay_adapter = results["replay_adapter_conformance"]
    replay_adapter_aggregate = replay_adapter.get("aggregate", {})
    if (
        replay_adapter_aggregate.get("case_count") != 3
        or replay_adapter_aggregate.get("contract_aware_passes") != 3
        or replay_adapter_aggregate.get("naive_failures", 0) < 2
    ):
        print("Replay adapter conformance did not pass expected scheduler cases.")
        return 1
    dataset_scale = results["dataset_scale_audit"]
    dataset_scale_aggregate = dataset_scale.get("aggregate", {})
    if not dataset_scale.get("pass"):
        print("Dataset-scale manifest audit failed.")
        return 1
    if (
        dataset_scale_aggregate.get("asset_descriptor_count", 0) < 1
        or not dataset_scale_aggregate.get("has_world_lineage_index")
        or not dataset_scale_aggregate.get("has_asset_digest_index")
        or not dataset_scale_aggregate.get("has_split_manifest_shard")
    ):
        print("Dataset-scale manifest audit is missing required production catalog invariants.")
        return 1
    dataset_scale_perf = results["dataset_scale_performance"]
    scale_catalog = dataset_scale_perf.get("generated_catalog", {})
    scale_partition = dataset_scale_perf.get("partition_pruning", {})
    scale_cache = dataset_scale_perf.get("digest_cache", {})
    scale_resolver = dataset_scale_perf.get("resolver_routing", {})
    if not dataset_scale_perf.get("pass"):
        print("Dataset-scale performance benchmark failed.")
        return 1
    if (
        scale_catalog.get("described_episode_capacity", 0) < 1_000_000_000
        or scale_catalog.get("trace_shard_count", 0) < 32768
        or not scale_partition.get("all_queries_pruned")
        or scale_partition.get("max_reduction_ratio", 1.0) >= 0.01
        or scale_cache.get("digest_mismatches", 1) != 0
        or scale_cache.get("cache_hit_rate", 0.0) < 0.70
        or scale_resolver.get("missing_resolver_count", 1) != 0
    ):
        print("Dataset-scale performance benchmark is missing required catalog behavior.")
        return 1
    cleanroom_reader = results["cleanroom_reader"]
    cleanroom_aggregate = cleanroom_reader.get("aggregate", {})
    if not cleanroom_reader.get("pass"):
        print("Clean-room reader check failed.")
        return 1
    if cleanroom_aggregate.get("case_count", 0) < 1 or cleanroom_aggregate.get("recall", 0.0) < 1.0:
        print("Clean-room reader did not catch all expected fixture requirements.")
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
