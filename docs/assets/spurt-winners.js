(function(root,factory){
  'use strict';
  const api=factory();
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  if(root)root.GSpurtWinners=api;
})(typeof window!=='undefined'?window:null,function(){
  'use strict';
  const finite=value=>value!==null&&value!==undefined&&value!==''&&Number.isFinite(Number(value));
  const flag=value=>value===true||value===1||String(value).toLowerCase()==='true';

  function lastTimingControl(race){
    if(!race||race.isTeam)return null;
    const checkpoints=race.checkpoints||[];
    if(checkpoints.length<2)return null;
    const candidates=checkpoints.slice(0,-1).filter(checkpoint=>
      checkpoint.is_timing_point!==false&&
      (flag(checkpoint.timing_only)||flag(checkpoint.speaker_checkpoint))
    );
    return candidates.at(-1)||null;
  }

  function classOptions(race,sex){
    return [...new Set((race?.records||[])
      .filter(record=>record.sex===sex&&record.class_name)
      .map(record=>String(record.class_name).trim())
      .filter(Boolean))]
      .sort((a,b)=>a.localeCompare(b,'sv'));
  }

  function ranking(race,adapter,{sex,className='',maxSpeedKmh=35}={}){
    const control=lastTimingControl(race);
    const finishCheckpoint=race?.checkpoints?.at(-1)||null;
    if(!control||!finishCheckpoint)return{control,finishCheckpoint,rows:[]};
    const controlDistance=finite(control.route_distance_km)?Number(control.route_distance_km):null;
    const finishDistance=finite(finishCheckpoint.route_distance_km)?Number(finishCheckpoint.route_distance_km):null;
    const rows=[];
    for(const record of race.records||[]){
      if(record.sex!==sex||className&&record.class_name!==className)continue;
      if(!(adapter?.statusFinished?adapter.statusFinished(record):record.status==='FINISHED'))continue;
      const finish=Number(record.finish_seconds);
      if(!Number.isFinite(finish)||finish<=0)continue;
      const profile=adapter?.profile?.(record);
      const anchor=profile?.anchors?.find(item=>item.checkpoint===control.key);
      if(!anchor||!finite(anchor.elapsedSeconds))continue;
      const controlTime=Number(anchor.elapsedSeconds);
      const sprint=finish-controlTime;
      if(!Number.isFinite(sprint)||sprint<=0)continue;
      if(controlDistance!==null&&finishDistance!==null&&finishDistance>controlDistance){
        const speed=(finishDistance-controlDistance)/(sprint/3600);
        if(!Number.isFinite(speed)||speed<=0||speed>maxSpeedKmh)continue;
      }
      rows.push({record,control,sprintSeconds:sprint});
    }
    rows.sort((a,b)=>a.sprintSeconds-b.sprintSeconds||
      (Number(a.record.overall_place)||Number.MAX_SAFE_INTEGER)-(Number(b.record.overall_place)||Number.MAX_SAFE_INTEGER)||
      String(a.record.name||'').localeCompare(String(b.record.name||''),'sv'));
    let previous=null,rank=0;
    return{control,finishCheckpoint,rows:rows.map((item,index)=>{
      if(previous===null||item.sprintSeconds!==previous){rank=index+1;previous=item.sprintSeconds}
      return{...item,rank};
    })};
  }

  const top=(rows,limit=5)=>(rows||[]).filter(item=>item.rank<=limit);
  return{lastTimingControl,classOptions,ranking,top};
});
