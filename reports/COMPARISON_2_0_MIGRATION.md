# Gotaleden → Loppanalys Comparison 2.0 migration plan

## Goal

Bring Gotaleden Head-to-head to the shared Comparison 2.0 interaction standard
while keeping Gotaleden's strongest contribution to Engine 1.0 intact:
**explicit person/team competition semantics**.

Canonical contract:

- `Stayinhealthyrunning/ultravasan-analys/config/comparison-contract-v2.json`
- explanatory reference: `reports/COMPARISON_2_0.md`.

## Current strengths to preserve

Gotaleden is already analytically close to the reference:

- exact two-entity Head-to-head;
- finish context;
- passages led and observed lead changes;
- most-time-won, nearest and largest-gap KPIs;
- signed checkpoint-gap journey;
- official placement journey;
- clickable segment duel;
- pacing against a stable complete FINISHED reference cohort;
- route/elevation context;
- shareable Head-to-head URL;
- 2–5 entity Kartduell with music, synchronized elevation and race clock;
- native support for both persons and relay teams.

Do not rewrite this as an Ultravasan clone.

## Primary gap: animated comparison inside Head-to-head

Continuous motion currently lives in Kartduell. Comparison 2.0 should also
offer a focused two-entity playback inside Head-to-head.

Reuse Gotaleden's existing map/replay/audio primitives rather than introducing
a second geometry model.

Target behavior:

- two markers on the verified course;
- one shared race clock;
- play/pause/reset;
- scrubber;
- 30 s / 1 min / 2 min / 3 min playback choices;
- 2 min default;
- whole-course / follow-both / follow-leader camera modes;
- synchronized elevation markers;
- elevation seeking;
- checkpoint/segment clicks seek or highlight the same analytical state;
- soundtrack with 30% neutral volume and persisted preference.

The motion between official timing anchors remains reconstructed.

## Team semantics are mandatory

The implementation must remain entity-aware:

- `participant.entity=person` for individual races;
- `participant.entity=team` for relay races;
- Head-to-head card labels and ranking context come from the race adapter;
- relay class metadata remains source-driven;
- non-competitive classes retain their existing semantics;
- team-member rows never become inferred relay legs.

A shared comparison component that assumes every entity is a person is
therefore not compatible with Gotaleden.

## Segment/checkpoint integrity

The current 75 km and 35 km analytical boundaries are source/contract-defined.
Do not promote auxiliary speaker/replay points to analytical checkpoints or
segments merely because they exist on the map.

Comparison clicks may seek replay via auxiliary geometry anchors, but analytical
gap/segment values must remain bound to the real analysis contract.

## Field normalization

Keep the current stable complete FINISHED cohort semantics. The visible 0%
reference and A/B direction should align with the shared contract.

If future relay editions require class-specific reference semantics, that must
be explicit in the adapter rather than inferred in the UI.

## Future 2027 readiness

There is only one current RaceEdition. Do not manufacture cross-year support
from 2026 data.

However, structure the comparison view-model so a future edition can enable
cross-edition dimensions independently:

- whole-course finish comparison;
- checkpoint comparison;
- segment comparison;
- shared geometry.

The same RaceFamily must never be treated as proof of equal CourseVersion.

## Sparse fallback

Implement the shared sparse fallback in the component architecture, but do not
change the rich 2026 presentation. It exists for future source-limited editions
and should activate only through capabilities/evidence.

## Suggested implementation order

1. Map existing Head-to-head analysis into the shared capability names.
2. Keep all current KPI/gap/placement/segment/field behavior passing unchanged.
3. Add embedded two-entity replay using existing GMapEngine/GRacePlayback/media.
4. Synchronize analytical selection with time/map/elevation.
5. Align duration/audio/camera defaults.
6. Add sparse fallback hooks.
7. Add browser coverage for individual and relay comparisons.
8. Add future-edition tests that prove same family does not imply comparability.

## Acceptance examples

An Individual 75 comparison should retain the current complete analytical view
and gain synchronized replay. A Relay 75 comparison should do the same using
team labels/class semantics, without pretending team members are individual
race entities or assigning legs. A future edition with insufficient timing
should degrade by capability rather than fabricate Gotaleden-style segments.

## Implemented comparison boundary

`GHeadToHead` keeps Engine 1.0's official A/B, placement, segment and stable
FINISHED-cohort calculations. `GComparisonReplay` is a separate presentation
controller inside that dialog, using the existing map, playback, media and
elevation primitives. It is enabled only for two selected results in the same
edition when that edition has replay capability, its own loaded route and at
least two source-backed replay anchors **for each** result. Elevation seeking
also requires that CourseVersion's elevation asset. Audio additionally requires
event media. A missing route or sparse result never disables the shareable
official comparison.

The shared clock and reconstructed positions between source observations are
never analytical checkpoints, segment times or official places. Sparse
comparisons show only shared observed steps, and DNF cannot create a synthetic
finish. This deliberately retains Gotaleden's stricter Engine 1.0 distinction
between replay anchors and the established nine/four analysis segments. Team
entities remain teams; member metadata never assigns a relay leg. Cross-edition
comparison remains disabled until course and identity compatibility is explicit.
