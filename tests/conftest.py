"""Shared paths for the worldepisode test suite."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# Allow running the suite from a checkout without installing the package.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def pilot_manifest() -> dict:
    return load_json(REPO_ROOT / "conformance" / "fixtures" / "pilot" / "manifest.json")


def independent_manifest() -> dict:
    return load_json(REPO_ROOT / "conformance" / "fixtures" / "independent" / "manifest.json")
