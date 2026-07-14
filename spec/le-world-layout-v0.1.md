# leWorldLayout v0.1 RFC Specification

Status: active RFC.

This document is intentionally normative. The paper can explain motivation and evaluation; this
file defines the interchange contract.

## 1. Document Shape

A `leWorldLayout` document MUST be a JSON object with:

- `schema_version`: string, currently `le-world-layout-0.1`.
- `world_layout`: object, required.
- `environment`: object, optional.

The `world_layout` object MUST contain:

- `objects`: array.
- `scenario_time_ms`: non-negative integer.
- `scenario_duration_ms`: non-negative integer.

The `world_layout` object MAY contain:

- `name`: string.
- `urdf_xml`: string.
- `joint_positions`: object mapping joint names to numeric radians.
- `cameras`: array.

Static world layouts MUST set `scenario_time_ms = 0` and `scenario_duration_ms = 0`.

## 2. Frame Convention

If present, `environment.frame_convention` SHOULD be one of:

- `ros-rep-103`
- `studio-y-up`

Tools MAY accept additional frame identifiers, but published layouts SHOULD use a known identifier
or provide a deterministic `frame_map` in the consuming scenario/adapter.

## 3. World Object Fields

Each object in `world_layout.objects[]` MUST include:

- `id`: stable object identifier.
- `name`: human-readable name.
- `type`: one of `cube`, `sphere`, `cylinder`, `point`, `mesh`, `splat`.
- `position_xyz`: `[x, y, z]` in world coordinates, meters.
- `size_xyz`: `[x, y, z]` in meters.
- `color`: CSS hex color string or equivalent implementation-supported color.

Each object MAY include:

- `rotation_rpy_rad`: `[roll, pitch, yaw]` in radians. Omitted means identity.
- `simulation`: legacy compatibility physics metadata.
- `appearance`: source-of-truth visual/perception representations.
- `physics`: source-of-truth simulator geometry and dynamics.
- `consistency`: link between appearance and physics layers.
- `asset_ref`, `asset_scale_xyz`, or `mesh`: legacy asset metadata.

## 4. Appearance Layer

`appearance.representations[]` describes render/perception assets. Each representation SHOULD
include:

- `id`: representation id.
- `kind`: `primitive`, `mesh`, or `splat`.
- `asset_ref`: required for `mesh` and `splat`; MAY be a URI string or an asset descriptor object.
- `scale_xyz`: optional per-axis scale.
- `semantic_role`: optional free-form tag.

Appearance assets MUST NOT be assumed to be collision geometry.

## 5. Physics Layer

`physics` describes what simulator adapters consume. It MAY include:

- `collision_geometry`: object.
- `fixed`: boolean.
- `collision`: boolean.
- `mass_kg`: number.
- `inertia`: object with `ixx`, `iyy`, `izz`, `ixy`, `ixz`, `iyz`.
- `friction`: number.
- `restitution`: number.
- `semantic_role`: string.

`physics.collision_geometry.kind` SHOULD be one of:

- `box`
- `sphere`
- `cylinder`
- `mesh`

Gaussian splat appearance representations MUST provide a physics proxy before the object is
considered simulator-portable, except for top-level appearance-only background objects that are
explicitly marked non-colliding.

## 6. Consistency Layer

`consistency` records how appearance and physics relate. It SHOULD include:

- `appearance_ref`: id of the appearance representation.
- `physics_ref`: id of the physics geometry.
- `method`: e.g. `hand-authored`, `bbox-fit`, `convex-decomposition`, `unchecked`.
- `status`: `valid`, `warning`, `missing`, or `unchecked`.
- `metrics`: optional object.

## 7. Asset Resolution

World layout assets MUST NOT be limited to relative paths. A valid asset reference MAY use:

- a path relative to the package root;
- an HTTPS URL;
- a Hugging Face repository URI such as `hf://organization/dataset/path`;
- object storage such as `s3://bucket/key` or compatible schemes;
- OCI artifact references;
- IPFS or other content-addressed registry URIs;
- an embedded payload when the profile permits it.

Portability depends on deterministic resolution and digest verification, not on forcing every
asset into one folder. The normative asset descriptor shape is:

```json
{
  "uri": "hf://organization/dataset/assets/world_001.spz",
  "sha256": "a821000000000000000000000000000000000000000000000000000000000000",
  "media_type": "model/vnd.spz",
  "mirrors": [
    "assets/world_001.spz"
  ]
}
```

`mirrors[]` MAY contain local relative mirrors or alternate resolvers. A consumer MUST verify that
the resolved bytes match `sha256` before treating the asset as the declared representation. Inline
assets MAY be represented with `embedded` metadata, but profiles SHOULD restrict embedded payloads
to small assets or metadata fixtures.

The rule applies to:

- top-level `asset_ref`;
- `mesh.asset_ref`, `mesh.path`, `mesh.uri`, `mesh.filename`;
- `appearance.representations[].asset_ref`;
- `physics.collision_geometry.asset_ref`.

## 8. Delivery Modes

A layout MAY be delivered as:

- a single JSON file;
- a folder containing the JSON file plus mirrored assets;
- a URL whose relative asset references resolve against the document URL;
- remote resolvers such as Hugging Face, object storage, OCI, or IPFS;
- a registry envelope containing the same `world_layout`.

Consumers MUST resolve relative mirrors against the document package root, not against the consumer
machine's current working directory. Remote URI schemes MUST be resolved by their declared binding
or rejected with a deterministic diagnostic.

## 9. Compatibility With Existing URDF Studio World Format

URDF Studio's `world_layout`, `world`, and `world_snapshot` payloads are the current implementation
base. `leWorldLayout` v0.1 preserves that practical shape while naming the public norm separately.
