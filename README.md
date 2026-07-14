# WorldEpisode (Universal Spatial State)

`WorldEpisode` is an executable state-integrity contract for diagnosing and correcting silent state
drift in robot-learning datasets. It targets failures where local files still load, but behavior is
invalid because state ancestry, asset identity, frame/clock mappings, representation roles,
transition semantics, or provenance drifted. We call the general family of invariants Universal
Spatial State (USS); WorldEpisode is the robotics profile implemented and evaluated in this
repository, and the only domain with measured evidence.

The goal is not another monolithic file format: WorldEpisode is a sidecar contract that binds into
LeRobotDataset, Rerun, MCAP, NCore, OpenUSD, glTF Gaussian splats, and other containers. OpenUSD
standardizes how the 3D world is composed; WorldEpisode standardizes how a robot modifies state
within that space over time without silent data corruption.

## Paper

- [WorldEpisode.pdf](WorldEpisode.pdf) - publication build
- [WorldEpisode-collab.pdf](WorldEpisode-collab.pdf) - working build with the C1--C7
  open-contribution task cards for collaborators
- [arXiv LaTeX source](paper/arxiv/main.tex) (`make -C paper/arxiv root-pdf` for the publication
  build, `make -C paper/arxiv collab-pdf` for the collab build)

## Quickstart: Preflight Validation

Install the reference validator and run a blocking check before training:

```bash
python3 -m pip install -e .
worldepisode preflight examples/minimal.worldepisode.json
worldepisode preflight --kind lerobot /path/to/lerobot_v3_dataset
worldepisode preflight --kind rerun /path/to/recording.rrd --sidecar /path/to/worldepisode.manifest.json
```

Or inside a LeRobot or Rerun pipeline:

```python
from worldepisode import preflight_lerobot, preflight_rerun

preflight_lerobot(dataset.root).raise_if_failed()
preflight_rerun("episode.rrd", sidecar="episode.worldepisode.json").raise_if_failed()
```

By default the preflight exits non-zero on warnings as well as errors, so a native LeRobot or Rerun
artifact without a WorldEpisode sidecar fails closed before training: the native container cannot
prove world revisions, entity identity, action timing, frame/clock mappings, lineage-safe splits,
or conversion loss. Use `--advisory` to report without failing.

Run the test suite (validator, preflight, CLI, and every conformance fixture):

```bash
python3 -m pip install -e '.[dev]'
make test
```

## Core Position

- **storage-neutral**: serializable in LeRobot, Rerun, NCore, MCAP, or a reference package;
- **representation-neutral**: splats, meshes, NeRFs, point clouds, collision proxies, telemetry;
- **runtime-neutral**: adapters for MuJoCo, Genesis (tested), Isaac Sim, SAPIEN (contract only);
- **loss-explicit**: conversions may be lossy, but never silently lossy;
- **resolver-neutral**: assets are portable through URI, media type, digest, and mirrors;
- **dataset-scale**: corpora use scoped IDs, shard catalogs, indexes, and append-only snapshots.

Gaussian splats are a high-value profile and demonstration, not the core claim. The stronger claim
is persistent, verifiable spatial-state interoperability, with robotics as the hardest current
stress test.

## Evidence

Measured results committed in this repository (details and boundaries in
[docs/experiments/RESULTS.md](docs/experiments/RESULTS.md)):

- **Scene leakage**: on a public SO-101 LeRobot release, a random episode split scores 0.850
  offline BC success and a scene-disjoint split drops the same probe to 0.000 (temporal ridge
  baseline: 0.925 to 0.420).
- **Action timing**: declaring the inferred 133 ms actuation delay cuts validation joint RMSE from
  4.732 to 1.862 degrees, and same-trace MuJoCo/Genesis replay RMSE from 3.425 to 1.563 degrees.
- **Loss-explicit conversion**: a LeRobot v3 round trip over ten public episodes preserves 1,935
  rows with maximum numerical error 0.0 while reporting source-absent fields as explicit loss.
- **Validator**: all 14 injected fault classes detected (1.000 recall, 0.933 precision); a
  clean-room reader reproduces the results without importing the package.

Stronger claims are intentionally open and fail-closed: ACT/Diffusion rollouts, famous-benchmark
inflation (the one executed DROID subset rerun does **not** show inflation), Isaac/SAPIEN replay,
external adoption. They are indexed with reproduction commands in
[docs/experiments/open_reproduction_gates](docs/experiments/open_reproduction_gates) and staged as
task cards C1--C7 in [WorldEpisode-collab.pdf](WorldEpisode-collab.pdf).

Reproduce everything:

```bash
python3 -m pip install -r requirements-experiments.txt
WORLDEPISODE_REQUIRE_ACTIVE_LEROBOT=1 python3 tools/run_experiments.py
python3 tools/release_readiness.py --strict-rfc
```

Full walkthrough: [docs/reproduction.md](docs/reproduction.md). Complete artifact index:
[docs/artifacts-index.md](docs/artifacts-index.md).

## Repository Layout

- `paper/arxiv/` - arXiv-ready LaTeX paper source.
- `spec/` - evidence-gated v0 RFC specification.
- `schemas/` - machine-readable v0 JSON Schemas.
- `conformance/` - requirement IDs, profiles, and fixture corpora.
- `worldepisode/` - reference validator, preflight CLI, and Python API.
- `tests/` - pytest suite over the validator, preflight, CLI, and conformance corpora.
- `tools/` - experiment runners, audits, and release gates.
- `docs/` - bindings, SDK contract, results, reproduction guide, and artifact index.
- `examples/` - small valid examples.
- `notes/` - research notes, decisions, and open questions.

## Relationship To URDF Studio

URDF Studio implements the practical base (world format, scene packages, cross-simulator transfer
into MuJoCo, Genesis, PyBullet, MJX/MJLab, and Blender). WorldEpisode extracts the interoperable
robotics contract and frames that world-layout work as one profile within the broader USS
spatial-state norm.

## License

Specification text, schemas, examples, and paper-adjacent documentation are released under CC0 1.0
Universal (`LICENSE`). The `worldepisode` reference validator, preflight CLI, and Python API are
released under Apache License 2.0 (`LICENSE-APACHE`). Dataset assets should declare their own
licenses.
