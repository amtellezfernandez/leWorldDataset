# Governance

Status: draft.

WorldEpisode should be governed as an open interoperability profile, not as a single-project data
dump.

## Licensing

- SDK and validator code: Apache-2.0 by default.
- Specification text, examples, and paper-adjacent documentation: CC-BY-4.0 by default.
- Dataset assets: explicit per-asset license in the asset descriptor.

## Process

- Use semantic versioning for schemas and conformance profiles.
- Use public RFC issues for normative changes.
- Keep requirement IDs stable once published.
- Maintain an extension registry for resolver schemes, representation roles, bindings, and
  conformance profiles.
- Record accepted design decisions in short decision records.
- Define deprecation windows before removing fields or profile requirements.
- Archive stable releases with DOIs.

## Independence Target

Before claiming standard status, the project should have:

- at least two independently written implementations;
- at least one external dataset that passes a published profile;
- maintainers from more than one institution;
- public conversion-loss reports for every reference adapter.

