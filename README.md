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
helt lagbaserad; intern runner-to-leg-källdata exponeras inte. Nolhaga är en officiell tidtagnings-
och speakerpunkt samt ett replay-ankare, men aldrig en stafettväxling eller analytisk delsträckegräns.
De publika analyserna har därför exakt nio segment för 75 km och fyra för 35 km. Sista segmentet är
alltid Västra Bodarna–Mål och räknas direkt mellan dessa två officiella analysgränser. Råtid vid
Nolhaga och Mål bevaras oförändrad för en eventuell framtida, separat funktion ”Snabbaste spurten”.

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

CourseVersion `course-v1` deklarerar GPX-källor, checkpointkatalog, segment och explicita route-ankare
i `config/races.json`. Bygget snappar koordinatankare till GPX, verifierar monoton geometri och gör
styckvis linjär mapping mellan valfritt antal ankare. Ingen generell kod tolkar ortnamn eller distans.

Checkpoints exporterar tre skilda avstånd:

- `nominal_cumulative_km` från loppets källmodell;
- `race_distance_km` relativt respektive start;
- `route_distance_km` absolut längs officiell GPX från Göteborg.

Gotaledens nuvarande konfiguration har ett geografiskt verifierat ankare vid kortloppets start samt
explicita start-/slutankare. Editionernas `route_range` väljer neutralt vilken del av CourseVersion
som används.

## Bygg och uppdatera

Den publika snapshoten finns incheckad för reproducerbara byggen. En ny snapshot hämtas uttryckligen:

```bash
python tools/fetch_eqtiming_public.py --source-event eqtiming-gotaleden-2026 --refresh
python tools/build_project_data.py
```

Bygget skapar SQLite-databasen, den årneutrala webbexporten `docs/data/results.json` och diagnostik
under `reports/`. `results-2026.json` och `import-summary-2026.json` skrivs tills vidare som
byte-identiska kompatibilitetsalias.

### Race-katalogens kontrakt

`config/races.json` skiljer på ett stabilt `event_key`, en stabil `race_family` och varje faktisk
race edition med oförändrat `race_key`, `year`, `race_date` och `course_version`. `course_version`
är ett stabilt, event-lokalt id för den banmodell som editionen använder; nuvarande modell heter
`course-v1`. Fälten är explicita och får inte härledas från race key, distans eller ortnamn.

Samma metadata följer oförändrad genom SQLite-tabellerna `course_versions`/`races` och webbexportens
course-katalog/race-poster. Fingerprinten täcker materiell route-/höjdgeometri, checkpointkatalog,
ankare och segment. Samma versions-id är immutable: materiell geometriändring kräver en ny
`course_version`.
Samma family och version är `exact`; olika versioner är endast `compatible` via en explicit gemensam
whole-course comparison group. Segment över versioner kräver motsvarande explicit comparison key.

Kanoniska browserassets ligger i `docs/data/courses/<course-version>/route.json` och
`elevation.json`. Frontend laddar och cachear bara vald editions CourseVersion. `route.json` och
`route-elevation-2026.json` finns kvar som kompatibilitetsalias men är inte generisk source of truth.

`GDataAdapter.race()` exponerar den som `key`, `eventKey`, `family`, `year`, `raceDate`,
`courseVersion` och `type`. Eventets toppnivå beskriver eventet; editionens år och datum kommer
alltid från respektive race-post.

Varje edition har dessutom explicit `data_status`: `available` kräver en provider-neutral
`source_binding`, medan `planned` får finnas i katalogen utan källa och exponeras då som icke
analyserbar. Bygget grupperar tillgängliga editions per `(provider, source_event)` och kör varje
source-event exakt en gång via sin adapter.

Ett resultat är en edition-bunden appearance och skiljs från canonical person. `person_key` är
deterministisk och skapas från en uttryckligt namespacad external identity. External IDs deklarerar
scope (`race_edition`, `source_event` eller `provider`) och evidens; namn eller demografi auto-mergar
aldrig personer. Utan verifierat ID blir identiteten edition-lokal. Motstridiga verifierade IDs failar
i stället för att tyst mergeas. Nuvarande EQ Timing contestant UID är konservativt `source_event`-
scopat eftersom stabilitet mellan event inte är verifierad. Lag med samma namn hålls edition-lokala.

`GHistoryEngine` bygger kronologiska RaceFamily-serier direkt ovanpå `GDataAdapter`. Saknade år får
ingen syntetisk datapunkt. Deltagande/status kan sammanfattas över banbyten, medan sluttids- och
segmentjämförelser kräver explicit CourseVersion-/segmentjämförbarhet. Personhistorik använder endast
exakt canonical `person_key`; identity match och tillåten performancejämförelse är separata beslut.

## Analyswebb

Den statiska GitHub Pages-sidan i `docs/` innehåller:

- loppöversikt, måltidsfördelning, medianfart och global filtrering;
- placeringsmotor, måltidssimulator, DNF-flöde, pacing och avancemang;
- genus-, delsträcke-, percentil-, fältflödes- och klubbanalys;
- sökbar och sorterbar resultatdatabas;
- individ- och lagprofiler med officiella passeringar, relativa prestationer och pacingprofil;
- Loppets utveckling med checkpointbaserad gapgraf, officiell placeringsresa och pacing-fingeravtryck mot en stabil komplett referenskohort;
- Banans svårighetsprofil med GPX-baserad klättring, farttapp, spridningsband och officiell placeringsrörelse för alla 9/4 analytiska segment;
- animerad Runner Replay med musik, zoom, startläge och tydligt märkt interpolation;
- Kartduell med musik för 2–5 löpare eller lag, öppnad som en stor modal i analysen;
- Head-to-head för exakt två löpare eller lag med direkta checkpointluckor, segmentduell,
  officiell placeringsresa, gemensam fältpacing, kart-/höjdkontext och delningsbar länk;
- lokalt sparade favoriter för löpare och stafettlag med snabbval till Head-to-head och Kartduell;
- `karta.html` som bakåtkompatibel standalone-vy för direkta och delade kartlänkar;
- höjdprofil längs samma officiella `route_distance_km` som replay.
- omfattande `(i)`-metodhjälp för alla analytiska komponenter.

Den gemensamma metodhjälpen fungerar i både statiska och dynamiskt renderade analyser. Varje `(i)`
förklarar komponentens syfte, exakta metod, datakälla, kohort, tolkning och materiella begränsningar.
Favoriter lagras endast lokalt i den aktuella webbläsaren som publika resultat-ID:n.

Runner Replay och Kartduell använder en gemensam, lokalt vendrad Leaflet 1.9.4-motor med
OpenStreetMap-rutor. Ett förenklat SVG-läge finns enbart som reserv om Leaflet inte kan starta.
Den inkluderade musikfilen används av båda uppspelningarna. Vid automatisk målgång stannar
animationen medan musiken fortsätter att loopa tills den stängs av, återställs eller respektive
popup stängs.

Stafettvyerna analyserar lagets checkpointserie. Lagmedlemmar visas endast som medlemslista och
kopplas inte till en viss etapp i publikt UI.

Journey-analyserna använder endast verkliga analytiska passager. Gap och pacing jämförs mot samma
kompletta FINISHED-kohort vid samtliga checkpoints; saknade observationer fylls aldrig ut och DNF
stannar vid sista verkliga passage. Diagram- och segmentklick söker Runner Replay utan att starta
animation eller musik.

Banprofilens pacefördelningar använder samma kompletta FINISHED-kohort i varje segment. Median visas
från fem observationer, Q25–Q75 från tio och Q10–Q90 i detalj från tjugo. Höjdmetrik kommer från den
normaliserade referensprofilen längs officiell GPX. Analysen är flerdimensionell och gör ingen teknisk
stigklassificering eller sammanslagen svårighetspoäng.

Frontendens dataadapter matar en gemensam analys- och kartmotor för alla fyra loppen. Navigering,
analysdjup, profilflöde och kartkomponenter följer systerproduktens etablerade struktur, medan texter,
data, rutt och den ljusa västkustidentiteten är Gotaledens egna. Flerårssektioner är avsiktligt
inaktiva under premiäråret 2026.

## Adding another event

Den generella kärnan är eventneutral. Ett nytt running-event definierar eventmetadata och branding,
RaceFamilies/RaceEditions, CourseVersions, participant-/competition-/class-kontrakt samt capabilities
i config/data. Tillgängliga editions kopplas till en provider-neutral source binding och befintlig
provideradapter, eller en ny avgränsad adapter. Kör sedan build/validering och lägg kontrakts- samt
browserfall för eventets labels, course, individer/team, features och eventnamespacad lagring. Varken
eventnamn, race keys, distanser eller ortnamn ska läggas som routingregler i frontendkärnan.

## Tester

```bash
python -m unittest discover -s tests -v
```

Browserflöden körs mot den verkliga statiska sidan med Playwright:

```bash
pnpm install
pnpm run test:e2e:install
pnpm run test:e2e
```

Playwright startar själv en lokal statisk server för `docs/`. Installation av Chromium behöver bara
göras första gången eller när Playwright-versionen ändras.

Testerna verifierar bland annat fyra lopp, källintegritet, splitimport, Nolhagas roll, stafettregler,
rådata, GPX-slicing, elevation fallback, replay-ankare och att runner-to-leg inte visas publikt.

Kvalitetsrapporter:

- `reports/eqtiming-split-coverage.{json,md}`
- `reports/gpx-comparison.{json,md}`
