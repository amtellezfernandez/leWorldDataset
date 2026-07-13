# Release Manifest

Status: `pass`.

Exact digests are used for stable artifacts. Timing-jitter reports are hashed after normalizing only wall-clock benchmark timing values.

## Summary

- Entries: 48
- Public evidence artifacts: 36
- Release scripts: 12
- Normalized timing digests: 4
- Missing artifacts: 0
- Empty artifacts: 0
- Generate: `python3 tools/release_manifest.py --strict`
- Verify without rewriting: `python3 tools/release_manifest.py --verify --strict`

## Entries

| Path | Category | Digest Mode | SHA-256 Prefix |
|---|---|---|---|
| `WorldEpisode.pdf` | public_evidence | exact | `e88b143bb68ad516` |
| `README.md` | public_evidence | exact | `ea4bf4d6d13c5bdf` |
| `spec/worldepisode-v0.1.md` | public_evidence | exact | `dc6a0126ee7621ba` |
| `spec/le-world-layout-v0.1.md` | public_evidence | exact | `bfb612a8c1300c0b` |
| `paper/le-world-layout.md` | public_evidence | exact | `51549aaafa85c61e` |
| `paper/arxiv/main.tex` | public_evidence | exact | `9830590b8320692d` |
| `paper/arxiv/sections/evaluation.tex` | public_evidence | exact | `a4266109d19ae8f9` |
| `paper/arxiv/sections/limitations.tex` | public_evidence | exact | `b06bc9090f83a2ae` |
| `schemas/worldepisode-core-v0.schema.json` | public_evidence | exact | `ee02649c28fb1c67` |
| `schemas/worldepisode-dataset-v0.schema.json` | public_evidence | exact | `488d517937e90a87` |
| `schemas/conformance-requirements-v0.schema.json` | public_evidence | exact | `effb7b3980139195` |
| `conformance/requirements.v0.json` | public_evidence | exact | `787a5bb7e07779a9` |
| `conformance/projections/uss-core-23.v0.json` | public_evidence | exact | `77d809797abe6b6c` |
| `docs/experiments/RESULTS.md` | public_evidence | normalized | `04c8038484121198` |
| `docs/experiments/results.json` | public_evidence | normalized | `0dfb7f0295734b7d` |
| `docs/experiments/dataset_scale_performance/README.md` | public_evidence | normalized | `943173b82eec9763` |
| `docs/experiments/dataset_scale_performance/performance_report.json` | public_evidence | normalized | `48293944cf0e21b1` |
| `docs/experiments/paper_claim_audit/paper_claim_audit_report.json` | public_evidence | exact | `ec389920745ae7ba` |
| `docs/experiments/public_maturity/public_maturity_report.json` | public_evidence | exact | `f866d92f5e2be9a4` |
| `docs/experiments/package_install_smoke/package_install_smoke_report.json` | public_evidence | exact | `996b3dc808a3f2bd` |
| `docs/experiments/open_reproduction_gates/open_reproduction_gates.json` | public_evidence | exact | `9d1f70f6bf73da32` |
| `docs/experiments/benchmark_inflation_gate/gate_report.json` | public_evidence | exact | `1a7ff1c3d96cc5e7` |
| `docs/experiments/lerobot_scene_leakage/leakage_report.json` | public_evidence | exact | `5ffe5fd924814d59` |
| `docs/experiments/lerobot_temporal_policy_baseline/temporal_policy_report.json` | public_evidence | exact | `3c25b3d8c8dc5339` |
| `docs/experiments/lerobot_worldepisode_roundtrip/conversion_report.json` | public_evidence | exact | `37449c7b32f10cb7` |
| `docs/experiments/lerobot_worldepisode_roundtrip_pusht/batch_roundtrip_report.json` | public_evidence | exact | `41f5fe7bebf87093` |
| `docs/experiments/lerobot_control_replay/control_replay_report.json` | public_evidence | exact | `2f716ad0ae2cccc5` |
| `docs/experiments/meta_simulator_contract/adapter_contract_report.json` | public_evidence | exact | `08834fc9ad47cddf` |
| `docs/experiments/realtosim_contract_drift/contract_drift_report.json` | public_evidence | exact | `f79a1a31658a0e3b` |
| `docs/experiments/cleanroom_reader/cleanroom_reader_report.json` | public_evidence | exact | `9ad13a25c61b1bca` |
| `docs/experiments/preflight/preflight_report.json` | public_evidence | exact | `4447b5c3faccca8a` |
| `docs/experiments/natural_failure_corpus/manifest.json` | public_evidence | exact | `af79dfde34d015d9` |
| `docs/reviewer-concern-matrix.md` | public_evidence | exact | `329489c9373ab983` |
| `docs/reference-release.md` | public_evidence | exact | `a17c16840efc720f` |
| `GOVERNANCE.md` | public_evidence | exact | `c5f5e9618c26f9e4` |
| `CITATION.cff` | public_evidence | exact | `9a0c9bde871ab55a` |
| `.github/workflows/ci.yml` | release_script | exact | `cee51b9a483411b0` |
| `Makefile` | release_script | exact | `edf330296fba3aa1` |
| `tools/run_experiments.py` | release_script | exact | `721b9799c328d37c` |
| `tools/open_reproduction_gates.py` | release_script | exact | `963ac258c6da5b0e` |
| `tools/paper_claim_audit.py` | release_script | exact | `cab8dc85069777b4` |
| `tools/lerobot_temporal_policy_baseline.py` | release_script | exact | `36377d5b43a5a52e` |
| `tools/public_maturity_audit.py` | release_script | exact | `5340db40d9d88271` |
| `tools/package_install_smoke.py` | release_script | exact | `3a71a0846173ff5f` |
| `tools/release_manifest.py` | release_script | exact | `7a5bcd971f8a510a` |
| `tools/submission_packet.py` | release_script | exact | `42a5af99e2927ee9` |
| `tools/release_readiness.py` | release_script | exact | `62c38876ddf81bca` |
| `tools/artifact_freshness.py` | release_script | exact | `872fb2ac81b56cfc` |

## Validation

- Passed: `True`
- Missing: `[]`
- Empty: `[]`
- Duplicate paths: `[]`
