# Open Reproduction Gates

Status: `open_gates_indexed`.

These are the results that remain executable but unclaimed. The paper renders the same boundary as amber callouts in the evaluation and limitations sections.

## Gates

### `POLICY.ROLL.001`

Claim: state-of-the-art policy or physical rollout impact

Status: `open_not_claimed`.

Boundary: No ACT, Diffusion Policy, IsaacLab, or hardware success number is claimed until policy metrics and rollout evidence are committed.

Commands:

- regenerate split packages and LeRobot job specs

  ```bash
  python3 tools/lerobot_policy_leakage_gate.py
  ```

- run generated ACT/Diffusion jobs in a LeRobot environment

  ```bash
  bash docs/experiments/lerobot_policy_gate/run_lerobot_policy_jobs.sh
  ```

Required artifacts:

- policy checkpoints or immutable checkpoint digests
- train/eval configs and seeds
- offline action metrics for both splits
- rollout traces or videos with content digests
- updated docs/experiments/lerobot_policy_gate/policy_gate_report.json

Acceptance rule: At least one ACT or Diffusion Policy run must report both random_episode and scene_disjoint metrics, and at least one rollout report must use the same split manifest before the stronger policy-impact claim can be made.

### `BENCH.INFLATE.001`

Claim: famous benchmark published scores are inflated

Status: `open_not_claimed`.

Boundary: The paper may call famous benchmarks unaudited with respect to WorldEpisode's controls, but it must not call published scores inflated until a benchmark-specific rerun passes.

Commands:

- attempt a targeted DROID-100 subset rerun

  ```bash
  uv run --with pyarrow --with requests --with numpy python tools/famous_benchmark_policy_rerun.py --benchmark droid_100 --required
  ```

- enforce the score-inflation proof contract

  ```bash
  python3 tools/benchmark_inflation_gate.py --required
  ```

Required artifacts:

- benchmark-specific WorldEpisode conversion
- lineage/timing audit proving the corrected protocol removes the failure
- published or faithful published-protocol policy rerun
- paired corrected evaluation under the same metric
- measured baseline-minus-corrected score drop

Acceptance rule: The gate must contain at least one inflation-proof valid rerun report with measured_inflation=true. Source-level metadata gaps alone are not score-inflation evidence.

### `NATURAL.001`

Claim: natural failure prevalence is maintainer-confirmed

Status: `open_not_claimed`.

Boundary: The current natural-source corpus is a scoped evidence corpus, not a prevalence estimate and not maintainer-confirmed bug evidence.

Commands:

- regenerate controlled and natural-source experiment reports

  ```bash
  python3 tools/run_experiments.py
  ```

Required artifacts:

- dataset-specific diagnostic reports for representative diagnostics
- dataset-specific WorldEpisode manifests for source-level gaps
- false-positive review records
- maintainer agreement, disagreement, or no-response evidence
- updated natural failure corpus manifest

Acceptance rule: Dataset-specific diagnostic reports support representative diagnostics only. A prevalence or maintainer-confirmed claim still requires recorded maintainer feedback, false-positive review, and pinned conversions for source-level benchmark gaps.

### `ADOPT.001`

Claim: mature external standard adoption

Status: `open_not_claimed`.

Boundary: The repository contains an internal clean-room reader, but no external independent implementation or externally published compatible dataset is claimed.

Commands:

- regenerate the internal clean-room reader evidence

  ```bash
  python3 tools/cleanroom_conformance_reader.py
  ```

- check RFC readiness after external evidence is added

  ```bash
  python3 tools/release_readiness.py --strict-rfc
  ```

Required artifacts:

- external reader/exporter repository or archived release
- external dataset manifest or conversion report
- conformance-suite output from the external implementation
- license and citation metadata for the external artifact

Acceptance rule: Mature-standard language requires at least one independently written implementation or externally published compatible dataset that passes the public conformance suite.

## Validation

Passed: `True`.
