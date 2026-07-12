# Paper Outline

## Working Title

leWorldLayout: A Portable World Layout Norm for Robot Simulation and Evaluation

## Claim

Robotics needs a small, validated world-layout contract between robot model files and
simulator-specific scene formats. The key norm is the separation of authored layout,
appearance assets, and physics proxies.

## Sections

1. **Introduction**
   - Robot models travel better than robot-world scenes.
   - Current simulator-specific scene formats fragment authoring and benchmarks.
   - State the need for a portable world layout norm.

2. **Requirements**
   - Simulator agnostic.
   - Frame explicit.
   - Asset portable.
   - Appearance/physics separated.
   - Schema validatable.
   - Scenario compatible.

3. **Format**
   - Document envelope.
   - Object model.
   - Asset references.
   - Appearance, physics, consistency.
   - Static layout constraints.

4. **Reference Implementation**
   - URDF Studio importer/exporter.
   - Static transfer services.
   - Validation and schema generation.
   - Simulator targets.

5. **Evaluation**
   - Same layout into several simulators.
   - Invalid-layout rejection tests.
   - Blender/browser authoring round trip.
   - Scenario reuse above layout.

6. **Discussion**
   - Scope boundary with URDF, MJCF, USD, and scenario/task formats.
   - Registry and digest layer.
   - Dynamic worlds.

7. **Conclusion**
   - Layout as a public contract, not a private app export.

