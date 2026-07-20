# Hugging Face Recovery

The private dataset repository
[`amtellezfernandez/worldepisode-experiment-recovery`](https://huggingface.co/datasets/amtellezfernandez/worldepisode-experiment-recovery)
stores immutable recovery snapshots that are too large, generated, or operationally noisy for Git.
The machine-readable snapshot pointer and verification result are in
[`huggingface-recovery.json`](huggingface-recovery.json).

Snapshot `a7dc01c` is pinned to Hugging Face commit
`442ee48368186e46b23fe8695ae5c73a454ccf8e`. It contains:

- the deterministic anonymous supplement;
- the publication PDF;
- all retained local and DGX Spark run logs; and
- a complete Git bundle containing every repository ref at the snapshot time.

Restore the snapshot with an authenticated Hugging Face account:

```bash
hf download amtellezfernandez/worldepisode-experiment-recovery \
  --repo-type dataset \
  --revision 442ee48368186e46b23fe8695ae5c73a454ccf8e \
  --include "snapshots/a7dc01c/**" \
  --local-dir worldepisode-recovery
```

Verify each restored file against
`snapshots/a7dc01c/artifact_manifest.json`. To recover the repository independently of GitHub:

```bash
git clone \
  worldepisode-recovery/snapshots/a7dc01c/artifacts/worldepisode-a7dc01c.bundle \
  leWorldDataset
```

Do not delete a local-only artifact until its Hugging Face commit is pinned here and a separate
download verifies every recorded SHA-256 digest.
