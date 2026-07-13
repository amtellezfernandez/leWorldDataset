#!/usr/bin/env python3
"""Fail if regenerated artifacts changed outside approved volatile timing fields.

CI regenerates the experiment, open-gate, paper-claim, and release-readiness artifacts before
running this check. A clean repository means the tracked evidence is fresh. The only approved
drift is wall-clock timing jitter from the dataset-scale catalog benchmark.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Pattern


ROOT = Path(__file__).resolve().parents[1]

TIMING = r"[0-9]+(?:\.[0-9]+)?"
TIMING_KEYS = (
    "catalog_open_parse_and_index",
    "digest_cache_resolution",
    "partition_pruning_queries",
    "resolver_routing",
)

ALLOWED_TEXT_DIFFS: dict[str, list[Pattern[str]]] = {
    "docs/experiments/dataset_scale_performance/performance_report.json": [
        re.compile(rf'^[+-]\s+"({"|".join(TIMING_KEYS)})": {TIMING},?$'),
    ],
    "docs/experiments/results.json": [
        re.compile(rf'^[+-]\s+"({"|".join(TIMING_KEYS)})": {TIMING},?$'),
    ],
    "docs/experiments/RESULTS.md": [
        re.compile(rf"^[+-]- Catalog open, parse, and index: {TIMING} ms$"),
        re.compile(rf"^[+-]- Partition-pruning query time: {TIMING} ms$"),
    ],
    "docs/experiments/dataset_scale_performance/README.md": [
        re.compile(rf"^[+-]\| Catalog open, parse, and index \| {TIMING} \|$"),
        re.compile(rf"^[+-]\| Partition-pruning queries \| {TIMING} \|$"),
        re.compile(rf"^[+-]\| Digest-cache resolution \| {TIMING} \|$"),
        re.compile(rf"^[+-]\| Resolver routing \| {TIMING} \|$"),
    ],
    "docs/experiments/release_readiness/README.md": [
        re.compile(
            r"^[+-]\| DOC\.007 \| controlled results exist \| True \| error \| "
            r"docs/experiments/results\.json \([0-9]+ bytes\) \|$"
        ),
    ],
    "docs/experiments/release_readiness/release_readiness_report.json": [
        re.compile(
            r'^[+-]\s+"evidence": "docs/experiments/results\.json \([0-9]+ bytes\)",$'
        ),
    ],
}

DIFF_METADATA_PREFIXES = (
    "diff --git ",
    "index ",
    "--- ",
    "+++ ",
    "@@",
    "\\ No newline",
)


def git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def changed_entries() -> list[dict[str, str]]:
    result = git(["status", "--porcelain", "--untracked-files=all"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git status --porcelain failed")
    entries: list[dict[str, str]] = []
    for line in result.stdout.splitlines():
        if not line:
            continue
        status = line[:2]
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        entries.append({"status": status, "path": path})
    return entries


def diff_for(path: str) -> list[str]:
    result = git(["diff", "--no-ext-diff", "HEAD", "--", path])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git diff failed for {path}")
    return result.stdout.splitlines()


def unapproved_lines(entry: dict[str, str]) -> list[str]:
    path = entry["path"]
    if entry["status"] == "??":
        return [f"{path}: untracked file"]

    patterns = ALLOWED_TEXT_DIFFS.get(path)
    if patterns is None:
        return [f"{path}: unapproved changed file"]

    rejected: list[str] = []
    for line in diff_for(path):
        if line.startswith(DIFF_METADATA_PREFIXES):
            continue
        if not line.startswith(("+", "-")):
            continue
        if not any(pattern.match(line) for pattern in patterns):
            rejected.append(f"{path}: {line}")
    return rejected


def build_report() -> dict[str, object]:
    entries = changed_entries()
    unapproved: list[str] = []
    allowed: list[str] = []
    for entry in entries:
        path = entry["path"]
        path_unapproved = unapproved_lines(entry)
        if path_unapproved:
            unapproved.extend(path_unapproved)
        else:
            allowed.append(path)

    if unapproved:
        status = "fail"
    elif allowed:
        status = "allowed_volatile_changes"
    else:
        status = "clean"

    return {
        "schema": "worldepisode_artifact_freshness_v1",
        "status": status,
        "changed_files": [entry["path"] for entry in entries],
        "changed_entries": entries,
        "allowed_volatile_files": allowed,
        "unapproved_changes": unapproved,
        "allowed_boundary": (
            "Only dataset-scale wall-clock timing jitter is allowed after regenerating artifacts."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="exit non-zero on unapproved changes")
    args = parser.parse_args()

    report = build_report()
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.strict and report["status"] == "fail":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
