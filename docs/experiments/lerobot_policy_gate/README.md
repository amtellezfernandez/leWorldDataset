# LeRobot ACT/Diffusion Leakage Gate

Status: ready_not_executed

This directory is the executable gate for the reviewer concern that the leakage result must be
tested with stronger LeRobot-native policies. It is intentionally not marked closed until ACT or
Diffusion checkpoints, offline action-evaluation reports, and rollout reports are present.

Source split manifest: `docs/experiments/lerobot_scene_leakage/split_manifest.json`

## Split Materialization

- Manifest: `docs/experiments/lerobot_policy_gate/materialized_splits/manifest.json`
- Virtual split datasets: 4
- Source files with digest descriptors: 27
- Train/test overlaps are zero: True
- Episode counts match split manifest: True
- Physical split package manifest: `docs/experiments/lerobot_policy_gate/physical_splits/manifest.json`
- Physical split packages: 4
- Physical source files verified: True
- Physical output frames: 241470

Boundary: Virtual manifests make split materialization deterministic for LeRobot-native policy jobs. They do not replace committed train/eval metrics or physical rollout reports.

Physical package boundary: Physical split packages are committed compact low-dimensional LeRobot folders. They are ready for state/action ACT or Diffusion reruns and still require external video mirroring before any vision-policy result can be claimed.

## Jobs

| Job | Policy | Split | Local train package |
|---|---|---|---|
| `act_random_episode_worldepisode_leakage` | `act` | `random_episode` | `docs/experiments/lerobot_policy_gate/physical_splits/random_episode_train` |
| `diffusion_random_episode_worldepisode_leakage` | `diffusion` | `random_episode` | `docs/experiments/lerobot_policy_gate/physical_splits/random_episode_train` |
| `act_scene_disjoint_worldepisode_leakage` | `act` | `scene_disjoint` | `docs/experiments/lerobot_policy_gate/physical_splits/scene_disjoint_train` |
| `diffusion_scene_disjoint_worldepisode_leakage` | `diffusion` | `scene_disjoint` | `docs/experiments/lerobot_policy_gate/physical_splits/scene_disjoint_train` |

## Run

1. Use the local train/test packages listed in `train_eval_jobs.json`, or upload those folders as the matching LeRobot repo IDs.
2. Run `bash docs/experiments/lerobot_policy_gate/run_lerobot_policy_jobs.sh` in an environment with LeRobot installed.
3. Evaluate each checkpoint with the offline action-evaluation contract.
4. Run `lerobot-eval` in a high-fidelity environment or `lerobot-rollout` on hardware.
5. Save the required result files listed per job. Mirror source videos first if the policy consumes images.

The gate remains open while `policy_gate_report.json` has `"pass": false`.
