#!/usr/bin/env python3
"""Generate the pinned Hugging Face recovery pointer from verified remote evidence."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VERIFICATION_PATH = (
    ROOT
    / "docs"
    / "experiments"
    / "huggingface_recovery"
    / "recovery_verification.json"
)
ASSET_PLAN_PATH = (
    ROOT
    / "docs"
    / "experiments"
    / "lerobot_policy_gate"
    / "front_camera_asset_manifest.json"
)
JSON_PATH = ROOT / "docs" / "huggingface-recovery.json"
MARKDOWN_PATH = ROOT / "docs" / "huggingface-recovery.md"
SCRIPT_PATH = "tools/huggingface_recovery_pointer.py"
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class RecoveryPointerError(ValueError):
    """Raised when remote recovery verification evidence is incomplete."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RecoveryPointerError(f"missing recovery input: {path.relative_to(ROOT)}") from exc
    except json.JSONDecodeError as exc:
        raise RecoveryPointerError(f"invalid JSON in {path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RecoveryPointerError(f"expected JSON object in {path.relative_to(ROOT)}")
    return payload


def validate_verification(report: dict[str, Any]) -> None:
    errors: list[str] = []
    if report.get("schema") != "worldepisode_recovery_verification_v1":
        errors.append("unexpected verification schema")
    if report.get("passed") is not True or report.get("errors") != []:
        errors.append("remote verification did not pass without errors")
    if report.get("bundle_fsck_passed") is not True:
        errors.append("Git bundle fsck did not pass")
    if not COMMIT_RE.fullmatch(str(report.get("bundle_head", ""))):
        errors.append("bundle head is not a full Git commit")
    if not COMMIT_RE.fullmatch(str(report.get("huggingface_commit", ""))):
        errors.append("Hugging Face revision is not an immutable commit")
    if not SHA256_RE.fullmatch(str(report.get("manifest_sha256", ""))):
        errors.append("manifest digest is not SHA-256")

    files = report.get("files")
    if not isinstance(files, list):
        errors.append("verification files must be a list")
        files = []
    paths = [item.get("path") for item in files if isinstance(item, dict)]
    if paths != sorted(set(paths)):
        errors.append("verified file paths are not unique and sorted")
    for item in files:
        if not isinstance(item, dict):
            errors.append("verified file descriptor is not an object")
            continue
        if not isinstance(item.get("size_bytes"), int) or item["size_bytes"] <= 0:
            errors.append(f"invalid byte count for {item.get('path')}")
        if not SHA256_RE.fullmatch(str(item.get("sha256", ""))):
            errors.append(f"invalid SHA-256 for {item.get('path')}")
    if report.get("verified_file_count") != len(files):
        errors.append("verified file count is stale")
    if report.get("verified_bytes") != sum(
        int(item.get("size_bytes", 0)) for item in files if isinstance(item, dict)
    ):
        errors.append("verified byte total is stale")
    expected_snapshot = f"snapshots/{str(report.get('bundle_head', ''))[:7]}"
    if report.get("snapshot_path") != expected_snapshot:
        errors.append("snapshot path does not match the verified Git commit")
    if errors:
        raise RecoveryPointerError("; ".join(errors))


def previous_snapshots(
    current_pointer: dict[str, Any] | None,
    new_snapshot: dict[str, Any],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if current_pointer:
        records.extend(current_pointer.get("previous_snapshots", []))
        current = current_pointer.get("snapshot")
        if isinstance(current, dict):
            records.append(current)
    by_commit = {
        str(item["huggingface_commit"]): {
            "git_commit": item["git_commit"],
            "path": item["path"],
            "huggingface_commit": item["huggingface_commit"],
            "manifest_sha256": item["manifest_sha256"],
        }
        for item in records
        if isinstance(item, dict)
        and item.get("huggingface_commit") != new_snapshot["huggingface_commit"]
        and all(
            key in item
            for key in ("git_commit", "path", "huggingface_commit", "manifest_sha256")
        )
    }
    return sorted(by_commit.values(), key=lambda item: item["path"])


def build_pointer(
    verification: dict[str, Any],
    asset_plan: dict[str, Any],
    current_pointer: dict[str, Any] | None,
) -> dict[str, Any]:
    validate_verification(verification)
    snapshot = {
        "git_commit": verification["bundle_head"],
        "path": verification["snapshot_path"],
        "huggingface_commit": verification["huggingface_commit"],
        "manifest_sha256": verification["manifest_sha256"],
    }
    source = asset_plan["source"]
    return {
        "schema_version": 1,
        "generated_by": {
            "script": SCRIPT_PATH,
            "verification_report": str(VERIFICATION_PATH.relative_to(ROOT)),
        },
        "repository": {
            "id": verification["repository"],
            "type": "dataset",
            "private": True,
        },
        "snapshot": snapshot,
        "verification": {
            "method": (
                "forced snapshot_download at the pinned Hugging Face commit followed by "
                "size and SHA-256 comparison, bundle clone, and git fsck"
            ),
            "passed": verification["passed"],
            "verified_file_count": verification["verified_file_count"],
            "verified_bytes": verification["verified_bytes"],
        },
        "source_media_recovery": {
            "mirrored": False,
            "repository": source["repo_id"],
            "revision": source["revision"],
            "asset_manifest": "policy_reports/front_camera_asset_manifest.json",
            "asset_count": asset_plan["asset_count"],
            "source_bytes": asset_plan["total_size_bytes"],
            "verification": "per-file LFS SHA-256",
        },
        "previous_snapshots": previous_snapshots(current_pointer, snapshot),
        "files": verification["files"],
    }


def render_markdown(pointer: dict[str, Any]) -> str:
    repository = pointer["repository"]["id"]
    snapshot = pointer["snapshot"]
    verification = pointer["verification"]
    source = pointer["source_media_recovery"]
    categories = Counter(
        item["path"].split("/", 1)[0] if "/" in item["path"] else "root"
        for item in pointer["files"]
    )
    category_lines = "\n".join(
        f"- `{name}`: {count} verified payload files"
        for name, count in sorted(categories.items())
    )
    bundle_path = next(
        item["path"] for item in pointer["files"] if item["path"].endswith(".bundle")
    )
    previous = pointer["previous_snapshots"]
    previous_text = (
        "\n".join(
            f"- `{item['path'].split('/')[-1]}` at Hugging Face commit "
            f"`{item['huggingface_commit']}`"
            for item in previous
        )
        if previous
        else "- None"
    )
    short = snapshot["git_commit"][:7]
    return f"""# Hugging Face Recovery

The private dataset repository
[`{repository}`](https://huggingface.co/datasets/{repository})
stores immutable recovery snapshots that are too large, generated, or operationally noisy for Git.
This page and its machine-readable companion are generated from a forced-download verification
report; counts and digests are not maintained manually.

Snapshot `{short}` is pinned to Hugging Face commit
`{snapshot["huggingface_commit"]}`. All {verification["verified_file_count"]} payload files
({verification["verified_bytes"]} bytes) passed size and SHA-256 verification, and the recovered
Git bundle cloned at the expected source commit and passed `git fsck --full`.

{category_lines}

Restore the snapshot with an authenticated Hugging Face account:

```bash
hf download {repository} \\
  --repo-type dataset \\
  --revision {snapshot["huggingface_commit"]} \\
  --include "{snapshot["path"]}/**" \\
  --local-dir worldepisode-recovery
```

Verify each restored file against `{snapshot["path"]}/artifact_manifest.json`. To recover the
repository independently of GitHub:

```bash
git clone \\
  worldepisode-recovery/{snapshot["path"]}/{bundle_path} \\
  leWorldDataset
```

The source videos are not duplicated in the private recovery repository. The mirrored asset plan
pins {source["asset_count"]} files ({source["source_bytes"]} source bytes) from
`{source["repository"]}@{source["revision"]}` with per-file LFS SHA-256 digests.

Earlier immutable snapshots:

{previous_text}

Do not delete a local-only artifact until its Hugging Face commit is pinned here and a separate
download verifies every recorded SHA-256 digest.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    verification = load_json(VERIFICATION_PATH)
    asset_plan = load_json(ASSET_PLAN_PATH)
    current_pointer = load_json(JSON_PATH) if JSON_PATH.is_file() else None
    pointer = build_pointer(verification, asset_plan, current_pointer)
    rendered_json = json.dumps(pointer, indent=2, sort_keys=True) + "\n"
    rendered_markdown = render_markdown(pointer)
    if args.check:
        current = (
            JSON_PATH.is_file()
            and MARKDOWN_PATH.is_file()
            and JSON_PATH.read_text(encoding="utf-8") == rendered_json
            and MARKDOWN_PATH.read_text(encoding="utf-8") == rendered_markdown
        )
        print(f"Hugging Face recovery pointer: {'current' if current else 'stale'}")
        return 0 if current else 1
    JSON_PATH.write_text(rendered_json, encoding="utf-8")
    MARKDOWN_PATH.write_text(rendered_markdown, encoding="utf-8")
    print(
        json.dumps(
            {
                "snapshot": pointer["snapshot"],
                "verification": pointer["verification"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
