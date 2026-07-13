"""Command-line interface for WorldEpisode."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .preflight import DEFAULT_FAIL_ON, preflight


def _add_preflight_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("target", help="WorldEpisode manifest, LeRobot v3 directory/repo id, or Rerun .rrd file.")
    parser.add_argument(
        "--kind",
        choices=["auto", "worldepisode", "worldepisode-dataset", "lerobot", "rerun"],
        default="auto",
        help="Artifact kind. Defaults to auto-detection.",
    )
    parser.add_argument("--sidecar", type=Path, help="Explicit WorldEpisode manifest/sidecar path.")
    parser.add_argument(
        "--fail-on",
        choices=["error", "warning"],
        default=DEFAULT_FAIL_ON,
        help="Exit non-zero when diagnostics at this severity or higher are present.",
    )
    parser.add_argument(
        "--advisory",
        action="store_true",
        help="Advisory mode: exit non-zero only on errors, not warnings.",
    )
    parser.add_argument("--json", action="store_true", help="Write machine-readable JSON output.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="worldepisode")
    subparsers = parser.add_subparsers(dest="command")
    for command in ("preflight", "validate"):
        subparser = subparsers.add_parser(command)
        _add_preflight_args(subparser)

    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 2

    fail_on = "error" if args.advisory else args.fail_on
    report = preflight(args.target, kind=args.kind, sidecar=args.sidecar, fail_on=fail_on)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(report.format_text())
    return 1 if report.has_failures() else 0
