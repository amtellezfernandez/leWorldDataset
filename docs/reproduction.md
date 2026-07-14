# Reproducing the Controlled Results

This is the full reproduction walkthrough for every committed experiment and release gate. The
short version lives in the top-level `README.md`; every command here runs from the repository
root. None of these commands are required to *use* the validator — see the README quickstart for
that.

## Full suite

```bash
python3 -m pip install -r requirements-experiments.txt
WORLDEPISODE_REQUIRE_ACTIVE_LEROBOT=1 python3 tools/run_experiments.py
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
- `docs/experiments/lerobot_scene_leakage/*`
- `docs/experiments/lerobot_control_replay/*`
- `docs/experiments/dataset_scale_audit/*` and `docs/experiments/dataset_scale_performance/*`
- `docs/experiments/cleanroom_reader/*`
- `docs/experiments/replay_adapter_conformance/*`
- `docs/experiments/uss_state_drift_pilots/*`
- `docs/experiments/natural_failure_corpus/*`
- `docs/experiments/recorded_episodes/*`
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
Together, the two public LeRobot batches preserve 1,935 action/state rows plus sample timestamps,
frame indices, episode indices, global sample indices, task indices, video timestamp ranges, and
physical-frame records with zero numerical loss. LeRobot source fields that are absent, such as
camera extrinsics and controller latency, are reported explicitly rather than silently invented.

## Scene-leakage audit and policy gates

```bash
python3 tools/lerobot_scene_leakage_experiment.py --required
python3 tools/lerobot_policy_leakage_gate.py
uv run --with pyarrow --with numpy python tools/lerobot_temporal_policy_baseline.py --strict
```

The scene-leakage audit uses `armnet/armnetbench_v01_lerobot_so101`, derives WorldEpisode-style
`world_lineage` hashes for task-scene/camera-layout groups, compares a random episode split against
a scene-disjoint split, and trains the same Torch MLP behavioral-cloning baseline on both. In the
committed run, the random split leaks all test scene lineages and obtains 0.850 offline BC success;
the scene-disjoint split has zero lineage leakage and drops to 0.000. The committed compact LeRobot
split packages are also executed by a temporal ridge state/action baseline with a three-frame state
history: random-episode success is 0.925, scene-disjoint success is 0.420, and the success-rate
drop is 0.505. This remains a low-dimensional offline result, not ACT, Diffusion, vision-policy,
simulator, or hardware evidence.

The ACT/Diffusion gate converts that same split manifest into LeRobot-native `lerobot-train` jobs,
episode allowlists, virtual split manifests, compact physical state/action LeRobot split packages,
and high-fidelity/physical rollout requirements; it is intentionally marked open until real
ACT/Diffusion metrics and rollout reports are committed. The compact packages omit source videos,
so vision-policy claims require mirrored video assets with digests.

## Control-loop replay

```bash
python3 tools/lerobot_control_replay_experiment.py --required
```

Reads the exported SO-101 LeRobot v3 trajectory, estimates the effective action delay from the
timestamped action/state streams, writes a WorldEpisode action contract, and tests timestamp-aware
replay in MuJoCo and Genesis. In the committed run, the inferred delay is four 30 Hz frames
(133 ms), validation alignment improves from 4.732 deg to 1.862 deg RMSE, and both tested
same-trace replay adapters improve from 3.425 deg to 1.563 deg RMSE. The Isaac adapter contract is
emitted and marked ready, but Isaac is intentionally untested here.

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
