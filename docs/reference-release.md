# Reference Release Plan

Status: draft.

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

## Release Order

1. Publish the landscape and RFC first: comparison, terminology, problem statement, non-goals,
   draft schemas, use cases, and unresolved design questions.
2. Release the validator before the large dataset.
3. Implement adapters for LeRobot, OpenUSD, Rerun, NCore, GSDF/GSWorld-style assets, glTF Gaussian
   splats, and MCAP.
4. Secure at least one independent implementation before paper submission.
5. Move governance to a neutral public process.
6. Align with relevant standards bodies rather than presenting WorldEpisode as a replacement.
7. Measure adoption with independent implementations, external datasets, adapter usage,
   conformance-suite usage, benchmark submissions, and RFC participation.

## Initial Repository Milestones

- `v0.1-rfc`: paper draft, schemas, examples, requirements, and profile definitions.
- `v0.2-validator`: executable validator with passing and failing fixtures.
- `v0.3-bindings`: LeRobot, Rerun, OpenUSD, glTF Gaussian, and MCAP import/export sketches.
- `v0.4-corpus`: golden conformance corpus and replay fixtures.
- `v1.0-rigid-tabletop`: stable rigid tabletop manipulation profile and benchmark release.

