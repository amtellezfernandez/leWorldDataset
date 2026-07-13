# Reviewer Concern Matrix

Status: living audit for the paper and reference release.

This file tracks the concerns that still matter for an IROS/ICRA-style review. A concern is treated
as closed only when there is executable evidence, a committed artifact, and paper text that states
the claim at the same scope as the evidence.

| Concern | Current evidence | Current paper status | Remaining closure gate |
|---|---|---|---|
| "This is only infrastructure." | Five-graph contract, conformance requirements, validators, binding artifacts, leakage/replay/conversion experiments, and an internal clean-room reader that does not import the reference SDK. | Mitigated. Discussion frames the contribution as falsifiable invariants rather than an SDK. | External independent adapter or dataset using the invariants without relying on the original implementation. |
| Offline leakage is not real robot success. | ArmnetBench LeRobot audit over 400 teleoperated reference episodes; random split leakage 1.000; scene-disjoint leakage 0.000; Torch BC probe drops 0.850 to 0.000 offline score; ACT/Diffusion gate now emits LeRobot-native jobs, virtual split manifests, compact physical state/action split packages, and rollout requirements. | Mitigated by scope. Abstract, evaluation, and limitations call this an offline imitation probe and mark the stronger policy gate open. | Run ACT/Diffusion jobs, then evaluate in high-fidelity simulation or on hardware; mirror source videos first for any vision-policy claim. |
| LeRobot round trip is too small. | Active pinned batch round trips over `lerobot/svla_so101_pickplace` and `lerobot/pusht`, episodes 0--4 each; 1,935 action/state rows; action/state/timestamp/index/video timestamp max error 0.0; source-absent fields tracked. | Closed for current scope. Evaluation calls this a two-dataset batch audit, not broad LeRobot coverage. | Extend only if claiming broad LeRobot coverage beyond the current paper scope. |
| Policy baseline is weak. | Executable Torch MLP BC probe over real LeRobot tensors plus `tools/lerobot_policy_leakage_gate.py`, which prepares ACT and Diffusion Policy jobs and compact physical state/action split packages for the same split manifest. | Mitigated but open. The paper avoids claiming state-of-the-art policy impact. | Run the generated ACT/Diffusion jobs and commit train, offline eval, and rollout reports. |
| Replay experiment is narrow. | Real SO-101 trajectory alignment; inferred 4-frame delay; validation RMSE 4.732 to 1.862 deg; MuJoCo replay 3.425 to 1.563 deg; Isaac mapping emitted but untested; `tools/replay_adapter_conformance.py` checks delay, hold-last, missing-command, and async queue scheduler semantics; URDF Studio separately tests MuJoCo and Genesis episode backends. | Mitigated by scope. Limitations state one WorldEpisode LeRobot replay trace, one WorldEpisode MuJoCo replay adapter, URDF Studio companion backend evidence, Isaac untested, and scheduler conformance only. | Run at least two trajectories, a second robot/dataset, and the same LeRobot replay trace through Genesis, Isaac, or another simulator with declared tolerance envelopes. |
| Runtime-neutral claim overstates evidence. | `tools/meta_simulator_contract.py` defines three adapter compliance layers; WorldEpisode reports MuJoCo replay tested and Isaac ready/untested; URDF Studio `SimBackend` conformance passed for fake, MuJoCo, and Genesis, and a one-episode carton-sorting run produced a MuJoCo--Genesis comparison report; SAPIEN remains adapter-required. | Mitigated for adapter availability. The paper can claim a meta-simulator adapter contract plus MuJoCo/Genesis companion runtime evidence, not equal physics or Isaac/SAPIEN replay evidence. | Bridge the URDF Studio Genesis backend to the WorldEpisode LeRobot replay trace, or run the same replay/contract-drift checks through another tested simulator adapter. |
| USS generality is overbroad. | `tools/uss_state_drift_pilots.py` emits deterministic game-engine collision-patch and autonomous-driving clock-domain pilots, while robotics remains the deep stress test. | Mitigated as framing only. The paper can claim USS vocabulary generalizes, not that production game/AV systems have been benchmarked. | Run at least one public game/simulation telemetry corpus or AV log through a USS adapter and report measured drift diagnostics. |
| Validator faults are synthetic. | 14 injected requirement faults; precision 0.933, recall 1.000; two independent hand-authored invalid fixtures; pilot natural-source corpus over five public datasets with 19 cases. | Mitigated further. Dataset-count gate is met, while maintainer feedback and dataset-specific conversions remain open. | Record maintainer agreement/disagreement for representative diagnostics and convert source-level metadata gaps into dataset-specific manifests where stronger claims are needed. |
| Validator is too tedious to adopt. | `pyproject.toml` packages `worldepisode`; `worldepisode preflight` and `from worldepisode import preflight_lerobot` provide blocking one-line checks; `docs/experiments/preflight/preflight_report.json` covers valid WorldEpisode, invalid WorldEpisode, native LeRobot without sidecar, and Rerun without sidecar. | Mitigated for local/reference adoption. The paper can claim an installable preflight surface, not ecosystem adoption. | Publish to PyPI or merge equivalent hooks upstream in LeRobot/Rerun examples. |
| Dataset design will not scale. | `schemas/worldepisode-dataset-v0.schema.json`, `examples/scalable-corpus.worldepisode-dataset.json`, `tools/dataset_scale_audit.py`, and `tools/dataset_scale_performance.py` validate catalog invariants and benchmark a generated 32,768-shard catalog describing 1,073,741,824 episodes for open/index latency, partition pruning, digest-cache behavior, and resolver routing. | Mitigated as catalog-side evidence. The paper can claim measured generated-catalog behavior, not payload throughput or multi-institution production deployment. | Benchmark payload validation, distributed object storage, cache eviction, concurrent readers, and federation across real institutional datasets. |
| Famous benchmark impact is not demonstrated. | `tools/benchmark_callout_audit.py` audits Open X-Embodiment, DROID, BridgeData V2, LIBERO, and CALVIN for public leakage/timing controls. `tools/benchmark_inflation_gate.py` now separately requires benchmark-specific conversion, split/timing audit, and policy-rerun artifacts before any score-inflation claim. Current measured famous-benchmark inflation claims: 0. | Open but fail-closed. The paper can say these benchmarks require targeted WorldEpisode audits and that the proof gate currently has no valid rerun reports; it must not say their scores are inflated. | Convert at least one famous benchmark into WorldEpisode and rerun a published protocol under lineage-disjoint splits or timestamp-aware replay. |
| Real-to-sim relevance is not concrete. | `tools/realtosim_contract_drift.py` now runs two controlled ablations: action contract drift and representation-role drift. Both succeed in the drifted simulator, fail under deployment proxies, and pass with the WorldEpisode contract. | Mitigated as a controlled proxy. The paper must not call this a RoboSnap/DROID-Sim hardware result. | Run the same checks on a real reconstructed scene from RoboSnap/DROID-Sim, GSDF, or another public real-to-sim pipeline. |
| Binding-retention metric looks subjective. | Versioned `conformance/projections/uss-core-23.v0.json` profile, `schemas/semantic-projection-v0.schema.json`, generated native/sidecar artifacts, and runner validation against field and requirement references. | Mitigated by artifact. The paper can cite a versioned pilot projection, not a universal score. | Obtain external review or an independent implementation that accepts or revises the projection. |
| "Why not just USD/ROS/Rerun?" | Architecture and bindings show native containers as targets/views; sidecar captures action/task/lineage/replay semantics not owned by a single container. | Mitigated. Paper explicitly avoids replacement framing. | Demonstrate a round trip through at least two independently maintained native containers with loss reports. |
| No independent adoption. | Public schema, governance draft, fixtures, examples, artifacts, and `tools/cleanroom_conformance_reader.py`, an internal reader that checks fixtures without importing `worldepisode`. | Open. Limitations state no external implementation or external dataset release yet. | Secure one independent reader/exporter or one external WorldEpisode-compatible dataset. |
| Too broad for version 1. | Paper and spec scope v0 to rigid tabletop manipulation with fixed-base single- or dual-arm robots. | Mitigated. Limitations table names unsupported domains. | Keep humanoids, locomotion, deformables, fluids, and multi-agent support out of v0 conformance claims. |

## Next Empirical Gates

1. **ACT/Diffusion leakage gate**
   - Input: `docs/experiments/lerobot_scene_leakage/split_manifest.json`.
   - Required output: random-vs-scene-disjoint policy results using at least one LeRobot-native
     sequence model.
   - Current output: `tools/lerobot_policy_leakage_gate.py` writes ACT and Diffusion job specs,
     episode allowlists, virtual split manifests with source file digests, compact physical
     state/action LeRobot split packages, rollout requirements, and
     `docs/experiments/lerobot_policy_gate/policy_gate_report.json`.
   - Remaining output: trained checkpoints, offline action metrics, high-fidelity simulator or
     physical rollout reports, and mirrored video assets for any vision-policy result.
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
   - Current output: `docs/experiments/natural_failure_corpus/manifest.json` records 19
     natural-source cases across five public datasets: `lerobot/svla_so101_pickplace`,
     `lerobot/pusht`, `armnet/armnetbench_v01_lerobot_so101`, DROID, and BridgeData V2.
   - Remaining output: maintainer feedback or explicit disagreement records, plus dataset-specific
     WorldEpisode manifests for source-level DROID and BridgeData V2 metadata gaps if making
     stronger benchmark claims.
   - Claim unlocked: conformance catches real dataset problems, not only injected faults.

4. **Famous benchmark call-out gate**
   - Input: Open X-Embodiment, DROID, BridgeData V2, LIBERO, and CALVIN public metadata.
   - Current output: `docs/experiments/benchmark_callout_audit/benchmark_callout_report.json`.
   - Proof gate: `docs/experiments/benchmark_inflation_gate/gate_report.json` records five
     required tests and zero valid famous-benchmark rerun reports. Reproduce the blocking gate with
     `python3 tools/benchmark_inflation_gate.py --required`; it should fail until rerun evidence is
     committed.
   - Remaining output: convert one or more of these benchmarks into WorldEpisode, derive actual
     world/entity/source-capture lineage, and rerun a published policy protocol under corrected
     splits or timestamp-aware replay.
   - Claim unlocked: the leakage/timing finding applies to a celebrated benchmark, not only a
     scoped ArmnetBench audit.

5. **Second replay backend gate**
   - Input: the WorldEpisode action contract emitted in
     `docs/experiments/lerobot_control_replay/action_contract.json`.
   - Current output: `docs/experiments/meta_simulator_contract/adapter_contract_report.json`
     defines adapter compliance layers, records one tested WorldEpisode MuJoCo replay adapter, one
     ready/untested Isaac mapping, and URDF Studio companion evidence where fake, MuJoCo, and
     Genesis pass `SimBackend` conformance and a MuJoCo--Genesis one-episode scenario comparison.
     `docs/experiments/replay_adapter_conformance/adapter_conformance_report.json` adds
     dependency-free scheduler conformance for delay, zero-order hold, missing-command, and async
     queue semantics.
   - Required output: the same LeRobot control-replay trace through Genesis, Isaac, or another
     simulator, with the same tolerance metrics as the MuJoCo report.
   - Claim unlocked: LeRobot replay assumptions transfer across more than one tested runtime.

6. **Dataset-scale performance gate**
   - Input: `examples/scalable-corpus.worldepisode-dataset.json` and a larger generated or public
     dataset catalog.
   - Current output: `docs/experiments/dataset_scale_audit/scale_audit_report.json` validates the
     current scale manifest for resolver coverage, digest-addressed assets, shard/index references,
     split manifests, lineage/digest indexes, and append-only snapshots.
     `docs/experiments/dataset_scale_performance/performance_report.json` benchmarks a generated
     32,768-shard catalog with 1,073,741,824 described episodes.
   - Remaining output: payload validation throughput, distributed object storage behavior,
     concurrent readers, cache eviction, and federation across real institutional datasets.
   - Claim unlocked: the manifest design is not only structurally scalable, but has measured
     generated-catalog open, pruning, cache, and resolver behavior.

7. **Real-to-sim reconstructed-scene gate**
   - Input: one public reconstructed scene from RoboSnap/DROID-Sim, GSDF, or another Gaussian/OpenUSD
     real-to-sim pipeline.
   - Current output: `docs/experiments/realtosim_contract_drift/contract_drift_report.json`
     provides a deterministic proxy over action contracts and representation roles.
   - Remaining output: bind the public reconstructed scene to WorldEpisode, replay the same action
     and representation-role checks, and report actual simulator/deployment or simulator/proxy
     divergence.
   - Claim unlocked: WorldEpisode prevents drift in a real reconstructed-scene pipeline, not only a
     controlled proxy.

8. **USS non-robotics evidence gate**
   - Input: one public game/simulation telemetry corpus or one public autonomous-driving log with
     enough metadata to test state revision, asset digest, frame/clock, and transition invariants.
   - Current output: `docs/experiments/uss_state_drift_pilots/state_drift_report.json` records two
     deterministic pilots, one collision-patch case and one AV clock-domain case.
   - Remaining output: measured diagnostics on a real non-robotics corpus and, ideally, an adapter
     maintained outside this repository.
   - Claim unlocked: USS is empirically useful outside robotics, not only a general vocabulary.

9. **Semantic projection review gate**
   - Input: `conformance/projections/uss-core-23.v0.json`.
   - Current output: versioned profile, schema validation, field-to-requirement mapping, and
     executable binding-retention artifacts.
   - Remaining output: external review or independently authored binding model that accepts,
     revises, or challenges the field set and native capability assumptions.
   - Claim unlocked: the binding-retention profile is an externally reviewed conformance view, not
     only the authors' pilot scoring model.

10. **Independent implementation gate**
   - Input: `schemas/worldepisode-core-v0.schema.json`, `conformance/fixtures/`, and `spec/`.
   - Current output: `docs/experiments/cleanroom_reader/cleanroom_reader_report.json` shows that an
     internal clean-room reader can parse the public schema, summarize the minimal example, and catch
     all expected requirement IDs in pilot and independent fixtures without importing the reference
     SDK.
   - Required output: a reader/exporter or dataset generated outside this repository that passes
     the public conformance suite.
   - Claim unlocked: the project begins to act like an interoperability profile rather than a
     single-codebase system.
