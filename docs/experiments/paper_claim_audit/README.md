# Paper Claim Audit

Status: `pass`.

This report ties the main quantitative and boundary claims in the paper source to tracked experiment artifacts. It fails if a checked number or boundary disappears from the paper or is unsupported by the committed evidence.

## Summary

- Claims checked: 13
- Passed: 13
- Failed: 0

## Claims

| Claim ID | Pass | Claim | Boundary |
|---|---:|---|---|
| CLAIM.LEAKAGE.001 | True | ArmnetBench random split leaks lineages and offline BC drops under scene-disjoint split. | Offline action-imitation result; not ACT/Diffusion or physical rollout success. |
| CLAIM.REPLAY.001 | True | Timestamp-aware LeRobot replay reduces joint RMSE in tested MuJoCo and Genesis adapters. | One LeRobot trace with minimal MuJoCo and Genesis position-servo adapters; Isaac is not claimed tested and contact-rich rollout remains open. |
| CLAIM.ROUNDTRIP.001 | True | Two public LeRobotDataset batches round-trip exactly through WorldEpisode. | Two five-episode batch audits; not full LeRobot coverage. |
| CLAIM.TEMPORAL_POLICY.001 | True | Temporal state/action baseline still drops under scene-disjoint LeRobot evaluation. | Offline temporal state/action baseline; not ACT, Diffusion, vision policy, or rollout. |
| CLAIM.BINDING.001 | True | Seven pilot bindings preserve 17--39% natively outside the reference binding, with sidecars recovering dataset/log/world projections. | Pilot projection score, not a universal storage-format ranking. |
| CLAIM.VALIDATOR.001 | True | Validator detects all injected fault classes and independent fixture failures. | Injected and hand-authored fixtures; natural prevalence remains open. |
| CLAIM.NATURAL.001 | True | Pilot natural-source corpus records 19 cases across five public robot-learning datasets. | Scoped natural-source corpus, not maintainer-confirmed prevalence. |
| CLAIM.NATURAL_DIAGNOSTICS.001 | True | Natural-source corpus has dataset-specific diagnostic reports for all five datasets. | Dataset-specific diagnostics, not prevalence or maintainer-confirmed bug evidence. |
| CLAIM.USS.001 | True | Two deterministic non-robotics USS pilots demonstrate collision-patch and clock-domain drift. | Deterministic pilots, not production game or AV dataset results. |
| CLAIM.REALTOSIM.001 | True | Controlled real-to-sim contract drift ablations fail under drifted contracts and recover with WorldEpisode. | Controlled proxy; not a hardware or RoboSnap/DROID-Sim rerun. |
| CLAIM.SCALE.001 | True | Generated catalog benchmark describes a billion-episode-capacity sharded corpus. | Catalog-side evidence only; does not materialize a billion rows or payload bytes. |
| CLAIM.BENCHMARK_BOUNDARY.001 | True | Famous benchmark audit is fail-closed and makes zero inflation claims in this release. | Source-level call-out audit; no published-score inflation claim. |
| CLAIM.OPEN_GATES.001 | True | Open results are visibly and machine-readably marked as not claimed. | Open gates are unclaimed results, not paper results. |
