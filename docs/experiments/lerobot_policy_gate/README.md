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

Boundary: Virtual manifests make split materialization deterministic for LeRobot-native policy jobs. They do not replace committed train/eval metrics or physical rollout reports.

## Jobs

| Job | Policy | Split | Materialized train dataset |
|---|---|---|---|
| `act_random_episode_worldepisode_leakage` | `act` | `random_episode` | `worldepisode/armnetbench_v01_lerobot_so101_random_episode_train` |
| `diffusion_random_episode_worldepisode_leakage` | `diffusion` | `random_episode` | `worldepisode/armnetbench_v01_lerobot_so101_random_episode_train` |
| `act_scene_disjoint_worldepisode_leakage` | `act` | `scene_disjoint` | `worldepisode/armnetbench_v01_lerobot_so101_scene_disjoint_train` |
| `diffusion_scene_disjoint_worldepisode_leakage` | `diffusion` | `scene_disjoint` | `worldepisode/armnetbench_v01_lerobot_so101_scene_disjoint_train` |

## Run

1. Materialize the train/test datasets listed in `train_eval_jobs.json` from the episode allowlists.
2. Run `bash docs/experiments/lerobot_policy_gate/run_lerobot_policy_jobs.sh` in an environment with LeRobot installed.
3. Evaluate each checkpoint with the offline action-evaluation contract.
4. Run `lerobot-eval` in a high-fidelity environment or `lerobot-rollout` on hardware.
5. Save the required result files listed per job.

The gate remains open while `policy_gate_report.json` has `"pass": false`.
