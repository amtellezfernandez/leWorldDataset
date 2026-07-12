# leWorldLayout

`leWorldLayout` is the paper and specification base for a portable robot-world layout format.

The goal is to make authored robot scenes portable across viewers, simulators, dataset pipelines,
and benchmark runners without forcing every tool to invent its own scene JSON. The format starts
from the working World format implemented in URDF Studio, then separates the stable public norm
from the implementation details.

## Repository Layout

- `paper/` - paper draft and outline.
- `spec/` - normative format text.
- `schemas/` - machine-readable JSON Schema drafts.
- `examples/` - small valid layout examples.
- `notes/` - research notes, decisions, and open questions.

## Core Position

A world layout is a simulator-agnostic scene contract:

- it names objects, cameras, robot state, and task-time state in one portable document;
- it stores world-frame poses and dimensions explicitly;
- it separates appearance assets from physics/collision proxies;
- it requires portable relative asset references;
- it is valid as a single JSON file, a folder of JSON plus assets, or an envelope inside a registry.

This repository should become the paper-facing source of truth for that norm. URDF Studio remains
the reference implementation and validation workbench.

## Current Drafts

- [Paper draft](paper/le-world-layout.md)
- [Normative draft spec](spec/le-world-layout-v0.1.md)
- [JSON Schema draft](schemas/le-world-layout-v0.schema.json)
- [Minimal example](examples/minimal-static-world.layout.json)

## Relationship To URDF Studio

URDF Studio already implements the practical base:

- `docs/specs/WORLD_FORMAT.md`
- `docs/specs/world-v1.schema.json`
- `backend/models/world_scene_package.py`
- `backend/services/world_layout_static_transfer.py`
- cross-simulator transfer into MuJoCo, Genesis, PyBullet, MJX/MJLab, and Blender

`leWorldLayout` extracts the interoperable contract and frames it as a format/norm that other
robotics tools can adopt.

