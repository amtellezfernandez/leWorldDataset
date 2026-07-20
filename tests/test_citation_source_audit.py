from __future__ import annotations

import json

from tools.citation_source_audit import (
    README_PATH,
    REPORT_PATH,
    SCHEMA,
    build_report,
    render_markdown,
)


def test_citation_source_audit_is_complete_and_current() -> None:
    report = build_report()

    assert report["schema"] == SCHEMA
    assert report["validation"] == {
        "passed": True,
        "errors": [],
        "undefined_citations": [],
        "unused_bibliography_entries": [],
    }
    assert REPORT_PATH.read_text(encoding="utf-8") == (
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    assert README_PATH.read_text(encoding="utf-8") == render_markdown(report)


def test_every_reference_has_a_source_class_and_locator() -> None:
    report = build_report()

    assert report["references"]
    for reference in report["references"]:
        assert reference["source_class"] != "unclassified"
        assert reference["locator"]
        assert reference["validation"] == {"passed": True, "errors": []}
