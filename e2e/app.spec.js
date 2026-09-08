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
