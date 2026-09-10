from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_exact(relative: str, old: str, new: str, expected: int = 1) -> None:
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"{relative}: expected {expected} occurrence(s), found {count}: {old[:120]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


# 1) Race UI owns provider-neutral source/result links and lookup presentation.
replace_exact(
    "docs/assets/race-ui.js",
    "const source=data?.meta?.event||data?.event||{};if(eventCache.has(source))return eventCache.get(source);",
    "const source=data?.meta?.event||data?.event||{},sourceEvents=data?.meta?.source_events||data?.source_events||{};if(eventCache.has(source))return eventCache.get(source);",
)
replace_exact(
    "docs/assets/race-ui.js",
    "presentation,helpContent:source.help_content||{},storageKey:suffix=>`${storageNamespace}:${suffix}`",
    "presentation,helpContent:source.help_content||{},sourceEvents,storageKey:suffix=>`${storageNamespace}:${suffix}`",
)
replace_exact(
    "docs/assets/race-ui.js",
    "const participant=source.participant||{},competition=source.competition||{},capabilities=source.capabilities||{},presentation=source.presentation||{},uiLabels=source.uiLabels||source.ui_labels||{},entity=participant.entity||'person',labels={singular:clean(participant.singular)||'deltagare',plural:clean(participant.plural)||'deltagare',profile:clean(participant.profile_label)||'DELTAGARANALYS',possessive:clean(participant.possessive)||'Deltagarens'},model={event:eventModel,race:source,entity,isTeam:entity==='team',labels,uiLabels,competition:{format:clean(competition.format)||'race',teamStructure:competition.team_structure||{kind:'none',member_assignment:'unknown'}},capabilities,presentation,can:key=>capabilities[key]===true,distanceLabel:clean(presentation.distance_label)||`${Number(source.distanceKm||source.gpx_distance_km||0).toLocaleString('sv-SE')} km`,finishLabel:clean(presentation.finish_label)||source.analysisCheckpoints?.at(-1)?.name||source.checkpoints?.at(-1)?.name||'Mål'};",
    "const participant=source.participant||{},competition=source.competition||{},capabilities=source.capabilities||{},presentation=source.presentation||{},uiLabels=source.uiLabels||source.ui_labels||{},entity=participant.entity||'person',labels={singular:clean(participant.singular)||'deltagare',plural:clean(participant.plural)||'deltagare',profile:clean(participant.profile_label)||'DELTAGARANALYS',possessive:clean(participant.possessive)||'Deltagarens'},sourceEventKey=source.sourceEventKey||source.source_event_key||null,sourceEvent=eventModel?.sourceEvents?.[sourceEventKey]||{},sourceUrl=clean(source.officialUrl||source.official_url||sourceEvent.results_url||''),model={event:eventModel,race:source,entity,isTeam:entity==='team',labels,uiLabels,sourceEventKey,sourceUrl,competition:{format:clean(competition.format)||'race',teamStructure:competition.team_structure||{kind:'none',member_assignment:'unknown'}},capabilities,presentation,can:key=>capabilities[key]===true,distanceLabel:clean(presentation.distance_label)||`${Number(source.distanceKm||source.gpx_distance_km||0).toLocaleString('sv-SE')} km`,finishLabel:clean(presentation.finish_label)||source.analysisCheckpoints?.at(-1)?.name||source.checkpoints?.at(-1)?.name||'Mål'};",
)
replace_exact(
    "docs/assets/race-ui.js",
    "const eyebrow=document.getElementById('hero-eyebrow'),route=document.querySelector('.hero__route');if(eyebrow)eyebrow.textContent=model.presentation.hero_eyebrow||'';if(route){const stops=model.presentation.route_stops||[];route.setAttribute('aria-label',model.presentation.route_aria_label||'Banans platser');route.innerHTML=stops.map((stop,index)=>`${index?'<i aria-hidden=\"true\"></i>':''}<span class=\"route-stop-${stop.role||'course'}\">${escapeHtml(stop.label)}</span>`).join('')}\n",
    "const eyebrow=document.getElementById('hero-eyebrow'),route=document.querySelector('.hero__route'),sourceLink=document.getElementById('source-link');if(eyebrow)eyebrow.textContent=model.presentation.hero_eyebrow||'';if(route){const stops=model.presentation.route_stops||[];route.setAttribute('aria-label',model.presentation.route_aria_label||'Banans platser');route.innerHTML=stops.map((stop,index)=>`${index?'<i aria-hidden=\"true\"></i>':''}<span class=\"route-stop-${stop.role||'course'}\">${escapeHtml(stop.label)}</span>`).join('')}if(sourceLink){sourceLink.hidden=!model.sourceUrl;if(model.sourceUrl){sourceLink.href=model.sourceUrl;sourceLink.textContent=model.uiLabels?.source_results||'Officiella resultat ↗'}else sourceLink.removeAttribute('href')}\n",
)

# 2) Remove provider/event assumptions from the static shell.
replace_exact(
    "docs/index.html",
    '<p class="eyebrow ink">INDIVIDUELL LOPPANALYS</p>',
    '<p class="eyebrow ink" id="lookup-eyebrow">DELTAGARANALYS</p>',
)
replace_exact(
    "docs/index.html",
    'Kartduell jämför två till fem löpare eller lag på banan. För analys av en enda deltagare använder du Löpare/Lag-analysen och Runner Replay.',
    'Kartduell jämför två till fem deltagare på banan. För analys av en enda deltagare använder du deltagaranalysen och Replay.',
)
replace_exact(
    "docs/index.html",
    '<a class="source-link" id="source-link" href="https://live.eqtiming.com/77906" target="_blank" rel="noopener">Officiella resultat ↗</a>',
    '<a class="source-link" id="source-link" href="#" target="_blank" rel="noopener" hidden>Officiella resultat ↗</a>',
)

# 3) Team presentation must come from participant/config semantics, never from a relay synonym.
replace_exact(
    "docs/assets/app.js",
    "$('#lookup-title').textContent=ui.uiLabels.lookup_title||`Analysera ${ui.labels.singular}`;$('#lookup-copy').textContent=ui.uiLabels.lookup_copy||`Sök fram en ${ui.labels.singular} och öppna profilen.`;",
    "$('#lookup-eyebrow').textContent=ui.uiLabels.lookup_eyebrow||ui.labels.profile;$('#lookup-title').textContent=ui.uiLabels.lookup_title||`Analysera ${ui.labels.singular}`;$('#lookup-copy').textContent=ui.uiLabels.lookup_copy||`Sök fram en ${ui.labels.singular} och öppna profilen.`;",
)
replace_exact("docs/assets/app.js", ",relayFacts=`", ",teamFacts=`")
replace_exact("docs/assets/app.js", "${race.isTeam?relayFacts:individualFacts}", "${race.isTeam?teamFacts:individualFacts}")
replace_exact(
    "docs/assets/app.js",
    "<small>Publicerad lagtid</small>",
    "<small>${esc(teamLabel(race,'finish_time_copy','Publicerad sluttid'))}</small>",
)
replace_exact(
    "docs/assets/app.js",
    "<span>Lagklass</span>",
    "<span>${esc(teamLabel(race,'class','Klass'))}</span>",
)
replace_exact(
    "docs/assets/app.js",
    "<small>av fullföljande lag i samma klass</small>",
    "<small>${esc(teamLabel(race,'class_percentile_copy','av fullföljande '+(race.participant?.plural||'deltagare')+' i samma '+teamLabel(race,'class','klass').toLocaleLowerCase('sv')))}</small>",
)
replace_exact(
    "docs/assets/app.js",
    "<small>av fullföljande lag</small>",
    "<small>${esc(teamLabel(race,'field_percentile_copy','av fullföljande '+(race.participant?.plural||'deltagare')))}</small>",
)
replace_exact(
    "docs/assets/app.js",
    "<span>Lagmedlemmar</span>",
    "<span>${esc(teamLabel(race,'members','Medlemmar'))}</span>",
)
replace_exact(
    "docs/assets/app.js",
    "<small>ingen koppling till etapper</small>",
    "<small>${esc(teamLabel(race,'member_count_copy','ingen koppling till delsträckor'))}</small>",
)
replace_exact(
    "docs/assets/app.js",
    "<h3>${race.isTeam?'Relativt egen klass':'Relativt fältet'}</h3>",
    "<h3>${race.isTeam?'Relativt '+esc(teamLabel(race,'class_reference','min klass').toLocaleLowerCase('sv')):'Relativt fältet'}</h3>",
)
replace_exact(
    "docs/assets/app.js",
    "<th>${race.isTeam&&!relayMeta.ranked?'Analytisk ordning':'Klassplats'}</th>",
    "<th>${race.isTeam&&!relayMeta.ranked?'Analytisk ordning':race.isTeam?esc(teamLabel(race,'class_place','Klassplats')):'Klassplats'}</th>",
)

# 4) Adapter presentation labels are config-driven for all team formats, including Duo.
replace_exact(
    "docs/assets/data-adapter.js",
    "label:raceValue.isTeam?'Lagklass':'Klass'",
    "label:raceValue.isTeam?(raceValue.uiLabels.class||'Klass'):'Klass'",
)
replace_exact(
    "docs/assets/data-adapter.js",
    "message:raceValue.isTeam?'Könsplacering används inte för lag':'Placering saknas'",
    "message:raceValue.isTeam?`Könsplacering används inte för ${raceValue.participant.plural}`:'Placering saknas'",
)

# 5) The alternate event proves source-link resolution and non-relay team copy end-to-end.
replace_exact(
    "tests/fixtures/alternate-event.js",
    "const data={meta:{event},courses:{},race_catalog:{},races:{},checkpoints:{},splits:[],teams:[],team_members:[]}",
    "const data={meta:{event,source_events:{'fixture-source':{provider:'fixture',results_url:'https://example.test/coast/results'}}},courses:{},race_catalog:{},races:{},checkpoints:{},splits:[],teams:[],team_members:[]}",
)
replace_exact(
    "tests/fixtures/alternate-event.js",
    "ui_labels:{navigation:team?'Duos':'Runners'",
    "ui_labels:{lookup_eyebrow:team?'DUO ANALYSIS':'RUNNER ANALYSIS',navigation:team?'Duos':'Runners'",
)
replace_exact(
    "e2e/app.spec.js",
    "await expect(page.getByRole('heading',{name:'Coast Trail Explorer'})).toBeVisible();await expect(page.locator('#race-switch [role=\"tab\"]')).toHaveCount(4);",
    "await expect(page.getByRole('heading',{name:'Coast Trail Explorer'})).toBeVisible();await expect(page.locator('#source-link')).toHaveAttribute('href','https://example.test/coast/results');await expect(page.locator('#race-switch [role=\"tab\"]')).toHaveCount(4);",
)
replace_exact(
    "e2e/app.spec.js",
    "await expect(page.locator('#detail-dialog')).toBeVisible();await expect(page.locator('.detail-members span')).toHaveCount(2);await expect(page.locator('.detail-members .eyebrow')).toHaveText('DUO MEMBERS');await expect(page.locator('#detail-replay [data-map-engine]')).toBeVisible();await expect(page.locator('#detail-dialog')).toContainText('DUO ANALYSIS');await page.locator('#detail-dialog .dialog-close').click();",
    "await expect(page.locator('#detail-dialog')).toBeVisible();await expect(page.locator('.detail-members span')).toHaveCount(2);await expect(page.locator('.detail-members .eyebrow')).toHaveText('DUO MEMBERS');await expect(page.locator('#detail-replay [data-map-engine]')).toBeVisible();await expect(page.locator('#detail-dialog')).toContainText('DUO ANALYSIS');const duoDetailText=await page.locator('#detail-dialog').innerText();for(const forbidden of ['lagtid','Lagklass','Lagmedlemmar','stafett','Stafett'])expect(duoDetailText).not.toContain(forbidden);await page.locator('#detail-dialog .dialog-close').click();",
)

# 6) Strengthen regression guards around these exact portability leaks.
replace_exact(
    "tests/test_event_portability.py",
    '        for value in ("Gotaleden", "Göteborg", "Floda", "Alingsås", "Nolhaga", "Skatås", "Tollered", "EQ Timing", "route-35", "Coast Trail Lab", "long-solo-a", "62 km", "alingsas", "floda", "gothenburg", "skatas", "nolhaga", "tollered"):\n',
    '        for value in ("Gotaleden", "Göteborg", "Floda", "Alingsås", "Nolhaga", "Skatås", "Tollered", "EQ Timing", "route-35", "Coast Trail Lab", "long-solo-a", "62 km", "alingsas", "floda", "gothenburg", "skatas", "nolhaga", "tollered", "Publicerad lagtid", "Lagklass", "Lagmedlemmar", "stafettfältet", "stafettens officiella"):\n',
)
replace_exact(
    "tests/test_event_portability.py",
    '        self.assertNotIn("isRelay", central_ui)\n',
    '        self.assertNotIn("isRelay", central_ui)\n        html = (ROOT / "docs/index.html").read_text(encoding="utf-8")\n        self.assertNotIn("live.eqtiming.com", html)\n',
)
replace_exact(
    "tests/test_event_portability.py",
    "console.log(JSON.stringify({isTeam:duo.isTeam,isRelay:duo.isRelay,format:duo.competitionFormat,field:adapter.referenceProfiles(first).field.label,classReference:adapter.referenceProfiles(first).class.label,finish:head.checkpoints.at(-1).checkpoint,finishName:head.checkpoints.at(-1).name,place:head.checkpoints.at(-1).placeA}));",
    "const duoUi=window.GRaceUI.race(duo,eventUi);console.log(JSON.stringify({isTeam:duo.isTeam,isRelay:duo.isRelay,format:duo.competitionFormat,field:adapter.referenceProfiles(first).field.label,classReference:adapter.referenceProfiles(first).class.label,finish:head.checkpoints.at(-1).checkpoint,finishName:head.checkpoints.at(-1).name,place:head.checkpoints.at(-1).placeA,sourceUrl:duoUi.sourceUrl}));",
)
replace_exact(
    "tests/test_event_portability.py",
    '        self.assertEqual(result["place"], 1)\n',
    '        self.assertEqual(result["place"], 1)\n        self.assertEqual(result["sourceUrl"], "https://example.test/coast/results")\n',
)

# One-shot files remove themselves from the final product commit.
(ROOT / ".github/workflows/one-shot-portability-cleanup.yml").unlink(missing_ok=True)
Path(__file__).unlink(missing_ok=True)
