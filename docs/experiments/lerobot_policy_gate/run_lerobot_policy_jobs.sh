#!/usr/bin/env bash
set -euo pipefail

# Materialize each split dataset first; see policy_gate_report.json for allowlists.

# act on random_episode
lerobot-train --dataset.repo_id=worldepisode/armnetbench_v01_lerobot_so101_random_episode_train --policy.type=act --output_dir=outputs/policy_leakage/act_random_episode_worldepisode_leakage --job_name=act_random_episode_worldepisode_leakage --policy.device=cuda --steps=20000 --seed=17 --wandb.enable=false

# diffusion on random_episode
lerobot-train --dataset.repo_id=worldepisode/armnetbench_v01_lerobot_so101_random_episode_train --policy.type=diffusion --output_dir=outputs/policy_leakage/diffusion_random_episode_worldepisode_leakage --job_name=diffusion_random_episode_worldepisode_leakage --policy.device=cuda --steps=20000 --seed=17 --wandb.enable=false

# act on scene_disjoint
lerobot-train --dataset.repo_id=worldepisode/armnetbench_v01_lerobot_so101_scene_disjoint_train --policy.type=act --output_dir=outputs/policy_leakage/act_scene_disjoint_worldepisode_leakage --job_name=act_scene_disjoint_worldepisode_leakage --policy.device=cuda --steps=20000 --seed=17 --wandb.enable=false

# diffusion on scene_disjoint
lerobot-train --dataset.repo_id=worldepisode/armnetbench_v01_lerobot_so101_scene_disjoint_train --policy.type=diffusion --output_dir=outputs/policy_leakage/diffusion_scene_disjoint_worldepisode_leakage --job_name=diffusion_scene_disjoint_worldepisode_leakage --policy.device=cuda --steps=20000 --seed=17 --wandb.enable=false

