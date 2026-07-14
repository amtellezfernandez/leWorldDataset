"""Unit tests for schema loading and semantic validation."""

from __future__ import annotations

import copy

import pytest

from conftest import REPO_ROOT, load_json
from worldepisode.validator import (
    load_schema,
    validate_dataset_manifest,
    validate_schema,
    validate_semantics,
    validate_worldepisode,
)

MINIMAL_EPISODE = REPO_ROOT / "examples" / "minimal.worldepisode.json"
DATASET_MANIFEST = REPO_ROOT / "examples" / "scalable-corpus.worldepisode-dataset.json"


def test_minimal_example_is_clean() -> None:
    payload = load_json(MINIMAL_EPISODE)
    errors = [diag for diag in validate_worldepisode(payload) if diag.severity == "error"]
    assert errors == []


def test_load_schema_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError, match="unknown schema kind"):
        load_schema("no-such-schema")


def test_schema_rejects_unknown_top_level_key() -> None:
    payload = load_json(MINIMAL_EPISODE)
    payload["unexpected_field"] = True
    diagnostics = validate_schema(payload, "worldepisode")
    assert any(diag.requirement == "SCHEMA.001" for diag in diagnostics)


def test_semantics_flags_unknown_transform_frame() -> None:
    payload = copy.deepcopy(load_json(MINIMAL_EPISODE))
    payload["frame_graph"]["transforms"][0]["source_frame"] = "not-declared"
    emitted = {diag.requirement for diag in validate_semantics(payload)}
    assert "FRAME.001" in emitted


def test_semantics_flags_non_content_addressed_world_revision() -> None:
    payload = copy.deepcopy(load_json(MINIMAL_EPISODE))
    payload["world_revision"]["world_revision_id"] = "world_demo_tabletop@v2"
    emitted = {diag.requirement for diag in validate_semantics(payload)}
    assert "WORLD.001" in emitted


def test_semantics_flags_resolved_digest_mismatch() -> None:
    payload = copy.deepcopy(load_json(MINIMAL_EPISODE))
    asset = payload["world_revision"]["asset"]
    asset["resolved_sha256"] = "f" * 64
    emitted = {diag.requirement for diag in validate_semantics(payload)}
    assert "ASSET.002" in emitted


def test_dataset_manifest_example_is_clean() -> None:
    payload = load_json(DATASET_MANIFEST)
    errors = [diag for diag in validate_dataset_manifest(payload) if diag.severity == "error"]
    assert errors == []


def test_dataset_manifest_flags_duplicate_namespace_prefix() -> None:
    payload = copy.deepcopy(load_json(DATASET_MANIFEST))
    payload["namespaces"].append(dict(payload["namespaces"][0]))
    emitted = {diag.requirement for diag in validate_dataset_manifest(payload)}
    assert "DATASET.003" in emitted
