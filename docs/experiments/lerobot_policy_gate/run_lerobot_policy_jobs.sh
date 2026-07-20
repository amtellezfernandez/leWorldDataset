#!/usr/bin/env bash
set -euo pipefail

# Local compact split packages are under docs/experiments/lerobot_policy_gate/physical_splits.
# LeRobot 0.6.0 ACT and Diffusion also require an image or environment-state input.
# Do not run these jobs until a semantically valid required modality has been materialized.

# act on random_episode
lerobot-train --dataset.repo_id=worldepisode/armnetbench_v01_lerobot_so101_random_episode_train --dataset.root=docs/experiments/lerobot_policy_gate/physical_splits/random_episode_train --policy.type=act --output_dir=outputs/policy_leakage/act_random_episode_worldepisode_leakage --job_name=act_random_episode_worldepisode_leakage --policy.device=cuda --policy.push_to_hub=false --steps=20000 --seed=17 --wandb.enable=false

# diffusion on random_episode
lerobot-train --dataset.repo_id=worldepisode/armnetbench_v01_lerobot_so101_random_episode_train --dataset.root=docs/experiments/lerobot_policy_gate/physical_splits/random_episode_train --policy.type=diffusion --output_dir=outputs/policy_leakage/diffusion_random_episode_worldepisode_leakage --job_name=diffusion_random_episode_worldepisode_leakage --policy.device=cuda --policy.push_to_hub=false --steps=20000 --seed=17 --wandb.enable=false

# act on scene_disjoint
lerobot-train --dataset.repo_id=worldepisode/armnetbench_v01_lerobot_so101_scene_disjoint_train --dataset.root=docs/experiments/lerobot_policy_gate/physical_splits/scene_disjoint_train --policy.type=act --output_dir=outputs/policy_leakage/act_scene_disjoint_worldepisode_leakage --job_name=act_scene_disjoint_worldepisode_leakage --policy.device=cuda --policy.push_to_hub=false --steps=20000 --seed=17 --wandb.enable=false

# diffusion on scene_disjoint
lerobot-train --dataset.repo_id=worldepisode/armnetbench_v01_lerobot_so101_scene_disjoint_train --dataset.root=docs/experiments/lerobot_policy_gate/physical_splits/scene_disjoint_train --policy.type=diffusion --output_dir=outputs/policy_leakage/diffusion_scene_disjoint_worldepisode_leakage --job_name=diffusion_scene_disjoint_worldepisode_leakage --policy.device=cuda --policy.push_to_hub=false --steps=20000 --seed=17 --wandb.enable=false

