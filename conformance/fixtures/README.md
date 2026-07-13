# Golden Conformance Fixtures

This directory will hold deterministic fixtures for validator and converter tests.

The first public corpus should include:

- 10 valid `WE-Core` packages;
- 10 valid advanced packages covering Gaussian appearance, rigid manipulation, replay, and
  counterfactual profiles;
- 30 intentionally invalid packages, one or two per requirement family;
- 10 lossy-conversion examples with expected conversion reports;
- 5 cross-simulator replay fixtures with expected tolerance envelopes and divergence summaries.

Each fixture should include:

- `package/` or binding-specific source data;
- `expected.json` with claimed profiles, expected diagnostics, and expected severity;
- `README.md` explaining the scenario;
- stable hashes for all assets used by the fixture.

Invalid fixture names should start with the failing requirement id, for example:

```text
FRAME.002_wrong_transform_direction/
ACTION.003_missing_delta_semantics/
ASSET.002_digest_mismatch/
WORLD.002_mutated_revision_without_new_hash/
```

