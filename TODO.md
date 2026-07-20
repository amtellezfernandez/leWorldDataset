# NeurIPS 2027 Submission TODO

Status: working experiment and submission plan. The NeurIPS 2027 call and style do not exist yet;
the paper currently uses the official NeurIPS 2026 Evaluations & Datasets format as a provisional
baseline.

## P0: Claims That Need Stronger Experiments

- [ ] **Disentangle scene leakage from task shift (`SPLIT.001`).**
  - Current problem: the ArmnetBench `world_lineage` proxy hashes task ID/text, so the current
    held-out protocol is task--scene-proxy-disjoint, not a scene-only intervention.
  - Required data: physical scene/source-capture IDs with the same tasks repeated across multiple
    scenes. Do not derive scene identity from task labels.
  - Protocol: compare a task-stratified random episode split with a task-stratified scene-lineage
    split. Every evaluated task must occur in both training and test; only scene lineage may differ.
  - Models: temporal ridge as a deterministic check, then ACT and Diffusion Policy with at least five
    training seeds per split.
  - Metrics: per-task and aggregate action nRMSE, rollout success, seed variation, episode-bootstrap
    95% CIs, and train/test lineage overlap.
  - Acceptance: zero scene-lineage overlap, identical task support across protocols, a preregistered
    metric/threshold, and a corrected-minus-random effect whose CI excludes zero.
  - Replace evidence in:
    `docs/experiments/lerobot_scene_leakage/`,
    `docs/experiments/lerobot_temporal_policy_baseline/`, and
    `docs/experiments/statistical_analysis/`.

- [ ] **Run common LeRobot policies and actual rollouts (`POLICY.ROLL.001`).**
  - Completed preflight: the compact packages now preserve LeRobot storage-limit metadata, include
    split-specific `meta/stats.json`, and load locally by explicit `dataset.root`.
  - Completed remote compatibility audit: pinned LeRobot 0.6.0 loads the representative package on
    the DGX Spark. The initial low-dimensional package makes both ACT and Diffusion stop before the
    first training step because it has only joint proprioception and neither an observation image
    nor a semantically valid `observation.environment_state`.
  - Do not relabel joint positions as environment state to bypass the policy contract. The generated
    jobs use the source front camera instead.
  - Completed media preflight: the generated front-camera asset manifest pins the source revision,
    metadata, required MP4 paths, byte sizes, and LFS SHA-256 digests. Remote materialization
    verifies every asset and all four split packages; pinned ACT and Diffusion paths both complete
    their CUDA smoke optimization step.
  - Preregistered offline training protocol:
    `docs/experiments/lerobot_policy_full_training/protocol.json` fixes ACT and Diffusion, both
    current split packages, five matched seeds, 20,000 optimizer steps, checkpoint/log provenance,
    and paired teacher-observation evaluation before the required run. The evaluation reference
    proves byte-identical actions, frame indices, and timestamps for the exact 21 source episodes
    shared by both test packages. This can establish common-policy offline action error only; the
    current lineage holdout is task-confounded and the required 20 jobs have not yet run.
  - The preflight closes training-input compatibility only. Full matched-seed training, held-out
    action metrics, checkpoints, and rollouts remain open.
  - Execute ACT and Diffusion jobs for both split protocols with matched hyperparameters and seeds.
  - Evaluate checkpoints in one high-fidelity simulator or on the source robot using the same split
    manifest.
  - Record checkpoint/config digests, seed-level metrics, rollout traces/videos, failures, and total
    compute.
  - Acceptance: both policies have complete random and lineage-disjoint runs; at least one policy has
    paired rollout evidence; no task/scene confound remains.

- [ ] **Generalize the action-timing result (`ACTION.002`).**
  - Completed partial evidence: a remote DGX Spark audit selects one lag from 320 calibration
    trajectories across eight tasks and evaluates 80 source-episode-disjoint trajectories. The
    paired episode 95% CI excludes zero, every held-out trajectory improves, and the report includes
    per-joint/per-task metrics plus interpolation and synthetic missing-command sensitivity.
  - Boundary: this is an action/state telemetry-lag proxy on one SO-101 dataset. The source has one
    frame timestamp, no motor-effective timestamps, and one robot/controller configuration;
    timestamp scheduling is therefore not an independent queue observation.
  - Remaining data: instrument command enqueue/consume and motor-effective timestamps, then repeat
    on a second robot or controller configuration.
  - Acceptance: measured motor-delay error and a queue-aware scheduler improve held-out behavior
    with a 95% CI excluding zero across at least two controller configurations.

- [x] **Add contact-rich cross-simulator replay (`REPLAY.001`).**
  - Preregistered protocol: `docs/experiments/contact_rich_replay/protocol.json` fixes two tasks,
    16 seeded initial states per task, runtime versions, kinematic action trajectories, metrics,
    bootstrap procedure, claim boundary, and completion checks before the required runtime run.
    `tools/contact_rich_cross_sim_replay.py` keeps MuJoCo and Genesis execution in separate
    processes and derives every comparison from retained raw trajectories and contact traces.
  - Completed without changing the preregistered protocol: both pinned runtimes execute all 32
    paired scenarios, retain raw pose/contact/grasp/outcome traces, and pass the independent
    cross-interpreter verifier. Contact F1 is high and outcomes agree, while substantial capture
    orientation drift correctly keeps equivalent-physics claims blocked.
  - Use the same world revision, initial state, action contract, and tolerance envelope in MuJoCo and
    Genesis; add Isaac Sim or SAPIEN only after the core two-runtime protocol is stable.
  - Measure object trajectory error, contact precision/recall/F1, grasp-state agreement, final pose
    error, and task outcome.
  - Acceptance: at least two contact-rich tasks, multiple initial states, complete runtime manifests,
    and per-metric uncertainty intervals. Do not claim equivalent physics.

- [ ] **Validate natural failures with dataset maintainers (`NATURAL.001`).**
  - Pin active WorldEpisode conversions for DROID and BridgeData V2 rather than relying on
    source-level metadata review.
  - Sample diagnostics before looking at outcomes, perform an independent false-positive review, and
    send representative cases to maintainers for adjudication.
  - Acceptance: per-dataset denominators, confirmed/contested/unclear labels, reviewer agreement, and
    maintainer responses or documented non-response. Until then, do not report prevalence.

## P1: Breadth and External Validity

- [ ] **Run a faithful published benchmark protocol (`BENCH.INFLATE.001`).**
  - Choose one benchmark with real scene/source lineage, reproduce its published policy and metric,
    and rerun only the split or timing intervention.
  - Acceptance: matched checkpoints/configuration, paired corrected evaluation, and a complete
    inflation-proof report. A metadata gap alone is not inflation evidence.

- [x] **Scale conversion beyond ten episodes.**
  - Convert complete pinned subsets from at least three LeRobot datasets, including one multi-camera
    manipulation dataset.
  - Report rows, bytes, wall time, peak memory, semantic-loss counts, and exact round-trip errors.
  - Completed on the remote DGX Spark over complete pinned source Parquet shards from three datasets:
    271 episodes and 43,601 paired state/action rows, including two multi-camera datasets. Temporary
    output packages are deleted after exact comparison; source video payloads are not converted.

- [ ] **Obtain an independent implementation (`ADOPT.001`).**
  - Have a second implementer build a reader/exporter from the public schema and conformance fixtures
    without importing `worldepisode`.
  - Acceptance: external implementation passes the conformance suite and publishes its own report.

- [ ] **Add one real non-robotics corpus or remove the broader framing.**
  - Evaluate a public game/simulation telemetry corpus or autonomous-driving log with a separately
    maintained adapter.
  - Acceptance: measured diagnostics on real data; deterministic toy pilots are not sufficient.

## Experiment Reporting

- [x] Add episode-level 95% intervals for the current MLP and temporal-ridge offline metrics.
- [x] Generate every paper measurement and plot coordinate from committed experiment reports;
  missing gated results render as `Not defined yet`.
- [x] Repeat the MLP with five optimization seeds and use crossed seed--episode bootstrap intervals.
- [x] Use continuous episode nRMSE as the primary offline metric; retain the unvalidated threshold
  only as an explicitly secondary diagnostic.
- [ ] Record CPU/GPU model, RAM/VRAM, storage, wall time, and failed/preliminary runs for every
  experiment.
  - Completed for the five-seed leakage run, DROID rerun, controlled suite, conversion scale,
    multi-trajectory timing audit, ACT/Diffusion compatibility preflight, and remote test suite on
    the DGX Spark, plus the local preregistered contact-rich MuJoCo/Genesis replay. The
    conversion-scale run additionally retains two failed preliminary attempts; older committed
    experiments still need the same provenance backfilled.
- [x] Add a validated machine-readable experiment manifest linking dataset revision, split digest,
  config, seed policy, exact code digest, repository commit, output report, and compute use.
- [x] Store a verified recovery snapshot of the Git history, paper, supplement, and retained run
  logs in a private Hugging Face dataset repository; pin its immutable commit and file digests in
  `docs/huggingface-recovery.json`.
- [ ] Upload every future policy checkpoint and rollout trace to the recovery repository before
  deleting its DGX Spark working directory.

## Submission and Paper

- [x] Use the latest official NeurIPS E&D style provisionally and produce an anonymous build.
- [x] Fit the main content within the current nine-page limit; references currently start on page 9.
- [x] Add a machine-checkable provisional-format gate for style digest, double-blind mode, page
  boundary, references/appendix order, and checklist placement.
- [x] Put references before appendices and the mandatory checklist last.
- [x] Correct the scene-only leakage overclaim and state the task-shift confound.
- [ ] Replace `neurips_2026.sty` with the official 2027 style when released and re-audit the page
  limit/checklist.
- [ ] Reconcile the paper against the complete NeurIPS 2027 E&D call, handbook, and checklist when
  published; the current configuration records the official 2026 rules only as a baseline.
- [ ] Provide a reviewer-accessible anonymous code URL in the OpenReview submission form. The
  deterministic anonymous supplement contains the executable artifact but is not itself the portal
  URL.
- [x] Create a deterministic anonymized code/data supplement with an automated PDF/ZIP identity
  audit.
- [x] Resolve and report licenses/terms for every third-party dataset and derived artifact; enforce
  adjacent machine-readable source notices for redistributed Parquet packages.
- [ ] Complete the author ethics attestation after reviewing the NeurIPS 2027 Code of Ethics.
- [x] Remove identifying text and metadata from the submission PDF and supplement, enforced by
  `tools/submission_anonymity_audit.py`.
- [x] Remove split author-name fields from citation metadata and regression-test standalone identity
  tokens in the anonymous supplement.
- [x] Run a citation-by-citation source audit; replace project-page citations with archival papers
  where available.
- [x] Run `make check`.
- [x] Archive the final submission build log in
  `docs/experiments/run_logs/paper_build_local.log`.
- [x] Inspect representative submission PDF pages visually after the generated-value conversion.
