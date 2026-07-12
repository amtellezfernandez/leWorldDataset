# Landscape and Positioning

Status: working RFC note.

## Verdict

The defensible category is not "LeRobotDataset plus Gaussian splats in one file format." That
category is crowded by Gaussian asset standards, GSDF-like simulation assets, RoboSnap/DROID-Sim,
OpenUSD, Rerun, NCore, and simulator-specific pipelines.

The stronger category is:

> A storage-neutral, representation-neutral interchange contract linking robot-learning episodes
> to immutable, versioned, replayable 3D worlds.

Gaussian splats should be a high-value profile and demonstration. They should not be the core claim.

## Category Definition

WorldEpisode is an open interchange profile that binds a robot-learning episode to an immutable
world revision using:

- persistent entity identity;
- explicit clocks and coordinate frames;
- fully specified action semantics;
- multiple visual and physical representation roles;
- replay assumptions;
- provenance and uncertainty;
- dataset lineage and leakage-aware splits.

## Non-Goals

- Do not replace LeRobot, Rerun, NCore, MCAP, OpenUSD, glTF, or GSDF.
- Do not claim universal losslessness.
- Do not claim simulator-independent behavior.
- Do not claim to be the first Gaussian robot-world format.
- Do not make Gaussian splats the normative center.

## Claim Language

Use:

- "storage-neutral interoperability profile"
- "canonical binding between robot episodes and versioned worlds"
- "representation-agnostic, with a Gaussian-appearance profile"
- "loss-explicit conversion"
- "replay under declared physical and numerical assumptions"
- "persistent identity across observations, assets, and simulation"
- "lineage-aware evaluation splits"

Avoid:

- "one universal format"
- "first Gaussian robot format"
- "perfect digital twin"
- "ground-truth physics"
- "lossless conversion between all simulators"
- "simulator-independent behavior"
- "replacement for LeRobot, USD, or Rerun"

## Novelty Wedges

1. Complete action semantics.
2. Immutable world revisions.
3. Cross-representation entity identity.
4. Loss-aware conversion reports.
5. Lineage-safe dataset splits.

## Initial Scope

Version 1 should target rigid tabletop manipulation with fixed-base single- or dual-arm robots.
Humanoids, locomotion, deformables, fluids, and multi-agent environments should become later
profiles.

## Reviewer Red Team

| Criticism | Response |
|---|---|
| "This is just USD." | USD represents composed worlds and assets. WorldEpisode specifies episode/action/task semantics, world revision binding, dataset lineage, conversion loss, and ML splits. |
| "GSDF already combines splats and physics." | Acknowledge GSDF as direct prior art and provide a binding/converter. Differentiate on storage-neutral world-episode interoperability. |
| "Rerun already solves robot data." | Rerun is a data layer and serialization target. WorldEpisode is a semantic contract that can live inside Rerun. |
| "NCore already has sensors and pose graphs." | Reuse NCore conventions; add action, task, outcome, physical-role, world-revision, and split-lineage semantics. |
| "A schema is not research." | Include conversion-fidelity experiments, validator fault injection, cross-simulator replay, leakage analysis, and downstream policy results. |
| "The scope is impossible." | Restrict v1 to rigid tabletop manipulation and make other domains profiles. |

