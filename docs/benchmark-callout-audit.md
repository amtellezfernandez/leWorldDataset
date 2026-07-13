# Famous Benchmark Call-Out Audit

Status: source-level audit, not a completed benchmark rerun.

The paper has one measured leakage result today: the ArmnetBench LeRobot audit where a random split
leaks all tested scene lineages and the offline BC probe drops from 0.850 to 0.000 when the split is
scene-disjoint. To scale that finding responsibly, the next step is to apply the same
WorldEpisode checks to famous public benchmarks.

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
is one attempted DROID subset rerun artifact, but it is invalid because Hugging Face DNS resolution
failed before the pinned Parquet shards could be fetched. There are still zero valid DROID,
BridgeData V2, Open X-Embodiment, LIBERO, or CALVIN rerun reports.

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
