// ─── CYPHER-GLOBE.JS ───
// Interactive globe with TopoJSON borders, country click, RSS intel feed

(function () {
  var gc = document.getElementById('globeHomeCanvas');
  if (!gc) return;

  function sizeGlobe() {
    var panel = document.getElementById('home-right-panel');
    var widget = document.getElementById('globe-widget');
    if (!panel || !widget) return;
    var panelW = panel.offsetWidth;
    if (panelW < 50) return;
    // Support both old and new title class names
    var titleEl = widget.querySelector('.hw-title') || widget.querySelector('.hud-widget-title');
    var coordEl = document.getElementById('globe-coord-bar');
    var titleH = titleEl ? titleEl.offsetHeight : 24;
    var coordH = coordEl ? coordEl.offsetHeight : 16;
    var availH = widget.offsetHeight - titleH - coordH - 20;
    var side = Math.min(Math.floor(panelW * 0.5) - 16, availH);
    side = Math.max(side, 80);
    gc.width = side; gc.height = side;
    GW = gc.width; GH = gc.height;
    gcx = GW / 2; gcy = GH / 2; GR = Math.floor(side * 0.46);
  }

  var gctx = gc.getContext('2d');
  var GW = 140, GH = 140, gcx = 70, gcy = 70, GR = 64;
  var gRotX = 0.3, gRotY = 0;
  var gDragging = false, gLastX = 0, gLastY = 0;
  var gAutoSpin = true;
  var gLastPinchDist = null;
  var gCountries = [];
  var gSelected = null, gHovered = null;

  var gNameMap = {
    '840':'United States of America','643':'Russia','156':'China','076':'Brazil',
    '036':'Australia','356':'India','276':'Germany','392':'Japan','124':'Canada',
    '710':'South Africa','826':'United Kingdom','250':'France','380':'Italy',
    '724':'Spain','484':'Mexico','586':'Pakistan','566':'Nigeria','818':'Egypt',
    '012':'Algeria','032':'Argentina','116':'Cambodia','120':'Cameroon','152':'Chile',
    '170':'Colombia','191':'Croatia','192':'Cuba','203':'Czechia','208':'Denmark',
    '218':'Ecuador','231':'Ethiopia','246':'Finland','288':'Ghana','300':'Greece',
    '348':'Hungary','360':'Indonesia','364':'Iran','368':'Iraq','372':'Ireland',
    '376':'Israel','400':'Jordan','398':'Kazakhstan','404':'Kenya','418':'Laos',
    '422':'Lebanon','458':'Malaysia','528':'Netherlands','554':'New Zealand',
    '578':'Norway','591':'Panama','604':'Peru','608':'Philippines','616':'Poland',
    '620':'Portugal','642':'Romania','682':'Saudi Arabia','703':'Slovakia',
    '706':'Somalia','752':'Sweden','756':'Switzerland','760':'Syria','764':'Thailand',
    '788':'Tunisia','792':'Turkey','804':'Ukraine','784':'United Arab Emirates',
    '858':'Uruguay','704':'Vietnam','887':'Yemen','410':'South Korea','050':'Bangladesh',
    '104':'Myanmar','144':'Sri Lanka','512':'Oman','634':'Qatar','414':'Kuwait','048':'Bahrain'
  };

  var gTagColors = {
    TECH:'rgba(0,200,255,0.9)',POL:'rgba(180,0,255,0.9)',ECO:'rgba(50,255,100,0.9)',
    MIL:'rgba(255,50,50,0.9)',ENV:'rgba(100,255,150,0.9)',WORLD:'rgba(255,180,50,0.9)',
    MIN:'rgba(255,150,50,0.9)',SEC:'rgba(255,80,80,0.9)',SPT:'rgba(255,120,50,0.9)',
    NEWS:'rgba(255,200,230,0.6)'
  };

  function gProject(lat, lon) {
    var phi=lat*Math.PI/180, lam=lon*Math.PI/180;
    var x=Math.cos(phi)*Math.sin(lam), y=Math.sin(phi), z=Math.cos(phi)*Math.cos(lam);
    var cosX=Math.cos(gRotX),sinX=Math.sin(gRotX),cosY=Math.cos(gRotY),sinY=Math.sin(gRotY);
    var x2=x*cosY-z*sinY, z2=x*sinY+z*cosY;
    var y2=y*cosX-z2*sinX, z3=y*sinX+z2*cosX;
    return {x:gcx+x2*GR, y:gcy-y2*GR, z:z3};
  }

  function gDrawCountry(coords, isSelected, isHovered) {
    if (!coords) return;
    coords.forEach(function (ring) {
      if (!ring || ring.length < 2) return;
      gctx.beginPath();
      var first=true, prevVis=false;
      ring.forEach(function (pt) {
        var p=gProject(pt[1],pt[0]);
        if(p.z>0){if(first||!prevVis){gctx.moveTo(p.x,p.y);first=false;}else gctx.lineTo(p.x,p.y);}
        prevVis=p.z>0;
      });
      gctx.closePath();
      if(isSelected){gctx.fillStyle='rgba(0,200,255,0.35)';gctx.strokeStyle='rgba(0,200,255,1.0)';gctx.lineWidth=1.2;}
      else if(isHovered){gctx.fillStyle='rgba(0,200,255,0.18)';gctx.strokeStyle='rgba(0,200,255,0.6)';gctx.lineWidth=0.7;}
      else{gctx.fillStyle='rgba(0,200,255,0.07)';gctx.strokeStyle='rgba(0,200,255,0.25)';gctx.lineWidth=0.4;}
      gctx.fill(); gctx.stroke();
    });
  }

  function gDraw() {
    gctx.clearRect(0,0,GW,GH);
    gctx.beginPath();gctx.arc(gcx,gcy,GR+1,0,Math.PI*2);gctx.strokeStyle='rgba(0,200,255,0.08)';gctx.lineWidth=8;gctx.stroke();
    gctx.beginPath();gctx.arc(gcx,gcy,GR,0,Math.PI*2);gctx.fillStyle='rgba(0,6,20,0.98)';gctx.fill();gctx.strokeStyle='rgba(0,200,255,0.5)';gctx.lineWidth=1.2;gctx.stroke();
    gctx.lineWidth=0.3;
    for(var la=-60;la<=60;la+=30){gctx.beginPath();var f=true;for(var lo=-180;lo<=180;lo+=4){var p=gProject(la,lo);if(p.z>0){f?gctx.moveTo(p.x,p.y):gctx.lineTo(p.x,p.y);f=false;}else f=true;}gctx.strokeStyle='rgba(0,200,255,0.06)';gctx.stroke();}
    for(var lo2=-150;lo2<=180;lo2+=30){gctx.beginPath();var f2=true;for(var la2=-80;la2<=80;la2+=4){var p2=gProject(la2,lo2);if(p2.z>0){f2?gctx.moveTo(p2.x,p2.y):gctx.lineTo(p2.x,p2.y);f2=false;}else f2=true;}gctx.strokeStyle='rgba(0,200,255,0.06)';gctx.stroke();}
    gCountries.forEach(function(f){
      if(!f||!f.geometry)return;
      var name=f.properties&&f.properties.name;
      var isSel=gSelected&&name===gSelected;
      var isHov=gHovered&&name===gHovered&&!isSel;
      var coords=[];
      if(f.geometry.type==='Polygon')coords=f.geometry.coordinates;
      else if(f.geometry.type==='MultiPolygon')f.geometry.coordinates.forEach(function(p){coords=coords.concat(p);});
      gDrawCountry(coords,isSel,isHov);
    });
    for(var sy=gcy-GR;sy<gcy+GR;sy+=5){var hw=Math.sqrt(Math.max(0,GR*GR-(sy-gcy)*(sy-gcy)));if(hw>0){gctx.fillStyle='rgba(0,200,255,0.01)';gctx.fillRect(gcx-hw,sy,hw*2,2);}}
    gctx.globalCompositeOperation='destination-in';
    gctx.beginPath();gctx.arc(gcx,gcy,GR,0,Math.PI*2);gctx.fillStyle='#000';gctx.fill();
    gctx.globalCompositeOperation='source-over';
    gctx.beginPath();gctx.arc(gcx,gcy,GR,0,Math.PI*2);gctx.strokeStyle='rgba(0,200,255,0.5)';gctx.lineWidth=1.2;gctx.stroke();
  }

  function gSelectCountry(name) {
    gSelected=name;
    var labelEl=document.getElementById('globe-country-label');
    var intelEl=document.getElementById('globe-intel');
    if(labelEl){labelEl.textContent=name.toUpperCase();labelEl.style.color='rgba(0,200,255,0.9)';}
    if(intelEl)intelEl.innerHTML='<div style="font-size:10px;color:rgba(255,200,230,0.3);padding:6px 0;letter-spacing:0.1em;">FETCHING INTEL...</div>';
    fetch('/news?country='+encodeURIComponent(name.toLowerCase()))
      .then(function(r){return r.json();})
      .then(function(data){
        if(!intelEl)return;
        if(!data.articles||data.articles.length===0){intelEl.innerHTML='<div style="font-size:10px;color:rgba(255,200,230,0.25);padding:6px 0;">No intel available for this region.</div>';return;}
        intelEl.innerHTML=data.articles.map(function(a){
          var c=gTagColors[a.tag]||'rgba(255,80,180,0.9)';
          var src=a.source?'<span style="font-size:8px;color:rgba(255,200,230,0.3);margin-left:4px;">— '+a.source+'</span>':'';
          return '<div class="intel-item"><span class="intel-tag" style="color:'+c+';">'+a.tag+'</span><span>'+a.title+src+'</span></div>';
        }).join('');
      })
      .catch(function(){if(intelEl)intelEl.innerHTML='<div style="font-size:10px;color:rgba(255,50,50,0.5);padding:6px 0;">INTEL FEED OFFLINE</div>';});
  }

  function gGetCountryAt(mx, my) {
    var best=null,bestZ=-999;
    gCountries.forEach(function(f){
      if(!f||!f.geometry||!f.properties||!f.properties.name)return;
      var coords=[];
      if(f.geometry.type==='Polygon')coords=f.geometry.coordinates;
      else if(f.geometry.type==='MultiPolygon')f.geometry.coordinates.forEach(function(p){coords=coords.concat(p);});
      coords.forEach(function(ring){
        if(!ring||ring.length<3)return;
        var pts=[],inside=false;
        ring.forEach(function(pt){var p=gProject(pt[1],pt[0]);if(p.z>0)pts.push(p);});
        if(pts.length<3)return;
        for(var i=0,j=pts.length-1;i<pts.length;j=i++){if(((pts[i].y>my)!=(pts[j].y>my))&&(mx<(pts[j].x-pts[i].x)*(my-pts[i].y)/(pts[j].y-pts[i].y)+pts[i].x))inside=!inside;}
        if(inside){var sz=pts.reduce(function(a,b){return a+b.z;},0)/pts.length;if(sz>bestZ){bestZ=sz;best=f.properties.name;}}
      });
    });
    return best;
  }

  gc.addEventListener('mousedown',function(e){gDragging=false;gAutoSpin=false;gLastX=e.offsetX;gLastY=e.offsetY;});
  gc.addEventListener('mousemove',function(e){
    var dx=e.offsetX-gLastX,dy=e.offsetY-gLastY;
    if(e.buttons&&(Math.abs(dx)>1||Math.abs(dy)>1)){gDragging=true;gRotY-=dx*0.007;gRotX+=dy*0.007;gRotX=Math.max(-1.3,Math.min(1.3,gRotX));gLastX=e.offsetX;gLastY=e.offsetY;}
    var ddx=e.offsetX-gcx,ddy=gcy-e.offsetY;
    var coordEl=document.getElementById('globe-coord');
    if(coordEl&&Math.sqrt(ddx*ddx+ddy*ddy)<GR)coordEl.textContent='LAT '+(ddy/GR*90).toFixed(1)+' LON '+(ddx/GR*180).toFixed(1);
    if(!e.buttons){var hov=gGetCountryAt(e.offsetX,e.offsetY);if(hov!==gHovered){gHovered=hov;gc.style.cursor=hov?'pointer':'grab';}}
  });
  gc.addEventListener('mouseup',function(e){if(!gDragging){var n=gGetCountryAt(e.offsetX,e.offsetY);if(n)gSelectCountry(n);}gDragging=false;});
  gc.addEventListener('mouseleave',function(){gDragging=false;gHovered=null;});
  gc.addEventListener('wheel',function(e){e.preventDefault();var delta=e.deltaY>0?-6:6;GR=Math.max(40,Math.min(200,GR+delta));gcx=GW/2;gcy=GH/2;},{passive:false});
  gc.addEventListener('touchstart',function(e){e.preventDefault();gAutoSpin=false;var r=gc.getBoundingClientRect();gLastX=e.touches[0].clientX-r.left;gLastY=e.touches[0].clientY-r.top;gDragging=false;},{passive:false});
  gc.addEventListener('touchmove',function(e){
    e.preventDefault();var r=gc.getBoundingClientRect();
    if(e.touches.length===2){var dx=e.touches[0].clientX-e.touches[1].clientX;var dy=e.touches[0].clientY-e.touches[1].clientY;var dist=Math.sqrt(dx*dx+dy*dy);if(gLastPinchDist)GR=Math.max(40,Math.min(200,GR+(dist-gLastPinchDist)*0.5));gLastPinchDist=dist;}
    else{var tx=e.touches[0].clientX-r.left,ty=e.touches[0].clientY-r.top;gRotY-=(tx-gLastX)*0.007;gRotX+=(ty-gLastY)*0.007;gRotX=Math.max(-1.3,Math.min(1.3,gRotX));gLastX=tx;gLastY=ty;gDragging=true;gLastPinchDist=null;}
  },{passive:false});
  gc.addEventListener('touchend',function(){gDragging=false;gLastPinchDist=null;});

  function gLoop(){
    if(!gDragging&&gAutoSpin)gRotY+=0.002;
    gDraw();
    requestAnimationFrame(gLoop);
  }

  function loadWorld(world){
    gCountries=topojson.feature(world,world.objects.countries).features;
    gCountries.forEach(function(f){
      var id=String(f.id).padStart(3,'0');
      if(!f.properties)f.properties={};
      if(gNameMap[id])f.properties.name=gNameMap[id];
      else if(!f.properties.name)f.properties.name='Region '+f.id;
    });
    var tag=document.getElementById('globe-live-tag');
    if(tag){tag.textContent='LIVE';tag.style.color='rgba(50,255,100,0.8)';}
  }

  function tryLoad(){
    if(typeof topojson==='undefined'){setTimeout(tryLoad,200);return;}
    fetch('https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json')
      .then(function(r){return r.json();})
      .then(function(world){loadWorld(world);sizeGlobe();})
      .catch(function(){var tag=document.getElementById('globe-live-tag');if(tag){tag.textContent='OFFLINE';tag.style.color='rgba(255,50,50,0.7)';}});
  }

  window.addEventListener('resize',sizeGlobe);

  // Retry until panel has real width (CSS calc needs layout pass)
  function sizeGlobeRetry(attempts) {
    var panel = document.getElementById('home-right-panel');
    if (panel && panel.offsetWidth > 50) {
      sizeGlobe(); tryLoad();
    } else if (attempts > 0) {
      setTimeout(function(){ sizeGlobeRetry(attempts - 1); }, 200);
    } else {
      sizeGlobe(); tryLoad();
    }
  }
  setTimeout(function(){ sizeGlobeRetry(20); }, 400);
  gLoop();
})();
