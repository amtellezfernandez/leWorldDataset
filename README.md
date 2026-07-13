# Universal Spatial State (USS) / WorldEpisode

Universal Spatial State (USS) is the paper-level contract for diagnosing and correcting silent
state drift across embodied and virtual spatial pipelines. It targets failures where local files
still load, but behavior is invalid because state ancestry, asset identity, frame/clock mappings,
representation roles, transition semantics, or provenance drifted.

`WorldEpisode` is the robotics-heavy USS reference profile in this repository. It binds
robot-learning episodes to immutable, versioned, replayable 3D worlds and provides the concrete
schemas, validator, converters, and experiments used by the paper.

The goal is not to create another monolithic file format. The goal is to define the semantic
contract that can be bound into LeRobotDataset, Rerun, NCore, MCAP, OpenUSD, glTF Gaussian splats,
GSDF-style assets, game-engine telemetry, autonomous-driving logs, object storage, or a reference
package layout. Large corpora are described through a dataset manifest and index layer, not by
treating a folder tree as the semantic API.

OpenUSD standardizes how the 3D world is composed, but USS standardizes how any agent, whether a
physical robot, a video game character, or an autonomous vehicle, modifies state within that space
over time without silent data corruption.

## Paper

- [WorldEpisode.pdf](WorldEpisode.pdf) - current USS / WorldEpisode paper build
- [arXiv LaTeX source](paper/arxiv/main.tex)

## Repository Layout

- `paper/arxiv/` - arXiv-ready LaTeX paper source.
- `paper/` - Markdown paper notes and outline.
- `spec/` - normative specification drafts.
- `schemas/` - machine-readable JSON Schema drafts.
- `conformance/` - requirement IDs, profiles, generated and independent fixture corpora.
- `docs/` - bindings, SDK contract, controlled results, research plan, and reference release plan.
- `examples/` - small valid layout examples.
- `notes/` - research notes, decisions, and open questions.

## Core Position

USS is:

- **storage-neutral**: it can be serialized in LeRobot, Rerun, NCore, MCAP, or a reference package;
- **representation-neutral**: appearance and state can use splats, meshes, NeRFs, point clouds, collision proxies, telemetry streams, or future representations;
- **runtime-neutral**: physical and virtual worlds can target MuJoCo, Isaac Sim, SAPIEN, Genesis, game engines, AV replay systems, or future runtimes;
- **loss-explicit**: conversions may be lossy, but never silently lossy.
- **resolver-neutral**: assets are portable through URI, media type, digest, and optional mirrors,
  not by forcing every asset into a local folder.
- **dataset-scale**: production corpora use globally scoped IDs, shard catalogs, materialized
  indexes, resolver registries, and append-only dataset snapshots.

WorldEpisode instantiates USS for robot-learning episodes. Gaussian splats are a high-value profile
and demonstration, not the core claim. The stronger claim is persistent, verifiable spatial-state
interoperability, with robotics used as the hardest current stress test.

## Current Drafts

- [Paper PDF](WorldEpisode.pdf)
- [arXiv LaTeX paper](paper/arxiv/main.tex)
- [Markdown paper notes](paper/le-world-layout.md)
- [USS framing note](docs/universal-spatial-state.md)
- [WorldEpisode draft spec](spec/worldepisode-v0.1.md)
- [WorldEpisode JSON Schema draft](schemas/worldepisode-core-v0.schema.json)
- [WorldEpisode dataset manifest schema draft](schemas/worldepisode-dataset-v0.schema.json)
- [Conformance JSON Schema draft](schemas/conformance-requirements-v0.schema.json)
- [World layout profile draft](spec/le-world-layout-v0.1.md)
- [World layout JSON Schema draft](schemas/le-world-layout-v0.schema.json)
- [Conformance requirements](conformance/requirements.md)
- [Machine-readable requirements](conformance/requirements.v0.json)
- [Conformance profiles](conformance/profiles.md)
- [USS-Core-23 semantic projection](conformance/projections/uss-core-23.v0.json)
- [Pilot conformance corpus](conformance/fixtures/pilot/manifest.json)
- [Independent conformance fixtures](conformance/fixtures/independent/manifest.json)
- [Bindings draft](docs/bindings.md)
- [Reference SDK contract](docs/sdk.md)
- [Production-scale dataset architecture](docs/production-scale.md)
- [Dataset-scale manifest audit artifacts](docs/experiments/dataset_scale_audit)
- [ACT/Diffusion policy leakage gate](docs/policy-leakage-gate.md)
- [Famous benchmark call-out audit](docs/benchmark-callout-audit.md)
- [Real-to-sim contract drift](docs/real-to-sim-contract-drift.md)
- [Meta-simulator contract](docs/meta-simulator-contract.md)
- [USS state-drift pilots](docs/experiments/uss_state_drift_pilots)
- [Replay adapter conformance](docs/experiments/replay_adapter_conformance)
- [Controlled experiment results](docs/experiments/RESULTS.md)
- [Reviewer concern matrix](docs/reviewer-concern-matrix.md)
- [Binding round-trip artifacts](docs/experiments/bindings)
- [Active LeRobot round-trip artifacts](docs/experiments/lerobot_worldepisode_roundtrip)
- [Active LeRobot scene-leakage artifacts](docs/experiments/lerobot_scene_leakage)
- [ACT/Diffusion leakage gate artifacts](docs/experiments/lerobot_policy_gate)
- [Famous benchmark call-out artifacts](docs/experiments/benchmark_callout_audit)
- [Real-to-sim contract-drift artifacts](docs/experiments/realtosim_contract_drift)
- [Meta-simulator contract artifacts](docs/experiments/meta_simulator_contract)
- [USS state-drift pilot artifacts](docs/experiments/uss_state_drift_pilots)
- [Replay adapter conformance artifacts](docs/experiments/replay_adapter_conformance)
- [Single-line preflight artifacts](docs/experiments/preflight/preflight_report.json)
- [Active LeRobot control-replay artifacts](docs/experiments/lerobot_control_replay)
- [Pilot natural-source failure corpus](docs/experiments/natural_failure_corpus/manifest.json)
- [Research plan](docs/research-plan.md)
- [Reference release plan](docs/reference-release.md)
- [Governance draft](GOVERNANCE.md)
- [Minimal example](examples/minimal-static-world.layout.json)
- [Minimal WorldEpisode example](examples/minimal.worldepisode.json)
- [Scalable corpus manifest example](examples/scalable-corpus.worldepisode-dataset.json)

## Build The Paper

```bash
cd paper/arxiv
make root-pdf
```

If `latexmk` is unavailable:

```bash
cd paper/arxiv
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

## Single-Line Preflight Validator

Install the reference validator from this repository:

```bash
python3 -m pip install -e .
```

Run a blocking preflight before training:

```bash
worldepisode preflight examples/minimal.worldepisode.json
worldepisode preflight --kind lerobot /path/to/lerobot_v3_dataset
worldepisode preflight --kind rerun /path/to/recording.rrd --sidecar /path/to/worldepisode.manifest.json
```

Use the same check inside a LeRobot or Rerun pipeline:

```python
from worldepisode import preflight_lerobot, preflight_rerun

preflight_lerobot(dataset.root).raise_if_failed()
preflight_rerun("episode.rrd", sidecar="episode.worldepisode.json").raise_if_failed()
```

By default, `worldepisode preflight` exits non-zero on warnings as well as errors. This makes a
native LeRobot or Rerun artifact without a WorldEpisode sidecar fail closed before training, because
the native container cannot prove world revisions, persistent entity identity, action timing,
frame/clock mappings, lineage-safe splits, or conversion loss. Use `--advisory` only when warnings
should be reported without failing the command.

## Reproduce Controlled Results

```bash
python3 -m pip install -r requirements-experiments.txt
WORLDEPISODE_REQUIRE_ACTIVE_LEROBOT=1 python3 tools/run_experiments.py
```

If this Python environment does not include `pip`, use `uv`:

```bash
uv run --with-requirements requirements-experiments.txt \
  env WORLDEPISODE_REQUIRE_ACTIVE_LEROBOT=1 python tools/run_experiments.py
```

For only the active public LeRobot conversion:

```bash
python3 -m pip install -r requirements-experiments.txt
python3 tools/lerobot_worldepisode_roundtrip.py --required
```

To extend that conversion from the default single-episode run to the committed batch audit:

```bash
python3 tools/lerobot_worldepisode_roundtrip.py --required --batch-episode-indices 0,1,2,3,4
python3 tools/lerobot_worldepisode_roundtrip.py --required \
  --repo-id lerobot/pusht \
  --revision 7628202a2180972f291ba1bc6723834921e72c19 \
  --output-dir docs/experiments/lerobot_worldepisode_roundtrip_pusht \
  --batch-episode-indices 0,1,2,3,4 \
  --max-download-mb 4
```

For the active public LeRobot scene-leakage audit:

```bash
python3 -m pip install -r requirements-experiments.txt
python3 tools/lerobot_scene_leakage_experiment.py --required
```

To prepare the stronger ACT/Diffusion leakage gate from the same split manifest:

```bash
python3 tools/lerobot_policy_leakage_gate.py
```

To generate the source-level call-out audit over famous public robot-learning benchmarks:

```bash
python3 tools/benchmark_callout_audit.py
```

To generate the controlled real-to-sim contract-drift ablation:

```bash
python3 tools/realtosim_contract_drift.py
```

To generate the runtime-neutral simulator adapter contract:

```bash
python3 tools/meta_simulator_contract.py
```

To generate the USS non-robotics state-drift pilots:

```bash
python3 tools/uss_state_drift_pilots.py
```

To audit the production-scale dataset manifest:

```bash
python3 tools/dataset_scale_audit.py
```

To generate the dependency-free replay adapter conformance checks:

```bash
python3 tools/replay_adapter_conformance.py
```

For the active public LeRobot control-loop replay experiment:

```bash
python3 -m pip install -r requirements-experiments.txt
python3 tools/lerobot_control_replay_experiment.py --required
```

The scene-leakage audit uses `armnet/armnetbench_v01_lerobot_so101`, derives
WorldEpisode-style `world_lineage` hashes for task-scene/camera-layout groups, compares a random
episode split against a scene-disjoint split, and trains the same Torch MLP behavioral-cloning
baseline on both. In the committed run, the random split leaks all test scene lineages and obtains
0.850 offline BC success; the scene-disjoint split has zero lineage leakage and drops to 0.000.
The ACT/Diffusion gate converts that same split manifest into LeRobot-native `lerobot-train` jobs,
episode allowlists, and high-fidelity/physical rollout requirements; it is intentionally marked
open until real ACT/Diffusion metrics and rollout reports are committed.
The famous benchmark call-out audit applies the same requirement lens to Open X-Embodiment, DROID,
BridgeData V2, LIBERO, and CALVIN. It flags missing public leakage/timing controls, but does not
claim a benchmark score is inflated until a measured rerun exists.
The real-to-sim contract-drift ablation shows two proxy failures that visual reconstruction alone
cannot prevent: action-interface drift and representation-role drift. It is a controlled proxy, not
a hardware rollout, but it positions WorldEpisode as the contract layer around Gaussian/OpenUSD
real-to-sim pipelines.
The meta-simulator contract makes that runtime-neutral: MuJoCo is the current tested minimal replay
adapter, Isaac is adapter-ready but untested, and Genesis/SAPIEN are explicit adapter-required
targets. The claim is adapter compliance, not simulator-independent physics.
The replay adapter conformance harness adds a dependency-free scheduler check for delay,
zero-order-hold, missing-command, and asynchronous queue semantics. It is not a second physics
simulator; it keeps runtime adapters honest before a MuJoCo, Isaac, Genesis, or SAPIEN replay is
trusted.
The USS state-drift pilots add two lightweight non-robotics checks: a game-engine collision patch
where a loadable client asset no longer matches the authoritative state, and an autonomous-driving
clock-domain offset where valid logs produce invalid spatial fusion. These pilots support the USS
vocabulary claim only; they are not production game-engine or AV benchmark results.
The dataset-scale audit validates the scalable corpus manifest: namespaces, resolver coverage for
asset URI schemes, digest-addressed assets with mirrors, shard/index references, split-manifest
presence, world-lineage and asset-digest indexes, and append-only version structure. It is a catalog
invariant check, not a billion-episode throughput benchmark.

The active converter downloads bounded metadata/data shards from
`lerobot/svla_so101_pickplace`, converts episode 0 through
`LeRobotDataset v3 -> WorldEpisode -> LeRobotDataset v3`, and can extend the audit to episodes 0--4
with `--batch-episode-indices 0,1,2,3,4`. A second committed batch repeats the same audit on
`lerobot/pusht`. Together, the two public LeRobot batches preserve 1,935 action/state rows plus
sample timestamps, frame indices, episode indices, global sample indices, task indices, video
timestamp ranges, and physical-frame records with zero numerical loss. LeRobot source fields that
are absent, such as camera extrinsics and controller latency, are reported explicitly rather than
silently invented.

The control-loop replay experiment reads the exported SO-101 LeRobot v3 trajectory, estimates the
effective action delay from the timestamped action/state streams, writes a WorldEpisode action
contract, and tests timestamp-aware replay in MuJoCo. In the committed run, the inferred delay is
four 30 Hz frames (133 ms), validation alignment improves from 4.732 deg to 1.862 deg RMSE, and the
tested MuJoCo replay improves from 3.425 deg to 1.563 deg RMSE. The Isaac adapter contract is
emitted and marked ready, but Isaac is intentionally untested here.

For the lightweight controlled suite without requiring the active LeRobot dependency path:

```bash
python3 tools/run_experiments.py
```

The script writes:

- `docs/experiments/results.json`
- `docs/experiments/RESULTS.md`
- `docs/experiments/bindings/*`
- `docs/experiments/lerobot_worldepisode_roundtrip/*`
- `docs/experiments/lerobot_scene_leakage/*`
- `docs/experiments/lerobot_control_replay/*`
- `docs/experiments/dataset_scale_audit/*`
- `docs/experiments/replay_adapter_conformance/*`
- `docs/experiments/uss_state_drift_pilots/*`
- `docs/experiments/natural_failure_corpus/*`
- `docs/experiments/recorded_episodes/*`
- `conformance/fixtures/pilot/*`

## Relationship To URDF Studio

URDF Studio already implements the practical base:

- `docs/specs/WORLD_FORMAT.md`
- `docs/specs/world-v1.schema.json`
- `backend/models/world_scene_package.py`
- `backend/services/world_layout_static_transfer.py`
- cross-simulator transfer into MuJoCo, Genesis, PyBullet, MJX/MJLab, and Blender

WorldEpisode extracts the interoperable robotics contract and frames the existing world-layout work
as one profile within the broader USS spatial-state norm.

## License

Specification text, schemas, examples, and paper-adjacent documentation are released under CC0 1.0
Universal. Dataset assets and future SDK code should declare their own licenses.
