(function(){
  'use strict';
  const KEY='race-analysis:favorites-v1';
  const ICON='<svg class="favorite-icon" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" focusable="false"><path d="m12 2.8 2.8 5.7 6.3.9-4.6 4.4 1.1 6.2-5.6-2.9L6.4 20l1.1-6.2-4.6-4.4 6.3-.9L12 2.8Z" fill="currentColor" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/></svg>';
  function create({storage,key=KEY,legacyKeys=[]}={}){
    let ids=[];
    const target=storage===undefined?(()=>{try{return window.localStorage}catch{return null}})():storage;
    let migrated=false;
    try{let raw=target?.getItem(key);if(raw===null||raw===undefined){for(const legacyKey of legacyKeys){raw=target?.getItem(legacyKey);if(raw!==null&&raw!==undefined){migrated=true;break}}}const parsed=JSON.parse(raw||'[]');if(Array.isArray(parsed))ids=[...new Set(parsed.filter(id=>typeof id==='string'&&id.includes(':')))]}catch{}
    const save=()=>{try{target?.setItem(key,JSON.stringify(ids))}catch{}}
    if(migrated)save();
    const api={
      has:id=>ids.includes(id),
      add(id){if(typeof id==='string'&&id.includes(':')&&!ids.includes(id)){ids.push(id);save()}return api.has(id)},
      remove(id){const next=ids.filter(item=>item!==id),changed=next.length!==ids.length;ids=next;if(changed)save();return changed},
      toggle(id){return api.has(id)?(api.remove(id),false):api.add(id)},
      all:()=>ids.slice(),
      forRace:raceKey=>ids.filter(id=>id.startsWith(`${raceKey}:`)),
      prune(validIds){const valid=new Set(validIds),next=ids.filter(id=>valid.has(id)),changed=next.length!==ids.length;ids=next;if(changed)save();return changed}
    };
    return api;
  }
  window.GFavorites={KEY,ICON,create};
})();
