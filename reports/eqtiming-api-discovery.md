# EQ Timing public API discovery — event 77906

Discovery was intentionally limited to the official public event page and its loaded JavaScript.

## Endpoint

- Metadata: `GET https://live.eqtiming.com/api/Contestants/77906`
- Detailed bulk data: `POST https://live.eqtiming.com/api/Contestants/77906?passes=true`
- Single-bib verification: `GET https://live.eqtiming.com/api/Result/Contestant/77906?bib={bib}`

The local adapter first resolves public contestant UIDs, then requests details in bounded chunks of
100. Every response is validated against the 607 known bibs and its expected race before the snapshot
is written atomically.

## Verified probes

- Bib 717, Anton Gustafsson, Ultra 75 km: ten positive passages from Skatås through Nolhaga and Mål.
- Bib 41, Hälle IF, Stafett 75 km: ten positive team passages plus nine public team-member positions.

The detailed endpoint exposes `EtappeDeltaker → Passeringer` with station, accumulated milliseconds,
split milliseconds/distance, speed, pace and overall/gender/class placing. The snapshot contains 607
validated contestants. The importer accepts only passages with positive accumulated time; zero-valued
schema placeholders are not interpreted as results.

## Model decisions

- Source names map reproducibly to configured checkpoints; `V:a Bodarna` maps to Västra Bodarna.
- Nolhaga is a timing point and never a relay-leg boundary.
- Relay runner assignments still require XML/result-list evidence and work when that evidence is absent.
- No split, placing, runner assignment or passage is interpolated into the source model.
