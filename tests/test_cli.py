"""CLI smoke tests: exit codes and JSON output of `worldepisode preflight`."""

from __future__ import annotations

import json
import subprocess
import sys

from conftest import REPO_ROOT

MINIMAL_EPISODE = REPO_ROOT / "examples" / "minimal.worldepisode.json"
INVALID_FIXTURE = (
    REPO_ROOT / "conformance" / "fixtures" / "pilot" / "invalid" / "TIME.001_missing_clock_domain.worldepisode.json"
)


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "worldepisode", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_preflight_passes_on_minimal_example() -> None:
    result = run_cli("preflight", str(MINIMAL_EPISODE))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS" in result.stdout


def test_preflight_fails_on_invalid_fixture() -> None:
    result = run_cli("preflight", str(INVALID_FIXTURE))
    assert result.returncode == 1
    assert "FAIL" in result.stdout


def test_preflight_json_output_is_parseable() -> None:
    result = run_cli("preflight", "--json", str(INVALID_FIXTURE))
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert any(diag["requirement"] == "TIME.001" for diag in payload["diagnostics"])


def test_missing_subcommand_exits_2() -> None:
    result = run_cli()
    assert result.returncode == 2
