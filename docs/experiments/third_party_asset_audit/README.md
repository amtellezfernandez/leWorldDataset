# Third-Party Asset Audit

Status: `pass`.

Third-party datasets named by the experiment manifest, source-derived Parquet files distributed under docs/experiments, directly used external software, context-only benchmark datasets, and the vendored NeurIPS style file. This is a provenance and notice audit, not legal advice or legal clearance.

## Active Datasets

| Dataset | Pinned revision | License expression | Experiments |
|---|---|---|---|
| `armnet/armnetbench_v01_lerobot_so101` | `2e5e89aee0e7f081078d9d6ab3b279fc4b83ea84` | `Apache-2.0` | `armnet_task_scene_proxy_mlp`, `armnet_task_scene_proxy_temporal_ridge`, `controlled_contract_suite`, `lerobot_act_diffusion_compatibility_preflight`, `lerobot_act_diffusion_front_camera_smoke`, `lerobot_conversion_scale`, `lerobot_multitrajectory_timing` |
| `lerobot/droid_100` | `87301a2d2e99340e2010c9ef0f1d8e780b08aaf9` | `MIT AND CC-BY-4.0` | `droid_100_proxy_ridge_rerun` |
| `lerobot/pusht` | `7628202a2180972f291ba1bc6723834921e72c19` | `MIT` | `controlled_contract_suite`, `lerobot_conversion_scale` |
| `lerobot/svla_so101_pickplace` | `f641879e22172be7e8161d5e6c1503c2d2feb657` | `Apache-2.0` | `controlled_contract_suite`, `lerobot_conversion_scale` |

## Redistributed Rows

- Parquet files: 48
- Parquet bytes: 6736270
- First-party Parquet sentinels: 1
- Source-license files: 16
- Source media files: 0

Source-derived rows retain their upstream license expression. Each redistributed Parquet package
must contain an adjacent `SOURCE_LICENSE.json`. WorldEpisode-authored manifests, diagnostics, and
aggregate reports are CC0-1.0 unless a file says otherwise.

## External Software

| Software | License | Use |
|---|---|---|
| LeRobot | `Apache-2.0` | dataset conventions and public dataset mirrors; not vendored |
| MuJoCo | `Apache-2.0` | runtime replay experiment; installed dependency, not vendored |
| Genesis | `Apache-2.0` | runtime replay experiment; installed dependency, not vendored |
| PyArrow | `Apache-2.0` | Parquet experiment I/O; installed dependency, not vendored |
| scikit-learn | `BSD-3-Clause` | controlled baselines; installed dependency, not vendored |
| PyTorch | `BSD-3-Clause` | MLP experiment; installed dependency, not vendored |

These dependencies are installed from their upstream packages and are not vendored here.

## Context-Only Datasets

| Dataset | License | Use |
|---|---|---|
| BridgeData V2 | `CC-BY-4.0` | related-work and source-level audit only; no rows or media redistributed |
| Open X-Embodiment | `dataset-specific` | related-work and source-level audit only; no component dataset redistributed |
| LIBERO | `MIT (source code)` | source-level benchmark audit only; no code, rows, or media redistributed |
| CALVIN | `MIT (source code)` | source-level benchmark audit only; no code, rows, or media redistributed |

## Vendored Submission Asset

`paper/arxiv/neurips_2026.sty` is the official NeurIPS 2026 author-kit style with pinned SHA-256
`c3fc2894e83d2517ca18b66741d6c595986d97957dc08ec08bb2125a7ec4555a`. The distributed file contains no separate
SPDX or license statement, so the audit records `NOASSERTION` rather than inventing a license.

## Validation Errors

- None
