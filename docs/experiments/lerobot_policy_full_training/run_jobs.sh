#!/usr/bin/env bash
set -euo pipefail

# Run inside the protocol's pinned uv environment after camera materialization.
python tools/lerobot_policy_full_training.py --check-inputs

python tools/lerobot_policy_full_training.py --run-job act__random_episode__seed00
python tools/lerobot_policy_full_training.py --evaluate-job act__random_episode__seed00

python tools/lerobot_policy_full_training.py --run-job act__random_episode__seed01
python tools/lerobot_policy_full_training.py --evaluate-job act__random_episode__seed01

python tools/lerobot_policy_full_training.py --run-job act__random_episode__seed02
python tools/lerobot_policy_full_training.py --evaluate-job act__random_episode__seed02

python tools/lerobot_policy_full_training.py --run-job act__random_episode__seed03
python tools/lerobot_policy_full_training.py --evaluate-job act__random_episode__seed03

python tools/lerobot_policy_full_training.py --run-job act__random_episode__seed04
python tools/lerobot_policy_full_training.py --evaluate-job act__random_episode__seed04

python tools/lerobot_policy_full_training.py --run-job act__task_confounded_lineage_holdout__seed00
python tools/lerobot_policy_full_training.py --evaluate-job act__task_confounded_lineage_holdout__seed00

python tools/lerobot_policy_full_training.py --run-job act__task_confounded_lineage_holdout__seed01
python tools/lerobot_policy_full_training.py --evaluate-job act__task_confounded_lineage_holdout__seed01

python tools/lerobot_policy_full_training.py --run-job act__task_confounded_lineage_holdout__seed02
python tools/lerobot_policy_full_training.py --evaluate-job act__task_confounded_lineage_holdout__seed02

python tools/lerobot_policy_full_training.py --run-job act__task_confounded_lineage_holdout__seed03
python tools/lerobot_policy_full_training.py --evaluate-job act__task_confounded_lineage_holdout__seed03

python tools/lerobot_policy_full_training.py --run-job act__task_confounded_lineage_holdout__seed04
python tools/lerobot_policy_full_training.py --evaluate-job act__task_confounded_lineage_holdout__seed04

python tools/lerobot_policy_full_training.py --run-job diffusion__random_episode__seed00
python tools/lerobot_policy_full_training.py --evaluate-job diffusion__random_episode__seed00

python tools/lerobot_policy_full_training.py --run-job diffusion__random_episode__seed01
python tools/lerobot_policy_full_training.py --evaluate-job diffusion__random_episode__seed01

python tools/lerobot_policy_full_training.py --run-job diffusion__random_episode__seed02
python tools/lerobot_policy_full_training.py --evaluate-job diffusion__random_episode__seed02

python tools/lerobot_policy_full_training.py --run-job diffusion__random_episode__seed03
python tools/lerobot_policy_full_training.py --evaluate-job diffusion__random_episode__seed03

python tools/lerobot_policy_full_training.py --run-job diffusion__random_episode__seed04
python tools/lerobot_policy_full_training.py --evaluate-job diffusion__random_episode__seed04

python tools/lerobot_policy_full_training.py --run-job diffusion__task_confounded_lineage_holdout__seed00
python tools/lerobot_policy_full_training.py --evaluate-job diffusion__task_confounded_lineage_holdout__seed00

python tools/lerobot_policy_full_training.py --run-job diffusion__task_confounded_lineage_holdout__seed01
python tools/lerobot_policy_full_training.py --evaluate-job diffusion__task_confounded_lineage_holdout__seed01

python tools/lerobot_policy_full_training.py --run-job diffusion__task_confounded_lineage_holdout__seed02
python tools/lerobot_policy_full_training.py --evaluate-job diffusion__task_confounded_lineage_holdout__seed02

python tools/lerobot_policy_full_training.py --run-job diffusion__task_confounded_lineage_holdout__seed03
python tools/lerobot_policy_full_training.py --evaluate-job diffusion__task_confounded_lineage_holdout__seed03

python tools/lerobot_policy_full_training.py --run-job diffusion__task_confounded_lineage_holdout__seed04
python tools/lerobot_policy_full_training.py --evaluate-job diffusion__task_confounded_lineage_holdout__seed04

python tools/lerobot_policy_full_training.py --aggregate
python tools/lerobot_policy_full_training.py --check --required
