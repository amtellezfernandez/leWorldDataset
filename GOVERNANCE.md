# Governance

Status: active RFC governance.

WorldEpisode is governed as an open interoperability profile, not as a single-project data dump.

## Licensing

- Specification text, schemas, examples, and paper-adjacent documentation in this repository: CC0
  1.0 Universal, as declared in `LICENSE`.
- SDK and validator implementation code (the `worldepisode` package): Apache License 2.0, as
  declared in `LICENSE-APACHE`, unless a file states otherwise.
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
