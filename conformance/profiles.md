# WorldEpisode Conformance Profiles

Status: active v0 profile set.

Profiles are composable. A dataset can claim several profiles if it passes every required rule for
each claimed profile.

## USS-Core-23 Semantic Projection

Purpose: make the binding-retention experiment auditable by publishing the exact semantic fields
and pilot binding capability model used in the paper.

Artifact:

- `conformance/projections/uss-core-23.v0.json`
- `schemas/semantic-projection-v0.schema.json`

Scope:

- 23 semantic fields used by the executable binding-retention artifacts;
- field-to-requirement mappings;
- native-field and sidecar-field assumptions for each pilot binding.

Boundary: this is a versioned pilot projection, not a universal score of LeRobot, Rerun, NCore,
MCAP, OpenUSD, glTF, or future bindings. It should become normative only after external review or
independent implementation feedback.

## WE-Core

Purpose: minimal robot-learning episode binding to a versioned world.

Required requirement groups:

- `TIME.001`
- `FRAME.001`
- `FRAME.002`
- `ENTITY.001`
- `REP.001`
- `ASSET.001`
- `ASSET.002`
- `WORLD.001`
- `TRACE.001`
- `PROV.001`
- `CONVERT.001`

Minimum contents:

- manifest and schema version;
- one episode id and dataset id;
- one immutable world revision;
- one clock domain;
- one frame graph;
- persistent entities;
- representation records with asset descriptors;
- provenance for derived assets.

## WE-Dataset-Scale

Purpose: expose large and federated robot corpora without treating a folder tree as the dataset API.

Adds:

- `DATASET.001`
- `DATASET.002`
- `DATASET.003`
- `DATASET.004`
- `DATASET.005`
- `ASSET.003`
- `ASSET.004`
- `SPLIT.001`

Minimum contents:

- dataset manifest and release version;
- globally scoped namespaces for episodes, worlds, entities, assets, tasks, and embodiments;
- resolver registry with deterministic digest verification and mirror priority;
- shard catalog with schema references, partition keys, row counts, byte sizes, and statistics;
- materialized indexes for lookup by episode, world lineage, entity, asset digest, split, and time;
- append-only version snapshots with tombstones or supersession records.

## WE-Physical-Coherence

Purpose: detect units, transform, timing, and calibration errors that break physical interpretation.

Adds:

- `TIME.002`
- `TIME.003`
- `TIME.004`
- `FRAME.003`
- `FRAME.004`
- `ACTION.001`
- `ACTION.002`
- `ACTION.003`
- `ACTION.004`
- `QUALITY.001`

Minimum contents:

- clock mappings for multi-clock datasets;
- transform directions and valid intervals;
- quaternion convention;
- calibration revisions or uncertainty for calibrated transforms;
- full action-channel contract.

## WE-Gaussian-Appearance

Purpose: carry Gaussian-splat appearance without making Gaussian splats the core format.

Adds:

- `REP.002`
- `REP.003`
- `ASSET.003`
- `ASSET.004`

Minimum contents:

- Gaussian representation marked as `appearance`;
- glTF `KHR_gaussian_splatting`, SPZ, OpenUSD Gaussian schema, or another declared binding;
- entity mapping between splat groups and persistent entities when object-level identity is claimed;
- separate collision or geometry representation when replay is claimed.

## WE-Rigid-Manipulation

Purpose: fixed-base single- or dual-arm rigid tabletop manipulation.

Adds:

- `ENTITY.002`
- `ACTION.005`
- `TRACE.002`
- `WORLD.002`

Minimum contents:

- rigid manipulated objects and task-relevant fixtures;
- gripper semantics if a gripper is present;
- object poses or deltas when manipulated objects move;
- contact, grasp, attachment, support, and failure events when known.

## WE-Replay

Purpose: replay demonstrations under declared physical and numerical assumptions.

Adds:

- `REPLAY.001`
- `REPLAY.002`

Minimum contents:

- simulator target and version;
- solver, timestep, contact/material assumptions;
- initialization state;
- replay tolerance envelope;
- measured divergence report for each tested runtime.

## WE-Counterfactual

Purpose: support editable worlds and augmentation with explicit lineage.

Adds:

- `PROV.002`
- `SPLIT.001`

Minimum contents:

- object-level world deltas;
- generated asset lineage;
- counterfactual camera/object/background changes;
- split constraints that can exclude shared world, entity, or reconstruction lineage.
