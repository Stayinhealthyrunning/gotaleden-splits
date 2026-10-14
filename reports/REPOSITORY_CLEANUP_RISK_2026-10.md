# Gotaleden cleanup risk classification — 2026-10

This is the Phase 2 evidence record for the clean `origin/main` checkout
`2c247d7b7d40fb7bd28bdfd700b34043fdcde00b`. It does not expose source rows,
participant identifiers or private registry material.

## Classification key

- **A — safe removal:** no runtime, CI, provenance, compatibility or GDPR
  dependency; removal can be proved by the repository tests.
- **B — retain/security-sensitive:** history sanitation, privacy gates, source
  restore, or support evidence. Never remove as housekeeping.
- **C — intentional compatibility duplicate:** generated alias or stable output
  consumed by tests, build tooling, Pages, or documented consumers.
- **D — active product/test dependency:** code, data, workflow or report used by
  the public application or verification suite.
- **E — unresolved/needs owner decision:** dependency evidence is incomplete;
  leave untouched and keep any cleanup PR Draft.

## Concrete candidates

| candidate | class | evidence | action |
|---|---|---|---|
| `docs/data/results.json` and `docs/data/results-2026.json` | C/D | byte-identical today, but `app.js`/map use `results.json`, compatibility tests explicitly require `results-2026.json`, and `protect-minors.yml` updates both | retain both; do not replace with symlink or delete |
| `docs/data/route.json` and `docs/data/courses/course-v1/route.json` | C/D | generator writes the course-scoped artifact and a Pages-compatible root alias; frontend/tests consume the root alias | retain both |
| `docs/data/route-elevation-2026.json` and `docs/data/courses/course-v1/elevation.json` | C/D | same generator contract as route files; adapter/tests consume the root compatibility path | retain both |
| `reports/eqtiming-*-2026-*` and `reports/eqtiming-*` aliases | C/D | `tools/build_official_data.py` regenerates both; README/tests and diagnostics consume canonical aliases | retain both until a versioned contract removes compatibility |
| `reports/import-summary.json` and `reports/import-summary-2026.json` | C/D | `tools/build_project_data.py` writes both and tests assert the compatibility filename | retain both |
| `reports/gpx-comparison-course-v1.*` and `reports/gpx-comparison.*` | C/D | generator copies the course report to the stable public report name; tests/README use stable name | retain both |
| `.github/workflows/guard-public-raw-sources.yml`, `privacy-registry.yml`, `protect-minors.yml`, `test.yml` | B/D | PR/push release gates and privacy contracts; removing any weakens publication safety | retain and run in CI |
| `.github/workflows/privacy-history-rehearsal.yml`, `prepare-support-pr-cleanup.yml`, `verify-sanitized-history.yml` | B | disposable-mirror audits and GitHub Support evidence; old PR refs are explicitly out of ordinary cleanup scope | retain; never convert to an automatic destructive job |
| `.github/workflows/purge-legacy-raw-ref-history.yml` | B/E | contains guarded force-with-lease history operations and is tied to legacy sanitation; no new invocation is authorized by this task | retain unchanged; require separate owner approval for any execution |
| `reports/eqtiming-*`, `reports/gpx-*`, `reports/*relay*` | D | generated provenance/diagnostics and regression fixtures, not runtime dead files | retain |

## Result

No tracked candidate meets class A. No class C consolidation is safe while
the current generator and tests explicitly require both names. The only local
test artifact created during baseline QA was untracked and ignored/temporary;
it is not a repository candidate. Therefore this PR deliberately performs no
deletion or code simplification: a deletion without a contract migration would
be an unverified regression.

## Verification performed

- `git ls-files` and SHA-256 grouping found the duplicates listed above.
- `rg` confirmed generator, frontend, workflow and test consumers for every
  C/D item.
- No raw/private source was copied into the public checkout.
- The existing 299-test Gotaleden baseline remains fixture-blocked (19 errors,
  2 failures); CI with the documented private restore is the required next
  verification step.
