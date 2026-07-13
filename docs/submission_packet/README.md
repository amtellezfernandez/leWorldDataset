# Submission Packet

Status: `pass`.

Only claims listed as passed in the paper claim audit are treated as measured. Open reproduction gates are executable reviewer tasks, not paper results.

## Summary

- Paper claims checked: 11
- Failed checked claims: 0
- Open results not claimed: 4
- Missing required public artifacts: 0
- Release gate: `python3 tools/release_readiness.py --strict-rfc`

## Required Public Artifacts

| Artifact | Exists | Nonempty |
|---|---:|---:|
| `WorldEpisode.pdf` | True | True |
| `README.md` | True | True |
| `spec/worldepisode-v0.1.md` | True | True |
| `spec/le-world-layout-v0.1.md` | True | True |
| `paper/le-world-layout.md` | True | True |
| `paper/arxiv/main.tex` | True | True |
| `schemas/worldepisode-core-v0.schema.json` | True | True |
| `schemas/worldepisode-dataset-v0.schema.json` | True | True |
| `conformance/requirements.v0.json` | True | True |
| `conformance/projections/uss-core-23.v0.json` | True | True |
| `docs/experiments/results.json` | True | True |
| `docs/experiments/paper_claim_audit/paper_claim_audit_report.json` | True | True |
| `docs/experiments/package_install_smoke/package_install_smoke_report.json` | True | True |
| `docs/experiments/open_reproduction_gates/open_reproduction_gates.json` | True | True |
| `docs/release_manifest/release_manifest.json` | True | True |
| `docs/release_manifest/README.md` | True | True |
| `docs/experiments/release_readiness/release_readiness_report.json` | True | True |
| `docs/reviewer-concern-matrix.md` | True | True |
| `GOVERNANCE.md` | True | True |
| `CITATION.cff` | True | True |

## Measured Claims

| Claim | Pass | Text | Boundary |
|---|---:|---|---|
| `CLAIM.LEAKAGE.001` | True | ArmnetBench random split leaks lineages and offline BC drops under scene-disjoint split. | Offline action-imitation result; not ACT/Diffusion or physical rollout success. |
| `CLAIM.REPLAY.001` | True | Timestamp-aware LeRobot replay reduces joint RMSE in tested MuJoCo and Genesis adapters. | One LeRobot trace with minimal MuJoCo and Genesis position-servo adapters; Isaac is not claimed tested and contact-rich rollout remains open. |
| `CLAIM.ROUNDTRIP.001` | True | Two public LeRobotDataset batches round-trip exactly through WorldEpisode. | Two five-episode batch audits; not full LeRobot coverage. |
| `CLAIM.BINDING.001` | True | Seven pilot bindings preserve 17--39% natively outside the reference binding, with sidecars recovering dataset/log/world projections. | Pilot projection score, not a universal storage-format ranking. |
| `CLAIM.VALIDATOR.001` | True | Validator detects all injected fault classes and independent fixture failures. | Injected and hand-authored fixtures; natural prevalence remains open. |
| `CLAIM.NATURAL.001` | True | Pilot natural-source corpus records 19 cases across five public robot-learning datasets. | Scoped natural-source corpus, not maintainer-confirmed prevalence. |
| `CLAIM.USS.001` | True | Two deterministic non-robotics USS pilots demonstrate collision-patch and clock-domain drift. | Deterministic pilots, not production game or AV dataset results. |
| `CLAIM.REALTOSIM.001` | True | Controlled real-to-sim contract drift ablations fail under drifted contracts and recover with WorldEpisode. | Controlled proxy; not a hardware or RoboSnap/DROID-Sim rerun. |
| `CLAIM.SCALE.001` | True | Generated catalog benchmark describes a billion-episode-capacity sharded corpus. | Catalog-side evidence only; does not materialize a billion rows or payload bytes. |
| `CLAIM.BENCHMARK_BOUNDARY.001` | True | Famous benchmark audit is fail-closed and makes zero inflation claims in this release. | Source-level call-out audit; no published-score inflation claim. |
| `CLAIM.OPEN_GATES.001` | True | Open results are visibly and machine-readably marked as not claimed. | Open gates are unclaimed results, not paper results. |

## Open Results Not Claimed

| Gate | Claim | Status | Acceptance Rule |
|---|---|---|---|
| `POLICY.ROLL.001` | state-of-the-art policy or physical rollout impact | open_not_claimed | At least one ACT or Diffusion Policy run must report both random_episode and scene_disjoint metrics, and at least one rollout report must use the same split manifest before the stronger policy-impact claim can be made. |
| `BENCH.INFLATE.001` | famous benchmark published scores are inflated | open_not_claimed | The gate must contain at least one valid rerun report with measured_inflation=true. Source-level metadata gaps alone are not score-inflation evidence. |
| `NATURAL.001` | natural failure prevalence is maintainer-confirmed | open_not_claimed | A prevalence or maintainer-confirmed claim requires recorded maintainer feedback or dataset-specific conversion reports for representative diagnostics. |
| `ADOPT.001` | mature external standard adoption | open_not_claimed | Mature-standard language requires at least one independently written implementation or externally published compatible dataset that passes the public conformance suite. |

## Reproduction Commands

| Step | Command |
|---|---|
| validate schemas, examples, and Python tools | `make validate` |
| regenerate controlled experiment evidence | `python3 tools/run_experiments.py` |
| validate open unclaimed-result gates | `python3 tools/open_reproduction_gates.py --strict` |
| audit paper claims against evidence | `python3 tools/paper_claim_audit.py --strict` |
| generate this submission packet | `python3 tools/submission_packet.py --strict` |
| audit public maturity language | `python3 tools/public_maturity_audit.py --strict` |
| smoke-test wheel install | `python3 tools/package_install_smoke.py --strict` |
| build digest release manifest | `python3 tools/release_manifest.py --strict` |
| verify committed release manifest | `python3 tools/release_manifest.py --verify --strict` |
| check RFC release readiness | `python3 tools/release_readiness.py --strict-rfc` |
| reject stale generated artifacts | `python3 tools/artifact_freshness.py --strict` |

## Validation

- Passed: `True`
- Missing artifacts: `[]`
- Failed claims: `[]`
- Invalid open gates: `[]`
