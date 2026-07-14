# Open Questions

- Addressed (2026-07-14): external adopter feedback on a multi-agent logistics deployment (VLA
  policies, PDA/WMS interfaces, human teleoperation) flagged "sidecar bloat" risk -- the temptation
  to model LLM/VLM reasoning traces, raw UI telemetry, and resource arbitration directly inside the
  WorldEpisode sidecar. Resolved by adding `spec/worldepisode-v0.1.md` Section 9 (Scope Boundaries:
  Non-Spatial State), which routes those signals to native containers and maps takeover-style events
  to the existing `intervention` event kind rather than a new field. Still open: a worked
  "hybrid stack" integration guide (WorldEpisode alongside MCAP/LeRobot as sync/audit glue) once a
  real adopter is exercising this boundary.

- Public name: keep `WorldEpisode` unless a naming collision appears.
- Use `leWorldLayout` only as a layout-profile or legacy working-directory name.
- Whether v0.1 should require `schema_version` or accept bare `world_layout` for compatibility.
- Whether `color` should be normative CSS hex only or implementation-defined.
- Whether top-level `type: "splat"` should require an explicit `physics.collision = false`.
- Whether registry envelope and artifact digests belong in v0.1 or a separate registry spec.
- Whether dynamic layouts belong in this format or only in the Scenario layer.
- Which frame conventions should be stable identifiers.
- Whether canonical JSON should be required for all published layouts or only registry artifacts.
