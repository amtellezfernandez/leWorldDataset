# ACT/Diffusion Policy Leakage Gate

Status: prepared, not executed.

The current result uses an offline Torch MLP behavioral-cloning probe and a measured temporal ridge
state/action baseline over the committed compact LeRobot split packages. The legacy
`scene_disjoint` split is actually a task--scene proxy holdout because task identity is part of its
lineage key. The metric change is useful as a diagnostic, but it does not isolate scene leakage and
is not enough to claim that lineage-safe splits change modern ACT or Diffusion Policy results. The
next gate is therefore explicit:

```bash
python3 tools/lerobot_policy_leakage_gate.py
```

This command reads
[`docs/experiments/lerobot_scene_leakage/split_manifest.json`](experiments/lerobot_scene_leakage/split_manifest.json)
and writes:

- `docs/experiments/lerobot_policy_gate/policy_gate_report.json`;
- ACT and Diffusion training jobs in `train_eval_jobs.json`;
- train/test episode allowlists for the random and legacy task--scene proxy holdout splits;
- virtual split materialization manifests in `materialized_splits/`, with source file digests and
  split-membership hashes;
- compact low-dimensional LeRobot split packages in `physical_splits/`, with source-file digest
  verification and explicit source-to-local episode maps;
- a rollout contract requiring high-fidelity simulation or physical robot evaluation;
- `run_lerobot_policy_jobs.sh`, which contains the LeRobot `lerobot-train` commands.

The related measured temporal baseline is regenerated separately with:

```bash
uv run --with pyarrow --with numpy python tools/lerobot_temporal_policy_baseline.py --strict
```

The gate is deliberately strict. It remains open until all required result files exist:

- train metrics for ACT and Diffusion on both split policies;
- offline action-evaluation reports on the corresponding held-out episodes;
- high-fidelity simulator or physical rollout reports using the same split manifest;
- digest-verified videos or traces for rollout evidence.

The training command template follows LeRobot's current `lerobot-train --policy.type=...`
interface. The rollout contract follows LeRobot's current `lerobot-eval` and `lerobot-rollout`
evaluation path. The generated report records whether those CLIs are present in the current
environment.

This is not a completed ACT/Diffusion empirical result. It is the executable gate that prevents the
paper from overclaiming the MLP and temporal-ridge proxy-holdout results as if they isolated scene
leakage or already covered ACT, Diffusion Policy, IsaacLab, or hardware rollouts.

The committed physical split packages are also bounded: they are state/action packages for
low-dimensional policy reruns. They preserve action, state, timestamp, frame, task, reward, and
done values from the cached public Parquet source and remap `episode_index`/`index` into contiguous
local LeRobot packages. They do not include video payloads; vision-policy results require mirroring
the source videos and committing their digests before any such result can be claimed.
