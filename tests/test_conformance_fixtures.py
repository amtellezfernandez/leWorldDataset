"""The committed conformance corpora are the ground truth for the validator.

Every invalid fixture must trigger at least its expected requirement IDs
(recall 1.0 over expected instances); valid fixtures must produce no
error-severity diagnostics.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import REPO_ROOT, independent_manifest, load_json, pilot_manifest
from worldepisode.validator import validate_worldepisode

PILOT_DIR = REPO_ROOT / "conformance" / "fixtures" / "pilot"
INDEPENDENT_DIR = REPO_ROOT / "conformance" / "fixtures" / "independent"


def _invalid_cases() -> list[tuple[Path, frozenset[str]]]:
    cases = []
    for entry in pilot_manifest()["invalid"]:
        cases.append((PILOT_DIR / entry["path"], frozenset(entry["expected_requirements"])))
    for entry in independent_manifest()["invalid"]:
        cases.append((INDEPENDENT_DIR / entry["path"], frozenset(entry["expected_requirements"])))
    return cases


def _valid_cases() -> list[Path]:
    return [PILOT_DIR / entry["path"] for entry in pilot_manifest()["valid"]]


@pytest.mark.parametrize(
    ("fixture_path", "expected"),
    _invalid_cases(),
    ids=lambda value: value.name if isinstance(value, Path) else "-".join(sorted(value)),
)
def test_invalid_fixture_triggers_expected_requirements(fixture_path: Path, expected: frozenset[str]) -> None:
    payload = load_json(fixture_path)
    emitted = {diag.requirement for diag in validate_worldepisode(payload)}
    missing = expected - emitted
    assert not missing, f"{fixture_path.name}: expected requirements not emitted: {sorted(missing)}"


@pytest.mark.parametrize("fixture_path", _valid_cases(), ids=lambda p: p.name)
def test_valid_fixture_has_no_errors(fixture_path: Path) -> None:
    payload = load_json(fixture_path)
    errors = [diag for diag in validate_worldepisode(payload) if diag.severity == "error"]
    assert not errors, f"{fixture_path.name}: unexpected errors: {[d.to_dict() for d in errors]}"


def test_corpus_shape_matches_paper_claim() -> None:
    """The paper claims 18 expected requirement instances across 17 fixtures."""
    pilot = pilot_manifest()
    independent = independent_manifest()
    fixture_count = len(pilot["invalid"]) + len(pilot["valid"]) + len(independent["invalid"])
    instance_count = sum(len(entry["expected_requirements"]) for entry in pilot["invalid"]) + sum(
        len(entry["expected_requirements"]) for entry in independent["invalid"]
    )
    assert fixture_count == 17
    assert instance_count == 18
