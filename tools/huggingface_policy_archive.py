#!/usr/bin/env python3
"""Archive and verify full policy-run artifacts in a private Hugging Face dataset."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT_DIR = (
    ROOT / "docs" / "experiments" / "lerobot_policy_full_training"
)
OUTPUT_ROOT = ROOT / "outputs" / "lerobot_policy_full_training"
DEFAULT_REPO_ID = "amtellezfernandez/worldepisode-experiment-recovery"
DEFAULT_STAGING = ROOT / "outputs" / "lerobot_policy_archive_staging"
DEFAULT_VERIFY_ROOT = ROOT / "outputs" / "lerobot_policy_archive_verification"
DEFAULT_REPORT = EXPERIMENT_DIR / "artifact_archive.json"
MANIFEST_PROFILE = "worldepisode-policy-artifact-archive-manifest-0.1"
REPORT_PROFILE = "worldepisode-policy-artifact-archive-report-0.1"
PAYLOAD_PATHS = (
    "docs/experiments/lerobot_policy_full_training/README.md",
    "docs/experiments/lerobot_policy_full_training/protocol.json",
    "docs/experiments/lerobot_policy_full_training/jobs.json",
    "docs/experiments/lerobot_policy_full_training/evaluation_reference.json",
    "docs/experiments/lerobot_policy_full_training/offline_policy_report.json",
    "docs/experiments/lerobot_policy_full_training/run_jobs.sh",
    "docs/experiments/lerobot_policy_full_training/jobs",
    "outputs/lerobot_policy_full_training",
    "tools/lerobot_policy_full_training.py",
)


class PolicyArchiveError(RuntimeError):
    """Raised when a recovery archive is incomplete or unverifiable."""


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PolicyArchiveError(f"missing required file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PolicyArchiveError(f"invalid JSON in {path}: {exc}") from exc


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def sha256_payload(payload: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_output(*args: str) -> str | None:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        return None
    value = completed.stdout.strip()
    return value or None


def safe_run_id(value: str) -> str:
    if not value or any(character not in "0123456789abcdef" for character in value):
        raise PolicyArchiveError("run id must be a lowercase hexadecimal Git revision")
    if len(value) < 7 or len(value) > 40:
        raise PolicyArchiveError("run id must contain 7 to 40 hexadecimal characters")
    return value


def archive_prefix(run_id: str) -> str:
    return f"policy_runs/{safe_run_id(run_id)}"


def validate_completed_experiment() -> dict[str, Any]:
    report_path = EXPERIMENT_DIR / "offline_policy_report.json"
    report = load_json(report_path)
    if report.get("profile") != "worldepisode-lerobot-offline-policy-report-0.1":
        raise PolicyArchiveError("unexpected offline policy report profile")
    if report.get("pass") is not True:
        raise PolicyArchiveError("offline policy report does not pass")
    if report.get("completed_job_count") != report.get("required_job_count"):
        raise PolicyArchiveError("offline policy job grid is incomplete")
    if report.get("required_job_count") != 20:
        raise PolicyArchiveError("offline policy report does not contain 20 jobs")
    return report


def iter_source_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if not path.is_dir():
        raise PolicyArchiveError(f"missing archive payload: {path}")
    return [
        child
        for child in sorted(path.rglob("*"))
        if child.is_file() and not child.is_symlink()
    ]


def hardlink_payload(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)


def stage_payload(staging: Path, prefix: str) -> Path:
    payload_root = staging / prefix / "payload" / "repository"
    for relative_path in PAYLOAD_PATHS:
        source = ROOT / relative_path
        for source_file in iter_source_files(source):
            destination = payload_root / source_file.relative_to(ROOT)
            hardlink_payload(source_file, destination)
    return payload_root


def create_git_bundle(destination: Path) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        ["git", "bundle", "create", str(destination), "--all"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise PolicyArchiveError(
            f"git bundle creation failed: {completed.stderr.strip()}"
        )
    verify = subprocess.run(
        ["git", "bundle", "verify", str(destination)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if verify.returncode:
        raise PolicyArchiveError(
            f"git bundle verification failed: {verify.stderr.strip()}"
        )
    return {
        "path": str(destination),
        "size_bytes": destination.stat().st_size,
        "sha256": sha256_file(destination),
        "verified": True,
    }


def manifest_entries(payload_root: Path) -> list[dict[str, Any]]:
    entries = []
    for path in sorted(payload_root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        entries.append(
            {
                "path": str(path.relative_to(payload_root)),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    if not entries:
        raise PolicyArchiveError("archive payload is empty")
    return entries


def build_manifest(
    payload_root: Path,
    *,
    run_id: str,
    repository_commit: str,
    training_source_commit: str,
) -> dict[str, Any]:
    entries = manifest_entries(payload_root)
    return {
        "profile": MANIFEST_PROFILE,
        "run_id": safe_run_id(run_id),
        "repository_commit": repository_commit,
        "training_source_commit": training_source_commit,
        "file_count": len(entries),
        "total_size_bytes": sum(item["size_bytes"] for item in entries),
        "entries_sha256": sha256_payload(entries),
        "entries": entries,
    }


def verify_manifest(payload_root: Path, manifest: dict[str, Any]) -> list[str]:
    errors = []
    if manifest.get("profile") != MANIFEST_PROFILE:
        errors.append("unexpected archive manifest profile")
        return errors
    expected_entries = manifest.get("entries")
    if not isinstance(expected_entries, list):
        errors.append("archive manifest entries are missing")
        return errors
    if manifest.get("file_count") != len(expected_entries):
        errors.append("archive manifest file count is stale")
    if manifest.get("total_size_bytes") != sum(
        int(item.get("size_bytes", -1)) for item in expected_entries
    ):
        errors.append("archive manifest byte count is stale")
    if manifest.get("entries_sha256") != sha256_payload(expected_entries):
        errors.append("archive manifest entry digest is stale")
    expected_paths = set()
    for entry in expected_entries:
        relative_path = entry.get("path")
        if (
            not isinstance(relative_path, str)
            or not relative_path
            or Path(relative_path).is_absolute()
            or ".." in Path(relative_path).parts
        ):
            errors.append(f"unsafe archive path: {relative_path!r}")
            continue
        expected_paths.add(relative_path)
        path = payload_root / relative_path
        if not path.is_file():
            errors.append(f"missing archived file: {relative_path}")
            continue
        if path.stat().st_size != entry.get("size_bytes"):
            errors.append(f"archived file size changed: {relative_path}")
        elif sha256_file(path) != entry.get("sha256"):
            errors.append(f"archived file digest changed: {relative_path}")
    actual_paths = {
        str(path.relative_to(payload_root))
        for path in payload_root.rglob("*")
        if path.is_file() and not path.is_symlink()
    }
    unexpected = sorted(actual_paths - expected_paths)
    if unexpected:
        errors.append(f"unexpected archived files: {unexpected}")
    return errors


def prepare_staging(
    staging: Path,
    *,
    run_id: str,
    force: bool,
) -> tuple[Path, Path, dict[str, Any]]:
    report = validate_completed_experiment()
    run_id = safe_run_id(run_id)
    if staging.exists():
        if not force:
            raise PolicyArchiveError(
                f"staging directory already exists: {staging}; reuse it for upload or pass --force"
            )
        shutil.rmtree(staging)
    prefix = archive_prefix(run_id)
    payload_root = stage_payload(staging, prefix)
    bundle_path = (
        payload_root / "recovery" / f"worldepisode-{run_id}.bundle"
    )
    create_git_bundle(bundle_path)
    training_source_commit = report.get("protocol", {}).get(
        "execution_source_revision"
    )
    if not isinstance(training_source_commit, str):
        raise PolicyArchiveError(
            "offline policy report has no training source revision"
        )
    repository_commit = git_output("rev-parse", "HEAD")
    if repository_commit is None:
        raise PolicyArchiveError("cannot determine repository commit")
    manifest = build_manifest(
        payload_root,
        run_id=run_id,
        repository_commit=repository_commit,
        training_source_commit=training_source_commit,
    )
    manifest_path = staging / prefix / "archive_manifest.json"
    write_json(manifest_path, manifest)
    errors = verify_manifest(payload_root, manifest)
    if errors:
        raise PolicyArchiveError("; ".join(errors))
    return payload_root, manifest_path, manifest


def upload_staging(
    staging: Path,
    manifest_path: Path,
    *,
    repo_id: str,
    run_id: str,
) -> dict[str, Any]:
    try:
        import huggingface_hub
        from huggingface_hub import HfApi
    except ModuleNotFoundError as exc:
        raise PolicyArchiveError(
            "huggingface_hub is required for policy artifact upload"
        ) from exc
    manifest = load_json(manifest_path)
    prefix = archive_prefix(run_id)
    payload_root = staging / prefix / "payload" / "repository"
    errors = verify_manifest(payload_root, manifest)
    if errors:
        raise PolicyArchiveError("; ".join(errors))
    api = HfApi()
    api.create_repo(
        repo_id=repo_id,
        repo_type="dataset",
        private=True,
        exist_ok=True,
    )
    api.upload_large_folder(
        repo_id=repo_id,
        folder_path=staging,
        repo_type="dataset",
        private=True,
    )
    info = api.repo_info(repo_id=repo_id, repo_type="dataset")
    if not info.sha:
        raise PolicyArchiveError("Hugging Face did not return an immutable commit")
    return {
        "huggingface_hub_version": huggingface_hub.__version__,
        "repo_id": repo_id,
        "repo_type": "dataset",
        "private": bool(info.private),
        "commit": info.sha,
        "prefix": prefix,
        "manifest_path": f"{prefix}/archive_manifest.json",
        "manifest_sha256": sha256_file(manifest_path),
        "file_count": manifest["file_count"],
        "total_size_bytes": manifest["total_size_bytes"],
    }


def verify_download(
    *,
    repo_id: str,
    commit: str,
    prefix: str,
    verify_root: Path,
    expected_manifest_sha256: str,
    force: bool,
) -> dict[str, Any]:
    try:
        import huggingface_hub
        from huggingface_hub import snapshot_download
    except ModuleNotFoundError as exc:
        raise PolicyArchiveError(
            "huggingface_hub is required for policy artifact verification"
        ) from exc
    if verify_root.exists() and force:
        shutil.rmtree(verify_root)
    verify_root.mkdir(parents=True, exist_ok=True)
    downloaded = Path(
        snapshot_download(
            repo_id=repo_id,
            repo_type="dataset",
            revision=commit,
            allow_patterns=f"{prefix}/**",
            local_dir=verify_root,
            force_download=force,
        )
    )
    manifest_path = downloaded / prefix / "archive_manifest.json"
    if sha256_file(manifest_path) != expected_manifest_sha256:
        raise PolicyArchiveError("downloaded archive manifest digest changed")
    manifest = load_json(manifest_path)
    payload_root = downloaded / prefix / "payload" / "repository"
    errors = verify_manifest(payload_root, manifest)
    bundle_entry = next(
        (
            item
            for item in manifest["entries"]
            if item["path"].startswith("recovery/")
            and item["path"].endswith(".bundle")
        ),
        None,
    )
    if bundle_entry is None:
        errors.append("downloaded archive has no Git bundle")
    else:
        bundle_path = payload_root / bundle_entry["path"]
        completed = subprocess.run(
            ["git", "bundle", "verify", str(bundle_path)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode:
            errors.append("downloaded Git bundle did not verify")
    return {
        "verified_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "huggingface_hub_version": huggingface_hub.__version__,
        "download_root": str(downloaded),
        "manifest_sha256": sha256_file(manifest_path),
        "verified_file_count": manifest["file_count"],
        "verified_total_size_bytes": manifest["total_size_bytes"],
        "git_bundle_verified": bundle_entry is not None and not any(
            "Git bundle" in error for error in errors
        ),
        "errors": errors,
        "pass": not errors,
    }


def delete_source_payload(report: dict[str, Any]) -> None:
    verification = report.get("verification", {})
    if verification.get("pass") is not True:
        raise PolicyArchiveError(
            "source deletion is forbidden before full download verification"
        )
    if not OUTPUT_ROOT.is_dir():
        return
    shutil.rmtree(OUTPUT_ROOT)


def check_report(report_path: Path, *, required: bool) -> list[str]:
    if not report_path.is_file():
        return ["required policy archive report is missing"] if required else []
    report = load_json(report_path)
    errors = []
    if report.get("profile") != REPORT_PROFILE:
        errors.append("unexpected policy archive report profile")
    upload = report.get("upload", {})
    if upload.get("repo_type") != "dataset":
        errors.append("policy archive is not stored in a dataset repository")
    if upload.get("private") is not True:
        errors.append("policy archive repository is not private")
    if not upload.get("commit"):
        errors.append("policy archive has no immutable Hugging Face commit")
    verification = report.get("verification", {})
    if verification.get("pass") is not True:
        errors.append("policy archive download verification did not pass")
    if verification.get("manifest_sha256") != upload.get("manifest_sha256"):
        errors.append("policy archive verification used a different manifest")
    if verification.get("verified_file_count") != upload.get("file_count"):
        errors.append("policy archive verified file count changed")
    if verification.get("verified_total_size_bytes") != upload.get(
        "total_size_bytes"
    ):
        errors.append("policy archive verified byte count changed")
    if required and report.get("pass") is not True:
        errors.append("required policy archive report does not pass")
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-id", default=DEFAULT_REPO_ID)
    parser.add_argument("--run-id")
    parser.add_argument("--staging", type=Path, default=DEFAULT_STAGING)
    parser.add_argument("--verify-root", type=Path, default=DEFAULT_VERIFY_ROOT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--stage", action="store_true")
    parser.add_argument("--upload", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--delete-source", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--required", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            errors = check_report(args.report, required=args.required)
            print(json.dumps({"valid": not errors, "errors": errors}, indent=2))
            return 1 if errors else 0
        if not any((args.stage, args.upload, args.verify, args.delete_source)):
            raise PolicyArchiveError(
                "select --stage, --upload, --verify, or --delete-source"
            )
        run_id = args.run_id or git_output("rev-parse", "HEAD")
        if run_id is None:
            raise PolicyArchiveError("cannot determine archive run id")
        run_id = safe_run_id(run_id)
        prefix = archive_prefix(run_id)
        manifest_path = args.staging / prefix / "archive_manifest.json"
        report: dict[str, Any] = (
            load_json(args.report) if args.report.is_file() else {}
        )
        if args.stage:
            _payload, manifest_path, manifest = prepare_staging(
                args.staging,
                run_id=run_id,
                force=args.force,
            )
            report = {
                "profile": REPORT_PROFILE,
                "status": "staged",
                "pass": False,
                "run_id": run_id,
                "staging": {
                    "path": str(args.staging),
                    "manifest_path": str(manifest_path),
                    "manifest_sha256": sha256_file(manifest_path),
                    "file_count": manifest["file_count"],
                    "total_size_bytes": manifest["total_size_bytes"],
                },
            }
            write_json(args.report, report)
        if args.upload:
            upload = upload_staging(
                args.staging,
                manifest_path,
                repo_id=args.repo_id,
                run_id=run_id,
            )
            report.update(
                {
                    "profile": REPORT_PROFILE,
                    "status": "uploaded_pending_download_verification",
                    "pass": False,
                    "run_id": run_id,
                    "upload": upload,
                }
            )
            write_json(args.report, report)
        if args.verify:
            upload = report.get("upload")
            if not isinstance(upload, dict):
                raise PolicyArchiveError(
                    "upload record is required before verification"
                )
            verification = verify_download(
                repo_id=upload["repo_id"],
                commit=upload["commit"],
                prefix=upload["prefix"],
                verify_root=args.verify_root,
                expected_manifest_sha256=upload["manifest_sha256"],
                force=args.force,
            )
            report["verification"] = verification
            report["status"] = (
                "verified_recoverable"
                if verification["pass"]
                else "verification_failed"
            )
            report["pass"] = verification["pass"]
            write_json(args.report, report)
            if not verification["pass"]:
                raise PolicyArchiveError("; ".join(verification["errors"]))
        if args.delete_source:
            delete_source_payload(report)
            report["source_payload_deleted_after_verification"] = True
            write_json(args.report, report)
        print(
            json.dumps(
                {
                    "status": report.get("status"),
                    "pass": report.get("pass"),
                    "run_id": run_id,
                },
                indent=2,
            )
        )
        return 0
    except (PolicyArchiveError, OSError, ValueError) as exc:
        print(f"policy archive error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
