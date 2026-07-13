#!/usr/bin/env python3
"""Replay a real LeRobot trajectory with a WorldEpisode control-timing contract.

The experiment reads the public LeRobot v3 episode materialized by
`tools/lerobot_worldepisode_roundtrip.py`, estimates the effective command delay from the
timestamped action/state streams, and compares naive command-time replay against
WorldEpisode timestamp-aware replay in MuJoCo and Genesis.

Isaac is intentionally not executed here. The report emits an adapter-ready control contract for
Isaac, but marks the backend untested until an Isaac environment is available.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DATA = (
    ROOT
    / "docs"
    / "experiments"
    / "lerobot_worldepisode_roundtrip"
    / "exported_lerobot_v3"
    / "data"
    / "chunk-000"
    / "file-000.parquet"
)
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "experiments" / "lerobot_control_replay"
CALIBRATION_FRACTION = 0.6
MAX_DELAY_FRAMES = 7
GENESIS_PYTHON_ENV = "WORLDEPISODE_GENESIS_PYTHON"


GENESIS_WORKER = r"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np


def build_mjcf(path: Path, *, timestep_s: float, joint_count: int, kp: float, kv: float) -> None:
    bodies = []
    actuators = []
    for index in range(joint_count):
        bodies.append(
            f'<body name="link_{index}" pos="0 0 {0.03 * index:.3f}">'
            f'<joint name="joint_{index}" type="hinge" axis="0 0 1" damping="0.1" armature="0.01"/>'
            '<geom type="sphere" size="0.01" mass="0.05"/>'
            "</body>"
        )
        actuators.append(
            f'<position name="actuator_{index}" joint="joint_{index}" kp="{kp}" kv="{kv}" '
            'ctrllimited="true" ctrlrange="-3.5 3.5"/>'
        )
    path.write_text(
        "<mujoco>"
        f'<option timestep="{timestep_s}" integrator="implicit" gravity="0 0 0"/>'
        f"<worldbody>{''.join(bodies)}</worldbody>"
        f"<actuator>{''.join(actuators)}</actuator>"
        "</mujoco>",
        encoding="utf-8",
    )


def to_numpy(value):
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    elif hasattr(value, "cpu"):
        value = value.cpu().numpy()
    return np.asarray(value, dtype=np.float64).reshape(-1)


def rmse(predicted, target) -> float:
    return float(np.sqrt(np.mean((np.asarray(predicted) - np.asarray(target)) ** 2)))


def main() -> int:
    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    actions_deg = np.asarray(payload["actions_deg"], dtype=np.float64)
    states_deg = np.asarray(payload["states_deg"], dtype=np.float64)
    timestep_s = float(payload["timestep_s"])
    joint_count = int(states_deg.shape[1])
    delay_frames = int(payload["delay_frames"])
    kp = float(payload["kp"])
    kv = float(payload["kv"])

    import genesis as gs

    gs.init(backend=gs.cpu, precision="32", logging_level="warning")
    model_path = output_path.with_suffix(".mjcf.xml")
    build_mjcf(model_path, timestep_s=timestep_s, joint_count=joint_count, kp=kp, kv=kv)
    scene = gs.Scene(
        show_viewer=False,
        sim_options=gs.options.SimOptions(dt=timestep_s, gravity=(0.0, 0.0, 0.0)),
        profiling_options=gs.options.ProfilingOptions(show_FPS=False),
    )
    robot = scene.add_entity(gs.morphs.MJCF(file=str(model_path)), name="robot")
    scene.build()
    dof_indices = list(range(joint_count))
    actions_rad = np.deg2rad(actions_deg)
    initial_rad = np.deg2rad(states_deg[0])

    def simulate(delay: int):
        robot.set_dofs_position(initial_rad, dofs_idx_local=dof_indices)
        if hasattr(robot, "zero_all_dofs_velocity"):
            robot.zero_all_dofs_velocity()
        predicted = []
        for index in range(len(states_deg)):
            command_index = max(0, index - delay)
            robot.control_dofs_position(actions_rad[command_index], dofs_idx_local=dof_indices)
            scene.step()
            predicted.append(np.rad2deg(to_numpy(robot.get_dofs_position())))
        return np.asarray(predicted)

    naive = simulate(0)
    aware = simulate(delay_frames)
    output = {
        "backend": "genesis",
        "tested": True,
        "ready": True,
        "model": "minimal six-joint MJCF position-servo adapter",
        "runtime": {
            "genesis_version": getattr(gs, "__version__", "unknown"),
            "backend": "cpu",
            "python_executable": sys.executable,
        },
        "kp": kp,
        "kv": kv,
        "timestep_s": timestep_s,
        "naive_command_time": {
            "joint_rmse_deg": rmse(naive, states_deg),
            "final_joint_rmse_deg": rmse(naive[-1], states_deg[-1]),
        },
        "timestamp_aware": {
            "joint_rmse_deg": rmse(aware, states_deg),
            "final_joint_rmse_deg": rmse(aware[-1], states_deg[-1]),
        },
    }
    output["rmse_improvement_over_naive"] = (
        output["naive_command_time"]["joint_rmse_deg"]
        / max(output["timestamp_aware"]["joint_rmse_deg"], 1e-12)
    )
    output_path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


class ControlReplayUnavailable(RuntimeError):
    """Raised when optional replay dependencies are missing."""


def require_pyarrow() -> Any:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ControlReplayUnavailable(
            "pyarrow is required. Install experiment dependencies with "
            "`python3 -m pip install -r requirements-experiments.txt` or run through "
            "`uv run --with-requirements requirements-experiments.txt`."
        ) from exc
    return pq


def require_mujoco() -> Any:
    try:
        import mujoco
    except ImportError as exc:
        raise ControlReplayUnavailable(
            "mujoco is required for the tested replay adapter. Install experiment dependencies with "
            "`python3 -m pip install -r requirements-experiments.txt` or run through "
            "`uv run --with-requirements requirements-experiments.txt`."
        ) from exc
    return mujoco


def default_genesis_python() -> Path | None:
    configured = os.environ.get(GENESIS_PYTHON_ENV, "").strip()
    if configured:
        return Path(configured)
    sibling = ROOT.parent / "urdf-studio" / ".venv" / "bin" / "python3"
    if sibling.is_file():
        return sibling
    discovered = shutil.which("python3")
    return Path(discovered) if discovered else None


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_lerobot_trace(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    pq = require_pyarrow()
    table = pq.read_table(path, columns=["action", "observation.state", "timestamp"]).to_pydict()
    return (
        np.asarray(table["action"], dtype=np.float64),
        np.asarray(table["observation.state"], dtype=np.float64),
        np.asarray(table["timestamp"], dtype=np.float64),
    )


def alignment_rmse_by_delay(
    actions: np.ndarray,
    states: np.ndarray,
    start: int,
    end: int,
    max_delay_frames: int,
) -> list[dict[str, Any]]:
    rows = []
    for delay_frames in range(max_delay_frames + 1):
        predicted = []
        target = []
        for index in range(start, end):
            predicted.append(actions[max(0, index - delay_frames)])
            target.append(states[index])
        error = float(np.sqrt(np.mean((np.asarray(predicted) - np.asarray(target)) ** 2)))
        rows.append({"delay_frames": delay_frames, "joint_rmse_deg": error})
    return rows


def best_delay(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return min(rows, key=lambda row: row["joint_rmse_deg"])


def mujoco_xml(timestep_s: float, joint_count: int, kp: float, kv: float) -> str:
    bodies = []
    actuators = []
    for index in range(joint_count):
        bodies.append(
            f'<body name="link_{index}" pos="0 0 {0.03 * index:.3f}">'
            f'<joint name="joint_{index}" type="hinge" axis="0 0 1" damping="0.1" armature="0.01"/>'
            '<geom type="sphere" size="0.01" mass="0.05"/>'
            "</body>"
        )
        actuators.append(
            f'<position name="actuator_{index}" joint="joint_{index}" kp="{kp}" kv="{kv}" '
            'ctrllimited="true" ctrlrange="-3.5 3.5"/>'
        )
    return (
        "<mujoco>"
        f'<option timestep="{timestep_s}" integrator="implicit" gravity="0 0 0"/>'
        f"<worldbody>{''.join(bodies)}</worldbody>"
        f"<actuator>{''.join(actuators)}</actuator>"
        "</mujoco>"
    )


def run_mujoco_position_servo(
    actions_deg: np.ndarray,
    states_deg: np.ndarray,
    timestep_s: float,
    delay_frames: int,
    kp: float,
    kv: float,
) -> dict[str, Any]:
    mujoco = require_mujoco()
    model = mujoco.MjModel.from_xml_string(mujoco_xml(timestep_s, states_deg.shape[1], kp, kv))
    data = mujoco.MjData(model)
    data.qpos[:] = np.deg2rad(states_deg[0])
    mujoco.mj_forward(model, data)
    action_rad = np.deg2rad(actions_deg)
    predicted = []
    for index in range(len(states_deg)):
        command_index = max(0, index - delay_frames)
        data.ctrl[:] = action_rad[command_index]
        mujoco.mj_step(model, data)
        predicted.append(np.rad2deg(data.qpos.copy()))
    predicted_arr = np.asarray(predicted)
    return {
        "joint_rmse_deg": float(np.sqrt(np.mean((predicted_arr - states_deg) ** 2))),
        "final_joint_rmse_deg": float(np.sqrt(np.mean((predicted_arr[-1] - states_deg[-1]) ** 2))),
    }


def run_genesis_position_servo(
    actions_deg: np.ndarray,
    states_deg: np.ndarray,
    timestep_s: float,
    delay_frames: int,
    kp: float,
    kv: float,
    genesis_python: Path | None,
) -> dict[str, Any]:
    if genesis_python is None or not genesis_python.is_file():
        return {
            "backend": "genesis",
            "tested": False,
            "ready": False,
            "reason": (
                f"Genesis Python runtime not found. Set {GENESIS_PYTHON_ENV} to a Python "
                "environment with Genesis installed."
            ),
        }
    with tempfile.TemporaryDirectory(prefix="worldepisode-genesis-replay-") as tmp:
        tmp_dir = Path(tmp)
        input_path = tmp_dir / "input.json"
        worker_path = tmp_dir / "genesis_worker.py"
        output_path = tmp_dir / "genesis_report.json"
        input_path.write_text(
            json.dumps(
                {
                    "actions_deg": actions_deg.tolist(),
                    "states_deg": states_deg.tolist(),
                    "timestep_s": timestep_s,
                    "delay_frames": delay_frames,
                    "kp": kp,
                    "kv": kv,
                }
            ),
            encoding="utf-8",
        )
        worker_path.write_text(GENESIS_WORKER, encoding="utf-8")
        completed = subprocess.run(
            [str(genesis_python), str(worker_path), str(input_path), str(output_path)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=300,
        )
        if completed.returncode != 0 or not output_path.is_file():
            return {
                "backend": "genesis",
                "tested": False,
                "ready": True,
                "python_executable": genesis_python.name,
                "reason": "Genesis replay worker failed.",
                "worker_returncode": completed.returncode,
                "worker_stdout_tail": completed.stdout[-2000:],
                "worker_stderr_tail": completed.stderr[-2000:],
            }
        report = json.loads(output_path.read_text(encoding="utf-8"))
        report["python_executable"] = genesis_python.name
        if isinstance(report.get("runtime"), dict):
            report["runtime"]["python_executable"] = Path(
                str(report["runtime"].get("python_executable", genesis_python.name))
            ).name
        report["claim_boundary"] = (
            "Same LeRobot replay trace and action timing contract as MuJoCo, using a minimal "
            "Genesis MJCF position-servo adapter. This is still a simple joint replay, not a "
            "task-level contact-rich hardware rollout."
        )
        return report


def build_action_contract(sample_period_s: float, effective_delay_frames: int) -> dict[str, Any]:
    latency_s = sample_period_s * effective_delay_frames
    return {
        "profile": "worldepisode-control-loop-0.1",
        "source_binding": "lerobot-v3",
        "control_mode": "joint_position",
        "parameterization": "absolute_joint_vector",
        "units": "position_units_inferred_degrees",
        "command_rate_hz": 1.0 / sample_period_s,
        "policy_output_timestamp_semantics": "policy inference output time; may be asynchronous",
        "action_enqueue_timestamp_semantics": "command enters an action queue/chunk buffer",
        "queue_consume_timestamp_semantics": "fixed-rate low-level control loop consumes the selected command",
        "motor_receive_timestamp_semantics": "estimated effective motor target time",
        "effective_timestamp_semantics": (
            "effective_time = sample_timestamp + "
            f"{effective_delay_frames} sample periods"
        ),
        "latency_model": {
            "type": "constant_frame_delay",
            "delay_frames": effective_delay_frames,
            "delay_s": latency_s,
            "estimated_from": "argmin action[t-delay] -> observation.state[t] joint RMSE on calibration prefix",
        },
        "action_chunking": {
            "chunk_size": "source_absent",
            "horizon": "source_absent",
            "stride": "source_absent",
            "supported_fields": ["chunk_id", "chunk_index", "horizon", "producer_timestamp", "consumer_timestamp"],
        },
        "selection_policy": "latest_valid_command_before_effective_time",
        "interpolation": "zero_order_hold",
        "missing_value_policy": "hold_last",
    }


def run_control_replay_experiment(
    source_data: Path = DEFAULT_SOURCE_DATA,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    genesis_python: Path | None = None,
) -> dict[str, Any]:
    actions, states, timestamps = load_lerobot_trace(source_data)
    if len(actions) < 10:
        raise ValueError("LeRobot trace is too short for replay timing calibration.")

    sample_period_s = float(np.median(np.diff(timestamps)))
    calibration_end = int(len(actions) * CALIBRATION_FRACTION)
    calibration_rows = alignment_rmse_by_delay(actions, states, 0, calibration_end, MAX_DELAY_FRAMES)
    validation_rows = alignment_rmse_by_delay(actions, states, calibration_end, len(actions), MAX_DELAY_FRAMES)
    full_rows = alignment_rmse_by_delay(actions, states, 0, len(actions), MAX_DELAY_FRAMES)
    inferred = best_delay(calibration_rows)
    effective_delay_frames = int(inferred["delay_frames"])
    contract = build_action_contract(sample_period_s, effective_delay_frames)

    mujoco_adapter = {
        "backend": "mujoco",
        "tested": True,
        "model": "minimal six-joint position-servo adapter",
        "kp": 20.0,
        "kv": 1.0,
        "timestep_s": sample_period_s,
    }
    mujoco_naive = run_mujoco_position_servo(actions, states, sample_period_s, delay_frames=0, kp=20.0, kv=1.0)
    mujoco_aware = run_mujoco_position_servo(
        actions,
        states,
        sample_period_s,
        delay_frames=effective_delay_frames,
        kp=20.0,
        kv=1.0,
    )
    genesis = run_genesis_position_servo(
        actions,
        states,
        sample_period_s,
        delay_frames=effective_delay_frames,
        kp=20.0,
        kv=1.0,
        genesis_python=genesis_python if genesis_python is not None else default_genesis_python(),
    )
    validation_naive = next(row for row in validation_rows if row["delay_frames"] == 0)
    validation_aware = next(row for row in validation_rows if row["delay_frames"] == effective_delay_frames)
    report = {
        "available": True,
        "pass": True,
        "source_trace": str(source_data.relative_to(ROOT)),
        "sample_count": int(len(actions)),
        "joint_count": int(actions.shape[1]),
        "sample_period_s": sample_period_s,
        "sample_rate_hz": 1.0 / sample_period_s,
        "calibration_fraction": CALIBRATION_FRACTION,
        "calibration_samples": calibration_end,
        "validation_samples": int(len(actions) - calibration_end),
        "worldepisode_action_contract": contract,
        "alignment": {
            "calibration_by_delay": calibration_rows,
            "validation_by_delay": validation_rows,
            "full_by_delay": full_rows,
            "inferred_effective_delay_frames": effective_delay_frames,
            "inferred_effective_delay_s": sample_period_s * effective_delay_frames,
            "validation_naive_rmse_deg": validation_naive["joint_rmse_deg"],
            "validation_timestamp_aware_rmse_deg": validation_aware["joint_rmse_deg"],
            "validation_improvement_over_naive": (
                validation_naive["joint_rmse_deg"] / max(validation_aware["joint_rmse_deg"], 1e-12)
            ),
        },
        "simulators": {
            "mujoco": {
                **mujoco_adapter,
                "naive_command_time": mujoco_naive,
                "timestamp_aware": mujoco_aware,
                "rmse_improvement_over_naive": (
                    mujoco_naive["joint_rmse_deg"] / max(mujoco_aware["joint_rmse_deg"], 1e-12)
                ),
            },
            "genesis": genesis,
            "isaac": {
                "backend": "isaac-sim",
                "tested": False,
                "ready": True,
                "reason": "Isaac Sim is not installed in this execution environment.",
                "adapter_contract": {
                    "input": "worldepisode_action_contract",
                    "expected_mapping": [
                        "policy_output_timestamp_semantics",
                        "action_enqueue_timestamp_semantics",
                        "queue_consume_timestamp_semantics",
                        "motor_receive_timestamp_semantics",
                        "latency_model",
                        "interpolation",
                    ],
                },
            },
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "control_replay_report.json", report)
    write_json(output_dir / "action_contract.json", contract)
    return report


def unavailable_report(error: Exception) -> dict[str, Any]:
    return {
        "available": False,
        "pass": False,
        "reason": str(error),
        "reproduce": "python3 -m pip install -r requirements-experiments.txt && "
        "python3 tools/lerobot_control_replay_experiment.py --required "
        "(or uv run --with-requirements requirements-experiments.txt python tools/lerobot_control_replay_experiment.py --required)",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-data", type=Path, default=DEFAULT_SOURCE_DATA)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--genesis-python",
        type=Path,
        default=None,
        help=(
            "Python executable with Genesis installed. Defaults to WORLDEPISODE_GENESIS_PYTHON "
            "or ../urdf-studio/.venv/bin/python3 when present."
        ),
    )
    parser.add_argument("--required", action="store_true")
    args = parser.parse_args()
    try:
        report = run_control_replay_experiment(
            source_data=args.source_data,
            output_dir=args.output_dir,
            genesis_python=args.genesis_python,
        )
    except ControlReplayUnavailable as exc:
        report = unavailable_report(exc)
        write_json(args.output_dir / "control_replay_report.json", report)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 1 if args.required else 0
    print(json.dumps(report["alignment"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
