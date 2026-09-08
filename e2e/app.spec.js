const {test,expect}=require('@playwright/test');

function watchRelevantErrors(page){
  const errors=[];
  page.on('pageerror',error=>errors.push(`page: ${error.message}`));
  page.on('console',message=>{if(message.type()==='error'&&!message.text().includes('Failed to load resource'))errors.push(`console: ${message.text()}`)});
  page.on('response',response=>{const request=response.request(),local=response.url().startsWith('http://127.0.0.1:4173/');if(local&&response.status()>=400&&['document','script','fetch','xhr'].includes(request.resourceType()))errors.push(`${response.status()} ${response.url()}`)});
  return errors;
}

async function openSite(page,url='/?race=individual-75-2026&section=runner-lookup'){
  await page.goto(url);await expect(page.locator('#loading')).toHaveClass(/hidden/);await expect(page.getByRole('heading',{name:'Gotaleden Splits'})).toBeVisible();
}

async function chooseDuelRunner(page,name){
  await page.locator('#duel-search').fill(name);await page.locator('#duel-suggestions [data-record-id]').filter({hasText:name}).first().click();
}

test('site, runner profile and Individual 75 target pace work without relevant errors',async({page})=>{
  const errors=watchRelevantErrors(page);await openSite(page);
  await page.locator('#runner-search').fill('Anton Gustafsson');await page.locator('#runner-suggestions [data-record-id]').filter({hasText:'Anton Gustafsson'}).click();
  await expect(page.locator('#detail-dialog')).toBeVisible();await expect(page.locator('#detail-dialog h2')).toHaveText('Anton Gustafsson');await expect(page.locator('#personal-summary')).toBeVisible();
  await page.getByRole('button',{name:'Planera måltempo'}).click();await expect(page).toHaveURL(/section=goal-pace/);
  await page.locator('[data-goal-hours]').fill('9');await page.locator('[data-goal-minutes]').fill('30');await page.locator('[data-goal-create]').click();
  await expect(page.locator('[data-goal-output] tbody tr')).toHaveCount(9);await expect(page.locator('[data-goal-output] tbody tr').last().locator('td').nth(4)).toHaveText('9:30:00');
  expect(errors).toEqual([]);
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

test('relay fallback hides target pace and browser navigation remains usable',async({page})=>{
  await openSite(page,'/?race=individual-35-2026&section=goal-pace');await page.goto('/?race=relay-75-2026&section=goal-pace');await expect(page).toHaveURL(/race=relay-75-2026&section=runner-lookup/);await expect(page.locator('[data-target="goal-pace"]')).toBeHidden();
  await page.goBack();await expect(page).toHaveURL(/race=individual-35-2026&section=goal-pace/);await expect(page.locator('#goal-pace')).toBeVisible();await page.goForward();await expect(page).toHaveURL(/race=relay-75-2026&section=runner-lookup/);await expect(page.locator('#runner-search')).toBeVisible();
});

test('390px viewport keeps critical controls usable without horizontal overflow',async({page})=>{
  await page.setViewportSize({width:390,height:844});await openSite(page,'/?race=individual-75-2026&section=goal-pace');
  await expect(page.locator('[data-goal-create]')).toBeVisible();await expect(page.locator('[data-goal-hours]')).toBeEditable();const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth);expect(overflow).toBe(false);
});

test('course difficulty keeps map, elevation, distribution, KPI and table on one selected segment',async({page})=>{
  const errors=watchRelevantErrors(page);await openSite(page,'/?race=individual-75-2026&section=segments');const course=page.locator('#course-difficulty');await course.scrollIntoViewIfNeeded();
  const nameAt=async index=>(await course.locator(`[data-course-row="${index}"] .course-segment-name strong`).textContent()).trim();
  const expectSelected=async index=>{await expect(course.locator('[data-course-selected] h3')).toHaveText(await nameAt(index));await expect(course.locator(`[data-course-row="${index}"]`)).toHaveAttribute('aria-pressed','true');await expect(course.locator(`[data-course-elevation] [data-course-segment="${index}"]`)).toHaveClass(/selected/);await expect(course.locator(`[data-course-distribution] .distribution-segment-hit[data-course-segment="${index}"]`)).toHaveClass(/selected/);const elevation=course.locator('[data-course-elevation] .elevation-range-highlight'),mapHighlight=course.locator('[data-course-map] .route-range-highlight');await expect(mapHighlight).toHaveCount(1);expect(await mapHighlight.getAttribute('data-map-highlight-from')).toBe(await elevation.getAttribute('data-highlight-from'));expect(await mapHighlight.getAttribute('data-map-highlight-to')).toBe(await elevation.getAttribute('data-highlight-to'))};
  const kpi=course.locator('[data-course-kpi]').first();await kpi.click();await expectSelected(Number(await kpi.getAttribute('data-course-kpi')));await page.mouse.move(0,0);
  const elevationHit=course.locator('[data-course-elevation] [data-course-segment="2"]');expect(await elevationHit.evaluate(element=>Boolean(element.onclick))).toBe(true);await elevationHit.click();await expectSelected(2);
  await course.locator('[data-course-distribution] .distribution-segment-hit[data-course-segment="4"]').click();await expectSelected(4);
  const committedFrom=await page.locator('#segment-from').inputValue(),previewHit=course.locator('[data-course-distribution] .distribution-segment-hit[data-course-segment="3"]');await previewHit.hover();await expect(previewHit).toHaveClass(/selected/);await expect(course.locator('[data-course-selected] h3')).toHaveText(await nameAt(4));expect(await page.locator('#segment-from').inputValue()).toBe(committedFrom);await page.mouse.move(0,0);await expectSelected(4);
  await course.locator('[data-course-row="6"]').click();await expectSelected(6);await expect(page.locator('#segment-from')).toHaveValue('tollered');await expect(page.locator('#segment-to')).toHaveValue('norsesund');
  const mapPath=course.locator('[data-course-map] [data-map-segment="1"]');await mapPath.press('Enter');await expectSelected(1);
  expect(errors).toEqual([]);
});

test('course segment interaction works for 35 km, both relays and a 390px viewport',async({page})=>{
  const errors=watchRelevantErrors(page);await page.setViewportSize({width:390,height:844});
  for(const [race,count,relay] of [['individual-35-2026',4,false],['relay-75-2026',9,true],['relay-35-2026',4,true]]){await openSite(page,`/?race=${race}&section=segments`);const course=page.locator('#course-difficulty');await expect(course.locator('[data-course-row]')).toHaveCount(count);const index=count-1,name=(await course.locator(`[data-course-row="${index}"] .course-segment-name strong`).textContent()).trim();await course.locator(`[data-course-elevation] [data-course-segment="${index}"]`).click();await expect(course.locator('[data-course-selected] h3')).toHaveText(name);await expect(course.locator(`[data-course-row="${index}"]`)).toHaveAttribute('aria-pressed','true');const elevation=course.locator('[data-course-elevation] .elevation-range-highlight'),mapHighlight=course.locator('[data-course-map] .route-range-highlight');await expect(mapHighlight).toHaveCount(1);expect(await mapHighlight.getAttribute('data-map-highlight-from')).toBe(await elevation.getAttribute('data-highlight-from'));expect(await mapHighlight.getAttribute('data-map-highlight-to')).toBe(await elevation.getAttribute('data-highlight-to'));await expect(course.locator('.course-chart-panel').nth(1).locator('.eyebrow')).toHaveText(relay?'LAGENS FART & SPRIDNING':'FÄLTETS FART & SPRIDNING');expect(await page.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth)).toBe(false)}
  expect(errors).toEqual([]);
});
