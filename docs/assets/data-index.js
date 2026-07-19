(function(){
  function create(data){
    const splitMap=new Map(),teamMap=new Map(),assignmentMap=new Map();
    for(const split of data.splits){const key=`${split.race_key}:${split.bib}`;if(!splitMap.has(key))splitMap.set(key,[]);splitMap.get(key).push(split)}
    for(const values of splitMap.values())values.sort((a,b)=>a.elapsed_seconds-b.elapsed_seconds);
    for(const team of data.teams)teamMap.set(`${team.race_key}:${team.bib}`,team);
    for(const item of data.relay_leg_assignments){const key=`${item.race_key}:${item.team_bib}`;if(!assignmentMap.has(key))assignmentMap.set(key,[]);assignmentMap.get(key).push(item)}
    for(const values of assignmentMap.values())values.sort((a,b)=>a.leg_no-b.leg_no);
    return{splits:(race,bib)=>splitMap.get(`${race}:${bib}`)||[],team:(race,bib)=>teamMap.get(`${race}:${bib}`),assignments:(race,bib)=>assignmentMap.get(`${race}:${bib}`)||[]};
  }
  window.GDataIndex={create};
})();
