import json

from tools.lerobot_policy_compatibility_audit import (
    DEFAULT_DATASET_ROOT,
    DEFAULT_REPORT,
    EXPECTED_MODALITY_ERROR,
    validate_existing_report,
)
from tools.lerobot_policy_video_materialization import (
    PROFILE as VIDEO_PROFILE,
    sha256_payload,
    validate_asset_plan,
)


def test_committed_policy_compatibility_report_matches_current_package() -> None:
    assert validate_existing_report(DEFAULT_REPORT, DEFAULT_DATASET_ROOT) == []

    report = json.loads(DEFAULT_REPORT.read_text(encoding="utf-8"))
    assert report["status"] == "blocked_missing_required_observation_modality"
    assert report["all_policy_probes_completed_training_step"] is False
    assert report["all_policy_probes_blocked_for_expected_reason"] is True
    assert {probe["policy"] for probe in report["policy_probes"]} == {"act", "diffusion"}
    assert all(
        probe["terminal_error"] == f"ValueError: {EXPECTED_MODALITY_ERROR}"
        for probe in report["policy_probes"]
    )


def test_video_asset_plan_validation_fails_closed() -> None:
    assets = [
        {
            "path": "videos/observation.images.front/chunk-000/file-013.mp4",
            "size_bytes": 123,
            "sha256": "a" * 64,
        }
    ]
    payload = {
        "profile": VIDEO_PROFILE,
        "source": {
            "repo_id": "example/source",
            "revision": "b" * 40,
        },
        "assets": assets,
        "asset_count": 1,
        "total_size_bytes": 123,
        "assets_sha256": sha256_payload(assets),
        "packages": [
            {
                "package": "example",
                "video_asset_count": 1,
                "video_paths": [assets[0]["path"]],
            }
        ],
    }
    assert validate_asset_plan(payload, require_current_script=False) == []

    payload["packages"][0]["video_paths"].append(
        "videos/observation.images.front/chunk-000/file-999.mp4"
    )
    errors = validate_asset_plan(payload, require_current_script=False)
    assert "example: video asset count is stale" in errors
    assert "example: required video asset is not pinned" in errors
