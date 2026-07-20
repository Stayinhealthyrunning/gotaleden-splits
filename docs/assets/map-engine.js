(function(){
  'use strict';
  const NS='http://www.w3.org/2000/svg';
  const esc=value=>String(value??'').replace(/[&<>"']/g,character=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));
  const clamp=(value,min,max)=>Math.max(min,Math.min(max,Number(value)||0));
  function element(name,attributes={}){const node=document.createElementNS(NS,name);for(const [key,value] of Object.entries(attributes))node.setAttribute(key,String(value));return node}

  function create(container,{adapter,race,mode='replay'}){
    const width=1000,height=520,padding=46,routePoints=adapter.routeSlice(race),checkpoints=race.checkpoints;
    const meanLat=routePoints.reduce((sum,point)=>sum+point[0],0)/routePoints.length*Math.PI/180;
    const raw=routePoints.map(point=>[point[1]*Math.cos(meanLat),point[0],point[2]]),xs=raw.map(point=>point[0]),ys=raw.map(point=>point[1]),minX=Math.min(...xs),maxX=Math.max(...xs),minY=Math.min(...ys),maxY=Math.max(...ys),scale=Math.min((width-padding*2)/(maxX-minX||1),(height-padding*2)/(maxY-minY||1));
    const projectPoint=point=>[padding+(point[1]*Math.cos(meanLat)-minX)*scale,height-padding-(point[0]-minY)*scale];
    const projectDistance=distance=>projectPoint(adapter.routePoint(distance));
    container.innerHTML=`<div class="route-map ${mode}"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Gotaleden från ${esc(checkpoints[0].name)} till Alingsås"><defs><filter id="mapShadow-${mode}"><feDropShadow dx="0" dy="3" stdDeviation="4" flood-opacity=".24"/></filter><linearGradient id="routeGradient-${mode}" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#0b5e69"/><stop offset=".52" stop-color="#4aa2b8"/><stop offset="1" stop-color="#7eae69"/></linearGradient></defs><g data-map-world></g></svg><div class="map-tools"><button data-map-action="zoom-in" aria-label="Zooma in">+</button><button data-map-action="zoom-out" aria-label="Zooma ut">−</button><button data-map-action="fit">Visa hela banan</button></div><div class="map-scale">Officiell GPX-rutt</div></div>`;
    const svg=container.querySelector('svg'),world=container.querySelector('[data-map-world]'),path=routePoints.map((point,index)=>{const projected=projectPoint(point);return`${index?'L':'M'}${projected[0].toFixed(2)} ${projected[1].toFixed(2)}`}).join(' ');
    const shadow=element('path',{d:path,class:'route-shadow'}),line=element('path',{d:path,class:'route-line-map',stroke:`url(#routeGradient-${mode})`});world.append(shadow,line);
    checkpoints.forEach((checkpoint,index)=>{const point=projectDistance(checkpoint.route_distance_km),group=element('g',{class:`map-checkpoint ${checkpoint.is_relay_exchange?'exchange':''}`,'data-checkpoint':checkpoint.key}),circle=element('circle',{cx:point[0],cy:point[1],r:index===0||index===checkpoints.length-1?7:5}),label=element('text',{x:point[0]+(index>checkpoints.length*.65?-10:10),y:point[1]-10,'text-anchor':index>checkpoints.length*.65?'end':'start'});label.textContent=checkpoint.name;group.append(circle,label);world.append(group)});
    const markers=element('g',{class:'map-runners'});world.append(markers);
    let markerMap=new Map(),view={scale:1,x:0,y:0},drag=null,destroyed=false;
    function transform(){world.setAttribute('transform',`translate(${view.x} ${view.y}) scale(${view.scale})`);world.style.setProperty('--map-inverse-scale',String(1/view.scale))}
    function setRunners(runners){
      const active=new Set(runners.map(runner=>String(runner.id)));for(const [id,node] of markerMap)if(!active.has(id)){node.remove();markerMap.delete(id)}
      runners.forEach((runner,index)=>{const id=String(runner.id);let group=markerMap.get(id);if(!group){group=element('g',{class:'map-runner',tabindex:'0','data-runner':id,filter:`url(#mapShadow-${mode})`});const pulse=element('circle',{class:'runner-pulse',r:14}),dot=element('circle',{class:'runner-dot',r:9,fill:runner.color}),number=element('text',{class:'runner-number',x:0,y:4,'text-anchor':'middle'}),label=element('text',{class:'runner-label',x:14,y:-12});number.textContent=String(index+1);label.textContent=runner.name;group.append(pulse,dot,number,label);markers.append(group);markerMap.set(id,group)}const point=projectDistance(runner.distance);group.setAttribute('transform',`translate(${point[0]} ${point[1]})`);group.querySelector('.runner-dot').setAttribute('fill',runner.color);group.querySelector('.runner-number').textContent=String(index+1);group.querySelector('.runner-label').textContent=runner.name;group.setAttribute('aria-label',runner.label||`${runner.name}, ${runner.distance.toFixed(1)} kilometer`);group.classList.toggle('finished',Boolean(runner.finished));group.classList.toggle('stopped',Boolean(runner.stopped))})
    }
    function zoom(factor,origin={x:width/2,y:height/2}){const previous=view.scale,next=clamp(previous*factor,1,7),ratio=next/previous;view.x=origin.x-(origin.x-view.x)*ratio;view.y=origin.y-(origin.y-view.y)*ratio;view.scale=next;if(next===1){view.x=0;view.y=0}transform()}
    function fit(){view={scale:1,x:0,y:0};transform()}
    function svgPoint(event){const rect=svg.getBoundingClientRect();return{x:(event.clientX-rect.left)/rect.width*width,y:(event.clientY-rect.top)/rect.height*height}}
    function pointerDown(event){if(event.button!==0)return;drag={...svgPoint(event),originX:view.x,originY:view.y,pointerId:event.pointerId};svg.setPointerCapture?.(event.pointerId);svg.classList.add('dragging')}
    function pointerMove(event){if(!drag)return;const point=svgPoint(event);view.x=drag.originX+point.x-drag.x;view.y=drag.originY+point.y-drag.y;transform()}
    function pointerUp(event){if(!drag)return;svg.releasePointerCapture?.(event.pointerId);drag=null;svg.classList.remove('dragging')}
    svg.addEventListener('wheel',event=>{event.preventDefault();zoom(event.deltaY<0?1.24:1/1.24,svgPoint(event))},{passive:false});svg.addEventListener('pointerdown',pointerDown);svg.addEventListener('pointermove',pointerMove);svg.addEventListener('pointerup',pointerUp);svg.addEventListener('pointercancel',pointerUp);
    container.querySelector('[data-map-action="zoom-in"]').onclick=()=>zoom(1.35);container.querySelector('[data-map-action="zoom-out"]').onclick=()=>zoom(1/1.35);container.querySelector('[data-map-action="fit"]').onclick=fit;
    transform();
    return{setRunners,fit,zoom,projectDistance,destroy(){destroyed=true;markerMap.clear();container.innerHTML=''},get destroyed(){return destroyed}};
  }
  window.GMapEngine={create};
})();
