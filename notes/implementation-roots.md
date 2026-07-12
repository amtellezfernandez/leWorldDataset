# Implementation Roots

The first world-layout profile draft is derived from the working URDF Studio World implementation.
The formal paper/specification target is now `WorldEpisode`: a storage-neutral contract that binds
robot-learning episodes to immutable world revisions.

Important source locations in `/home/amdev/studio/urdf-studio`:

- `docs/specs/WORLD_FORMAT.md` - prose reference for the current World format.
- `docs/specs/world-v1.schema.json` - generated public schema.
- `docs/specs/WSP_manifest.schema.json` - legacy registry envelope schema path.
- `backend/models/world_scene_package.py` - pydantic model and validator source.
- `backend/services/world_asset_refs.py` - portable asset reference normalization.
- `backend/services/world_layout_static_transfer.py` - static layout parser/transfer entrypoint.
- `backend/services/world_layout_transfer_mujoco.py` - MuJoCo transfer.
- `backend/services/world_layout_transfer_genesis.py` - Genesis transfer.
- `backend/services/simulator_adapters/world_scene.py` - simulator scene loading.
- `docs/specs/SCENARIO_FORMAT.md` - task/evaluation layer above world layout.

Paper positioning:

- URDF Studio is the reference implementation.
- `leWorldLayout` is a world-layout profile and historical working name.
- `WorldEpisode` is the independent norm/specification surface.
- The paper should avoid making the public contract depend on URDF Studio internals.
