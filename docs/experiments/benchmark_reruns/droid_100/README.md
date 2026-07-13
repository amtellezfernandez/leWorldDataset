# Famous Benchmark Policy Rerun

Benchmark: `droid`.

Available: `False`.

This artifact is the benchmark-specific evidence record consumed by
`tools/benchmark_inflation_gate.py`. It is fail-closed: unavailable data, proxy lineage, or a
non-published policy protocol must not unlock a published-score inflation claim.

## Result

- Baseline score: `None`
- Corrected score: `None`
- Score drop: `None`
- Lineage source: `None`
- Lineage sufficient for score-inflation claim: `None`

## Boundary

No benchmark inflation claim is supported because the rerun did not execute.

Unavailable reason:

```text
pyarrow is required to read public LeRobot parquet shards. Reproduce with `uv run --with pyarrow --with requests --with numpy python tools/famous_benchmark_policy_rerun.py --required`.
```
