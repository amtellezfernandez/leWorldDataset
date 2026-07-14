# Paper Outline

## Working Title

WorldEpisode: A Storage-Neutral Interchange Contract Linking Robot-Learning Episodes to Versioned, Replayable 3D Worlds

## Claim

Robotics needs a storage-neutral semantic contract between robot-learning episodes and immutable,
versioned, replayable 3D worlds. Gaussian splats are an important appearance profile, not the
normative center.

## Sections

1. **Introduction**
   - Robot-learning datasets and scene formats solve different layers.
   - "LeRobot plus Gaussian splats" is not a safe novelty claim.
   - State the need for a world-episode interoperability contract.

2. **Requirements**
   - Storage neutral.
   - Representation neutral.
   - Runtime neutral.
   - Loss explicit.
   - Schema validatable.
   - Conformance executable.

3. **Five-Graph Model**
   - Identity graph.
   - Frame and clock graph.
   - Representation-role graph.
   - Temporal state and event graph.
   - Provenance and derivation graph.

4. **Contracts**
   - Complete action semantics.
   - Immutable world revisions.
   - Loss-aware conversion.
   - Lineage-safe splits.

5. **Evaluation**
   - Semantic preservation across bindings.
   - Fault injection for physical-coherence errors.
   - Cross-simulator replay.
   - VLA robustness.
   - Leakage analysis.

6. **Discussion**
   - Bindings instead of monolithic storage.
   - Relationship to LeRobot, Rerun, NCore, MCAP, OpenUSD, glTF, GSDF.
   - Governance and conformance profiles.

7. **Conclusion**
   - World-episode semantics as a public executable contract.
