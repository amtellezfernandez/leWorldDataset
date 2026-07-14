# Release Manifest

Status: `pass`.

Exact digests are used for stable artifacts. Timing-jitter reports are hashed after normalizing only wall-clock benchmark timing values.

## Summary

- Entries: 61
- Public evidence artifacts: 48
- Release scripts: 13
- Normalized timing digests: 4
- Missing artifacts: 0
- Empty artifacts: 0
- Generate: `python3 tools/release_manifest.py --strict`
- Verify without rewriting: `python3 tools/release_manifest.py --verify --strict`

## Entries

| Path | Category | Digest Mode | SHA-256 Prefix |
|---|---|---|---|
| `WorldEpisode.pdf` | public_evidence | exact | `9a64ccfdfd6eb47a` |
| `README.md` | public_evidence | exact | `bd2395ad36d3b3ac` |
| `spec/worldepisode-v0.1.md` | public_evidence | exact | `245a953769413e3d` |
| `spec/le-world-layout-v0.1.md` | public_evidence | exact | `bfb612a8c1300c0b` |
| `paper/le-world-layout.md` | public_evidence | exact | `51549aaafa85c61e` |
| `paper/arxiv/main.tex` | public_evidence | exact | `4a6e4e4690738141` |
| `paper/arxiv/sections/evaluation.tex` | public_evidence | exact | `6fae876b5002653f` |
| `paper/arxiv/sections/limitations.tex` | public_evidence | exact | `7847f95f89d35315` |
| `schemas/worldepisode-core-v0.schema.json` | public_evidence | exact | `ee02649c28fb1c67` |
| `schemas/worldepisode-dataset-v0.schema.json` | public_evidence | exact | `488d517937e90a87` |
| `schemas/conformance-requirements-v0.schema.json` | public_evidence | exact | `effb7b3980139195` |
| `conformance/requirements.v0.json` | public_evidence | exact | `787a5bb7e07779a9` |
| `conformance/projections/uss-core-23.v0.json` | public_evidence | exact | `77d809797abe6b6c` |
| `docs/experiments/RESULTS.md` | public_evidence | normalized | `6379a9dc83cc26ef` |
| `docs/experiments/results.json` | public_evidence | normalized | `9ad887c897e0775c` |
| `docs/experiments/dataset_scale_performance/README.md` | public_evidence | normalized | `943173b82eec9763` |
| `docs/experiments/dataset_scale_performance/performance_report.json` | public_evidence | normalized | `48293944cf0e21b1` |
| `docs/experiments/paper_claim_audit/paper_claim_audit_report.json` | public_evidence | exact | `42bf840c048b1eb7` |
| `docs/experiments/public_maturity/public_maturity_report.json` | public_evidence | exact | `ad2317ff410f7c52` |
| `docs/experiments/package_install_smoke/package_install_smoke_report.json` | public_evidence | exact | `a9eaa2d54f1ed2ba` |
| `docs/experiments/open_reproduction_gates/open_reproduction_gates.json` | public_evidence | exact | `8b00495fc1b1d359` |
| `docs/experiments/benchmark_inflation_gate/gate_report.json` | public_evidence | exact | `db940893a05e95e9` |
| `docs/experiments/benchmark_reruns/droid_100/rerun_report.json` | public_evidence | exact | `e717fa79695d880a` |
| `docs/experiments/benchmark_reruns/droid_100/conversion_report.json` | public_evidence | exact | `a89360586e63ff86` |
| `docs/experiments/benchmark_reruns/droid_100/lineage_manifest.json` | public_evidence | exact | `c8e54a23e714e23f` |
| `docs/experiments/benchmark_reruns/droid_100/split_manifest.json` | public_evidence | exact | `62c6d72a0a8bcb1f` |
| `docs/experiments/benchmark_reruns/droid_100/worldepisode.manifest.json` | public_evidence | exact | `fcf78b7baf2f2617` |
| `docs/experiments/lerobot_scene_leakage/leakage_report.json` | public_evidence | exact | `5ffe5fd924814d59` |
| `docs/experiments/lerobot_temporal_policy_baseline/temporal_policy_report.json` | public_evidence | exact | `3c25b3d8c8dc5339` |
| `docs/experiments/lerobot_worldepisode_roundtrip/conversion_report.json` | public_evidence | exact | `37449c7b32f10cb7` |
| `docs/experiments/lerobot_worldepisode_roundtrip_pusht/batch_roundtrip_report.json` | public_evidence | exact | `41f5fe7bebf87093` |
| `docs/experiments/lerobot_control_replay/control_replay_report.json` | public_evidence | exact | `2f716ad0ae2cccc5` |
| `docs/experiments/meta_simulator_contract/adapter_contract_report.json` | public_evidence | exact | `08834fc9ad47cddf` |
| `docs/experiments/realtosim_contract_drift/contract_drift_report.json` | public_evidence | exact | `f79a1a31658a0e3b` |
| `docs/experiments/cleanroom_reader/cleanroom_reader_report.json` | public_evidence | exact | `9ad13a25c61b1bca` |
| `docs/experiments/preflight/preflight_report.json` | public_evidence | exact | `4447b5c3faccca8a` |
| `docs/experiments/natural_failure_corpus/README.md` | public_evidence | exact | `529a4c34f10d6d83` |
| `docs/experiments/natural_failure_corpus/dataset_diagnostics.json` | public_evidence | exact | `8dc6a160f6de3685` |
| `docs/experiments/natural_failure_corpus/datasets/armnet_armnetbench_v01_lerobot_so101_2e5e89aee0e7.json` | public_evidence | exact | `c770c6c95384e90f` |
| `docs/experiments/natural_failure_corpus/datasets/benchmark_bridgedata_v2_source_level.json` | public_evidence | exact | `69f840314c3e8d26` |
| `docs/experiments/natural_failure_corpus/datasets/benchmark_droid_source_level.json` | public_evidence | exact | `d67761f69169d956` |
| `docs/experiments/natural_failure_corpus/datasets/lerobot_pusht_7628202a2180.json` | public_evidence | exact | `bd31ed1229ecf2b5` |
| `docs/experiments/natural_failure_corpus/datasets/lerobot_svla_so101_pickplace_f641879e2217.json` | public_evidence | exact | `2fd75a4b0962189e` |
| `docs/experiments/natural_failure_corpus/manifest.json` | public_evidence | exact | `af79dfde34d015d9` |
| `docs/reviewer-concern-matrix.md` | public_evidence | exact | `9e19f02a5a7bd69d` |
| `docs/reference-release.md` | public_evidence | exact | `855a4016ea702867` |
| `GOVERNANCE.md` | public_evidence | exact | `00db931e8bfa6960` |
| `CITATION.cff` | public_evidence | exact | `27c7bb3e93aac9fa` |
| `.github/workflows/ci.yml` | release_script | exact | `cee51b9a483411b0` |
| `Makefile` | release_script | exact | `0bad5fa567a4b614` |
| `tools/run_experiments.py` | release_script | exact | `e39779d00f167054` |
| `tools/open_reproduction_gates.py` | release_script | exact | `569e40c4830f8b0e` |
| `tools/paper_claim_audit.py` | release_script | exact | `d2dc1c4cb33a33db` |
| `tools/famous_benchmark_policy_rerun.py` | release_script | exact | `378481f06aa4d9c3` |
| `tools/lerobot_temporal_policy_baseline.py` | release_script | exact | `36377d5b43a5a52e` |
| `tools/public_maturity_audit.py` | release_script | exact | `2c6f3ed15c56efb6` |
| `tools/package_install_smoke.py` | release_script | exact | `3a71a0846173ff5f` |
| `tools/release_manifest.py` | release_script | exact | `528354712b57a662` |
| `tools/submission_packet.py` | release_script | exact | `42a5af99e2927ee9` |
| `tools/release_readiness.py` | release_script | exact | `b0bfde182fbd6eab` |
| `tools/artifact_freshness.py` | release_script | exact | `872fb2ac81b56cfc` |

## Validation

- Passed: `True`
- Missing: `[]`
- Empty: `[]`
- Duplicate paths: `[]`
