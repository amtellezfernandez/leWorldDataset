# Production-Scale Dataset Architecture

Status: draft.

The single-episode `*.worldepisode.json` record is not the production dataset container. It is the
core semantic record for one episode. A corpus that spans laboratories, robot embodiments, capture
sessions, world reconstructions, and simulator exports needs a dataset manifest above those records.

WorldEpisode therefore separates three layers:

- **Core episode record:** the world revision, entities, frames, clocks, actions, trace references,
  events, provenance, and quality records for one episode.
- **Dataset manifest:** a small catalog that declares namespaces, resolvers, registries, shards,
  materialized indexes, split manifests, and append-only versions.
- **Payload backends:** LeRobot, Rerun, NCore, MCAP, Parquet/Arrow, USD, glTF, object storage,
  Hugging Face repositories, OCI artifacts, IPFS, or local mirrors.

The production contract is that opening or validating a dataset must start from the dataset manifest.
It must not require a recursive filesystem scan, a full object-store listing, or loading every
episode into memory.

## Dataset Manifest

A dataset-scale manifest declares:

- global dataset identity and release version;
- globally scoped namespaces for episodes, worlds, entities, assets, tasks, and embodiments;
- resolver priority for URI schemes such as `hf`, `https`, `s3`, `gs`, `az`, `oci`, `ipfs`, and
  local mirrors;
- registry shards for world revisions, entities, embodiments, action spaces, tasks, schemas,
  provenance, quality records, and conversion reports;
- payload shards with kind, URI, media type, digest, schema reference, partition keys, row counts,
  byte size, and column statistics when available;
- materialized indexes for episode lookup, world lineage, entity lookup, asset digests,
  split membership, time ranges, and embodiment/task queries;
- append-only release snapshots, parent versions, supersession records, and tombstones.

The draft machine-readable schema is
[`schemas/worldepisode-dataset-v0.schema.json`](../schemas/worldepisode-dataset-v0.schema.json).
The example
[`examples/scalable-corpus.worldepisode-dataset.json`](../examples/scalable-corpus.worldepisode-dataset.json)
shows the intended layout.

## ID Scope

Local names such as `mug_017` or `episode_000421` are not sufficient across world-scale robot
datasets. Production manifests must declare namespaces so persistent IDs can be compared without
collisions:

```text
we://organization/dataset/episode/episode_000421
we://organization/dataset/world/world_001@sha256:...
we://organization/dataset/entity/world_001/mug_017
```

Bindings may keep compact local IDs inside a shard, but those IDs must resolve through the declared
namespace when crossing a dataset boundary.

## Sharding

Large corpora should be partitioned by fields that make common robot-learning queries cheap:

- `dataset_id`;
- `embodiment_id` or robot family;
- `task_id`;
- `collection_site`;
- `capture_session`;
- `world_lineage_id`;
- `world_revision_id`;
- `split`;
- time range;
- modality or payload kind.

Trace, event, provenance, asset-index, and split payloads may use different physical layouts. The
manifest is the common catalog that tells a reader which shard to load.

## Assets

Assets are not constrained to relative paths. Portability depends on:

```json
{
  "uri": "hf://organization/dataset/assets/world_001.spz",
  "media_type": "model/vnd.spz",
  "sha256": "a821000000000000000000000000000000000000000000000000000000000000",
  "mirrors": [
    "assets/world_001.spz"
  ]
}
```

Resolvers may use Hugging Face, object storage, OCI, IPFS, content-addressed registries, HTTP(S), or
local mirrors. Every resolved payload is verified by digest before it is trusted.

## Append-Only Versions

Production datasets need stable references. WorldEpisode dataset versions are append-only snapshots.
Replacing a broken shard creates a new snapshot. Removing an episode, world, or asset creates a
tombstone or supersession record; it does not mutate the old release in place.

This keeps published split manifests, replay reports, and paper results reproducible even when the
corpus continues to grow.

## What This Fixes

The reference directory layout is useful for small examples and conformance fixtures, but it is not
the architecture for a global robot dataset. The scalable architecture avoids:

- scanning millions of files to open a corpus;
- duplicating large world assets inside every episode package;
- comparing unscoped local IDs across labs;
- treating object storage layout as the semantic API;
- breaking published evaluations when a dataset is updated;
- hiding lineage leakage because split information lives outside the dataset contract.

The production claim is therefore not "put every robot dataset in one folder." The claim is a
manifest and index contract that lets many storage systems expose the same world-episode semantics.
