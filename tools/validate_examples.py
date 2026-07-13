#!/usr/bin/env python3
"""Validate WorldEpisode examples against their draft schemas."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
LAYOUT_SCHEMA_PATH = ROOT / "schemas" / "le-world-layout-v0.schema.json"
WORLDEPISODE_SCHEMA_PATH = ROOT / "schemas" / "worldepisode-core-v0.schema.json"
WORLDEPISODE_DATASET_SCHEMA_PATH = ROOT / "schemas" / "worldepisode-dataset-v0.schema.json"
CONFORMANCE_SCHEMA_PATH = ROOT / "schemas" / "conformance-requirements-v0.schema.json"
SEMANTIC_PROJECTION_SCHEMA_PATH = ROOT / "schemas" / "semantic-projection-v0.schema.json"
EXAMPLES_DIR = ROOT / "examples"
CONFORMANCE_REQUIREMENTS_PATH = ROOT / "conformance" / "requirements.v0.json"
SEMANTIC_PROJECTION_PATH = ROOT / "conformance" / "projections" / "uss-core-23.v0.json"


def load_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    validators = {
        ".layout.json": jsonschema.Draft202012Validator(load_json(LAYOUT_SCHEMA_PATH)),
        ".worldepisode-dataset.json": jsonschema.Draft202012Validator(
            load_json(WORLDEPISODE_DATASET_SCHEMA_PATH)
        ),
        ".worldepisode.json": jsonschema.Draft202012Validator(load_json(WORLDEPISODE_SCHEMA_PATH)),
    }
    failures = 0

    for example_path in sorted(EXAMPLES_DIR.glob("*.json")):
        validator = next(
            (candidate for suffix, candidate in validators.items() if example_path.name.endswith(suffix)),
            None,
        )
        if validator is None:
            failures += 1
            print(f"FAIL {example_path.relative_to(ROOT)}")
            print("  <root>: no schema mapping for example filename")
            continue
        payload = load_json(example_path)
        errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.path))
        if errors:
            failures += 1
            print(f"FAIL {example_path.relative_to(ROOT)}")
            for error in errors:
                location = ".".join(str(part) for part in error.path) or "<root>"
                print(f"  {location}: {error.message}")
        else:
            print(f"OK   {example_path.relative_to(ROOT)}")

    conformance_validator = jsonschema.Draft202012Validator(load_json(CONFORMANCE_SCHEMA_PATH))
    conformance_payload = load_json(CONFORMANCE_REQUIREMENTS_PATH)
    requirement_ids = {item["id"] for item in conformance_payload["requirements"]}
    conformance_errors = sorted(
        conformance_validator.iter_errors(conformance_payload),
        key=lambda error: list(error.path),
    )
    if conformance_errors:
        failures += 1
        print(f"FAIL {CONFORMANCE_REQUIREMENTS_PATH.relative_to(ROOT)}")
        for error in conformance_errors:
            location = ".".join(str(part) for part in error.path) or "<root>"
            print(f"  {location}: {error.message}")
    else:
        unknown_profile_refs = {
            requirement_id
            for profile_ids in conformance_payload["profiles"].values()
            for requirement_id in profile_ids
            if requirement_id not in requirement_ids
        }
        if unknown_profile_refs:
            failures += 1
            refs = ", ".join(sorted(unknown_profile_refs))
            print(f"FAIL {CONFORMANCE_REQUIREMENTS_PATH.relative_to(ROOT)}")
            print(f"  profiles: unknown requirement reference(s): {refs}")
        else:
            print(f"OK   {CONFORMANCE_REQUIREMENTS_PATH.relative_to(ROOT)}")

    projection_validator = jsonschema.Draft202012Validator(load_json(SEMANTIC_PROJECTION_SCHEMA_PATH))
    projection_payload = load_json(SEMANTIC_PROJECTION_PATH)
    projection_errors = sorted(
        projection_validator.iter_errors(projection_payload),
        key=lambda error: list(error.path),
    )
    if projection_errors:
        failures += 1
        print(f"FAIL {SEMANTIC_PROJECTION_PATH.relative_to(ROOT)}")
        for error in projection_errors:
            location = ".".join(str(part) for part in error.path) or "<root>"
            print(f"  {location}: {error.message}")
    else:
        projection_fields = [field["path"] for field in projection_payload["fields"]]
        duplicate_projection_fields = sorted(
            {field for field in projection_fields if projection_fields.count(field) > 1}
        )
        unknown_requirement_refs = {
            requirement_id
            for field in projection_payload["fields"]
            for requirement_id in field["requirement_ids"]
            if requirement_id not in requirement_ids
        }
        unknown_field_refs = {
            f"{binding['binding']}:{field}"
            for binding in projection_payload["binding_models"]
            for field in [*binding.get("native_fields", []), *binding.get("sidecar_fields", [])]
            if field not in projection_fields
        }
        listed_without_fields = {
            binding["binding"]
            for binding in projection_payload["binding_models"]
            if binding["sidecar_policy"] == "listed_only" and "sidecar_fields" not in binding
        }
        projection_failures = []
        if projection_payload["field_count"] != len(projection_fields):
            projection_failures.append(
                f"field_count {projection_payload['field_count']} != {len(projection_fields)}"
            )
        if duplicate_projection_fields:
            projection_failures.append(
                "duplicate field path(s): " + ", ".join(duplicate_projection_fields)
            )
        if unknown_requirement_refs:
            projection_failures.append(
                "unknown requirement reference(s): " + ", ".join(sorted(unknown_requirement_refs))
            )
        if unknown_field_refs:
            projection_failures.append(
                "unknown binding field reference(s): " + ", ".join(sorted(unknown_field_refs))
            )
        if listed_without_fields:
            projection_failures.append(
                "listed_only binding(s) without sidecar_fields: " + ", ".join(sorted(listed_without_fields))
            )
        if projection_failures:
            failures += 1
            print(f"FAIL {SEMANTIC_PROJECTION_PATH.relative_to(ROOT)}")
            for failure in projection_failures:
                print(f"  {failure}")
        else:
            print(f"OK   {SEMANTIC_PROJECTION_PATH.relative_to(ROOT)}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
