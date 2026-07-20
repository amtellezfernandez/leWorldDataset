from pathlib import Path

import pytest

from tools.huggingface_policy_archive import (
    PolicyArchiveError,
    build_manifest,
    check_report,
    safe_run_id,
    verify_manifest,
    write_json,
)


def test_archive_manifest_verifies_every_payload_byte(tmp_path: Path) -> None:
    payload = tmp_path / "payload"
    (payload / "checkpoints").mkdir(parents=True)
    (payload / "checkpoints" / "model.safetensors").write_bytes(b"weights")
    (payload / "training.log").write_text("step=20000\n", encoding="utf-8")

    manifest = build_manifest(
        payload,
        run_id="a" * 40,
        repository_commit="b" * 40,
        training_source_commit="c" * 40,
    )

    assert manifest["file_count"] == 2
    assert manifest["total_size_bytes"] == len(b"weights") + len(b"step=20000\n")
    assert verify_manifest(payload, manifest) == []

    (payload / "training.log").write_text("changed\n", encoding="utf-8")
    assert verify_manifest(payload, manifest) == [
        "archived file size changed: training.log"
    ]


def test_archive_run_id_rejects_unsafe_paths() -> None:
    assert safe_run_id("0123456") == "0123456"
    with pytest.raises(PolicyArchiveError, match="hexadecimal"):
        safe_run_id("../escape")
    with pytest.raises(PolicyArchiveError, match="7 to 40"):
        safe_run_id("abc")


def test_archive_report_check_requires_private_verified_commit(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "artifact_archive.json"
    write_json(
        report_path,
        {
            "profile": "worldepisode-policy-artifact-archive-report-0.1",
            "pass": True,
            "upload": {
                "repo_type": "dataset",
                "private": True,
                "commit": "d" * 40,
                "manifest_sha256": "e" * 64,
                "file_count": 20,
                "total_size_bytes": 1000,
            },
            "verification": {
                "pass": True,
                "manifest_sha256": "e" * 64,
                "verified_file_count": 20,
                "verified_total_size_bytes": 1000,
            },
        },
    )

    assert check_report(report_path, required=True) == []

    value = report_path.read_text(encoding="utf-8").replace(
        '"private": true',
        '"private": false',
    )
    report_path.write_text(value, encoding="utf-8")
    assert "policy archive repository is not private" in check_report(
        report_path,
        required=True,
    )
