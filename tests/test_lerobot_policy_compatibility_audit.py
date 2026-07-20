import json

from tools.lerobot_policy_compatibility_audit import (
    DEFAULT_DATASET_ROOT,
    DEFAULT_REPORT,
    EXPECTED_MODALITY_ERROR,
    validate_existing_report,
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
