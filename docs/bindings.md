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
| LeRobotDataset v3 | Policy-training view | Parquet state/action/timestamp rows, MP4 camera streams, episode metadata, task records, schema/statistics metadata | world revision, entity graph, representation roles, action semantics beyond the native training schema, provenance, split-lineage constraints |
| Rerun `.rrd` | Multirate physical-data view | time-indexed streams, transforms, annotations, visualization/query data | conformance profile claims, conversion-loss report, persistent world revision manifest |
| NVIDIA NCore | Sensor and reconstruction capture | sensor models, calibrations, pose graphs, transform conventions | action/task/outcome semantics, world deltas, learning split lineage |
| MCAP / ROS 2 | Raw robotics logs | timestamped messages, transforms, schemas, robot telemetry | immutable world revision, entity-role graph, action normalization, provenance graph |
| OpenUSD / SimReady | Composed simulation world | scene composition, assets, physics metadata, runtime validation hooks | episode trace, action contract, task/outcome records, split lineage |
| glTF Gaussian / SPZ | Portable Gaussian appearance asset | Gaussian appearance payload and asset metadata | entity graph, collision roles, world revision, replay assumptions |
| GSDF / GSWorld-style assets | Gaussian-plus-physics manipulation asset | Gaussian assets, robot/object scene integration, physics proxies | storage-neutral episode binding, loss report, profile mapping |
| ASAM OpenLABEL | Annotation interchange | objects, actions, events, contexts, coordinate-system annotations | action-space contract, world revision identity, replay assumptions |
| MLCommons Croissant | Dataset discovery and loading | metadata, distributions, loading records | physical semantics, world deltas, replay and conversion diagnostics |
| W3C PROV-O | Provenance graph | entities, activities, agents, derivation relationships | robotics-specific action/world/replay semantics |

## Active LeRobot v3 Converter

The repository includes an executable converter at `tools/lerobot_worldepisode_roundtrip.py`.
It downloads bounded shards from the pinned public dataset
`lerobot/svla_so101_pickplace@f641879e22172be7e8161d5e6c1503c2d2feb657`, converts episode 0 through
`LeRobotDataset v3 -> WorldEpisode -> LeRobotDataset v3`, exports a compact LeRobot v3 package, and
asserts zero numerical loss for action tensors, state tensors, sample timestamps, and video
timestamp ranges. Source semantics absent from LeRobot, including camera extrinsics, action units,
robot/world calibration, and controller latency, are tracked in the conversion report.

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
