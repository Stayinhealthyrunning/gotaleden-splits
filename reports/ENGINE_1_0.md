# Loppanalys Engine 1.0 – fryst semantiskt kontrakt

## Beslut

Engine 1.0 är ett **gemensamt semantiskt gränssnitt**, inte ett krav på en gemensam fysisk JavaScript-kodbas. Det gör att Gotaleden och Ultravasan kan fortsätta fungera utan riskfylld omskrivning samtidigt som nästa lopp – Österlen Spring Trail – kan byggas mot ett stabilt kontrakt.

Den maskinläsbara normen är `config/engine-contract-v1.json`.

## Vad som kommer från Gotaleden

Gotaleden har redan verifierad portabilitet för ett helt annat event och framtida upplagor. Engine 1.0 behåller därför dess explicita modeller för:

- Event och event-scopad lagring.
- RaceEdition och RaceFamily med opaka nycklar.
- `participant.entity` = person/team.
- `competition.format` och teamstruktur.
- Capability-driven UI.
- CourseVersion och explicit jämförbarhet.
- Planerade/missing editions utan fabricerade nollor.

## Vad som kommer från Ultravasan

Ultravasans senare arkitektur skärper kontraktet med:

- strikt separation mellan RaceFamily och CourseVersion,
- route/geometry evidence skild från visningsgeometri,
- verifierad identitet före flerårig personhistorik,
- verkliga checkpoints kontra auxiliary/display-punkter,
- progressiv dataladdning active/core/full med semantisk paritet,
- flerårig history/course intelligence som endast jämför uttryckligen kompatibla data.

## Vad som inte standardiseras i 1.0

Följande får vara implementationsspecifikt:

- DOM-struktur och CSS,
- exakt modulindelning,
- diagramrenderare,
- source acquisition/import,
- SQLite-schema,
- event-specifik text/design,
- leverantörsspecifika fält.

Det är avsiktligt. Ett försök att samtidigt slå ihop båda befintliga frontendkodbaserna skulle öka regressionsrisken utan att vara nödvändigt för ÖST.

## Capability-regeln

En funktion visas bara när aktuell RaceEdition har tillräckligt källunderlag. Ett annat år eller en annan distans får aldrig låna data för att aktivera funktionen.

Särskilt gäller:

- segmentanalys kräver verkliga observerade analysgränser,
- replay kräver verkliga timingankare **och** lokalt användbar rutt,
- course history kräver explicit banjämförbarhet,
- person history kräver verifierad/confidence-bearing identitetslänkning,
- team members innebär inte automatiskt verifierad etapptilldelning.

## Konsekvens för Gotaleden

Ingen stor frontendmigrering krävs. Gotaledens portabilitetsmodell ligger nära Engine 1.0 och fungerar som referens för event/competition/capabilities. Senare Ultravasan-UX ska bara synkas när samma funktion och databetydelse finns.

## Konsekvens för Ultravasan

Ingen riskfylld omskrivning krävs före ÖST. Ultravasan fungerar som referens för modular loading, route evidence, identity/history och de senare analysmodulerna. En framtida intern adapter kan exponera Engine 1.0-formen utan att ändra den verifierade legacy-/modular-dataexporten.

## Konsekvens för ÖST

ÖST ska konsumera sin redan kuraterade databas via en adapter till Engine 1.0. Sportstiming ska inte crawlas om. Feature availability ska komma från den befintliga readiness-matrisen och banversionerna från ÖST:s evidensmodell.

Det första integrationsmålet är inte full funktionsparitet för alla distanser. Det är korrekt capability-driven rendering för varje RaceEdition.
