#!/usr/bin/env python3
"""Plan, verify, and materialize pinned source videos for LeRobot policy splits."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACKAGES_ROOT = (
    ROOT / "docs" / "experiments" / "lerobot_policy_gate" / "physical_splits"
)
DEFAULT_ASSET_MANIFEST = (
    ROOT
    / "docs"
    / "experiments"
    / "lerobot_policy_gate"
    / "front_camera_asset_manifest.json"
)
DEFAULT_MATERIALIZATION_REPORT = (
    ROOT
    / "docs"
    / "experiments"
    / "lerobot_policy_gate"
    / "front_camera_materialization_report.json"
)
CAMERA_KEY = "observation.images.front"
PROFILE = "worldepisode-lerobot-video-asset-plan-0.1"
REPORT_PROFILE = "worldepisode-lerobot-video-materialization-0.1"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_payload(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def descriptor(path: Path) -> dict[str, Any]:
    return {
        "path": relative(path),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def import_pyarrow() -> tuple[Any, Any]:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RuntimeError(
            "pyarrow is required; run with `uv run --with pyarrow ...`"
        ) from exc
    return pa, pq


def import_huggingface() -> tuple[Any, Any]:
    try:
        from huggingface_hub import HfApi, hf_hub_download
    except ImportError as exc:
        raise RuntimeError(
            "huggingface_hub is required; run with `uv run --with huggingface-hub ...`"
        ) from exc
    return HfApi, hf_hub_download


def video_columns(camera_key: str) -> list[str]:
    prefix = f"videos/{camera_key}"
    return [
        f"{prefix}/chunk_index",
        f"{prefix}/file_index",
        f"{prefix}/from_timestamp",
        f"{prefix}/to_timestamp",
    ]


def package_directories(packages_root: Path) -> list[Path]:
    summary = load_json(packages_root / "manifest.json")
    directories = []
    for package in summary["packages"]:
        path = ROOT / package["local_path"]
        if not path.is_dir():
            candidate = packages_root / Path(package["local_path"]).name
            if not candidate.is_dir():
                raise FileNotFoundError(f"missing split package: {path}")
            path = candidate
        directories.append(path)
    return directories


def ordered_episode_map(package_dir: Path) -> list[dict[str, int]]:
    package = load_json(package_dir / "worldepisode_split_package.json")
    mapping = sorted(
        package["episode_filter"]["local_episode_map"],
        key=lambda item: int(item["local_episode_index"]),
    )
    local_indices = [int(item["local_episode_index"]) for item in mapping]
    if local_indices != list(range(len(mapping))):
        raise ValueError(f"{package_dir}: local episode map is not contiguous")
    return [
        {
            "local_episode_index": int(item["local_episode_index"]),
            "source_episode_index": int(item["source_episode_index"]),
        }
        for item in mapping
    ]


def source_identity(package_dirs: list[Path]) -> tuple[str, str]:
    identities = {
        (
            load_json(path / "worldepisode_split_package.json")["source_dataset"]["repo_id"],
            load_json(path / "worldepisode_split_package.json")["source_dataset"]["revision"],
        )
        for path in package_dirs
    }
    if len(identities) != 1:
        raise ValueError(f"split packages do not share one source identity: {sorted(identities)}")
    return next(iter(identities))


def source_root_from_summary(packages_root: Path) -> Path:
    summary = load_json(packages_root / "manifest.json")
    return ROOT / summary["source_cache_root"]


def required_assets(
    source_episode_path: Path,
    package_dirs: list[Path],
    camera_key: str,
) -> tuple[list[str], list[dict[str, Any]]]:
    _pa, pq = import_pyarrow()
    columns = ["episode_index", *video_columns(camera_key)]
    table = pq.read_table(source_episode_path, columns=columns)
    rows = {
        int(row["episode_index"]): row
        for row in table.to_pylist()
    }
    package_requirements = []
    all_paths: set[str] = set()
    for package_dir in package_dirs:
        mapping = ordered_episode_map(package_dir)
        source_episodes = [item["source_episode_index"] for item in mapping]
        missing = sorted(set(source_episodes) - rows.keys())
        if missing:
            raise ValueError(f"{package_dir}: source episode metadata missing {missing[:5]}")
        file_indices = sorted(
            {
                int(rows[episode][f"videos/{camera_key}/file_index"])
                for episode in source_episodes
            }
        )
        chunk_indices = sorted(
            {
                int(rows[episode][f"videos/{camera_key}/chunk_index"])
                for episode in source_episodes
            }
        )
        paths = [
            f"videos/{camera_key}/chunk-{chunk_index:03d}/file-{file_index:03d}.mp4"
            for chunk_index in chunk_indices
            for file_index in file_indices
            if any(
                int(rows[episode][f"videos/{camera_key}/chunk_index"]) == chunk_index
                and int(rows[episode][f"videos/{camera_key}/file_index"]) == file_index
                for episode in source_episodes
            )
        ]
        all_paths.update(paths)
        package_requirements.append(
            {
                "package": relative(package_dir),
                "source_episode_count": len(source_episodes),
                "source_episode_indices_sha256": sha256_payload(source_episodes),
                "video_asset_count": len(paths),
                "video_paths": paths,
            }
        )
    return sorted(all_paths), package_requirements


def build_asset_plan(
    packages_root: Path,
    source_root: Path,
    camera_key: str = CAMERA_KEY,
) -> dict[str, Any]:
    HfApi, _hf_hub_download = import_huggingface()
    package_dirs = package_directories(packages_root)
    repo_id, revision = source_identity(package_dirs)
    source_info_path = source_root / "meta" / "info.json"
    source_episode_path = source_root / "meta" / "episodes" / "chunk-000" / "file-000.parquet"
    source_info = load_json(source_info_path)
    feature = source_info.get("features", {}).get(camera_key)
    if not isinstance(feature, dict) or feature.get("dtype") != "video":
        raise ValueError(f"source feature {camera_key!r} is not a video")

    paths, package_requirements = required_assets(
        source_episode_path,
        package_dirs,
        camera_key,
    )
    folder = f"videos/{camera_key}/chunk-000"
    api_entries = HfApi().list_repo_tree(
        repo_id=repo_id,
        repo_type="dataset",
        revision=revision,
        path_in_repo=folder,
        recursive=False,
        expand=True,
    )
    by_path = {entry.path: entry for entry in api_entries if hasattr(entry, "path")}
    assets = []
    for path in paths:
        entry = by_path.get(path)
        if entry is None or entry.lfs is None:
            raise ValueError(f"pinned Hugging Face tree has no LFS metadata for {path}")
        assets.append(
            {
                "path": path,
                "size_bytes": int(entry.size),
                "sha256": str(entry.lfs.sha256),
            }
        )
    payload = {
        "profile": PROFILE,
        "status": "source_video_assets_pinned",
        "source": {
            "repo_id": repo_id,
            "revision": revision,
            "repo_type": "dataset",
            "info": {
                **descriptor(source_info_path),
                "repo_path": "meta/info.json",
            },
            "episodes": {
                **descriptor(source_episode_path),
                "repo_path": "meta/episodes/chunk-000/file-000.parquet",
            },
        },
        "camera_key": camera_key,
        "video_feature": feature,
        "video_path_template": source_info["video_path"],
        "assets": assets,
        "asset_count": len(assets),
        "total_size_bytes": sum(item["size_bytes"] for item in assets),
        "assets_sha256": sha256_payload(assets),
        "packages": package_requirements,
        "script": relative(Path(__file__)),
        "script_sha256": sha256_file(Path(__file__)),
        "claim_boundary": (
            "This plan pins the source front-camera files required by the selected episodes. "
            "It is a media-integrity and package-compatibility artifact, not a policy result."
        ),
    }
    errors = validate_asset_plan(payload, require_current_script=True)
    if errors:
        raise ValueError("; ".join(errors))
    return payload


def validate_asset_plan(
    payload: dict[str, Any],
    *,
    require_current_script: bool,
) -> list[str]:
    errors = []
    if payload.get("profile") != PROFILE:
        errors.append("unexpected asset-plan profile")
    source = payload.get("source", {})
    if not source.get("repo_id") or len(str(source.get("revision", ""))) != 40:
        errors.append("source repository or pinned revision is missing")
    assets = payload.get("assets", [])
    paths = [item.get("path") for item in assets]
    if paths != sorted(set(paths)):
        errors.append("asset paths are not unique and sorted")
    for item in assets:
        digest = str(item.get("sha256", ""))
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            errors.append(f"invalid SHA-256 for {item.get('path')}")
        if int(item.get("size_bytes", 0)) <= 0:
            errors.append(f"invalid size for {item.get('path')}")
    if payload.get("asset_count") != len(assets):
        errors.append("asset count does not match asset list")
    if payload.get("total_size_bytes") != sum(int(item["size_bytes"]) for item in assets):
        errors.append("total asset bytes do not match asset list")
    if payload.get("assets_sha256") != sha256_payload(assets):
        errors.append("asset-list digest is stale")
    available = set(paths)
    for package in payload.get("packages", []):
        required = package.get("video_paths", [])
        if package.get("video_asset_count") != len(required):
            errors.append(f"{package.get('package')}: video asset count is stale")
        if not set(required).issubset(available):
            errors.append(f"{package.get('package')}: required video asset is not pinned")
    if require_current_script and payload.get("script_sha256") != sha256_file(Path(__file__)):
        errors.append("asset plan was generated by a different script digest")
    return errors


def download_and_verify_assets(
    plan: dict[str, Any],
    source_root: Path,
    *,
    download: bool,
) -> list[dict[str, Any]]:
    _HfApi, hf_hub_download = import_huggingface()
    source = plan["source"]
    verified = []
    for asset in plan["assets"]:
        path = source_root / asset["path"]
        if download and not path.exists():
            downloaded = hf_hub_download(
                repo_id=source["repo_id"],
                repo_type=source["repo_type"],
                revision=source["revision"],
                filename=asset["path"],
                local_dir=source_root,
            )
            path = Path(downloaded)
        if not path.is_file():
            raise FileNotFoundError(f"source video is not materialized: {path}")
        actual_size = path.stat().st_size
        actual_sha256 = sha256_file(path)
        if actual_size != asset["size_bytes"] or actual_sha256 != asset["sha256"]:
            raise ValueError(f"source video digest mismatch: {asset['path']}")
        verified.append(
            {
                **asset,
                "local_path": relative(path),
            }
        )
    return verified


def download_and_verify_source_metadata(
    plan: dict[str, Any],
    source_root: Path,
    *,
    download: bool,
) -> list[dict[str, Any]]:
    _HfApi, hf_hub_download = import_huggingface()
    source = plan["source"]
    verified = []
    for name in ("info", "episodes"):
        expected = source[name]
        repo_path = expected["repo_path"]
        path = source_root / repo_path
        if download and not path.exists():
            downloaded = hf_hub_download(
                repo_id=source["repo_id"],
                repo_type=source["repo_type"],
                revision=source["revision"],
                filename=repo_path,
                local_dir=source_root,
            )
            path = Path(downloaded)
        if not path.is_file():
            raise FileNotFoundError(f"source metadata is not materialized: {path}")
        if (
            path.stat().st_size != expected["size_bytes"]
            or sha256_file(path) != expected["sha256"]
        ):
            raise ValueError(f"source metadata digest mismatch: {repo_path}")
        verified.append(
            {
                "role": name,
                "repo_path": repo_path,
                "local_path": relative(path),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return verified


def replace_or_append_column(pa: Any, table: Any, name: str, values: list[Any], field: Any) -> Any:
    array = pa.array(values, type=field.type)
    if name in table.column_names:
        return table.set_column(table.schema.get_field_index(name), name, array)
    return table.append_column(name, array)


def aggregate_episode_stats(
    source_rows: dict[int, dict[str, Any]],
    source_episodes: list[int],
    feature_name: str,
) -> dict[str, Any]:
    import numpy as np

    stat_names = ("min", "max", "mean", "std", "count", "q01", "q10", "q50", "q90", "q99")
    values = {
        stat: np.asarray(
            [
                source_rows[episode][f"stats/{feature_name}/{stat}"]
                for episode in source_episodes
            ],
            dtype=np.float64,
        )
        for stat in stat_names
    }
    counts = values["count"]
    means = values["mean"]
    while counts.ndim < means.ndim:
        counts = np.expand_dims(counts, axis=-1)
    total_count = counts.sum(axis=0)
    total_mean = (means * counts).sum(axis=0) / total_count
    total_variance = (
        ((values["std"] ** 2) + (means - total_mean) ** 2) * counts
    ).sum(axis=0) / total_count
    aggregate = {
        "min": values["min"].min(axis=0),
        "max": values["max"].max(axis=0),
        "mean": total_mean,
        "std": np.sqrt(total_variance),
        "count": total_count,
    }
    for quantile in ("q01", "q10", "q50", "q90", "q99"):
        aggregate[quantile] = (values[quantile] * counts).sum(axis=0) / total_count
    return {
        stat: np.atleast_1d(value).tolist()
        for stat, value in aggregate.items()
    }


def materialize_package(
    package_dir: Path,
    source_root: Path,
    plan: dict[str, Any],
    source_video_rows: dict[int, dict[str, Any]],
    source_video_schema: Any,
) -> dict[str, Any]:
    pa, pq = import_pyarrow()
    camera_key = plan["camera_key"]
    columns = video_columns(camera_key)
    mapping = ordered_episode_map(package_dir)
    source_episodes = [item["source_episode_index"] for item in mapping]
    package_meta_path = package_dir / "meta" / "episodes" / "chunk-000" / "file-000.parquet"
    table = pq.read_table(package_meta_path)
    local_episodes = [int(value) for value in table["episode_index"].to_pylist()]
    if local_episodes != list(range(len(mapping))):
        raise ValueError(f"{package_dir}: episode metadata is not in local episode order")
    for name in columns:
        values = [source_video_rows[episode][name] for episode in source_episodes]
        table = replace_or_append_column(
            pa,
            table,
            name,
            values,
            source_video_schema.field(name),
        )
    temporary_meta = package_meta_path.with_suffix(".tmp.parquet")
    pq.write_table(table, temporary_meta, compression="zstd")
    os.replace(temporary_meta, package_meta_path)

    info_path = package_dir / "meta" / "info.json"
    info = load_json(info_path)
    info["features"][camera_key] = plan["video_feature"]
    info["video_path"] = plan["video_path_template"]
    write_json(info_path, info)

    stats_path = package_dir / "meta" / "stats.json"
    stats = load_json(stats_path)
    stats[camera_key] = aggregate_episode_stats(
        source_video_rows,
        source_episodes,
        camera_key,
    )
    write_json(stats_path, stats)

    required_paths = next(
        item["video_paths"]
        for item in plan["packages"]
        if Path(item["package"]).name == package_dir.name
    )
    links = []
    for relative_path in required_paths:
        source_path = (source_root / relative_path).resolve()
        target_path = package_dir / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if target_path.is_symlink():
            if target_path.resolve() != source_path:
                target_path.unlink()
        elif target_path.exists():
            raise FileExistsError(f"refusing to replace non-symlink video: {target_path}")
        if not target_path.exists():
            target_path.symlink_to(source_path)
        links.append(
            {
                "path": relative(target_path),
                "source_path": relative(source_path),
            }
        )
    return {
        "package": relative(package_dir),
        "episode_count": len(mapping),
        "video_asset_count": len(required_paths),
        "episodes": descriptor(package_meta_path),
        "info": descriptor(info_path),
        "stats": descriptor(stats_path),
        "links": links,
    }


def materialize(
    packages_root: Path,
    source_root: Path,
    plan: dict[str, Any],
    *,
    download: bool,
) -> dict[str, Any]:
    errors = validate_asset_plan(plan, require_current_script=True)
    if errors:
        raise ValueError("; ".join(errors))
    verified_metadata = download_and_verify_source_metadata(
        plan,
        source_root,
        download=download,
    )
    verified = download_and_verify_assets(plan, source_root, download=download)
    _pa, pq = import_pyarrow()
    camera_key = plan["camera_key"]
    stat_names = ("min", "max", "mean", "std", "count", "q01", "q10", "q50", "q90", "q99")
    columns = [
        "episode_index",
        *video_columns(camera_key),
        *(f"stats/{camera_key}/{stat}" for stat in stat_names),
    ]
    source_episode_path = source_root / "meta" / "episodes" / "chunk-000" / "file-000.parquet"
    source_table = pq.read_table(source_episode_path, columns=columns)
    source_rows = {
        int(row["episode_index"]): row
        for row in source_table.to_pylist()
    }
    packages = [
        materialize_package(
            package_dir,
            source_root,
            plan,
            source_rows,
            source_table.schema,
        )
        for package_dir in package_directories(packages_root)
    ]
    return {
        "profile": REPORT_PROFILE,
        "status": "front_camera_materialized",
        "pass": True,
        "asset_plan": {
            "path": relative(DEFAULT_ASSET_MANIFEST),
            "sha256": sha256_payload(plan),
        },
        "source": plan["source"],
        "camera_key": camera_key,
        "verified_source_metadata": verified_metadata,
        "verified_assets": verified,
        "verified_asset_count": len(verified),
        "verified_total_size_bytes": sum(item["size_bytes"] for item in verified),
        "packages": packages,
        "script": relative(Path(__file__)),
        "script_sha256": sha256_file(Path(__file__)),
        "claim_boundary": (
            "The compact split packages now expose one source camera with digest-verified source "
            "media. This establishes loader and training-input compatibility only; it does not "
            "establish policy quality or rollout impact."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--plan", action="store_true")
    action.add_argument("--materialize", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--packages-root", type=Path, default=DEFAULT_PACKAGES_ROOT)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--asset-manifest", type=Path, default=DEFAULT_ASSET_MANIFEST)
    parser.add_argument(
        "--materialization-report",
        type=Path,
        default=DEFAULT_MATERIALIZATION_REPORT,
    )
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    if args.check:
        if not args.asset_manifest.exists():
            errors = [f"missing asset plan: {args.asset_manifest}"]
        else:
            errors = validate_asset_plan(
                load_json(args.asset_manifest),
                require_current_script=True,
            )
        print(json.dumps({"valid": not errors, "errors": errors}, indent=2))
        return 1 if args.strict and errors else 0

    source_root = args.source_root or source_root_from_summary(args.packages_root)
    if args.plan:
        payload = build_asset_plan(args.packages_root, source_root)
        write_json(args.asset_manifest, payload)
        print(
            json.dumps(
                {
                    "status": payload["status"],
                    "asset_count": payload["asset_count"],
                    "total_size_bytes": payload["total_size_bytes"],
                },
                indent=2,
            )
        )
        return 0

    plan = load_json(args.asset_manifest)
    report = materialize(
        args.packages_root,
        source_root,
        plan,
        download=args.download,
    )
    write_json(args.materialization_report, report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "verified_asset_count": report["verified_asset_count"],
                "package_count": len(report["packages"]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
