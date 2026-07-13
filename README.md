# WorldEpisode

`WorldEpisode` is the paper and specification base for a storage-neutral interchange contract
linking robot-learning episodes to immutable, versioned, replayable 3D worlds.

The goal is not to create another monolithic file format. The goal is to define the semantic
contract that can be bound into LeRobotDataset, Rerun, NCore, MCAP, OpenUSD, glTF Gaussian splats,
GSDF-style assets, or a reference package layout.

## Paper

- [WorldEpisode.pdf](WorldEpisode.pdf)
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

WorldEpisode is:

- **storage-neutral**: it can be serialized in LeRobot, Rerun, NCore, MCAP, or a reference package;
- **representation-neutral**: appearance can be Gaussian splats, meshes, NeRFs, point clouds, or future representations;
- **runtime-neutral**: physical worlds can target Isaac Sim, MuJoCo, SAPIEN, Genesis, or other simulators;
- **loss-explicit**: conversions may be lossy, but never silently lossy.
- **resolver-neutral**: assets are portable through URI, media type, digest, and optional mirrors,
  not by forcing every asset into a local folder.

Gaussian splats are a high-value profile and demonstration, not the core claim. The stronger claim
is persistent, verifiable world-episode interoperability.

## Current Drafts

- [Paper PDF](WorldEpisode.pdf)
- [arXiv LaTeX paper](paper/arxiv/main.tex)
- [Markdown paper notes](paper/le-world-layout.md)
- [WorldEpisode draft spec](spec/worldepisode-v0.1.md)
- [WorldEpisode JSON Schema draft](schemas/worldepisode-core-v0.schema.json)
- [Conformance JSON Schema draft](schemas/conformance-requirements-v0.schema.json)
- [World layout profile draft](spec/le-world-layout-v0.1.md)
- [World layout JSON Schema draft](schemas/le-world-layout-v0.schema.json)
- [Conformance requirements](conformance/requirements.md)
- [Machine-readable requirements](conformance/requirements.v0.json)
- [Conformance profiles](conformance/profiles.md)
- [Pilot conformance corpus](conformance/fixtures/pilot/manifest.json)
- [Independent conformance fixtures](conformance/fixtures/independent/manifest.json)
- [Bindings draft](docs/bindings.md)
- [Reference SDK contract](docs/sdk.md)
- [Controlled experiment results](docs/experiments/RESULTS.md)
- [Binding round-trip artifacts](docs/experiments/bindings)
- [Active LeRobot round-trip artifacts](docs/experiments/lerobot_worldepisode_roundtrip)
- [Active LeRobot scene-leakage artifacts](docs/experiments/lerobot_scene_leakage)
- [Active LeRobot control-replay artifacts](docs/experiments/lerobot_control_replay)
- [Research plan](docs/research-plan.md)
- [Reference release plan](docs/reference-release.md)
- [Governance draft](GOVERNANCE.md)
- [Minimal example](examples/minimal-static-world.layout.json)
- [Minimal WorldEpisode example](examples/minimal.worldepisode.json)

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

## Reproduce Controlled Results

```bash
python3 -m pip install -r requirements-experiments.txt
WORLDEPISODE_REQUIRE_ACTIVE_LEROBOT=1 python3 tools/run_experiments.py
```

For only the active public LeRobot conversion:

```bash
python3 -m pip install -r requirements-experiments.txt
python3 tools/lerobot_worldepisode_roundtrip.py --required
```

For the active public LeRobot scene-leakage audit:

```bash
python3 -m pip install -r requirements-experiments.txt
python3 tools/lerobot_scene_leakage_experiment.py --required
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

The active converter downloads bounded metadata/data shards from
`lerobot/svla_so101_pickplace`, converts episode 0 through
`LeRobotDataset v3 -> WorldEpisode -> LeRobotDataset v3`, exports a small LeRobot v3 package, and
asserts zero numerical loss for action tensors, state tensors, timestamps, and video timestamp
ranges. LeRobot source fields that are absent, such as camera extrinsics and controller latency, are
reported explicitly rather than silently invented.

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
- `docs/experiments/recorded_episodes/*`
- `conformance/fixtures/pilot/*`

## Relationship To URDF Studio

URDF Studio already implements the practical base:

- `docs/specs/WORLD_FORMAT.md`
- `docs/specs/world-v1.schema.json`
- `backend/models/world_scene_package.py`
- `backend/services/world_layout_static_transfer.py`
- cross-simulator transfer into MuJoCo, Genesis, PyBullet, MJX/MJLab, and Blender

WorldEpisode extracts the interoperable contract and frames the existing world-layout work as one
profile within a broader episode-to-world norm.

## License

Specification text, schemas, examples, and paper-adjacent documentation are released under CC0 1.0
Universal. Dataset assets and future SDK code should declare their own licenses.
