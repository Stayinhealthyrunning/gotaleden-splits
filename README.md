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
löparkopplingar förblir saknade; inga tider eller relationer fabriceras. Nolhaga är en officiell
tidtagningspunkt men inte en stafettväxling.

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

Frontendens uppdelning i dataindex, diagram, replay och vylogik följer mogna arkitekturidéer från
Ultravasan Analys, men implementation, datamodell och visuell identitet är Gotaledens egna.

## Tester

```bash
python -m unittest discover -s tests -v
```

Testerna verifierar bland annat fyra lopp, källintegritet, splitimport, Nolhagas roll, stafettregler,
rådata, GPX-slicing och att den statiska sidan refererar till alla analysmoduler.
