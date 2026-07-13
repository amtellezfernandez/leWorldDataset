# Reviewer Concern Matrix

Status: living audit for the paper and reference release.

This file tracks the concerns that still matter for an IROS/ICRA-style review. A concern is treated
as closed only when there is executable evidence, a committed artifact, and paper text that states
the claim at the same scope as the evidence.

| Concern | Current evidence | Current paper status | Remaining closure gate |
|---|---|---|---|
| "This is only infrastructure." | Five-graph contract, conformance requirements, validators, binding artifacts, leakage/replay/conversion experiments. | Mitigated. Discussion frames the contribution as falsifiable invariants rather than an SDK. | Independent adapter or dataset using the invariants without relying on the original implementation. |
| Offline leakage is not real robot success. | ArmnetBench LeRobot audit over 400 teleoperated reference episodes; random split leakage 1.000; scene-disjoint leakage 0.000; Torch BC probe drops 0.850 to 0.000 offline score. | Mitigated by scope. Abstract, evaluation, and limitations call this an offline imitation probe. | Run the committed split manifest with ACT or Diffusion Policy, then evaluate in simulation or on hardware. |
| LeRobot round trip is too small. | Active pinned `lerobot/svla_so101_pickplace` batch round trip over episodes 0--4; 1,197 action/state rows; action/state/timestamp/index/video timestamp max error 0.0; source-absent fields tracked. | Mitigated for one dataset. Evaluation calls this a batch audit, not broad LeRobot coverage. | Repeat on at least a second public LeRobot dataset with pinned revision and committed batch report. |
| Policy baseline is weak. | Executable Torch MLP BC probe over real LeRobot tensors. | Mitigated by scope. The paper avoids claiming state-of-the-art policy impact. | Repeat leakage experiment with LeRobot-native ACT and Diffusion Policy using the same split manifest. |
| Replay experiment is narrow. | Real SO-101 trajectory alignment; inferred 4-frame delay; validation RMSE 4.732 to 1.862 deg; MuJoCo replay 3.425 to 1.563 deg; Isaac mapping emitted but untested. | Mitigated by scope. Limitations state one trace, one MuJoCo adapter, Isaac untested. | Run at least two trajectories, a second robot/dataset, and an Isaac or second-simulator replay with declared tolerance envelopes. |
| Validator faults are synthetic. | 14 injected requirement faults; precision 0.933, recall 1.000; two independent hand-authored invalid fixtures. | Partially mitigated. Limitations identify need for natural failure corpus. | Audit several public datasets for naturally occurring faults and report maintainers' agreement/disagreement with diagnostics. |
| Binding-retention metric looks subjective. | Predeclared 23-field semantic projection stored in `tools/run_experiments.py` and `docs/experiments/results.json`; native and sidecar artifacts checked by reimport. | Mitigated by scope. The paper calls it a pilot projection, not a universal score. | Publish the projection as a versioned conformance profile and obtain external review or an independent implementation. |
| "Why not just USD/ROS/Rerun?" | Architecture and bindings show native containers as targets/views; sidecar captures action/task/lineage/replay semantics not owned by a single container. | Mitigated. Paper explicitly avoids replacement framing. | Demonstrate a round trip through at least two independently maintained native containers with loss reports. |
| No independent adoption. | Public schema, governance draft, fixtures, examples, and artifacts exist. | Open. Limitations state no independent implementation or external dataset release yet. | Secure one independent reader/exporter or one external WorldEpisode-compatible dataset. |
| Too broad for version 1. | Paper and spec scope v0 to rigid tabletop manipulation with fixed-base single- or dual-arm robots. | Mitigated. Limitations table names unsupported domains. | Keep humanoids, locomotion, deformables, fluids, and multi-agent support out of v0 conformance claims. |

## Next Empirical Gates

1. **ACT/Diffusion leakage gate**
   - Input: `docs/experiments/lerobot_scene_leakage/split_manifest.json`.
   - Required output: random-vs-scene-disjoint policy results using at least one LeRobot-native
     sequence model.
   - Claim unlocked: lineage-safe splitting affects a stronger robot-learning baseline, not only a
     Torch MLP probe.

2. **Multi-episode conversion gate**
   - Input: two public LeRobot datasets with pinned revisions.
   - Command for the first dataset:
     `python3 tools/lerobot_worldepisode_roundtrip.py --required --batch-episode-indices 0,1,2,3,4`.
   - Current output: per-episode round-trip reports and aggregate equality/error table in
     `docs/experiments/lerobot_worldepisode_roundtrip/batch_roundtrip_report.json` for
     `lerobot/svla_so101_pickplace` episodes 0--4.
   - Remaining output: repeat on a second public LeRobot dataset with conversion loss reports.
   - Claim unlocked: active conversion is more than a one-episode smoke test for the first dataset.

3. **Natural failure corpus gate**
   - Input: at least five public robot-learning datasets.
   - Required output: requirement failure counts, example diagnostics, false-positive review, and
     maintainer feedback when available.
   - Claim unlocked: conformance catches real dataset problems, not only injected faults.

4. **Second replay backend gate**
   - Input: the WorldEpisode action contract emitted in
     `docs/experiments/lerobot_control_replay/action_contract.json`.
   - Required output: a replay report from Isaac or another simulator, with the same tolerance
     metrics as the MuJoCo report.
   - Claim unlocked: replay assumptions transfer across more than one tested runtime.

5. **Independent implementation gate**
   - Input: `schemas/worldepisode-core-v0.schema.json`, `conformance/fixtures/`, and `spec/`.
   - Required output: a reader/exporter or dataset generated outside this repository that passes
     the public conformance suite.
   - Claim unlocked: the project begins to act like an interoperability profile rather than a
     single-codebase system.
