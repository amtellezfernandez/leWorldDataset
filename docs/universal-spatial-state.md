# Universal Spatial State

Status: framing note for the paper.

Universal Spatial State (USS) is the umbrella contract. WorldEpisode is the robotics-heavy profile
implemented in this repository.

The shift from "episode" to "state" changes the scope. An episode is usually a retrospective
recording. A state contract can also describe live synchronization between a simulator, a physical
robot, a game client/server pair, an autonomous-driving replay stack, or a cloud digital twin.

USS focuses on silent state drift: files deserialize and assets load, but the behavioral state is
wrong. Examples include a collision mesh changed by a game-engine patch, an autonomous-driving log
with an undeclared clock-domain offset, or a robot controller interpreting a policy vector under the
wrong action semantics.

## Vocabulary Mapping

| WorldEpisode term | USS term | Meaning |
|---|---|---|
| Base world plus deltas | State ancestry and lineage | The immutable state revision and ordered changes that define what is true at time `t`. |
| Action contract | State transition invariant | The semantics that make a command, control input, or state transition valid. |
| Representation role | State role semantics | Whether an asset is safe for appearance, collision, physics, semantics, supervision, or another role. |
| World-lineage split | State-lineage split | Evaluation splits that prevent shared environments, assets, captures, or generated lineages from leaking. |
| Replay assumptions | Runtime accountability | The solver, timing, adapter, and tolerance assumptions under which a runtime result is meaningful. |

## Paper Strategy

The paper should use a universal theory and grounded proof structure:

1. Introduce USS as a domain-agnostic state-integrity contract for interactive spatial pipelines.
2. Define the five graphs as general invariants: identity, space/time, role semantics, temporal
   state/events, and lineage/provenance.
3. Use robotics as the deep stress test because it combines real hardware, asynchronous control,
   reconstruction assets, simulators, and policy evaluation.
4. Include lightweight non-robotics pilots for game-engine collision drift and AV clock-domain
   drift, while explicitly stating that these are deterministic pilots, not measured industry
   deployments.

## Evidence Boundary

The current strong evidence remains robotics:

- public LeRobot conversion round trips;
- ArmnetBench scene-lineage leakage;
- SO-101 control-loop replay drift;
- MuJoCo timestamp-aware replay;
- validator and preflight artifacts;
- real-to-sim contract drift;
- meta-simulator adapter contract.

The USS-specific evidence is deliberately narrower:

- `docs/experiments/uss_state_drift_pilots/state_drift_report.json`;
- one deterministic game-engine collision-patch pilot;
- one deterministic autonomous-driving clock-domain pilot.

The paper can claim that USS vocabulary applies beyond robotics. It cannot yet claim measured
Epic, Unity, Waymo, autonomous-driving fleet, or production game-engine results.
