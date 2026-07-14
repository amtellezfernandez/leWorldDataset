# Famous Benchmark Call-Out Audit

Status: source-level audit, not a completed leakage/replay experiment.

This artifact audits five famous public robot-learning benchmarks for the controls needed to make
world-lineage leakage, asset/entity leakage, action timing, and replay assumptions auditable. It
does not claim that a published score is inflated unless a measured experiment exists.

## Benchmarks

| Rank | Benchmark | Domain | High-Severity Open Controls | Call-Out Level |
|---:|---|---|---:|---|
| 1 | Open X-Embodiment / RT-X | real_robot_multi_embodiment | 5 | requires_worldepisode_audit_before_generalization_claim |
| 2 | DROID | real_robot_in_the_wild_manipulation | 5 | requires_worldepisode_audit_before_generalization_claim |
| 3 | BridgeData V2 | real_robot_low_cost_manipulation | 5 | requires_worldepisode_audit_before_generalization_claim |
| 4 | LIBERO | simulated_lifelong_robot_manipulation | 2 | requires_worldepisode_audit_before_generalization_claim |
| 5 | CALVIN | simulated_language_conditioned_long_horizon_manipulation | 3 | requires_worldepisode_audit_before_generalization_claim |

## Checks

| Check | Question | High | Medium |
|---|---|---:|---:|
| `WE-CALLOUT.001` | Does the public benchmark expose world/scene lineage IDs and lineage-disjoint splits? | 4 | 0 |
| `WE-CALLOUT.002` | Does each episode bind to an immutable, content-addressed world or environment revision? | 5 | 0 |
| `WE-CALLOUT.003` | Are persistent physical entity IDs carried across observations, assets, simulator actors, and annotations? | 3 | 2 |
| `WE-CALLOUT.004` | Are action units, reference frames, absolute/delta semantics, command time, effective time, and latency model explicit? | 5 | 0 |
| `WE-CALLOUT.005` | Are frames, transform directions, clock domains, and cross-clock mappings explicit enough for replay? | 0 | 5 |
| `WE-CALLOUT.006` | Are simulator/runtime assumptions and conversion-loss reports available for published policy scores? | 3 | 2 |

## Interpretation

The explosive ArmnetBench result remains the measured leakage case in this repository. This
five-benchmark audit is the next target list: each benchmark should be converted into a
WorldEpisode manifest, validated for the checks above, and rerun under lineage-disjoint splits or
timestamp-aware replay before making any stronger claim.

The stronger claim is enforced by `tools/benchmark_inflation_gate.py`. Until
`docs/experiments/benchmark_inflation_gate/gate_report.json` contains an inflation-proof valid
rerun report, the paper must treat these benchmarks as unaudited rather than inflated.

The first targeted rerun harness is `tools/famous_benchmark_policy_rerun.py --benchmark droid_100`.
It is allowed to fail closed when the pinned public shards cannot be fetched, when only proxy
lineage is available, or when the policy protocol is not a published-protocol reproduction.
