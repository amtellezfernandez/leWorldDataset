#!/usr/bin/env python3
"""Validate WorldEpisode examples against their draft schemas."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
LAYOUT_SCHEMA_PATH = ROOT / "schemas" / "le-world-layout-v0.schema.json"
WORLDEPISODE_SCHEMA_PATH = ROOT / "schemas" / "worldepisode-core-v0.schema.json"
EXAMPLES_DIR = ROOT / "examples"


def load_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    validators = {
        ".layout.json": jsonschema.Draft202012Validator(load_json(LAYOUT_SCHEMA_PATH)),
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

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
