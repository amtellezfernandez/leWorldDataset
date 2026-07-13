# WorldEpisode Bindings

Status: draft.

WorldEpisode defines semantics first and storage second. Bindings describe how the semantic contract
is represented in existing containers, logs, scene formats, or dataset packages.

## Binding Principles

- Bindings MUST preserve requirement IDs and profile claims.
- Bindings MUST emit a conversion report when a source field cannot be represented natively.
- Bindings MAY externalize fields into sidecar manifests if the target container lacks a native
  location for them.
- Bindings MUST preserve asset descriptors as URI, media type, digest, and optional mirrors.
- Bindings SHOULD preserve persistent entity identity across masks, annotations, assets, simulator
  actors, events, and traces.

## Recommended Initial Bindings

| Binding | Primary Role | Preserved Natively | Common Sidecars or Reports |
|---|---|---|---|
| LeRobotDataset v3 | Policy-training view | episode metadata, observations, actions, timestamps, media streams | world revision, entity graph, action semantics beyond native schema, provenance, split-lineage constraints |
| Rerun `.rrd` | Multirate physical-data view | time-indexed streams, transforms, annotations, visualization/query data | conformance profile claims, conversion-loss report, persistent world revision manifest |
| NVIDIA NCore | Sensor and reconstruction capture | sensor models, calibrations, pose graphs, transform conventions | action/task/outcome semantics, world deltas, learning split lineage |
| MCAP / ROS 2 | Raw robotics logs | timestamped messages, transforms, schemas, robot telemetry | immutable world revision, entity-role graph, action normalization, provenance graph |
| OpenUSD / SimReady | Composed simulation world | scene composition, assets, physics metadata, runtime validation hooks | episode trace, action contract, task/outcome records, split lineage |
| glTF Gaussian / SPZ | Portable Gaussian appearance asset | Gaussian appearance payload and asset metadata | entity graph, collision roles, world revision, replay assumptions |
| GSDF / GSWorld-style assets | Gaussian-plus-physics manipulation asset | Gaussian assets, robot/object scene integration, physics proxies | storage-neutral episode binding, loss report, profile mapping |
| ASAM OpenLABEL | Annotation interchange | objects, actions, events, contexts, coordinate-system annotations | action-space contract, world revision identity, replay assumptions |
| MLCommons Croissant | Dataset discovery and loading | metadata, distributions, loading records | physical semantics, world deltas, replay and conversion diagnostics |
| W3C PROV-O | Provenance graph | entities, activities, agents, derivation relationships | robotics-specific action/world/replay semantics |

## Loss Report Shape

Converters should produce a report similar to:

```json
{
  "source_profile": "worldepisode/0.1",
  "target_binding": "lerobot-v3",
  "preserved": ["observations", "actions", "timestamps", "tasks"],
  "externalized": ["world_revision", "entity_graph", "provenance"],
  "approximated": ["contact_material"],
  "discarded": ["solver_warm_start_state"],
  "warnings": ["target binding cannot express action latency distribution"]
}
```

Lossy conversion is acceptable only when the loss is declared.

