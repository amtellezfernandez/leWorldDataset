# Release Manifest

Status: `pass`.

Exact digests are used for stable artifacts. Timing-jitter reports are hashed after normalizing only wall-clock benchmark timing values.

## Summary

- Entries: 46
- Public evidence artifacts: 35
- Release scripts: 11
- Normalized timing digests: 4
- Missing artifacts: 0
- Empty artifacts: 0
- Generate: `python3 tools/release_manifest.py --strict`
- Verify without rewriting: `python3 tools/release_manifest.py --verify --strict`

## Entries

| Path | Category | Digest Mode | SHA-256 Prefix |
|---|---|---|---|
| `WorldEpisode.pdf` | public_evidence | exact | `40ef9015f3bc528d` |
| `README.md` | public_evidence | exact | `0bb8ad516328ee56` |
| `spec/worldepisode-v0.1.md` | public_evidence | exact | `dc6a0126ee7621ba` |
| `spec/le-world-layout-v0.1.md` | public_evidence | exact | `bfb612a8c1300c0b` |
| `paper/le-world-layout.md` | public_evidence | exact | `51549aaafa85c61e` |
| `paper/arxiv/main.tex` | public_evidence | exact | `9830590b8320692d` |
| `paper/arxiv/sections/evaluation.tex` | public_evidence | exact | `870cbf1790e94df4` |
| `paper/arxiv/sections/limitations.tex` | public_evidence | exact | `f5933251d27c6886` |
| `schemas/worldepisode-core-v0.schema.json` | public_evidence | exact | `ee02649c28fb1c67` |
| `schemas/worldepisode-dataset-v0.schema.json` | public_evidence | exact | `488d517937e90a87` |
| `schemas/conformance-requirements-v0.schema.json` | public_evidence | exact | `effb7b3980139195` |
| `conformance/requirements.v0.json` | public_evidence | exact | `787a5bb7e07779a9` |
| `conformance/projections/uss-core-23.v0.json` | public_evidence | exact | `77d809797abe6b6c` |
| `docs/experiments/RESULTS.md` | public_evidence | normalized | `0cba8a4fdf7f2aa3` |
| `docs/experiments/results.json` | public_evidence | normalized | `2afa23e0780ce6a9` |
| `docs/experiments/dataset_scale_performance/README.md` | public_evidence | normalized | `943173b82eec9763` |
| `docs/experiments/dataset_scale_performance/performance_report.json` | public_evidence | normalized | `48293944cf0e21b1` |
| `docs/experiments/paper_claim_audit/paper_claim_audit_report.json` | public_evidence | exact | `6a9b7bf4282bc321` |
| `docs/experiments/public_maturity/public_maturity_report.json` | public_evidence | exact | `6823f9f886f2f1b0` |
| `docs/experiments/package_install_smoke/package_install_smoke_report.json` | public_evidence | exact | `2e7e9f53c4b032be` |
| `docs/experiments/open_reproduction_gates/open_reproduction_gates.json` | public_evidence | exact | `9d1f70f6bf73da32` |
| `docs/experiments/benchmark_inflation_gate/gate_report.json` | public_evidence | exact | `1a7ff1c3d96cc5e7` |
| `docs/experiments/lerobot_scene_leakage/leakage_report.json` | public_evidence | exact | `5ffe5fd924814d59` |
| `docs/experiments/lerobot_worldepisode_roundtrip/conversion_report.json` | public_evidence | exact | `37449c7b32f10cb7` |
| `docs/experiments/lerobot_worldepisode_roundtrip_pusht/batch_roundtrip_report.json` | public_evidence | exact | `41f5fe7bebf87093` |
| `docs/experiments/lerobot_control_replay/control_replay_report.json` | public_evidence | exact | `2f716ad0ae2cccc5` |
| `docs/experiments/meta_simulator_contract/adapter_contract_report.json` | public_evidence | exact | `08834fc9ad47cddf` |
| `docs/experiments/realtosim_contract_drift/contract_drift_report.json` | public_evidence | exact | `f79a1a31658a0e3b` |
| `docs/experiments/cleanroom_reader/cleanroom_reader_report.json` | public_evidence | exact | `9ad13a25c61b1bca` |
| `docs/experiments/preflight/preflight_report.json` | public_evidence | exact | `4447b5c3faccca8a` |
| `docs/experiments/natural_failure_corpus/manifest.json` | public_evidence | exact | `af79dfde34d015d9` |
| `docs/reviewer-concern-matrix.md` | public_evidence | exact | `e2b0dbfb74863d5a` |
| `docs/reference-release.md` | public_evidence | exact | `a17c16840efc720f` |
| `GOVERNANCE.md` | public_evidence | exact | `c5f5e9618c26f9e4` |
| `CITATION.cff` | public_evidence | exact | `9a0c9bde871ab55a` |
| `.github/workflows/ci.yml` | release_script | exact | `cee51b9a483411b0` |
| `Makefile` | release_script | exact | `edf330296fba3aa1` |
| `tools/run_experiments.py` | release_script | exact | `d6e8dbd24c0e313c` |
| `tools/open_reproduction_gates.py` | release_script | exact | `963ac258c6da5b0e` |
| `tools/paper_claim_audit.py` | release_script | exact | `ae0814d108af0578` |
| `tools/public_maturity_audit.py` | release_script | exact | `c3f02c825a5fce01` |
| `tools/package_install_smoke.py` | release_script | exact | `3a71a0846173ff5f` |
| `tools/release_manifest.py` | release_script | exact | `7229855450006277` |
| `tools/submission_packet.py` | release_script | exact | `a2ab86582a3855b9` |
| `tools/release_readiness.py` | release_script | exact | `b2943ce0ea807e29` |
| `tools/artifact_freshness.py` | release_script | exact | `872fb2ac81b56cfc` |

## Validation

- Passed: `True`
- Missing: `[]`
- Empty: `[]`
- Duplicate paths: `[]`
