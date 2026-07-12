# Open Questions

- Public name: keep `WorldEpisode` unless a naming collision appears.
- Use `leWorldLayout` only as a layout-profile or legacy working-directory name.
- Whether v0.1 should require `schema_version` or accept bare `world_layout` for compatibility.
- Whether `color` should be normative CSS hex only or implementation-defined.
- Whether top-level `type: "splat"` should require an explicit `physics.collision = false`.
- Whether registry envelope and artifact digests belong in v0.1 or a separate registry spec.
- Whether dynamic layouts belong in this format or only in the Scenario layer.
- Which frame conventions should be stable identifiers.
- Whether canonical JSON should be required for all published layouts or only registry artifacts.
