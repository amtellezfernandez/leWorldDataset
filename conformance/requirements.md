# WorldEpisode Conformance Requirements

Status: draft.

This document defines the first executable requirement namespace for WorldEpisode. The prose
specification explains the model; these requirements define what validators, fixtures, and
conversion reports should test.

Requirement levels:

- `MUST`: required for the named profile.
- `SHOULD`: expected unless a profile or binding documents why it cannot be preserved.
- `MAY`: optional extension behavior.

Severity levels:

- `error`: invalid for the profile.
- `warning`: valid but not recommended or incomplete.
- `info`: valid advisory diagnostic.

## Time

| ID | Level | Severity | Normative Rule | Validation Target |
|---|---|---|---|---|
| `TIME.001` | MUST | error | Every temporal stream declares a clock domain. | Trace streams, event tables, sensor streams, action streams. |
| `TIME.002` | MUST | error | Every cross-clock mapping declares source clock, target clock, offset, drift model, and estimated error when a cross-clock conversion is used. | Clock graph mappings. |
| `TIME.003` | SHOULD | warning | Camera observations declare exposure start and end when available. | Camera stream metadata. |
| `TIME.004` | SHOULD | warning | Actions declare both command timestamp and effective timestamp semantics. | Action channel metadata. |

## Frames

| ID | Level | Severity | Normative Rule | Validation Target |
|---|---|---|---|---|
| `FRAME.001` | MUST | error | Every spatial value declares coordinate frame and units. | Poses, transforms, meshes, splats, collision assets, annotations. |
| `FRAME.002` | MUST | error | Every transform declares source-to-target direction and validity interval. | Frame graph transforms. |
| `FRAME.003` | MUST | error | Quaternion convention is declared whenever quaternions are used. | Frame graph and pose traces. |
| `FRAME.004` | SHOULD | warning | Reconstructed or calibrated transforms include uncertainty or calibration revision. | Transform records. |

## Entities and Representations

| ID | Level | Severity | Normative Rule | Validation Target |
|---|---|---|---|---|
| `ENTITY.001` | MUST | error | Persistent entities maintain identity across observations, representations, annotations, events, and simulator actors. | Entity graph and all references. |
| `ENTITY.002` | MUST | error | Entity identifiers are stable within a world lineage and are not reused for different physical entities. | World revisions and deltas. |
| `REP.001` | MUST | error | Every representation declares a role such as `appearance`, `geometry`, `collision`, `semantics`, or `learned`. | Representation records. |
| `REP.002` | MUST | error | A representation role is not treated as another role without an explicit conversion and loss report. | Converters and bindings. |
| `REP.003` | SHOULD | warning | Gaussian splats used for appearance have a separate collision or physics representation when replay is claimed. | Gaussian appearance and replay profiles. |

## Assets

| ID | Level | Severity | Normative Rule | Validation Target |
|---|---|---|---|---|
| `ASSET.001` | MUST | error | Every external asset declares URI, media type, digest, and license when license is known. | Asset descriptors. |
| `ASSET.002` | MUST | error | Every asset can be resolved deterministically and verified by digest. | Asset resolvers and package manifests. |
| `ASSET.003` | MAY | info | Assets may use relative paths, HTTP(S), Hugging Face, object storage, OCI, IPFS, content-addressed registries, or registered resolver schemes. | Asset URI parser. |
| `ASSET.004` | SHOULD | warning | Remote assets provide at least one local mirror or cache hint for reproducible offline evaluation. | Asset descriptors. |
| `ASSET.005` | MUST | error | Embedded assets declare encoding, media type, and digest of the decoded bytes. | Embedded asset descriptors. |

## Actions

| ID | Level | Severity | Normative Rule | Validation Target |
|---|---|---|---|---|
| `ACTION.001` | MUST | error | Every action channel declares control mode, parameterization, frame, and units. | Action space metadata. |
| `ACTION.002` | MUST | error | Command time and effective-time semantics are declared. | Action space metadata and traces. |
| `ACTION.003` | MUST | error | Absolute, delta, velocity, normalized, or target semantics are declared for every action dimension. | Action channels. |
| `ACTION.004` | SHOULD | warning | Limits, interpolation, latency model, and missing-value policy are declared. | Action channels. |
| `ACTION.005` | SHOULD | warning | Gripper channels declare open/close semantics, force interpretation, and attachment policy when used for replay. | Gripper channels. |

## Worlds, Trace, and Replay

| ID | Level | Severity | Normative Rule | Validation Target |
|---|---|---|---|---|
| `WORLD.001` | MUST | error | Every world revision is immutable and content-addressed. | World revision records. |
| `WORLD.002` | MUST | error | A new revision is created when geometry, scale, calibration, collision proxies, physical parameters, entity decomposition, object identity, or task-relevant fixtures change. | World lineage. |
| `TRACE.001` | MUST | error | Every episode references one base world revision and an ordered delta sequence. | Episode records. |
| `TRACE.002` | SHOULD | warning | Events represent contacts, grasps, attachments, support, containment, resets, interventions, subgoals, and failures when known. | Event tables. |
| `REPLAY.001` | MUST | error | Replay records simulator, version, solver, timestep, materials, initialization assumptions, and tolerance envelope. | Replay manifests. |
| `REPLAY.002` | SHOULD | warning | Cross-simulator replay reports measured divergence rather than claiming simulator-independent identity. | Replay reports. |

## Provenance, Quality, Conversion, and Splits

| ID | Level | Severity | Normative Rule | Validation Target |
|---|---|---|---|---|
| `PROV.001` | MUST | error | Every derived representation records source and transformation provenance. | Provenance graph. |
| `PROV.002` | SHOULD | warning | Provenance uses W3C PROV-compatible entities, activities, and agents when serialized as JSON-LD. | Provenance exports. |
| `QUALITY.001` | MUST | error | Inferred or reconstructed values declare uncertainty and source status. | Quality records. |
| `CONVERT.001` | MUST | error | Every conversion emits a machine-readable loss report. | Import/export commands. |
| `CONVERT.002` | MUST | error | Loss reports classify fields as preserved, externalized, approximated, discarded, or warning. | Conversion reports. |
| `SPLIT.001` | SHOULD | warning | Dataset splits may enforce world, entity, source-capture, reconstruction-run, generated-asset-family, and site disjointness. | Split manifests. |

