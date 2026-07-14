# USS State Drift Pilots

Status: deterministic non-robotics pilots.

Universal Spatial State (USS) is the umbrella state-integrity contract. WorldEpisode is the
robotics-heavy reference profile evaluated in depth elsewhere in this repository. These pilots test
whether the same invariant vocabulary also catches silent drift in adjacent spatial domains.

| Case | Domain | Local File Valid | USS Detected Drift | USS Corrected Behavior | Diagnostics |
|---|---|---:|---:|---:|---|
| game_engine_collision_patch_drift | virtual_agent_telemetry | True | True | True | ASSET.002, WORLD.001, REP.001 |
| autonomous_vehicle_clock_domain_drift | autonomous_driving_log | True | True | True | TIME.001, TIME.002, FRAME.001 |

## Boundary

These cases are deliberately small. They support the paper's vocabulary claim that state ancestry,
asset digests, representation roles, frame/clock mappings, and transition invariants generalize
beyond robot episodes. They do not support claims about production game engines, autonomous-driving
fleets, or public AV benchmark prevalence.
