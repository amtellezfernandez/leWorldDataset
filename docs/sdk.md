# Reference SDK Contract

Status: v0 SDK contract with an implemented preflight subset.

The reference SDK should expose semantic objects and lazy bindings. The SDK is not the standard,
but it is the executable proof that the standard can be validated, converted, and inspected.

## CLI

```bash
worldepisode preflight dataset_or_manifest
worldepisode validate dataset/
worldepisode inspect dataset/
worldepisode index build dataset/
worldepisode index compact dataset/
worldepisode resolve asset dataset/ asset_id
worldepisode resolve shard dataset/ shard_id
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

The implemented `v0.1.0` package currently provides the blocking preflight/validate surface:

```bash
python3 -m pip install -e .
worldepisode preflight examples/minimal.worldepisode.json
worldepisode preflight --kind lerobot /path/to/lerobot_v3_dataset
worldepisode preflight --kind rerun /path/to/recording.rrd --sidecar /path/to/worldepisode.manifest.json
```

`preflight` defaults to fail-closed behavior: warnings return a non-zero exit code, because a native
LeRobot folder or Rerun `.rrd` without a WorldEpisode sidecar cannot prove replay-safe physical
semantics. `--advisory` keeps the diagnostics but exits non-zero only on errors.

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

The implemented one-line preflight API is:

```python
from worldepisode import preflight, preflight_lerobot, preflight_rerun

preflight("episode.worldepisode.json").raise_if_failed()
preflight_lerobot(dataset.root).raise_if_failed()
preflight_rerun("episode.rrd", sidecar="episode.worldepisode.json").raise_if_failed()
```

The full semantic validator runs on `worldepisode-0.1` manifests. Native LeRobot and Rerun inputs
are recognized directly, but without a sidecar they produce blocking diagnostics for the missing
world, entity, representation-role, action-timing, frame/clock, split-lineage, and conversion-loss
controls.

For production corpora, `Dataset.open` should read the dataset manifest first and then lazily load
only the shards selected by indexes and partition keys:

```python
from worldepisode import Dataset

dataset = Dataset.open("hf://organization/worldepisode-corpus@v2026.07")

for shard in dataset.shards(
    kind="episode_trace",
    partition={"robot_family": "so101", "split": "train"},
):
    for episode in shard.iter_episodes(columns=["episode_id", "world_revision_id", "action"]):
        process(episode)
```

The SDK must be able to answer catalog queries without listing the backing object store or loading
all episodes into memory.

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

At dataset scale, resolver configuration lives in the dataset manifest. The SDK should respect
manifest-declared resolver priority, local mirror policy, and cache policy before fetching remote
assets.

## Dataset-Scale Contract

The SDK should expose:

- `dataset.namespaces()` for globally scoped episode, world, entity, asset, and embodiment IDs;
- `dataset.shards(kind=..., partition=...)` for partition-pruned lazy access;
- `dataset.index("world_lineage")` for leakage and split audits;
- `dataset.resolve_asset(asset_id)` for digest-verified asset lookup;
- `dataset.version(version_id)` for immutable release snapshots;
- `dataset.tombstones()` for removals and supersessions.

Opening a production dataset must start from the manifest and its indexes. It must not depend on a
recursive directory scan.

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
