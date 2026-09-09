(function(){
  'use strict';
  const SECTIONS=['runner-lookup','map-duel','goal-pace','overview','statistics','gender','age-analysis','segments','history','clubs','results'];

  function parse(search,{raceExists,storedRace,defaultRace='individual-75-2026'}={}){
    const params=new URLSearchParams(search||''),requested=params.get('race');
    const raceKey=raceExists?.(requested)?requested:raceExists?.(storedRace)?storedRace:defaultRace;
    return{
      params,
      raceKey,
      unit:params.get('unit')==='speed'?'speed':'pace',
      activeSection:SECTIONS.includes(params.get('section'))?params.get('section'):'runner-lookup',
      filters:{sex:params.get('sex')||'',className:params.get('class')||'',status:params.get('status')||'',club:params.get('club')||''},
      runnerBib:params.get('runner')||null,
      duelBibs:(params.get('duel')||'').split(',').filter(Boolean).slice(0,5)
    };
  }

  function url(href,state,filters={}){
    const next=new URL(href);next.search='';next.searchParams.set('race',state.raceKey);
    if(state.activeSection&&state.activeSection!=='overview')next.searchParams.set('section',state.activeSection);
    if(filters.sex)next.searchParams.set('sex',filters.sex);if(filters.className)next.searchParams.set('class',filters.className);if(filters.status)next.searchParams.set('status',filters.status);if(filters.club)next.searchParams.set('club',filters.club);
    if(state.unit!=='pace')next.searchParams.set('unit',state.unit);if(state.selectedRecordId)next.searchParams.set('runner',state.selectedRecordId.split(':').at(-1));if(state.duelIds?.length)next.searchParams.set('duel',state.duelIds.map(id=>id.split(':').at(-1)).join(','));
    return next.href;
  }

  function visibleSection(sections,offset,fallback='runner-lookup'){
    let active=fallback;for(const section of sections){if(section&&!section.hidden&&section.offsetTop<=offset)active=section.id}return active;
  }

  window.GAppState={SECTIONS,parse,url,visibleSection};
})();
