const {test,expect}=require('@playwright/test');
const {create: createFutureEditionFixture}=require('../tests/fixtures/future-edition.js');
const {create: createAlternateEventFixture}=require('../tests/fixtures/alternate-event.js');

function watchRelevantErrors(page){
  const errors=[];
  page.on('pageerror',error=>errors.push(`page: ${error.message}`));
  page.on('console',message=>{if(message.type()==='error'&&!message.text().includes('Failed to load resource'))errors.push(`console: ${message.text()}`)});
  page.on('response',response=>{const request=response.request(),local=response.url().startsWith('http://127.0.0.1:4173/');if(local&&response.status()>=400&&['document','script','fetch','xhr'].includes(request.resourceType()))errors.push(`${response.status()} ${response.url()}`)});
  return errors;
}

async function openSite(page,url='/?race=individual-75-2026&section=runner-lookup'){
  await page.goto(url);await expect(page.locator('#loading')).toHaveClass(/hidden/);await expect(page.locator('h1')).toBeVisible();
}

async function installFutureEditionFixture(page){
  const fixture=createFutureEditionFixture(),requests=[];
  await page.route('**/data/results.json**',route=>route.fulfill({contentType:'application/json',body:JSON.stringify(fixture.data)}));
  await page.route('**/data/test-courses/**',route=>{
    const path=new URL(route.request().url()).pathname.replace(/^\//,'');requests.push(path);
    const asset=fixture.assets[path];return asset?route.fulfill({contentType:'application/json',body:JSON.stringify(asset)}):route.continue();
  });
  return{fixture,requests};
}

async function installAlternateEventFixture(page){
  const fixture=createAlternateEventFixture();
  await page.route('**/data/results.json**',route=>route.fulfill({contentType:'application/json',body:JSON.stringify(fixture.data)}));
  await page.route('**/data/alternate/**',route=>{const path=new URL(route.request().url()).pathname.replace(/^\//,'').split('?')[0],asset=fixture.assets[path];return asset?route.fulfill({contentType:'application/json',body:JSON.stringify(asset)}):route.continue()});
  return fixture;
}

async function chooseDuelRunner(page,name){
  await page.locator('#duel-search').fill(name);await page.locator('#duel-suggestions [data-record-id]').filter({hasText:name}).first().click();
}

async function leafletHighlightVisual(course){
  return course.locator('[data-course-map] .route-range-highlight').evaluate(element=>{
    const map=element.closest('[data-course-map]').querySelector('.leaflet-map'),svg=element.ownerSVGElement,pane=element.closest('.route-segment-highlight-pane'),rect=node=>{const value=node.getBoundingClientRect();return{x:value.x,y:value.y,width:value.width,height:value.height,right:value.right,bottom:value.bottom}},overlaps=(a,b)=>a.right>b.x&&a.x<b.right&&a.bottom>b.y&&a.y<b.bottom,mapRect=rect(map),svgRect=rect(svg),pathRect=rect(element),style=getComputedStyle(element),svgStyle=getComputedStyle(svg),d=element.getAttribute('d')||'';
    return{stroke:style.stroke,strokeWidth:parseFloat(style.strokeWidth),paneZ:Number(getComputedStyle(pane).zIndex),mapRect,svgRect,pathRect,svgWidthAttribute:Number(svg.getAttribute('width')),svgHeightAttribute:Number(svg.getAttribute('height')),svgComputedWidth:svgStyle.width,svgComputedHeight:svgStyle.height,svgMaxHeight:svgStyle.maxHeight,rendererOverlapsMap:overlaps(svgRect,mapRect),pathOverlapsMap:overlaps(pathRect,mapRect),pathCommands:(d.match(/[ML]/g)||[]).length};
  });
}

test('site, runner profile and Individual 75 target pace work without relevant errors',async({page})=>{
  const errors=watchRelevantErrors(page);await openSite(page);
  await expect(page.locator('#group-insights-data-label')).toHaveText('faktisk 2026-data');await expect(page.locator('#standouts-eyebrow')).toHaveText('PRESTATIONER SOM STICKER UT · 2026');
  await page.locator('#runner-search').fill('Anton Gustafsson');await page.locator('#runner-suggestions [data-record-id]').filter({hasText:'Anton Gustafsson'}).click();
  await expect(page.locator('#detail-dialog')).toBeVisible();await expect(page.locator('#detail-dialog h2')).toHaveText('Anton Gustafsson');await expect(page.locator('#personal-summary')).toBeVisible();
  await page.getByRole('button',{name:'Planera måltempo'}).click();await expect(page).toHaveURL(/section=goal-pace/);await expect(page.locator('[data-goal-create]')).toHaveText('Skapa loppplan');
  await page.locator('[data-goal-hours]').fill('9');await page.locator('[data-goal-minutes]').fill('30');await page.locator('[data-goal-create]').click();
  await expect(page.locator('[data-goal-output] tbody tr')).toHaveCount(9);await expect(page.locator('[data-goal-output] tbody tr').last().locator('td').nth(4)).toHaveText('9:30:00');
  expect(errors).toEqual([]);
});

test('Spurtvinnaren uses the last timing-only control before finish for individual races',async({page})=>{
  const errors=watchRelevantErrors(page);await openSite(page,'/?race=individual-75-2026&section=segments');
  await expect(page.locator('#spurtvinnaren')).toBeVisible();await expect(page.locator('#sprint-control-label')).toHaveText('Nolhaga → mål');
  expect(await page.locator('#sprint-women .sprint-row').count()).toBeGreaterThanOrEqual(5);expect(await page.locator('#sprint-men .sprint-row').count()).toBeGreaterThanOrEqual(5);
  await expect(page.locator('#sprint-women .sprint-row').first()).toHaveClass(/medal-1/);await expect(page.locator('#sprint-men .sprint-row').first()).toHaveClass(/medal-1/);
  await expect(page.locator('#sprint-women-filter-wrap')).toBeHidden();await expect(page.locator('#sprint-men-filter-wrap')).toBeHidden();
  const firstName=(await page.locator('#sprint-women .sprint-row').first().locator('.sprint-runner strong').textContent()).trim();await page.locator('#sprint-women .sprint-row').first().click();await expect(page.locator('#detail-dialog h2')).toHaveText(firstName);await page.locator('#detail-dialog .dialog-close').click();
  await page.getByRole('tab',{name:/Individuellt\s*35/}).click();await expect(page.locator('#sprint-control-label')).toHaveText('Nolhaga → mål');expect(await page.locator('#sprint-women .sprint-row').count()).toBeGreaterThanOrEqual(5);expect(await page.locator('#sprint-men .sprint-row').count()).toBeGreaterThanOrEqual(5);
  await page.getByRole('tab',{name:/Stafett 75/}).click();await expect(page.locator('#spurtvinnaren')).toBeHidden();expect(errors).toEqual([]);
});

test('Individual 35 stays scoped to four Floda-to-Alingsås segments',async({page})=>{
  await openSite(page);await page.getByRole('tab',{name:/Individuellt\s*35/}).click();await expect(page).toHaveURL(/race=individual-35-2026/);await page.locator('[data-target="goal-pace"]').click();
  await expect(page.getByRole('tab',{name:/Individuellt\s*35/})).toHaveAttribute('aria-selected','true');await expect(page.locator('#goal-pace-race')).toHaveText('Individuellt 35');
  await page.locator('[data-goal-hours]').fill('4');await page.locator('[data-goal-minutes]').fill('45');await page.locator('[data-goal-create]').click();
  await expect(page.locator('[data-goal-output] tbody tr')).toHaveCount(4);await expect(page.locator('[data-goal-output]')).toContainText('Tollered');await expect(page.locator('[data-goal-output]')).not.toContainText('Skatås');await expect(page.locator('[data-goal-output] tbody tr').last().locator('td').nth(4)).toHaveText('4:45:00');
});

test('invalid target is graceful and valid target persists after reload',async({page})=>{
  await openSite(page,'/?race=individual-75-2026&section=goal-pace');
  await page.locator('[data-goal-minutes]').fill('75');await page.locator('[data-goal-create]').click();await expect(page.locator('.goal-pace-error')).toContainText('mellan 0 och 59');
  await page.locator('[data-goal-hours]').fill('11');await page.locator('[data-goal-minutes]').fill('15');await page.locator('[data-goal-create]').click();await page.reload();
  await expect(page.locator('[data-goal-hours]')).toHaveValue('11');await expect(page.locator('[data-goal-minutes]')).toHaveValue('15');await expect(page.locator('[data-goal-output] tbody tr').last().locator('td').nth(4)).toHaveText('11:15:00');
});

test('favorites add, persist and remove',async({page})=>{
  await openSite(page,'/?race=individual-75-2026&section=results');
  const add=page.locator('#results-body [data-favorite-id]').first();const name=await add.getAttribute('aria-label');await add.click();await page.reload();
  await expect(page.locator('#favorites-list')).not.toContainText('Inga sparade löpare');await expect(page.locator('#favorites-list [data-favorite-id]')).toHaveCount(1);
  await page.locator('#favorites-list [data-favorite-id]').click();await expect(page.locator('#favorites-list')).toContainText('Inga sparade löpare');expect(name).toContain('Lägg');
});

test('Head-to-head opens for two valid runners',async({page})=>{
  await openSite(page,'/?race=individual-75-2026&section=map-duel');await chooseDuelRunner(page,'Anton Gustafsson');await chooseDuelRunner(page,'Anton Aro');
  await expect(page.locator('#open-head-to-head')).toBeEnabled();await page.locator('#open-head-to-head').click();await expect(page.locator('#head-to-head-dialog')).toBeVisible();await expect(page.locator('#head-to-head-dialog')).toContainText('Anton Gustafsson');await expect(page.locator('#head-to-head-dialog')).toContainText('Anton Aro');
});

test('Runner Replay, Kartduell and a direct map link use the selected course bundle',async({page})=>{
  const errors=watchRelevantErrors(page);await openSite(page);
  await page.locator('#runner-search').fill('Anton Gustafsson');const runner=page.locator('#runner-suggestions [data-record-id]').filter({hasText:'Anton Gustafsson'});const runnerId=await runner.getAttribute('data-record-id');await runner.click();await expect(page.locator('#detail-replay [data-map-engine]')).toBeVisible();await page.locator('#detail-dialog .dialog-close').click();
  await page.locator('[data-target="map-duel"]').click();await chooseDuelRunner(page,'Anton Gustafsson');await chooseDuelRunner(page,'Anton Aro');await page.locator('#open-map-duel').click();await expect(page.getByRole('dialog',{name:'Individuellt 75'})).toBeVisible();await expect(page.locator('#duel-dialog [data-duel-map] .leaflet-container')).toBeVisible();
  const secondId=await page.locator('#duel-selected [data-remove-duel]').nth(1).getAttribute('data-remove-duel');await page.goto(`/karta.html?race=individual-75-2026&entries=${runnerId.split(':')[1]},${secondId.split(':')[1]}`);await expect(page.locator('#map-page-root')).toHaveAttribute('aria-busy','false');await expect(page.locator('#map-page-root [data-duel-map] .leaflet-container')).toBeVisible();
  expect(errors).toEqual([]);
});

test('relay fallback hides target pace and browser navigation remains usable',async({page})=>{
  await openSite(page,'/?race=individual-35-2026&section=goal-pace');await page.goto('/?race=relay-75-2026&section=goal-pace');await expect(page).toHaveURL(/race=relay-75-2026&section=runner-lookup/);await expect(page.locator('[data-target="goal-pace"]')).toBeHidden();
  await page.goBack();await expect(page).toHaveURL(/race=individual-35-2026&section=goal-pace/);await expect(page.locator('#goal-pace')).toBeVisible();await page.goForward();await expect(page).toHaveURL(/race=relay-75-2026&section=runner-lookup/);await expect(page.locator('#runner-search')).toBeVisible();
});

test('390px viewport keeps critical controls usable without horizontal overflow',async({page})=>{
  await page.setViewportSize({width:390,height:844});await openSite(page,'/?race=individual-75-2026&section=goal-pace');
  await expect(page.locator('[data-goal-create]')).toBeVisible();await expect(page.locator('[data-goal-hours]')).toBeEditable();const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth);expect(overflow).toBe(false);
});

test('catalog-driven family and year controls keep single-year history intentional',async({page})=>{
  const errors=watchRelevantErrors(page);await openSite(page,'/?race=individual-75-2026&section=history');
  await expect(page.locator('#race-switch [role="tab"]')).toHaveCount(4);await expect(page.locator('#race-year')).toHaveValue('individual-75-2026');await expect(page).toHaveURL(/race=individual-75-2026&section=history/);
  await expect(page.locator('#history-content')).toContainText('Flerårsjämförelser aktiveras när ytterligare analyserbara upplagor finns.');await expect(page.locator('[data-history-edition]')).toHaveCount(1);await expect(page.locator('[data-history-reference]')).toHaveCount(0);
  await page.getByRole('tab',{name:/Individuellt 35/}).click();await expect(page).toHaveURL(/race=individual-35-2026/);await expect(page.locator('#race-year')).toHaveValue('individual-35-2026');await expect(page.locator('#history-content h2')).toContainText('Individuellt 35');
  for(const race of ['relay-75-2026','relay-35-2026']){await openSite(page,`/?race=${race}&section=history`);await expect(page.locator('#race-year')).toHaveValue(race);await expect(page.locator('#history-content [data-history-edition]')).toHaveCount(1);await expect(page.locator('#history-content')).toContainText('Inga verifierade återkommande deltagare')}
  await page.setViewportSize({width:390,height:844});await openSite(page,'/?race=individual-75-2026&section=history');expect(await page.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth)).toBe(false);expect(errors).toEqual([]);
});

test('acceptance panels, groups, finish progression and profile layout use the retained analyses',async({page})=>{
  const errors=watchRelevantErrors(page);await openSite(page,'/?race=individual-75-2026&section=gender');
  await expect(page.locator('#median-pace')).toHaveCount(0);await expect(page.locator('#pacing-chart')).toHaveCount(0);
  for(const name of ['Alla','Kvinnor','Män']){await expect(page.locator('#gender-pace .legend')).toContainText(name);await expect(page.locator('#gender-retention .legend')).toContainText(name)}
  await page.locator('[data-target="segments"]').click();const progression=page.locator('#percentile-ladder .finish-progression');await expect(page.getByRole('heading',{name:'När hade fältet gått i mål?'})).toBeVisible();await expect(progression).toBeVisible();await expect(progression.locator('.finish-threshold')).toHaveCount(5);await expect(progression.locator('[data-finish-share="50"]')).toContainText('50 % i mål · median');for(const group of ['Kvinnor','Män'])await expect(progression.locator('.finish-threshold').first()).toContainText(group);await expect(page.locator('#percentile-ladder .percentile-timeline')).toHaveCount(0);
  const widths=await page.locator('#segments .feature-grid.equal-panels>.panel').evaluateAll(nodes=>nodes.map(node=>node.getBoundingClientRect().width));expect(Math.abs(widths[0]-widths[1])).toBeLessThan(2);
  const label=page.locator('#course-difficulty .distribution-label').first();const labelStyle=await label.evaluate(element=>({fontSize:getComputedStyle(element).fontSize,transform:getComputedStyle(element).transform}));expect(parseFloat(labelStyle.fontSize)).toBeLessThanOrEqual(12);expect(labelStyle.transform).not.toBe('none');
  await page.getByRole('tab',{name:/Stafett 75/}).click();await page.locator('[data-target="segments"]').click();await expect(page.locator('#percentile-ladder .finish-threshold')).toHaveCount(5);await expect(page.locator('#percentile-ladder')).toContainText('Mixed fri · Ej tävling');
  await page.setViewportSize({width:390,height:844});await page.getByRole('tab',{name:/Individuellt 75/}).click();await page.locator('[data-target="segments"]').click();expect(await page.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth)).toBe(false);expect(await page.locator('#percentile-ladder').evaluate(element=>element.scrollWidth<=element.clientWidth)).toBe(true);
  await page.locator('[data-target="runner-lookup"]').click();await page.locator('#runner-search').fill('Anton Gustafsson');await page.locator('#runner-suggestions [data-record-id]').filter({hasText:'Anton Gustafsson'}).click();await expect(page.locator('#detail-placement')).toHaveCount(0);await expect(page.locator('#detail-content .detail-grid.single')).toBeVisible();await expect(page.locator('[data-journey-placement-chart]')).toBeVisible();await expect(page.locator('[data-journey-placement="overall"]')).toHaveAttribute('aria-pressed','true');expect(errors).toEqual([]);
});

test('participant search explains no matches and profile dialog restores focus',async({page})=>{
  const errors=watchRelevantErrors(page);await openSite(page);const search=page.locator('#runner-search');
  await expect(search).toHaveAttribute('role','combobox');await expect(search).toHaveAttribute('aria-autocomplete','list');await search.fill('zzzz-ingen-traff');await expect(page.locator('#runner-suggestions')).toBeVisible();await expect(page.locator('#runner-suggestions [role="option"]')).toHaveText('Ingen träff i valt lopp.');
  await search.fill('Anton Gustafsson');await page.locator('#runner-suggestions [data-record-id]').filter({hasText:'Anton Gustafsson'}).click();await expect(page.getByRole('dialog',{name:'Anton Gustafsson'})).toBeVisible();await expect(page.locator('#detail-dialog .dialog-close')).toBeFocused();
  await page.locator('#detail-dialog .dialog-close').click();await expect(search).toBeFocused();await expect(page.locator('#detail-dialog')).not.toBeVisible();expect(errors).toEqual([]);
});

test('empty segment selections show a truthful race-story state in every race mode',async({page})=>{
  const errors=watchRelevantErrors(page);
  for(const race of ['individual-75-2026','individual-35-2026','relay-75-2026','relay-35-2026']){
    await openSite(page,`/?race=${race}&section=statistics`);await page.locator('#status-filter').selectOption('DNS');
    await expect(page.locator('#race-story .empty')).toHaveText('Inga genomförda segment i urvalet.');
  }
  expect(errors).toEqual([]);
});

test('a declarative future edition activates through the real catalog, course loader and history UI',async({page})=>{
  await page.setViewportSize({width:390,height:844});const errors=watchRelevantErrors(page),fixture=await installFutureEditionFixture(page);
  await openSite(page,'/?race=solo-future&section=history');
  await expect(page).toHaveURL(/race=solo-future&section=history/);await expect(page.locator('#race-switch [role="tab"]')).toHaveCount(2);await expect(page.locator('#race-year')).toHaveValue('solo-future');await expect(page.locator('#race-year option')).toHaveCount(4);await expect(page.locator('#history-content [data-history-edition]')).toHaveCount(4);
  await expect(page.locator('#race-switch [role="tab"]').first()).toContainText('4 upplagor');await expect(page.locator('#group-insights-data-label')).toHaveText('faktisk 2033-data');await expect(page.locator('#standouts-eyebrow')).toHaveText('PRESTATIONER SOM STICKER UT · 2033');await expect(page.locator('#history-content')).toContainText('4 katalogiserade upplagor');
  await expect(page.locator('[data-history-relation="compatible"]')).toContainText('2031');await expect(page.locator('[data-history-relation="incomparable"]')).toContainText('2034');await expect(page.locator('[data-history-segment-relation="compatible"]')).toContainText('2031');await expect(page.locator('#race-year option[value="solo-planned"]')).toHaveAttribute('disabled','');await expect(page.locator('#history-content')).not.toContainText('2032');
  await expect(page.locator('#course-difficulty [data-course-map] .leaflet-container')).toBeVisible();
  expect(fixture.requests.filter(path=>path.includes('route-beta')).length).toBe(2);expect(fixture.requests.some(path=>path.includes('route-alpha')||path.includes('route-gamma'))).toBe(false);
  await page.locator('[data-target="goal-pace"]').click();await page.locator('[data-goal-hours]').fill('5');await page.locator('[data-goal-minutes]').fill('20');await page.locator('[data-goal-create]').click();await expect(page.locator('[data-goal-output] tbody tr')).toHaveCount(2);
  await page.locator('#race-year').selectOption('solo-before');await expect(page).toHaveURL(/race=solo-before/);expect(fixture.requests.filter(path=>path.includes('route-alpha')).length).toBe(2);
  await expect(page.locator('[data-goal-hours]')).not.toHaveValue('5');await page.locator('#race-year').selectOption('solo-future');await expect(page.locator('[data-goal-hours]')).toHaveValue('5');expect(fixture.requests.filter(path=>path.includes('route-beta')).length).toBe(2);
  await page.locator('[data-target="results"]').click();await page.locator('#results-body [data-favorite-id]').first().click();await expect(page.locator('#favorites-list')).toContainText('Verified Global');
  await page.locator('#runner-search').fill('Verified Global');await page.locator('#runner-suggestions [data-record-id]').click();await expect(page.locator('.profile-history')).toContainText('Verifierad personhistorik');await expect(page.locator('.profile-history')).toContainText('Inte jämförbar');await page.locator('#detail-dialog .dialog-close').click();
  await chooseDuelRunner(page,'Verified Global');await chooseDuelRunner(page,'Runner 5');await expect(page.locator('#open-head-to-head')).toBeEnabled();await page.locator('#race-year').selectOption('solo-before');await expect(page.locator('#duel-selected')).toContainText('Inga valda');await expect(page.locator('#favorites-list')).toContainText('Inga sparade');
  await page.getByRole('tab',{name:/Team/}).click();await expect(page).toHaveURL(/race=team-before/);await expect(page.locator('#race-year option')).toHaveCount(2);await expect(page.locator('#race-year')).not.toContainText('2032');await expect(page.locator('[data-target="goal-pace"]')).toBeHidden();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth)).toBe(false);expect(errors).toEqual([]);
});

test('an alternate four-family event and two-person Duo use the same generic runtime',async({page})=>{
  await page.setViewportSize({width:390,height:844});const errors=watchRelevantErrors(page);await installAlternateEventFixture(page);await openSite(page,'/?race=long-solo-b&section=history');
  await expect(page.getByRole('heading',{name:'Coast Trail Explorer'})).toBeVisible();await expect(page.locator('#source-link')).toHaveAttribute('href','https://example.test/coast/results');await expect(page.locator('#race-switch [role="tab"]')).toHaveCount(4);await expect(page.locator('#race-subtitle')).toContainText('62 km');await expect(page.locator('.hero__route')).toContainText('Salt Marsh');await expect(page.locator('.hero__route')).toContainText('Harbor Light');await expect(page.locator('[data-target="goal-pace"]')).toBeVisible();await expect(page.locator('#sex-filter-field')).toBeVisible();
  const alternateCourse=page.locator('#course-difficulty');await alternateCourse.locator('[data-course-elevation] [data-course-segment="0"]').click();const alternateVisual=await leafletHighlightVisual(alternateCourse);expect(alternateVisual.rendererOverlapsMap).toBe(true);expect(alternateVisual.pathOverlapsMap).toBe(true);expect(alternateVisual.svgComputedWidth).not.toBe('0px');
  await page.locator('[data-target="results"]').click();await page.locator('#results-body [data-favorite-id]').first().click();expect(await page.evaluate(()=>localStorage.getItem('coast-lab:favorites-v1'))).toContain('long-solo-b');expect(await page.evaluate(()=>localStorage.getItem('gotaleden-favorites-v1'))).toBeNull();
  await page.getByRole('tab',{name:/Duo Long/}).click();await expect(page.locator('[data-target="runner-lookup"]')).toHaveText('Duos');await expect(page.locator('[data-target="goal-pace"]')).toBeHidden();await expect(page.locator('#sex-filter-field')).toBeHidden();await expect(page.locator('#club-filter-field')).toBeHidden();await expect(page.locator('#results-head')).toContainText('duo');await expect(page.locator('#results-head')).toContainText('Division');
  await page.locator('[data-target="gender"]').click();await expect(page.locator('#group-analysis-eyebrow')).toHaveText('DUO DIVISIONS');await expect(page.locator('#group-analysis-title')).toHaveText('Duos by division');await page.locator('[data-target="segments"]').click();await expect(page.locator('#percentile-ladder .finish-threshold')).toHaveCount(5);await expect(page.locator('#percentile-ladder')).toContainText('Pairs');await page.locator('[data-target="age-analysis"]').click();await expect(page.locator('#age-analysis-eyebrow')).toHaveText('DUO DIVISIONS');await expect(page.locator('#age-analysis')).toContainText('Compare official duo divisions');
  await page.locator('#runner-search').fill('Sea Duo 1');await page.locator('#runner-suggestions [data-record-id]').first().click();await expect(page.locator('#detail-dialog')).toBeVisible();await expect(page.locator('.detail-members span')).toHaveCount(2);await expect(page.locator('.detail-members .eyebrow')).toHaveText('DUO MEMBERS');await expect(page.locator('#detail-replay [data-map-engine]')).toBeVisible();await expect(page.locator('#detail-dialog')).toContainText('DUO ANALYSIS');const duoDetailText=await page.locator('#detail-dialog').innerText();for(const forbidden of ['lagtid','Lagklass','Lagmedlemmar','stafett','Stafett'])expect(duoDetailText).not.toContain(forbidden);await page.locator('#detail-dialog .dialog-close').click();
  await page.locator('#duel-search').fill('Sea Duo 1');await page.locator('#duel-suggestions [data-record-id]').first().click();await page.locator('#duel-search').fill('Sea Duo 2');await page.locator('#duel-suggestions [data-record-id]').first().click();await expect(page.locator('#open-head-to-head')).toBeEnabled();await page.locator('#open-head-to-head').click();await expect(page.locator('#head-to-head-dialog')).toContainText('Sea Duo 1');await page.locator('#head-to-head-dialog .head-to-head-close').click();
  await page.goto('/karta.html?race=duo-long-a&entries=1,2');await expect(page.locator('#map-page-root')).toHaveAttribute('aria-busy','false');await expect(page.locator('#map-page-root [data-duel-map] .leaflet-container')).toBeVisible();await expect(page).toHaveTitle(/Coast Trail Explorer/);const mapText=await page.locator('body').innerText();for(const forbidden of ['Gotaleden','Göteborg','Floda','Alingsås','stafett','Stafett'])expect(mapText).not.toContain(forbidden);
  const visibleText=await page.locator('body').innerText();for(const forbidden of ['Gotaleden','Göteborg','Floda','Alingsås','stafett','Stafett'])expect(visibleText).not.toContain(forbidden);expect(await page.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth)).toBe(false);expect(errors).toEqual([]);
});

test('source and event text cannot create markup in runtime views',async({page})=>{
  const fixture=createAlternateEventFixture(),payload='<img data-e4-xss="true" src="missing" onerror="window.__e4Xss=(window.__e4Xss||0)+1">';
  const solo=fixture.data.races['long-solo-b'];solo.participant.profile_label=payload;solo.participant.possessive=payload;fixture.data.race_catalog['long-solo-b'].participant=solo.participant;fixture.data.checkpoints['long-solo-b'][0].name=payload;fixture.data.checkpoints['long-solo-b'][1].name=payload;
  const duo=fixture.data.races['duo-long-a'];duo.records[0].class_name=payload;
  await page.route('**/data/results.json**',route=>route.fulfill({contentType:'application/json',body:JSON.stringify(fixture.data)}));
  await page.route('**/data/alternate/**',route=>{const path=new URL(route.request().url()).pathname.replace(/^\//,'').split('?')[0],asset=fixture.assets[path];return asset?route.fulfill({contentType:'application/json',body:JSON.stringify(asset)}):route.continue()});
  await openSite(page,'/?race=long-solo-b&runner=1');await expect(page.locator('#detail-dialog')).toBeVisible();expect(await page.locator('[data-e4-xss]').count()).toBe(0);expect(await page.evaluate(()=>window.__e4Xss||0)).toBe(0);await page.locator('#detail-dialog .dialog-close').click();
  await page.getByRole('tab',{name:/Duo Long/}).click();await page.locator('#class-filter').selectOption(payload);expect(await page.locator('[data-e4-xss]').count()).toBe(0);expect(await page.evaluate(()=>window.__e4Xss||0)).toBe(0);
});

test('course difficulty keeps map, elevation, distribution, KPI and table on one selected segment',async({page})=>{
  const errors=watchRelevantErrors(page);await openSite(page,'/?race=individual-75-2026&section=segments');const course=page.locator('#course-difficulty');await course.scrollIntoViewIfNeeded();
  const nameAt=async index=>(await course.locator(`[data-course-row="${index}"] .course-segment-name strong`).textContent()).trim();
  const expectSelected=async index=>{await expect(course.locator('[data-course-selected] h3')).toHaveText(await nameAt(index));await expect(course.locator(`[data-course-row="${index}"]`)).toHaveAttribute('aria-pressed','true');await expect(course.locator(`[data-course-elevation] [data-course-segment="${index}"]`)).toHaveClass(/selected/);await expect(course.locator(`[data-course-distribution] .distribution-segment-hit[data-course-segment="${index}"]`)).toHaveClass(/selected/);const elevation=course.locator('[data-course-elevation] .elevation-range-highlight'),mapHighlight=course.locator('[data-course-map] .route-range-highlight');await expect(mapHighlight).toHaveCount(1);expect(await mapHighlight.getAttribute('data-map-highlight-from')).toBe(await elevation.getAttribute('data-highlight-from'));expect(await mapHighlight.getAttribute('data-map-highlight-to')).toBe(await elevation.getAttribute('data-highlight-to'))};
  const kpi=course.locator('[data-course-kpi]').first();await kpi.click();await expectSelected(Number(await kpi.getAttribute('data-course-kpi')));await page.mouse.move(0,0);
  const elevationHit=course.locator('[data-course-elevation] [data-course-segment="1"]');expect(await elevationHit.evaluate(element=>Boolean(element.onclick))).toBe(true);await elevationHit.click();await expectSelected(1);const mapVisual=await leafletHighlightVisual(course);expect(mapVisual.stroke).toBe('rgb(219, 95, 40)');expect(mapVisual.strokeWidth).toBeGreaterThanOrEqual(11);expect(mapVisual.paneZ).toBeGreaterThan(400);expect(mapVisual.svgWidthAttribute).toBeGreaterThan(0);expect(mapVisual.svgHeightAttribute).toBeGreaterThan(0);expect(mapVisual.svgRect.width).toBeGreaterThanOrEqual(mapVisual.mapRect.width);expect(mapVisual.svgRect.height).toBeGreaterThanOrEqual(mapVisual.mapRect.height);expect(mapVisual.svgComputedWidth).not.toBe('0px');expect(mapVisual.svgComputedHeight).not.toBe('0px');expect(mapVisual.svgMaxHeight).toBe('none');expect(mapVisual.rendererOverlapsMap).toBe(true);expect(mapVisual.pathOverlapsMap).toBe(true);expect(mapVisual.pathCommands).toBeGreaterThan(10);
  await course.locator('[data-course-distribution] .distribution-segment-hit[data-course-segment="4"]').click();await expectSelected(4);
  const committedFrom=await page.locator('#segment-from').inputValue(),previewHit=course.locator('[data-course-distribution] .distribution-segment-hit[data-course-segment="3"]');await previewHit.hover();await expect(previewHit).toHaveClass(/selected/);await expect(course.locator('[data-course-selected] h3')).toHaveText(await nameAt(4));expect(await page.locator('#segment-from').inputValue()).toBe(committedFrom);await page.mouse.move(0,0);await expectSelected(4);
  await course.locator('[data-course-row="6"]').click();await expectSelected(6);await expect(page.locator('#segment-from')).toHaveValue('tollered');await expect(page.locator('#segment-to')).toHaveValue('norsesund');
  await page.locator('#segment-from').selectOption('kasjon');await page.locator('#segment-to').selectOption('jonsered');await expectSelected(2);
  const mapPath=course.locator('[data-course-map] [data-map-segment="1"]');await mapPath.press('Enter');await expectSelected(1);await course.locator('[data-course-map] [data-map-action="fit"]').click();await expectSelected(1);expect((await leafletHighlightVisual(course)).pathOverlapsMap).toBe(true);
  const story=course.locator('#race-intelligence');await expect(story).toBeVisible();expect(await course.evaluate(root=>{const distribution=root.querySelector('[data-course-distribution]'),story=root.querySelector('#race-intelligence'),segments=root.querySelector('.course-segments');return Boolean(distribution&&story&&segments&&distribution.compareDocumentPosition(story)&Node.DOCUMENT_POSITION_FOLLOWING&&story.compareDocumentPosition(segments)&Node.DOCUMENT_POSITION_FOLLOWING)})).toBe(true);const storyButton=story.locator('[data-story-index]').first(),storySegment=(await storyButton.locator('strong').textContent()).trim();await storyButton.click();await expect(course.locator('[data-course-selected] h3')).toHaveText(storySegment);await expect(course.locator('[data-course-map] .route-range-highlight')).toHaveCount(1);
  expect(errors).toEqual([]);
});

test('course difficulty fallback SVG keeps its responsive route and highlight',async({page})=>{
  const errors=watchRelevantErrors(page);await page.route('**/vendor/leaflet/leaflet.js**',route=>route.fulfill({contentType:'text/javascript',body:''}));await openSite(page,'/?race=individual-75-2026&section=segments');const course=page.locator('#course-difficulty');await course.locator('[data-course-elevation] [data-course-segment="1"]').click();const fallback=course.locator('[data-course-map] .fallback-map');await expect(fallback).toBeVisible();const visual=await fallback.evaluate(root=>{const svg=root.querySelector(':scope > svg'),route=root.querySelector('.route-line-map'),highlight=root.querySelector('.route-range-highlight'),rootRect=root.getBoundingClientRect(),svgRect=svg.getBoundingClientRect(),highlightRect=highlight.getBoundingClientRect(),d=highlight.getAttribute('d')||'';return{rootWidth:rootRect.width,svgWidth:svgRect.width,svgHeight:svgRect.height,routeVisible:route.getBoundingClientRect().width>0&&route.getBoundingClientRect().height>0,highlightVisible:highlightRect.width>0&&highlightRect.height>0,stroke:getComputedStyle(highlight).stroke,strokeWidth:parseFloat(getComputedStyle(highlight).strokeWidth),pathCommands:(d.match(/[ML]/g)||[]).length}});expect(visual.svgWidth).toBeCloseTo(visual.rootWidth,0);expect(visual.svgHeight).toBeGreaterThan(0);expect(visual.routeVisible).toBe(true);expect(visual.highlightVisible).toBe(true);expect(visual.stroke).toBe('rgb(219, 95, 40)');expect(visual.strokeWidth).toBeGreaterThanOrEqual(11);expect(visual.pathCommands).toBeGreaterThan(10);expect(errors).toEqual([]);
});

test('group pace and retention cards share a desktop baseline and stack on mobile',async({page})=>{
  const errors=watchRelevantErrors(page);await openSite(page,'/?race=individual-75-2026&section=gender');const cards=async()=>page.evaluate(()=>['gender-pace','gender-retention'].map(id=>{const panel=document.getElementById(id).closest('.panel').getBoundingClientRect();return{top:panel.top,bottom:panel.bottom,height:panel.height}}));let [pace,retention]=await cards();expect(Math.abs(pace.bottom-retention.bottom)).toBeLessThanOrEqual(1);expect(Math.abs(pace.height-retention.height)).toBeLessThanOrEqual(1);await page.setViewportSize({width:390,height:844});await openSite(page,'/?race=individual-75-2026&section=gender');[pace,retention]=await cards();expect(retention.top).toBeGreaterThanOrEqual(pace.bottom);expect(await page.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth)).toBe(false);expect(errors).toEqual([]);
});

test('course highlight is visibly laid out in all four Gotaleden race modes on desktop',async({page})=>{
  const errors=watchRelevantErrors(page);for(const [race,count] of [['individual-75-2026',9],['individual-35-2026',4],['relay-75-2026',9],['relay-35-2026',4]]){await openSite(page,`/?race=${race}&section=segments`);const course=page.locator('#course-difficulty'),index=count-1;await course.locator(`[data-course-elevation] [data-course-segment="${index}"]`).click();const visual=await leafletHighlightVisual(course);expect(visual.rendererOverlapsMap).toBe(true);expect(visual.pathOverlapsMap).toBe(true);expect(visual.svgRect.width).toBeGreaterThanOrEqual(visual.mapRect.width);expect(visual.strokeWidth).toBeGreaterThanOrEqual(11);expect(visual.pathCommands).toBeGreaterThan(2)}expect(errors).toEqual([]);
});

test('course segment interaction works for 35 km, both relays and a 390px viewport',async({page})=>{
  const errors=watchRelevantErrors(page);await page.setViewportSize({width:390,height:844});
  for(const [race,count,relay] of [['individual-35-2026',4,false],['relay-75-2026',9,true],['relay-35-2026',4,true]]){await openSite(page,`/?race=${race}&section=segments`);const course=page.locator('#course-difficulty');await expect(course.locator('[data-course-row]')).toHaveCount(count);const index=count-1,name=(await course.locator(`[data-course-row="${index}"] .course-segment-name strong`).textContent()).trim();await course.locator(`[data-course-elevation] [data-course-segment="${index}"]`).click();await expect(course.locator('[data-course-selected] h3')).toHaveText(name);await expect(course.locator(`[data-course-row="${index}"]`)).toHaveAttribute('aria-pressed','true');const elevation=course.locator('[data-course-elevation] .elevation-range-highlight'),mapHighlight=course.locator('[data-course-map] .route-range-highlight');await expect(mapHighlight).toHaveCount(1);expect(await mapHighlight.getAttribute('data-map-highlight-from')).toBe(await elevation.getAttribute('data-highlight-from'));expect(await mapHighlight.getAttribute('data-map-highlight-to')).toBe(await elevation.getAttribute('data-highlight-to'));const visual=await leafletHighlightVisual(course);expect(visual.rendererOverlapsMap).toBe(true);expect(visual.pathOverlapsMap).toBe(true);expect(visual.svgRect.width).toBeGreaterThanOrEqual(visual.mapRect.width);await expect(course.locator('.course-chart-panel').nth(1).locator('.eyebrow')).toHaveText(relay?'LAGENS FART & SPRIDNING':'FÄLTETS FART & SPRIDNING');expect(await page.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth)).toBe(false)}
  expect(errors).toEqual([]);
});
