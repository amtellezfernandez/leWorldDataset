# Contact-Rich Cross-Simulator Replay

Status: `contact_rich_cross_simulator_replay_complete`.

The preregistered protocol executes a straight push and a parallel-jaw capture over
32 initial-state scenarios in both MuJoCo and Genesis. Both runtimes
receive the same primitive world parameters, initial states, sampled actor poses, and clock. MuJoCo
is the metric reference only; it is not physical ground truth.

## Aggregate results

- Object trajectory position RMSE:
  0.009007 m
  (95% scenario-bootstrap CI
  [0.007381,
  0.010646]).
- Contact precision / recall / F1:
  0.995 /
  0.964 /
  0.979.
- Final object position error:
  0.008791 m
  (95% CI
  [0.006891,
  0.010742]).
- Task-outcome agreement:
  1.000
  (95% CI
  [1.000,
  1.000]).

## Reproduce

```bash
UV_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu uv run --isolated --python 3.11 --index-strategy unsafe-best-match --with 'torch==2.8.0+cpu' --with 'numpy==2.4.6' --with 'mujoco==3.3.7' --with 'genesis-world==1.2.2' python tools/contact_rich_cross_sim_replay.py --required
```

The committed runtime reports retain every object pose, contact sample, grasp-state sample, and
scenario outcome. The report does not claim simulator-equivalent physics or hardware validity.
