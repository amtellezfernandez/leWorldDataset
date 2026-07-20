from __future__ import annotations

import json

from tools.third_party_asset_audit import (
    NOTICE_PATH,
    README_PATH,
    REPORT_PATH,
    SCHEMA,
    build_report,
    render_markdown,
    render_notice,
)


def test_third_party_asset_audit_is_complete_and_current() -> None:
    report = build_report()

    assert report["schema"] == SCHEMA
    assert report["validation"] == {"passed": True, "errors": []}
    assert REPORT_PATH.read_text(encoding="utf-8") == (
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    assert README_PATH.read_text(encoding="utf-8") == render_markdown(report)
    assert NOTICE_PATH.read_text(encoding="utf-8") == render_notice(report)


def test_every_redistributed_parquet_has_source_license_evidence() -> None:
    report = build_report()

    assert report["redistributed_source_rows"]
    for artifact in report["redistributed_source_rows"]:
        assert artifact["source_license_file"]
        assert artifact["license_expression"]
        assert artifact["repo_id"]
        assert artifact["revision"]
    assert report["aggregate"]["source_media_count"] == 0
