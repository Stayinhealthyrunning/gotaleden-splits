# Gotaleden Splits

Fristående analysverktyg för **Gotaleden Stafett & Ultra 2026**. Webbplatsen har fyra separata
lägen: Individuellt 75, Individuellt 35, Stafett 75 och Stafett 35.

## Datakällor

- Officiell kombinerad EQ Timing-resultatlista: 607 deltagare och lag.
- EQ Timings publika contestant-endpoint: 4 059 faktiska passeringar efter att nollvärda
  DNS-/kontrollplatshållare filtrerats bort.
- Officiell XML-startlista: verifierad etapp–löpare-koppling för stafetter.
- `data/source/gpx/Gotaleden_Ultra_75km-30april.gpx`: enda geometrikälla för banan.

Alla råfält bevaras i SQLite `raw_json`. Webbfilen är avsiktligt kompakt. Saknade passeringar och
löparkopplingar förblir saknade; inga tider eller relationer fabriceras. Publikt är stafettanalysen
helt lagbaserad; intern runner-to-leg-källdata exponeras inte. Nolhaga är en officiell tidtagningspunkt
men inte en stafettväxling.

Normaliseringen skiljer mellan splitfart/-placering och ackumulerad fart/-placering. Den kompletterar
även deltagar-UID, ålder, födelseår, klubbers källprioritet och EQ Timings klassrankningsflagga.

## GPX och höjd

`Gotaleden_Ultra_75km-30april.gpx` är alltid master för geometri, avstånd, checkpointprojektion och
replay. `Suunto 9 baro Gotaleden 75.gpx` är en personlig referensmätning med en känd felspringning och
får aldrig ersätta den officiella rutten.

Suunto-elevation används endast när punkten kan matchas inom 50 meter och med sekventiell,
monotont rimlig progression längs officiell GPX. Off-route-sektioner ignoreras. Referenshöjden
aggregeras var 50:e meter och jämnas försiktigt; saknas eller underkänns referensfilen används den
officiella GPX-filens elevation utan fabricerad ersättning.

Checkpoints exporterar tre skilda avstånd:

- `nominal_cumulative_km` från loppets källmodell;
- `race_distance_km` relativt respektive start;
- `route_distance_km` absolut längs officiell GPX från Göteborg.

Mappingen är proportionell i två segment med den geografiskt verifierade Floda-punkten som ankare.
Mål är alltid exakt GPX-ruttens slutpunkt.

## Bygg och uppdatera

Den publika snapshoten finns incheckad för reproducerbara byggen. En ny snapshot hämtas uttryckligen:

```bash
python tools/fetch_eqtiming_public.py --refresh
python tools/build_project_data.py
```

Bygget skapar SQLite-databasen, kompakt webbdata under `docs/data/` och diagnostik under `reports/`.

## Analyswebb

Den statiska GitHub Pages-sidan i `docs/` innehåller:

- måltids- och klassfördelning;
- medianfart per delsträcka;
- sökbara och sorterbara resultat;
- individ- och lagdetaljer med officiella passeringar;
- stafettbelastning och verifierade etappkopplingar;
- jämförelse av upp till fem deltagare eller lag;
- GPX-replay med tydligt märkt uppskattning mellan officiella passeringar.
- höjdprofil längs samma officiella `route_distance_km` som replay.

Frontendens uppdelning i dataindex, diagram, replay och vylogik följer mogna arkitekturidéer från
Ultravasan Analys, men implementation, datamodell och visuell identitet är Gotaledens egna.

## Tester

```bash
python -m unittest discover -s tests -v
```

Testerna verifierar bland annat fyra lopp, källintegritet, splitimport, Nolhagas roll, stafettregler,
rådata, GPX-slicing, elevation fallback, replay-ankare och att runner-to-leg inte visas publikt.

Kvalitetsrapporter:

- `reports/eqtiming-split-coverage.{json,md}`
- `reports/gpx-comparison.{json,md}`
