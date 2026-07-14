# Famous Benchmark Policy Rerun

Benchmark: `droid`.

Available: `True`.

This artifact is the benchmark-specific evidence record consumed by
`tools/benchmark_inflation_gate.py`. It is fail-closed: unavailable data, proxy lineage, or a
non-published policy protocol must not unlock a published-score inflation claim.

## Result

- Baseline score: `0.4958081537296595`
- Corrected score: `0.515540983544114`
- Score drop: `-0.019732829814454567`
- Lineage source: `task_camera_schema_proxy`
- Lineage sufficient for score-inflation claim: `False`

## Boundary

Small public DROID LeRobot mirror. This is a bounded offline state/action rerun, not a reproduction of a DROID leaderboard or a hardware rollout. The report is valid evidence for this subset and metric only. It is not a published-score inflation claim unless the strict proof gate accepts it.
