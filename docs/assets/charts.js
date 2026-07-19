(function(){
  const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const palette=["#0d5964","#51a9c5","#7cac69","#d19b55","#9d6ba8"];
  function svg(viewBox,body){return `<svg viewBox="${viewBox}" role="img">${body}</svg>`}
  function histogram(values,bins=12){
    if(!values.length)return '<div class="empty">Ingen måltid att visa.</div>';
    const min=Math.min(...values),max=Math.max(...values),step=Math.max((max-min)/bins,1),counts=Array(bins).fill(0);
    values.forEach(v=>counts[Math.min(bins-1,Math.floor((v-min)/step))]++);const peak=Math.max(...counts),w=680,h=250,p=34,bw=(w-p*2)/bins;
    let body=`<line class="axis" x1="${p}" y1="${h-p}" x2="${w-p}" y2="${h-p}"/>`;
    counts.forEach((n,i)=>{const bh=n/peak*(h-p*2);body+=`<rect class="bar" x="${p+i*bw+2}" y="${h-p-bh}" width="${bw-4}" height="${bh}" rx="3"><title>${n} resultat</title></rect>`});
    for(let i=0;i<=4;i++){const x=p+(w-p*2)*i/4,t=min+(max-min)*i/4;body+=`<text x="${x}" y="${h-9}" text-anchor="middle">${Math.floor(t/3600)}:${String(Math.round(t%3600/60)).padStart(2,"0")}</text>`}
    return svg(`0 0 ${w} ${h}`,body);
  }
  function bars(items){
    if(!items.length)return '<div class="empty">Ingen klassdata.</div>';const rows=items.slice(0,7),max=Math.max(...rows.map(x=>x[1])),w=460,h=rows.length*34+12;
    return svg(`0 0 ${w} ${h}`,rows.map((x,i)=>{const y=i*34+5,bw=x[1]/max*230;return `<text x="0" y="${y+17}">${esc(x[0].length>24?x[0].slice(0,23)+'…':x[0])}</text><rect class="bar ${i%2?'alt':''}" x="190" y="${y}" width="${bw}" height="22" rx="6"/><text x="${196+bw}" y="${y+16}">${x[1]}</text>`}).join(""));
  }
  function lines(series,xLabels,yFormat=v=>String(Math.round(v))){
    if(!series.length)return '<div class="empty">Välj resultat med publicerade passeringar.</div>';const w=900,h=310,p={l:55,r:20,t:20,b:55};const all=series.flatMap(s=>s.values.filter(v=>v!=null));if(!all.length)return '<div class="empty">Passeringar saknas.</div>';const max=Math.max(...all)*1.04,min=Math.min(0,...all);const x=i=>p.l+(w-p.l-p.r)*(xLabels.length===1?0:i/(xLabels.length-1));const y=v=>h-p.b-(v-min)/(max-min||1)*(h-p.t-p.b);
    let body="";for(let i=0;i<5;i++){const value=min+(max-min)*i/4,yy=y(value);body+=`<line class="gridline" x1="${p.l}" y1="${yy}" x2="${w-p.r}" y2="${yy}"/><text x="${p.l-7}" y="${yy+4}" text-anchor="end">${esc(yFormat(value))}</text>`}
    xLabels.forEach((label,i)=>{body+=`<text x="${x(i)}" y="${h-27}" text-anchor="middle" transform="rotate(-22 ${x(i)} ${h-27})">${esc(label)}</text>`});
    series.forEach((s,si)=>{const points=s.values.map((v,i)=>v==null?null:[x(i),y(v)]);let d="",open=false;points.forEach(pt=>{if(!pt){open=false;return}d+=`${open?'L':'M'}${pt[0]},${pt[1]} `;open=true});body+=`<path class="plot-line" stroke="${palette[si%palette.length]}" d="${d}"/>`;points.filter(Boolean).forEach(pt=>body+=`<circle class="point" fill="${palette[si%palette.length]}" cx="${pt[0]}" cy="${pt[1]}" r="4"/>`)});
    const legend=`<div class="legend">${series.map((s,i)=>`<span><i style="background:${palette[i%palette.length]}"></i>${esc(s.name)}</span>`).join("")}</div>`;return legend+svg(`0 0 ${w} ${h}`,body);
  }
  window.GCharts={histogram,bars,lines,palette};
})();
