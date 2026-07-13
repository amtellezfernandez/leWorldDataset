# USS / WorldEpisode Research Plan

Status: draft.

The paper should answer scientific questions, not only publish a schema.

The paper-level frame is Universal Spatial State (USS): a runtime-neutral contract for detecting
silent state drift across embodied and virtual spatial pipelines. WorldEpisode is the concrete
robotics-heavy USS profile. The intended structure is universal theory with grounded proof:
domain-agnostic invariants first, then robotics as the deepest current stress test, plus lightweight
game-engine and autonomous-driving pilots to prevent the broader framing from being purely
aspirational.

## RQ1: Semantic Preservation Across Bindings

Convert the same dataset through:

```text
LeRobot <-> WorldEpisode <-> Rerun
                         <-> NCore
                         <-> MCAP
                         <-> OpenUSD
                         <-> glTF / Gaussian assets
```

Measure field retention, semantic retention, deterministic round-trip equality, externalized fields,
approximated fields, discarded fields, and declared conversion loss.

Current executable artifact: `conformance/projections/uss-core-23.v0.json` externalizes the
23-field semantic projection and pilot binding capability model used by
`tools/run_experiments.py`. The profile is schema-validated and maps each field to conformance
requirements. It remains a pilot projection until reviewed or reimplemented independently.

## RQ2: Physical-Coherence Fault Detection

Inject controlled failures:

- wrong camera transform direction;
- millimeters interpreted as meters;
- quaternion-order mismatch;
- timestamp offset;
- stale calibration revision;
- action in base frame mislabeled as tool frame;
- collision mesh with inconsistent scale;
- reused entity id;
- world revision changed without a new hash.

Measure validator precision, recall, and diagnosis quality.

Preflight adoption artifact: `worldepisode preflight` and the Python APIs
`preflight(...)`, `preflight_lerobot(...)`, and `preflight_rerun(...)` make the validator runnable
as a single blocking line before a costly training job. The committed regression artifact at
`docs/experiments/preflight/preflight_report.json` checks that a valid WorldEpisode manifest passes,
an invalid fixture fails, and native LeRobot/Rerun artifacts without a WorldEpisode sidecar fail
closed on missing physical-semantics controls.

## RQ3: Cross-Simulator Replay

Replay the same demonstrations in at least two simulators.

Measure:

- end-effector trajectory RMSE;
- object trajectory RMSE;
- grasp-state agreement;
- contact-event precision, recall, and F1;
- final-state pose error;
- task-outcome agreement;
- success-rate rank correlation across policy checkpoints.

The claim is replay within a declared tolerance envelope, not bit-identical physics.

Meta-simulator artifact: `tools/meta_simulator_contract.py` defines the runtime-neutral adapter
contract. It separates the invariant interface, asynchronous schema extensions, and deterministic
replay accountability. The current matrix records MuJoCo as one tested minimal adapter, Isaac as an
adapter-ready but untested mapping, and Genesis/SAPIEN as adapter-required targets. The next
scientific step is to run the same WorldEpisode replay contract through a second tested runtime and
measure cross-simulator drift.

Replay-adapter conformance artifact: `tools/replay_adapter_conformance.py` adds a dependency-free
reference scheduler for delay, zero-order hold, missing-command, and asynchronous queue semantics.
It checks whether a runtime adapter honors the action timing contract before it is trusted as a
replay target. This is scheduler conformance only; it does not replace the second tested simulator
required for the full cross-simulator replay claim.

## RQ4: VLA Robustness From World Binding

Train three conditions:

1. observations and actions only;
2. observations/actions plus unstructured 3D side files;
3. full WorldEpisode identity, world alignment, and counterfactual augmentation.

Evaluate shifted camera extrinsics, unseen viewpoints, object displacement, background replacement,
distractor insertion, partial occlusion, lighting changes, novel object instances, and held-out
worlds.

## RQ5: Asset and World Leakage

Compare:

- random episode split;
- task-disjoint split;
- world-disjoint split;
- entity-disjoint split;
- reconstruction-lineage-disjoint split.

The expected contribution is showing how ordinary episode-level splits can overestimate
generalization when reconstructed rooms, objects, Gaussian assets, source videos, or generated
asset families leak across train and evaluation.

Current executable artifact: `tools/lerobot_scene_leakage_experiment.py` runs this audit on
`armnet/armnetbench_v01_lerobot_so101`, derives `world_lineage` hashes for task-scene/camera-layout
groups, and compares random-episode against scene-disjoint splits with a Torch MLP BC baseline.

Scale-out artifact: `tools/benchmark_callout_audit.py` creates a source-level audit over Open
X-Embodiment, DROID, BridgeData V2, LIBERO, and CALVIN. That artifact identifies which famous
benchmarks lack public evidence for lineage-disjoint splits, content-addressed world revisions,
action timing contracts, and replay/loss reports. The next experiment is to convert one benchmark at
a time into a WorldEpisode manifest and rerun a published policy protocol under the corrected split
or timing contract.

Real-to-sim artifact: `tools/realtosim_contract_drift.py` adds a controlled proxy for the
Gaussian/OpenUSD hype cycle. It shows that a drifted action interface can succeed in simulation and
fail under the deployment controller, and that an appearance-only reconstruction can succeed in
simulation while colliding with real foreground geometry when the collision role is dropped. This
does not replace a RoboSnap/DROID-Sim rerun, but it states the methodological claim that visual
reconstruction must be bound to action contracts and representation roles.

## USS Generality Pilots

Use `tools/uss_state_drift_pilots.py` to keep the broader Universal Spatial State claim executable.
The current pilots cover:

- a game-engine collision patch where a client asset remains structurally valid but no longer
  matches the authoritative collision state;
- an autonomous-driving clock-domain offset where camera/lidar logs deserialize correctly but naive
  fusion exceeds the declared spatial tolerance.

These pilots show that state ancestry, asset digests, representation roles, frame/clock mappings,
and transition invariants are not robotics-only concepts. They do not replace measured game-engine
or autonomous-driving dataset experiments.

## End-to-End Demonstration

The strongest demonstration:

1. Record synchronized multi-camera manipulation demonstrations using LeRobot.
2. Preserve device clocks, calibrations, and action timing.
3. Reconstruct the static visual environment as a Gaussian splat.
4. Decompose manipulated objects into persistent entities.
5. Create render, collision, and semantic representations for each entity.
6. Package the base scene as an immutable world revision.
7. Represent object motion, contact, and grasp state as episode deltas and events.
8. Serialize the same semantic episode into LeRobot, Rerun, and NCore bindings.
9. Export the same world to OpenUSD and glTF Gaussian representations.
10. Replay the trajectory in two simulation engines.
11. Generate counterfactual cameras, backgrounds, and object placements.
12. Train a VLA with and without those counterfactual variants.
13. Evaluate on the original real robot.
14. Publish every conversion-loss report and conformance result.
