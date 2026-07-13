# WorldEpisode Research Plan

Status: draft.

The paper should answer scientific questions, not only publish a schema.

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
