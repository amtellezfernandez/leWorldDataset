# WorldEpisode v0.1 Draft Specification

Status: draft.

WorldEpisode is a storage-neutral, representation-neutral interchange profile that binds a
robot-learning episode to an immutable world revision.

It does not replace LeRobotDataset, Rerun, NCore, MCAP, OpenUSD, glTF, GSDF, or simulator-native
formats. It specifies the semantic contract those systems can carry.

## 1. Core Model

A WorldEpisode record is:

```text
E = <M, W, B, K, F, C, O, A, X, V, P, Q>
```

Where:

- `M`: manifest and version.
- `W`: immutable base world revision.
- `B`: embodiment.
- `K`: task and outcome specification.
- `F`: frame graph.
- `C`: clocks and synchronization mappings.
- `O`: persistent entities and representations.
- `A`: action-space contract.
- `X`: synchronized observation/action trace references.
- `V`: world deltas and interaction events.
- `P`: provenance and derivation graph.
- `Q`: quality and uncertainty records.

The world state for episode `e` at time `t` is:

```text
W_e(t) = W^(r) + Delta W_e(t)
```

where `W^(r)` is an immutable, content-addressed world revision and `Delta W_e(t)` is the ordered
sequence of episode-specific state changes in a declared clock domain.

## 2. Five Graphs

### 2.1 Identity Graph

Every physical or logical entity MUST have a persistent `entity_id`. The same id MUST be usable
across observations, masks, bounding boxes, Gaussian groups, render meshes, collision bodies,
simulator actors, language references, contact events, object trajectories, and grasp events.

### 2.2 Frame and Clock Graph

Every spatial value MUST declare frame, units, transform direction, and validity interval.

Every temporal stream MUST declare a clock domain. Cross-clock mappings MUST declare offset,
drift model, and estimated error when available.

### 2.3 Representation-Role Graph

One entity MAY have many representations. Each representation MUST declare:

- `representation_id`
- `entity_id`
- `role`
- `asset.uri`
- `asset.media_type`
- `asset.sha256`
- `coordinate_frame`
- `units`
- `valid_interval`
- `derivation`
- `uncertainty`
- `license`

`asset.uri` MAY be a relative path, HTTPS URL, Hugging Face repository URI, object-storage URI,
OCI artifact URI, IPFS/content-addressed registry URI, or another registered resolver scheme.
Portability depends on deterministic resolution plus digest verification, not on forcing every
asset to live inside a local folder. `asset.mirrors[]` MAY provide local relative mirrors or
alternate resolvers. `asset.embedded` MAY carry small inline assets when a profile permits it.

Representation roles include `appearance`, `geometry`, `collision`, `semantics`, and `learned`.
Gaussian splats are an appearance role unless paired with an explicit physics proxy.

### 2.4 Temporal State and Event Graph

WorldEpisode SHOULD model interactions as events, not only poses. Event kinds include contact,
grasp, attachment, support, containment, articulation change, spawn/despawn, simulator reset,
intervention, subgoal completion, and failure detection.

### 2.5 Provenance and Derivation Graph

Every derived asset SHOULD identify source episodes, sensors, intervals, reconstruction algorithm,
software version, model/checkpoint hash, configuration, calibration revision, manual edits, input
and output hashes, creator, license, and quality metrics.

## 3. Action Semantics

Every action channel MUST declare:

- actuator
- control mode
- parameterization
- reference frame
- units
- absolute/delta/velocity semantics
- limits
- command rate
- command timestamp
- effective timestamp
- latency model
- interpolation
- normalization
- gripper semantics
- missing-value policy

An action vector without this contract is not portable.

## 4. Immutable World Revisions

Each episode MUST reference exactly one base `world_revision_id` and zero or more ordered episode
deltas. A new world revision is required when semantically relevant information changes, including
geometry, metric scale, calibration, collision proxies, physical parameters, entity decomposition,
object identity, or task-relevant fixtures.

## 5. Loss-Aware Conversion

Every converter SHOULD emit a machine-readable conversion report containing:

- source profile
- target binding
- preserved fields
- externalized fields
- approximated fields
- discarded fields
- warnings

Lossy conversion is allowed. Silent lossy conversion is not.

## 6. Conformance Requirements

The initial requirement namespace is:

| ID | Rule |
|---|---|
| `TIME.001` | Every temporal stream declares a clock domain. |
| `TIME.002` | Cross-clock mappings declare offset, drift model, and estimated error. |
| `FRAME.001` | Every spatial value declares coordinate frame and units. |
| `FRAME.002` | Every transform declares source-to-target direction and validity interval. |
| `ACTION.001` | Every action channel declares control mode, parameterization, frame, and units. |
| `ACTION.002` | Command time and effective-time semantics are declared. |
| `ENTITY.001` | Persistent entities maintain identity across representations and annotations. |
| `REP.001` | Every representation declares a role. |
| `WORLD.001` | Every world revision is immutable and content-addressed. |
| `TRACE.001` | Every episode references one base world revision and an ordered delta sequence. |
| `PROV.001` | Derived representations record source and transformation provenance. |
| `QUALITY.001` | Inferred or reconstructed values declare uncertainty and source status. |
| `CONVERT.001` | Every conversion emits a machine-readable loss report. |
| `SPLIT.001` | Dataset splits may enforce world, entity, and derivation-lineage disjointness. |
| `REPLAY.001` | Replay records simulator, version, solver, timestep, materials, and initialization assumptions. |
| `ASSET.001` | Every asset declares URI, media type, digest, and license when license is known. |
| `ASSET.002` | Every asset can be resolved deterministically and verified by digest. |

## 7. Initial Profiles

- `WE-Core`: episode, identity, time, frames, provenance.
- `WE-Physical-Coherence`: calibrations, units, uncertainty, action timing.
- `WE-Gaussian-Appearance`: Gaussian representations through glTF/OpenUSD-compatible bindings.
- `WE-Rigid-Manipulation`: rigid bodies, grippers, contacts, attachments.
- `WE-Replay`: simulator configuration, initial state, runtime checks.
- `WE-Counterfactual`: entity-level decomposition and editable world deltas.

Version 1 should target rigid tabletop manipulation with fixed-base single- or dual-arm robots.
