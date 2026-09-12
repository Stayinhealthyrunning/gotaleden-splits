(function(){
  'use strict';

  const finite=value=>value!==null&&value!==undefined&&value!==''&&Number.isFinite(Number(value));
  const unique=values=>[...new Set(values)].sort((a,b)=>typeof a==='number'&&typeof b==='number'?a-b:String(a).localeCompare(String(b)));
  const present=(value,extra={})=>({available:true,value,...extra});
  const missing=(reason,extra={})=>({available:false,value:null,reason,...extra});
  const editionOrder=(a,b)=>{
    if(a.raceDate&&b.raceDate){const dates=String(a.raceDate).localeCompare(String(b.raceDate));if(dates)return dates}
    return Number(a.year??Number.MAX_SAFE_INTEGER)-Number(b.year??Number.MAX_SAFE_INTEGER)||a.raceKey.localeCompare(b.raceKey);
  };

  function create(adapter){
    if(!adapter?.races||!adapter?.raceCatalog)throw new Error('GHistoryEngine requires a GDataAdapter instance.');

    const catalogByKey=new Map();
    const familyIndex=new Map();
    const personIndex=new Map();
    const summaryCache=new Map();

    function normalizeCatalog(key,source={}){
      const race=adapter.race(key);
      return{
        raceKey:key,
        eventKey:source.event_key??race?.eventKey??null,
        family:source.race_family??race?.family??null,
        year:finite(source.year??race?.year)?Number(source.year??race.year):null,
        raceDate:source.race_date??race?.raceDate??null,
        type:source.type??race?.type??null,
        courseVersion:source.course_version??race?.courseVersion??null,
        dataStatus:source.data_status??race?.dataStatus??'available',
        analyzable:Boolean(race&&source.analyzable!==false&&race.analyzable!==false),
        sourceEvent:source.source_event_key??race?.sourceEventKey??null,
        sourceAvailable:source.source_available??Boolean(race),
        nominalDistanceKm:finite(source.nominal_distance_km??race?.nominalDistanceKm)?Number(source.nominal_distance_km??race.nominalDistanceKm):null,
        gpxDistanceKm:finite(source.gpx_distance_km??race?.distanceKm)?Number(source.gpx_distance_km??race.distanceKm):null,
      };
    }

    for(const [key,source] of adapter.raceCatalog)catalogByKey.set(key,normalizeCatalog(key,source));
    for(const [key] of adapter.races)if(!catalogByKey.has(key))catalogByKey.set(key,normalizeCatalog(key));
    for(const edition of catalogByKey.values()){
      if(!familyIndex.has(edition.family))familyIndex.set(edition.family,[]);
      familyIndex.get(edition.family).push(edition);
    }
    for(const values of familyIndex.values())values.sort(editionOrder);

    for(const race of adapter.races.values())for(const record of race.records){
      if(record.isTeam||!record.personKey)continue;
      if(!personIndex.has(record.personKey))personIndex.set(record.personKey,[]);
      personIndex.get(record.personKey).push(record);
    }

    function families(){
      return[...familyIndex].map(([family,values])=>({family,editionCount:values.length,years:unique(values.map(item=>item.year).filter(finite))})).sort((a,b)=>a.family.localeCompare(b.family));
    }

    function editions(family,options={}){
      const includePlanned=options.includePlanned!==false;
      return(familyIndex.get(family)||[]).filter(item=>includePlanned||item.dataStatus!=='planned').map(item=>({...item}));
    }

    function availability(edition,race){
      if(edition.dataStatus==='planned')return{status:'planned',available:false,analyzable:false,reason:'edition_planned'};
      if(!race)return{status:'missing',available:false,analyzable:false,reason:'edition_data_missing'};
      if(!edition.analyzable)return{status:'available_not_analyzable',available:true,analyzable:false,reason:'edition_not_analyzable'};
      return{status:'analyzable',available:true,analyzable:true,reason:null};
    }

    function selectedRecords(race,filters={}){
      if(!race)return[];
      const normalized={...filters};
      if(race.isTeam)delete normalized.sex;
      if(normalized.class&&!normalized.className)normalized.className=normalized.class;
      delete normalized.class;
      return adapter.filtered?adapter.filtered(race.key,normalized):race.records.filter(record=>(!normalized.sex||record.sex===normalized.sex)&&(!normalized.className||record.class_name===normalized.className)&&(!normalized.status||record.status===normalized.status));
    }

    function editionSummary(raceKey,filters={}){
      const cacheable=!Object.keys(filters).length;
      if(cacheable&&summaryCache.has(raceKey))return summaryCache.get(raceKey);
      const edition=catalogByKey.get(raceKey);
      if(!edition)return null;
      const race=adapter.race(raceKey),state=availability(edition,race),records=state.available?selectedRecords(race,filters):null;
      const starters=records?.filter(adapter.statusStarter)??null;
      const finishers=records?.filter(adapter.statusFinished)??null;
      const dnf=records?.filter(record=>String(record.status||'').toUpperCase()==='DNF')??null;
      const dns=records?.filter(record=>String(record.status||'').toUpperCase()==='DNS')??null;
      const distribution=state.analyzable?adapter.distributionSummary(finishers.map(record=>record.finish_seconds)):null;
      const performanceReason=!state.analyzable?state.reason:!distribution?.available?'insufficient_finish_samples':null;
      const result={
        ...edition,
        availability:state,
        records:records?.length??null,
        starters:starters?.length??null,
        finishers:finishers?.length??null,
        dnf:dnf?.length??null,
        dns:dns?.length??null,
        finishRate:starters?.length?finishers.length/starters.length:null,
        dnfRate:starters?.length?dnf.length/starters.length:null,
        finishTime:distribution?.available?{
          available:true,reason:null,sampleSize:distribution.n,median:distribution.median,
          q25:distribution.q25,q75:distribution.q75,bandAvailable:distribution.bandAvailable,
        }:{available:false,reason:performanceReason,sampleSize:distribution?.n??0,median:null,q25:null,q75:null,bandAvailable:false},
      };
      if(cacheable)summaryCache.set(raceKey,result);
      return result;
    }

    function comparability(firstRaceKey,secondRaceKey){
      const first=catalogByKey.get(firstRaceKey),second=catalogByKey.get(secondRaceKey);
      if(!first||!second)return{value:'incomparable',reason:'edition_missing'};
      if(first.family!==second.family)return{value:'incomparable',reason:'race_family_mismatch'};
      const value=adapter.courseComparability(first,second);
      return{value,reason:value==='incomparable'?'course_incomparable':null};
    }

    function delta(first,second,key){
      const a=first?.[key],b=second?.[key];
      return finite(a)&&finite(b)?{available:true,first:Number(a),second:Number(b),delta:Number(b)-Number(a),reason:null}:missing('metric_missing',{first:finite(a)?Number(a):null,second:finite(b)?Number(b):null,delta:null});
    }

    function compareEditions(firstRaceKey,secondRaceKey,filters={}){
      const first=editionSummary(firstRaceKey,filters),second=editionSummary(secondRaceKey,filters);
      if(!first||!second)return null;
      const course=comparability(firstRaceKey,secondRaceKey);
      const participation={};
      for(const key of ['records','starters','finishers','dnf','dns','finishRate','dnfRate'])participation[key]=delta(first,second,key);
      const courseAllowed=course.value==='exact'||course.value==='compatible';
      const finishReady=first.finishTime.available&&second.finishTime.available;
      const reason=!courseAllowed?(course.reason||'course_incomparable'):!finishReady?(first.finishTime.reason||second.finishTime.reason||'metric_missing'):null;
      const medianFinishSeconds=courseAllowed&&finishReady?{
        available:true,first:first.finishTime.median,second:second.finishTime.median,
        delta:second.finishTime.median-first.finishTime.median,reason:null,
      }:missing(reason,{first:finishReady?first.finishTime.median:null,second:finishReady?second.finishTime.median:null,delta:null});
      const allowedMetrics=Object.entries(participation).filter(([,metric])=>metric.available).map(([key])=>key);
      if(medianFinishSeconds.available)allowedMetrics.push('medianFinishSeconds');
      return{
        first,second,comparability:course.value,reason:course.reason,
        participation,
        performance:{available:medianFinishSeconds.available,comparability:course.value,medianFinishSeconds,reason},
        allowedMetrics,
        blockedMetrics:medianFinishSeconds.available?[]:[{metric:'medianFinishSeconds',reason}],
      };
    }

    function familySeries(family,options={}){
      const referenceKey=options.referenceRaceKey||null;
      const reference=referenceKey?catalogByKey.get(referenceKey):null;
      if(referenceKey&&!reference)throw new Error('Unknown reference edition.');
      if(reference&&reference.family!==family)throw new Error('Reference edition belongs to another race family.');
      return{
        family,
        referenceRaceKey:referenceKey,
        observations:editions(family,options).map(edition=>{
          const summary=editionSummary(edition.raceKey,options.filters||{});
          if(!referenceKey)return{...summary,referenceComparability:null,comparablePerformance:missing('reference_not_requested')};
          const course=comparability(referenceKey,edition.raceKey),allowed=course.value!=='incomparable'&&summary.finishTime.available;
          return{
            ...summary,
            referenceComparability:course.value,
            comparablePerformance:allowed?present(summary.finishTime.median,{comparability:course.value,sampleSize:summary.finishTime.sampleSize}):missing(course.value==='incomparable'?(course.reason||'course_incomparable'):summary.finishTime.reason,{comparability:course.value}),
          };
        }),
      };
    }

    function courseSegment(courseVersion,segmentKey){
      return(adapter.data.courses?.[courseVersion]?.segments||[]).find(segment=>segment.key===segmentKey)||null;
    }

    function matchingSegment(reference,courseVersion){
      const candidates=adapter.data.courses?.[courseVersion]?.segments||[];
      if(reference.course_version===courseVersion)return candidates.find(segment=>segment.key===reference.key)||null;
      if(!reference.comparison_key)return null;
      return candidates.find(segment=>segment.comparison_key===reference.comparison_key)||null;
    }

    function segmentSeries(family,options={}){
      const referenceRaceKey=options.referenceRaceKey,segmentKey=options.segmentKey;
      const referenceEdition=catalogByKey.get(referenceRaceKey);
      if(!referenceEdition||referenceEdition.family!==family)throw new Error('A reference edition in the requested family is required.');
      const reference=courseSegment(referenceEdition.courseVersion,segmentKey);
      if(!reference)throw new Error('Unknown reference segment.');
      const filters=options.filters||{};
      return{
        family,referenceRaceKey,segmentKey,
        observations:editions(family,options).map(edition=>{
          const candidate=matchingSegment(reference,edition.courseVersion);
          const segmentComparison=candidate?adapter.segmentComparability(reference,candidate):'incomparable';
          const race=adapter.race(edition.raceKey),state=availability(edition,race);
          if(segmentComparison==='incomparable')return{raceKey:edition.raceKey,year:edition.year,courseVersion:edition.courseVersion,segment:null,comparability:'incomparable',sampleSize:0,cohortSize:0,pace:missing('segment_incomparable')};
          if(!state.analyzable)return{raceKey:edition.raceKey,year:edition.year,courseVersion:edition.courseVersion,segment:candidate,comparability:segmentComparison,sampleSize:0,cohortSize:0,pace:missing(state.reason)};
          const selected=new Set(selectedRecords(race,filters).map(record=>record.id));
          const group=adapter.segmentGroupDistribution(race,record=>selected.has(record.id));
          const distribution=group.segments.find(item=>item.from===candidate.from&&item.to===candidate.to)?.pace;
          if(!distribution)return{raceKey:edition.raceKey,year:edition.year,courseVersion:edition.courseVersion,segment:candidate,comparability:segmentComparison,sampleSize:0,cohortSize:group.count,pace:missing('segment_not_in_edition')};
          const pace=distribution?.available?{
            available:true,reason:null,median:distribution.median,q25:distribution.q25,q75:distribution.q75,
            q10:distribution.q10,q90:distribution.q90,bandAvailable:distribution.bandAvailable,
            outerAvailable:distribution.outerAvailable,sampleSize:distribution.n,
          }:{available:false,reason:'insufficient_segment_samples',median:null,q25:null,q75:null,q10:null,q90:null,bandAvailable:false,outerAvailable:false,sampleSize:distribution?.n??0};
          return{raceKey:edition.raceKey,year:edition.year,courseVersion:edition.courseVersion,segment:candidate,comparability:segmentComparison,sampleSize:distribution?.n??0,cohortSize:group.count,pace};
        }),
      };
    }

    function appearance(record){
      const race=adapter.race(record.raceKey);
      return{
        id:record.id,personKey:record.personKey,raceKey:race.key,family:race.family,year:race.year,
        raceDate:race.raceDate,courseVersion:race.courseVersion,bib:record.bib,publishedName:record.name,
        status:record.status,finishTime:adapter.statusFinished(record)?Number(record.finish_seconds):null,
        identityStatus:record.identityStatus,identityScope:record.identityScope,
      };
    }

    function personHistory(personKey){
      const appearances=(personIndex.get(personKey)||[]).map(appearance).sort(editionOrder);
      return{
        personKey,appearances,appearanceCount:appearances.length,
        editionCount:new Set(appearances.map(item=>item.raceKey)).size,
        families:unique(appearances.map(item=>item.family)),
        years:unique(appearances.map(item=>item.year).filter(finite)),
      };
    }

    function compareAppearances(firstId,secondId){
      const first=adapter.record(firstId),second=adapter.record(secondId);
      if(!first||!second)return null;
      const samePerson=Boolean(first.personKey&&first.personKey===second.personKey&&!first.isTeam&&!second.isTeam);
      const course=comparability(first.raceKey,second.raceKey);
      const finishTimeComparisonAllowed=samePerson&&course.value!=='incomparable'&&adapter.statusFinished(first)&&adapter.statusFinished(second);
      return{
        first:appearance(first),second:appearance(second),samePerson,
        wholeCourseComparability:course.value,
        finishTimeComparisonAllowed,
        finishTimeDelta:finishTimeComparisonAllowed?Number(second.finish_seconds)-Number(first.finish_seconds):null,
        reason:!samePerson?'identity_mismatch':course.value==='incomparable'?(course.reason||'course_incomparable'):!adapter.statusFinished(first)||!adapter.statusFinished(second)?'finish_time_missing':null,
      };
    }

    function repeatParticipants(options={}){
      const minimumEditions=Number(options.minimumEditions||2),minimumYears=Number(options.minimumYears||2);
      return[...personIndex.keys()].map(personHistory).filter(item=>item.editionCount>=minimumEditions&&item.years.length>=minimumYears&&item.appearances.every(appearance=>appearance.identityStatus==='verified'&&appearance.identityScope!=='race_edition')).sort((a,b)=>b.editionCount-a.editionCount||a.personKey.localeCompare(b.personKey));
    }

    return{
      families,editions,editionSummary,compareEditions,familySeries,segmentSeries,
      personHistory,compareAppearances,repeatParticipants,
    };
  }

  window.GHistoryEngine={create};
})();
