# Hugging Face Recovery

The private dataset repository
[`amtellezfernandez/worldepisode-experiment-recovery`](https://huggingface.co/datasets/amtellezfernandez/worldepisode-experiment-recovery)
stores immutable recovery snapshots that are too large, generated, or operationally noisy for Git.
The machine-readable snapshot pointer and verification result are in
[`huggingface-recovery.json`](huggingface-recovery.json).

Snapshot `ef7cc49` is pinned to Hugging Face commit
`adf9157ee60356a6a9748320e0d186f6054a9a51`. Its 24 digest-verified payload files
contain:

- the deterministic anonymous supplement;
- the publication PDF;
- all retained local and DGX Spark run logs;
- the front-camera asset plan, materialization report, compatibility evidence, and policy gate; and
- a complete Git bundle containing every repository ref at the snapshot time.

Restore the snapshot with an authenticated Hugging Face account:

```bash
hf download amtellezfernandez/worldepisode-experiment-recovery \
  --repo-type dataset \
  --revision adf9157ee60356a6a9748320e0d186f6054a9a51 \
  --include "snapshots/ef7cc49/**" \
  --local-dir worldepisode-recovery
```

Verify each restored file against
`snapshots/ef7cc49/artifact_manifest.json`. To recover the repository independently of GitHub:

```bash
git clone \
  worldepisode-recovery/snapshots/ef7cc49/artifacts/worldepisode-ef7cc49.bundle \
  leWorldDataset
```

The source videos are not duplicated in the private recovery repository. The committed
`front_camera_asset_manifest.json` pins all source paths to the public
`armnet/armnetbench_v01_lerobot_so101` revision and records each LFS SHA-256 digest, so the
materializer can restore and verify the media independently.

The earlier snapshot `a7dc01c` remains available at Hugging Face commit
`442ee48368186e46b23fe8695ae5c73a454ccf8e`.

Do not delete a local-only artifact until its Hugging Face commit is pinned here and a separate
download verifies every recorded SHA-256 digest.
