# Famous Benchmark Inflation Proof Gate

Status: measured_famous_benchmark_inflation_not_proven.

This is the hard evidence gate for claims that a famous benchmark score is inflated. The source
call-out audit is not enough. A claim needs a benchmark-specific WorldEpisode conversion, a
split/timing audit, and a policy rerun under the corrected protocol.

## Required Tests

| Test | Name | Required Evidence |
|---|---|---|
| `BENCH-INFLATE.001` | benchmark_specific_worldepisode_conversion | A WorldEpisode manifest/sidecar for the benchmark subset, plus conversion report with loss accounting and source data revision. |
| `BENCH-INFLATE.002` | lineage_or_timing_audit | A split or replay audit showing the original protocol leaks world/entity/source lineage or omits timing semantics, and the corrected protocol removes that failure. |
| `BENCH-INFLATE.003` | published_protocol_rerun | A rerun of a published policy protocol or faithful reproduction, with policy code, configuration, seeds, and evaluation command recorded. |
| `BENCH-INFLATE.004` | paired_corrected_evaluation | The same policy evaluated under the corrected lineage-disjoint split or timestamp-aware replay with the same metric and tolerance envelope. |
| `BENCH-INFLATE.005` | measured_score_delta | A positive baseline-minus-corrected score drop with enough seeds or paired episodes to support the claim being made. |

## Rerun Reports

| Benchmark | Valid | Score Drop | Measured Inflation | Report |
|---|---:|---:|---:|---|
| none | false | n/a | false | no rerun reports committed |

## Current Policy

The paper may call famous benchmarks unaudited with respect to WorldEpisode controls, but must not call their scores inflated until this gate has at least one measured inflation claim.

Measured inflation claims: 0.
