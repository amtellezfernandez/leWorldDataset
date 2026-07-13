# leWorldLayout Legacy Profile Notes

`leWorldLayout` is retained as a legacy world-layout profile and implementation root for
WorldEpisode. It is not the public paper category. The public paper and specification name is
`WorldEpisode`: a storage-neutral interchange contract linking robot-learning episodes to immutable,
versioned, replayable 3D worlds.

## Abstract

Robotics tools routinely exchange robot models, but they exchange robot-world scenes poorly.
URDF, MJCF, USD, and simulator-native scene files each capture part of the problem, yet none acts
as a small, portable, simulator-agnostic layout contract for the authored state surrounding a robot:
objects, cameras, frame conventions, task-time state, asset references, and the split between visual
appearance and physical collision. The `leWorldLayout` profile records static or time-indexed world
objects in a declared frame convention, uses deterministic asset descriptors, and separates
appearance representations from physics geometry so that splats, meshes, primitives, and simulator
colliders can coexist without ambiguity. In the WorldEpisode architecture, this profile is one
possible world-revision binding. A reference implementation in URDF Studio validates the profile and
transfers the same layout into MuJoCo, Genesis, PyBullet, MJX/MJLab, and Blender.

## 1. Motivation

Robot assets are not enough to reproduce a manipulation scene. A reusable scene also needs:

- object identities and semantic roles;
- poses, dimensions, and frame conventions;
- robot joint state and optional embedded URDF;
- cameras and observation configuration;
- asset paths that work outside the author machine;
- collision proxies for high-fidelity visual assets;
- a stable envelope for registries, datasets, and benchmark tasks.

Existing scene formats are strong inside their own ecosystems but weak as a minimal interchange
contract. A MuJoCo MJCF is not a neutral description for Blender authoring. A USD stage is powerful
but too broad to be a lightweight validation target for small robot-world datasets. A URDF gives the
robot but not the authored world around it. Dataset samples often store enough state to replay one
pipeline but not enough to be a public scene norm.

The profile targets the missing middle: a small, inspectable, validated layout document that can be
consumed by many downstream tools.

## 2. Thesis

A portable world layout format should be:

1. **Simulator-agnostic**: the document should not name a physics engine as its source of truth.
2. **Asset-portable**: all assets must declare a URI, media type, digest, and optional mirrors so
   consumers can resolve and verify bytes deterministically across local and remote storage.
3. **Frame-explicit**: frame convention must be declared or mappable, not silently inferred.
4. **Appearance/physics separated**: visual assets and simulation geometry are related but not the
   same contract.
5. **Static-first, scenario-ready**: static layouts should be simple, while dynamic/task layers can
   reference the same world document.
6. **Schema-validatable**: third-party tools should validate documents without importing a full app.

## 3. Format Overview

The authored document has one primary object:

```json
{
  "schema_version": "le-world-layout-0.1",
  "world_layout": {
    "name": "desk-setup",
    "objects": [],
    "scenario_time_ms": 0,
    "scenario_duration_ms": 0,
    "urdf_xml": "<robot name=\"demo\"/>",
    "joint_positions": {},
    "cameras": []
  },
  "environment": {
    "frame_convention": "ros-rep-103"
  }
}
```

Every object records a stable id, pose, dimensions, type, optional semantic role, optional
appearance representations, optional physics geometry, and optional consistency metadata linking
appearance to physics.

## 4. Normative Object Model

World objects should be represented with three layers:

- `identity`: `id`, `name`, `semantic_role`;
- `layout`: `type`, `position_xyz`, `rotation_rpy_rad`, `size_xyz`, `color`;
- `transfer`: `appearance`, `physics`, and `consistency`.

The important design choice is that appearance does not imply collision. A Gaussian splat may be a
useful visual/perception asset and still be invalid as simulator geometry. A mesh may be visually
accurate and still require a simplified collision proxy. The layout profile makes this split
explicit.

## 5. Relationship To Scenarios

A layout is not a task. A scenario references a layout and adds:

- task instruction and role bindings;
- randomization;
- policy and control timing;
- success and guard conditions;
- evaluation metrics and artifact recording.

This separation allows the same layout to support manual inspection, Blender edits, simulator
transfer, dataset packaging, and benchmark execution.

## 6. Reference Implementation

URDF Studio currently provides the implementation base:

- schema generation and validation;
- browser import from JSON, folder, or link;
- static world transfer;
- asset reference validation;
- cross-simulator transfer into MuJoCo, Genesis, PyBullet, MJX/MJLab, and Blender;
- scenario-level benchmark execution above the world layout layer.

The paper should report this as an existence proof, not as a requirement that all adopters use URDF
Studio.

## 7. Evaluation Plan

The paper should evaluate:

1. **Interchange coverage**: one layout imported into multiple targets without target-specific
   authoring.
2. **Validation quality**: invalid paths, missing collision proxies, frame ambiguity, and dynamic
   timestamps rejected early.
3. **Authoring loop**: browser or Blender edits round-trip back into the same layout contract.
4. **Benchmark reuse**: scenarios reference the same world layout across simulators.
5. **Ablations**: compare flat mesh-only objects against explicit appearance/physics split.

## 8. Claimed Contributions

- A compact world-layout profile for robot-world scene interchange inside WorldEpisode.
- A validated appearance/physics split for meshes, primitives, and splats.
- A deterministic asset-resolution rule suitable for files, folders, links, object storage,
  Hugging Face repositories, OCI artifacts, IPFS, and registries.
- A reference implementation and cross-simulator transfer path in URDF Studio.
- A bridge between scene authoring and scenario-level robot evaluation.

## 9. Open Questions

- Which frame convention identifiers should be mandatory in v0.1?
- Should dynamic layouts live in this spec or only in a scenario layer?
- Which fields should be required for publication versus allowed for local drafts?
- How strict should the paper be about JSON canonicalization and registry digests?
