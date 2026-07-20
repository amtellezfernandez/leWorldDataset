from __future__ import annotations

import json

from tools.huggingface_recovery_pointer import (
    ASSET_PLAN_PATH,
    JSON_PATH,
    MARKDOWN_PATH,
    VERIFICATION_PATH,
    build_pointer,
    load_json,
    render_markdown,
)


def test_huggingface_recovery_pointer_is_verified_and_current() -> None:
    verification = load_json(VERIFICATION_PATH)
    current = load_json(JSON_PATH)
    pointer = build_pointer(verification, load_json(ASSET_PLAN_PATH), current)

    assert pointer["verification"]["passed"] is True
    assert pointer["snapshot"]["git_commit"] == verification["bundle_head"]
    assert JSON_PATH.read_text(encoding="utf-8") == (
        json.dumps(pointer, indent=2, sort_keys=True) + "\n"
    )
    assert MARKDOWN_PATH.read_text(encoding="utf-8") == render_markdown(pointer)
