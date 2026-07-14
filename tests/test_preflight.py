"""Preflight behavior: valid manifests pass, invalid ones and bare native artifacts fail closed."""

from __future__ import annotations

import pytest

from conftest import REPO_ROOT
from worldepisode import preflight
from worldepisode.preflight import preflight_rerun

MINIMAL_EPISODE = REPO_ROOT / "examples" / "minimal.worldepisode.json"
INVALID_FIXTURE = (
    REPO_ROOT / "conformance" / "fixtures" / "pilot" / "invalid" / "TIME.001_missing_clock_domain.worldepisode.json"
)
BARE_RRD = REPO_ROOT / "docs" / "experiments" / "preflight" / "recording_without_sidecar.rrd"


def test_valid_manifest_passes() -> None:
    report = preflight(str(MINIMAL_EPISODE))
    assert report.ok, report.format_text()
    report.raise_if_failed()


def test_invalid_fixture_fails() -> None:
    report = preflight(str(INVALID_FIXTURE))
    assert not report.ok
    assert any(diag.requirement == "TIME.001" for diag in report.diagnostics)
    with pytest.raises(RuntimeError, match="preflight failed"):
        report.raise_if_failed()


def test_rerun_recording_without_sidecar_fails_closed() -> None:
    report = preflight_rerun(str(BARE_RRD))
    assert report.has_failures(), "a native .rrd without a WorldEpisode sidecar must fail closed"


def test_rerun_recording_with_valid_sidecar_passes() -> None:
    report = preflight_rerun(str(BARE_RRD), sidecar=str(MINIMAL_EPISODE))
    assert report.ok, report.format_text()
