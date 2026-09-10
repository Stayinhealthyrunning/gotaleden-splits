from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def rep(path_name, old, new, count=1):
    path = ROOT / path_name
    text = path.read_text(encoding="utf-8")
    found = text.count(old)
    if found != count:
        raise RuntimeError(f"{path_name}: expected {count}, found {found}: {old[:100]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


# Race UI: resolve official results from provider-neutral source metadata.
rep("docs/assets/race-ui.js",
    "const source=data?.meta?.event||data?.event||{};if(eventCache.has(source))return eventCache.get(source);",
    "const source=data?.meta?.event||data?.event||{},sourceEvents=data?.meta?.source_events||data?.source_events||{};if(eventCache.has(source))return eventCache.get(source);")
rep("docs/assets/race-ui.js",
    "presentation,helpContent:source.help_content||{},storageKey:suffix=>`${storageNamespace}:${suffix}`",
    "presentation,helpContent:source.help_content||{},sourceEvents,storageKey:suffix=>`${storageNamespace}:${suffix}`")
rep("docs/assets/race-ui.js",
    "const participant=source.participant||{},competition=source.competition||{},capabilities=source.capabilities||{},presentation=source.presentation||{},uiLabels=source.uiLabels||source.ui_labels||{},entity=participant.entity||'person',labels={singular:clean(participant.singular)||'deltagare',plural:clean(participant.plural)||'deltagare',profile:clean(participant.profile_label)||'DELTAGARANALYS',possessive:clean(participant.possessive)||'Deltagarens'},model={event:eventModel,race:source,entity,isTeam:entity==='team',labels,uiLabels,competition:",
    "const participant=source.participant||{},competition=source.competition||{},capabilities=source.capabilities||{},presentation=source.presentation||{},uiLabels=source.uiLabels||source.ui_labels||{},entity=participant.entity||'person',labels={singular:clean(participant.singular)||'deltagare',plural:clean(participant.plural)||'deltagare',profile:clean(participant.profile_label)||'DELTAGARANALYS',possessive:clean(participant.possessive)||'Deltagarens'},sourceEventKey=source.sourceEventKey||source.source_event_key||null,sourceEvent=eventModel?.sourceEvents?.[sourceEventKey]||{},sourceUrl=clean(source.officialUrl||source.official_url||sourceEvent.results_url||''),model={event:eventModel,race:source,entity,isTeam:entity==='team',labels,uiLabels,sourceEventKey,sourceUrl,competition:")
rep("docs/assets/race-ui.js",
    "route=document.querySelector('.hero__route');",
    "route=document.querySelector('.hero__route'),sourceLink=document.getElementById('source-link');")
rep("docs/assets/race-ui.js",
    ").join('')}\n  }\n  function escapeHtml",
    ").join('')}if(sourceLink){sourceLink.hidden=!model.sourceUrl;if(model.sourceUrl){sourceLink.href=model.sourceUrl;sourceLink.textContent=model.uiLabels?.source_results||'Officiella resultat ↗'}else sourceLink.removeAttribute('href')}\n  }\n  function escapeHtml")

# Static shell: no event/provider/participant-format assumptions.
rep("docs/index.html",
    '<p class="eyebrow ink">INDIVIDUELL LOPPANALYS</p>',
    '<p class="eyebrow ink" id="lookup-eyebrow">DELTAGARANALYS</p>')
rep("docs/index.html",
    'Kartduell jämför två till fem löpare eller lag på banan. För analys av en enda deltagare använder du Löpare/Lag-analysen och Runner Replay.',
    'Kartduell jämför två till fem deltagare på banan. För analys av en enda deltagare använder du deltagaranalysen och Replay.')
rep("docs/index.html",
    '<a class="source-link" id="source-link" href="https://live.eqtiming.com/77906" target="_blank" rel="noopener">Officiella resultat ↗</a>',
    '<a class="source-link" id="source-link" href="#" target="_blank" rel="noopener" hidden>Officiella resultat ↗</a>')

# App: team is an entity model, not a synonym for relay/stafett.
rep("docs/assets/app.js",
    "$('#lookup-title').textContent=ui.uiLabels.lookup_title||`Analysera ${ui.labels.singular}`;",
    "$('#lookup-eyebrow').textContent=ui.uiLabels.lookup_eyebrow||ui.labels.profile;$('#lookup-title').textContent=ui.uiLabels.lookup_title||`Analysera ${ui.labels.singular}`;")
rep("docs/assets/app.js", ",relayFacts=`", ",teamFacts=`")
rep("docs/assets/app.js", "${race.isTeam?relayFacts:individualFacts}", "${race.isTeam?teamFacts:individualFacts}")
rep("docs/assets/app.js", "<small>Publicerad lagtid</small>", "<small>${esc(teamLabel(race,'finish_time_copy','Publicerad sluttid'))}</small>")
rep("docs/assets/app.js", "<span>Lagklass</span>", "<span>${esc(teamLabel(race,'class','Klass'))}</span>")
rep("docs/assets/app.js", "<small>av fullföljande lag i samma klass</small>", "<small>${esc(teamLabel(race,'class_percentile_copy','av fullföljande '+(race.participant?.plural||'deltagare')+' i samma '+teamLabel(race,'class','klass').toLocaleLowerCase('sv')))}</small>")
rep("docs/assets/app.js", "<small>av fullföljande lag</small>", "<small>${esc(teamLabel(race,'field_percentile_copy','av fullföljande '+(race.participant?.plural||'deltagare')))}</small>")
rep("docs/assets/app.js", "<span>Lagmedlemmar</span>", "<span>${esc(teamLabel(race,'members','Medlemmar'))}</span>")
rep("docs/assets/app.js", "<small>ingen koppling till etapper</small>", "<small>${esc(teamLabel(race,'member_count_copy','ingen koppling till delsträckor'))}</small>")
rep("docs/assets/app.js", "<h3>${race.isTeam?'Relativt egen klass':'Relativt fältet'}</h3>", "<h3>${race.isTeam?'Relativt '+esc(teamLabel(race,'class_reference','min klass').toLocaleLowerCase('sv')):'Relativt fältet'}</h3>")
rep("docs/assets/app.js", "<th>${race.isTeam&&!relayMeta.ranked?'Analytisk ordning':'Klassplats'}</th>", "<th>${race.isTeam&&!relayMeta.ranked?'Analytisk ordning':race.isTeam?esc(teamLabel(race,'class_place','Klassplats')):'Klassplats'}</th>")

# Adapter: presentation labels are config-driven for arbitrary team formats.
rep("docs/assets/data-adapter.js", "label:raceValue.isTeam?'Lagklass':'Klass'", "label:raceValue.isTeam?(raceValue.uiLabels.class||'Klass'):'Klass'")
rep("docs/assets/data-adapter.js", "message:raceValue.isTeam?'Könsplacering används inte för lag':'Placering saknas'", "message:raceValue.isTeam?`Könsplacering används inte för ${raceValue.participant.plural}`:'Placering saknas'")

# Preserve Gotaleden-specific wording in event configuration, not generic runtime.
rep("config/races.json",
    '"ui_labels": {"navigation": "Löpare", "saved": "Sparade löpare",',
    '"ui_labels": {"lookup_eyebrow": "INDIVIDUELL LOPPANALYS", "navigation": "Löpare", "saved": "Sparade löpare",')
rep("config/races.json",
    '"members": "Lagmedlemmar", "member_assignment_copy": "Medlemslistan anger inte vem som sprang en viss etapp."',
    '"members": "Lagmedlemmar", "finish_time_copy": "Publicerad lagtid", "class_percentile_copy": "av fullföljande lag i samma klass", "field_percentile_copy": "av fullföljande lag", "member_count_copy": "ingen koppling till etapper", "member_assignment_copy": "Medlemslistan anger inte vem som sprang en viss etapp."')

# Alternate event: prove an unrelated source URL and Duo wording through the real UI path.
rep("tests/fixtures/alternate-event.js",
    "const data={meta:{event},courses:{},race_catalog:{},races:{},checkpoints:{},splits:[],teams:[],team_members:[]}",
    "const data={meta:{event,source_events:{'fixture-source':{provider:'fixture',results_url:'https://example.test/coast/results'}}},courses:{},race_catalog:{},races:{},checkpoints:{},splits:[],teams:[],team_members:[]}")
rep("tests/fixtures/alternate-event.js",
    "ui_labels:{navigation:team?'Duos':'Runners'",
    "ui_labels:{lookup_eyebrow:team?'DUO ANALYSIS':'RUNNER ANALYSIS',navigation:team?'Duos':'Runners'")
rep("e2e/app.spec.js",
    "await expect(page.getByRole('heading',{name:'Coast Trail Explorer'})).toBeVisible();await expect(page.locator('#race-switch [role=\"tab\"]')).toHaveCount(4);",
    "await expect(page.getByRole('heading',{name:'Coast Trail Explorer'})).toBeVisible();await expect(page.locator('#source-link')).toHaveAttribute('href','https://example.test/coast/results');await expect(page.locator('#race-switch [role=\"tab\"]')).toHaveCount(4);")
rep("e2e/app.spec.js",
    "await expect(page.locator('#detail-dialog')).toContainText('DUO ANALYSIS');await page.locator('#detail-dialog .dialog-close').click();",
    "await expect(page.locator('#detail-dialog')).toContainText('DUO ANALYSIS');const duoDetailText=await page.locator('#detail-dialog').innerText();for(const forbidden of ['lagtid','Lagklass','Lagmedlemmar','stafett','Stafett'])expect(duoDetailText).not.toContain(forbidden);await page.locator('#detail-dialog .dialog-close').click();")

# Regression gates: these leaks must not return to generic runtime/static shell.
rep("tests/test_event_portability.py",
    '"62 km", "alingsas", "floda", "gothenburg", "skatas", "nolhaga", "tollered"):',
    '"62 km", "alingsas", "floda", "gothenburg", "skatas", "nolhaga", "tollered", "Publicerad lagtid", "Lagklass", "Lagmedlemmar", "stafettfältet", "stafettens officiella"):' )
rep("tests/test_event_portability.py",
    '        self.assertNotIn("isRelay", central_ui)\n',
    '        self.assertNotIn("isRelay", central_ui)\n        html = (ROOT / "docs/index.html").read_text(encoding="utf-8")\n        self.assertNotIn("live.eqtiming.com", html)\n')
rep("tests/test_event_portability.py",
    "console.log(JSON.stringify({isTeam:duo.isTeam,isRelay:duo.isRelay,format:duo.competitionFormat,field:adapter.referenceProfiles(first).field.label,classReference:adapter.referenceProfiles(first).class.label,finish:head.checkpoints.at(-1).checkpoint,finishName:head.checkpoints.at(-1).name,place:head.checkpoints.at(-1).placeA}));",
    "const duoUi=window.GRaceUI.race(duo,eventUi);console.log(JSON.stringify({isTeam:duo.isTeam,isRelay:duo.isRelay,format:duo.competitionFormat,field:adapter.referenceProfiles(first).field.label,classReference:adapter.referenceProfiles(first).class.label,finish:head.checkpoints.at(-1).checkpoint,finishName:head.checkpoints.at(-1).name,place:head.checkpoints.at(-1).placeA,sourceUrl:duoUi.sourceUrl}));")
rep("tests/test_event_portability.py",
    '        self.assertEqual(result["place"], 1)\n',
    '        self.assertEqual(result["place"], 1)\n        self.assertEqual(result["sourceUrl"], "https://example.test/coast/results")\n')

# Do not leave one-shot machinery in the product branch.
(ROOT / ".github/workflows/one-shot-portability-cleanup.yml").unlink(missing_ok=True)
Path(__file__).unlink(missing_ok=True)
