(function(){
  'use strict';
  const finite=value=>value!==null&&value!==undefined&&value!==''&&Number.isFinite(Number(value));
  const number=value=>finite(value)?Number(value):null;
  const median=values=>{const sorted=values.filter(finite).map(Number).sort((a,b)=>a-b);if(!sorted.length)return null;const middle=Math.floor(sorted.length/2);return sorted.length%2?sorted[middle]:(sorted[middle-1]+sorted[middle])/2};
  const quantile=(values,q)=>{const sorted=values.filter(finite).map(Number).sort((a,b)=>a-b);if(!sorted.length)return null;const index=(sorted.length-1)*q,low=Math.floor(index),high=Math.ceil(index);return sorted[low]+(sorted[high]-sorted[low])*(index-low)};
  const average=values=>{const valid=values.filter(finite).map(Number);return valid.length?valid.reduce((sum,value)=>sum+value,0)/valid.length:null};
  const statusFinished=record=>record?.status==='FINISHED'&&finite(record.finish_seconds)&&Number(record.finish_seconds)>0;
  const statusStarter=record=>!['DNS'].includes(String(record?.status||'').toUpperCase());
  const normalizeClubName=value=>String(value||'').trim().replace(/\s+/g,' ');
  const clubKey=value=>normalizeClubName(value).toLocaleLowerCase('sv');
  const MIN_REFERENCE_SIZE=5;

  function create(data,route,elevation){
    const races=new Map(),records=new Map(),splitsByResult=new Map(),teams=new Map(),profileCache=new Map(),referenceCache=new Map();
    const elevationPoints=elevation?.profile||elevation?.points||[];
    for(const team of data.teams||[])teams.set(`${team.race_key}:${team.bib}`,team);
    for(const [raceKey,source] of Object.entries(data.races||{})){
      const checkpoints=(data.checkpoints?.[raceKey]||[]).map((checkpoint,index)=>({...checkpoint,index}));
      const checkpointMap=new Map(checkpoints.map(checkpoint=>[checkpoint.key,checkpoint]));
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
        checkpointMap,
        records:[]
      };
      for(const sourceRecord of source.records||[]){
        const id=`${raceKey}:${sourceRecord.bib}`;
        const record={...sourceRecord,id,raceKey,isRelay:race.isRelay,displayType:race.isRelay?'lag':'löpare'};
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
        const previous=anchors.at(-1);if(split.routeDistanceKm<=previous.distance||Number(split.elapsed_seconds)<=previous.elapsedSeconds)continue;
        anchors.push({checkpoint:split.checkpoint,name:split.source_point_name||raceValue.checkpointMap.get(split.checkpoint)?.name,elapsedSeconds:Number(split.elapsed_seconds),distance:split.routeDistanceKm,placeOverall:number(split.place_overall),placeClass:number(split.place_class),placeGender:number(split.place_gender),splitPlaceOverall:number(split.split_place_overall),splitSeconds:number(split.split_seconds),splitSpeedKmh:number(split.split_speed_kmh),splitPaceMinKm:number(split.split_pace_min_per_km),cumulativeSpeedKmh:number(split.cumulative_speed_kmh),cumulativePaceMinKm:number(split.cumulative_pace_min_per_km),source:split,kind:split.checkpoint==='alingsas'?'finish':'checkpoint'});
      }
      const segments=[];
      for(let index=1;index<anchors.length;index++){
        const from=anchors[index-1],to=anchors[index],distance=to.distance-from.distance,time=to.elapsedSeconds-from.elapsedSeconds;
        if(distance<=0||time<=0)continue;
        segments.push({index:index-1,from,to,name:`${from.name}–${to.name}`,distance,time,paceSecondsKm:time/distance,speedKmh:distance/(time/3600),placeGain:finite(from.placeOverall)&&finite(to.placeOverall)?Number(from.placeOverall)-Number(to.placeOverall):null,splitPlaceOverall:to.splitPlaceOverall});
      }
      const built={record:item,race:raceValue,anchors,segments,complete:anchors.length===raceValue.checkpoints.length,finish:statusFinished(item),maxTime:Number(item.finish_seconds)||anchors.at(-1)?.elapsedSeconds||0,maxDistance:anchors.at(-1)?.distance||raceValue.startDistanceKm};profileCache.set(item.id,built);return built;
    }
    function distanceAtTime(profileValue,time){
      const anchors=profileValue.anchors;if(!anchors.length)return profileValue.race.startDistanceKm;const target=Math.max(0,Number(time)||0);
      if(target>=anchors.at(-1).elapsedSeconds)return anchors.at(-1).distance;
      let index=1;while(index<anchors.length&&anchors[index].elapsedSeconds<target)index++;
      const from=anchors[index-1],to=anchors[index],share=(target-from.elapsedSeconds)/(to.elapsedSeconds-from.elapsedSeconds||1);return from.distance+(to.distance-from.distance)*share;
    }
    function stateAtTime(profileValue,time){
      const distance=distanceAtTime(profileValue,time),anchors=profileValue.anchors;let index=1;while(index<anchors.length&&anchors[index].distance<distance-.001)index++;const from=anchors[Math.max(0,index-1)],to=anchors[Math.min(index,anchors.length-1)],atTo=Math.abs(distance-to.distance)<.02,known=atTo?to:from,segment=profileValue.segments[Math.max(0,index-1)]||null;
      return{distance,from,to,segment,place:known.placeOverall||null,classPlace:known.placeClass||null,genderPlace:known.placeGender||null,placeExact:atTo&&finite(to.placeOverall),classPlaceExact:atTo&&finite(to.placeClass),genderPlaceExact:atTo&&finite(to.placeGender),finished:time>=profileValue.maxTime&&profileValue.finish,stopped:time>=profileValue.maxTime&&!profileValue.finish};
    }
    function timeAtDistance(profileValue,distance){
      const anchors=profileValue.anchors,target=Math.max(profileValue.race.startDistanceKm,Math.min(Number(distance)||0,profileValue.maxDistance));if(target>=anchors.at(-1).distance)return anchors.at(-1).elapsedSeconds;let index=1;while(index<anchors.length&&anchors[index].distance<target)index++;const from=anchors[index-1],to=anchors[index],share=(target-from.distance)/(to.distance-from.distance||1);return from.elapsedSeconds+(to.elapsedSeconds-from.elapsedSeconds)*share;
    }
    function elevationAtDistance(distance){
      if(!elevationPoints.length)return null;const target=Number(distance)||0;let low=0,high=elevationPoints.length-1;while(low<high){const middle=(low+high)>>1;if(Number(elevationPoints[middle].route_distance_km)<target)low=middle+1;else high=middle}const current=elevationPoints[low],previous=elevationPoints[Math.max(0,low-1)],span=Number(current.route_distance_km)-Number(previous.route_distance_km),share=span>0?(target-Number(previous.route_distance_km))/span:0;return Number(previous.elevation_m)+(Number(current.elevation_m)-Number(previous.elevation_m))*share;
    }
    function completeProfiles(raceValue){
      const item=typeof raceValue==='string'?race(raceValue):raceValue;return item.records.filter(statusFinished).map(profile).filter(candidate=>candidate.complete&&candidate.finish&&candidate.anchors.length===item.checkpoints.length&&candidate.anchors.every((anchor,index)=>anchor.checkpoint===item.checkpoints[index].key)&&(candidate.anchors.every((anchor,index)=>index===0||anchor.elapsedSeconds>candidate.anchors[index-1].elapsedSeconds)));
    }
    function cohortReference(id,label,color,profiles,raceValue){
      if(profiles.length<MIN_REFERENCE_SIZE)return{id,label,color,count:profiles.length,available:false,message:'För få kompletta profiler för en stabil median'};const anchors=raceValue.checkpoints.map((checkpoint,index)=>({checkpoint:checkpoint.key,name:checkpoint.name,distance:Number(checkpoint.route_distance_km),elapsedSeconds:index===0?0:Math.round(median(profiles.map(candidate=>candidate.anchors[index].elapsedSeconds))),placeOverall:null,placeClass:null,placeGender:null,kind:index===raceValue.checkpoints.length-1?'finish':'reference'}));for(let index=1;index<anchors.length;index++)anchors[index].elapsedSeconds=Math.max(anchors[index].elapsedSeconds,anchors[index-1].elapsedSeconds+1);return{id,label,color,count:profiles.length,available:true,anchors,race:raceValue,maxTime:anchors.at(-1).elapsedSeconds,maxDistance:anchors.at(-1).distance,finish:true,cohortIds:profiles.map(candidate=>candidate.record.id).sort()};
    }
    function referenceProfiles(value){
      const item=typeof value==='string'?record(value):value,raceValue=race(item.raceKey),cacheKey=`${raceValue.key}|${item.class_name||'-'}|${item.sex||'-'}`;if(referenceCache.has(cacheKey))return referenceCache.get(cacheKey);const complete=completeProfiles(raceValue),field=cohortReference('field','Hela fältet','#66756f',complete,raceValue),classProfiles=complete.filter(candidate=>candidate.record.class_name===item.class_name),classReference=cohortReference('class','Min klass','#138a78',classProfiles,raceValue),sexProfiles=raceValue.isRelay?[]:complete.filter(candidate=>candidate.record.sex===item.sex),sexReference=raceValue.isRelay?{id:'sex',label:'Mitt kön',color:item.sex==='F'?'#db2777':'#2563eb',count:0,available:false,message:'Könsreferens används inte för stafettlag'}:cohortReference('sex','Mitt kön',item.sex==='F'?'#db2777':'#2563eb',sexProfiles,raceValue);const same=classReference.available&&sexReference.available&&classReference.cohortIds.join('|')===sexReference.cohortIds.join('|');if(same){classReference.coincidesWith='sex';sexReference.coincidesWith='class'}const result={field,class:classReference,sex:sexReference,completeCount:complete.length,minimumSize:MIN_REFERENCE_SIZE};referenceCache.set(cacheKey,result);return result;
    }
    function referenceGap(reference,runnerTime,runnerDistance){return reference?.available?timeAtDistance(reference,runnerDistance)-Number(runnerTime||0):null}
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
      return raceValue.checkpoints.slice(1).map((checkpoint,index)=>{
        const samples=[];
        for(const item of recordList){const segment=profile(item).segments.find(value=>value.to.checkpoint===checkpoint.key);if(segment)samples.push(segment)}
        const paces=samples.map(value=>value.paceSecondsKm),times=samples.map(value=>value.time);
        return{index,checkpoint,name:samples[0]?.name||`${raceValue.checkpoints[index].name}–${checkpoint.name}`,count:samples.length,medianPace:median(paces),q25Pace:quantile(paces,.25),q75Pace:quantile(paces,.75),medianTime:median(times),fastest:Math.min(...times.filter(finite),Infinity),samples};
      });
    }
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
    function segmentRanking(recordList,fromKey,toKey,metric='time'){
      const raceValue=race(recordList[0]?.raceKey),fromCp=raceValue?.checkpointMap.get(fromKey),toCp=raceValue?.checkpointMap.get(toKey);if(!fromCp||!toCp||toCp.index<=fromCp.index)return[];const entries=[];
      for(const item of recordList){const current=profile(item),from=current.anchors.find(anchor=>anchor.checkpoint===fromKey),to=current.anchors.find(anchor=>anchor.checkpoint===toKey);if(!from||!to||to.elapsedSeconds<=from.elapsedSeconds)continue;const time=to.elapsedSeconds-from.elapsedSeconds,distance=to.distance-from.distance,pace=time/distance,fromPlace=from.placeOverall,toPlace=to.placeOverall,gain=finite(fromPlace)&&finite(toPlace)?Number(fromPlace)-Number(toPlace):null;entries.push({record:item,time,distance,pace,gain,fromPlace,toPlace})}
      const medianPace=median(entries.map(entry=>entry.pace));entries.forEach(entry=>entry.relative=entry.pace/medianPace);
      return entries.sort(metric==='gain'?(a,b)=>(b.gain??-Infinity)-(a.gain??-Infinity):metric==='relative'?(a,b)=>a.relative-b.relative:(a,b)=>a.time-b.time);
    }
    function clubNames(recordList){return clubGroups(recordList).map(group=>[group.name,group.count,group.key]).sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0],'sv'))}
    function clubStats(recordList,name){const members=clubRecords(recordList,name),finishers=members.filter(statusFinished),starters=members.filter(statusStarter);return{name:clubDisplayName(name,recordList),key:clubKey(name),count:members.length,finishers:finishers.length,finishRate:starters.length?finishers.length/starters.length:null,medianFinish:median(finishers.map(item=>item.finish_seconds)),segments:segmentStats(members)}}
    function fieldFlow(recordList){
      const raceValue=race(recordList[0]?.raceKey);if(!raceValue)return[];return raceValue.checkpoints.slice(1).map(checkpoint=>{const times=[];for(const item of recordList){const anchor=profile(item).anchors.find(value=>value.checkpoint===checkpoint.key);if(anchor)times.push(anchor.elapsedSeconds)}return{checkpoint,name:checkpoint.name,count:times.length,median:median(times),q10:quantile(times,.1),q90:quantile(times,.9),spread:finite(quantile(times,.9))?quantile(times,.9)-quantile(times,.1):null}})
    }
    return{data,route,elevation,races,records,race,record,resultSplits,team,profile,distanceAtTime,timeAtDistance,stateAtTime,elevationAtDistance,completeProfiles,referenceProfiles,referenceGap,routePoint,routeSlice,elevationSlice,filtered,segmentStats,percentile,relativeProfile,advancements,segmentRanking,normalizeClubName,clubKey,clubDisplayName,clubRecords,clubNames,clubStats,fieldFlow,median,quantile,average,statusFinished,statusStarter,MIN_REFERENCE_SIZE};
  }
  window.GDataAdapter={create,median,quantile,average,statusFinished,statusStarter,normalizeClubName,clubKey,MIN_REFERENCE_SIZE};
})();
