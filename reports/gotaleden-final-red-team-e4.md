# E4 – final red-team / freeze audit

Datum: 2026-09-12. Auditerad bas: `c6ad6a578cf2059b15f563f71e0e2994b624ed4d` (`origin/main`, E3/PR #37 mergad). Granskningen gjordes före ändring; nedanstående P1–P2 reproducerades med fallande regressionstester före minsta korrigering.

## Omfattning och fynd

Kedjan rå EQ Timing → source binding/import → SQLite → webbexport → adapter → analyser/UI granskades med oberoende SQL-/JSON-beräkningar, kontraktsmutationer och verklig Chromium. DNF/DNS, Nolhaga, kohorter, percentiler, kvantiler, pacing, Måltempo, Course Difficulty, identitet, CourseVersion/historik, lag/Duo, filter, URL/storage, tangentbord/mobil, lifecycle, atomisk writer, externa länkar och eventneutralitet ingick. En andra pass gick igenom fallback/legacy/TODO, finalsegment, ties och missing-värden.

| Klass | Reproduktion och kodväg | Konsekvens och minsta fix |
| --- | --- | --- |
| P0 | Inget verifierat. | Ingen rådata-/CourseVersion-korrigering. |
| P1 | Verkliga DNS-bib 782 och 519 i Individuellt 75 har vardera en bevarad sen chip-observation vid Mål. `GDataAdapter.profile()` behandlade den som progression från start till mål. | Replay/placering såg ut som ett genomfört lopp trots DNS. Statusstyrd avgränsning av profilens analytiska observationer; råspliten bevaras oförändrad. Testet kontrollerar både bevarad källa och frånvaro av progression. |
| P1 | Syntetisk event-/checkpoint-/klasscopy med `<img onerror>` gav tre faktiska DOM-element i profilen/simulatorn före fix. Vägen var interpolering av konfig-/source-strängar i `innerHTML`. | Möjlig scriptkörning i statisk publicerad data. Escape vid de verifierade renderingsställena i app, personlig sammanfattning och Replay. Browserregression verifierar att markup inte skapas eller exekveras. |
| P2 | Alternate Duo (`isTeam=true`, `isRelay=false`) med avsiktligt förgiftad `person_key` dök upp som personhistorik; sexfilter kunde felaktigt tillämpas. `history-engine.js` använde `isRelay` för entity-semantik. | Lag kunde framstå som verifierad person. Bytt till `isTeam` för personindex, filter och jämförelser. Riktat beteendetest. |
| P2 | Generiska `GAppState.parse()` innehöll fortfarande default `individual-75-2026` trots configdrivet explicit default i appen. | Modulens fristående fallback läckte eventedition. Neutral `null`-default; befintliga deep links/fallback från appen bibehålls. |
| P3, accepterat | `Snabbare än` avrundar 205/206 till `100 %` för snabbaste 75 km-löparen trots att det matematiska värdet är 99,51 %. Hjälpcopy anger avrundat andelsmått. | Ingen metodändring i freeze-audit; exakt antal vore framtida copyförfining. |
| Inte fel | En DNF kan ha en sen rå Mål-observation (t.ex. bib 599), och en annan enbart Mål (relay 35 bib 1026). | Källbevis bevaras; FINISHED-kohort, Journey/H2H och Replay får inte konstruera framtida officiell placering eller komplett analysprofil. |

## Oberoende matematiska stickprov

Beräkningarna nedan gjordes direkt från SQLite-observationer/GPX-distanser och jämfördes med adapter/visad metod; tider i sekunder, tempo i s/km. Nolhaga är en timing-/Replay-observation, inte en analytisk gräns: 75 km har nio och 35 km fyra segment.

| Verkligt exempel | Oberoende kontroll |
| --- | --- |
| Individuellt 75, bib 717 Anton Gustafsson | FINISHED 19 441,4 s, totalplats 1. Första segmentet 1 050,9 s / 4,4819 km = 234,48 s/km. Nio fullständiga analyssegment. |
| Individuellt 75, bib 579 Robert Boldt | FINISHED 36 511,5 s, plats 104. Första segmentet 1 680,97 s / 4,4819 km = 375,06 s/km. Strikt snabbare än 103 av 206 fullföljande = 50 %. |
| Individuellt 75, bib 558 | FINISHED 47 388,3 s, plats 206; strikt snabbare än 0/206 = 0 %. Bib 648/637 delar exakt 40 129,9 s; lika tid räknas inte som strikt slagen. |
| Individuellt 35, bib 1630 Daniel Norin | FINISHED 10 007,1 s. Första 35-segmentet 1 986,34 s / 7,8436 km = 253,24 s/km; fyra segment från Floda, ingen 75-kontaminering. |
| Stafett 75, bib 41 Hälle IF | Lagets FINISHED-tid 18 901,2 s. Första segmentet 956,81 s / 4,4819 km = 213,48 s/km, inte medlems-/löparpace. |
| Stafett 75, bib 7 | Ej rankad Mixed: FINISHED 28 109,4 s, fältmedian; 50 % enligt strikt fältandel, ingen påhittad klassplacering. |
| Stafett 35, bib 1010 Lalarunt | FINISHED 9 057,3 s. Första segmentet 2 115,66 s / 7,8436 km = 269,73 s/km. |
| DNF/DNS | DNF bib 599 har verkliga observationer till Floda och sen rå Mål-notering, men ingen syntetisk framtida analyssträcka. DNS bib 782/519 har en rå Mål-notering vardera men noll analytisk progression efter fix. |

Komplett FINISHED-kohort för analyssegment är 205/127/94/43 (i75/i35/r75/r35), inte samtliga 206/127/109/45 fullföljande. Handräknade i75-segmentmedianer (s/km): 392,37; 430,12; 427,63; 462,26; 465,02; 522,63; 480,66; 541,83; 478,36. Median sluttid i respektive race: 36 500,15 / 14 920,7 / 28 109,4 / 13 543,0 s. En empirisk i75-Måltempo på 10 h fördelas 1 753 + 4 483 + 3 184 + 4 589 + 4 154 + 4 086 + 5 636 + 3 441 + 4 674 = exakt 36 000 s; fallback är endast jämnt distanstempo och copy säger det. Q25/Q75, histogram, grupper och filter kontrollerades mot stabil komplett kohort och relevanta riktade regressioner; ingen ytterligare mismatch verifierades.

## Negativa kontrakt, integritet och QA

- Befintliga riktade mutationstester prövade source-config, konflikter i verifierade identiteter, namn/bib utan identitetsmerge, CourseVersion-geometri och LF/CRLF, explicita course-/segmentjämförelser, planned/otillgängliga editions, saknade segment och ofullständiga Måltempo-profiler. Okända/saknade observationer fabriceras inte. Lagmedlemmar utan verifierad etapptilldelning tillskrivs ingen etapp. EQ Timing-konflikter blir `conflict`, inte verifierad person. Atomisk writer: same-directory temp, UTF-8, stängning före `os.replace`, högst fem korta Windows-försök, ingen POSIX-retry och cleanup även vid fel. Full rebuild-idempotens körs i `test_project_data`.
- Full Python: 277/277; full Playwright/Chromium: 17/17. Node `--check`: 24/24 publika JS-assets. `git diff --check`: utan fel. Playwright använder en worker på Windows på grund av kall testservers backlog, inte för att dölja assertions; normala timeoutar gäller. E2E prövar fyra race, profil, Måltempo, H2H, Kartduell/direktlänk, Replay, historik, filter/tomläge, keyboard/fokus, back/forward, 390 px samt annat event med Duo. Ingen relevant page/console error. Separat Windows-datorstyrning timeoutade vid appanslutning; denna verifiering bygger på verklig automatiserad Chromium, inte ytterligare manuell UI-session.
- Canonical data: 607 resultat, 4 059 splits, per race 274/163/121/49; status 206/13/55, 127/2/34, 109/1/11, 45/1/3 (FINISHED/DNF/DNS). Inga duplicerade scoped resultat/checkpoint-splits eller icke-positiva passager. Alla 12 skyddade EQ Timing-sourcefiler bytehashade via `test_project_data`; officiell GPX oförändrad. `course-v1` fingerprint `ba79f364dc99c9ef939c4325a10682e562324a5a1e40ae66aec3bfea6a7fc668`. Publik JSON jämfördes rekursivt mot HEAD utan en enda semantisk skillnad efter rebuild. Genererad SQLite/JSON-churn tas inte med i E4-commit.
- [Officiell eventlänk](https://www.gotaledenstafettultra.se/) och [EQ Timing-källa](https://live.eqtiming.com/77906) svarar. Sociala Instagram/YouTube-länkar finns med säkra externa `rel`-attribut; deras åtkomlighet kunde inte bekräftas med webbverktyget. Canonical/deep links och standalone-karta prövades i Chromium.

Kända begränsningar: 2026 är enda tillgängliga resultatåret; 2027 är annonserat men saknar resultat. Olika CourseVersions jämförs inte i performance utan explicit jämförbarhet. Ofullständiga officiella passager ger inget komplett segmentmått. Interpolerad kartanimation är märkt uppskattad, inte officiell observation. Resultatdata och råa källmotsägelser korrigeras inte automatiskt.

## Freeze-beslut

Ingen känd kvarvarande P0/P1 eller freeze-värd P2 efter de riktade fixarna; en accepterad avrundnings-P3 och öppet redovisade databegränsningar återstår. Canonical data och CourseVersion är oförändrade; matematik har oberoende stickprovskontrollerats. Den generiska kärnan kan bära Österlen Spring Trail genom config/data/course/provideradapter utan kopiering av Gotaleden-specifik analyskod. **Freeze recommendation: YES**, förutsatt att PR:ns CI förblir grön och PR granskas innan merge.
