# Real-to-Sim Contract Drift

Status: controlled proxy experiment, not a physical hardware rollout.

This artifact positions WorldEpisode as the contract layer for real-to-sim pipelines such as
Gaussian-splat/OpenUSD reconstruction systems. The question is not whether splats are visually
useful; the question is whether the reconstructed world, action interface, physical roles, and
deployment assumptions remain bound to the robot episode.

## Results

| Ablation | Sim Success With Drifted Contract | Deployment Success With Drifted Contract | Deployment Success With WorldEpisode Contract |
|---|---:|---:|---:|
| Action contract drift | True | False | True |
| Representation-role drift | True | False | True |

## Interpretation

The action ablation shows a simulated policy that succeeds when actions are interpreted as absolute
radian joint targets. The same vector fails immediately under the deployment controller because the
source hardware contract expects delta-degree commands. WorldEpisode prevents that drift by making
the policy-side and hardware-side action contracts explicit.

The representation ablation shows an appearance-only real-to-sim export that drops the collision
role. The straight-line policy succeeds in simulation because the collision proxy is absent, then
collides with the real foreground geometry. WorldEpisode prevents that drift by requiring the same
entity to carry explicit appearance, collision, and semantic roles.
