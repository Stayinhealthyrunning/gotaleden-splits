(function(){
  'use strict';

  const courseDefinitions={
    'course-a':{
      key:'course-a',whole_course_comparison_group:'shared-course-group',
      segments:[
        {key:'opening-a',from:'start-a',to:'middle-a',course_version:'course-a',comparison_key:'shared-opening'},
        {key:'closing-a',from:'middle-a',to:'finish-a',course_version:'course-a'},
      ],
    },
    'course-b':{
      key:'course-b',whole_course_comparison_group:'shared-course-group',
      segments:[
        {key:'opening-b',from:'start-b',to:'middle-b',course_version:'course-b',comparison_key:'shared-opening'},
        {key:'closing-b',from:'middle-b',to:'finish-b',course_version:'course-b'},
      ],
    },
    'course-c':{
      key:'course-c',whole_course_comparison_group:null,
      segments:[
        {key:'opening-c',from:'start-c',to:'middle-c',course_version:'course-c'},
        {key:'closing-c',from:'middle-c',to:'finish-c',course_version:'course-c'},
      ],
    },
  };

  const editions=[
    ['family-a-2024','family-a',2024,'2024-05-04','course-a','individual','source-a'],
    ['family-a-2025','family-a',2025,'2025-05-03','course-a','individual','source-b'],
    ['family-a-2026','family-a',2026,'2026-05-02','course-b','individual','source-c'],
    ['family-a-2027','family-a',2027,'2027-05-01','course-c','individual','source-d'],
    ['family-b-2025','family-b',2025,'2025-06-07','course-a','relay','source-b'],
    ['family-b-2027','family-b',2027,'2027-06-05','course-a','relay','source-d'],
  ];
  const planned=['family-a-2028-planned','family-a',2028,'2028-05-06','course-b','individual',null];

  function checkpointKeys(courseVersion){
    const suffix=courseVersion.at(-1);
    return{start:`start-${suffix}`,timing:`timing-${suffix}`,middle:`middle-${suffix}`,finish:`finish-${suffix}`};
  }

  function checkpoints(courseVersion){
    const keys=checkpointKeys(courseVersion);
    return[
      {key:keys.start,name:'Start',route_distance_km:0,race_distance_km:0,analysis_boundary:true,replay_anchor:true},
      {key:keys.timing,name:'Timing only',route_distance_km:.5,race_distance_km:.5,analysis_boundary:false,timing_only:true,replay_anchor:true},
      {key:keys.middle,name:'Middle',route_distance_km:1,race_distance_km:1,analysis_boundary:true,replay_anchor:true},
      {key:keys.finish,name:'Finish',route_distance_km:2,race_distance_km:2,analysis_boundary:true,replay_anchor:true},
    ];
  }

  function identity(index,raceKey,year){
    if(index===1)return{person_key:'person-provider-global',identity_status:'verified',identity_scope:'provider',name:'Global Runner'};
    if(index===2)return{person_key:`person-source-${year}`,identity_status:'verified',identity_scope:'source_event',name:'Source Scoped'};
    if(index===3)return{person_key:`person-local-${raceKey}`,identity_status:'local',identity_scope:'race_edition',name:'Local Runner'};
    if(index===4)return{person_key:`person-same-name-${raceKey}`,identity_status:'verified',identity_scope:'provider',name:'Same Name'};
    return{person_key:`person-${raceKey}-${index}`,identity_status:'verified',identity_scope:'provider',name:`Runner ${index}`};
  }

  function buildRace([raceKey,family,year,raceDate,courseVersion,type,sourceEvent],raceOffset){
    const keys=checkpointKeys(courseVersion),records=[],splits=[];
    for(let index=1;index<=8;index++){
      const relay=type==='relay',status=index===7?'DNF':index===8?'DNS':'FINISHED';
      const person=relay?{person_key:null,identity_status:null,identity_scope:null,name:'Same Team'}:identity(index,raceKey,year);
      const finish=status==='FINISHED'?1000+raceOffset*40+index*10:null;
      records.push({
        source_result_id:index===2?'shared-source-id':`${raceKey}:${index}`,
        bib:String(index),entity_type:relay?'team':'athlete',name:person.name,
        person_key:person.person_key,identity_status:person.identity_status,identity_scope:person.identity_scope,
        sex:relay?null:index%2?'F':'M',class_name:relay?'Open':index%2?'Women':'Men',club:relay?null:index<=4?'North Club':'South Club',
        status,finish_seconds:finish,overall_place:status==='FINISHED'?index:null,
      });
      if(status==='DNS')continue;
      const timing=360+raceOffset*10+index,middle=500+raceOffset*20+index*2;
      splits.push({race_key:raceKey,bib:String(index),checkpoint:keys.timing,elapsed_seconds:timing});
      if(index!==6)splits.push({race_key:raceKey,bib:String(index),checkpoint:keys.middle,elapsed_seconds:middle});
      if(status==='FINISHED')splits.push({race_key:raceKey,bib:String(index),checkpoint:keys.finish,elapsed_seconds:finish});
    }
    return{
      race:{
        race_key:raceKey,event_key:'portable-event',race_family:family,year,race_date:raceDate,
        course_version:courseVersion,data_status:'available',source_event_key:sourceEvent,analyzable:true,
        section:raceKey,type,nominal_distance_km:2,gpx_distance_km:2,
        route_start_distance_km:0,route_end_distance_km:2,records,
      },
      checkpoints:checkpoints(courseVersion),splits,
    };
  }

  function catalogEntry([raceKey,family,year,raceDate,courseVersion,type,sourceEvent],dataStatus='available'){
    return{
      race_key:raceKey,event_key:'portable-event',race_family:family,year,race_date:raceDate,
      course_version:courseVersion,type,section:raceKey,data_status:dataStatus,
      source_available:dataStatus==='available',analyzable:dataStatus==='available',source_event_key:sourceEvent,
    };
  }

  function create(){
    const data={meta:{project:'History fixture'},courses:courseDefinitions,race_catalog:{},races:{},checkpoints:{},splits:[],teams:[],team_members:[]};
    editions.forEach((edition,index)=>{
      const built=buildRace(edition,index);
      data.race_catalog[edition[0]]=catalogEntry(edition);
      data.races[edition[0]]=built.race;
      data.checkpoints[edition[0]]=built.checkpoints;
      data.splits.push(...built.splits);
    });
    data.race_catalog[planned[0]]=catalogEntry(planned,'planned');
    return{
      data,
      route:{points:[[0,0,0,0],[0,.005,0,.5],[0,.01,0,1],[0,.02,0,2]],full_distance_km:2},
      elevation:{points:[{route_distance_km:0,elevation_m:0},{route_distance_km:2,elevation_m:0}]},
    };
  }

  window.GHistoryFixture={create};
})();
