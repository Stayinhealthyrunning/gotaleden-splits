# Gotaleden historical source inventory

Audit date: **2026-09-10**

## Result

No additional historical RaceEdition can be imported. Gotaleden Stafett & Ultra premiered on
9 May 2026, and the four 2026 editions already form the canonical dataset. The announced event on
8 May 2027 is still in the future and has no result source, so it is deliberately not represented as
available data.

This means the production catalog correctly remains single-edition per RaceFamily. The generic
history engine still handles multiple editions, missing years, finish-only editions, explicit course
comparability and conservative person identity in its synthetic contract fixtures; none of those
capabilities justify inventing a production year.

## Canonical edition inventory

| RaceEdition | Results | Splits | CourseVersion |
| --- | ---: | ---: | --- |
| `individual-75-2026` | 274 | 2,121 | `course-v1` |
| `individual-35-2026` | 163 | 638 | `course-v1` |
| `relay-75-2026` | 121 | 1,077 | `course-v1` |
| `relay-35-2026` | 49 | 223 | `course-v1` |
| **Total** | **607** | **4,059** | |

No cross-year CourseVersion equivalence or person identity is asserted. Existing 2026
source-event-scoped identities and the immutable `course-v1` fingerprint remain unchanged.

## Evidence and provenance

- [Official event site](https://www.gotaledenstafettultra.se/) identifies 2026 as the first edition
  and announces 8 May 2027 as the next event.
- [Official 2026 results page](https://www.gotaledenstafettultra.se/resultat-2026/) exposes only 2026
  and links the four formats to [EQ Timing event 77906](https://live.eqtiming.com/77906).
- [Leader Göta Älv project record](https://leadergotaalv.se/projekt/gotaleden-stafatt-ultra/)
  describes a new event whose first running was planned for 9 May 2026.
- [Contemporary pre-event reporting](https://www.lokalpressen.se/nytt-lopp-pa-gotaleden-infor-2026-6.2.2562.f9eec92980)
  states that no race had previously existed on Gotaleden and announces the 2026 premiere.
- [Post-event reporting](https://www.borjessonsbil.se/nyheter/succe-for-gotaleden-stafett-ultra)
  calls 9 May 2026 the premiere and identifies 8 May 2027 as the planned next edition.

The machine-readable inventory and explicit non-import decisions are in
`reports/gotaleden-history-source-inventory.json`.
