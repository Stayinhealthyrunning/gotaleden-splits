# EQ Timing — nuläge och nästa datasteg

## Importerat vid projektstart

Fyra officiellt nedladdade CSV-filer från EQ Timing:

- Ultra 75 km
- Sprint 35 km
- Stafett 75 km
- Stafett 35 km

Samtliga 81 kolumner bevaras i råfilerna och i `raw_json`/`raw` i processad data.

## Bekräftad begränsning

De fyra startfilerna innehåller endast `PointName = Mål`. De ger därför:

- deltagare/lag
- startnummer
- lopp och klass
- status
- sluttid
- placeringar
- starttid/måltid
- övriga 81 exportfält

men inte separata rader för Skatås, Kåsjön, Jonsered, Lerum, Floda, Tollered, Norsesund eller Västra Bodarna.

## Stafett

Stafettfilernas `NameFormatted` är lagnamnet.
`Firstname` och `Surname` lagras försiktigt som `listed_contact_name`.
De får inte tolkas som säker etapptilldelning.

## Nästa tekniska undersökning

1. Identifiera EQ Timings publika JSON/XHR-anrop bakom `https://live.eqtiming.com/77906`.
2. Hämta minst en komplett individprofil med alla passager.
3. Hämta minst ett komplett stafettlag med alla lagpassager.
4. Kontrollera om publika data exponerar:
   - lagmedlemmar,
   - vem som sprang vilken etapp,
   - etapptid kontra ackumulerad tid,
   - placering per etapp.
5. Spara råpayload oförändrad innan normalisering.

Ingen mellanpassage ska uppskattas eller fabriceras i databasen.
