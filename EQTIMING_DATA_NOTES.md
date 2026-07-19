# EQ Timing — officiella filer för event 77906

## Källprioritet

1. `Resultlist-77906-20260719155435.csv` är primär resultatkälla. Den har 607 poster, alla fyra lopp
   och 22 fält, inklusive lagnamn och ordnade medlemspositioner för stafett.
2. `Startlist-77906-20260719155427.xml` är primär källa för stafettens etapp–löpare-relation.
3. Övriga `Resultlist`-filer används för korsvalidering.
4. `Startlist-77906-20260719155430.csv` används för kompletterande kontroll av startdata.
5. De fyra äldre 81-kolumnsfilerna används som fallback, för exakta start-/nettotider och för att
   bevara alla tidigare originalfält.

Alla källrader som används för ett resultat bevaras i SQLite `raw_json`. Originalfilerna ändras aldrig.

## Verifierad stafettkodning

För Stafett 75 avgränsas XML-poster med starttid `08:00:00`. För lagnummer `B` och etapp `L` gäller
`startno = L * 1000 + B`, med etapp 1–9.

För Stafett 35 avgränsas XML-poster med starttid `12:00:00`. För lagnummer `B` och etapp `L` gäller
`startno = B + L * 1000`, vilket innebär prefix 2–5 för etapp 1–4.

Starttiden är en obligatorisk del av identiteten eftersom samma numeriska XML-koder förekommer i
olika lopp. Mönstren verifieras över samtliga lag, inte från enstaka exempel. Resultatfilens tomma
medlemspositioner bevaras; listan komprimeras aldrig. Samma person kan därför kopplas till flera etapper.

Assignments får status `verified_xml_and_result_list` när XML och medlemspositionen överensstämmer,
`verified_xml` när bara XML ger ett namn, `missing` när XML saknar namn/post och `conflict` vid
motsägelse. `missing` och `conflict` får aldrig ett `athlete_id`.

## Kvarvarande datalucka

Ingen av de officiella filerna innehåller separata passager vid Skatås, Kåsjön, Jonsered, Lerum,
Floda, Tollered, Norsesund eller Västra Bodarna. De innehåller inte heller ackumulerad lagtids-passage,
faktisk etapptid eller placering efter varje stafettetapp. Endast befintliga målresultat lagras som
splits; inga mellantider fabriceras.

Detaljer finns i:

- `reports/eqtiming-files-analysis.json`
- `reports/relay-member-import-report.json`
- `reports/eqtiming-missing-data.json`
