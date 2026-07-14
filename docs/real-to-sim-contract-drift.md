# Real-to-Sim Contract Drift

Status: controlled proxy experiment, not a physical robot rollout.

Real-to-sim systems such as RoboSnap/DROID-Sim make the right bet: reusable robot-learning
infrastructure will come from reconstructed, replayable worlds, often with layered Gaussian
appearance and physics-aware foreground assets. WorldEpisode should not compete with that pipeline.
It should be the contract that keeps the reconstructed world tied to the original robot episode.

Run:

```bash
python3 tools/realtosim_contract_drift.py
```

The generated artifact is:

- `docs/experiments/realtosim_contract_drift/contract_drift_report.json`;
- `docs/experiments/realtosim_contract_drift/README.md`.

The controlled ablation isolates two drift mechanisms:

- **Action contract drift:** a policy succeeds in a simulator where actions are interpreted as
  absolute joint-radian targets, then fails under a deployment controller that expects delta-degree
  commands.
- **Representation-role drift:** an appearance-only Gaussian export drops the collision role, so a
  straight-line policy succeeds in simulation and collides with the real foreground geometry.

In both cases, the drifted real-to-sim contract reports simulated success and deployment failure.
The WorldEpisode contract recovers deployment success by declaring the action adapter and the
appearance/collision/semantic roles explicitly.

This is deliberately a proxy. It does not claim a measured RoboSnap, DROID-Sim, or hardware result.
Its purpose is to make the methodological point reviewers need to see: visual reconstruction alone
does not make a real-to-sim pipeline scientifically safe.
