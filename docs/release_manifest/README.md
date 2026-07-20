# Release Manifest

Status: `pass`.

Exact digests are used for stable artifacts. Timing-jitter reports are hashed after normalizing only wall-clock benchmark timing values.

## Summary

- Entries: 126
- Public evidence artifacts: 98
- Release scripts: 28
- Normalized timing digests: 4
- Missing artifacts: 0
- Empty artifacts: 0
- Generate: `python3 tools/release_manifest.py --strict`
- Verify without rewriting: `python3 tools/release_manifest.py --verify --strict`

## Entries

| Path | Category | Digest Mode | SHA-256 Prefix |
|---|---|---|---|
| `WorldEpisode.pdf` | public_evidence | exact | `33580770468a2f7e` |
| `WorldEpisode-supplement.zip` | public_evidence | exact | `5f85d61a9d339047` |
| `README.md` | public_evidence | exact | `5b46014158912401` |
| `THIRD_PARTY_ASSETS.md` | public_evidence | exact | `7d27eec228630e01` |
| `TODO.md` | public_evidence | exact | `ce285b2cfc1e3eb9` |
| `third_party_licenses/README.md` | public_evidence | exact | `b6932775e0d8047c` |
| `third_party_licenses/pusht-MIT.txt` | public_evidence | exact | `304e99a48271e108` |
| `spec/worldepisode-v0.1.md` | public_evidence | exact | `245a953769413e3d` |
| `spec/le-world-layout-v0.1.md` | public_evidence | exact | `bfb612a8c1300c0b` |
| `paper/le-world-layout.md` | public_evidence | exact | `51549aaafa85c61e` |
| `paper/arxiv/main.tex` | public_evidence | exact | `ed2ec4671ae9c0bc` |
| `paper/arxiv/checklist.tex` | public_evidence | exact | `fe82276d24b6fbf8` |
| `paper/arxiv/generated/experiment_values.tex` | public_evidence | exact | `eccb88390b7fa9f8` |
| `paper/arxiv/neurips_2026.sty` | public_evidence | exact | `c3fc2894e83d2517` |
| `paper/arxiv/references.bib` | public_evidence | exact | `08905a7f169dce51` |
| `paper/arxiv/sections/introduction.tex` | public_evidence | exact | `0c72cc31579dcb2a` |
| `paper/arxiv/sections/requirements.tex` | public_evidence | exact | `8e18521d823cdf15` |
| `paper/arxiv/sections/architecture.tex` | public_evidence | exact | `316c2b41d460a67b` |
| `paper/arxiv/sections/evaluation.tex` | public_evidence | exact | `1c9af15e517a37ad` |
| `paper/arxiv/sections/discussion.tex` | public_evidence | exact | `2f46adbfe92f0e8b` |
| `paper/arxiv/sections/limitations.tex` | public_evidence | exact | `2f78090e38fc6cec` |
| `paper/arxiv/sections/conclusion.tex` | public_evidence | exact | `dbac558b857e6e9e` |
| `paper/arxiv/sections/appendix.tex` | public_evidence | exact | `56e66f428a33ff6a` |
| `schemas/worldepisode-core-v0.schema.json` | public_evidence | exact | `ee02649c28fb1c67` |
| `schemas/worldepisode-dataset-v0.schema.json` | public_evidence | exact | `488d517937e90a87` |
| `schemas/conformance-requirements-v0.schema.json` | public_evidence | exact | `effb7b3980139195` |
| `conformance/requirements.v0.json` | public_evidence | exact | `787a5bb7e07779a9` |
| `conformance/projections/uss-core-23.v0.json` | public_evidence | exact | `77d809797abe6b6c` |
| `docs/experiments/RESULTS.md` | public_evidence | normalized | `7cacdfa6ac710855` |
| `docs/experiments/results.json` | public_evidence | normalized | `a74aa8d45231d612` |
| `docs/experiments/dataset_scale_performance/README.md` | public_evidence | normalized | `f385e2b3b213b393` |
| `docs/experiments/dataset_scale_performance/performance_report.json` | public_evidence | normalized | `10446ac9a70e6be9` |
| `docs/experiments/paper_claim_audit/paper_claim_audit_report.json` | public_evidence | exact | `5599cd231d8284b0` |
| `docs/experiments/public_maturity/public_maturity_report.json` | public_evidence | exact | `ad2317ff410f7c52` |
| `docs/experiments/package_install_smoke/package_install_smoke_report.json` | public_evidence | exact | `d267f5bcf8e0f46f` |
| `docs/experiments/open_reproduction_gates/open_reproduction_gates.json` | public_evidence | exact | `8b00495fc1b1d359` |
| `docs/experiments/benchmark_inflation_gate/gate_report.json` | public_evidence | exact | `64b28aa7e9b6f8f1` |
| `docs/experiments/benchmark_reruns/droid_100/rerun_report.json` | public_evidence | exact | `a9627558862650f5` |
| `docs/experiments/benchmark_reruns/droid_100/conversion_report.json` | public_evidence | exact | `a89360586e63ff86` |
| `docs/experiments/benchmark_reruns/droid_100/lineage_manifest.json` | public_evidence | exact | `c8e54a23e714e23f` |
| `docs/experiments/benchmark_reruns/droid_100/split_manifest.json` | public_evidence | exact | `62c6d72a0a8bcb1f` |
| `docs/experiments/benchmark_reruns/droid_100/worldepisode.manifest.json` | public_evidence | exact | `fcf78b7baf2f2617` |
| `docs/experiments/lerobot_scene_leakage/leakage_report.json` | public_evidence | exact | `99ebb7a37610069b` |
| `docs/experiments/lerobot_scene_leakage/bc_episode_errors.json` | public_evidence | exact | `a703cfde36f97dce` |
| `docs/experiments/lerobot_scene_leakage/split_manifest.json` | public_evidence | exact | `51852d83a6d6204a` |
| `docs/experiments/lerobot_scene_leakage/world_lineage.json` | public_evidence | exact | `baaff4a7254744a0` |
| `docs/experiments/lerobot_temporal_policy_baseline/temporal_policy_report.json` | public_evidence | exact | `d2903766f39b08c4` |
| `docs/experiments/statistical_analysis/statistical_report.json` | public_evidence | exact | `dc2071f80ad184e4` |
| `docs/experiments/lerobot_conversion_scale/README.md` | public_evidence | exact | `77be0fe4026c6916` |
| `docs/experiments/lerobot_conversion_scale/scale_report.json` | public_evidence | exact | `6064340fa4173041` |
| `docs/experiments/lerobot_multitrajectory_timing/README.md` | public_evidence | exact | `f7fe5a2b2b699922` |
| `docs/experiments/lerobot_multitrajectory_timing/timing_report.json` | public_evidence | exact | `f3d5cd5d7b81bd02` |
| `docs/experiments/lerobot_policy_gate/README.md` | public_evidence | exact | `57e2387c2bad892c` |
| `docs/experiments/lerobot_policy_gate/policy_gate_report.json` | public_evidence | exact | `621a0527964d0c86` |
| `docs/experiments/lerobot_policy_gate/policy_compatibility_report.json` | public_evidence | exact | `a1eb99c74ebb7ff9` |
| `docs/experiments/lerobot_policy_gate/train_eval_jobs.json` | public_evidence | exact | `8e373f305170114d` |
| `docs/experiments/lerobot_policy_gate/rollout_contract.json` | public_evidence | exact | `0062384aba1e8529` |
| `docs/experiments/lerobot_policy_gate/physical_splits/manifest.json` | public_evidence | exact | `999bee80b6bc28e0` |
| `docs/experiments/lerobot_policy_gate/run_lerobot_policy_jobs.sh` | public_evidence | exact | `bdb7ab078ce2f66f` |
| `docs/experiments/experiment_manifest/README.md` | public_evidence | exact | `7ca4cdd86b47235e` |
| `docs/experiments/experiment_manifest/experiment_manifest.json` | public_evidence | exact | `fdd5de833175c39c` |
| `docs/experiments/citation_source_audit/README.md` | public_evidence | exact | `be8acacd24357053` |
| `docs/experiments/citation_source_audit/citation_source_audit.json` | public_evidence | exact | `6e8cdc8524c6a758` |
| `docs/experiments/third_party_asset_audit/README.md` | public_evidence | exact | `29f7a9fff385c616` |
| `docs/experiments/third_party_asset_audit/asset_audit.json` | public_evidence | exact | `5b7e046488ee1a00` |
| `docs/anonymous_supplement/README.md` | public_evidence | exact | `28ff6bd6d90c1e63` |
| `docs/anonymous_supplement/supplement_report.json` | public_evidence | exact | `53901b0e2388adda` |
| `docs/experiments/anonymity_audit/README.md` | public_evidence | exact | `f336656c4ad49e16` |
| `docs/experiments/anonymity_audit/anonymity_report.json` | public_evidence | exact | `8f2c3a7e055dbd8e` |
| `docs/experiments/run_logs/controlled_suite_dgx_spark.log` | public_evidence | exact | `053c10a9941f3f49` |
| `docs/experiments/run_logs/droid_100_dgx_spark.log` | public_evidence | exact | `74f44ca7752efaaa` |
| `docs/experiments/run_logs/lerobot_scene_leakage_dgx_spark.log` | public_evidence | exact | `a91ba3685d310484` |
| `docs/experiments/run_logs/lerobot_conversion_scale_dgx_spark.log` | public_evidence | exact | `2c77da4a84617c0f` |
| `docs/experiments/run_logs/lerobot_conversion_scale_dgx_spark_failed_01.log` | public_evidence | exact | `7bf27bfacf30a8af` |
| `docs/experiments/run_logs/lerobot_conversion_scale_dgx_spark_failed_02.log` | public_evidence | exact | `3f4333ff1a86fbf2` |
| `docs/experiments/run_logs/lerobot_multitrajectory_timing_dgx_spark.log` | public_evidence | exact | `1c2cbd5b1c236d59` |
| `docs/experiments/run_logs/lerobot_policy_compatibility_dgx_spark.log` | public_evidence | exact | `9fc33440d9c8e757` |
| `docs/experiments/run_logs/paper_build_local.log` | public_evidence | exact | `090d651b9757e65e` |
| `docs/experiments/run_logs/remote_tests_dgx_spark.log` | public_evidence | exact | `c3719b1a27266a88` |
| `docs/experiments/lerobot_worldepisode_roundtrip/conversion_report.json` | public_evidence | exact | `17cd849e6f923adb` |
| `docs/experiments/lerobot_worldepisode_roundtrip_pusht/batch_roundtrip_report.json` | public_evidence | exact | `41f5fe7bebf87093` |
| `docs/experiments/lerobot_control_replay/control_replay_report.json` | public_evidence | exact | `2f716ad0ae2cccc5` |
| `docs/experiments/meta_simulator_contract/adapter_contract_report.json` | public_evidence | exact | `797193a841df02b2` |
| `docs/experiments/realtosim_contract_drift/contract_drift_report.json` | public_evidence | exact | `f79a1a31658a0e3b` |
| `docs/experiments/cleanroom_reader/cleanroom_reader_report.json` | public_evidence | exact | `9ad13a25c61b1bca` |
| `docs/experiments/preflight/preflight_report.json` | public_evidence | exact | `4447b5c3faccca8a` |
| `docs/experiments/natural_failure_corpus/README.md` | public_evidence | exact | `5213a7fded971b3d` |
| `docs/experiments/natural_failure_corpus/dataset_diagnostics.json` | public_evidence | exact | `66c1ec842b0a5e3e` |
| `docs/experiments/natural_failure_corpus/datasets/armnet_armnetbench_v01_lerobot_so101_2e5e89aee0e7.json` | public_evidence | exact | `c396299867af4396` |
| `docs/experiments/natural_failure_corpus/datasets/benchmark_bridgedata_v2_source_level.json` | public_evidence | exact | `69f840314c3e8d26` |
| `docs/experiments/natural_failure_corpus/datasets/benchmark_droid_source_level.json` | public_evidence | exact | `d67761f69169d956` |
| `docs/experiments/natural_failure_corpus/datasets/lerobot_pusht_7628202a2180.json` | public_evidence | exact | `bd31ed1229ecf2b5` |
| `docs/experiments/natural_failure_corpus/datasets/lerobot_svla_so101_pickplace_f641879e2217.json` | public_evidence | exact | `2fd75a4b0962189e` |
| `docs/experiments/natural_failure_corpus/manifest.json` | public_evidence | exact | `2fce06f9e38a4a4f` |
| `docs/reviewer-concern-matrix.md` | public_evidence | exact | `2b393aa3eb37c0bc` |
| `docs/reference-release.md` | public_evidence | exact | `17e95cff3912f3c2` |
| `GOVERNANCE.md` | public_evidence | exact | `00db931e8bfa6960` |
| `CITATION.cff` | public_evidence | exact | `b416c4fbe9a2c3b8` |
| `.github/workflows/ci.yml` | release_script | exact | `09f46535f7f985db` |
| `Makefile` | release_script | exact | `cab3cc76248cdb93` |
| `tools/run_experiments.py` | release_script | exact | `bddb4a10c639b5e6` |
| `tools/open_reproduction_gates.py` | release_script | exact | `97d17499d76ad4bd` |
| `tools/paper_claim_audit.py` | release_script | exact | `e002795174217911` |
| `tools/experiment_statistics.py` | release_script | exact | `61aa84c935c69e60` |
| `tools/experiment_manifest.py` | release_script | exact | `3e309989564891ce` |
| `tools/citation_source_audit.py` | release_script | exact | `0477d6683c1a2e18` |
| `tools/dataset_license_registry.py` | release_script | exact | `1587e0f4bbf9cbca` |
| `tools/third_party_asset_audit.py` | release_script | exact | `af2807464d2e82b2` |
| `tools/paper_experiment_values.py` | release_script | exact | `7cd546489a04c701` |
| `tools/build_anonymous_supplement.py` | release_script | exact | `458dd3c52e8fdae2` |
| `tools/submission_anonymity_audit.py` | release_script | exact | `558fd94fa7f2ea02` |
| `tools/benchmark_callout_audit.py` | release_script | exact | `76173d115631956b` |
| `tools/famous_benchmark_policy_rerun.py` | release_script | exact | `378481f06aa4d9c3` |
| `tools/lerobot_conversion_scale.py` | release_script | exact | `ad005fb27a5fff8b` |
| `tools/lerobot_multitrajectory_timing_audit.py` | release_script | exact | `f9e094e5397d8886` |
| `tools/lerobot_policy_compatibility_audit.py` | release_script | exact | `619070884feb10e0` |
| `tools/lerobot_policy_leakage_gate.py` | release_script | exact | `a0e93e248b82b680` |
| `tools/lerobot_scene_leakage_experiment.py` | release_script | exact | `28af6fa76943d3cc` |
| `tools/lerobot_worldepisode_roundtrip.py` | release_script | exact | `db7546d06ab885d7` |
| `tools/lerobot_temporal_policy_baseline.py` | release_script | exact | `168345270a48d451` |
| `tools/public_maturity_audit.py` | release_script | exact | `2c6f3ed15c56efb6` |
| `tools/package_install_smoke.py` | release_script | exact | `3a71a0846173ff5f` |
| `tools/release_manifest.py` | release_script | exact | `f2d35eba3a6ab013` |
| `tools/submission_packet.py` | release_script | exact | `16990dd4972c0980` |
| `tools/release_readiness.py` | release_script | exact | `27b157ff60c9fbf8` |
| `tools/artifact_freshness.py` | release_script | exact | `872fb2ac81b56cfc` |

## Validation

- Passed: `True`
- Missing: `[]`
- Empty: `[]`
- Duplicate paths: `[]`
