(function(){
  'use strict';
  function create(catalog,{version='course-assets-v1',fetchJson=null}={}){
    const entries=catalog||{},cache=new Map(),loadJson=fetchJson||((path)=>fetch(`${path}?v=${version}`,{cache:'no-store'}).then(response=>{if(!response.ok)throw new Error(`${path}: HTTP ${response.status}`);return response.json()}));
    async function load(courseVersion){
      const entry=entries[courseVersion];
      if(!entry)throw new Error(`CourseVersion ${courseVersion||'<missing>'} saknas i course-katalogen.`);
      if(!cache.has(courseVersion)){
        const routePath=entry.assets?.route,elevationPath=entry.assets?.elevation;
        if(!routePath||!elevationPath)throw new Error(`CourseVersion ${courseVersion} saknar assetreferenser.`);
        cache.set(courseVersion,Promise.all([loadJson(routePath),loadJson(elevationPath)]).then(([route,elevation])=>{
          if(route?.course_version&&route.course_version!==courseVersion)throw new Error(`Ruttasset för ${courseVersion} har fel versionsidentitet.`);
          if(entry.fingerprint&&route?.fingerprint!==entry.fingerprint)throw new Error(`Ruttasset för ${courseVersion} har fel fingerprint.`);
          return{route,elevation};
        }).catch(error=>{cache.delete(courseVersion);throw error}));
      }
      return cache.get(courseVersion);
    }
    return{load,has:courseVersion=>cache.has(courseVersion),catalog:entries};
  }
  window.GCourseData={create};
})();
