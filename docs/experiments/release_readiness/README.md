# Release Readiness

Status: rfc_release_ready.

RFC release ready: `True`.

Full standard ready: `False`.

A ready RFC release means the repository is executable and evidence-gated. It does not mean ACT/Diffusion, famous benchmark inflation, external adoption, or full contact-rich simulator-neutral rollout claims are complete.

Open reproduction gate index: `docs/experiments/open_reproduction_gates/open_reproduction_gates.json`.

Paper claim audit: `docs/experiments/paper_claim_audit/paper_claim_audit_report.json`.

This gate adapts the evidence workflow pattern from `~/sota/wayspan`: compact tracked artifacts,
strict claim gates, and explicit blockers for claims that are not yet proven.

## Checks

| Check | Name | Pass | Severity | Evidence |
|---|---|---:|---|---|
| DOC.001 | top-level README exists | True | error | README.md (20056 bytes) |
| DOC.002 | license exists | True | error | LICENSE (254 bytes) |
| DOC.003 | governance exists | True | error | GOVERNANCE.md (1245 bytes) |
| DOC.004 | WorldEpisode RFC spec exists | True | error | spec/worldepisode-v0.1.md (10281 bytes) |
| DOC.005 | world layout RFC spec exists | True | error | spec/le-world-layout-v0.1.md (5602 bytes) |
| DOC.006 | paper PDF exists | True | error | WorldEpisode.pdf (479077 bytes) |
| DOC.007 | paper source exists | True | error | paper/arxiv/main.tex (5365 bytes) |
| DOC.008 | reviewer concern matrix exists | True | error | docs/reviewer-concern-matrix.md (17852 bytes) |
| DOC.009 | controlled results exist | True | error | docs/experiments/results.json (180605 bytes) |
| DOC.010 | public citation metadata exists | True | error | CITATION.cff (432 bytes) |
| DOC.011 | CI workflow exists | True | error | .github/workflows/ci.yml (1402 bytes) |
| CI.001 | CI workflow runs evidence gates | True | error | missing=[] |
| PKG.001 | pyproject exists | True | error | pyproject.toml (1177 bytes) |
| PKG.002 | package metadata parses | True | error | name='worldepisode', version='0.1.0' |
| PKG.003 | console script is exposed | True | error | worldepisode='worldepisode.cli:main' |
| PKG.004 | license and authors are declared | True | error | license and authors present in pyproject.toml |
| PKG.005 | wheel install smoke passes | True | error | docs/experiments/package_install_smoke/package_install_smoke_report.json wheel=worldepisode-0.1.0-py3-none-any.whl |
| EVID.001 | baseline manifest validates | True | error | schema_errors=0 and semantic_errors=0 |
| EVID.002 | active LeRobot round trips are exact | True | error | two pinned public LeRobot batch reports with zero source-native errors |
| EVID.003 | scene leakage result is measured | True | error | random=1.0, disjoint=0.0, drop=0.85 |
| EVID.004 | ACT/Diffusion gate is explicit and not overclaimed | True | warning | policy jobs and compact split packages exist; metrics are not claimed |
| EVID.011 | temporal policy baseline is measured | True | error | random=0.925, scene=0.42, drop=0.5050000000000001 |
| EVID.005 | famous benchmark inflation gate is fail-closed | True | error | reruns=1, valid=0, claims=0 |
| EVID.006 | dataset-scale manifest and generated catalog checks pass | True | error | dataset manifest audit plus generated billion-episode-capacity catalog benchmark |
| EVID.007 | clean-room reader consumes public schema/fixtures | True | error | status=pass, recall=1.0 |
| EVID.008 | replay timing evidence is executable | True | error | LeRobot control replay through MuJoCo and Genesis plus adapter scheduler conformance |
| EVID.009 | real-to-sim and meta-simulator boundaries are explicit | True | error | controlled proxy and runtime-neutral contract, not hardware/Isaac claim |
| EVID.010 | natural failure corpus has scoped evidence | True | warning | five-dataset count met; maintainer feedback still open |
| GATE.001 | open reproduction gate index validates | True | error | docs/experiments/open_reproduction_gates/open_reproduction_gates.json gates=4 |
| GATE.002 | blocked claims have reproduction commands | True | error | uncovered=[], commandless=[] |
| CLAIM.001 | paper claims are evidence-backed | True | error | docs/experiments/paper_claim_audit/paper_claim_audit_report.json claims=12, failed=0 |
| PUBLIC.001 | public surface avoids draft-only framing | True | error | docs/experiments/public_maturity/public_maturity_report.json violations=0 |
| MANIFEST.001 | release manifest validates | True | error | status=pass, entries=48, normalized=4 |
| SUBMIT.001 | submission packet validates | True | error | status=pass, claims=12, open_gates=4 |

## Blocked Stronger Claims

| Blocker | Claim | Blocked | Required Evidence |
|---|---|---:|---|
| `POLICY.ROLL.001` | state-of-the-art policy or physical rollout impact | True | ACT or Diffusion Policy metrics plus high-fidelity simulator or hardware rollout reports. |
| `BENCH.INFLATE.001` | famous benchmark published scores are inflated | True | valid benchmark-specific conversion, lineage/timing audit, published-protocol rerun, corrected evaluation, and score delta. |
| `NATURAL.001` | natural failure prevalence is maintainer-confirmed | True | maintainer agreement/disagreement records or dataset-specific conversion reports. |
| `SIM.001` | runtime-neutral replay equivalence across contact-rich simulator rollouts | False | same WorldEpisode LeRobot replay trace through at least one additional tested simulator adapter. |
| `ADOPT.001` | mature external standard adoption | True | external independent implementation or external compatible dataset release. |
