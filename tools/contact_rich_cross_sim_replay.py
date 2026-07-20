#!/usr/bin/env python3
"""Run a preregistered contact-rich replay in MuJoCo and Genesis.

The parent process executes each simulator in a fresh subprocess, then compares their
scenario-aligned trajectories and contact traces. Runtime imports are deliberately lazy so
`--check` and unit tests do not require either simulator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import random
import resource
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "experiments" / "contact_rich_replay"
DEFAULT_PROTOCOL = DEFAULT_OUTPUT_DIR / "protocol.json"
DEFAULT_REPORT = DEFAULT_OUTPUT_DIR / "contact_rich_replay_report.json"
RUNTIME_IDS = ("mujoco", "genesis")


class ContactReplayError(RuntimeError):
    """Raised when the contact-rich replay cannot produce valid evidence."""


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def canonical_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_payload(payload: Any) -> str:
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_numeric(payload: Any) -> Any:
    """Stabilize derived floats across supported Python/libm builds."""
    if isinstance(payload, dict):
        return {key: normalize_numeric(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [normalize_numeric(value) for value in payload]
    if isinstance(payload, float):
        if not math.isfinite(payload):
            raise ContactReplayError("derived analysis contains a non-finite value")
        return float(f"{payload:.12g}")
    return payload


def analyses_equivalent(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            analyses_equivalent(left[key], right[key]) for key in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            analyses_equivalent(a, b) for a, b in zip(left, right)
        )
    if isinstance(left, float):
        return math.isclose(left, right, rel_tol=1e-10, abs_tol=1e-8)
    return left == right


def relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def git_output(*args: str) -> str | None:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode:
        return None
    value = completed.stdout.strip()
    return value or None


def protocol_preregistration(protocol_path: Path) -> dict[str, Any]:
    path = relative(protocol_path)
    history = git_output("log", "--reverse", "--format=%H", "--", path)
    first_commit = history.splitlines()[0] if history else None
    return {
        "protocol_path": path,
        "protocol_sha256": sha256_file(protocol_path),
        "git_blob_oid": git_output("hash-object", path),
        "first_committed_revision": first_commit,
        "committed_before_required_execution": first_commit is not None,
    }


def validate_protocol(protocol: dict[str, Any]) -> None:
    if protocol.get("profile") != "worldepisode-contact-rich-cross-simulator-replay-protocol-0.1":
        raise ContactReplayError("unexpected contact-rich replay protocol profile")
    tasks = protocol.get("tasks")
    if not isinstance(tasks, list) or len(tasks) < 2:
        raise ContactReplayError("protocol must define at least two tasks")
    task_ids = [task.get("task_id") for task in tasks]
    if len(set(task_ids)) != len(task_ids) or any(not value for value in task_ids):
        raise ContactReplayError("protocol task ids must be nonempty and unique")
    required_runtimes = protocol.get("acceptance", {}).get("required_runtime_ids")
    if required_runtimes != list(RUNTIME_IDS):
        raise ContactReplayError(f"protocol required runtimes must be {list(RUNTIME_IDS)}")
    scenario_count = protocol.get("scenario_generation", {}).get("scenario_count_per_task")
    minimum_count = protocol.get("acceptance", {}).get("minimum_scenarios_per_task")
    if not isinstance(scenario_count, int) or not isinstance(minimum_count, int):
        raise ContactReplayError("scenario counts must be integers")
    if scenario_count < minimum_count or minimum_count < 2:
        raise ContactReplayError("protocol does not include multiple accepted initial states per task")
    if protocol.get("simulation", {}).get("actor_contract") != "sampled_kinematic_pose":
        raise ContactReplayError("unsupported actor contract")


def task_seed(base_seed: int, task_id: str) -> int:
    digest = hashlib.sha256(f"{base_seed}:{task_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def scenarios_for_task(protocol: dict[str, Any], task: dict[str, Any]) -> list[dict[str, Any]]:
    generation = protocol["scenario_generation"]
    rng = random.Random(task_seed(int(generation["seed"]), str(task["task_id"])))
    distribution = task["initial_state_distribution"]
    nominal = task["object"]["nominal_position_m"]
    scenarios = []
    for index in range(int(generation["scenario_count_per_task"])):
        x_offset = rng.uniform(*distribution["object_x_offset_m"])
        y_offset = rng.uniform(*distribution["object_y_offset_m"])
        yaw_deg = rng.uniform(*distribution["object_yaw_deg"])
        scenarios.append(
            {
                "scenario_id": f"{task['task_id']}-{index:03d}",
                "object_position_m": [
                    float(nominal[0]) + x_offset,
                    float(nominal[1]) + y_offset,
                    float(nominal[2]),
                ],
                "object_yaw_deg": yaw_deg,
            }
        )
    return scenarios


def smoothstep(index: int, step_count: int) -> float:
    if step_count <= 0:
        return 1.0
    t = min(1.0, max(0.0, (index + 1) / step_count))
    return t * t * (3.0 - 2.0 * t)


def actor_positions(task: dict[str, Any], step_index: int) -> dict[str, list[float]]:
    action = task["action"]
    if task["task_id"] == "straight_push":
        alpha = smoothstep(step_index, int(action["move_steps"]))
        start = action["pusher_start_m"]
        end = action["pusher_end_m"]
        return {
            "pusher": [
                float(start[axis]) + alpha * (float(end[axis]) - float(start[axis]))
                for axis in range(3)
            ]
        }
    if task["task_id"] == "parallel_jaw_capture":
        alpha = smoothstep(step_index, int(action["close_steps"]))
        initial = float(action["initial_half_separation_m"])
        final = float(action["final_half_separation_m"])
        separation = initial + alpha * (final - initial)
        x = float(action["finger_center_x_m"])
        z = float(action["finger_center_z_m"])
        return {
            "left_finger": [x, -separation, z],
            "right_finger": [x, separation, z],
        }
    raise ContactReplayError(f"unsupported task: {task['task_id']}")


def task_step_count(task: dict[str, Any]) -> int:
    action = task["action"]
    if task["task_id"] == "straight_push":
        return int(action["move_steps"]) + int(action["hold_steps"])
    if task["task_id"] == "parallel_jaw_capture":
        return int(action["close_steps"]) + int(action["hold_steps"])
    raise ContactReplayError(f"unsupported task: {task['task_id']}")


def yaw_quaternion(yaw_deg: float) -> list[float]:
    half = math.radians(yaw_deg) / 2.0
    return [math.cos(half), 0.0, 0.0, math.sin(half)]


def to_list(value: Any) -> list[float]:
    import numpy as np

    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    elif hasattr(value, "cpu"):
        value = value.cpu().numpy()
    return [float(item) for item in np.asarray(value, dtype=np.float64).reshape(-1)]


def contact_count(contact_info: dict[str, Any]) -> int:
    import numpy as np

    values = contact_info["geom_a"]
    if hasattr(values, "detach"):
        values = values.detach().cpu().numpy()
    return int(np.asarray(values).size)


def scenario_outcome(task: dict[str, Any], trajectory: dict[str, Any]) -> bool:
    outcome = task["outcome"]
    if outcome["type"] == "final_object_position":
        final = trajectory["object_position_m"][-1]
        return (
            float(final[0]) >= float(outcome["minimum_final_x_m"])
            and abs(float(final[1])) <= float(outcome["maximum_abs_y_m"])
        )
    if outcome["type"] == "sustained_parallel_jaw_capture":
        window = int(outcome["evaluation_window_steps"])
        grasp = trajectory["grasp_state"][-window:]
        return statistics.fmean(float(value) for value in grasp) >= float(
            outcome["minimum_grasp_fraction"]
        )
    raise ContactReplayError(f"unsupported outcome type: {outcome['type']}")


def machine_manifest() -> dict[str, Any]:
    memory_bytes = None
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        page_count = os.sysconf("SC_PHYS_PAGES")
        memory_bytes = int(page_size * page_count)
    except (AttributeError, ValueError, OSError):
        pass
    cpu_model = platform.processor()
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.is_file():
        for line in cpuinfo.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.lower().startswith("model name"):
                cpu_model = line.split(":", 1)[-1].strip()
                break
    storage = shutil.disk_usage(ROOT)
    max_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    max_rss_bytes = int(max_rss * 1024) if sys.platform != "darwin" else int(max_rss)
    return {
        "hostname_sha256": hashlib.sha256(platform.node().encode("utf-8")).hexdigest(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpu_model": cpu_model or "unknown",
        "logical_cpu_count": os.cpu_count(),
        "ram_bytes": memory_bytes,
        "gpu": "not_used_cpu_protocol",
        "gpu_vram_bytes": "not_used_cpu_protocol",
        "storage_total_bytes": storage.total,
        "storage_free_bytes": storage.free,
        "max_rss_bytes": max_rss_bytes,
    }


def mujoco_xml(protocol: dict[str, Any], task: dict[str, Any]) -> str:
    simulation = protocol["simulation"]
    friction = float(simulation["surface_friction"])
    object_spec = task["object"]
    object_half = [float(value) / 2.0 for value in object_spec["size_m"]]
    actor_bodies = []
    for actor in task["actors"]:
        actor_id = str(actor["actor_id"])
        half = [float(value) / 2.0 for value in actor["size_m"]]
        initial_position = actor_positions(task, 0)[actor_id]
        actor_bodies.append(
            f'<body name="{actor_id}" mocap="true" '
            f'pos="{initial_position[0]} {initial_position[1]} {initial_position[2]}">'
            f'<geom name="{actor_id}_geom" type="box" '
            f'size="{half[0]} {half[1]} {half[2]}" '
            f'friction="{friction} 0.005 0.0001"/>'
            "</body>"
        )
    nominal = object_spec["nominal_position_m"]
    return (
        '<mujoco model="worldepisode_contact_replay">'
        f'<option timestep="{simulation["time_step_s"]}" gravity="'
        f'{simulation["gravity_m_s2"][0]} {simulation["gravity_m_s2"][1]} '
        f'{simulation["gravity_m_s2"][2]}" integrator="implicitfast" solver="Newton" '
        'iterations="100" tolerance="1e-10"/>'
        "<worldbody>"
        f'<geom name="ground" type="plane" size="2 2 0.1" '
        f'friction="{friction} 0.005 0.0001"/>'
        f'<body name="object" pos="{nominal[0]} {nominal[1]} {nominal[2]}">'
        '<freejoint name="object_free"/>'
        f'<geom name="object_geom" type="box" '
        f'size="{object_half[0]} {object_half[1]} {object_half[2]}" '
        f'density="{simulation["object_density_kg_m3"]}" '
        f'friction="{friction} 0.005 0.0001"/>'
        "</body>"
        f'{"".join(actor_bodies)}'
        "</worldbody>"
        "</mujoco>"
    )


def run_mujoco(protocol: dict[str, Any]) -> dict[str, Any]:
    started = time.monotonic()
    started_utc = datetime.now(timezone.utc).isoformat()
    try:
        import mujoco
        import numpy as np
    except ImportError as exc:
        raise ContactReplayError(
            "MuJoCo runtime unavailable; run with the pinned reproduction environment"
        ) from exc

    tasks_payload = {}
    for task in protocol["tasks"]:
        model = mujoco.MjModel.from_xml_string(mujoco_xml(protocol, task))
        data = mujoco.MjData(model)
        object_body_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "object")
        object_joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "object_free")
        qpos_address = int(model.jnt_qposadr[object_joint_id])
        actor_body_ids = {
            actor["actor_id"]: mujoco.mj_name2id(
                model, mujoco.mjtObj.mjOBJ_BODY, actor["actor_id"]
            )
            for actor in task["actors"]
        }
        actor_mocap_ids = {
            actor_id: int(model.body_mocapid[body_id])
            for actor_id, body_id in actor_body_ids.items()
        }
        actor_geom_ids = {
            actor["actor_id"]: mujoco.mj_name2id(
                model, mujoco.mjtObj.mjOBJ_GEOM, f"{actor['actor_id']}_geom"
            )
            for actor in task["actors"]
        }
        object_geom_id = mujoco.mj_name2id(
            model, mujoco.mjtObj.mjOBJ_GEOM, "object_geom"
        )
        scenario_rows = []
        for scenario in scenarios_for_task(protocol, task):
            mujoco.mj_resetData(model, data)
            data.qpos[qpos_address : qpos_address + 3] = np.asarray(
                scenario["object_position_m"], dtype=np.float64
            )
            data.qpos[qpos_address + 3 : qpos_address + 7] = np.asarray(
                yaw_quaternion(float(scenario["object_yaw_deg"])), dtype=np.float64
            )
            initial_actor_positions = actor_positions(task, 0)
            for actor_id, position in initial_actor_positions.items():
                data.mocap_pos[actor_mocap_ids[actor_id]] = np.asarray(
                    position, dtype=np.float64
                )
            mujoco.mj_forward(model, data)
            for _ in range(int(protocol["simulation"]["settle_steps"])):
                mujoco.mj_step(model, data)

            trajectory = {
                "object_position_m": [],
                "object_quaternion_wxyz": [],
                "contacts": {channel: [] for channel in task["contact_channels"]},
            }
            if "grasp_definition" in task:
                trajectory["grasp_state"] = []
            for step_index in range(task_step_count(task)):
                positions = actor_positions(task, step_index)
                for actor_id, position in positions.items():
                    data.mocap_pos[actor_mocap_ids[actor_id]] = np.asarray(
                        position, dtype=np.float64
                    )
                mujoco.mj_step(model, data)
                trajectory["object_position_m"].append(
                    [float(value) for value in data.xpos[object_body_id]]
                )
                trajectory["object_quaternion_wxyz"].append(
                    [float(value) for value in data.xquat[object_body_id]]
                )
                channel_values = {}
                for channel in task["contact_channels"]:
                    actor_geom_id = actor_geom_ids[channel]
                    active = any(
                        {int(contact.geom1), int(contact.geom2)}
                        == {object_geom_id, actor_geom_id}
                        for contact in data.contact
                    )
                    channel_values[channel] = active
                    trajectory["contacts"][channel].append(active)
                if "grasp_definition" in task:
                    trajectory["grasp_state"].append(
                        channel_values["left_finger"]
                        and channel_values["right_finger"]
                    )
            scenario_rows.append(
                {
                    **scenario,
                    "trajectory": trajectory,
                    "outcome_success": scenario_outcome(task, trajectory),
                }
            )
        tasks_payload[task["task_id"]] = {
            "contact_channels": task["contact_channels"],
            "scenario_count": len(scenario_rows),
            "scenarios": scenario_rows,
            "step_count": task_step_count(task),
        }
    return {
        "profile": "worldepisode-contact-rich-runtime-report-0.1",
        "protocol_sha256": sha256_payload(protocol),
        "runtime_id": "mujoco",
        "runtime_manifest": {
            **machine_manifest(),
            "backend": "cpu",
            "mujoco_version": mujoco.__version__,
            "numpy_version": np.__version__,
            "precision": "float64",
            "solver": "Newton",
            "integrator": "implicitfast",
            "contact_role": "reference_not_physical_ground_truth",
            "started_utc": started_utc,
            "finished_utc": datetime.now(timezone.utc).isoformat(),
            "wall_time_seconds": time.monotonic() - started,
        },
        "execution": {
            "script": relative(Path(__file__)),
            "script_sha256": sha256_file(Path(__file__)),
            "repository_commit": git_output("rev-parse", "HEAD"),
            "exit_status": 0,
            "preliminary_runs": [],
        },
        "tasks": tasks_payload,
        "tested": True,
    }


def run_genesis(protocol: dict[str, Any]) -> dict[str, Any]:
    started = time.monotonic()
    started_utc = datetime.now(timezone.utc).isoformat()
    try:
        import genesis as gs
        import numpy as np
        import torch
    except ImportError as exc:
        raise ContactReplayError(
            "Genesis runtime unavailable; run with the pinned reproduction environment"
        ) from exc

    simulation = protocol["simulation"]
    gs.init(
        backend=gs.cpu,
        precision=str(protocol["runtime_environment"]["genesis"]["precision"]),
        seed=int(protocol["scenario_generation"]["seed"]),
        logging_level="warning",
    )
    tasks_payload = {}
    for task in protocol["tasks"]:
        scene = gs.Scene(
            show_viewer=False,
            sim_options=gs.options.SimOptions(
                dt=float(simulation["time_step_s"]),
                gravity=tuple(float(value) for value in simulation["gravity_m_s2"]),
            ),
            rigid_options=gs.options.RigidOptions(
                enable_collision=True,
                enable_joint_limit=True,
                constraint_solver=gs.constraint_solver.Newton,
            ),
            profiling_options=gs.options.ProfilingOptions(show_FPS=False),
        )
        friction = float(simulation["surface_friction"])
        material = lambda rho: gs.materials.Rigid(rho=float(rho), friction=friction)
        scene.add_entity(gs.morphs.Plane(), material=material(1000.0), name="ground")
        object_spec = task["object"]
        object_entity = scene.add_entity(
            gs.morphs.Box(
                pos=tuple(float(value) for value in object_spec["nominal_position_m"]),
                size=tuple(float(value) for value in object_spec["size_m"]),
            ),
            material=material(simulation["object_density_kg_m3"]),
            name="object",
        )
        initial_positions = actor_positions(task, 0)
        actors = {}
        for actor in task["actors"]:
            actor_id = str(actor["actor_id"])
            actors[actor_id] = scene.add_entity(
                gs.morphs.Box(
                    pos=tuple(initial_positions[actor_id]),
                    size=tuple(float(value) for value in actor["size_m"]),
                    fixed=True,
                    batch_fixed_verts=True,
                ),
                material=material(1000.0),
                name=actor_id,
            )
        scene.build()
        scenario_rows = []
        for scenario in scenarios_for_task(protocol, task):
            initial_positions = actor_positions(task, 0)
            for actor_id, position in initial_positions.items():
                actors[actor_id].set_pos(position)
            object_entity.set_pos(scenario["object_position_m"])
            object_entity.set_quat(yaw_quaternion(float(scenario["object_yaw_deg"])))
            object_entity.zero_all_dofs_velocity()
            for _ in range(int(simulation["settle_steps"])):
                scene.step()

            trajectory = {
                "object_position_m": [],
                "object_quaternion_wxyz": [],
                "contacts": {channel: [] for channel in task["contact_channels"]},
            }
            if "grasp_definition" in task:
                trajectory["grasp_state"] = []
            for step_index in range(task_step_count(task)):
                positions = actor_positions(task, step_index)
                for actor_id, position in positions.items():
                    actors[actor_id].set_pos(position)
                scene.step()
                trajectory["object_position_m"].append(
                    to_list(object_entity.get_pos())
                )
                trajectory["object_quaternion_wxyz"].append(
                    to_list(object_entity.get_quat())
                )
                channel_values = {}
                for channel in task["contact_channels"]:
                    active = contact_count(
                        object_entity.get_contacts(with_entity=actors[channel])
                    ) > 0
                    channel_values[channel] = active
                    trajectory["contacts"][channel].append(active)
                if "grasp_definition" in task:
                    trajectory["grasp_state"].append(
                        channel_values["left_finger"]
                        and channel_values["right_finger"]
                    )
            scenario_rows.append(
                {
                    **scenario,
                    "trajectory": trajectory,
                    "outcome_success": scenario_outcome(task, trajectory),
                }
            )
        tasks_payload[task["task_id"]] = {
            "contact_channels": task["contact_channels"],
            "scenario_count": len(scenario_rows),
            "scenarios": scenario_rows,
            "step_count": task_step_count(task),
        }
    return {
        "profile": "worldepisode-contact-rich-runtime-report-0.1",
        "protocol_sha256": sha256_payload(protocol),
        "runtime_id": "genesis",
        "runtime_manifest": {
            **machine_manifest(),
            "backend": "cpu",
            "genesis_world_version": getattr(gs, "__version__", "unknown"),
            "numpy_version": np.__version__,
            "torch_version": torch.__version__,
            "precision": str(protocol["runtime_environment"]["genesis"]["precision"]),
            "solver": "Newton",
            "contact_role": "comparison_not_physical_ground_truth",
            "started_utc": started_utc,
            "finished_utc": datetime.now(timezone.utc).isoformat(),
            "wall_time_seconds": time.monotonic() - started,
        },
        "execution": {
            "script": relative(Path(__file__)),
            "script_sha256": sha256_file(Path(__file__)),
            "repository_commit": git_output("rev-parse", "HEAD"),
            "exit_status": 0,
            "preliminary_runs": [],
        },
        "tasks": tasks_payload,
        "tested": True,
    }


def quantile(values: list[float], probability: float) -> float:
    if not values:
        raise ContactReplayError("cannot compute a quantile from no values")
    ordered = sorted(values)
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def bootstrap_ci(
    rows: list[dict[str, Any]],
    statistic: Callable[[list[dict[str, Any]]], float],
    *,
    resamples: int,
    seed: int,
) -> dict[str, Any]:
    if not rows:
        raise ContactReplayError("cannot bootstrap no scenarios")
    estimate = float(statistic(rows))
    rng = random.Random(seed)
    count = len(rows)
    estimates = [
        float(statistic([rows[rng.randrange(count)] for _ in range(count)]))
        for _ in range(resamples)
    ]
    return {
        "estimate": estimate,
        "ci_low": quantile(estimates, 0.025),
        "ci_high": quantile(estimates, 0.975),
        "confidence_level": 0.95,
        "method": "scenario_percentile_bootstrap",
        "resamples": resamples,
        "seed": seed,
        "sample_size_scenarios": count,
    }


def quaternion_angle_deg(left: list[float], right: list[float]) -> float:
    left_norm = math.sqrt(sum(float(value) ** 2 for value in left))
    right_norm = math.sqrt(sum(float(value) ** 2 for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        raise ContactReplayError("zero-norm quaternion in runtime trajectory")
    dot = abs(
        sum(float(a) * float(b) for a, b in zip(left, right))
        / (left_norm * right_norm)
    )
    return math.degrees(2.0 * math.acos(min(1.0, max(-1.0, dot))))


def binary_metrics(tp: int, fp: int, fn: int) -> dict[str, float | int]:
    precision_denominator = tp + fp
    recall_denominator = tp + fn
    precision = tp / precision_denominator if precision_denominator else 1.0
    recall = tp / recall_denominator if recall_denominator else 1.0
    f1 = (
        2.0 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return {
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def scenario_comparison(
    task: dict[str, Any],
    mujoco_row: dict[str, Any],
    genesis_row: dict[str, Any],
) -> dict[str, Any]:
    if mujoco_row["scenario_id"] != genesis_row["scenario_id"]:
        raise ContactReplayError("runtime scenario ids do not align")
    if (
        mujoco_row["object_position_m"] != genesis_row["object_position_m"]
        or mujoco_row["object_yaw_deg"] != genesis_row["object_yaw_deg"]
    ):
        raise ContactReplayError("runtime initial states do not align")
    mujoco_trajectory = mujoco_row["trajectory"]
    genesis_trajectory = genesis_row["trajectory"]
    mujoco_positions = mujoco_trajectory["object_position_m"]
    genesis_positions = genesis_trajectory["object_position_m"]
    if len(mujoco_positions) != len(genesis_positions) or not mujoco_positions:
        raise ContactReplayError("runtime trajectory lengths do not align")
    squared_position_errors = [
        sum((float(left[axis]) - float(right[axis])) ** 2 for axis in range(3))
        for left, right in zip(mujoco_positions, genesis_positions)
    ]
    orientation_errors = [
        quaternion_angle_deg(left, right)
        for left, right in zip(
            mujoco_trajectory["object_quaternion_wxyz"],
            genesis_trajectory["object_quaternion_wxyz"],
        )
    ]
    final_position_error = math.sqrt(squared_position_errors[-1])
    tp = fp = fn = agreement = sample_count = 0
    mujoco_positive = genesis_positive = 0
    for channel in task["contact_channels"]:
        left_values = mujoco_trajectory["contacts"][channel]
        right_values = genesis_trajectory["contacts"][channel]
        if len(left_values) != len(right_values):
            raise ContactReplayError("runtime contact trace lengths do not align")
        for left, right in zip(left_values, right_values):
            left = bool(left)
            right = bool(right)
            tp += int(left and right)
            fp += int(right and not left)
            fn += int(left and not right)
            agreement += int(left == right)
            mujoco_positive += int(left)
            genesis_positive += int(right)
            sample_count += 1
    contact = binary_metrics(tp, fp, fn)
    contact["state_agreement"] = agreement / sample_count
    contact["sample_count"] = sample_count
    contact["mujoco_positive_samples"] = mujoco_positive
    contact["genesis_positive_samples"] = genesis_positive
    row = {
        "scenario_id": mujoco_row["scenario_id"],
        "task_id": task["task_id"],
        "trajectory_position_rmse_m": math.sqrt(
            statistics.fmean(squared_position_errors)
        ),
        "trajectory_orientation_mean_error_deg": statistics.fmean(
            orientation_errors
        ),
        "final_position_error_m": final_position_error,
        "final_orientation_error_deg": orientation_errors[-1],
        "contact": contact,
        "mujoco_outcome_success": bool(mujoco_row["outcome_success"]),
        "genesis_outcome_success": bool(genesis_row["outcome_success"]),
        "outcome_agreement": bool(
            mujoco_row["outcome_success"] == genesis_row["outcome_success"]
        ),
    }
    if "grasp_definition" in task:
        left_grasp = mujoco_trajectory["grasp_state"]
        right_grasp = genesis_trajectory["grasp_state"]
        row["grasp_state_agreement"] = statistics.fmean(
            float(left == right) for left, right in zip(left_grasp, right_grasp)
        )
        row["mujoco_grasp_positive_samples"] = sum(bool(value) for value in left_grasp)
        row["genesis_grasp_positive_samples"] = sum(
            bool(value) for value in right_grasp
        )
    return row


def metric_seed(base_seed: int, label: str) -> int:
    digest = hashlib.sha256(f"{base_seed}:{label}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def summarize_rows(
    rows: list[dict[str, Any]],
    *,
    resamples: int,
    base_seed: int,
    label: str,
) -> dict[str, Any]:
    def mean_key(key: str) -> Callable[[list[dict[str, Any]]], float]:
        return lambda selected: statistics.fmean(float(row[key]) for row in selected)

    def pooled_contact(key: str) -> Callable[[list[dict[str, Any]]], float]:
        def statistic(selected: list[dict[str, Any]]) -> float:
            tp = sum(int(row["contact"]["true_positive"]) for row in selected)
            fp = sum(int(row["contact"]["false_positive"]) for row in selected)
            fn = sum(int(row["contact"]["false_negative"]) for row in selected)
            return float(binary_metrics(tp, fp, fn)[key])

        return statistic

    summary = {
        "scenario_count": len(rows),
        "trajectory_position_rmse_m": bootstrap_ci(
            rows,
            mean_key("trajectory_position_rmse_m"),
            resamples=resamples,
            seed=metric_seed(base_seed, f"{label}:trajectory-position"),
        ),
        "trajectory_orientation_mean_error_deg": bootstrap_ci(
            rows,
            mean_key("trajectory_orientation_mean_error_deg"),
            resamples=resamples,
            seed=metric_seed(base_seed, f"{label}:trajectory-orientation"),
        ),
        "final_position_error_m": bootstrap_ci(
            rows,
            mean_key("final_position_error_m"),
            resamples=resamples,
            seed=metric_seed(base_seed, f"{label}:final-position"),
        ),
        "final_orientation_error_deg": bootstrap_ci(
            rows,
            mean_key("final_orientation_error_deg"),
            resamples=resamples,
            seed=metric_seed(base_seed, f"{label}:final-orientation"),
        ),
        "contact_precision": bootstrap_ci(
            rows,
            pooled_contact("precision"),
            resamples=resamples,
            seed=metric_seed(base_seed, f"{label}:contact-precision"),
        ),
        "contact_recall": bootstrap_ci(
            rows,
            pooled_contact("recall"),
            resamples=resamples,
            seed=metric_seed(base_seed, f"{label}:contact-recall"),
        ),
        "contact_f1": bootstrap_ci(
            rows,
            pooled_contact("f1"),
            resamples=resamples,
            seed=metric_seed(base_seed, f"{label}:contact-f1"),
        ),
        "contact_state_agreement": bootstrap_ci(
            rows,
            lambda selected: (
                sum(int(row["contact"]["true_positive"]) for row in selected)
                + sum(
                    int(row["contact"]["sample_count"])
                    - int(row["contact"]["true_positive"])
                    - int(row["contact"]["false_positive"])
                    - int(row["contact"]["false_negative"])
                    for row in selected
                )
            )
            / sum(int(row["contact"]["sample_count"]) for row in selected),
            resamples=resamples,
            seed=metric_seed(base_seed, f"{label}:contact-state-agreement"),
        ),
        "mujoco_task_success_rate": bootstrap_ci(
            rows,
            mean_key("mujoco_outcome_success"),
            resamples=resamples,
            seed=metric_seed(base_seed, f"{label}:mujoco-success"),
        ),
        "genesis_task_success_rate": bootstrap_ci(
            rows,
            mean_key("genesis_outcome_success"),
            resamples=resamples,
            seed=metric_seed(base_seed, f"{label}:genesis-success"),
        ),
        "task_outcome_agreement": bootstrap_ci(
            rows,
            mean_key("outcome_agreement"),
            resamples=resamples,
            seed=metric_seed(base_seed, f"{label}:outcome-agreement"),
        ),
    }
    grasp_rows = [row for row in rows if "grasp_state_agreement" in row]
    if grasp_rows:
        summary["grasp_state_agreement"] = bootstrap_ci(
            grasp_rows,
            mean_key("grasp_state_agreement"),
            resamples=resamples,
            seed=metric_seed(base_seed, f"{label}:grasp-state-agreement"),
        )
    return summary


def compare_runtime_reports(
    protocol: dict[str, Any],
    mujoco_report: dict[str, Any],
    genesis_report: dict[str, Any],
) -> dict[str, Any]:
    expected_digest = sha256_payload(protocol)
    for runtime_id, report in (
        ("mujoco", mujoco_report),
        ("genesis", genesis_report),
    ):
        if report.get("runtime_id") != runtime_id or report.get("tested") is not True:
            raise ContactReplayError(f"{runtime_id} report is not a tested runtime result")
        if report.get("protocol_sha256") != expected_digest:
            raise ContactReplayError(f"{runtime_id} report uses a different protocol")

    all_rows = []
    task_summaries = {}
    contact_totals = {runtime_id: {} for runtime_id in RUNTIME_IDS}
    resamples = int(protocol["analysis"]["bootstrap_resamples"])
    base_seed = int(protocol["analysis"]["bootstrap_seed"])
    for task in protocol["tasks"]:
        task_id = task["task_id"]
        mujoco_task = mujoco_report["tasks"][task_id]
        genesis_task = genesis_report["tasks"][task_id]
        if mujoco_task["scenario_count"] != genesis_task["scenario_count"]:
            raise ContactReplayError(f"{task_id} runtime scenario counts differ")
        rows = [
            scenario_comparison(task, left, right)
            for left, right in zip(
                mujoco_task["scenarios"], genesis_task["scenarios"]
            )
        ]
        all_rows.extend(rows)
        task_summaries[task_id] = summarize_rows(
            rows,
            resamples=resamples,
            base_seed=base_seed,
            label=task_id,
        )
        for runtime_id, runtime_task in (
            ("mujoco", mujoco_task),
            ("genesis", genesis_task),
        ):
            contact_totals[runtime_id][task_id] = sum(
                sum(bool(value) for values in row["trajectory"]["contacts"].values() for value in values)
                for row in runtime_task["scenarios"]
            )

    aggregate = summarize_rows(
        all_rows,
        resamples=resamples,
        base_seed=base_seed,
        label="aggregate",
    )
    acceptance = protocol["acceptance"]
    checks = {
        "required_runtimes_tested": all(
            report.get("tested") is True
            for report in (mujoco_report, genesis_report)
        ),
        "required_task_count": len(task_summaries)
        >= int(acceptance["required_task_count"]),
        "minimum_scenarios_per_task": all(
            summary["scenario_count"]
            >= int(acceptance["minimum_scenarios_per_task"])
            for summary in task_summaries.values()
        ),
        "contact_observed_in_every_runtime_task": all(
            count >= int(acceptance["minimum_contact_samples_per_runtime_task"])
            for runtime_totals in contact_totals.values()
            for count in runtime_totals.values()
        ),
        "finite_aggregate_metrics": all(
            math.isfinite(float(metric["estimate"]))
            and math.isfinite(float(metric["ci_low"]))
            and math.isfinite(float(metric["ci_high"]))
            for key, metric in aggregate.items()
            if key != "scenario_count"
        ),
    }
    return {
        "aggregate": aggregate,
        "contact_positive_sample_totals": contact_totals,
        "per_scenario": all_rows,
        "tasks": task_summaries,
        "acceptance": {
            "checks": checks,
            "pass": all(checks.values()),
        },
    }


def readme_text(report: dict[str, Any]) -> str:
    analysis = report["analysis"]
    aggregate = analysis["aggregate"]
    return f"""# Contact-Rich Cross-Simulator Replay

Status: `{report["status"]}`.

The preregistered protocol executes a straight push and a parallel-jaw capture over
{aggregate["scenario_count"]} initial-state scenarios in both MuJoCo and Genesis. Both runtimes
receive the same primitive world parameters, initial states, sampled actor poses, and clock. MuJoCo
is the metric reference only; it is not physical ground truth.

## Aggregate results

- Object trajectory position RMSE:
  {aggregate["trajectory_position_rmse_m"]["estimate"]:.6f} m
  (95% scenario-bootstrap CI
  [{aggregate["trajectory_position_rmse_m"]["ci_low"]:.6f},
  {aggregate["trajectory_position_rmse_m"]["ci_high"]:.6f}]).
- Contact precision / recall / F1:
  {aggregate["contact_precision"]["estimate"]:.3f} /
  {aggregate["contact_recall"]["estimate"]:.3f} /
  {aggregate["contact_f1"]["estimate"]:.3f}.
- Final object position error:
  {aggregate["final_position_error_m"]["estimate"]:.6f} m
  (95% CI
  [{aggregate["final_position_error_m"]["ci_low"]:.6f},
  {aggregate["final_position_error_m"]["ci_high"]:.6f}]).
- Task-outcome agreement:
  {aggregate["task_outcome_agreement"]["estimate"]:.3f}
  (95% CI
  [{aggregate["task_outcome_agreement"]["ci_low"]:.3f},
  {aggregate["task_outcome_agreement"]["ci_high"]:.3f}]).

## Reproduce

```bash
{report["reproduce"]}
```

The committed runtime reports retain every object pose, contact sample, grasp-state sample, and
scenario outcome. The report does not claim simulator-equivalent physics or hardware validity.
"""


def run_runtime_worker(
    runtime_id: str,
    protocol_path: Path,
    output_path: Path,
) -> None:
    protocol = load_json(protocol_path)
    validate_protocol(protocol)
    if runtime_id == "mujoco":
        payload = run_mujoco(protocol)
    elif runtime_id == "genesis":
        payload = run_genesis(protocol)
    else:
        raise ContactReplayError(f"unknown runtime: {runtime_id}")
    write_json(output_path, payload)


def reproduction_command() -> str:
    return (
        "UV_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu "
        "uv run --isolated --python 3.11 --index-strategy unsafe-best-match "
        "--with 'torch==2.8.0+cpu' --with 'numpy==2.4.6' "
        "--with 'mujoco==3.3.7' --with 'genesis-world==1.2.2' "
        "python tools/contact_rich_cross_sim_replay.py --required"
    )


def execute_protocol(protocol_path: Path, output_dir: Path) -> dict[str, Any]:
    protocol = load_json(protocol_path)
    validate_protocol(protocol)
    preregistration = protocol_preregistration(protocol_path)
    started = time.monotonic()
    runtime_reports = {}
    runtime_artifacts = {}
    with tempfile.TemporaryDirectory(prefix="worldepisode-contact-replay-") as tmp:
        temp_dir = Path(tmp)
        for runtime_id in RUNTIME_IDS:
            temp_output = temp_dir / f"{runtime_id}_runtime_report.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--runtime",
                    runtime_id,
                    "--protocol",
                    str(protocol_path.resolve()),
                    "--runtime-output",
                    str(temp_output),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            log_path = output_dir / f"{runtime_id}_runtime.log"
            write_text(log_path, completed.stdout + completed.stderr)
            if completed.returncode or not temp_output.is_file():
                raise ContactReplayError(
                    f"{runtime_id} runtime failed; inspect {relative(log_path)}"
                )
            destination = output_dir / f"{runtime_id}_runtime_report.json"
            destination.write_bytes(temp_output.read_bytes())
            runtime_reports[runtime_id] = load_json(destination)
            runtime_artifacts[runtime_id] = {
                "path": relative(destination),
                "sha256": sha256_file(destination),
                "log": relative(log_path),
            }

    analysis = normalize_numeric(
        compare_runtime_reports(
            protocol,
            runtime_reports["mujoco"],
            runtime_reports["genesis"],
        )
    )
    preregistration_check = bool(preregistration["committed_before_required_execution"])
    analysis["acceptance"]["checks"]["protocol_committed_before_required_execution"] = (
        preregistration_check
    )
    analysis["acceptance"]["pass"] = all(
        analysis["acceptance"]["checks"].values()
    )
    report = {
        "profile": "worldepisode-contact-rich-cross-simulator-replay-report-0.1",
        "status": (
            "contact_rich_cross_simulator_replay_complete"
            if analysis["acceptance"]["pass"]
            else "contact_rich_cross_simulator_replay_incomplete"
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository_commit": git_output("rev-parse", "HEAD"),
        "protocol": preregistration,
        "runtime_artifacts": runtime_artifacts,
        "runtime_manifests": {
            runtime_id: runtime_reports[runtime_id]["runtime_manifest"]
            for runtime_id in RUNTIME_IDS
        },
        "analysis": analysis,
        "wall_time_seconds": time.monotonic() - started,
        "reproduce": reproduction_command(),
        "claim_boundary": protocol["claim_boundary"],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / DEFAULT_REPORT.name, report)
    write_text(output_dir / "README.md", readme_text(report))
    return report


def check_committed_report(
    protocol_path: Path,
    report_path: Path,
    *,
    required: bool,
) -> bool:
    if not report_path.is_file():
        if required:
            raise ContactReplayError(f"missing required report: {relative(report_path)}")
        return False
    protocol = load_json(protocol_path)
    validate_protocol(protocol)
    report = load_json(report_path)
    if report.get("protocol", {}).get("protocol_sha256") != sha256_file(protocol_path):
        raise ContactReplayError("committed report protocol digest is stale")
    runtime_reports = {}
    for runtime_id in RUNTIME_IDS:
        artifact = report.get("runtime_artifacts", {}).get(runtime_id, {})
        path = ROOT / artifact.get("path", "")
        if not path.is_file() or sha256_file(path) != artifact.get("sha256"):
            raise ContactReplayError(f"{runtime_id} runtime artifact is missing or stale")
        runtime_reports[runtime_id] = load_json(path)
    expected_analysis = normalize_numeric(
        compare_runtime_reports(
            protocol,
            runtime_reports["mujoco"],
            runtime_reports["genesis"],
        )
    )
    expected_analysis["acceptance"]["checks"][
        "protocol_committed_before_required_execution"
    ] = bool(report["protocol"].get("committed_before_required_execution"))
    expected_analysis["acceptance"]["pass"] = all(
        expected_analysis["acceptance"]["checks"].values()
    )
    if not analyses_equivalent(report.get("analysis"), expected_analysis):
        raise ContactReplayError("committed report analysis is not reproducible from raw reports")
    if required and report["analysis"]["acceptance"]["pass"] is not True:
        raise ContactReplayError("required contact-rich replay acceptance gate did not pass")
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--required", action="store_true")
    parser.add_argument("--runtime", choices=RUNTIME_IDS, help=argparse.SUPPRESS)
    parser.add_argument("--runtime-output", type=Path, help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.runtime:
            if args.runtime_output is None:
                raise ContactReplayError("--runtime-output is required for runtime workers")
            run_runtime_worker(args.runtime, args.protocol, args.runtime_output)
            return 0
        report_path = args.output_dir / DEFAULT_REPORT.name
        if args.check:
            current = check_committed_report(
                args.protocol,
                report_path,
                required=args.required,
            )
            print("Contact-rich replay report is current." if current else "No report available.")
            return 0
        report = execute_protocol(args.protocol, args.output_dir)
        print(
            f"Wrote {relative(report_path)} "
            f"(acceptance={report['analysis']['acceptance']['pass']})."
        )
        if args.required and report["analysis"]["acceptance"]["pass"] is not True:
            return 1
        return 0
    except (ContactReplayError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"contact-rich replay error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
