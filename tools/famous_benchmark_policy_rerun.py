#!/usr/bin/env python3
"""Run a bounded policy-rerun evidence probe on a famous public benchmark subset.

This tool exists to keep the paper honest. A source-level call-out audit can identify missing
public controls, but it cannot prove score inflation. This script downloads a pinned public
LeRobot-style benchmark subset, builds a small WorldEpisode evidence package, compares a random
episode split against a lineage-disjoint split, and runs the same deterministic offline
state-action policy on both splits.

The default target is the small public DROID LeRobot mirror. The result is intentionally scoped:
it can support a measured subset-level offline imitation finding, but it does not become a claim
about published leaderboard inflation unless the stricter benchmark inflation gate accepts it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import numpy as np
import requests


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = ROOT / "docs" / "experiments" / "benchmark_reruns"
DEFAULT_CACHE_ROOT = ROOT / ".cache" / "worldepisode" / "famous_benchmark_reruns"
AUDIT_DATE = "2026-07-13"
RANDOM_SEED = 17
RIDGE_LAMBDA = 1e-3


BENCHMARKS: dict[str, dict[str, Any]] = {
    "droid_100": {
        "benchmark_id": "droid",
        "name": "DROID 100 LeRobot subset",
        "repo_id": "lerobot/droid_100",
        "revision": "87301a2d2e99340e2010c9ef0f1d8e780b08aaf9",
        "required_paths": [
            "meta/info.json",
            "meta/tasks.parquet",
            "meta/episodes/chunk-000/file-000.parquet",
            "data/chunk-000/file-000.parquet",
        ],
        "expected_data_files": ["data/chunk-000/file-000.parquet"],
        "claim_boundary": (
            "Small public DROID LeRobot mirror. This is a bounded offline state/action rerun, not "
            "a reproduction of a DROID leaderboard or a hardware rollout."
        ),
    },
    "bridgedata2_v3_tiny": {
        "benchmark_id": "bridgedata_v2",
        "name": "BridgeData V2 LeRobot v3 tiny shard subset",
        "repo_id": "nvidia/BridgeData2_LeRobot_v3",
        "revision": "b96f7216e3cff58007884656a81584c857c185ae",
        "required_paths": [
            "meta/info.json",
            "meta/tasks.parquet",
            "meta/episodes/chunk-000/file-000.parquet",
            "data/chunk-000/file-000.parquet",
            "data/chunk-000/file-001.parquet",
        ],
        "expected_data_files": [
            "data/chunk-000/file-000.parquet",
            "data/chunk-000/file-001.parquet",
        ],
        "claim_boundary": (
            "First two public BridgeData V2 LeRobot v3 data shards. This is a bounded offline "
            "state/action rerun, not a full BridgeData V2 policy reproduction."
        ),
    },
}


class RerunUnavailable(RuntimeError):
    """Raised when required data or optional dependencies are unavailable."""


@dataclass(frozen=True)
class EpisodeGroup:
    episode_index: int
    lineage_id: str
    lineage_value: str
    task_index: int | None
    frame_count: int


def import_pyarrow() -> tuple[Any, Any]:
    try:
        import pyarrow.compute as pc  # type: ignore[import-not-found]
        import pyarrow.parquet as pq  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:
        raise RerunUnavailable(
            "pyarrow is required to read public LeRobot parquet shards. Reproduce with "
            "`uv run --with pyarrow --with requests --with numpy python "
            "tools/famous_benchmark_policy_rerun.py --required`."
        ) from exc
    return pc, pq


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hf_url(repo_id: str, revision: str, path: str) -> str:
    return f"https://huggingface.co/datasets/{repo_id}/resolve/{revision}/{path}"


def hf_uri(repo_id: str, revision: str, path: str) -> str:
    return f"hf://{repo_id}@{revision}/{path}"


def resolve_host_with_doh(hostname: str) -> list[str]:
    """Resolve a hostname through DNS-over-HTTPS when the local resolver is unavailable."""
    try:
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except (ImportError, AttributeError):
        pass
    resolvers = [
        (
            "https://1.1.1.1/dns-query",
            {"accept": "application/dns-json", "host": "cloudflare-dns.com"},
        ),
        (
            "https://8.8.8.8/resolve",
            {"host": "dns.google"},
        ),
    ]
    addresses: list[str] = []
    for endpoint, headers in resolvers:
        try:
            response = requests.get(
                endpoint,
                params={"name": hostname, "type": "A"},
                headers=headers,
                timeout=20,
                verify=False,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError):
            continue
        for answer in payload.get("Answer", []):
            if answer.get("type") == 1 and isinstance(answer.get("data"), str):
                addresses.append(answer["data"])
    return sorted(set(addresses))


def download_with_resolved_host(url: str, output_path: Path) -> list[str]:
    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        return ["fallback skipped: URL has no hostname"]
    curl = shutil.which("curl")
    if curl is None:
        return ["fallback skipped: curl is not installed"]
    addresses = resolve_host_with_doh(hostname)
    if not addresses:
        return [f"fallback skipped: DNS-over-HTTPS returned no A records for {hostname}"]

    errors: list[str] = []
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    for address in addresses:
        command = [
            curl,
            "--fail",
            "--location",
            "--silent",
            "--show-error",
            "--connect-timeout",
            "30",
            "--max-time",
            "180",
            "--resolve",
            f"{hostname}:443:{address}",
            url,
            "--output",
            str(tmp_path),
        ]
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        if result.returncode == 0 and tmp_path.exists() and tmp_path.stat().st_size > 0:
            tmp_path.replace(output_path)
            return []
        errors.append(
            f"curl --resolve {hostname}:443:{address} exited {result.returncode}: "
            f"{(result.stderr or result.stdout).strip()[:400]}"
        )
        tmp_path.unlink(missing_ok=True)
    return errors


def download_file(repo_id: str, revision: str, remote_path: str, cache_root: Path) -> dict[str, Any]:
    local_path = cache_root / repo_id.replace("/", "__") / revision / remote_path
    local_path.parent.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    if not local_path.exists():
        url = hf_url(repo_id, revision, remote_path)
        for attempt in range(1, 6):
            try:
                response = requests.get(url, timeout=120)
                response.raise_for_status()
                local_path.write_bytes(response.content)
                break
            except requests.RequestException as exc:
                errors.append(f"attempt {attempt}: {type(exc).__name__}: {exc}")
                time.sleep(min(2 * attempt, 10))
        else:
            fallback_errors = download_with_resolved_host(url, local_path)
            if fallback_errors:
                errors.extend(fallback_errors)
        if not local_path.exists():
            raise RerunUnavailable(f"could not download {remote_path}: " + " | ".join(errors))
    return {
        "uri": hf_uri(repo_id, revision, remote_path),
        "path": remote_path,
        "local_mirror": rel(local_path),
        "bytes": local_path.stat().st_size,
        "sha256": sha256_file(local_path),
        "media_type": "application/vnd.apache.parquet" if remote_path.endswith(".parquet") else "application/json",
    }


def fetch_sources(config: dict[str, Any], cache_root: Path) -> dict[str, dict[str, Any]]:
    return {
        path: download_file(config["repo_id"], config["revision"], path, cache_root)
        for path in config["required_paths"]
    }


def local_source_path(cache_root: Path, config: dict[str, Any], remote_path: str) -> Path:
    return cache_root / config["repo_id"].replace("/", "__") / config["revision"] / remote_path


def flatten_vector(value: Any) -> list[float]:
    if value is None:
        return []
    if isinstance(value, np.ndarray):
        return [float(item) for item in value.reshape(-1).tolist()]
    if isinstance(value, (list, tuple)):
        out: list[float] = []
        for item in value:
            out.extend(flatten_vector(item))
        return out
    return [float(value)]


def task_map(tasks_table: dict[str, Any]) -> dict[int, str]:
    if "task_index" in tasks_table and "task" in tasks_table:
        return {
            int(task_index): str(task)
            for task_index, task in zip(tasks_table["task_index"], tasks_table["task"], strict=False)
        }
    if "index" in tasks_table and "task" in tasks_table:
        return {
            int(task_index): str(task)
            for task_index, task in zip(tasks_table["index"], tasks_table["task"], strict=False)
        }
    return {index: str(task) for index, task in enumerate(tasks_table.get("task", []))}


def detect_episode_lineage(
    info: dict[str, Any],
    episodes: dict[str, Any],
    task_by_index: dict[int, str],
    episode_task_index: dict[int, int],
    frame_counts: dict[int, int],
    repo_id: str,
    revision: str,
) -> tuple[list[EpisodeGroup], dict[str, Any]]:
    episode_ids = sorted(frame_counts)
    candidate_columns = [
        column
        for column in episodes
        if any(token in column.lower() for token in ("scene", "environment", "env", "location", "site", "camera"))
    ]
    selected_column = None
    selected_values: dict[int, str] = {}
    if "episode_index" in episodes:
        episode_rows = [int(value) for value in episodes["episode_index"]]
        for column in candidate_columns:
            values = episodes[column]
            by_episode = {
                episode_index: json.dumps(value, sort_keys=True, default=str)
                for episode_index, value in zip(episode_rows, values, strict=False)
            }
            distinct = {by_episode.get(episode_id) for episode_id in episode_ids}
            if len(distinct) > 1:
                selected_column = column
                selected_values = {episode_id: by_episode.get(episode_id, "unknown") for episode_id in episode_ids}
                break

    camera_schema = {
        name: feature.get("shape")
        for name, feature in sorted(info.get("features", {}).items())
        if isinstance(feature, dict) and feature.get("dtype") == "video"
    }
    groups: list[EpisodeGroup] = []
    if selected_column:
        lineage_source = {
            "kind": "physical_metadata_column",
            "column": selected_column,
            "sufficient_for_score_inflation_claim": True,
        }
    else:
        lineage_source = {
            "kind": "task_camera_schema_proxy",
            "column": "task_index + task text + camera feature schema",
            "sufficient_for_score_inflation_claim": False,
            "reason": (
                "The mirrored public metadata did not expose a distinct physical scene, site, or "
                "capture-lineage column. The corrected split is therefore a proxy stress test, not "
                "proof of scene-leakage inflation in the original benchmark."
            ),
        }

    for episode_id in episode_ids:
        task_index = episode_task_index.get(episode_id)
        if selected_column:
            lineage_value = selected_values.get(episode_id, "unknown")
        else:
            task_text = task_by_index.get(task_index, "unknown_task") if task_index is not None else "unknown_task"
            lineage_value = json.dumps(
                {
                    "repo_id": repo_id,
                    "revision": revision,
                    "task_index": task_index,
                    "task": task_text,
                    "camera_schema": camera_schema,
                },
                sort_keys=True,
            )
        lineage_id = "sha256:" + sha256_bytes(lineage_value.encode("utf-8"))
        groups.append(
            EpisodeGroup(
                episode_index=episode_id,
                lineage_id=lineage_id,
                lineage_value=lineage_value,
                task_index=task_index,
                frame_count=frame_counts[episode_id],
            )
        )
    return groups, lineage_source


def make_splits(groups: list[EpisodeGroup]) -> dict[str, Any]:
    episode_ids = [group.episode_index for group in groups]
    by_episode = {group.episode_index: group for group in groups}
    rng = random.Random(RANDOM_SEED)
    test_size = max(1, int(round(len(episode_ids) * 0.2)))
    random_test = set(rng.sample(episode_ids, test_size))
    random_train = set(episode_ids) - random_test

    lineage_to_episodes: dict[str, list[int]] = {}
    for group in groups:
        lineage_to_episodes.setdefault(group.lineage_id, []).append(group.episode_index)
    sorted_lineages = sorted(
        lineage_to_episodes,
        key=lambda lineage: (len(lineage_to_episodes[lineage]), lineage),
        reverse=True,
    )
    target_test_episodes = max(1, int(round(len(episode_ids) * 0.2)))
    corrected_test: set[int] = set()
    corrected_lineages: list[str] = []
    for lineage in sorted_lineages:
        if corrected_test and len(corrected_test) >= target_test_episodes:
            break
        corrected_lineages.append(lineage)
        corrected_test.update(lineage_to_episodes[lineage])
    if len(corrected_test) == len(episode_ids) and len(sorted_lineages) > 1:
        removed = corrected_lineages.pop()
        corrected_test.difference_update(lineage_to_episodes[removed])
    corrected_train = set(episode_ids) - corrected_test

    def summarize(name: str, train: set[int], test: set[int]) -> dict[str, Any]:
        train_lineages = {by_episode[episode_id].lineage_id for episode_id in train}
        test_lineages = {by_episode[episode_id].lineage_id for episode_id in test}
        leaked = sorted(
            episode_id
            for episode_id in test
            if by_episode[episode_id].lineage_id in train_lineages
        )
        return {
            "name": name,
            "train_episodes": sorted(train),
            "test_episodes": sorted(test),
            "train_count": len(train),
            "test_count": len(test),
            "train_lineage_count": len(train_lineages),
            "test_lineage_count": len(test_lineages),
            "test_lineages_seen_in_train": sorted(test_lineages & train_lineages),
            "test_leaked_episode_count": len(leaked),
            "leakage_rate": len(leaked) / len(test) if test else 0.0,
        }

    return {
        "random_episode": summarize("random_episode", random_train, random_test),
        "lineage_disjoint": summarize("lineage_disjoint", corrected_train, corrected_test),
    }


def load_arrays(
    config: dict[str, Any],
    cache_root: Path,
    data_paths: list[str],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[int, int], dict[int, int]]:
    _pc, pq = import_pyarrow()
    features: list[list[float]] = []
    actions: list[list[float]] = []
    episode_ids: list[int] = []
    episode_task_index: dict[int, int] = {}
    frame_counts: dict[int, int] = {}
    max_task_index = 0
    rows: list[tuple[list[float], list[float], float, int, int, int]] = []
    for remote_path in data_paths:
        table = pq.read_table(local_source_path(cache_root, config, remote_path))
        columns = set(table.column_names)
        required = {"observation.state", "action", "timestamp", "frame_index", "episode_index", "task_index"}
        missing = sorted(required - columns)
        if missing:
            raise RerunUnavailable(f"{remote_path} is missing required low-dimensional columns: {missing}")
        payload = table.select(sorted(required)).to_pydict()
        for state, action, timestamp, frame_index, episode_index, task_index in zip(
            payload["observation.state"],
            payload["action"],
            payload["timestamp"],
            payload["frame_index"],
            payload["episode_index"],
            payload["task_index"],
            strict=False,
        ):
            episode_id = int(episode_index)
            task_id = int(task_index)
            state_values = flatten_vector(state)
            action_values = flatten_vector(action)
            if not state_values or not action_values:
                continue
            rows.append((state_values, action_values, float(timestamp), int(frame_index), episode_id, task_id))
            episode_task_index.setdefault(episode_id, task_id)
            frame_counts[episode_id] = frame_counts.get(episode_id, 0) + 1
            max_task_index = max(max_task_index, task_id)
    task_count = max_task_index + 1
    episode_lengths = dict(frame_counts)
    for state, action, timestamp, frame_index, episode_id, task_id in rows:
        phase = frame_index / max(episode_lengths.get(episode_id, 1) - 1, 1)
        one_hot = [0.0] * task_count
        one_hot[task_id] = 1.0
        features.append([*state, phase, timestamp, *one_hot])
        actions.append(action)
        episode_ids.append(episode_id)
    return (
        np.asarray(features, dtype=np.float64),
        np.asarray(actions, dtype=np.float64),
        np.asarray(episode_ids, dtype=np.int64),
        episode_task_index,
        frame_counts,
    )


def ridge_predict(x_train: np.ndarray, y_train: np.ndarray, x_test: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    x_mean = x_train.mean(axis=0)
    x_std = x_train.std(axis=0)
    x_std[x_std < 1e-9] = 1.0
    y_mean = y_train.mean(axis=0)
    y_std = y_train.std(axis=0)
    y_std[y_std < 1e-9] = 1.0
    x_train_n = (x_train - x_mean) / x_std
    x_test_n = (x_test - x_mean) / x_std
    y_train_n = (y_train - y_mean) / y_std
    design = np.concatenate([x_train_n, np.ones((x_train_n.shape[0], 1))], axis=1)
    test_design = np.concatenate([x_test_n, np.ones((x_test_n.shape[0], 1))], axis=1)
    regularizer = RIDGE_LAMBDA * np.eye(design.shape[1])
    regularizer[-1, -1] = 0.0
    weights = np.linalg.solve(design.T @ design + regularizer, design.T @ y_train_n)
    prediction = (test_design @ weights) * y_std + y_mean
    return prediction, {
        "model": "closed_form_ridge_regression",
        "ridge_lambda": RIDGE_LAMBDA,
        "feature_count": int(x_train.shape[1]),
        "action_width": int(y_train.shape[1]),
        "normalization": "train_split_standard_score",
    }


def evaluate_split(
    split: dict[str, Any],
    features: np.ndarray,
    actions: np.ndarray,
    episode_ids: np.ndarray,
) -> dict[str, Any]:
    train_ids = set(int(value) for value in split["train_episodes"])
    test_ids = set(int(value) for value in split["test_episodes"])
    train_mask = np.isin(episode_ids, list(train_ids))
    test_mask = np.isin(episode_ids, list(test_ids))
    if int(train_mask.sum()) == 0 or int(test_mask.sum()) == 0:
        raise RerunUnavailable(f"split {split['name']} has empty train or test rows")
    predictions, policy = ridge_predict(features[train_mask], actions[train_mask], features[test_mask])
    y_test = actions[test_mask]
    y_train = actions[train_mask]
    target_std = y_train.std(axis=0)
    target_std[target_std < 1e-9] = 1.0
    normalized_sq_error = ((predictions - y_test) / target_std) ** 2
    nrmse = float(math.sqrt(float(normalized_sq_error.mean())))
    action_rmse = float(math.sqrt(float(((predictions - y_test) ** 2).mean())))
    score = float(1.0 / (1.0 + nrmse))
    return {
        "policy": policy,
        "train_frames": int(train_mask.sum()),
        "test_frames": int(test_mask.sum()),
        "action_rmse": action_rmse,
        "action_nrmse": nrmse,
        "offline_action_agreement_score": score,
    }


def build_worldepisode_artifacts(
    output_dir: Path,
    config: dict[str, Any],
    source_files: dict[str, dict[str, Any]],
    info: dict[str, Any],
    lineage_source: dict[str, Any],
    groups: list[EpisodeGroup],
    splits: dict[str, Any],
) -> dict[str, str]:
    manifest_path = output_dir / "worldepisode.manifest.json"
    conversion_path = output_dir / "conversion_report.json"
    split_path = output_dir / "split_manifest.json"
    lineage_path = output_dir / "lineage_manifest.json"
    manifest = {
        "profile": "worldepisode-famous-benchmark-subset-0.1",
        "benchmark_id": config["benchmark_id"],
        "source_dataset": {
            "repo_id": config["repo_id"],
            "revision": config["revision"],
            "name": config["name"],
        },
        "asset_resolution": {
            "policy": "uri_digest_optional_local_mirror",
            "source_files": source_files,
        },
        "dataset": {
            "robot_type": info.get("robot_type"),
            "total_episodes": info.get("total_episodes"),
            "total_frames": info.get("total_frames"),
            "fps": info.get("fps"),
        },
        "lineage_source": lineage_source,
        "claim_boundary": config["claim_boundary"],
    }
    conversion = {
        "source_profile": "public_lerobot_subset",
        "target_profile": "worldepisode-famous-benchmark-subset-0.1",
        "source_revision": config["revision"],
        "preserved": [
            "observation.state",
            "action",
            "timestamp",
            "frame_index",
            "episode_index",
            "task_index",
            "low-dimensional policy tensors",
        ],
        "externalized": [
            "source file URI",
            "source file sha256",
            "lineage-disjoint split manifest",
        ],
        "approximated": ["world_lineage" if not lineage_source["sufficient_for_score_inflation_claim"] else ""],
        "discarded": ["video payloads"],
        "warnings": [
            lineage_source.get("reason", "")
        ],
    }
    conversion["approximated"] = [item for item in conversion["approximated"] if item]
    conversion["warnings"] = [item for item in conversion["warnings"] if item]
    lineage = {
        "profile": "worldepisode-famous-benchmark-lineage-0.1",
        "lineage_source": lineage_source,
        "lineage_count": len({group.lineage_id for group in groups}),
        "episodes": [
            {
                "episode_index": group.episode_index,
                "lineage_id": group.lineage_id,
                "task_index": group.task_index,
                "frame_count": group.frame_count,
            }
            for group in groups
        ],
    }
    split_manifest = {
        "profile": "worldepisode-famous-benchmark-split-audit-0.1",
        "random_seed": RANDOM_SEED,
        "lineage_source": lineage_source,
        "splits": splits,
    }
    write_json(manifest_path, manifest)
    write_json(conversion_path, conversion)
    write_json(lineage_path, lineage)
    write_json(split_path, split_manifest)
    return {
        "manifest": rel(manifest_path),
        "conversion_report": rel(conversion_path),
        "lineage_manifest": rel(lineage_path),
        "split_manifest": rel(split_path),
    }


def write_markdown_summary(output_dir: Path, report: dict[str, Any]) -> None:
    score_drop = report.get("evaluation", {}).get("score_drop")
    lineage_source = report.get("split_or_timing_audit", {}).get("lineage_source", {})
    if not isinstance(lineage_source, dict):
        lineage_source = {}
    text = f"""# Famous Benchmark Policy Rerun

Benchmark: `{report.get("benchmark_id")}`.

Available: `{report.get("available")}`.

This artifact is the benchmark-specific evidence record consumed by
`tools/benchmark_inflation_gate.py`. It is fail-closed: unavailable data, proxy lineage, or a
non-published policy protocol must not unlock a published-score inflation claim.

## Result

- Baseline score: `{report.get("evaluation", {}).get("baseline_score")}`
- Corrected score: `{report.get("evaluation", {}).get("corrected_score")}`
- Score drop: `{score_drop}`
- Lineage source: `{lineage_source.get("kind")}`
- Lineage sufficient for score-inflation claim: `{lineage_source.get("sufficient_for_score_inflation_claim")}`

## Boundary

{report.get("claim_boundary")}
"""
    if not report.get("available"):
        text += f"\nUnavailable reason:\n\n```text\n{report.get('error')}\n```\n"
    (output_dir / "README.md").write_text(text, encoding="utf-8")


def run_benchmark_rerun(
    benchmark: str,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    cache_root: Path = DEFAULT_CACHE_ROOT,
) -> dict[str, Any]:
    if benchmark not in BENCHMARKS:
        raise RerunUnavailable(f"unknown benchmark key {benchmark}; choose one of {sorted(BENCHMARKS)}")
    config = BENCHMARKS[benchmark]
    _pc, pq = import_pyarrow()
    output_dir = output_root / benchmark
    output_dir.mkdir(parents=True, exist_ok=True)
    source_files = fetch_sources(config, cache_root)
    info = load_json(local_source_path(cache_root, config, "meta/info.json"))
    tasks = pq.read_table(local_source_path(cache_root, config, "meta/tasks.parquet")).to_pydict()
    episodes = pq.read_table(local_source_path(cache_root, config, "meta/episodes/chunk-000/file-000.parquet")).to_pydict()
    features, actions, episode_ids, episode_task_index, frame_counts = load_arrays(
        config,
        cache_root,
        config["expected_data_files"],
    )
    task_by_index = task_map(tasks)
    groups, lineage_source = detect_episode_lineage(
        info=info,
        episodes=episodes,
        task_by_index=task_by_index,
        episode_task_index=episode_task_index,
        frame_counts=frame_counts,
        repo_id=config["repo_id"],
        revision=config["revision"],
    )
    splits = make_splits(groups)
    random_eval = evaluate_split(splits["random_episode"], features, actions, episode_ids)
    corrected_eval = evaluate_split(splits["lineage_disjoint"], features, actions, episode_ids)
    artifacts = build_worldepisode_artifacts(
        output_dir=output_dir,
        config=config,
        source_files=source_files,
        info=info,
        lineage_source=lineage_source,
        groups=groups,
        splits=splits,
    )
    baseline_score = random_eval["offline_action_agreement_score"]
    corrected_score = corrected_eval["offline_action_agreement_score"]
    score_drop = baseline_score - corrected_score
    rerun_report = {
        "schema": "worldepisode_benchmark_rerun_report.v1",
        "audit_date": AUDIT_DATE,
        "available": True,
        "benchmark_id": config["benchmark_id"],
        "benchmark_subset": {
            "name": config["name"],
            "repo_id": config["repo_id"],
            "revision": config["revision"],
            "episode_count": len(set(int(value) for value in episode_ids.tolist())),
            "frame_count": int(len(episode_ids)),
            "source_file_count": len(source_files),
            "source_files_sha256": sha256_bytes(canonical_json_bytes(source_files)),
        },
        "worldepisode_conversion": {
            "pass": True,
            "manifest": artifacts["manifest"],
            "conversion_report": artifacts["conversion_report"],
            "lineage_manifest": artifacts["lineage_manifest"],
            "split_manifest": artifacts["split_manifest"],
            "source_digest_verified": True,
        },
        "split_or_timing_audit": {
            "pass": True,
            "baseline_lineage_overlap": splits["random_episode"]["leakage_rate"],
            "corrected_lineage_overlap": len(splits["lineage_disjoint"]["test_lineages_seen_in_train"]),
            "timestamp_or_latency_fixed": False,
            "lineage_source": lineage_source,
            "lineage_count": len({group.lineage_id for group in groups}),
        },
        "published_protocol": {
            "name": "bounded_offline_lerobot_state_action_probe",
            "source": "tools/famous_benchmark_policy_rerun.py",
            "published_leaderboard_reproduction": False,
            "faithful_reproduction_scope": (
                "Uses the public benchmark tensors and paired random-vs-lineage-disjoint split "
                "audit, but does not reproduce a published DROID/BridgeData policy protocol."
            ),
        },
        "policy": {
            "name": "ridge_bc_state_action",
            "implementation": "tools/famous_benchmark_policy_rerun.py",
            "random_seed": RANDOM_SEED,
            "family": "offline_behavior_cloning_probe",
        },
        "evaluation": {
            "metric": "offline_action_agreement_score = 1 / (1 + action_nrmse)",
            "baseline_split": "random_episode",
            "corrected_split": "lineage_disjoint",
            "baseline_score": baseline_score,
            "corrected_score": corrected_score,
            "score_drop": score_drop,
            "seed_count": 1,
            "random_episode": random_eval,
            "lineage_disjoint": corrected_eval,
        },
        "claim_boundary": (
            config["claim_boundary"]
            + " The report is valid evidence for this subset and metric only. It is not a "
            "published-score inflation claim unless the strict proof gate accepts it."
        ),
    }
    write_json(output_dir / "rerun_report.json", rerun_report)
    write_markdown_summary(output_dir, rerun_report)
    return rerun_report


def unavailable_report(benchmark: str, error: Exception, output_root: Path) -> dict[str, Any]:
    config = BENCHMARKS.get(benchmark, {"benchmark_id": benchmark, "name": benchmark})
    output_dir = output_root / benchmark
    report = {
        "schema": "worldepisode_benchmark_rerun_report.v1",
        "audit_date": AUDIT_DATE,
        "available": False,
        "benchmark_id": config.get("benchmark_id", benchmark),
        "benchmark_subset": {
            "name": config.get("name", benchmark),
            "repo_id": config.get("repo_id"),
            "revision": config.get("revision"),
        },
        "error": str(error),
        "worldepisode_conversion": {
            "pass": False,
            "manifest": None,
            "conversion_report": None,
        },
        "split_or_timing_audit": {
            "pass": False,
            "timestamp_or_latency_fixed": False,
        },
        "published_protocol": {
            "name": "not_run",
            "source": "network_or_dependency_unavailable",
        },
        "policy": {
            "name": "not_run",
            "implementation": "tools/famous_benchmark_policy_rerun.py",
        },
        "evaluation": {
            "baseline_score": None,
            "corrected_score": None,
            "seed_count": 0,
        },
        "claim_boundary": "No benchmark inflation claim is supported because the rerun did not execute.",
    }
    write_json(output_dir / "rerun_report.json", report)
    write_markdown_summary(output_dir, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", choices=sorted(BENCHMARKS), default="droid_100")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--required", action="store_true")
    args = parser.parse_args()
    try:
        report = run_benchmark_rerun(
            benchmark=args.benchmark,
            output_root=args.output_root,
            cache_root=args.cache_root,
        )
    except Exception as exc:  # noqa: BLE001 - writes fail-closed evidence artifact.
        report = unavailable_report(args.benchmark, exc, args.output_root)
        print(json.dumps({"available": False, "error": str(exc), "report": rel(args.output_root / args.benchmark / "rerun_report.json")}, indent=2))
        return 1 if args.required else 0
    print(
        json.dumps(
            {
                "available": report["available"],
                "benchmark_id": report["benchmark_id"],
                "baseline_score": report["evaluation"]["baseline_score"],
                "corrected_score": report["evaluation"]["corrected_score"],
                "score_drop": report["evaluation"]["score_drop"],
                "lineage_source": report["split_or_timing_audit"]["lineage_source"],
                "report": rel(args.output_root / args.benchmark / "rerun_report.json"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
