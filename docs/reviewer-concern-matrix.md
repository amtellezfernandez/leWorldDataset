# Reviewer Concern Matrix

Status: living audit for the paper and reference release.

This file tracks the concerns that still matter for an IROS/ICRA-style review. A concern is treated
as closed only when there is executable evidence, a committed artifact, and paper text that states
the claim at the same scope as the evidence.

| Concern | Current evidence | Current paper status | Remaining closure gate |
|---|---|---|---|
| "This is only infrastructure." | Five-graph contract, conformance requirements, validators, binding artifacts, leakage/replay/conversion experiments. | Mitigated. Discussion frames the contribution as falsifiable invariants rather than an SDK. | Independent adapter or dataset using the invariants without relying on the original implementation. |
| Offline leakage is not real robot success. | ArmnetBench LeRobot audit over 400 teleoperated reference episodes; random split leakage 1.000; scene-disjoint leakage 0.000; Torch BC probe drops 0.850 to 0.000 offline score; ACT/Diffusion gate now emits LeRobot-native jobs and rollout requirements. | Mitigated by scope. Abstract, evaluation, and limitations call this an offline imitation probe and mark the stronger policy gate open. | Materialize the split datasets, run ACT/Diffusion jobs, then evaluate in high-fidelity simulation or on hardware. |
| LeRobot round trip is too small. | Active pinned batch round trips over `lerobot/svla_so101_pickplace` and `lerobot/pusht`, episodes 0--4 each; 1,935 action/state rows; action/state/timestamp/index/video timestamp max error 0.0; source-absent fields tracked. | Closed for current scope. Evaluation calls this a two-dataset batch audit, not broad LeRobot coverage. | Extend only if claiming broad LeRobot coverage beyond the current paper scope. |
| Policy baseline is weak. | Executable Torch MLP BC probe over real LeRobot tensors plus `tools/lerobot_policy_leakage_gate.py`, which prepares ACT and Diffusion Policy jobs for the same split manifest. | Mitigated but open. The paper avoids claiming state-of-the-art policy impact. | Run the generated ACT/Diffusion jobs and commit train, offline eval, and rollout reports. |
| Replay experiment is narrow. | Real SO-101 trajectory alignment; inferred 4-frame delay; validation RMSE 4.732 to 1.862 deg; MuJoCo replay 3.425 to 1.563 deg; Isaac mapping emitted but untested. | Mitigated by scope. Limitations state one trace, one MuJoCo adapter, Isaac untested. | Run at least two trajectories, a second robot/dataset, and an Isaac or second-simulator replay with declared tolerance envelopes. |
| Validator faults are synthetic. | 14 injected requirement faults; precision 0.933, recall 1.000; two independent hand-authored invalid fixtures; pilot natural-source corpus over three public LeRobot-format datasets with nine cases. | Mitigated but not closed. Evaluation and limitations distinguish the pilot corpus from a full prevalence survey. | Extend to at least five public datasets and record maintainer agreement/disagreement with representative diagnostics. |
| Binding-retention metric looks subjective. | Predeclared 23-field semantic projection stored in `tools/run_experiments.py` and `docs/experiments/results.json`; native and sidecar artifacts checked by reimport. | Mitigated by scope. The paper calls it a pilot projection, not a universal score. | Publish the projection as a versioned conformance profile and obtain external review or an independent implementation. |
| "Why not just USD/ROS/Rerun?" | Architecture and bindings show native containers as targets/views; sidecar captures action/task/lineage/replay semantics not owned by a single container. | Mitigated. Paper explicitly avoids replacement framing. | Demonstrate a round trip through at least two independently maintained native containers with loss reports. |
| No independent adoption. | Public schema, governance draft, fixtures, examples, and artifacts exist. | Open. Limitations state no independent implementation or external dataset release yet. | Secure one independent reader/exporter or one external WorldEpisode-compatible dataset. |
| Too broad for version 1. | Paper and spec scope v0 to rigid tabletop manipulation with fixed-base single- or dual-arm robots. | Mitigated. Limitations table names unsupported domains. | Keep humanoids, locomotion, deformables, fluids, and multi-agent support out of v0 conformance claims. |

## Next Empirical Gates

1. **ACT/Diffusion leakage gate**
   - Input: `docs/experiments/lerobot_scene_leakage/split_manifest.json`.
   - Required output: random-vs-scene-disjoint policy results using at least one LeRobot-native
     sequence model.
   - Current output: `tools/lerobot_policy_leakage_gate.py` writes ACT and Diffusion job specs,
     episode allowlists, rollout requirements, and `docs/experiments/lerobot_policy_gate/policy_gate_report.json`.
   - Remaining output: materialized split datasets, trained checkpoints, offline action metrics,
     and high-fidelity simulator or physical rollout reports.
   - Claim unlocked: lineage-safe splitting affects a stronger robot-learning baseline, not only a
     Torch MLP probe.

2. **Multi-episode conversion gate**
   - Input: two public LeRobot datasets with pinned revisions.
   - Command for the first dataset:
     `python3 tools/lerobot_worldepisode_roundtrip.py --required --batch-episode-indices 0,1,2,3,4`.
   - Command for the second dataset:
     `python3 tools/lerobot_worldepisode_roundtrip.py --required --repo-id lerobot/pusht --revision 7628202a2180972f291ba1bc6723834921e72c19 --output-dir docs/experiments/lerobot_worldepisode_roundtrip_pusht --batch-episode-indices 0,1,2,3,4 --max-download-mb 4`.
   - Current output: per-episode round-trip reports and aggregate equality/error tables in
     `docs/experiments/lerobot_worldepisode_roundtrip/batch_roundtrip_report.json` for
     `lerobot/svla_so101_pickplace` episodes 0--4 and
     `docs/experiments/lerobot_worldepisode_roundtrip_pusht/batch_roundtrip_report.json` for
     `lerobot/pusht` episodes 0--4.
   - Remaining output: none for current scope.
   - Claim unlocked: active conversion is more than a one-episode or one-dataset smoke test.

3. **Natural failure corpus gate**
   - Input: at least five public robot-learning datasets.
   - Required output: requirement failure counts, example diagnostics, false-positive review, and
     maintainer feedback when available.
   - Current output: `docs/experiments/natural_failure_corpus/manifest.json` records nine
     natural-source cases across `lerobot/svla_so101_pickplace`, `lerobot/pusht`, and
     `armnet/armnetbench_v01_lerobot_so101`.
   - Remaining output: at least two more public datasets plus maintainer feedback or explicit
     disagreement records.
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
