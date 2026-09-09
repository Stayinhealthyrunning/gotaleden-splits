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
Stafetter analyseras publikt som `lag → kontroll → delsträcka`; löpar-etapp-koppling får inte krävas
eller härledas i publikt UI.

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
- EQ Timings publika resultattjänst används för officiella passager via den reproducerbara
  probe-/adapterkedjan.
- Ingen mellantid får fabriceras. Saknas splitdata ska det märkas tydligt, och officiell GPX förblir
  master för kartgeometri och distanser.
- Profilernas Journey-analyser använder verkliga analytiska passager och en fast komplett
  FINISHED-kohort genom hela gap- och pacingjämförelsen. DNF slutar vid sista verkliga observation.

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
- En race edition refererar en provider-neutral `source_binding`; flera editions får dela samma
  source event. Providerfält och source-routing hör till source-konfigurationen/adaptern och får
  inte härledas från race key, år, distans eller ortnamn.
- Editions med `data_status=available` måste ha en giltig source binding. `planned` får katalogiseras
  utan resultatkälla och ska då inte exponeras som analyserbar. Import körs en gång per
  `(provider, source_event)` och source-/resultatidentiteter måste vara event-skopade.
- Race family, race edition och source event är skilda identiteter. En full build inkluderar alla
  editions med tillgänglig data från samtliga source events; kanonisk webbexport är flerårig och
  routing får inte innehålla års- eller race-key-specialfall. Providerlogik hör hemma i adaptern.
- Varje RaceEdition refererar explicit en CourseVersion och neutral `route_range`. Course geometry,
  checkpoints, ankare och segment definieras i course-config utan ort-, distans- eller årsheuristik.
  Samma course-version-id är immutable och skyddas av fingerprint; geometriändring kräver nytt id.
  Olika course versions är inte whole-course-jämförbara utan explicit comparison group, och segment
  över versioner kräver explicit gemensam comparison identity.
- Ett race-resultat är en edition-bunden appearance, inte automatiskt en canonical person. External
  IDs måste ha explicit scope; namn/demografi får aldrig ensamma mergea personer, lokal identity får
  inte tolkas cross-year och konflikter får inte tyst mergeas. Lagidentitet får inte skapas över år
  enbart från lagnamn.
- Bygg import och validering reproducerbart i Python och GitHub Actions.
- Bevara källspårning och importdiagnostik.
- GitHub Pages publiceras från `docs/`.
- Sidan ska kunna byggas och publiceras utan lokal utvecklingsinstallation hos användaren.
- Arbeta normalt på branch/PR när integrationen stödjer det.
- Race-level segmentfördelningar ska använda samma kompletta FINISHED-kohort genom hela loppet.
- Banans svårighetsprofil får beskriva klättring, farttapp, spridning och officiell placeringsrörelse, men inte påstå teknisk stigsvårighet eller skapa ett syntetiskt totalscore.
- Head-to-head-luckor använder endast gemensamma verkliga officiella analyspassager. Segmentdelta
  kräver verkliga endpoints för båda, placeringsresan använder endast officiell totalplacering och
  fältpacing använder samma stabila kompletta race-referens för båda deltagarna eller lagen.
- Alla analytiska delkomponenter i Head-to-head ska ha entries i den gemensamma metodhjälpen.
- Favoriter lagrar endast canonical result-ID lokalt i webbläsaren och hålls separata från jämförelsevalet.
- Varje användarsynlig analytisk komponent ska ha en konsekvent `(i)`-kontroll med metodhjälp. En
  enrads-tooltip räcker inte. Hjälpen ska beskriva syfte, exakt beräkning/metod, datakälla,
  kohort/urval, tolkning och materiella begränsningar samt skilja officiella observationer från
  härledda mått och interpolerade/modellerade värden. En ny analysfunktion är inte färdig förrän dess
  help-entry finns, UI:t exponerar den och regressionstest verifierar kopplingen. Hjälpen måste bevara
  stafettsemantik, Nolhagas roll och projektets data-/icke-fabriceringsinvarianter.
