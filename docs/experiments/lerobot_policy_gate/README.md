# LeRobot ACT/Diffusion Leakage Gate

Status: ready_for_policy_training

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

Physical package boundary: Physical split packages are committed compact low-dimensional LeRobot folders. Their state/action rows are ready for policies that support proprioception-only input. LeRobot 0.6.0 ACT and Diffusion require an image or environment-state input, so source videos or a semantically valid environment-state feature must be materialized before those jobs can run.

## Policy Compatibility

- Pinned LeRobot requirement version: 0.6.0
- Compatibility report: `docs/experiments/lerobot_policy_gate/policy_compatibility_report.json`
- Current package digests match the probe: True
- ACT/Diffusion completed a training step: False
- Probe status: blocked_missing_required_observation_modality

This probe validates the committed low-dimensional package loader and the pinned LeRobot ACT/Diffusion model-construction path. It is not a policy result. Both policies stop before training because joint proprioception alone does not satisfy their observation contract. Source videos were not mirrored, and joint positions must not be relabeled as environment state.

## Front-Camera Vision Smoke

- Vision smoke report: `docs/experiments/lerobot_policy_gate/policy_vision_smoke_report.json`
- Current input descriptors match the probe: True
- Image features: ['observation.images.front']
- ACT/Diffusion completed a training step: True
- Probe status: training_step_smoke_passed

This one-step probe validates source-image decoding and pinned ACT/Diffusion training-input compatibility. A completed optimization step is not a policy-quality or rollout result.

## Jobs

| Job | Policy | Split | Local train package |
|---|---|---|---|
| `act_random_episode_worldepisode_leakage` | `act` | `random_episode` | `docs/experiments/lerobot_policy_gate/physical_splits/random_episode_train` |
| `diffusion_random_episode_worldepisode_leakage` | `diffusion` | `random_episode` | `docs/experiments/lerobot_policy_gate/physical_splits/random_episode_train` |
| `act_scene_disjoint_worldepisode_leakage` | `act` | `scene_disjoint` | `docs/experiments/lerobot_policy_gate/physical_splits/scene_disjoint_train` |
| `diffusion_scene_disjoint_worldepisode_leakage` | `diffusion` | `scene_disjoint` | `docs/experiments/lerobot_policy_gate/physical_splits/scene_disjoint_train` |

## Run

1. Run `bash docs/experiments/lerobot_policy_gate/run_lerobot_policy_jobs.sh` in an environment with LeRobot installed; it
   materializes the pinned front camera before training.
2. Evaluate each checkpoint with the offline action-evaluation contract.
3. Run `lerobot-eval` in a high-fidelity environment or `lerobot-rollout` on hardware.
4. Save the required result files listed per job.

The gate remains open while `policy_gate_report.json` has `"pass": false`.
