(function(){
  'use strict';
  const ICON='<svg class="analysis-help-icon" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="1.8"/><circle cx="12" cy="8" r="1.15" fill="currentColor"/><path d="M12 11.2V16.4" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/></svg>';
  const TARGETS=[
    ['head-to-head-overview','#head-to-head-dialog [data-head-help="overview"]',null,null],
    ['head-to-head-gap','#head-to-head-dialog [data-head-help="gap"]',null,null],
    ['head-to-head-placement','#head-to-head-dialog [data-head-help="placement"]',null,null],
    ['head-to-head-segments','#head-to-head-dialog [data-head-help="segments"]',null,null],
    ['head-to-head-field-pacing','#head-to-head-dialog [data-head-help="field-pacing"]',null,null],
    ['head-to-head-course','#head-to-head-dialog [data-head-help="course"]',null,null],
    ['filters','.toolbar','.toolbar',null],
    ['overview-kpis','#overview-kpis','#overview-kpis',null],
    ['finish-distribution','#finish-histogram','.panel','h2'],
    ['overview-segment-pace','#median-pace','.panel','h2'],
    ['elevation-profile','#elevation-profile','.panel','h2'],
    ['placement-engine','#placement-scatter','.panel','h3'],
    ['target-time-simulator','#target-time-result','.simulator','h3'],
    ['dnf-funnel','#dnf-funnel','.panel','h3'],
    ['segment-character','#segment-character','.panel','h3'],
    ['advancement-ranking','#overtake-ranking','.panel','h3'],
    ['whole-race-pacing','#pacing-chart','.panel','h3'],
    ['group-kpis','#gender-kpis','#gender-kpis',null],
    ['group-pace-distribution','#gender-pace','.panel','h3'],
    ['group-retention','#gender-retention','.panel','h3'],
    ['group-insights','#gender-insights','.automatic-insights','h3'],
    ['age-class-lab','#age-analysis .section-intro','.section-intro','h2'],
    ['age-class-pace','#age-pace','.panel','h3'],
    ['pace-heatmap','#age-heatmap','.panel','h3'],
    ['course-difficulty','#course-difficulty .course-difficulty-head','.course-difficulty-head','h2'],
    ['course-elevation-map','#course-difficulty .course-main','.course-main','.course-selected h3'],
    ['course-distribution','#course-difficulty [data-course-distribution]','.course-chart-panel','h3'],
    ['segment-lab','.segment-lab','.segment-lab',null],
    ['time-thresholds','#percentile-ladder','.panel','h3'],
    ['field-flow','#field-flow','.panel','h3'],
    ['race-intelligence','#race-intelligence','#race-intelligence','h3'],
    ['standouts','#standouts','#standouts','h3'],
    ['club-arena','.club-arena','.club-arena',null],
    ['profile-summary','#detail-content .detail-hero','.detail-hero','h2'],
    ['profile-relative-insights','#detail-content .insight-cards','.insight-cards',null],
    ['profile-placement','#detail-placement','.detail-grid > article','h3'],
    ['profile-pacing','#detail-pacing','.detail-grid > article','h3'],
    ['profile-splits','#detail-content .split-section','.split-section','h3'],
    ['runner-replay','#detail-content [data-runner-replay] .replay-top','.replay-top','h3'],
    ['journey-gap','#detail-content [data-journey-gap]','.journey-card','h4'],
    ['journey-placement','#detail-content [data-journey-placement-chart]','.journey-card','h4'],
    ['journey-pacing','#detail-content .journey-pacing','.journey-pacing','h4'],
    ['map-duel','.duel-dialog-header, .map-page-topbar',null,'.duel-dialog-heading strong, .map-page-heading strong'],
    ['results-database','#results','#results','h2'],
    ['data-principles','.data-note','.data-note',null]
  ];
  const registry=()=>window.GAnalysisHelpContent||{};
  const esc=value=>String(value??'').replace(/[&<>"]/g,character=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[character]));
  const entry=id=>Object.prototype.hasOwnProperty.call(registry(),id)?registry()[id]:null;
  const has=id=>Boolean(entry(id));
  const button=(id,label)=>{const item=entry(id);if(!item){console.warn?.(`Unknown analysis help id: ${id}`);return''}return`<button type="button" class="analysis-help-button" data-analysis-help="${esc(id)}" aria-label="${esc(label||`Information om ${item.title}`)}">${ICON}</button>`};
  let trigger=null,scheduled=false,observer=null;
  function ensureDialog(){
    let dialog=document.getElementById('analysis-help-dialog');if(dialog)return dialog;
    dialog=document.createElement('dialog');dialog.id='analysis-help-dialog';dialog.className='analysis-help-dialog';dialog.setAttribute('aria-labelledby','analysis-help-title');
    dialog.innerHTML='<div class="analysis-help-shell"><header class="analysis-help-header"><div><p class="eyebrow ink">OM DEN HÄR ANALYSEN</p><h2 id="analysis-help-title"></h2></div><button type="button" class="analysis-help-close analysis-help-close-x" aria-label="Stäng metodhjälp">×</button></header><div class="analysis-help-body" data-analysis-help-body></div><footer class="analysis-help-footer"><button type="button" class="button analysis-help-close">Stäng</button></footer></div>';
    dialog.querySelectorAll('.analysis-help-close').forEach(control=>control.addEventListener('click',close));
    dialog.addEventListener('cancel',event=>event.stopPropagation());
    dialog.addEventListener('click',event=>{if(event.target===dialog)close()});
    dialog.addEventListener('close',()=>{const previous=trigger;trigger=null;if(previous?.isConnected)queueMicrotask(()=>previous.focus())});
    document.body.append(dialog);return dialog;
  }
  function open(id,source){const item=entry(id);if(!item){console.warn?.(`Unknown analysis help id: ${id}`);return false}const dialog=ensureDialog(),body=dialog.querySelector('[data-analysis-help-body]');trigger=source||document.activeElement;dialog.querySelector('#analysis-help-title').textContent=item.title;body.innerHTML=item.html;body.scrollTop=0;if(!dialog.open)dialog.showModal();dialog.querySelector('.analysis-help-close-x').focus();return true}
  function close(){const dialog=document.getElementById('analysis-help-dialog');if(dialog?.open)dialog.close()}
  function mount(target,id,hostSelector,titleSelector){
    const host=hostSelector?(target.matches?.(hostSelector)?target:target.closest?.(hostSelector)):target;if(!host||host.querySelector?.(`[data-analysis-help="${id}"]`))return;
    const title=titleSelector?host.querySelector(titleSelector):null;if(title){let wrapper=title.parentElement?.classList?.contains('analysis-title-with-help')?title.parentElement:null;if(!wrapper){wrapper=document.createElement('div');wrapper.className='analysis-title-with-help';title.replaceWith(wrapper);wrapper.append(title)}wrapper.insertAdjacentHTML('beforeend',button(id));return}
    host.classList?.add('analysis-help-host');const holder=document.createElement('div');holder.className='analysis-help-floating';holder.innerHTML=button(id);host.append(holder);
  }
  function enhance(root=document){for(const [id,selector,hostSelector,titleSelector] of TARGETS){const nodes=[];if(root.matches?.(selector))nodes.push(root);root.querySelectorAll?.(selector).forEach(node=>nodes.push(node));nodes.forEach(node=>mount(node,id,hostSelector,titleSelector))}}
  function scheduleEnhance(){if(scheduled)return;scheduled=true;queueMicrotask(()=>{scheduled=false;enhance(document)})}
  function init(){enhance(document);document.addEventListener('click',event=>{const control=event.target.closest?.('[data-analysis-help]');if(!control)return;event.preventDefault();event.stopPropagation();open(control.dataset.analysisHelp,control)});if(typeof MutationObserver!=='undefined'){observer=new MutationObserver(scheduleEnhance);observer.observe(document.body,{childList:true,subtree:true})}}
  const usedIds=()=>[...new Set(TARGETS.map(([id])=>id))];
  const validate=()=>{const registryIds=Object.keys(registry()),used=usedIds();return{registryIds,usedIds:used,missing:registryIds.filter(id=>!used.includes(id)),unknown:used.filter(id=>!registryIds.includes(id))}};
  window.GAnalysisHelp={button,open,close,entry,has,enhance,usedIds,validate,targets:TARGETS.map(item=>item.slice())};
  if(typeof document!=='undefined'){if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init()}
})();
