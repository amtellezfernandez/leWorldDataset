#!/usr/bin/env python3
"""Pinned license evidence for datasets used by the WorldEpisode experiments."""

from __future__ import annotations

import copy
import hashlib
import re
from pathlib import Path
from typing import Any


class DatasetLicenseError(ValueError):
    """Raised when a pinned dataset card disagrees with the license registry."""


DATASET_LICENSE_RECORDS: dict[tuple[str, str], dict[str, Any]] = {
    (
        "armnet/armnetbench_v01_lerobot_so101",
        "2e5e89aee0e7f081078d9d6ab3b279fc4b83ea84",
    ): {
        "license_expression": "Apache-2.0",
        "card_license": "apache-2.0",
        "card_sha256": "a561f1f10cc7792a0b4e0e44df6a1e95ef562c31c9633ed38fdef107975eccfd",
        "attribution": (
            "ArmnetBench v0.1 (LeRobot, single-arm SO-101), Armnet, pinned revision "
            "2e5e89aee0e7f081078d9d6ab3b279fc4b83ea84."
        ),
        "citation_key": "armnetbench_lerobot_so101",
        "upstream_evidence": [],
    },
    (
        "lerobot/svla_so101_pickplace",
        "f641879e22172be7e8161d5e6c1503c2d2feb657",
    ): {
        "license_expression": "Apache-2.0",
        "card_license": "apache-2.0",
        "card_sha256": "74a5ac3cf6de11b315eb4d01b1ce0e6250782fa809183f76b56aaa3d26a63d76",
        "attribution": (
            "svla_so101_pickplace, LeRobot, pinned revision "
            "f641879e22172be7e8161d5e6c1503c2d2feb657."
        ),
        "citation_key": "lerobot_svla_so101_pickplace",
        "upstream_evidence": [],
    },
    (
        "lerobot/pusht",
        "7628202a2180972f291ba1bc6723834921e72c19",
    ): {
        "license_expression": "MIT",
        "card_license": "mit",
        "card_sha256": "246e94b68f204bfcd05bb32e23631c3316b8de6152d7a85e693d4455540ef72f",
        "attribution": (
            "PushT LeRobot conversion, pinned revision "
            "7628202a2180972f291ba1bc6723834921e72c19; PushT data and task from "
            "Diffusion Policy, Columbia Artificial Intelligence and Robotics Lab."
        ),
        "citation_key": "lerobot_pusht",
        "upstream_evidence": [
            {
                "license": "MIT",
                "url": "https://github.com/real-stanford/diffusion_policy/blob/main/LICENSE",
                "copyright": (
                    "Copyright (c) 2023 Columbia Artificial Intelligence and Robotics Lab"
                ),
            }
        ],
    },
    (
        "lerobot/droid_100",
        "87301a2d2e99340e2010c9ef0f1d8e780b08aaf9",
    ): {
        # The immediate LeRobot card says MIT while the DROID paper releases the
        # underlying data under CC-BY-4.0. Preserve both obligations conservatively.
        "license_expression": "MIT AND CC-BY-4.0",
        "card_license": "mit",
        "card_sha256": "153177e2fdbbab7f3bd77137b0411f29e591535c71c9c78adbe34d45a36ea3ab",
        "attribution": (
            "lerobot/droid_100, pinned revision "
            "87301a2d2e99340e2010c9ef0f1d8e780b08aaf9; derived from DROID by "
            "Khazatsky et al."
        ),
        "citation_key": "droid",
        "upstream_evidence": [
            {
                "license": "CC-BY-4.0",
                "url": "https://arxiv.org/abs/2403.12945",
                "evidence": (
                    "The DROID paper states that the full dataset is released under CC-BY 4.0."
                ),
            }
        ],
    },
}


def card_url(repo_id: str, revision: str) -> str:
    return (
        f"https://huggingface.co/datasets/{repo_id}/resolve/{revision}/README.md"
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_card_license(text: str) -> str:
    front_matter = text
    if text.startswith("---"):
        closing = text.find("\n---", 3)
        if closing >= 0:
            front_matter = text[: closing + 4]
    match = re.search(
        r"(?im)^\s*license\s*:\s*['\"]?([A-Za-z0-9.+-]+)",
        front_matter,
    )
    if not match:
        raise DatasetLicenseError("dataset card has no license field")
    return match.group(1).lower()


def license_record(repo_id: str, revision: str) -> dict[str, Any]:
    key = (repo_id, revision)
    if key not in DATASET_LICENSE_RECORDS:
        raise DatasetLicenseError(
            f"no pinned license evidence for {repo_id}@{revision}"
        )
    record = copy.deepcopy(DATASET_LICENSE_RECORDS[key])
    record.update(
        {
            "repo_id": repo_id,
            "revision": revision,
            "card_url": card_url(repo_id, revision),
        }
    )
    return record


def validate_dataset_card(
    path: Path,
    repo_id: str,
    revision: str,
) -> dict[str, Any]:
    record = license_record(repo_id, revision)
    actual_sha256 = sha256_file(path)
    if actual_sha256 != record["card_sha256"]:
        raise DatasetLicenseError(
            f"dataset card digest mismatch for {repo_id}@{revision}: "
            f"expected {record['card_sha256']}, got {actual_sha256}"
        )
    actual_license = parse_card_license(path.read_text(encoding="utf-8"))
    if actual_license != record["card_license"]:
        raise DatasetLicenseError(
            f"dataset card license mismatch for {repo_id}@{revision}: "
            f"expected {record['card_license']}, got {actual_license}"
        )
    return record


def source_license_payload(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "worldepisode_source_license_v1",
        "repo_id": record["repo_id"],
        "revision": record["revision"],
        "license_expression": record["license_expression"],
        "attribution": record["attribution"],
        "evidence": {
            "dataset_card": {
                "url": record["card_url"],
                "sha256": record["card_sha256"],
                "declared_license": record["card_license"],
            },
            "upstream": record["upstream_evidence"],
        },
        "derived_artifact_policy": (
            "Source-derived rows remain under the source license expression. "
            "WorldEpisode-authored manifests, diagnostics, and aggregate reports are CC0-1.0."
        ),
    }
