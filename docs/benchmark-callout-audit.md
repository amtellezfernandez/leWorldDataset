# Famous Benchmark Call-Out Audit

Status: source-level audit, not a completed benchmark rerun.

The ArmnetBench LeRobot audit currently measures a task--scene proxy holdout, not scene-only
leakage: task identity is part of the proxy key and the holdout removes tasks. To obtain a
benchmark-level leakage result responsibly, the next step is to use physical scene/source lineage,
preserve task support across protocols, and apply the same WorldEpisode checks to a public
benchmark.

Run:

```bash
python3 tools/benchmark_callout_audit.py
```

The generated artifact is:

- `docs/experiments/benchmark_callout_audit/benchmark_callout_report.json`;
- `docs/experiments/benchmark_callout_audit/README.md`.

The inflation-proof gate is separate:

```bash
uv run --with pyarrow --with requests --with numpy \
  python tools/famous_benchmark_policy_rerun.py --benchmark droid_100 --required
python3 tools/benchmark_inflation_gate.py
python3 tools/benchmark_inflation_gate.py --required
```

The default command records the current evidence state in
`docs/experiments/benchmark_inflation_gate/gate_report.json`. The `--required` form returns
non-zero unless at least one famous benchmark has a valid WorldEpisode conversion, split/timing
audit, and policy rerun report. In the current repository this required gate correctly fails. There
is one executed DROID subset rerun over pinned public LeRobot shards, but it is not
inflation-proof: the lineage source is a task/camera-schema proxy, the policy protocol is a bounded
offline probe rather than a published leaderboard reproduction, and the corrected proxy split does
not reduce the score. There are still zero inflation-proof DROID, BridgeData V2,
Open X-Embodiment, LIBERO, or CALVIN rerun reports.

The current top-five source-level audit covers:

- Open X-Embodiment / RT-X;
- DROID;
- BridgeData V2;
- LIBERO;
- CALVIN.

The audit checks whether public metadata exposes:

- world or scene lineage IDs and lineage-disjoint split manifests;
- immutable, content-addressed world or environment revisions;
- persistent entity identity across observations, assets, simulator actors, and annotations;
- action units, reference frames, absolute/delta semantics, command time, effective time, and latency;
- frame and clock graphs sufficient for replay;
- runtime assumptions and conversion-loss reports for published policy scores.

The result is a target list, not an accusation. A benchmark is called out when public metadata does
not expose enough information to audit leakage or timing. A benchmark is only called inflated after
the corresponding policy protocol is rerun under lineage-disjoint splits or timestamp-aware replay
and the score changes. The proof gate enforces that distinction.
