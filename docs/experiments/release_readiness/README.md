# Release Readiness

Status: rfc_release_ready.

RFC release ready: `True`.

Full standard ready: `False`.

A ready RFC release means the repository is executable and evidence-gated. It does not mean ACT/Diffusion, famous benchmark inflation, external adoption, or full simulator-neutral replay claims are complete.

Open reproduction gate index: `docs/experiments/open_reproduction_gates/open_reproduction_gates.json`.

This gate adapts the evidence workflow pattern from `~/sota/wayspan`: compact tracked artifacts,
strict claim gates, and explicit blockers for claims that are not yet proven.

## Checks

| Check | Name | Pass | Severity | Evidence |
|---|---|---:|---|---|
| DOC.001 | top-level README exists | True | error | README.md (17756 bytes) |
| DOC.002 | license exists | True | error | LICENSE (254 bytes) |
| DOC.003 | governance exists | True | error | GOVERNANCE.md (1236 bytes) |
| DOC.004 | paper PDF exists | True | error | WorldEpisode.pdf (469670 bytes) |
| DOC.005 | paper source exists | True | error | paper/arxiv/main.tex (5282 bytes) |
| DOC.006 | reviewer concern matrix exists | True | error | docs/reviewer-concern-matrix.md (17534 bytes) |
| DOC.007 | controlled results exist | True | error | docs/experiments/results.json (147867 bytes) |
| DOC.008 | public citation metadata exists | True | error | CITATION.cff (432 bytes) |
| DOC.009 | CI workflow exists | True | error | .github/workflows/ci.yml (677 bytes) |
| PKG.001 | pyproject exists | True | error | pyproject.toml (1244 bytes) |
| PKG.002 | package metadata parses | True | error | name='worldepisode', version='0.1.0' |
| PKG.003 | console script is exposed | True | error | worldepisode='worldepisode.cli:main' |
| PKG.004 | license and authors are declared | True | error | license and authors present in pyproject.toml |
| EVID.001 | baseline manifest validates | True | error | schema_errors=0 and semantic_errors=0 |
| EVID.002 | active LeRobot round trips are exact | True | error | two pinned public LeRobot batch reports with zero source-native errors |
| EVID.003 | scene leakage result is measured | True | error | random=1.0, disjoint=0.0, drop=0.85 |
| EVID.004 | ACT/Diffusion gate is explicit and not overclaimed | True | warning | policy jobs and compact split packages exist; metrics are not claimed |
| EVID.005 | famous benchmark inflation gate is fail-closed | True | error | reruns=1, valid=0, claims=0 |
| EVID.006 | dataset-scale manifest and generated catalog checks pass | True | error | dataset manifest audit plus generated billion-episode-capacity catalog benchmark |
| EVID.007 | clean-room reader consumes public schema/fixtures | True | error | status=pass, recall=1.0 |
| EVID.008 | replay timing evidence is executable | True | error | LeRobot control replay plus adapter scheduler conformance |
| EVID.009 | real-to-sim and meta-simulator boundaries are explicit | True | error | controlled proxy and runtime-neutral contract, not hardware/Isaac claim |
| EVID.010 | natural failure corpus has scoped evidence | True | warning | five-dataset count met; maintainer feedback still open |
| GATE.001 | open reproduction gate index validates | True | error | docs/experiments/open_reproduction_gates/open_reproduction_gates.json gates=5 |
| GATE.002 | blocked claims have reproduction commands | True | error | uncovered=[], commandless=[] |

## Blocked Stronger Claims

| Blocker | Claim | Blocked | Required Evidence |
|---|---|---:|---|
| `POLICY.ROLL.001` | state-of-the-art policy or physical rollout impact | True | ACT or Diffusion Policy metrics plus high-fidelity simulator or hardware rollout reports. |
| `BENCH.INFLATE.001` | famous benchmark published scores are inflated | True | valid benchmark-specific conversion, lineage/timing audit, published-protocol rerun, corrected evaluation, and score delta. |
| `NATURAL.001` | natural failure prevalence is maintainer-confirmed | True | maintainer agreement/disagreement records or dataset-specific conversion reports. |
| `SIM.001` | runtime-neutral replay equivalence across simulators | True | same WorldEpisode LeRobot replay trace through at least one additional tested simulator adapter. |
| `ADOPT.001` | mature external standard adoption | True | external independent implementation or external compatible dataset release. |
