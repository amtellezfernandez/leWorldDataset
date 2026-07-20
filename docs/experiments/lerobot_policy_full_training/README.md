# LeRobot ACT/Diffusion Offline Policy Experiment

Status: preregistered; required training not yet executed

`POLICY.OFFLINE.001.armnet.v1` fixes 20 required jobs: ACT and
Diffusion Policy, the random-episode and task-confounded lineage-holdout packages,
and five matched seeds. Evaluation uses the exact 21 source episodes
shared by both test packages.

The primary metric is mean per-episode action nRMSE. Every checkpoint is evaluated
sequentially with teacher observations while preserving the policy's native action
queue and resetting it only at episode boundaries. There is no success threshold.

## Required Runtime

```bash
uv run --isolated --python 3.12 \
  --with 'lerobot[training,diffusion]==0.6.0' \
  --with pyarrow --with numpy --with huggingface-hub \
  python tools/lerobot_policy_video_materialization.py --materialize --download

uv run --isolated --python 3.12 \
  --with 'lerobot[training,diffusion]==0.6.0' \
  --with pyarrow --with numpy --with huggingface-hub \
  bash docs/experiments/lerobot_policy_full_training/run_jobs.sh
```

## Claim Boundary

This is sequential teacher-observation action prediction with each policy's native action queue. It is not a closed-loop rollout. The current lineage holdout removes two tasks from training because the available lineage key includes task identity; it is therefore a task-confounded holdout and cannot isolate scene leakage.
