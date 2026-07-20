from __future__ import annotations

import json

from tools.neurips_submission_audit import (
    OUTPUT_PATH,
    README_PATH,
    SCHEMA,
    build_report,
    render_markdown,
)


def test_neurips_submission_report_is_current_and_valid() -> None:
    report = build_report()

    assert report["schema"] == SCHEMA
    assert report["status"] == "provisional_ready_pending_target_author_kit"
    assert report["target"]["requirements_final"] is False
    assert report["baseline"]["migration_required"] is True
    assert report["validation"]["passed"] is True
    assert report["validation"]["errors"] == []
    assert (
        report["paper"]["main_content_last_page"]
        <= report["paper"]["main_content_page_limit"]
    )
    assert (
        report["paper"]["heading_pages"]["references"]
        < report["paper"]["heading_pages"]["appendix"]
    )
    assert (
        report["paper"]["heading_pages"]["conclusion"]
        <= report["paper"]["heading_pages"]["references"]
    )
    assert OUTPUT_PATH.read_text(encoding="utf-8") == (
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    assert README_PATH.read_text(encoding="utf-8") == render_markdown(report)
