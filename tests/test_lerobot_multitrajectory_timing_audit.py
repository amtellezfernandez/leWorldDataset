from __future__ import annotations

import json
import math

from tools.lerobot_multitrajectory_timing_audit import (
    README_PATH,
    REPORT_PATH,
    SCHEMA,
    read_json,
    render_markdown,
    validate_report,
)


def test_multitrajectory_timing_report_is_current_and_valid() -> None:
    report = read_json(REPORT_PATH)

    assert report["schema"] == SCHEMA
    assert validate_report(report) == []
    assert report["validation"] == {"passed": True, "errors": []}
    assert REPORT_PATH.read_text(encoding="utf-8") == (
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    assert README_PATH.read_text(encoding="utf-8") == render_markdown(report)


def test_timing_protocol_is_held_out_and_scoped() -> None:
    report = read_json(REPORT_PATH)
    calibration = report["calibration"]
    evaluation = report["evaluation"]
    improvement = evaluation["paired_episode_improvement"]

    assert report["source"]["source_episode_overlap_count"] == 0
    assert calibration["episode_count"] >= 20
    assert evaluation["episode_count"] >= 20
    assert evaluation["task_count"] >= 2
    assert improvement["ci_low"] > 0
    assert improvement["improved_episode_count"] == evaluation["episode_count"]
    assert all(row["rmse_improvement_mean"] > 0 for row in evaluation["by_task"])
    assert report["source"]["effective_motor_timestamp_available"] is False
    assert report["acceptance"]["action_002_fully_satisfied"] is False


def test_regular_grid_linear_scheduler_matches_frozen_frame_shift() -> None:
    report = read_json(REPORT_PATH)
    evaluation = report["evaluation"]

    assert math.isclose(
        evaluation["scheduler_sensitivity"]["timestamp_linear"]["pooled_joint_rmse"],
        evaluation["frozen_frame_delay"]["pooled_joint_rmse"],
        rel_tol=0.0,
        abs_tol=1e-6,
    )
