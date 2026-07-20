from __future__ import annotations

import json

from tools.submission_anonymity_audit import (
    OUTPUT_PATH,
    README_PATH,
    SCHEMA,
    build_report,
    render_markdown,
)


def test_submission_anonymity_report_is_current_and_passes() -> None:
    report = build_report()
    assert report["schema"] == SCHEMA
    assert report["status"] == "pass"
    assert report["validation"]["passed"] is True
    assert report["paper"]["author_metadata_empty"] is True
    assert report["paper"]["identity_pattern_matches"] == 0
    assert report["supplement"]["identity_pattern_matches"] == 0
    assert OUTPUT_PATH.read_text(encoding="utf-8") == (
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    assert README_PATH.read_text(encoding="utf-8") == render_markdown(report)
