(function(){
  function create(data){
    const splitMap=new Map(),teamMap=new Map();
    for(const split of data.splits){const key=`${split.race_key}:${split.bib}`;if(!splitMap.has(key))splitMap.set(key,[]);splitMap.get(key).push(split)}
    for(const values of splitMap.values())values.sort((a,b)=>a.elapsed_seconds-b.elapsed_seconds);
    for(const team of data.teams)teamMap.set(`${team.race_key}:${team.bib}`,team);
    return{splits:(race,bib)=>splitMap.get(`${race}:${bib}`)||[],team:(race,bib)=>teamMap.get(`${race}:${bib}`)};
  }
  window.GDataIndex={create};
})();
