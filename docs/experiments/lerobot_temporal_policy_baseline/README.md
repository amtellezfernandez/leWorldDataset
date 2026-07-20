# Temporal Policy Baseline

Status: `measured_offline_temporal_baseline`.

Measured offline temporal state/action baseline over committed compact LeRobot split packages. This is not ACT, Diffusion Policy, a vision-policy result, a simulator rollout, or a physical-robot rollout.

| Split | Train Frames | Test Frames | Episode nRMSE Mean | Thresholded Imitation Rate |
|---|---:|---:|---:|---:|
| random_episode | 98990 | 21745 | 0.157 | 0.925 |
| scene_disjoint | 100422 | 20313 | 0.255 | 0.420 |

Primary task--scene proxy holdout/random nRMSE ratio:
`1.62x`.

Secondary thresholded imitation-rate drop: `0.505`.
