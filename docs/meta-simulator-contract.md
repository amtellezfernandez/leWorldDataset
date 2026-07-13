# Meta-Simulator Contract

Status: runtime-neutral adapter architecture.

WorldEpisode is not a MuJoCo, Isaac, Genesis, or SAPIEN format. It is a meta-simulator data
contract: a simulator becomes a trusted target by implementing an adapter that preserves the same
world-episode invariants, extension rules, replay assumptions, and conversion-loss reports.

Run:

```bash
python3 tools/meta_simulator_contract.py
```

The generated artifact is:

- `docs/experiments/meta_simulator_contract/adapter_contract_report.json`;
- `docs/experiments/meta_simulator_contract/README.md`.

## Compliance Layers

1. **Invariant interface**

   The adapter must ingest WorldEpisode's immutable world revision, frame/clock graph, action
   channels, entity IDs, representation roles, asset digests, quality records, and provenance.

2. **Asynchronous schema extension**

   Runtime-specific capabilities such as deformables, cloth, fluids, custom contact models, or
   procedural scene generation can be registered as extensions. They cannot weaken the core
   sidecar contract.

3. **Deterministic replay accountability**

   The adapter must record simulator identity, version, solver, timestep, actuator parameters,
   initialization state, command/effective timing, latency model, tolerance envelope, and measured
   divergence.

## Current Runtime Matrix

The current evidence is intentionally scoped:

- MuJoCo: tested minimal six-joint WorldEpisode position-servo replay adapter, plus URDF Studio
  episode-backend conformance and one carton-sorting scenario run.
- Isaac Sim: adapter mapping emitted and ready, but untested in this environment.
- Genesis: tested in URDF Studio as an episode backend using the same `SimBackend` conformance
  suite and one MuJoCo--Genesis carton-sorting comparison; not yet tested on the WorldEpisode
  LeRobot control-replay trace.
- SAPIEN: adapter required; no replay runtime result claimed.

URDF Studio evidence recorded in the generated report:

- Branch/commit observed locally: `paper/cross-sim-benchmark` at `99f1bf0`.
- Conformance command: `.venv/bin/python3 -m pytest backend/tests/test_sim_backend_conformance.py backend/tests/test_scenario_run_orchestrator.py backend/tests/test_scenario_runner_mujoco.py backend/tests/test_world_layout_transfer_check_script.py`
- Result: `24 passed, 12 warnings in 27.22s`.
- Cross-sim command: `.venv/bin/python3 -m backend.scripts.scenario_run scenarios/carton_sorting_0001 --sim mujoco --sim genesis --out /tmp/urdf-studio-cross-sim-smoke --episodes 1`.
- Result: both MuJoCo and Genesis completed one episode successfully; task-success agreement was
  `1.0`, final carton position delta was `0.0597 m`, and divergence onset was localized at
  `60 ms` on joint RMSE.

This is the useful power move: WorldEpisode judges adapter compliance, not simulator brand. A
runtime can be fast, photorealistic, or physically rich and still be unusable for auditable robot
learning if it cannot preserve the episode contract.
