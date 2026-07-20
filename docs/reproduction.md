# Reproducing the Controlled Results

This is the full reproduction walkthrough for every committed experiment and release gate. The
short version lives in the top-level `README.md`; every command here runs from the repository
root. None of these commands are required to *use* the validator — see the README quickstart for
that.

## Full suite

```bash
python3 -m pip install -r requirements-experiments.txt
WORLDEPISODE_REQUIRE_ACTIVE_LEROBOT=1 python3 tools/run_experiments.py
python3 tools/experiment_statistics.py
python3 tools/experiment_manifest.py --strict
python3 tools/paper_experiment_values.py
python3 tools/build_anonymous_supplement.py --strict
python3 tools/submission_anonymity_audit.py --strict
python3 tools/open_reproduction_gates.py --strict
python3 tools/paper_claim_audit.py --strict
python3 tools/package_install_smoke.py --strict
python3 tools/submission_packet.py --strict
python3 tools/public_maturity_audit.py --strict
python3 tools/release_manifest.py --strict
python3 tools/release_manifest.py --verify --strict
python3 tools/release_readiness.py --strict-rfc
python3 tools/artifact_freshness.py --strict
```

If this Python environment does not include `pip`, use `uv`:

```bash
uv run --with-requirements requirements-experiments.txt \
  env WORLDEPISODE_REQUIRE_ACTIVE_LEROBOT=1 python tools/run_experiments.py
```

For the lightweight controlled suite without requiring the active LeRobot dependency path:

```bash
python3 tools/run_experiments.py
```

The experiment runner writes:

- `docs/experiments/results.json` and `docs/experiments/RESULTS.md`
- `docs/experiments/bindings/*`
- `docs/experiments/lerobot_worldepisode_roundtrip/*`
- `docs/experiments/lerobot_conversion_scale/*`
- `docs/experiments/lerobot_multitrajectory_timing/*`
- `docs/experiments/lerobot_scene_leakage/*`
- `docs/experiments/lerobot_control_replay/*`
- `docs/experiments/dataset_scale_audit/*` and `docs/experiments/dataset_scale_performance/*`
- `docs/experiments/cleanroom_reader/*`
- `docs/experiments/replay_adapter_conformance/*`
- `docs/experiments/uss_state_drift_pilots/*`
- `docs/experiments/natural_failure_corpus/*`
- `docs/experiments/recorded_episodes/*`
- `docs/experiments/experiment_manifest/*`
- `WorldEpisode-supplement.zip`, `docs/anonymous_supplement/*`, and
  `docs/experiments/anonymity_audit/*`
- `conformance/fixtures/pilot/*`

## Active LeRobot conversion (round trip)

```bash
python3 -m pip install -r requirements-experiments.txt
python3 tools/lerobot_worldepisode_roundtrip.py --required
```

To extend from the default single-episode run to the committed batch audit:

```bash
python3 tools/lerobot_worldepisode_roundtrip.py --required --batch-episode-indices 0,1,2,3,4
python3 tools/lerobot_worldepisode_roundtrip.py --required \
  --repo-id lerobot/pusht \
  --revision 7628202a2180972f291ba1bc6723834921e72c19 \
  --output-dir docs/experiments/lerobot_worldepisode_roundtrip_pusht \
  --batch-episode-indices 0,1,2,3,4 \
  --max-download-mb 4
```

The active converter downloads bounded metadata/data shards from `lerobot/svla_so101_pickplace`,
converts episode 0 through `LeRobotDataset v3 -> WorldEpisode -> LeRobotDataset v3`, and can extend
the audit to episodes 0--4. A second committed batch repeats the same audit on `lerobot/pusht`.
Together, the two public LeRobot batches preserve all action/state rows plus sample timestamps,
frame indices, episode indices, global sample indices, task indices, video timestamp ranges, and
physical-frame records with zero numerical loss. LeRobot source fields that are absent, such as
camera extrinsics and controller latency, are reported explicitly rather than silently invented.

### Complete-shard conversion-scale audit

```bash
uv run --with pyarrow --with requests \
  python tools/lerobot_conversion_scale.py --required
```

This deterministic command converts every episode assigned to one complete immutable source
Parquet shard from each of the pinned SVLA, PushT, and ArmnetBench releases. It checks exact
action/state/index/timestamp equality, records input and temporary-output bytes, wall time, peak
resident memory, and source-absent semantics, then deletes the temporary packages. Source video
payloads are not downloaded; only stream and timestamp metadata are audited. The committed report
is `docs/experiments/lerobot_conversion_scale/scale_report.json`, and `--check --required` validates
it without rerunning or downloading data.

## Task--scene proxy audit and policy gates

```bash
uv run --with torch --with pyarrow --with requests --with numpy \
  python tools/lerobot_scene_leakage_experiment.py \
  --seeds 0,1,2,3,4 --epochs 12 --device auto --required
python3 tools/lerobot_policy_leakage_gate.py
python3 tools/lerobot_policy_compatibility_audit.py --check --strict
uv run --with pyarrow --with numpy python tools/lerobot_temporal_policy_baseline.py --strict
python3 tools/experiment_statistics.py
```

The audit uses `armnet/armnetbench_v01_lerobot_so101` and derives `world_lineage` hashes from task
identity as well as source and camera metadata. It compares a random episode split with a
task--scene proxy holdout (stored under the legacy `scene_disjoint` key) and trains the same Torch
MLP baseline with five matched optimization seeds on both. The statistical report uses a crossed
seed--episode bootstrap for the MLP, pairing sampled seeds across protocols while independently
resampling their different held-out episode sets. Because the proxy contains task identity and the
holdout removes tasks, the measured metric changes do not isolate scene leakage from task shift.
The compact LeRobot split packages are also executed by a deterministic temporal ridge state/action
baseline. Both are low-dimensional offline diagnostics, not ACT, Diffusion, vision-policy,
simulator, or hardware evidence.

The ACT/Diffusion gate converts that same split manifest into LeRobot-native `lerobot-train` jobs
with explicit local dataset roots, episode allowlists, virtual split manifests, compact physical
state/action LeRobot split packages, and high-fidelity/physical rollout requirements. The compact
packages include split-specific normalization statistics and pass the pinned LeRobot 0.6.0 loader.
The remote compatibility report records that ACT and Diffusion both stop before training because
their input contract requires an image or environment-state feature in addition to the available
joint proprioception. Joint positions are not relabeled to bypass that contract. Reproduce the
remote probe in a pinned environment with:

```bash
uv run --isolated --with 'lerobot[training,diffusion]==0.6.0' \
  python tools/lerobot_policy_compatibility_audit.py --strict
```

The gate remains blocked until source images or a semantically valid environment-state feature are
materialized. Vision-policy claims also require mirrored video assets with committed digests.
Generate and validate the pinned front-camera asset plan without downloading video payloads:

```bash
uv run --with pyarrow --with huggingface-hub \
  python tools/lerobot_policy_video_materialization.py --plan
python3 tools/lerobot_policy_video_materialization.py --check --strict
```

On the remote training host, materialize only the files in that plan and run the one-step vision
smoke test:

```bash
uv run --with pyarrow --with huggingface-hub \
  python tools/lerobot_policy_video_materialization.py --materialize --download
uv run --isolated --with 'lerobot[training,diffusion]==0.6.0' \
  python tools/lerobot_policy_vision_smoke.py --strict
```

The asset manifest pins the source repository revision, source metadata digests, and every required
MP4 LFS SHA-256. The materializer preserves source video timestamps and file indices; it does not
copy image values into a different semantic feature.

## Control-loop replay

```bash
uv run --with pyarrow --with numpy \
  python tools/lerobot_multitrajectory_timing_audit.py --required
python3 tools/lerobot_control_replay_experiment.py --required
```

The multi-trajectory audit estimates one action/state telemetry lag on the calibration split,
freezes it, and evaluates source-episode-disjoint trajectories with paired episode bootstrap
intervals, per-joint and per-task metrics, and interpolation/missing-command sensitivity. It does
not measure motor latency: the source has only a frame timestamp and covers one SO-101 controller
configuration.

The separate replay command reads one exported SO-101 LeRobot v3 trajectory, writes a WorldEpisode
action contract around an estimated delay, and tests that contract in MuJoCo and Genesis. Those
same-trace adapters improve alignment under the declared contract, but both use the same minimal
servo model. The Isaac adapter is emitted and marked ready but remains untested.

## Famous-benchmark call-out and inflation gate

```bash
python3 tools/benchmark_callout_audit.py
uv run --with pyarrow --with requests --with numpy \
  python tools/famous_benchmark_policy_rerun.py --benchmark droid_100 --required
python3 tools/benchmark_inflation_gate.py
python3 tools/benchmark_inflation_gate.py --required
```

The call-out audit applies the requirement lens to Open X-Embodiment, DROID, BridgeData V2, LIBERO,
and CALVIN. It flags missing public leakage/timing controls, but does not claim a benchmark score
is inflated until a measured rerun exists. The separate inflation gate currently records one
attempted DROID subset rerun artifact, zero valid famous-benchmark rerun reports, and zero measured
famous-benchmark inflation claims; the `--required` form is expected to fail until a famous
benchmark has a committed WorldEpisode conversion, split/timing audit, and policy rerun report.

## Real-to-sim, meta-simulator, and adapter conformance

```bash
python3 tools/realtosim_contract_drift.py
python3 tools/meta_simulator_contract.py
python3 tools/replay_adapter_conformance.py
```

The real-to-sim ablation shows two proxy failures that visual reconstruction alone cannot prevent:
action-interface drift and representation-role drift. It is a controlled proxy, not a hardware
rollout. The meta-simulator contract records tested same-trace MuJoCo and Genesis replay adapters;
Isaac is adapter-ready but untested, and SAPIEN remains adapter-required — the claim is adapter
compliance, not simulator-independent physics. The replay-adapter conformance harness adds a
dependency-free scheduler check for delay, zero-order-hold, missing-command, and asynchronous queue
semantics.

## Non-robotics pilots, dataset scale, and clean-room reader

```bash
python3 tools/uss_state_drift_pilots.py
python3 tools/dataset_scale_audit.py
python3 tools/dataset_scale_performance.py
python3 tools/cleanroom_conformance_reader.py
```

The USS state-drift pilots add two lightweight non-robotics checks (game-engine collision patch,
autonomous-driving clock-domain offset); they support the vocabulary claim only. The dataset-scale
audit validates the scalable corpus manifest; the performance benchmark generates a 32,768-shard
catalog describing 1,073,741,824 episodes and measures catalog-side behavior only. The clean-room
reader parses the public schema and fixture corpus without importing the `worldepisode` package; it
is not an external implementation or adoption claim.

## Release gates

```bash
python3 tools/open_reproduction_gates.py --strict
python3 tools/paper_claim_audit.py --strict
python3 tools/package_install_smoke.py --strict
python3 tools/submission_packet.py --strict
python3 tools/public_maturity_audit.py --strict
python3 tools/release_manifest.py --verify --strict
python3 tools/release_readiness.py --strict-rfc
```

The gate currently passes the executable RFC-release checks and still blocks full standard claims
such as ACT/Diffusion rollout impact, famous-benchmark inflation, external adoption, and full
cross-simulator replay. `tools/open_reproduction_gates.py` indexes every stronger result that is
intentionally not claimed yet and records the commands needed to produce the missing evidence.
`tools/paper_claim_audit.py` checks the paper's numerical and boundary claims against committed
artifacts. `tools/release_manifest.py` records SHA-256 digests for stable public evidence.
`tools/submission_packet.py` renders the reviewer-facing packet tying measured claims, open
results, required artifacts, and reproduction commands together.
