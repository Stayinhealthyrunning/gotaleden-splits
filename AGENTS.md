# AGENTS.md — Gotaleden Splits

## Projektets syfte

Detta repository innehåller **Gotaleden Splits**, ett fristående analysverktyg för Gotaleden Stafett & Ultra.
Projektet ska hållas helt separat från Ultravasan Analys, men mogen arkitektur och återanvändbara idéer från
`Stayinhealthyrunning/ultravasan-analys` får användas som förebild.

## Produktstruktur

Webbplatsen har fyra huvudsektioner:

1. **Individuellt 75** — källdata: EQ Timing `Ultra 75 km`.
2. **Individuellt 35** — källdata: EQ Timing `Sprint 35 km`.
3. **Stafett 75** — källdata: EQ Timing `Stafett 75 km`.
4. **Stafett 35** — källdata: EQ Timing `Stafett 35 km`.

Individuella lopp analyseras primärt som `löpare → kontroll → delsträcka`.
Stafetter analyseras primärt som `lag → etapp → löpare`, men all laganalys måste fungera även om
kopplingen mellan en viss löpare och en viss etapp saknas i källdatan.

## Bana och GPX

- `data/source/gpx/Gotaleden_Ultra_75km-30april.gpx` är enda source of truth för banans geometri.
- Alla fyra loppen följer samma bana.
- 75 km-loppen använder hela rutten Göteborg–Alingsås.
- 35 km-loppen använder samma rutt från Floda till Alingsås.
- Floda-start: cirka `57.80629, 12.35532`.
- När GPX processas används närmaste ruttpunkt som reproducerbar 35 km-start.
- Officiella produktnamn 75/35 behålls även om faktisk GPX-distans avviker.
- Distansbaserad analys ska använda GPX-baserad distans när sådan finns.

## Officiella etapper

75 km:
1. Göteborg–Skatås — 4,5 km
2. Skatås–Kåsjön — 10,5 km
3. Kåsjön–Jonsered — 7,5 km
4. Jonsered–Lerum — 10 km
5. Lerum–Floda — 9 km
6. Floda–Tollered — 8 km
7. Tollered–Norsesund — 12 km
8. Norsesund–Västra Bodarna — 6,5 km
9. Västra Bodarna–Alingsås — 10 km

35 km-loppen använder etapp 6–9.

## Resultatdata

- Originalfiler från EQ Timing sparas oförändrade under `data/source/eqtiming/`.
- Importen ska bevara **alla originalfält** i `raw_json`.
- 2026 är premiäråret.
- De fyra CSV-exporterna vid projektstart innehåller en rad per deltagare/lag vid `Mål`.
- Mellanpassager finns inte som separata rader i dessa exporter.
- Projektet ska senare kompletteras med en probe/adapter mot EQ Timings publika resultattjänst/API eller
  de publika JSON-anrop som webbsidan använder.
- Ingen mellantid får fabriceras. Saknas splitdata ska det märkas tydligt.

## Stafett

- Stafett 75: 2–9 deltagare, 9 etapper.
- Stafett 35: 2–4 deltagare, 4 etapper.
- Samma person kan springa flera etapper.
- `Firstname`/`Surname` i stafettens mål-CSV är inte bevis för vem som sprang en specifik etapp.
  Dessa fält lagras därför som `listed_contact_name` tills samband är verifierat.
- Laganalys ska fungera utan löpar-etapp-koppling.

## Design

- Produktnamn: **Gotaleden Splits**.
- Egen identitet, inte en kopia av Ultravasan.
- Följ Gotaleden Stafett & Ultras officiella färgidentitet så nära som möjligt.
- Känsla: Göteborg/Västkust, Sävedalen, hav av vitsippor, skimrande blå sjöar, vårgrönska och solljus.
- Uttrycket ska vara ljust, friskt, elegant och seriöst.
- Banlinjen Göteborg–Skatås–Kåsjön–Jonsered–Lerum–Floda–Tollered–Norsesund–Västra Bodarna–Alingsås
  får gärna återkomma grafiskt.

## Arkitektur

- Separera rådata, processad data och webbdata.
- Bygg import och validering reproducerbart i Python och GitHub Actions.
- Bevara källspårning och importdiagnostik.
- GitHub Pages publiceras från `docs/`.
- Sidan ska kunna byggas och publiceras utan lokal utvecklingsinstallation hos användaren.
- Arbeta normalt på branch/PR när integrationen stödjer det.
