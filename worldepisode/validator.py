"""Schema and semantic validation for WorldEpisode manifests."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

import jsonschema


SHA_RE = re.compile(r"^[a-f0-9]{64}$")
WORLD_REVISION_RE = re.compile(r"sha256:[a-f0-9]{64}")

SCHEMA_FILES = {
    "worldepisode": "worldepisode-core-v0.schema.json",
    "worldepisode-dataset": "worldepisode-dataset-v0.schema.json",
    "conformance": "conformance-requirements-v0.schema.json",
    "layout": "le-world-layout-v0.schema.json",
}


@dataclass(frozen=True)
class Diagnostic:
    requirement: str
    location: str
    message: str
    severity: str = "error"
    hint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "requirement": self.requirement,
            "severity": self.severity,
            "location": self.location,
            "message": self.message,
        }
        if self.hint:
            payload["hint"] = self.hint
        return payload


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_schema(kind: str) -> dict[str, Any]:
    try:
        filename = SCHEMA_FILES[kind]
    except KeyError as exc:
        known = ", ".join(sorted(SCHEMA_FILES))
        raise ValueError(f"unknown schema kind {kind!r}; expected one of {known}") from exc
    with resources.files("worldepisode.schemas").joinpath(filename).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def json_pointer(parts: list[str | int]) -> str:
    if not parts:
        return "/"
    escaped = [str(part).replace("~", "~0").replace("/", "~1") for part in parts]
    return "/" + "/".join(escaped)


def iter_assets(payload: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    assets: list[tuple[str, dict[str, Any]]] = []

    def walk(value: Any, path: list[str | int]) -> None:
        if isinstance(value, dict):
            if {"uri", "media_type", "sha256"}.issubset(value.keys()):
                assets.append((json_pointer(path), value))
            for key, child in value.items():
                walk(child, [*path, key])
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, [*path, index])

    walk(payload, [])
    return assets


def validate_schema(payload: dict[str, Any], kind: str = "worldepisode") -> list[Diagnostic]:
    validator = jsonschema.Draft202012Validator(load_schema(kind))
    diagnostics = []
    for error in sorted(validator.iter_errors(payload), key=lambda item: list(item.path)):
        diagnostics.append(
            Diagnostic(
                "SCHEMA.001",
                json_pointer(list(error.path)),
                error.message,
                "error",
                "Validate the document against the published JSON Schema before training.",
            )
        )
    return diagnostics


def validate_semantics(payload: dict[str, Any]) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []

    def add(requirement: str, location: str, message: str, hint: str | None = None) -> None:
        diagnostics.append(Diagnostic(requirement, location, message, "error", hint))

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
            add(
                "TIME.002",
                f"/clock_graph/mappings/{index}",
                "Cross-clock mapping lacks drift or error.",
            )

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
    if not WORLD_REVISION_RE.search(world_revision_id):
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


def validate_worldepisode(payload: dict[str, Any], *, schema: bool = True, semantics: bool = True) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if schema:
        diagnostics.extend(validate_schema(payload, "worldepisode"))
    if semantics:
        diagnostics.extend(validate_semantics(payload))
    return diagnostics


def validate_dataset_manifest(payload: dict[str, Any], *, schema: bool = True) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if schema:
        diagnostics.extend(validate_schema(payload, "worldepisode-dataset"))

    namespace_prefixes = [
        item.get("prefix")
        for item in payload.get("namespaces", [])
        if isinstance(item, dict) and item.get("prefix")
    ]
    duplicates = sorted({prefix for prefix in namespace_prefixes if namespace_prefixes.count(prefix) > 1})
    for prefix in duplicates:
        diagnostics.append(
            Diagnostic(
                "DATASET.001",
                "/namespaces",
                f"Duplicate namespace prefix {prefix!r}.",
                "error",
                "Namespace prefixes must be stable, unique keys for production-scale catalogs.",
            )
        )
    return diagnostics
