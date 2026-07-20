from __future__ import annotations

import json

from tools.experiment_manifest import (
    OUTPUT_PATH,
    README_PATH,
    SCHEMA,
    build_manifest,
    render_markdown,
)


def test_experiment_manifest_is_current_and_complete() -> None:
    manifest = build_manifest()
    assert manifest["schema"] == SCHEMA
    assert manifest["validation"] == {"passed": True, "errors": []}
    assert OUTPUT_PATH.read_text(encoding="utf-8") == (
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    assert README_PATH.read_text(encoding="utf-8") == render_markdown(manifest)


def test_principal_experiments_have_reproducibility_fields() -> None:
    manifest = build_manifest()
    assert {item["experiment_id"] for item in manifest["experiments"]} == {
        "armnet_task_scene_proxy_mlp",
        "armnet_task_scene_proxy_temporal_ridge",
        "droid_100_proxy_ridge_rerun",
        "controlled_contract_suite",
        "lerobot_conversion_scale",
        "lerobot_multitrajectory_timing",
        "contact_rich_cross_simulator_replay",
        "lerobot_act_diffusion_compatibility_preflight",
        "lerobot_act_diffusion_front_camera_smoke",
    }
    for experiment in manifest["experiments"]:
        assert experiment["datasets"] or experiment.get("authored_inputs")
        assert experiment["configuration"]
        assert experiment["seed_policy"]["kind"]
        assert experiment["code"]
        assert experiment["outputs"]
        assert experiment["execution"]["repository_commit"]
        assert experiment["execution"]["compute"]["wall_time_seconds"] > 0
        assert experiment["execution"]["compute"]["max_rss_bytes"] > 0
        assert experiment["execution"]["exit_status"] == 0
