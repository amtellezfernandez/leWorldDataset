# Reference Release Plan

Status: evidence-gated RFC release plan.

The repository now has an executable release-readiness gate:

```bash
python3 tools/open_reproduction_gates.py --strict
python3 tools/paper_claim_audit.py --strict
python3 tools/release_readiness.py --strict-rfc
```

The current gate passes the RFC-release checks: package metadata, public docs, paper artifact,
schema/examples, controlled experiments, fail-closed benchmark claims, dataset-scale evidence, and
clean-room reader evidence. It deliberately does not mark the full standard complete. Stronger
claims remain blocked until ACT/Diffusion or rollout results, valid famous-benchmark reruns,
maintainer feedback, external adoption, and broader simulator replay evidence exist.
Each blocked stronger claim is mapped to a command-backed open reproduction gate in
`docs/experiments/open_reproduction_gates/open_reproduction_gates.json`.
The main numerical and boundary claims in the paper are separately checked against committed
evidence in `docs/experiments/paper_claim_audit/paper_claim_audit_report.json`.

The first release should beat larger real-to-sim datasets in completeness, interoperability, and
auditability rather than in raw scene count.

## Minimum Credible Benchmark

- at least three robot embodiments;
- at least 50 fully specified real-world scenes;
- at least 1,000 episodes;
- several episodes and tasks per world;
- explicit world revisions;
- static and manipulated entities;
- Gaussian appearance;
- render and collision meshes;
- camera calibration;
- action contracts;
- object trajectories;
- contact and attachment events;
- raw-to-derived provenance;
- at least two simulator exports;
- world-, entity-, and lineage-disjoint split manifests.

## Production-Scale Release Constraints

The public release should not imply that a dataset is a folder of per-episode packages. It should
ship:

- one dataset-scale manifest that validates against
  `schemas/worldepisode-dataset-v0.schema.json`;
- globally scoped IDs for episodes, worlds, entities, embodiments, tasks, assets, and split
  manifests;
- sharded trace, event, provenance, quality, asset-index, and split payloads with declared schema
  references;
- materialized indexes for episode lookup, world lineage, entity lookup, asset digest, split
  membership, time range, and embodiment/task queries;
- resolver definitions for Hugging Face, object storage, OCI artifacts, local mirrors, and any
  content-addressed registries used by the release;
- append-only version snapshots with tombstones or supersession records for corrections.

Small reference packages remain useful as conformance fixtures, but the benchmark release should be
opened through the manifest and indexes without scanning the backing storage.

## Release Order

1. Publish the landscape and RFC first: comparison, terminology, problem statement, non-goals,
   versioned schemas, use cases, and unresolved design questions.
2. Release the validator before the large dataset, including `pip install worldepisode`,
   `worldepisode preflight`, and one-line Python hooks for LeRobot and Rerun pipelines.
3. Implement adapters for LeRobot, OpenUSD, Rerun, NCore, GSDF/GSWorld-style assets, glTF Gaussian
   splats, and MCAP.
4. Secure at least one independent implementation before paper submission.
5. Move governance to a neutral public process.
6. Align with relevant standards bodies rather than presenting WorldEpisode as a replacement.
7. Measure adoption with independent implementations, external datasets, adapter usage,
   conformance-suite usage, benchmark submissions, and RFC participation.

The internal clean-room reader at `tools/cleanroom_conformance_reader.py` is a useful pre-release
sanity check because it consumes the public schema and fixtures without importing the reference SDK.
It does not replace step 4; an external reader/exporter or external compatible dataset is still
required before claiming independent implementation.

## Initial Repository Milestones

- `v0.1-rfc`: paper, schemas, examples, requirements, and profile definitions.
- `v0.2-validator`: executable validator with passing and failing fixtures plus blocking preflight
  CLI/API checks.
- `v0.3-bindings`: LeRobot, Rerun, OpenUSD, glTF Gaussian, and MCAP import/export sketches.
- `v0.4-corpus`: golden conformance corpus and replay fixtures.
- `v1.0-rigid-tabletop`: stable rigid tabletop manipulation profile and benchmark release.
