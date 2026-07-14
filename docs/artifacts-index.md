# Evidence and Artifact Index

Every public artifact backing the WorldEpisode paper and RFC, in one place. Paths are relative to
this `docs/` directory; run commands from the repository root.

## Paper and specification

- [Paper PDF (publication build)](../WorldEpisode.pdf)
- [Collaborator working PDF](../WorldEpisode-collab.pdf)
- [arXiv LaTeX paper](../paper/arxiv/main.tex)
- [Markdown paper notes](../paper/le-world-layout.md)
- [USS framing note](universal-spatial-state.md)
- [WorldEpisode v0.1 RFC spec](../spec/worldepisode-v0.1.md)
- [World layout profile v0.1 RFC](../spec/le-world-layout-v0.1.md)

## Schemas and conformance

- [WorldEpisode JSON Schema v0](../schemas/worldepisode-core-v0.schema.json)
- [WorldEpisode dataset manifest schema v0](../schemas/worldepisode-dataset-v0.schema.json)
- [Conformance JSON Schema v0](../schemas/conformance-requirements-v0.schema.json)
- [World layout JSON Schema v0](../schemas/le-world-layout-v0.schema.json)
- [Conformance requirements](../conformance/requirements.md)
- [Machine-readable requirements](../conformance/requirements.v0.json)
- [Conformance profiles](../conformance/profiles.md)
- [USS-Core-23 semantic projection](../conformance/projections/uss-core-23.v0.json)
- [Pilot conformance corpus](../conformance/fixtures/pilot/manifest.json)
- [Independent conformance fixtures](../conformance/fixtures/independent/manifest.json)

## Design documents

- [Bindings RFC](bindings.md)
- [Reference SDK contract](sdk.md)
- [Production-scale dataset architecture](production-scale.md)
- [ACT/Diffusion policy leakage gate](policy-leakage-gate.md)
- [Famous benchmark call-out audit](benchmark-callout-audit.md)
- [Real-to-sim contract drift](real-to-sim-contract-drift.md)
- [Meta-simulator contract](meta-simulator-contract.md)
- [Reviewer concern matrix](reviewer-concern-matrix.md)
- [Research plan](research-plan.md)
- [Reference release plan](reference-release.md)
- [Governance](../GOVERNANCE.md)

## Executed experiment artifacts

- [Controlled experiment results](experiments/RESULTS.md)
- [Binding round-trip artifacts](experiments/bindings)
- [Active LeRobot round-trip artifacts](experiments/lerobot_worldepisode_roundtrip)
- [Active LeRobot scene-leakage artifacts](experiments/lerobot_scene_leakage)
- [ACT/Diffusion leakage gate artifacts](experiments/lerobot_policy_gate)
- [Active LeRobot control-replay artifacts](experiments/lerobot_control_replay)
- [Famous benchmark call-out artifacts](experiments/benchmark_callout_audit)
- [Famous benchmark inflation-gate artifacts](experiments/benchmark_inflation_gate)
- [Real-to-sim contract-drift artifacts](experiments/realtosim_contract_drift)
- [Meta-simulator contract artifacts](experiments/meta_simulator_contract)
- [USS state-drift pilot artifacts](experiments/uss_state_drift_pilots)
- [Replay adapter conformance artifacts](experiments/replay_adapter_conformance)
- [Dataset-scale manifest audit artifacts](experiments/dataset_scale_audit)
- [Dataset-scale performance benchmark](experiments/dataset_scale_performance)
- [Clean-room reader artifacts](experiments/cleanroom_reader)
- [Pilot natural-source failure corpus](experiments/natural_failure_corpus/manifest.json)
- [Natural-source dataset diagnostics](experiments/natural_failure_corpus/dataset_diagnostics.json)
- [Single-line preflight artifacts](experiments/preflight/preflight_report.json)

## Release gates and packets

- [Open reproduction gate artifacts](experiments/open_reproduction_gates)
- [Paper claim audit artifacts](experiments/paper_claim_audit)
- [Release readiness gate](experiments/release_readiness)
- [Digest release manifest](release_manifest)
- [Reviewer submission packet](submission_packet)
- Generated artifact freshness gate: `python3 tools/artifact_freshness.py --strict`

## Examples

- [Minimal WorldEpisode example](../examples/minimal.worldepisode.json)
- [Minimal layout example](../examples/minimal-static-world.layout.json)
- [Scalable corpus manifest example](../examples/scalable-corpus.worldepisode-dataset.json)
