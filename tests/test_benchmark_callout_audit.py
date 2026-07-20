from __future__ import annotations

import json
from pathlib import Path

from tools.benchmark_callout_audit import measured_contrast


def test_measured_contrast_reads_current_leakage_report(tmp_path: Path) -> None:
    report_path = tmp_path / "leakage_report.json"
    report_path.write_text(
        json.dumps(
            {
                "available": True,
                "repo_id": "example/dataset",
                "revision": "revision-1",
                "bc_seeds": [3, 5],
                "splits": {
                    "random_episode": {
                        "leakage_rate": 0.75,
                        "bc": {"offline_bc_success_rate": 0.625},
                    },
                    "scene_disjoint": {
                        "leakage_rate": 0.0,
                        "bc": {"offline_bc_success_rate": 0.125},
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    contrast = measured_contrast(report_path)

    assert contrast["dataset"] == "example/dataset"
    assert contrast["seed_count"] == 2
    assert contrast["random_offline_bc_success"] == 0.625
    assert contrast["scene_disjoint_offline_bc_success"] == 0.125
