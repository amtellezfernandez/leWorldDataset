# Experiment Provenance Manifest

Schema: `worldepisode_experiment_manifest_v1`.

Principal paper experiments and the shared controlled suite. Derived paper rendering is tracked separately by the release manifest.

| Experiment | Status | Pinned datasets | Wall time (s) | Max RSS (MiB) | Run log |
|---|---|---|---:|---:|---|
| `armnet_task_scene_proxy_mlp` | measured | armnet/armnetbench_v01_lerobot_so101@2e5e89aee0e7 | 46.69 | 1510.7 | `docs/experiments/run_logs/lerobot_scene_leakage_dgx_spark.log` |
| `armnet_task_scene_proxy_temporal_ridge` | measured | armnet/armnetbench_v01_lerobot_so101@2e5e89aee0e7 | 3.84 | 626.2 | `docs/experiments/run_logs/controlled_suite_dgx_spark.log` |
| `droid_100_proxy_ridge_rerun` | measured_no_inflation_evidence | lerobot/droid_100@87301a2d2e99 | 0.62 | 223.0 | `docs/experiments/run_logs/droid_100_dgx_spark.log` |
| `controlled_contract_suite` | measured | lerobot/svla_so101_pickplace@f641879e2217, lerobot/pusht@7628202a2180, armnet/armnetbench_v01_lerobot_so101@2e5e89aee0e7 | 3.84 | 626.2 | `docs/experiments/run_logs/controlled_suite_dgx_spark.log` |
| `lerobot_conversion_scale` | measured | lerobot/svla_so101_pickplace@f641879e2217, lerobot/pusht@7628202a2180, armnet/armnetbench_v01_lerobot_so101@2e5e89aee0e7 | 48.24 | 393.3 | `docs/experiments/run_logs/lerobot_conversion_scale_dgx_spark.log` |
| `lerobot_multitrajectory_timing` | measured_partial_action_002 | armnet/armnetbench_v01_lerobot_so101@2e5e89aee0e7 | 1.20 | 247.6 | `docs/experiments/run_logs/lerobot_multitrajectory_timing_dgx_spark.log` |
| `lerobot_act_diffusion_compatibility_preflight` | blocked_missing_required_observation_modality | armnet/armnetbench_v01_lerobot_so101@2e5e89aee0e7 | 10.61 | 894.4 | `docs/experiments/run_logs/lerobot_policy_compatibility_dgx_spark.log` |
| `lerobot_act_diffusion_front_camera_smoke` | training_step_smoke_passed | armnet/armnetbench_v01_lerobot_so101@2e5e89aee0e7 | 24.80 | 2464.6 | `docs/experiments/run_logs/lerobot_policy_vision_smoke_dgx_spark.log` |

## Validation

Passed: `True`.

- None
