# Gotaleden Splits

Fristående analysverktyg för **Gotaleden Stafett & Ultra**.

## Fyra sektioner

- Individuellt 75
- Individuellt 35
- Stafett 75
- Stafett 35

Projektet återanvänder arkitekturprinciper från Ultravasan Analys men har egen datamodell för stafettlag och egen grafisk identitet.

## Data som ingår i denna första grund

Officiella EQ Timing-exporter från premiäråret 2026:

| Sektion | EQ Timing-lopp | Poster |
|---|---|---:|
| Individuellt 75 | Ultra 75 km | 274 |
| Individuellt 35 | Sprint 35 km | 163 |
| Stafett 75 | Stafett 75 km | 121 |
| Stafett 35 | Stafett 35 km | 49 |

Alla originalkolumner bevaras. De aktuella CSV-filerna innehåller endast målpassagen, så mellanpassager måste kompletteras från EQ Timings publika resultattjänst/API.

## Bana

`data/source/gpx/Gotaleden_Ultra_75km-30april.gpx` är enda source of truth för banans geometri.

35 km-loppen använder samma rutt från Floda, cirka `57.80629, 12.35532`.

Byggscriptet hittar närmaste GPX-punkt automatiskt och skapar `docs/data/route.json`.

## Bygg data

```bash
python tools/build_project_data.py
```

Det skapar:

- `data/gotaleden.sqlite`
- `docs/data/results-2026.json`
- `docs/data/route.json`
- `reports/import-summary-2026.json`

## Tester

```bash
python -m unittest discover -s tests
```

## Webbplats

Statisk webbplats finns i `docs/` och är förberedd för GitHub Pages.

Designriktning: Gotaledens identitet, Göteborg/Västkust, vårskog, vitsippor, skimrande blå sjöar och ljus vårgrönska.

## Viktigt om stafettdata

CSV-exporten ger lagnamn och ett listat personnamn men inte en verifierad komplett koppling mellan lagmedlem och etapp.
Systemet behandlar därför stafetten på lagnivå tills bättre källdata finns.
