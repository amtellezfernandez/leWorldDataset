from __future__ import annotations

import io
import json
import zipfile

from tools.build_anonymous_supplement import (
    ARCHIVE_ROOT,
    FORBIDDEN_PATTERNS,
    OUTPUT_PATH,
    README_PATH,
    REPORT_PATH,
    build_archive,
    build_report,
    render_markdown,
)


def test_anonymous_supplement_is_current_and_valid() -> None:
    archive_bytes, internal_manifest = build_archive()
    report = build_report(archive_bytes, internal_manifest)
    assert report["status"] == "pass"
    assert report["validation"] == {
        "passed": True,
        "errors": [],
        "identity_pattern_matches": 0,
    }
    assert OUTPUT_PATH.read_bytes() == archive_bytes
    assert REPORT_PATH.read_text(encoding="utf-8") == (
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    assert README_PATH.read_text(encoding="utf-8") == render_markdown(report)


def test_archive_has_no_history_or_local_environment() -> None:
    with zipfile.ZipFile(io.BytesIO(OUTPUT_PATH.read_bytes()), mode="r") as archive:
        names = archive.namelist()
    assert f"{ARCHIVE_ROOT}/SUPPLEMENT_MANIFEST.json" in names
    assert f"{ARCHIVE_ROOT}/ANONYMITY.md" in names
    assert not any("/.git/" in name or "/.venv/" in name for name in names)
    assert not any("__pycache__" in name or name.endswith(".pyc") for name in names)


def test_archive_removes_split_author_name_fields() -> None:
    archive_bytes, _ = build_archive()
    citation_path = f"{ARCHIVE_ROOT}/CITATION.cff"
    with zipfile.ZipFile(io.BytesIO(archive_bytes), mode="r") as archive:
        citation = archive.read(citation_path).decode("utf-8")

    assert 'family-names: "Anonymous Author"' in citation
    assert 'given-names: "Anonymous"' in citation
    assert 'repository-code: "https://github.com/anonymous/leWorldDataset"' in citation
    assert all(pattern.search(citation) is None for pattern in FORBIDDEN_PATTERNS)
