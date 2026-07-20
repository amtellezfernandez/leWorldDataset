# Hugging Face Recovery

The private dataset repository
[`amtellezfernandez/worldepisode-experiment-recovery`](https://huggingface.co/datasets/amtellezfernandez/worldepisode-experiment-recovery)
stores immutable recovery snapshots that are too large, generated, or operationally noisy for Git.
This page and its machine-readable companion are generated from a forced-download verification
report; counts and digests are not maintained manually.

Snapshot `7822fc9` is pinned to Hugging Face commit
`926edb4979f3e50129158f16dbfceef3820f1eb0`. All 34 payload files
(24841901 bytes) passed size and SHA-256 verification, and the recovered
Git bundle cloned at the expected source commit and passed `git fsck --full`.

- `artifacts`: 3 verified payload files
- `contact_rich_replay`: 5 verified payload files
- `policy_reports`: 6 verified payload files
- `release_reports`: 5 verified payload files
- `run_logs`: 15 verified payload files

Restore the snapshot with an authenticated Hugging Face account:

```bash
hf download amtellezfernandez/worldepisode-experiment-recovery \
  --repo-type dataset \
  --revision 926edb4979f3e50129158f16dbfceef3820f1eb0 \
  --include "snapshots/7822fc9/**" \
  --local-dir worldepisode-recovery
```

Verify each restored file against `snapshots/7822fc9/artifact_manifest.json`. To recover the
repository independently of GitHub:

```bash
git clone \
  worldepisode-recovery/snapshots/7822fc9/artifacts/worldepisode-7822fc9.bundle \
  leWorldDataset
```

The source videos are not duplicated in the private recovery repository. The mirrored asset plan
pins 24 files (1864680767 source bytes) from
`armnet/armnetbench_v01_lerobot_so101@2e5e89aee0e7f081078d9d6ab3b279fc4b83ea84` with per-file LFS SHA-256 digests.

Earlier immutable snapshots:

- `ef7cc49` at Hugging Face commit `adf9157ee60356a6a9748320e0d186f6054a9a51`

Do not delete a local-only artifact until its Hugging Face commit is pinned here and a separate
download verifies every recorded SHA-256 digest.
