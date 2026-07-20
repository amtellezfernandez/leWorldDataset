# Natural Failure Corpus Dataset Diagnostics

Status: `dataset_specific_diagnostics_ready`.

These reports materialize the pilot natural-source corpus by dataset. They are intended for
reviewer audit and maintainer follow-up. They are not prevalence estimates, maintainer-confirmed
bug records, or benchmark score-inflation evidence.

| Dataset | Evidence Status | Cases | Report |
| --- | --- | ---: | --- |
| armnet/armnetbench_v01_lerobot_so101 | active_task_scene_proxy_split_audit | 1 | `docs/experiments/natural_failure_corpus/datasets/armnet_armnetbench_v01_lerobot_so101_2e5e89aee0e7.json` |
| benchmark/bridgedata_v2 | source_level_public_metadata_only | 5 | `docs/experiments/natural_failure_corpus/datasets/benchmark_bridgedata_v2_source_level.json` |
| benchmark/droid | source_level_public_metadata_only | 5 | `docs/experiments/natural_failure_corpus/datasets/benchmark_droid_source_level.json` |
| lerobot/pusht | active_worldepisode_conversion_reports | 4 | `docs/experiments/natural_failure_corpus/datasets/lerobot_pusht_7628202a2180.json` |
| lerobot/svla_so101_pickplace | active_worldepisode_conversion_reports | 4 | `docs/experiments/natural_failure_corpus/datasets/lerobot_svla_so101_pickplace_f641879e2217.json` |

Summary:

- Dataset reports: 5
- Cases covered: 19
- Active LeRobot reports: 2
- Source-level-only reports: 2
- Maintainer feedback satisfied: False

Remaining for stronger claims:

- Record maintainer agreement, disagreement, or no-response evidence.
- Convert source-level DROID and BridgeData V2 gaps into pinned WorldEpisode manifests.
- Run false-positive review before using the corpus as prevalence evidence.
