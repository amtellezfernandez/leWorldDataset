import copy
import json
from pathlib import Path

import pytest

from tools.lerobot_policy_full_training import (
    DEFAULT_PROTOCOL,
    PolicyExperimentError,
    analysis_from_reports,
    make_jobs_payload,
    parse_loss_curve,
    sha256_payload,
    validate_protocol,
)


def protocol() -> dict:
    return json.loads(DEFAULT_PROTOCOL.read_text(encoding="utf-8"))


def test_protocol_fixes_twenty_matched_jobs() -> None:
    value = protocol()
    validate_protocol(value)

    payload = make_jobs_payload(value)

    assert payload["job_count"] == 20
    assert len({job["job_id"] for job in payload["jobs"]}) == 20
    assert {
        (job["policy"], job["split_id"], job["seed"])
        for job in payload["jobs"]
    } == {
        (policy, split["id"], seed)
        for policy in ("act", "diffusion")
        for split in value["training"]["split_conditions"]
        for seed in range(5)
    }
    for job in payload["jobs"]:
        command = job["training_command_template"]
        assert "--steps=20000" in command
        assert "--save_freq=5000" in command
        assert "--env_eval_freq=0" in command
        assert "--eval_steps=0" in command
        assert "--cudnn_deterministic=true" in command
        assert "--wandb.enable=false" in command


def test_protocol_episode_digest_and_claim_boundary_are_fail_closed() -> None:
    value = protocol()
    episodes = value["evaluation"]["episode_selection"][
        "expected_source_episode_indices"
    ]
    assert sha256_payload(episodes) == value["evaluation"]["episode_selection"][
        "expected_source_episode_indices_sha256"
    ]

    invalid = copy.deepcopy(value)
    invalid["evaluation"]["metrics"]["success_threshold"] = 0.5
    with pytest.raises(PolicyExperimentError, match="success threshold"):
        validate_protocol(invalid)

    invalid = copy.deepcopy(value)
    invalid["claim_boundary"]["does_not_establish"].remove(
        "scene_only_leakage"
    )
    with pytest.raises(PolicyExperimentError, match="scene_only_leakage"):
        validate_protocol(invalid)


def test_training_loss_parser_rejects_nonfinite_values(tmp_path: Path) -> None:
    log = tmp_path / "train.log"
    log.write_text(
        "INFO step:100 smpl:800 ep:2 epch:0.01 loss:1.25\n"
        "INFO step:20K smpl:160K ep:40 epch:1.00 loss:2.5e-2\n",
        encoding="utf-8",
    )
    assert parse_loss_curve(log) == [
        {"step": 100, "loss": 1.25},
        {"step": 20000, "loss": 0.025},
    ]

    log.write_text("INFO step:100 loss:nan\n", encoding="utf-8")
    with pytest.raises(PolicyExperimentError, match="non-finite"):
        parse_loss_curve(log)


def test_paired_analysis_uses_same_seeds_and_source_episodes() -> None:
    value = protocol()
    value["analysis"]["bootstrap_resamples"] = 200
    jobs = make_jobs_payload(value)
    source_episodes = value["evaluation"]["episode_selection"][
        "expected_source_episode_indices"
    ]
    reports = {}
    for job in jobs["jobs"]:
        offset = (
            1.0
            if job["split_id"] == "task_confounded_lineage_holdout"
            else 0.0
        )
        rows = [
            {
                "source_episode_index": source_episode,
                "normalized_rmse": (
                    0.1 * job["seed"] + 0.001 * episode_index + offset
                ),
            }
            for episode_index, source_episode in enumerate(source_episodes)
        ]
        reports[job["job_id"]] = {
            "evaluation": {"metrics": {"per_episode": rows}}
        }

    result = analysis_from_reports(value, jobs, reports)

    for policy in ("act", "diffusion"):
        effect = result["policies"][policy]["paired_effect"]
        assert effect["estimate"] == pytest.approx(1.0)
        assert effect["ci_low"] == pytest.approx(1.0)
        assert effect["ci_high"] == pytest.approx(1.0)
        assert effect["paired_by"] == ["training_seed", "source_episode"]
