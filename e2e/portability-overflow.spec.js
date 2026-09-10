const {test,expect}=require('@playwright/test');
const {create:createAlternateEventFixture}=require('../tests/fixtures/alternate-event.js');

async function installAlternateEventFixture(page){
  const fixture=createAlternateEventFixture();
  await page.route('**/data/results.json**',route=>route.fulfill({contentType:'application/json',body:JSON.stringify(fixture.data)}));
  await page.route('**/data/alternate/**',route=>{const path=new URL(route.request().url()).pathname.replace(/^\//,'').split('?')[0],asset=fixture.assets[path];return asset?route.fulfill({contentType:'application/json',body:JSON.stringify(asset)}):route.continue()});
}

async function overflowReport(page){
  return page.evaluate(()=>{
    const root=document.documentElement,width=root.clientWidth,describe=element=>{const rect=element.getBoundingClientRect(),style=getComputedStyle(element);return{tag:element.tagName.toLowerCase(),id:element.id||'',className:typeof element.className==='string'?element.className:'',left:Math.round(rect.left*10)/10,right:Math.round(rect.right*10)/10,width:Math.round(rect.width*10)/10,clientWidth:element.clientWidth,scrollWidth:element.scrollWidth,overflowX:style.overflowX,display:style.display,position:style.position,text:(element.textContent||'').trim().replace(/\s+/g,' ').slice(0,80)}};
    const elements=[...document.querySelectorAll('body *')],offenders=elements.map(describe).filter(item=>item.display!=='none'&&(item.right>width+1||item.left<-1)).sort((a,b)=>Math.max(b.right-width,-b.left)-Math.max(a.right-width,-a.left)).slice(0,20);
    const leakingContainers=elements.filter(element=>{const style=getComputedStyle(element);return style.display!=='none'&&element.scrollWidth>element.clientWidth+1&&!['auto','scroll','hidden','clip'].includes(style.overflowX)}).map(describe).sort((a,b)=>(b.scrollWidth-b.clientWidth)-(a.scrollWidth-a.clientWidth)).slice(0,20);
    const bodyChildren=[...document.body.children].map(describe);
    return{clientWidth:width,scrollWidth:root.scrollWidth,bodyClientWidth:document.body.clientWidth,bodyScrollWidth:document.body.scrollWidth,offenders,leakingContainers,bodyChildren};
  });
}

async function choose(page,name){
  await page.locator('#duel-search').fill(name);
  await page.locator('#duel-suggestions [data-record-id]').filter({hasText:name}).first().click();
}

test('alternate event remains page-width safe at 390px through Duo profile and H2H',async({page})=>{
  await page.setViewportSize({width:390,height:844});
  await installAlternateEventFixture(page);
  await page.goto('/?race=duo-long-a&section=age-analysis');
  await expect(page.locator('#loading')).toHaveClass(/hidden/);
  await page.locator('#runner-search').fill('Sea Duo 1');
  await page.locator('#runner-suggestions [data-record-id]').first().click();
  await expect(page.locator('#detail-dialog')).toBeVisible();
  await page.locator('#detail-dialog .dialog-close').click();
  await choose(page,'Sea Duo 1');await choose(page,'Sea Duo 2');
  await page.locator('#open-head-to-head').click();
  await expect(page.locator('#head-to-head-dialog')).toBeVisible();
  await page.locator('#head-to-head-dialog .head-to-head-close').click();
  const report=await overflowReport(page);
  console.log('PORTABILITY_OVERFLOW_REPORT '+JSON.stringify(report));
  expect(report.scrollWidth,`Page overflow: ${JSON.stringify(report)}`).toBeLessThanOrEqual(report.clientWidth);
});
