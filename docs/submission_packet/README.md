# Submission Packet

Status: `pass`.

Only claims listed as passed in the paper claim audit are treated as measured. Open reproduction gates are executable reviewer tasks, not paper results.

## Summary

- Paper claims checked: 15
- Failed checked claims: 0
- Open results not claimed: 4
- Missing required public artifacts: 0
- Release gate: `python3 tools/release_readiness.py --strict-rfc`

## Required Public Artifacts

| Artifact | Exists | Nonempty |
|---|---:|---:|
| `WorldEpisode.pdf` | True | True |
| `WorldEpisode-supplement.zip` | True | True |
| `README.md` | True | True |
| `THIRD_PARTY_ASSETS.md` | True | True |
| `TODO.md` | True | True |
| `third_party_licenses/README.md` | True | True |
| `third_party_licenses/pusht-MIT.txt` | True | True |
| `spec/worldepisode-v0.1.md` | True | True |
| `spec/le-world-layout-v0.1.md` | True | True |
| `paper/le-world-layout.md` | True | True |
| `paper/arxiv/main.tex` | True | True |
| `paper/arxiv/checklist.tex` | True | True |
| `paper/arxiv/generated/experiment_values.tex` | True | True |
| `schemas/worldepisode-core-v0.schema.json` | True | True |
| `schemas/worldepisode-dataset-v0.schema.json` | True | True |
| `conformance/requirements.v0.json` | True | True |
| `conformance/projections/uss-core-23.v0.json` | True | True |
| `docs/experiments/results.json` | True | True |
| `docs/experiments/lerobot_scene_leakage/leakage_report.json` | True | True |
| `docs/experiments/lerobot_scene_leakage/bc_episode_errors.json` | True | True |
| `docs/experiments/lerobot_scene_leakage/split_manifest.json` | True | True |
| `docs/experiments/lerobot_temporal_policy_baseline/temporal_policy_report.json` | True | True |
| `docs/experiments/lerobot_conversion_scale/README.md` | True | True |
| `docs/experiments/lerobot_conversion_scale/scale_report.json` | True | True |
| `docs/experiments/lerobot_multitrajectory_timing/README.md` | True | True |
| `docs/experiments/lerobot_multitrajectory_timing/timing_report.json` | True | True |
| `docs/experiments/run_logs/lerobot_multitrajectory_timing_dgx_spark.log` | True | True |
| `docs/experiments/lerobot_policy_gate/policy_gate_report.json` | True | True |
| `docs/experiments/lerobot_policy_gate/policy_compatibility_report.json` | True | True |
| `docs/experiments/lerobot_policy_gate/front_camera_asset_manifest.json` | True | True |
| `docs/experiments/lerobot_policy_gate/front_camera_materialization_report.json` | True | True |
| `docs/experiments/lerobot_policy_gate/policy_vision_smoke_report.json` | True | True |
| `docs/experiments/lerobot_policy_gate/policy_vision_smoke_failed_01_report.json` | True | True |
| `docs/experiments/run_logs/lerobot_policy_compatibility_dgx_spark.log` | True | True |
| `docs/experiments/run_logs/lerobot_policy_video_materialization_dgx_spark.log` | True | True |
| `docs/experiments/run_logs/lerobot_policy_vision_smoke_dgx_spark.log` | True | True |
| `docs/experiments/run_logs/lerobot_policy_vision_smoke_failed_01_dgx_spark.log` | True | True |
| `docs/experiments/run_logs/lerobot_conversion_scale_dgx_spark.log` | True | True |
| `docs/experiments/run_logs/lerobot_conversion_scale_dgx_spark_failed_01.log` | True | True |
| `docs/experiments/run_logs/lerobot_conversion_scale_dgx_spark_failed_02.log` | True | True |
| `docs/experiments/statistical_analysis/statistical_report.json` | True | True |
| `docs/experiments/experiment_manifest/experiment_manifest.json` | True | True |
| `docs/experiments/citation_source_audit/citation_source_audit.json` | True | True |
| `docs/experiments/third_party_asset_audit/asset_audit.json` | True | True |
| `docs/anonymous_supplement/supplement_report.json` | True | True |
| `docs/experiments/anonymity_audit/anonymity_report.json` | True | True |
| `docs/experiments/paper_claim_audit/paper_claim_audit_report.json` | True | True |
| `docs/experiments/package_install_smoke/package_install_smoke_report.json` | True | True |
| `docs/experiments/open_reproduction_gates/open_reproduction_gates.json` | True | True |
| `docs/release_manifest/release_manifest.json` | True | True |
| `docs/release_manifest/README.md` | True | True |
| `docs/experiments/release_readiness/release_readiness_report.json` | True | True |
| `docs/reviewer-concern-matrix.md` | True | True |
| `GOVERNANCE.md` | True | True |
| `CITATION.cff` | True | True |

## Measured Claims

| Claim | Pass | Text | Boundary |
|---|---:|---|---|
| `CLAIM.LEAKAGE.001` | True | ArmnetBench random split overlaps task--scene proxy lineages; the task-confounded holdout changes offline imitation metrics. | Task--scene proxy shift confounded with task identity; offline action imitation only, not scene-only leakage, ACT/Diffusion, or rollout success. |
| `CLAIM.POLICY_VISION_SMOKE.001` | True | Pinned LeRobot ACT and Diffusion paths decode the materialized source front camera and complete the CUDA smoke optimization step. | Input compatibility only; no trained checkpoint, held-out policy metric, simulator rollout, or physical rollout. |
| `CLAIM.TIMING.001` | True | A lag frozen on calibration trajectories improves held-out SO-101 action/state telemetry alignment across multiple tasks. | Action/state telemetry-lag proxy on one SO-101 dataset; no independently instrumented motor latency or second robot/controller. |
| `CLAIM.REPLAY.001` | True | Timestamp-aware LeRobot replay reduces joint RMSE in tested MuJoCo and Genesis adapters. | One LeRobot trace with minimal MuJoCo and Genesis position-servo adapters; Isaac is not claimed tested and contact-rich rollout remains open. |
| `CLAIM.ROUNDTRIP.001` | True | Complete pinned source shards from multiple public LeRobotDatasets round-trip exactly through WorldEpisode. | One complete pinned Parquet shard per dataset; not full corpora or source-video conversion throughput. |
| `CLAIM.TEMPORAL_POLICY.001` | True | Temporal state/action baseline changes under the task--scene proxy holdout. | Task-confounded offline temporal state/action baseline; not a scene-only, vision-policy, ACT, Diffusion, or rollout result. |
| `CLAIM.BINDING.001` | True | Pilot bindings inventory native and sidecar retention for a versioned projection. | Pilot projection score, not a universal storage-format ranking. |
| `CLAIM.VALIDATOR.001` | True | Validator detects all injected fault classes and independent fixture failures. | Injected and hand-authored fixtures; natural prevalence remains open. |
| `CLAIM.NATURAL.001` | True | Pilot natural-source audit records scoped cases across public dataset sources. | Scoped natural-source corpus, not maintainer-confirmed prevalence. |
| `CLAIM.NATURAL_DIAGNOSTICS.001` | True | Natural-source audit distinguishes active artifacts from source-level metadata reviews. | Dataset-specific diagnostics, not prevalence or maintainer-confirmed bug evidence. |
| `CLAIM.USS.001` | True | Deterministic non-robotics USS pilots demonstrate collision-patch and clock-domain drift. | Deterministic pilots, not production game or AV dataset results. |
| `CLAIM.REALTOSIM.001` | True | Controlled real-to-sim contract drift ablations fail under drifted contracts and recover with WorldEpisode. | Controlled proxy; not a hardware or RoboSnap/DROID-Sim rerun. |
| `CLAIM.SCALE.001` | True | Generated catalog benchmark describes a large-capacity sharded corpus. | Catalog-side evidence only; does not materialize a billion rows or payload bytes. |
| `CLAIM.BENCHMARK_BOUNDARY.001` | True | Famous benchmark audit is fail-closed and makes zero inflation claims in this release. | Source-level call-out audit; no published-score inflation claim. |
| `CLAIM.OPEN_GATES.001` | True | Open results are visibly and machine-readably marked as not claimed. | Open gates are unclaimed results, not paper results. |

## Open Results Not Claimed

| Gate | Claim | Status | Acceptance Rule |
|---|---|---|---|
| `POLICY.ROLL.001` | state-of-the-art policy or physical rollout impact | open_not_claimed | At least one ACT or Diffusion Policy run must report both random_episode and scene_disjoint metrics, and at least one rollout report must use the same split manifest before the stronger policy-impact claim can be made. |
| `BENCH.INFLATE.001` | famous benchmark published scores are inflated | open_not_claimed | The gate must contain at least one inflation-proof valid rerun report with measured_inflation=true. Source-level metadata gaps alone are not score-inflation evidence. |
| `NATURAL.001` | natural failure prevalence is maintainer-confirmed | open_not_claimed | Dataset-specific diagnostic reports support representative diagnostics only. A prevalence or maintainer-confirmed claim still requires recorded maintainer feedback, false-positive review, and pinned conversions for source-level benchmark gaps. |
| `ADOPT.001` | mature external standard adoption | open_not_claimed | Mature-standard language requires at least one independently written implementation or externally published compatible dataset that passes the public conformance suite. |

## Reproduction Commands

| Step | Command |
|---|---|
| validate schemas, examples, and Python tools | `make validate` |
| regenerate controlled experiment evidence | `python3 tools/run_experiments.py` |
| regenerate measured temporal policy baseline | `uv run --with pyarrow --with numpy python tools/lerobot_temporal_policy_baseline.py --strict` |
| regenerate five-seed task--scene proxy audit | `uv run --with torch --with pyarrow --with requests --with numpy python tools/lerobot_scene_leakage_experiment.py --seeds 0,1,2,3,4 --epochs 12 --device auto --required` |
| regenerate seed-and-episode uncertainty intervals | `python3 tools/experiment_statistics.py` |
| regenerate complete-shard LeRobot conversion-scale evidence | `uv run --with pyarrow --with requests python tools/lerobot_conversion_scale.py --required` |
| regenerate held-out multi-trajectory timing evidence | `uv run --with pyarrow --with numpy python tools/lerobot_multitrajectory_timing_audit.py --required` |
| validate pinned LeRobot policy compatibility evidence | `python3 tools/lerobot_policy_compatibility_audit.py --check --strict` |
| validate pinned LeRobot front-camera and policy smoke evidence | `python3 tools/lerobot_policy_video_materialization.py --check --strict && python3 tools/lerobot_policy_vision_smoke.py --check --strict` |
| regenerate and validate experiment provenance | `python3 tools/experiment_manifest.py --strict` |
| audit every paper citation | `python3 tools/citation_source_audit.py --strict` |
| audit third-party assets and redistributed source rows | `python3 tools/third_party_asset_audit.py --strict` |
| build the anonymous supplementary archive | `python3 tools/build_anonymous_supplement.py --strict` |
| audit PDF and supplement anonymity | `python3 tools/submission_anonymity_audit.py --strict` |
| regenerate paper values from experiment reports | `python3 tools/paper_experiment_values.py` |
| validate open unclaimed-result gates | `python3 tools/open_reproduction_gates.py --strict` |
| audit paper claims against evidence | `python3 tools/paper_claim_audit.py --strict` |
| generate this submission packet | `python3 tools/submission_packet.py --strict` |
| audit public maturity language | `python3 tools/public_maturity_audit.py --strict` |
| smoke-test wheel install | `python3 tools/package_install_smoke.py --strict` |
| build digest release manifest | `python3 tools/release_manifest.py --strict` |
| verify committed release manifest | `python3 tools/release_manifest.py --verify --strict` |
| check RFC release readiness | `python3 tools/release_readiness.py --strict-rfc` |
| reject stale generated artifacts | `python3 tools/artifact_freshness.py --strict` |

## Validation

- Passed: `True`
- Missing artifacts: `[]`
- Failed claims: `[]`
- Invalid open gates: `[]`
