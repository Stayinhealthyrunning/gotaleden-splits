(function(){
  'use strict';
  const finite=value=>value!==null&&value!==undefined&&value!==''&&Number.isFinite(Number(value));
  const number=value=>finite(value)?Number(value):null;
  const median=values=>{const sorted=values.filter(finite).map(Number).sort((a,b)=>a-b);if(!sorted.length)return null;const middle=Math.floor(sorted.length/2);return sorted.length%2?sorted[middle]:(sorted[middle-1]+sorted[middle])/2};
  const quantile=(values,q)=>{const sorted=values.filter(finite).map(Number).sort((a,b)=>a-b);if(!sorted.length)return null;const index=(sorted.length-1)*q,low=Math.floor(index),high=Math.ceil(index);return sorted[low]+(sorted[high]-sorted[low])*(index-low)};
  const average=values=>{const valid=values.filter(finite).map(Number);return valid.length?valid.reduce((sum,value)=>sum+value,0)/valid.length:null};
  function distributionSummary(values){
    const valid=(values||[]).filter(finite).map(Number),n=valid.length,available=n>=5,bandAvailable=n>=10,outerAvailable=n>=20;
    return{n,median:available?median(valid):null,q25:bandAvailable?quantile(valid,.25):null,q75:bandAvailable?quantile(valid,.75):null,q10:outerAvailable?quantile(valid,.1):null,q90:outerAvailable?quantile(valid,.9):null,available,bandAvailable,outerAvailable,smallSample:available&&!bandAvailable,message:!available?'För litet underlag':!bandAvailable?'Litet underlag':''};
  }
  const statusFinished=record=>record?.status==='FINISHED'&&finite(record.finish_seconds)&&Number(record.finish_seconds)>0;
  const statusStarter=record=>!['DNS'].includes(String(record?.status||'').toUpperCase());
  const normalizeClubName=value=>String(value||'').trim().replace(/\s+/g,' ');
  const clubKey=value=>normalizeClubName(value).toLocaleLowerCase('sv');
  const MIN_REFERENCE_SIZE=5;
  const RELAY_CLASS_DEFINITIONS=Object.freeze({
    'Män':Object.freeze({id:'men',family:'men',shortLabel:'Män',fullLabel:'Män',ranked:true,competitionType:'competitive',color:'#2563eb',softColor:'#dbeafe'}),
    'Kvinnor':Object.freeze({id:'women',family:'women',shortLabel:'Kvinnor',fullLabel:'Kvinnor',ranked:true,competitionType:'competitive',color:'#db2777',softColor:'#fce7f3'}),
    'Mixed tävling - Minst hälften kvinnor':Object.freeze({id:'mixed-ranked',family:'mixed',shortLabel:'Mixed tävling',fullLabel:'Mixed tävling - Minst hälften kvinnor',ranked:true,competitionType:'competitive',color:'#7c3aed',softColor:'#ede9fe'}),
    'Mixed ej tävling - Fri fördelning':Object.freeze({id:'mixed-free',family:'mixed',shortLabel:'Mixed fri',fullLabel:'Mixed ej tävling - Fri fördelning',ranked:false,competitionType:'non_competitive',color:'#c56a16',softColor:'#fff1d6'})
  });
  const normalizeRelayClassName=value=>String(value||'').trim().replace(/\s+/g,' ');
  function relayClassMeta(value){const record=typeof value==='object'&&value?value:null,name=normalizeRelayClassName(record?.class_name??value),base=RELAY_CLASS_DEFINITIONS[name]||{id:`other-${name.toLocaleLowerCase('sv').replace(/[^a-z0-9åäö]+/g,'-').replace(/^-|-$/g,'')||'unknown'}`,family:'other',shortLabel:name||'Klass saknas',fullLabel:name||'Klass saknas',ranked:true,competitionType:'competitive',color:'#66756f',softColor:'#edf1ef'},ranked=record&&record.class_is_ranked!==undefined&&record.class_is_ranked!==null?record.class_is_ranked===true||record.class_is_ranked===1||record.class_is_ranked==='true':base.ranked,competitionType=record?.class_competition_type||base.competitionType;return{...base,fullLabel:name||base.fullLabel,ranked:competitionType==='non_competitive'?false:ranked,competitionType}}

  function create(data,route,elevation){
    const races=new Map(),records=new Map(),splitsByResult=new Map(),teams=new Map(),profileCache=new Map(),referenceCache=new Map(),journeyReferenceCache=new Map();
    const elevationPoints=elevation?.profile||elevation?.points||[];
    for(const team of data.teams||[])teams.set(`${team.race_key}:${team.bib}`,team);
    for(const [raceKey,source] of Object.entries(data.races||{})){
      const checkpoints=(data.checkpoints?.[raceKey]||[]).map((checkpoint,index)=>({...checkpoint,index}));
      const checkpointMap=new Map(checkpoints.map(checkpoint=>[checkpoint.key,checkpoint]));
      const analysisCheckpoints=checkpoints.filter(checkpoint=>checkpoint.analysis_boundary!==false);
      const replayCheckpoints=checkpoints.filter(checkpoint=>checkpoint.replay_anchor!==false);
      const race={
        key:raceKey,
        section:source.section,
        type:source.type,
        isRelay:source.type==='relay',
        distanceKm:Number(source.gpx_distance_km),
        nominalDistanceKm:Number(source.nominal_distance_km),
        startDistanceKm:Number(checkpoints[0]?.route_distance_km||0),
        endDistanceKm:Number(checkpoints.at(-1)?.route_distance_km||route.full_distance_km),
        checkpoints,
        analysisCheckpoints,
        replayCheckpoints,
        checkpointMap,
        records:[]
      };
      for(const sourceRecord of source.records||[]){
        const id=`${raceKey}:${sourceRecord.bib}`;
        const record={...sourceRecord,class_name:race.isRelay?normalizeRelayClassName(sourceRecord.class_name):sourceRecord.class_name,id,raceKey,isRelay:race.isRelay,displayType:race.isRelay?'lag':'löpare'};
        race.records.push(record);records.set(id,record);
      }
      races.set(raceKey,race);
    }
    for(const split of data.splits||[]){
      const id=`${split.race_key}:${split.bib}`,race=races.get(split.race_key),checkpoint=race?.checkpointMap.get(split.checkpoint);
      if(!race||!checkpoint||!finite(split.elapsed_seconds)||Number(split.elapsed_seconds)<=0)continue;
      const normalized={...split,id:`${id}:${split.checkpoint}`,resultId:id,routeDistanceKm:Number(checkpoint.route_distance_km),raceDistanceKm:Number(checkpoint.race_distance_km)};
      if(!splitsByResult.has(id))splitsByResult.set(id,[]);
      splitsByResult.get(id).push(normalized);
    }
    for(const values of splitsByResult.values())values.sort((a,b)=>a.routeDistanceKm-b.routeDistanceKm||a.elapsed_seconds-b.elapsed_seconds);

    function race(key){return races.get(key)}
    function record(id){return records.get(id)}
    function resultSplits(value){return splitsByResult.get(typeof value==='string'?value:value?.id)||[]}
    function team(value){const item=typeof value==='string'?record(value):value;return item?.isRelay?teams.get(`${item.raceKey}:${item.bib}`):null}
    function routePoint(distance){
      const points=route.points||[],target=Math.max(0,Math.min(Number(route.full_distance_km),Number(distance)||0));let low=0,high=points.length-1;
      while(low<high){const middle=(low+high)>>1;if(Number(points[middle][3])<target)low=middle+1;else high=middle}
      const current=points[low],previous=points[Math.max(0,low-1)],span=Number(current?.[3])-Number(previous?.[3]),share=span>0?(target-Number(previous[3]))/span:0;
      return [Number(previous?.[0])+(Number(current?.[0])-Number(previous?.[0]))*share,Number(previous?.[1])+(Number(current?.[1])-Number(previous?.[1]))*share,target];
    }
    function routeSlice(raceValue){
      const item=typeof raceValue==='string'?race(raceValue):raceValue,start=item.startDistanceKm,end=item.endDistanceKm,points=[routePoint(start)];
      for(const point of route.points||[])if(Number(point[3])>start&&Number(point[3])<end)points.push([Number(point[0]),Number(point[1]),Number(point[3])]);
      points.push(routePoint(end));return points;
    }
    function elevationSlice(raceValue){
      const item=typeof raceValue==='string'?race(raceValue):raceValue,start=item.startDistanceKm,end=item.endDistanceKm;
      return elevationPoints.filter(point=>Number(point.route_distance_km)>=start&&Number(point.route_distance_km)<=end).map(point=>({...point}));
    }
    function profile(value){
      const item=typeof value==='string'?record(value):value;if(profileCache.has(item.id))return profileCache.get(item.id);const raceValue=race(item.raceKey),known=resultSplits(item),anchors=[{checkpoint:raceValue.checkpoints[0].key,name:raceValue.checkpoints[0].name,elapsedSeconds:0,distance:raceValue.startDistanceKm,placeOverall:null,placeClass:null,placeGender:null,kind:'start'}];
      for(const split of known){
        const checkpoint=raceValue.checkpointMap.get(split.checkpoint),previous=anchors.at(-1);if(checkpoint?.replay_anchor===false||split.routeDistanceKm<=previous.distance||Number(split.elapsed_seconds)<=previous.elapsedSeconds)continue;
        anchors.push({checkpoint:split.checkpoint,name:checkpoint.name,sourceName:split.source_point_name||checkpoint.name,elapsedSeconds:Number(split.elapsed_seconds),distance:split.routeDistanceKm,placeOverall:number(split.place_overall),placeClass:number(split.place_class),placeGender:number(split.place_gender),splitPlaceOverall:number(split.split_place_overall),splitSeconds:number(split.split_seconds),splitSpeedKmh:number(split.split_speed_kmh),splitPaceMinKm:number(split.split_pace_min_per_km),cumulativeSpeedKmh:number(split.cumulative_speed_kmh),cumulativePaceMinKm:number(split.cumulative_pace_min_per_km),source:split,kind:split.checkpoint==='alingsas'?'finish':'checkpoint'});
      }
      const makeSegment=(from,to,index,analytical)=>{const distance=to.distance-from.distance,time=to.elapsedSeconds-from.elapsedSeconds;if(distance<=0||time<=0)return null;const checkpointSpan=raceValue.checkpointMap.get(to.checkpoint).index-raceValue.checkpointMap.get(from.checkpoint).index;return{index,from,to,name:`${from.name}–${to.name}`,distance,time,paceSecondsKm:time/distance,speedKmh:distance/(time/3600),placeGain:finite(from.placeOverall)&&finite(to.placeOverall)?Number(from.placeOverall)-Number(to.placeOverall):null,splitPlaceOverall:checkpointSpan===1?to.splitPlaceOverall:null,analytical,combinedTimingPassages:Math.max(0,checkpointSpan-1)}};
      const timingSegments=[];for(let index=1;index<anchors.length;index++){const segment=makeSegment(anchors[index-1],anchors[index],index-1,false);if(segment)timingSegments.push(segment)}
      const analysisAnchors=raceValue.analysisCheckpoints.map(checkpoint=>anchors.find(anchor=>anchor.checkpoint===checkpoint.key)).filter(Boolean),segments=[];
      for(let index=1;index<raceValue.analysisCheckpoints.length;index++){const fromBoundary=raceValue.analysisCheckpoints[index-1],toBoundary=raceValue.analysisCheckpoints[index],from=anchors.find(anchor=>anchor.checkpoint===fromBoundary.key),to=anchors.find(anchor=>anchor.checkpoint===toBoundary.key);if(!from||!to)continue;const segment=makeSegment(from,to,index-1,true);if(segment)segments.push(segment)}
      const built={record:item,race:raceValue,anchors,analysisAnchors,timingSegments,segments,complete:anchors.length===raceValue.replayCheckpoints.length,finish:statusFinished(item),maxTime:Number(item.finish_seconds)||anchors.at(-1)?.elapsedSeconds||0,maxDistance:anchors.at(-1)?.distance||raceValue.startDistanceKm};profileCache.set(item.id,built);return built;
    }
    function distanceAtTime(profileValue,time){
      const anchors=profileValue.anchors;if(!anchors.length)return profileValue.race.startDistanceKm;const target=Math.max(0,Number(time)||0);
      if(target>=anchors.at(-1).elapsedSeconds)return anchors.at(-1).distance;
      let index=1;while(index<anchors.length&&anchors[index].elapsedSeconds<target)index++;
      const from=anchors[index-1],to=anchors[index],share=(target-from.elapsedSeconds)/(to.elapsedSeconds-from.elapsedSeconds||1);return from.distance+(to.distance-from.distance)*share;
    }
    function stateAtTime(profileValue,time){
      const distance=distanceAtTime(profileValue,time),anchors=profileValue.anchors;let index=1;while(index<anchors.length&&anchors[index].distance<distance-.001)index++;const from=anchors[Math.max(0,index-1)],to=anchors[Math.min(index,anchors.length-1)],atTo=Math.abs(distance-to.distance)<.02,known=atTo?to:from,timingSegment=profileValue.timingSegments[Math.max(0,index-1)]||null,analysisInterval=analysisIntervalAtDistance(profileValue.race,distance),segment=profileValue.segments.find(candidate=>candidate.from.checkpoint===analysisInterval?.from.key&&candidate.to.checkpoint===analysisInterval?.to.key)||null;
      return{distance,from,to,timingSegment,analysisInterval,segment,place:known.placeOverall||null,classPlace:known.placeClass||null,genderPlace:known.placeGender||null,placeExact:atTo&&finite(to.placeOverall),classPlaceExact:atTo&&finite(to.placeClass),genderPlaceExact:atTo&&finite(to.placeGender),finished:time>=profileValue.maxTime&&profileValue.finish,stopped:time>=profileValue.maxTime&&!profileValue.finish};
    }
    function analysisIntervalAtDistance(raceValue,distance){const checkpoints=raceValue.analysisCheckpoints,target=Number(distance)||raceValue.startDistanceKm;let index=1;while(index<checkpoints.length&&Number(checkpoints[index].route_distance_km)<target-.001)index++;const from=checkpoints[Math.max(0,index-1)],to=checkpoints[Math.min(index,checkpoints.length-1)];return from&&to&&from!==to?{index:Math.max(0,index-1),from,to,name:`${from.name}–${to.name}`} : null}
    function timeAtDistance(profileValue,distance){
      const anchors=profileValue.anchors,target=Math.max(profileValue.race.startDistanceKm,Math.min(Number(distance)||0,profileValue.maxDistance));if(target>=anchors.at(-1).distance)return anchors.at(-1).elapsedSeconds;let index=1;while(index<anchors.length&&anchors[index].distance<target)index++;const from=anchors[index-1],to=anchors[index],share=(target-from.distance)/(to.distance-from.distance||1);return from.elapsedSeconds+(to.elapsedSeconds-from.elapsedSeconds)*share;
    }
    function elevationAtDistance(distance){
      if(!elevationPoints.length)return null;const target=Number(distance)||0;let low=0,high=elevationPoints.length-1;while(low<high){const middle=(low+high)>>1;if(Number(elevationPoints[middle].route_distance_km)<target)low=middle+1;else high=middle}const current=elevationPoints[low],previous=elevationPoints[Math.max(0,low-1)],span=Number(current.route_distance_km)-Number(previous.route_distance_km),share=span>0?(target-Number(previous.route_distance_km))/span:0;return Number(previous.elevation_m)+(Number(current.elevation_m)-Number(previous.elevation_m))*share;
    }
    function elevationRangeStats(fromDistance,toDistance){
      if(!elevationPoints.length)return{ascentM:null,descentM:null,netElevationM:null,startElevationM:null,endElevationM:null};
      const from=Math.min(Number(fromDistance),Number(toDistance)),to=Math.max(Number(fromDistance),Number(toDistance)),startElevationM=elevationAtDistance(from),endElevationM=elevationAtDistance(to),range=[{route_distance_km:from,elevation_m:startElevationM},...elevationPoints.filter(point=>Number(point.route_distance_km)>from&&Number(point.route_distance_km)<to),{route_distance_km:to,elevation_m:endElevationM}];let ascentM=0,descentM=0;
      for(let index=1;index<range.length;index++){const difference=Number(range[index].elevation_m)-Number(range[index-1].elevation_m);if(difference>0)ascentM+=difference;else descentM+=Math.abs(difference)}
      return{ascentM,descentM,netElevationM:endElevationM-startElevationM,startElevationM,endElevationM};
    }
    function completeProfiles(raceValue){
      const item=typeof raceValue==='string'?race(raceValue):raceValue;return item.records.filter(statusFinished).map(profile).filter(candidate=>candidate.complete&&candidate.finish&&candidate.anchors.length===item.replayCheckpoints.length&&candidate.anchors.every((anchor,index)=>anchor.checkpoint===item.replayCheckpoints[index].key)&&(candidate.anchors.every((anchor,index)=>index===0||anchor.elapsedSeconds>candidate.anchors[index-1].elapsedSeconds)));
    }
    function cohortReference(id,label,color,profiles,raceValue){
      if(profiles.length<MIN_REFERENCE_SIZE)return{id,label,color,count:profiles.length,available:false,message:'För få kompletta profiler för en stabil median'};const anchors=raceValue.replayCheckpoints.map((checkpoint,index)=>({checkpoint:checkpoint.key,name:checkpoint.name,distance:Number(checkpoint.route_distance_km),elapsedSeconds:index===0?0:Math.round(median(profiles.map(candidate=>candidate.anchors[index].elapsedSeconds))),placeOverall:null,placeClass:null,placeGender:null,kind:index===raceValue.replayCheckpoints.length-1?'finish':'reference'}));for(let index=1;index<anchors.length;index++)anchors[index].elapsedSeconds=Math.max(anchors[index].elapsedSeconds,anchors[index-1].elapsedSeconds+1);return{id,label,color,count:profiles.length,available:true,anchors,race:raceValue,maxTime:anchors.at(-1).elapsedSeconds,maxDistance:anchors.at(-1).distance,finish:true,cohortIds:profiles.map(candidate=>candidate.record.id).sort()};
    }
    function referenceProfiles(value){
      const item=typeof value==='string'?record(value):value,raceValue=race(item.raceKey),cacheKey=`${raceValue.key}|${item.class_name||'-'}|${item.sex||'-'}`;if(referenceCache.has(cacheKey))return referenceCache.get(cacheKey);const complete=completeProfiles(raceValue),field=cohortReference('field','Hela fältet','#66756f',complete,raceValue),classProfiles=complete.filter(candidate=>candidate.record.class_name===item.class_name),classReference=cohortReference('class','Min klass','#138a78',classProfiles,raceValue),sexProfiles=raceValue.isRelay?[]:complete.filter(candidate=>candidate.record.sex===item.sex),sexReference=raceValue.isRelay?{id:'sex',label:'Mitt kön',color:item.sex==='F'?'#db2777':'#2563eb',count:0,available:false,message:'Könsreferens används inte för stafettlag'}:cohortReference('sex','Mitt kön',item.sex==='F'?'#db2777':'#2563eb',sexProfiles,raceValue);const same=classReference.available&&sexReference.available&&classReference.cohortIds.join('|')===sexReference.cohortIds.join('|');if(same){classReference.coincidesWith='sex';sexReference.coincidesWith='class'}const result={field,class:classReference,sex:sexReference,completeCount:complete.length,minimumSize:MIN_REFERENCE_SIZE};referenceCache.set(cacheKey,result);return result;
    }
    function referenceGap(reference,runnerTime,runnerDistance){return reference?.available?timeAtDistance(reference,runnerDistance)-Number(runnerTime||0):null}
    function journeyCompleteProfiles(raceValue){
      const item=typeof raceValue==='string'?race(raceValue):raceValue,segments=item.analysisCheckpoints.length-1;
      return item.records.filter(statusFinished).map(profile).filter(candidate=>candidate.finish&&candidate.segments.length===segments&&item.analysisCheckpoints.slice(1).every((checkpoint,index)=>{const segment=candidate.segments[index];return segment?.from.checkpoint===item.analysisCheckpoints[index].key&&segment?.to.checkpoint===checkpoint.key&&finite(segment.from.elapsedSeconds)&&finite(segment.to.elapsedSeconds)&&finite(segment.paceSecondsKm)&&Number(segment.paceSecondsKm)>0}));
    }
    function segmentDistributionProfile(raceValue,profiles){
      const item=typeof raceValue==='string'?race(raceValue):raceValue,cohort=(profiles||journeyCompleteProfiles(item)).map(candidate=>candidate?.record&&candidate?.segments?candidate:profile(candidate)).filter(candidate=>candidate?.race?.key===item.key),boundaries=item.analysisCheckpoints;
      return boundaries.slice(1).map((to,index)=>{const from=boundaries[index],samples=cohort.map(candidate=>candidate.segments[index]).filter(segment=>segment?.from.checkpoint===from.key&&segment?.to.checkpoint===to.key&&finite(segment.paceSecondsKm)&&Number(segment.paceSecondsKm)>0),pace=distributionSummary(samples.map(segment=>segment.paceSecondsKm));return{id:`${from.key}--${to.key}`,index,from:from.key,to:to.key,name:`${from.name}–${to.name==='Mål'?'Alingsås':to.name}`,fromDistance:Number(from.route_distance_km),toDistance:Number(to.route_distance_km),distanceKm:Number(to.route_distance_km)-Number(from.route_distance_km),pace,n:pace.n,samples}});
    }
    function segmentGroupDistribution(raceValue,predicate){
      const item=typeof raceValue==='string'?race(raceValue):raceValue,cohort=journeyCompleteProfiles(item).filter(candidate=>typeof predicate==='function'?predicate(candidate.record):true);
      return{race:item,cohort:cohort.map(candidate=>candidate.record),count:cohort.length,segments:segmentDistributionProfile(item,cohort)};
    }
    function courseDifficultyProfile(raceValue){
      const item=typeof raceValue==='string'?race(raceValue):raceValue,cohort=journeyCompleteProfiles(item),distance=Number(item.distanceKm),baselinePace=median(cohort.map(candidate=>Number(candidate.record.finish_seconds)/distance)),segments=segmentDistributionProfile(item,cohort).map(segment=>{const elevationStats=elevationRangeStats(segment.fromDistance,segment.toDistance),movements=segment.index===0?[]:cohort.map(candidate=>{const sample=candidate.segments[segment.index];return finite(sample?.from.placeOverall)&&finite(sample?.to.placeOverall)?Math.abs(Number(sample.from.placeOverall)-Number(sample.to.placeOverall)):null}).filter(finite),paceIqrSeconds=segment.pace.bandAvailable?segment.pace.q75-segment.pace.q25:null,paceIqrPercent=finite(paceIqrSeconds)&&segment.pace.median?paceIqrSeconds/segment.pace.median*100:null,paceIndex=segment.pace.median&&baselinePace?baselinePace/segment.pace.median*100:null,slowdownPercent=segment.pace.median&&baselinePace?(segment.pace.median/baselinePace-1)*100:null;return{...segment,...elevationStats,climbIntensity:segment.distanceKm?elevationStats.ascentM/segment.distanceKm:null,paceIndex,slowdownPercent,paceIqrSeconds,paceIqrPercent,placementMovementMedian:median(movements),placementN:movements.length}}),rank=(key,eligible=()=>true)=>segments.filter(segment=>finite(segment[key])&&eligible(segment)).sort((a,b)=>Number(b[key])-Number(a[key]))[0]||null;
      return{race:item,cohortCount:cohort.length,baselinePace,segments,standouts:{mostClimbing:rank('ascentM'),biggestSlowdown:rank('slowdownPercent'),biggestSpread:rank('paceIqrPercent',segment=>segment.pace.bandAvailable),mostPlacementMovement:rank('placementMovementMedian',segment=>segment.placementN>0)},geometrySource:'official-gpx',elevationSource:elevation?.meta?.source||'normalized-elevation-profile',paceSource:'official-passages-derived',placementSource:'official-passages-derived'};
    }
    function journeyReference(id,label,color,profiles,raceValue){
      const count=profiles.length,available=count>=MIN_REFERENCE_SIZE,checkpoints=raceValue.analysisCheckpoints.slice(1).map((checkpoint,index)=>({key:checkpoint.key,name:checkpoint.name==='Mål'?'Alingsås':checkpoint.name,distance:Number(checkpoint.route_distance_km),medianElapsed:available?median(profiles.map(candidate=>candidate.analysisAnchors.find(anchor=>anchor.checkpoint===checkpoint.key)?.elapsedSeconds)):null,medianPace:available?median(profiles.map(candidate=>candidate.segments[index]?.paceSecondsKm)):null,sourceType:'derived-median'}));
      return{id,label,color,count,available,smallSample:available&&count<10,message:available&&count<10?'Litet underlag':available?'':'För litet underlag',checkpoints,cohortIds:profiles.map(candidate=>candidate.record.id).sort(),sourceType:'derived-median'};
    }
    function journeyReferences(value){
      const item=typeof value==='string'?record(value):value,raceValue=race(item.raceKey),cacheKey=`${raceValue.key}|${item.class_name||'-'}|${raceValue.isRelay?'relay':item.sex||'-'}`;if(journeyReferenceCache.has(cacheKey))return journeyReferenceCache.get(cacheKey);const complete=journeyCompleteProfiles(raceValue),field=journeyReference('field',raceValue.isRelay?'Alla lag':'Hela fältet','#0b6671',complete,raceValue),classProfiles=complete.filter(candidate=>candidate.record.class_name===item.class_name),classReference=journeyReference('class',raceValue.isRelay?'Min stafettklass':'Min klass','#138a78',classProfiles,raceValue),references=[field,classReference];if(!raceValue.isRelay)references.push(journeyReference('sex','Mitt kön',item.sex==='F'?'#db2777':'#2563eb',complete.filter(candidate=>candidate.record.sex===item.sex),raceValue));const result={race:raceValue,references,field,class:classReference,sex:references.find(reference=>reference.id==='sex')||null,completeCount:complete.length,minimumSize:MIN_REFERENCE_SIZE,analyticSegmentCount:raceValue.analysisCheckpoints.length-1};journeyReferenceCache.set(cacheKey,result);return result;
    }
    function journeyGap(referenceMedianElapsed,runnerElapsed){return finite(referenceMedianElapsed)&&finite(runnerElapsed)?Number(referenceMedianElapsed)-Number(runnerElapsed):null}
    function journeyRelativePerformance(referencePace,ownPace){return finite(referencePace)&&finite(ownPace)&&Number(ownPace)>0?(Number(referencePace)/Number(ownPace)-1)*100:null}
    function journeyPacingCategory(value){if(!finite(value))return{id:'missing',symbol:'–',label:'Ej genomfört / tid saknas'};const number=Number(value);if(number>=8)return{id:'very-strong',symbol:'▲',label:'Mycket starkt relativt'};if(number>=3)return{id:'strong',symbol:'▲',label:'Starkare'};if(number>=-3)return{id:'level',symbol:'≈',label:'I nivå'};if(number>-8)return{id:'weak',symbol:'▼',label:'Svagare'};return{id:'very-weak',symbol:'▼',label:'Tydligt svagare'}}
    function journeyAnalysis(value,referenceId='field'){
      const item=typeof value==='string'?record(value):value,raceValue=race(item.raceKey),profileValue=profile(item),referenceSet=journeyReferences(item),reference=referenceSet.references.find(candidate=>candidate.id===referenceId&&candidate.available)||referenceSet.references.find(candidate=>candidate.available)||referenceSet.references[0],checkpoints=raceValue.analysisCheckpoints.slice(1),relayMeta=relayClassMeta(item),gapPoints=checkpoints.map((checkpoint,index)=>{const anchor=checkpoint.key==='alingsas'&&!statusFinished(item)?null:profileValue.analysisAnchors.find(candidate=>candidate.checkpoint===checkpoint.key),medianElapsed=reference?.checkpoints[index]?.medianElapsed,gapSeconds=anchor?journeyGap(medianElapsed,anchor.elapsedSeconds):null;return{index,checkpoint:checkpoint.key,name:checkpoint.name==='Mål'?'Alingsås':checkpoint.name,distance:Number(checkpoint.route_distance_km),elapsedSeconds:anchor?.elapsedSeconds??null,referenceMedianElapsed:medianElapsed??null,gapSeconds,sourceType:anchor?'official':null,referenceType:'derived-median'}}),placementPoints=checkpoints.map((checkpoint,index)=>{const finish=checkpoint.key==='alingsas'&&statusFinished(item),anchor=checkpoint.key==='alingsas'&&!finish?null:profileValue.analysisAnchors.find(candidate=>candidate.checkpoint===checkpoint.key),overall=finish&&finite(item.overall_place)?Number(item.overall_place):anchor?.placeOverall??null,classPlace=finish&&finite(item.class_place)?Number(item.class_place):anchor?.placeClass??null,gender=finish&&finite(item.gender_place)?Number(item.gender_place):anchor?.placeGender??null;return{index,checkpoint:checkpoint.key,name:checkpoint.name==='Mål'?'Alingsås':checkpoint.name,distance:Number(checkpoint.route_distance_km),overall:anchor||finish?overall:null,class:relayMeta.ranked&&(anchor||finish)?classPlace:null,sex:!raceValue.isRelay&&(anchor||finish)?gender:null,sourceType:anchor||finish?'official':null}}),pacing=checkpoints.map((checkpoint,index)=>{const expectedFrom=raceValue.analysisCheckpoints[index],segment=profileValue.segments.find(candidate=>candidate.from.checkpoint===expectedFrom.key&&candidate.to.checkpoint===checkpoint.key),ownPace=segment?.paceSecondsKm??null,referenceMedianPace=reference?.checkpoints[index]?.medianPace??null,relativePerformance=journeyRelativePerformance(referenceMedianPace,ownPace),category=journeyPacingCategory(relativePerformance);return{index,checkpoint:checkpoint.key,name:`${expectedFrom.name}–${checkpoint.name==='Mål'?'Alingsås':checkpoint.name}`,fromDistance:Number(expectedFrom.route_distance_km),toDistance:Number(checkpoint.route_distance_km),midpointDistance:(Number(expectedFrom.route_distance_km)+Number(checkpoint.route_distance_km))/2,ownPace,referenceMedianPace,relativePerformance,...category,sourceType:segment?'official':null,referenceType:'derived-median'}});return{record:item,race:raceValue,profile:profileValue,references:referenceSet.references,reference,minimumSize:MIN_REFERENCE_SIZE,gapPoints,placementPoints,pacing,placementSeries:{overall:{id:'overall',label:'Total',available:placementPoints.some(point=>finite(point.overall)),values:placementPoints.map(point=>point.overall)},class:{id:'class',label:raceValue.isRelay?'Lagklass':'Klass',available:relayMeta.ranked&&placementPoints.some(point=>finite(point.class)),message:relayMeta.ranked?'Placering saknas':'Ej tävling – ingen officiell klassplacering',values:placementPoints.map(point=>point.class)},sex:{id:'sex',label:'Kön',available:!raceValue.isRelay&&placementPoints.some(point=>finite(point.sex)),message:raceValue.isRelay?'Könsplacering används inte för stafettlag':'Placering saknas',values:placementPoints.map(point=>point.sex)}}};
    }
    function clubGroups(recordList){
      const groups=new Map();
      for(const item of recordList){
        const variant=normalizeClubName(item.club),key=clubKey(variant);if(!key)continue;
        if(!groups.has(key))groups.set(key,{key,count:0,records:[],variants:new Map()});
        const group=groups.get(key);group.count++;group.records.push(item);group.variants.set(variant,(group.variants.get(variant)||0)+1);
      }
      return[...groups.values()].map(group=>{group.name=[...group.variants].sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0],'sv'))[0][0];return group});
    }
    function clubDisplayName(value,recordList){const normalized=normalizeClubName(value);if(!recordList?.length)return normalized;return clubGroups(recordList).find(group=>group.key===clubKey(value))?.name||normalized}
    function clubRecords(recordList,value){const key=clubKey(value);return recordList.filter(item=>clubKey(item.club)===key)}
    function filtered(raceKey,filters={}){
      const query=String(filters.query||'').trim().toLocaleLowerCase('sv'),club=String(filters.club||'').trim().toLocaleLowerCase('sv');
      const raceRecords=race(raceKey).records;
      return raceRecords.filter(item=>{const displayClub=clubDisplayName(item.club,raceRecords).toLocaleLowerCase('sv');return(!filters.sex||item.sex===filters.sex)&&(!filters.className||item.class_name===filters.className)&&(!filters.status||item.status===filters.status)&&(!club||displayClub.includes(club))&&(!query||`${item.name} ${item.bib} ${displayClub}`.toLocaleLowerCase('sv').includes(query))});
    }
    function segmentStats(recordList){
      const raceValue=race(recordList[0]?.raceKey);if(!raceValue)return[];
      return raceValue.analysisCheckpoints.slice(1).map((checkpoint,index)=>{
        const samples=[];
        for(const item of recordList){const segment=profile(item).segments.find(value=>value.to.checkpoint===checkpoint.key);if(segment)samples.push(segment)}
        const paces=samples.map(value=>value.paceSecondsKm),times=samples.map(value=>value.time);
        return{index,checkpoint,name:samples[0]?.name||`${raceValue.analysisCheckpoints[index].name}–${checkpoint.name}`,count:samples.length,medianPace:median(paces),q25Pace:quantile(paces,.25),q75Pace:quantile(paces,.75),medianTime:median(times),fastest:Math.min(...times.filter(finite),Infinity),samples};
      });
    }
    function wholeRacePaceProfile(recordList,raceValue){
      const item=typeof raceValue==='string'?race(raceValue):raceValue||race(recordList[0]?.raceKey),checkpoints=item?.analysisCheckpoints.slice(1)||[],distance=Number(item?.distanceKm);
      if(!item||!finite(distance)||distance<=0)return{race:item||null,cohort:[],count:0,baselinePace:null,overallPaces:[],segmentStats:[],segmentMedianPaces:[],indexValues:[]};
      const complete=(recordList||[]).filter(statusFinished).map(record=>({record,profile:profile(record)})).filter(candidate=>candidate.profile.race.key===item.key&&candidate.profile.segments.length===checkpoints.length&&checkpoints.every((checkpoint,index)=>{const segment=candidate.profile.segments[index];return segment?.to.checkpoint===checkpoint.key&&finite(segment.paceSecondsKm)&&Number(segment.paceSecondsKm)>0}));
      const overallPaces=complete.map(candidate=>Number(candidate.record.finish_seconds)/distance),baselinePace=median(overallPaces),segmentStats=checkpoints.map((checkpoint,index)=>{const samples=complete.map(candidate=>candidate.profile.segments[index]),medianPace=median(samples.map(segment=>segment.paceSecondsKm));return{index,checkpoint,name:samples[0]?.name||`${item.analysisCheckpoints[index].name}–${checkpoint.name}`,count:samples.length,medianPace,samples,indexValue:finite(medianPace)&&baselinePace?baselinePace/medianPace*100:null}});
      return{race:item,cohort:complete.map(candidate=>candidate.record),count:complete.length,baselinePace,overallPaces,segmentStats,segmentMedianPaces:segmentStats.map(stat=>stat.medianPace),indexValues:segmentStats.map(stat=>stat.indexValue)};
    }
    function relayClassRecords(recordList,value){const name=relayClassMeta(value).fullLabel;return(recordList||[]).filter(item=>relayClassMeta(item).fullLabel===name)}
    function relayClassGroups(recordList,raceValue){const byId=new Map();for(const item of recordList||[]){const meta=relayClassMeta(item);if(!byId.has(meta.id))byId.set(meta.id,{...meta,records:[]});byId.get(meta.id).records.push(item)}return[...byId.values()].sort((a,b)=>Object.keys(RELAY_CLASS_DEFINITIONS).indexOf(a.fullLabel)-Object.keys(RELAY_CLASS_DEFINITIONS).indexOf(b.fullLabel)).map(group=>{const starters=group.records.filter(statusStarter),finishers=group.records.filter(statusFinished);return{...group,all:group.records,starters,finishers,finishRate:starters.length?finishers.length/starters.length:null,medianFinish:median(finishers.map(item=>item.finish_seconds)),fastest:finishers.slice().sort((a,b)=>a.finish_seconds-b.finish_seconds)[0]||null,stats:segmentStats(group.records),retention:wholeRacePaceProfile(group.records,raceValue)}})}
    function relayClassPercentile(value,recordList){const item=typeof value==='string'?record(value):value;return percentile(item,relayClassRecords(recordList,item))}
    function relayClassAdvancements(recordList){return(recordList||[]).filter(item=>relayClassMeta(item).ranked).map(item=>{const anchors=profile(item).anchors.filter(anchor=>finite(anchor.placeClass));if(anchors.length<2)return null;return{record:item,from:anchors[0].placeClass,to:anchors.at(-1).placeClass,gain:Number(anchors[0].placeClass)-Number(anchors.at(-1).placeClass)}}).filter(Boolean).sort((a,b)=>b.gain-a.gain)}
    function percentile(value,recordList){
      const item=typeof value==='string'?record(value):value,finishers=recordList.filter(statusFinished).slice().sort((a,b)=>a.finish_seconds-b.finish_seconds),index=finishers.findIndex(candidate=>candidate.id===item.id);return index<0?null:Math.round((finishers.length-index)/finishers.length*100);
    }
    function relativeProfile(value,recordList){
      const own=profile(value),stats=segmentStats(recordList),segments=own.segments.map(segment=>{const stat=stats.find(item=>item.checkpoint.key===segment.to.checkpoint),ratio=stat?.medianPace?segment.paceSecondsKm/stat.medianPace:null;return{...segment,fieldMedianPace:stat?.medianPace,relative:ratio,relativePercent:finite(ratio)?Math.round((1-ratio)*100):null}});const ranked=segments.filter(segment=>finite(segment.relative)).slice().sort((a,b)=>a.relative-b.relative);
      return{segments,strongest:ranked[0]||null,weakest:ranked.at(-1)||null,percentile:percentile(value,recordList),averageRelative:average(segments.map(segment=>segment.relative))};
    }
    function advancements(recordList){
      return recordList.map(item=>{const anchors=profile(item).anchors.filter(anchor=>finite(anchor.placeOverall));if(anchors.length<2)return null;return{record:item,from:anchors[0].placeOverall,to:anchors.at(-1).placeOverall,gain:Number(anchors[0].placeOverall)-Number(anchors.at(-1).placeOverall)}}).filter(Boolean).sort((a,b)=>b.gain-a.gain);
    }
    function segmentRanking(recordList,fromKey,toKey,metric='time',comparison='field'){
      const raceValue=race(recordList[0]?.raceKey),fromCp=raceValue?.checkpointMap.get(fromKey),toCp=raceValue?.checkpointMap.get(toKey);if(!fromCp||!toCp||toCp.index<=fromCp.index)return[];const entries=[];
      for(const item of recordList){const current=profile(item),from=current.anchors.find(anchor=>anchor.checkpoint===fromKey),to=current.anchors.find(anchor=>anchor.checkpoint===toKey);if(!from||!to||to.elapsedSeconds<=from.elapsedSeconds)continue;const time=to.elapsedSeconds-from.elapsedSeconds,distance=to.distance-from.distance,pace=time/distance,fromPlace=from.placeOverall,toPlace=to.placeOverall,gain=finite(fromPlace)&&finite(toPlace)?Number(fromPlace)-Number(toPlace):null;entries.push({record:item,time,distance,pace,gain,fromPlace,toPlace})}
      const medianPace=median(entries.map(entry=>entry.pace)),classMedians=new Map();if(comparison==='class')for(const entry of entries){const name=relayClassMeta(entry.record).fullLabel;if(!classMedians.has(name))classMedians.set(name,median(entries.filter(candidate=>relayClassMeta(candidate.record).fullLabel===name).map(candidate=>candidate.pace)))}entries.forEach(entry=>{const reference=comparison==='class'?classMedians.get(relayClassMeta(entry.record).fullLabel):medianPace;entry.relative=entry.pace/reference;entry.referencePace=reference});
      return entries.sort(metric==='gain'?(a,b)=>(b.gain??-Infinity)-(a.gain??-Infinity):metric==='relative'?(a,b)=>a.relative-b.relative:(a,b)=>a.time-b.time);
    }
    function clubNames(recordList){return clubGroups(recordList).map(group=>[group.name,group.count,group.key]).sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0],'sv'))}
    function clubStats(recordList,name){const members=clubRecords(recordList,name),finishers=members.filter(statusFinished),starters=members.filter(statusStarter);return{name:clubDisplayName(name,recordList),key:clubKey(name),count:members.length,finishers:finishers.length,finishRate:starters.length?finishers.length/starters.length:null,medianFinish:median(finishers.map(item=>item.finish_seconds)),segments:segmentStats(members),wholeRacePace:wholeRacePaceProfile(members)}}
    function fieldFlow(recordList){
      const raceValue=race(recordList[0]?.raceKey);if(!raceValue)return[];return raceValue.analysisCheckpoints.slice(1).map(checkpoint=>{const times=[];for(const item of recordList){const anchor=profile(item).anchors.find(value=>value.checkpoint===checkpoint.key);if(anchor)times.push(anchor.elapsedSeconds)}return{checkpoint,name:checkpoint.name,count:times.length,median:median(times),q10:quantile(times,.1),q90:quantile(times,.9),spread:finite(quantile(times,.9))?quantile(times,.9)-quantile(times,.1):null}})
    }
    function dnfByLastAnalysisCheckpoint(recordList){
      const raceValue=race(recordList[0]?.raceKey);if(!raceValue)return[];const groups=[{key:'before-first',checkpoint:null,name:'Före första kontroll',records:[]},...raceValue.analysisCheckpoints.slice(1).map(checkpoint=>({key:checkpoint.key,checkpoint,name:checkpoint.name,records:[]}))],groupMap=new Map(groups.map(group=>[group.key,group]));
      for(const item of recordList.filter(record=>record.status==='DNF')){let last=null;for(const split of resultSplits(item)){const checkpoint=raceValue.checkpointMap.get(split.checkpoint);if(checkpoint?.analysis_boundary!==false&&groupMap.has(checkpoint.key)&&(!last||checkpoint.index>last.index))last=checkpoint}groupMap.get(last?.key||'before-first').records.push(item)}
      return groups.filter(group=>group.records.length).map(group=>({...group,count:group.records.length}))
    }
    return{data,route,elevation,races,records,race,record,resultSplits,team,profile,distanceAtTime,timeAtDistance,stateAtTime,analysisIntervalAtDistance,elevationAtDistance,elevationRangeStats,completeProfiles,referenceProfiles,referenceGap,journeyCompleteProfiles,journeyReferences,journeyGap,journeyRelativePerformance,journeyPacingCategory,journeyAnalysis,routePoint,routeSlice,elevationSlice,filtered,segmentStats,segmentDistributionProfile,segmentGroupDistribution,courseDifficultyProfile,wholeRacePaceProfile,relayClassMeta,relayClassRecords,relayClassGroups,relayClassPercentile,relayClassAdvancements,percentile,relativeProfile,advancements,segmentRanking,normalizeClubName,clubKey,clubDisplayName,clubRecords,clubNames,clubStats,fieldFlow,dnfByLastAnalysisCheckpoint,median,quantile,average,distributionSummary,statusFinished,statusStarter,MIN_REFERENCE_SIZE};
  }
  window.GDataAdapter={create,median,quantile,average,distributionSummary,statusFinished,statusStarter,normalizeClubName,clubKey,normalizeRelayClassName,relayClassMeta,RELAY_CLASS_DEFINITIONS,MIN_REFERENCE_SIZE};
})();
