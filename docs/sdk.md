# Reference SDK Contract

Status: draft.

The reference SDK should expose semantic objects and lazy bindings. The SDK is not the standard,
but it is the executable proof that the standard can be validated, converted, and inspected.

## CLI

```bash
worldepisode validate dataset/
worldepisode inspect dataset/
worldepisode diff-world world_a world_b
worldepisode audit-splits dataset/
worldepisode report-lineage dataset/
worldepisode replay-check episode_id
worldepisode import lerobot ...
worldepisode import ncore ...
worldepisode import mcap ...
worldepisode import gsdf ...
worldepisode export lerobot ...
worldepisode export rerun ...
worldepisode export usd ...
worldepisode export gltf ...
worldepisode conversion-report report.json
```

## Python API

```python
from worldepisode import Dataset

dataset = Dataset.open("hf://organization/dataset")

episode = dataset.episode("episode_000421")
world = episode.base_world
state = episode.world_at(timestamp_ns=12_540_000_000)

camera = episode.sensor("wrist_camera")
action_spec = episode.action_space("right_arm")

mug = state.entity("mug_017")
appearance = mug.representation(role="appearance")
collision = mug.representation(role="collision")

report = episode.validate(profile="WE-Rigid-Manipulation")
```

## Resolver Contract

Asset resolution is a first-class SDK service:

```python
asset = world.asset("world_demo_tabletop")
resolved = dataset.resolver.resolve(asset)
resolved.verify_sha256()
```

Resolvers MUST support deterministic digest verification. They MAY support:

- local relative paths;
- HTTP(S);
- Hugging Face repositories;
- object storage;
- OCI artifacts;
- IPFS or other content-addressed registries;
- embedded base64 assets where a profile permits them.

## Validator Output

Diagnostics should include requirement id, severity, location, message, and optional repair hint:

```json
{
  "requirement": "ACTION.003",
  "severity": "error",
  "location": "/action_space/channels/0",
  "message": "Action channel does not declare absolute, delta, velocity, normalized, or target semantics.",
  "hint": "Set semantics to one of delta, absolute, velocity, normalized, or target."
}
```

