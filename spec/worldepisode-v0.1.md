# WorldEpisode v0.1 RFC Specification

Status: active RFC.

WorldEpisode is a storage-neutral, representation-neutral interchange profile that binds a
robot-learning episode to an immutable world revision. At dataset scale, it also defines a manifest
and index layer for sharded corpora.

It does not replace LeRobotDataset, Rerun, NCore, MCAP, OpenUSD, glTF, GSDF, or simulator-native
formats. It specifies the semantic contract those systems can carry.

## 1. Core Model

A WorldEpisode core record describes one episode:

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

Each episode also induces a coupled graph object:

```text
G_E = (G_I, G_FC, G_R, G_T, G_P)
```

Where:

- `G_I`: persistent entity identity graph.
- `G_FC`: frame and clock graph.
- `G_R`: representation-role graph mapping entities to assets and roles.
- `G_T`: temporal state and interaction-event graph.
- `G_P`: provenance and derivation graph.

A core episode record is valid only if graph references are closed, the base world revision is
content-addressed, and every lossy binding emits a conversion report:

```text
valid(E) iff closed(G_E) and hashed(W^(r)) and for every binding b there exists L_b
```

`closed(G_E)` means every entity, frame, clock, action, asset, event, and provenance reference
resolves to a declared node. `L_b` records preserved, externalized, approximated, and discarded
semantics for binding `b`.

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
- policy-output timestamp semantics
- action-enqueue timestamp semantics
- queue-consume timestamp semantics
- motor-receive/effective timestamp semantics
- action-chunk horizon, stride, and selection policy when chunked control is used
- interpolation
- aggregation policy when several policy outputs compete for one control tick
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

## 6. Dataset-Scale Manifest and Sharding

The reference directory layout is a packaging profile for examples, fixtures, and small artifacts.
It is not the production architecture for large robot datasets.

A WorldEpisode dataset manifest describes the corpus without requiring recursive filesystem scans,
object-store listings, or eager loading of every episode. It declares:

- dataset identity, release version, and append-only versioning policy;
- globally scoped namespaces for episodes, worlds, entities, assets, embodiments, tasks, splits,
  and provenance;
- URI resolvers, cache policies, and mirror priority;
- registries for world revisions, entities, embodiments, action spaces, tasks, schemas, provenance,
  quality records, and conversion reports;
- sharded payload catalogs with URI, media type, digest, schema reference, partition keys, byte
  size, row count, and statistics when available;
- materialized indexes for episode lookup, world lineage, entity lookup, asset digests,
  split membership, time ranges, and embodiment/task queries;
- split manifests and append-only release snapshots with tombstones or supersession records.

Persistent identifiers MUST be globally scoped when they cross a dataset boundary. Bindings MAY use
compact local identifiers inside a shard, but those local identifiers MUST resolve through declared
namespaces before they are compared with identifiers from another dataset.

Payloads MAY live in LeRobot, Rerun, NCore, MCAP, Parquet/Arrow, OpenUSD, glTF, object storage,
Hugging Face repositories, OCI artifacts, IPFS, HTTP(S), local mirrors, or other registered storage
systems. The semantic API is the manifest and its indexes, not the physical folder layout.

## 7. Conformance Requirements

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
| `DATASET.001` | Dataset-scale deployments declare a manifest with shard and index catalogs; opening or validating a dataset does not require recursive storage scans. |
| `DATASET.002` | Every shard and index declares URI, media type, digest, schema reference, partition keys, and row/object counts where available. |
| `DATASET.003` | Persistent IDs are globally scoped by declared namespace when crossing dataset boundaries. |
| `DATASET.004` | Dataset versions are append-only snapshots; replacement or removal uses tombstones or supersession records. |
| `DATASET.005` | Resolvers declare supported URI schemes, cache policy, and mirror priority for deterministic resolution at scale. |

## 8. Initial Profiles

- `WE-Core`: episode, identity, time, frames, provenance.
- `WE-Dataset-Scale`: manifest, namespaces, shard catalogs, indexes, resolvers, and append-only snapshots.
- `WE-Physical-Coherence`: calibrations, units, uncertainty, action timing.
- `WE-Gaussian-Appearance`: Gaussian representations through glTF/OpenUSD-compatible bindings.
- `WE-Rigid-Manipulation`: rigid bodies, grippers, contacts, attachments.
- `WE-Replay`: simulator configuration, initial state, runtime checks.
- `WE-Counterfactual`: entity-level decomposition and editable world deltas.

The v1 target is rigid tabletop manipulation with fixed-base single- or dual-arm robots.
