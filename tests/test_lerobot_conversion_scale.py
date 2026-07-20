from __future__ import annotations

import json
from pathlib import Path

from tools.lerobot_conversion_scale import (
    DATASETS,
    README_PATH,
    REPORT_PATH,
    SCHEMA,
    read_json,
    render_markdown,
    validate_report,
)
from tools.lerobot_worldepisode_roundtrip import display_path


def test_conversion_scale_report_is_current_and_valid() -> None:
    report = read_json(REPORT_PATH)

    assert report["schema"] == SCHEMA
    assert validate_report(report) == []
    assert report["validation"] == {"passed": True, "errors": []}
    assert REPORT_PATH.read_text(encoding="utf-8") == (
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    assert README_PATH.read_text(encoding="utf-8") == render_markdown(report)


def test_conversion_scale_covers_complete_multi_camera_subsets() -> None:
    report = read_json(REPORT_PATH)

    assert {item["dataset_id"] for item in report["datasets"]} == set(DATASETS)
    assert report["aggregate"]["dataset_count"] == 3
    assert report["aggregate"]["multi_camera_dataset_count"] >= 2
    assert report["aggregate"]["episode_count"] == sum(
        item["expected_episode_count"] for item in DATASETS.values()
    )
    for dataset in report["datasets"]:
        assert dataset["source_subset"]["complete_source_file"] is True
        assert dataset["modality"]["source_video_payload_downloaded"] is False
        assert dataset["conversion"]["discarded_fields"] == []
        assert max(dataset["conversion"]["max_errors"].values()) == 0.0


def test_roundtrip_artifact_paths_support_temporary_directories() -> None:
    outside_repo = Path("/tmp/worldepisode-scale/episode_000000")

    assert display_path(outside_repo) == str(outside_repo)
