# Paper Claim Audit

Status: `pass`.

This report ties the main quantitative and boundary claims in the paper source to tracked experiment artifacts. It fails if a checked number or boundary disappears from the paper or is unsupported by the committed evidence.

## Summary

- Claims checked: 16
- Passed: 16
- Failed: 0

## Claims

| Claim ID | Pass | Claim | Boundary |
|---|---:|---|---|
| CLAIM.LEAKAGE.001 | True | ArmnetBench random split overlaps task--scene proxy lineages; the task-confounded holdout changes offline imitation metrics. | Task--scene proxy shift confounded with task identity; offline action imitation only, not scene-only leakage, ACT/Diffusion, or rollout success. |
| CLAIM.POLICY_VISION_SMOKE.001 | True | Pinned LeRobot ACT and Diffusion paths decode the materialized source front camera and complete the CUDA smoke optimization step. | Input compatibility only; no trained checkpoint, held-out policy metric, simulator rollout, or physical rollout. |
| CLAIM.TIMING.001 | True | A lag frozen on calibration trajectories improves held-out SO-101 action/state telemetry alignment across multiple tasks. | Action/state telemetry-lag proxy on one SO-101 dataset; no independently instrumented motor latency or second robot/controller. |
| CLAIM.REPLAY.001 | True | Timestamp-aware LeRobot replay reduces joint RMSE in tested MuJoCo and Genesis adapters. | One LeRobot trace with minimal MuJoCo and Genesis position-servo adapters; Isaac is not claimed tested; contact physics is evaluated separately. |
| CLAIM.REPLAY.CONTACT.001 | True | A preregistered two-runtime contact protocol measures trajectory, contact, grasp, pose, and outcome agreement without claiming equivalent physics. | Two scripted primitive tasks with kinematic actors and no hardware ground truth; the observed orientation divergence blocks equivalent-physics claims. |
| CLAIM.ROUNDTRIP.001 | True | Complete pinned source shards from multiple public LeRobotDatasets round-trip exactly through WorldEpisode. | One complete pinned Parquet shard per dataset; not full corpora or source-video conversion throughput. |
| CLAIM.TEMPORAL_POLICY.001 | True | Temporal state/action baseline changes under the task--scene proxy holdout. | Task-confounded offline temporal state/action baseline; not a scene-only, vision-policy, ACT, Diffusion, or rollout result. |
| CLAIM.BINDING.001 | True | Pilot bindings inventory native and sidecar retention for a versioned projection. | Pilot projection score, not a universal storage-format ranking. |
| CLAIM.VALIDATOR.001 | True | Validator detects all injected fault classes and independent fixture failures. | Injected and hand-authored fixtures; natural prevalence remains open. |
| CLAIM.NATURAL.001 | True | Pilot natural-source audit records scoped cases across public dataset sources. | Scoped natural-source corpus, not maintainer-confirmed prevalence. |
| CLAIM.NATURAL_DIAGNOSTICS.001 | True | Natural-source audit distinguishes active artifacts from source-level metadata reviews. | Dataset-specific diagnostics, not prevalence or maintainer-confirmed bug evidence. |
| CLAIM.USS.001 | True | Deterministic non-robotics USS pilots demonstrate collision-patch and clock-domain drift. | Deterministic pilots, not production game or AV dataset results. |
| CLAIM.REALTOSIM.001 | True | Controlled real-to-sim contract drift ablations fail under drifted contracts and recover with WorldEpisode. | Controlled proxy; not a hardware or RoboSnap/DROID-Sim rerun. |
| CLAIM.SCALE.001 | True | Generated catalog benchmark describes a large-capacity sharded corpus. | Catalog-side evidence only; does not materialize a billion rows or payload bytes. |
| CLAIM.BENCHMARK_BOUNDARY.001 | True | Famous benchmark audit is fail-closed and makes zero inflation claims in this release. | Source-level call-out audit; no published-score inflation claim. |
| CLAIM.OPEN_GATES.001 | True | Open results are visibly and machine-readably marked as not claimed. | Open gates are unclaimed results, not paper results. |
