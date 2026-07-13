# Meta-Simulator Contract

Status: runtime-neutral adapter contract.

WorldEpisode does not privilege MuJoCo, Isaac Sim, Genesis, SAPIEN, or any future simulator. A
simulator becomes a trusted target only through an adapter that preserves the same sidecar
invariants and emits replay/loss evidence.

## Compliance Layers

| Layer | Name | Requirement IDs |
|---|---|---|
| `META-SIM.001` | invariant_interface | WORLD.001, TRACE.001, FRAME.001, FRAME.002, TIME.001, TIME.002, ENTITY.001, REP.001, ACTION.001, ACTION.002, ASSET.001, QUALITY.001 |
| `META-SIM.002` | asynchronous_schema_extension | REP.001, ENTITY.001, PROV.001, CONVERT.001 |
| `META-SIM.003` | deterministic_replay_accountability | REPLAY.001, ACTION.002, ACTION.004, TIME.002, CONVERT.001 |

## Runtime Targets

| Runtime | Adapter Status | Implemented Layers | Claim Boundary |
|---|---|---|---|
| mujoco | tested_replay_and_urdf_studio_episode_backend | META-SIM.001, META-SIM.003 | WorldEpisode has a minimal six-joint MuJoCo replay adapter for the LeRobot trace; URDF Studio also tests MuJoCo as an episode backend in the shared scenario runner. |
| isaac_sim | adapter_contract_ready_untested | META-SIM.001, META-SIM.003 | Adapter mapping only; no Isaac runtime result is claimed. |
| genesis | tested_replay_and_urdf_studio_episode_backend | META-SIM.001, META-SIM.003 | Genesis is tested on the same LeRobot trace with a minimal position-servo adapter and separately as a URDF Studio episode backend. This is not a contact-rich task rollout and does not claim Isaac or SAPIEN coverage. |
| sapien | adapter_required | none | No SAPIEN adapter or runtime result is claimed. |

## Rule

WorldEpisode certifies adapter conformance, not simulator quality in the abstract. If a simulator
cannot ingest the invariant interface, declare extensions, and report deterministic replay
assumptions, then its dataset export is not replay-safe under the WorldEpisode profile.
