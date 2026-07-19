(function(){
  function create(canvas,route){
    const ctx=canvas.getContext("2d"),pad=28,points=route.points;let runners=[],duration=1,progress=0,timer=null;
    const lats=points.map(p=>p[0]),lons=points.map(p=>p[1]),minLat=Math.min(...lats),maxLat=Math.max(...lats),minLon=Math.min(...lons),maxLon=Math.max(...lons);
    const project=p=>[pad+(p[1]-minLon)/(maxLon-minLon)*(canvas.width-pad*2),canvas.height-pad-(p[0]-minLat)/(maxLat-minLat)*(canvas.height-pad*2)];
    const routePoint=distance=>{const target=Math.max(0,Math.min(route.full_distance_km,distance));let lo=0,hi=points.length-1;while(lo<hi){const mid=(lo+hi)>>1;if(points[mid][3]<target)lo=mid+1;else hi=mid}return project(points[lo])};
    function estimatedDistance(r,time){const values=r.splits;if(!values.length)return null;if(time<=0)return r.offset;if(time>=values[values.length-1].elapsed_seconds)return r.offset+values[values.length-1].distance;let prev={elapsed_seconds:0,distance:0},next=values[0];for(const value of values){if(value.elapsed_seconds>=time){next=value;break}prev=value}const share=(time-prev.elapsed_seconds)/(next.elapsed_seconds-prev.elapsed_seconds||1);return r.offset+prev.distance+(next.distance-prev.distance)*share}
    function draw(){ctx.clearRect(0,0,canvas.width,canvas.height);ctx.lineCap="round";ctx.lineJoin="round";ctx.strokeStyle="rgba(255,255,255,.9)";ctx.lineWidth=10;ctx.beginPath();points.forEach((p,i)=>{const q=project(p);i?ctx.lineTo(...q):ctx.moveTo(...q)});ctx.stroke();ctx.strokeStyle="#69aebc";ctx.lineWidth=4;ctx.stroke();const time=progress*duration;runners.forEach((r,i)=>{const d=estimatedDistance(r,time);if(d==null)return;const q=routePoint(d);ctx.fillStyle=window.GCharts.palette[i%5];ctx.beginPath();ctx.arc(q[0],q[1],8,0,Math.PI*2);ctx.fill();ctx.strokeStyle="#fff";ctx.lineWidth=2;ctx.stroke();ctx.fillStyle="#15343a";ctx.font="700 13px system-ui";ctx.fillText(r.name,q[0]+11,q[1]-8)});return time}
    function set(next){runners=next;duration=Math.max(1,...runners.flatMap(r=>r.splits.map(s=>s.elapsed_seconds)));draw()}
    function seek(value){progress=Math.max(0,Math.min(1,value));return draw()}
    function play(onFrame){if(timer){cancelAnimationFrame(timer);timer=null;return false}let last=performance.now();function tick(now){progress=Math.min(1,progress+(now-last)/30000);last=now;onFrame(progress,draw());if(progress<1)timer=requestAnimationFrame(tick);else timer=null}timer=requestAnimationFrame(tick);return true}
    return{set,seek,play};
  }
  window.GReplay={create};
})();
