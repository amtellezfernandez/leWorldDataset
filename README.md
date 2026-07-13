# WorldEpisode

`WorldEpisode` is the paper and specification base for a storage-neutral interchange contract
linking robot-learning episodes to immutable, versioned, replayable 3D worlds.

The old working directory name is `leWorldLayout`, but the formal standards/paper name should be
`WorldEpisode`. The goal is not to create another monolithic file format. The goal is to define the
semantic contract that can be bound into LeRobotDataset, Rerun, NCore, MCAP, OpenUSD, glTF Gaussian
splats, GSDF-style assets, or a reference package layout.

## Repository Layout

- `paper/arxiv/` - arXiv-ready LaTeX paper source.
- `paper/` - Markdown paper notes and outline.
- `spec/` - normative specification drafts.
- `schemas/` - machine-readable JSON Schema drafts.
- `conformance/` - requirement IDs, profiles, and fixture plan.
- `docs/` - bindings, SDK contract, research plan, and reference release plan.
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
- [Bindings draft](docs/bindings.md)
- [Reference SDK contract](docs/sdk.md)
- [Research plan](docs/research-plan.md)
- [Reference release plan](docs/reference-release.md)
- [Governance draft](GOVERNANCE.md)
- [Minimal example](examples/minimal-static-world.layout.json)
- [Minimal WorldEpisode example](examples/minimal.worldepisode.json)

## Build The Paper

```bash
cd paper/arxiv
make
```

If `latexmk` is unavailable:

```bash
cd paper/arxiv
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

## Relationship To URDF Studio

URDF Studio already implements the practical base:

- `docs/specs/WORLD_FORMAT.md`
- `docs/specs/world-v1.schema.json`
- `backend/models/world_scene_package.py`
- `backend/services/world_layout_static_transfer.py`
- cross-simulator transfer into MuJoCo, Genesis, PyBullet, MJX/MJLab, and Blender

WorldEpisode extracts the interoperable contract and frames the existing world-layout work as one
profile within a broader episode-to-world norm.
