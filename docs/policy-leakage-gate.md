# ACT/Diffusion Policy Leakage Gate

Status: prepared, not executed.

The current leakage result uses an offline Torch MLP behavioral-cloning probe. That is useful as a
diagnostic, but it is not enough to claim that lineage-safe splits change results for modern
LeRobot policies. The next gate is therefore explicit:

```bash
python3 tools/lerobot_policy_leakage_gate.py
```

This command reads
[`docs/experiments/lerobot_scene_leakage/split_manifest.json`](experiments/lerobot_scene_leakage/split_manifest.json)
and writes:

- `docs/experiments/lerobot_policy_gate/policy_gate_report.json`;
- ACT and Diffusion training jobs in `train_eval_jobs.json`;
- train/test episode allowlists for the random and scene-disjoint splits;
- virtual split materialization manifests in `materialized_splits/`, with source file digests and
  split-membership hashes;
- a rollout contract requiring high-fidelity simulation or physical robot evaluation;
- `run_lerobot_policy_jobs.sh`, which contains the LeRobot `lerobot-train` commands.

The gate is deliberately strict. It remains open until all required result files exist:

- train metrics for ACT and Diffusion on both split policies;
- offline action-evaluation reports on the corresponding held-out episodes;
- high-fidelity simulator or physical rollout reports using the same split manifest;
- digest-verified videos or traces for rollout evidence.

The training command template follows LeRobot's current `lerobot-train --policy.type=...`
interface. The rollout contract follows LeRobot's current `lerobot-eval` and `lerobot-rollout`
evaluation path. The generated report records whether those CLIs are present in the current
environment.

This is not a completed empirical result. It is the executable gate that prevents the paper from
overclaiming the MLP leakage result as if it already covered ACT, Diffusion Policy, IsaacLab, or
hardware rollouts.

The materialization manifests are also bounded: they fix source integrity and episode membership
for the split datasets, but they are not committed physical copies of every LeRobot payload shard
and video.
