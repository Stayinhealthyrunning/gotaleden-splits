(function(root,factory){
  const api=factory();
  if(typeof module!=='undefined')module.exports=api;
  root.GFutureEditionFixture=api;
})(typeof window!=='undefined'?window:globalThis,function(){
  'use strict';
  const courseVersions={
    'route-alpha':{key:'route-alpha',whole_course_comparison_group:'shared-route',assets:{route:'data/test-courses/route-alpha/route.json',elevation:'data/test-courses/route-alpha/elevation.json'},segments:[{key:'alpha-opening',from:'alpha-start',to:'alpha-middle',course_version:'route-alpha',comparison_key:'shared-opening'},{key:'alpha-closing',from:'alpha-middle',to:'alpha-finish',course_version:'route-alpha'}]},
    'route-beta':{key:'route-beta',whole_course_comparison_group:'shared-route',assets:{route:'data/test-courses/route-beta/route.json',elevation:'data/test-courses/route-beta/elevation.json'},segments:[{key:'beta-opening',from:'beta-start',to:'beta-middle',course_version:'route-beta',comparison_key:'shared-opening'},{key:'beta-closing',from:'beta-middle',to:'beta-finish',course_version:'route-beta'}]},
    'route-gamma':{key:'route-gamma',whole_course_comparison_group:null,assets:{route:'data/test-courses/route-gamma/route.json',elevation:'data/test-courses/route-gamma/elevation.json'},segments:[{key:'gamma-opening',from:'gamma-start',to:'gamma-middle',course_version:'route-gamma'},{key:'gamma-closing',from:'gamma-middle',to:'gamma-finish',course_version:'route-gamma'}]},
  };
  const editions=[
    ['solo-before','solo-family',2031,'2031-05-03','route-alpha','individual','source-before','Solo'],
    ['solo-future','solo-family',2033,'2033-05-05','route-beta','individual','source-future','Solo'],
    ['solo-incompatible','solo-family',2034,'2034-05-04','route-gamma','individual','source-future','Solo'],
    ['team-before','team-family',2031,'2031-06-07','route-alpha','relay','source-before','Team'],
    ['team-future','team-family',2033,'2033-06-09','route-alpha','relay','source-future','Team'],
  ];
  const planned=['solo-planned','solo-family',2035,'2035-05-06','route-beta','individual',null,'Solo'];
  const keysFor=version=>{const token=version.split('-').at(-1);return{start:`${token}-start`,middle:`${token}-middle`,finish:`${token}-finish`}};
  const checkpoints=version=>{const keys=keysFor(version);return[
    {key:keys.start,name:'Start',route_distance_km:0,race_distance_km:0,analysis_boundary:true,replay_anchor:true},
    {key:keys.middle,name:'Middle',route_distance_km:1,race_distance_km:1,analysis_boundary:true,replay_anchor:true},
    {key:keys.finish,name:'Finish',route_distance_km:2,race_distance_km:2,analysis_boundary:true,replay_anchor:true},
  ]};
  function identity(index,raceKey){
    if(index===1)return{person_key:'verified-global-runner',identity_status:'verified',identity_scope:'provider',name:'Verified Global'};
    if(index===2)return{person_key:`source-scoped-${raceKey}`,identity_status:'verified',identity_scope:'source_event',name:'Source Scoped'};
    if(index===3)return{person_key:`local-${raceKey}`,identity_status:'local',identity_scope:'race_edition',name:'Local Runner'};
    if(index===4)return{person_key:`same-name-${raceKey}`,identity_status:'verified',identity_scope:'provider',name:'Same Name'};
    return{person_key:`runner-${raceKey}-${index}`,identity_status:'verified',identity_scope:'provider',name:`Runner ${index}`};
  }
  function catalogEntry([raceKey,family,year,raceDate,courseVersion,type,sourceEvent,section],status='available'){
    const team=type==='relay';return{race_key:raceKey,event_key:'portable-fixture-event',race_family:family,year,race_date:raceDate,course_version:courseVersion,type,section,data_status:status,source_available:status==='available',analyzable:status==='available',source_event_key:sourceEvent,participant:{entity:team?'team':'person',singular:team?'lag':'löpare',plural:team?'lag':'deltagare',profile_label:team?'LAGANALYS':'LÖPARANALYS',possessive:team?'Lagets':'Löparens'},competition:{format:team?'stage-team':'solo',team_structure:{kind:team?'sequential':'none',leg_count:team?2:undefined,member_assignment:'unknown'}},capabilities:{goal_pace:!team,sex_filter:!team,age_analysis:!team,club_analysis:!team,person_history:!team,team_members:team,class_analysis:true,segment_analysis:true,replay:true,head_to_head:true},goal_pace:team?null:{minimum_seconds:3600,maximum_seconds:21600,default_seconds:7200},ui_labels:{navigation:team?'Lag':'Löpare',saved:team?'Sparade lag':'Sparade löpare',class:team?'Lagklass':'Klass'},presentation:{distance_label:'2 km',finish_label:'Finish',hero_eyebrow:'START · FINISH',route_stops:[{label:'Start',role:'start'},{label:'Middle'},{label:'Finish',role:'finish'}]}};
  }
  function raceData(edition,offset){
    const [raceKey,family,year,raceDate,courseVersion,type,sourceEvent,section]=edition,relay=type==='relay',keys=keysFor(courseVersion),records=[],splits=[];
    for(let index=1;index<=7;index++){
      const status=index===7?'DNF':'FINISHED',person=relay?{person_key:null,identity_status:null,identity_scope:null,name:'Shared Team'}:identity(index,raceKey),finish=status==='FINISHED'?7200+offset*120+index*30:null;
      records.push({source_result_id:index===2?'reused-source-result':`${raceKey}:${index}`,bib:String(index),entity_type:relay?'team':'athlete',name:person.name,person_key:person.person_key,identity_status:person.identity_status,identity_scope:person.identity_scope,sex:relay?null:index%2?'F':'M',class_name:relay?'Open':index%2?'Women':'Men',club:relay?null:'Fixture Club',status,finish_seconds:finish,overall_place:status==='FINISHED'?index:null,class_place:status==='FINISHED'?index:null});
      const middle=3500+offset*60+index*12;splits.push({race_key:raceKey,bib:String(index),checkpoint:keys.middle,elapsed_seconds:middle});
      if(status==='FINISHED')splits.push({race_key:raceKey,bib:String(index),checkpoint:keys.finish,elapsed_seconds:finish});
    }
    return{race:{...catalogEntry(edition),nominal_distance_km:2,gpx_distance_km:2,route_start_distance_km:0,route_end_distance_km:2,records},checkpoints:checkpoints(courseVersion),splits};
  }
  function routeAsset(version,index){return{course_version:version,points:[[57.70+index*.01,12.20,20,0],[57.705+index*.01,12.21,25,1],[57.71+index*.01,12.22,30,2]],full_distance_km:2}}
  function create(){
    const data={meta:{project:'Future edition test fixture',event:{event_key:'portable-fixture-event',name:'Portable Fixture',product_title:'Portable Analysis',short_name:'Portable',official_site_url:'https://example.test',storage_namespace:'portable-fixture',custom_event_namespace:'portable-fixture',presentation:{title_lead:'Portable',title_accent:'Analysis',hero_lead:'A generic history fixture.'}}},courses:courseVersions,race_catalog:{},races:{},checkpoints:{},splits:[],teams:[],team_members:[]},assets={};
    editions.forEach((edition,index)=>{const built=raceData(edition,index);data.race_catalog[edition[0]]=catalogEntry(edition);data.races[edition[0]]=built.race;data.checkpoints[edition[0]]=built.checkpoints;data.splits.push(...built.splits)});
    data.race_catalog[planned[0]]=catalogEntry(planned,'planned');
    Object.keys(courseVersions).forEach((version,index)=>{const entry=courseVersions[version],route=routeAsset(version,index),elevation={course_version:version,points:[{route_distance_km:0,elevation_m:20},{route_distance_km:1,elevation_m:25},{route_distance_km:2,elevation_m:30}]};assets[entry.assets.route]=route;assets[entry.assets.elevation]=elevation});
    return{data,assets};
  }
  return{create};
});
