(function(){
  'use strict';
  const TILE_URL='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
  const TILE_ATTRIBUTION='&copy; OpenStreetMap-bidragsgivare';
  const esc=value=>String(value??'').replace(/[&<>"']/g,character=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));
  const clamp=(value,min,max)=>Math.max(min,Math.min(max,Number(value)||0));
  const validLatLng=value=>Array.isArray(value)&&value.length>=2&&Number.isFinite(Number(value[0]))&&Number.isFinite(Number(value[1]));
  let engineSequence=0;

  function routeSegment(adapter,from,to){
    const start=Math.max(0,Number(from)||0),end=Math.max(start,Number(to)||0),points=[adapter.routePoint(start)];
    for(const point of adapter.route.points||[])if(Number(point[3])>start&&Number(point[3])<end)points.push([Number(point[0]),Number(point[1]),Number(point[3])]);
    points.push(adapter.routePoint(end));return points.filter(validLatLng).map(point=>[Number(point[0]),Number(point[1])]);
  }
  function markerText(runner,index){return runner.bib?String(runner.bib).slice(-3):String(runner.name||index+1).split(/\s+/).map(part=>part[0]).join('').slice(0,2).toUpperCase()}
  function shell(container){
    container.innerHTML='<div class="route-map leaflet-primary" data-map-engine="leaflet"><div class="leaflet-map" data-leaflet-map></div><div class="map-engine-status" data-map-status hidden></div><div class="map-primary-actions"><button type="button" data-map-action="fit">Visa hela banan</button></div></div>';
    return{root:container.firstElementChild,mapElement:container.querySelector('[data-leaflet-map]'),status:container.querySelector('[data-map-status]')};
  }
  function createLeaflet(container,{adapter,race,mode}){
    const elements=shell(container),routePoints=adapter.routeSlice(race).filter(validLatLng),coordinates=routePoints.map(point=>[Number(point[0]),Number(point[1])]);
    if(coordinates.length<2)throw new Error('Banan saknar giltiga GPS-koordinater.');
    const map=L.map(elements.mapElement,{zoomControl:true,preferCanvas:true,attributionControl:true,keyboard:true}),bounds=L.latLngBounds(coordinates);
    if(bounds.isValid())map.fitBounds(bounds,{padding:[42,42],animate:false});else map.setView(coordinates[0],9);
    let tileErrors=0,follow=false,destroyed=false;
    const tileLayer=L.tileLayer(TILE_URL,{maxZoom:17,attribution:TILE_ATTRIBUTION}).on('tileerror',()=>{tileErrors++;if(tileErrors===4){elements.status.hidden=false;elements.status.textContent='Kartbakgrunden kunde inte läsas, men banlager och deltagare fungerar.'}}).addTo(map);
    const routeGroup=L.layerGroup().addTo(map),routeColor='#0b6671';
    L.polyline(coordinates,{color:'#fff',weight:11,opacity:.8,lineCap:'round'}).addTo(routeGroup);
    L.polyline(coordinates,{color:routeColor,weight:5,opacity:.97,lineCap:'round'}).addTo(routeGroup);
    for(const checkpoint of race.checkpoints){
      const point=adapter.routePoint(checkpoint.route_distance_km);if(!validLatLng(point))continue;
      const finish=checkpoint.key==='alingsas',start=checkpoint===race.checkpoints[0],marker=L.circleMarker([point[0],point[1]],{radius:finish||start?8:5,color:routeColor,weight:2,fillColor:finish?'#db7b3b':start?'#f1cc6e':checkpoint.is_relay_exchange?'#d8edcd':'#fffefa',fillOpacity:1}).addTo(routeGroup);
      marker.bindTooltip(`${race.section} · ${checkpoint.name} · ${(checkpoint.route_distance_km-race.startDistanceKm).toFixed(1)} km`,{direction:'top',className:'checkpoint-map-label',offset:[0,-5]});
    }
    const markerMap=new Map();
    function setRunners(runners){
      const active=new Set(runners.map(runner=>String(runner.id)));for(const [id,item] of markerMap)if(!active.has(id)){item.marker.remove();item.tail.remove();markerMap.delete(id)}
      runners.forEach((runner,index)=>{
        const id=String(runner.id),point=adapter.routePoint(runner.distance);if(!validLatLng(point))return;let item=markerMap.get(id);
        if(!item){
          const icon=L.divIcon({className:'gotaleden-runner-icon',html:`<div class="runner-marker" style="--runner-color:${runner.color};background:${runner.color}"><span>${esc(markerText(runner,index))}</span><b>${index+1}</b></div>`,iconSize:[42,42],iconAnchor:[21,21]});
          const marker=L.marker([point[0],point[1]],{icon,zIndexOffset:500-index,keyboard:true}).addTo(map).bindTooltip(`${esc(runner.name)} · #${esc(runner.bib||'–')}`,{direction:'top',offset:[0,-20],className:'runner-map-tooltip'}),tail=L.polyline([],{color:runner.color,weight:6,opacity:.72,lineCap:'round'}).addTo(map);item={marker,tail,distance:runner.distance};markerMap.set(id,item)
        }
        item.distance=runner.distance;item.marker.setLatLng([point[0],point[1]]);item.tail.setLatLngs(routeSegment(adapter,Math.max(race.startDistanceKm,runner.distance-2.4),runner.distance));const markerElement=item.marker.getElement()?.querySelector('.runner-marker');markerElement?.classList.toggle('finished',Boolean(runner.finished));markerElement?.classList.toggle('stopped',Boolean(runner.stopped));item.marker.setTooltipContent(`${esc(runner.name)} · #${esc(runner.bib||'–')} · ${(runner.distance-race.startDistanceKm).toFixed(1)} km`)
      });
      if(follow&&runners.length===1){const point=adapter.routePoint(runners[0].distance);map.panTo([point[0],point[1]],{animate:false})}
    }
    function fit(){follow=false;map.invalidateSize(false);if(bounds.isValid())map.fitBounds(bounds,{padding:[42,42],animate:false});elements.root.dispatchEvent(new CustomEvent('gotaleden:map-fit'))}
    function zoom(factor){factor>1?map.zoomIn():map.zoomOut()}
    function setFollow(value){follow=Boolean(value);return follow}
    function panToDistance(distance,zoomLevel=14){const point=adapter.routePoint(distance);if(validLatLng(point))map.setView([point[0],point[1]],zoomLevel,{animate:false})}
    function fitDistances(distances){const points=distances.map(distance=>adapter.routePoint(distance)).filter(validLatLng).map(point=>[point[0],point[1]]);if(!points.length)return;if(points.length===1){map.setView(points[0],14,{animate:false});return}map.fitBounds(L.latLngBounds(points),{padding:[90,90],maxZoom:14,animate:false})}
    elements.root.querySelector('[data-map-action="fit"]').onclick=fit;
    setTimeout(()=>{if(destroyed)return;map.invalidateSize(false);fit()},80);
    return{kind:'leaflet',map,tileLayer,setRunners,fit,zoom,setFollow,panToDistance,fitDistances,destroy(){destroyed=true;markerMap.clear();map.remove();container.innerHTML=''},get destroyed(){return destroyed}};
  }
  function createFallback(container,{adapter,race,mode}){
    const id=`fallback-${++engineSequence}`,width=1000,height=520,padding=46,routePoints=adapter.routeSlice(race),meanLat=routePoints.reduce((sum,point)=>sum+point[0],0)/routePoints.length*Math.PI/180,xs=routePoints.map(point=>point[1]*Math.cos(meanLat)),ys=routePoints.map(point=>point[0]),minX=Math.min(...xs),maxX=Math.max(...xs),minY=Math.min(...ys),maxY=Math.max(...ys),scale=Math.min((width-padding*2)/(maxX-minX||1),(height-padding*2)/(maxY-minY||1)),project=point=>[padding+(point[1]*Math.cos(meanLat)-minX)*scale,height-padding-(point[0]-minY)*scale],path=routePoints.map((point,index)=>{const projected=project(point);return`${index?'L':'M'}${projected[0].toFixed(1)} ${projected[1].toFixed(1)}`}).join(' ');
    container.innerHTML=`<div class="route-map fallback-map" data-map-engine="fallback"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Förenklad reservkarta"><path class="route-shadow" d="${path}"/><path class="route-line-map" d="${path}"/><g data-fallback-runners></g></svg><div class="map-engine-status">Interaktiv kartbakgrund saknas. Förenklad banvy används.</div></div>`;const runners=container.querySelector('[data-fallback-runners]');
    function setRunners(values){runners.innerHTML=values.map((runner,index)=>{const point=project(adapter.routePoint(runner.distance));return`<g class="map-runner" transform="translate(${point[0]} ${point[1]})"><circle class="runner-pulse" r="14"/><circle class="runner-dot" r="9" fill="${runner.color}"/><text class="runner-number" y="4" text-anchor="middle">${index+1}</text><text class="runner-label" x="14" y="-12">${esc(runner.name)}</text></g>`}).join('')}
    return{kind:'fallback',setRunners,fit(){},zoom(){},setFollow(){return false},panToDistance(){},fitDistances(){},destroy(){container.innerHTML=''},get destroyed(){return false}};
  }
  function create(container,options){
    if(window.L){try{return createLeaflet(container,options)}catch(error){console.error('Leaflet-kartan kunde inte starta',error)}}
    return createFallback(container,options)
  }
  window.GMapEngine={create,TILE_URL,TILE_ATTRIBUTION};
})();
