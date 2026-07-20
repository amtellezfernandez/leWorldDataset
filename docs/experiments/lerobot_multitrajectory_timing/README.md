# Multi-Trajectory SO-101 Telemetry-Lag Audit

This generated report freezes an integer action/state lag using the calibration package, then
evaluates it on source-episode-disjoint trajectories.

- Calibration: 320 episodes across 8 tasks.
- Held out: 80 episodes across 8 tasks.
- Frozen lag: 3 frames (150.0 ms at the source frame rate).
- Held-out zero-delay pooled RMSE: 4.845232 source position units.
- Held-out frozen-delay pooled RMSE: 1.934062 source position units.
- Mean paired episode improvement: 3.087120
  (95% CI 2.890437 to 3.286380).
- Improved held-out episodes: 80/80.

| Task index | Episodes | Zero-delay mean RMSE | Frozen-delay mean RMSE | Mean improvement |
|---:|---:|---:|---:|---:|
| 0 | 10 | 3.982418 | 1.309257 | 2.673160 |
| 1 | 11 | 4.069669 | 1.634374 | 2.435295 |
| 2 | 6 | 4.133825 | 1.659558 | 2.474267 |
| 3 | 13 | 6.491092 | 2.279450 | 4.211642 |
| 4 | 8 | 6.157982 | 2.150383 | 4.007600 |
| 5 | 11 | 4.691141 | 1.517412 | 3.173730 |
| 6 | 11 | 5.463065 | 2.009053 | 3.454012 |
| 7 | 10 | 4.439012 | 2.550329 | 1.888683 |

## Boundary

The audit measures lag between same-named action targets and observed joint-state telemetry on one SO-101 dataset. The source has one frame timestamp and no command-enqueue, queue-consume, or motor-effective timestamps, so this is not measured motor latency or evidence across robot/controller configurations. Timestamp scheduling uses the same sampled frame timestamps rather than independent queue observations; its result is interpolation-sensitive under float32 timestamp quantization.

`ACTION.002` remains open because motor-effective timestamps, a second controller configuration,
and an independently distinguishable queue-aware scheduler comparison are not available.

## Reproduce

```bash
uv run --with pyarrow --with numpy python tools/lerobot_multitrajectory_timing_audit.py --required
```
