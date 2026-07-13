# Dataset-Scale Manifest Audit

Status: pass

This artifact checks the production-scale manifest structure. It proves only catalog invariants,
not distributed performance.

- Manifest: `examples/scalable-corpus.worldepisode-dataset.json`
- Namespaces: 5
- Resolvers: 3
- Registries: 3
- Shards: 3
- Indexes: 2
- Versions: 1
- Asset descriptors: 9
- Assets with local mirrors: 9
- Local mirror entries: 9
- Asset URI schemes: hf, oci, s3
- World-lineage index: True
- Asset-digest index: True
- Split manifest shard: True

| Check | Severity | Message |
|---|---|---|
| none | none | no diagnostics |

Boundary: This audit validates catalog invariants for scalable manifests. It is not a billion-episode latency, cache, or federation benchmark.
