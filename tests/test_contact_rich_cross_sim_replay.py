from __future__ import annotations

import copy
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "contact_rich_cross_sim_replay.py"
SPEC = importlib.util.spec_from_file_location("contact_rich_cross_sim_replay", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def synthetic_runtime(protocol, runtime_id: str, position_offset: float):
    tasks = {}
    for task in protocol["tasks"]:
        scenarios = []
        for scenario in MODULE.scenarios_for_task(protocol, task):
            count = MODULE.task_step_count(task)
            contacts = {
                channel: [index >= count // 2 for index in range(count)]
                for channel in task["contact_channels"]
            }
            trajectory = {
                "object_position_m": [
                    [position_offset + index * 0.001, 0.0, 0.03]
                    for index in range(count)
                ],
                "object_quaternion_wxyz": [[1.0, 0.0, 0.0, 0.0] for _ in range(count)],
                "contacts": contacts,
            }
            if "grasp_definition" in task:
                trajectory["grasp_state"] = [
                    contacts["left_finger"][index]
                    and contacts["right_finger"][index]
                    for index in range(count)
                ]
            scenarios.append(
                {
                    **scenario,
                    "trajectory": trajectory,
                    "outcome_success": True,
                }
            )
        tasks[task["task_id"]] = {
            "contact_channels": task["contact_channels"],
            "scenario_count": len(scenarios),
            "scenarios": scenarios,
            "step_count": MODULE.task_step_count(task),
        }
    return {
        "profile": "worldepisode-contact-rich-runtime-report-0.1",
        "protocol_sha256": MODULE.sha256_payload(protocol),
        "runtime_id": runtime_id,
        "runtime_manifest": {},
        "tasks": tasks,
        "tested": True,
    }


def test_protocol_generates_multiple_identical_scenario_sets():
    protocol = MODULE.load_json(MODULE.DEFAULT_PROTOCOL)
    MODULE.validate_protocol(protocol)
    for task in protocol["tasks"]:
        first = MODULE.scenarios_for_task(protocol, task)
        second = MODULE.scenarios_for_task(protocol, task)
        assert first == second
        assert len(first) >= protocol["acceptance"]["minimum_scenarios_per_task"]


def test_comparison_reports_known_position_offset_and_perfect_contacts():
    protocol = MODULE.load_json(MODULE.DEFAULT_PROTOCOL)
    protocol = copy.deepcopy(protocol)
    protocol["analysis"]["bootstrap_resamples"] = 100
    mujoco = synthetic_runtime(protocol, "mujoco", 0.0)
    genesis = synthetic_runtime(protocol, "genesis", 0.01)
    analysis = MODULE.compare_runtime_reports(protocol, mujoco, genesis)

    assert analysis["acceptance"]["pass"] is True
    assert abs(
        analysis["aggregate"]["trajectory_position_rmse_m"]["estimate"] - 0.01
    ) < 1e-12
    assert analysis["aggregate"]["contact_precision"]["estimate"] == 1.0
    assert analysis["aggregate"]["contact_recall"]["estimate"] == 1.0
    assert analysis["aggregate"]["contact_f1"]["estimate"] == 1.0
    assert analysis["aggregate"]["task_outcome_agreement"]["estimate"] == 1.0
    assert analysis["aggregate"]["grasp_state_agreement"]["estimate"] == 1.0


def test_comparison_rejects_runtime_initial_state_mismatch():
    protocol = MODULE.load_json(MODULE.DEFAULT_PROTOCOL)
    protocol = copy.deepcopy(protocol)
    protocol["analysis"]["bootstrap_resamples"] = 10
    mujoco = synthetic_runtime(protocol, "mujoco", 0.0)
    genesis = synthetic_runtime(protocol, "genesis", 0.0)
    task_id = protocol["tasks"][0]["task_id"]
    genesis["tasks"][task_id]["scenarios"][0]["object_position_m"][0] += 0.1

    try:
        MODULE.compare_runtime_reports(protocol, mujoco, genesis)
    except MODULE.ContactReplayError as exc:
        assert "initial states" in str(exc)
    else:
        raise AssertionError("mismatched initial states should fail")


def test_numeric_normalization_is_stable_across_libm_scale_noise():
    left = {"metric": 40.59804501386309, "nested": [0.009006994767989345]}
    right = {"metric": 40.598045013859824, "nested": [0.009006994767988991]}

    assert MODULE.normalize_numeric(left) == MODULE.normalize_numeric(right)


def test_analysis_equivalence_tolerates_only_negligible_float_noise():
    baseline = {"metric": 0.0031753911418, "count": 32, "passed": True}
    libm_variant = {"metric": 0.00317539068269, "count": 32, "passed": True}
    material_change = {"metric": 0.0032, "count": 32, "passed": True}
    discrete_change = {"metric": 0.0031753911418, "count": 31, "passed": True}

    assert MODULE.analyses_equivalent(baseline, libm_variant)
    assert not MODULE.analyses_equivalent(baseline, material_change)
    assert not MODULE.analyses_equivalent(baseline, discrete_change)
