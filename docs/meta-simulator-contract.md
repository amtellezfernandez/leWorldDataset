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

- MuJoCo: tested minimal six-joint WorldEpisode position-servo replay adapter on the same LeRobot
  trace.
- Isaac Sim: adapter mapping emitted and ready, but untested in this environment.
- Genesis: tested minimal six-joint WorldEpisode position-servo replay adapter on the same
  LeRobot trace.
- SAPIEN: adapter required; no replay runtime result claimed.

External collaboration status: **Not defined yet**.

This is the useful power move: WorldEpisode judges adapter compliance, not simulator brand. A
runtime can be fast, photorealistic, or physically rich and still be unusable for auditable robot
learning if it cannot preserve the episode contract.
