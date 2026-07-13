# Replay Adapter Conformance

Status: dependency-free scheduler conformance, not a physics simulator.

This artifact checks whether a runtime adapter honors the WorldEpisode action contract before it is
trusted as a replay target. It complements the MuJoCo replay result but does not claim coverage from
a second physics simulator.

| Case | Naive RMSE | Contract-Aware RMSE | Contract-Aware Pass |
|---|---:|---:|---:|
| constant_frame_delay_scheduler | 0.571 | 0.000 | True |
| zero_order_hold_missing_command | 0.727 | 0.000 | True |
| asynchronous_queue_selection | 0.671 | 0.000 | True |

Boundary: this is a scheduler and timestamp conformance harness. A second tested physics simulator
is still required before claiming cross-simulator replay.
