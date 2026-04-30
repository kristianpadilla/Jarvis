// ─── CYPHER-UI.JS ───────────────────────────────────────────────────────────
// State, waveform, clocks, weather, timer, calendar, mode system
// LEFT PANEL: sys donuts, temps, network+storage, processes,
//             session log+goals, countdown, peripherals, FPS

// ─── WAVEFORM ───────────────────────────────────────────────────────────────
var waveCanvas = document.getElementById('cypher-waveform-canvas');
var waveCtx = waveCanvas ? waveCanvas.getContext('2d') : null;
var wavePhase = 0, waveTargetAmplitude = 3, waveCurrentAmplitude = 0, waveState = 'standby';
function resizeWaveCanvas() { if (!waveCanvas) return; waveCanvas.width = 380; waveCanvas.height = 40; }
resizeWaveCanvas(); window.addEventListener('resize', resizeWaveCanvas);
function drawWaveform() {
  if (!waveCtx) { requestAnimationFrame(drawWaveform); return; }
  var w = waveCanvas.width, h = waveCanvas.height;
  waveCtx.clearRect(0, 0, w, h);
  waveCurrentAmplitude += (waveTargetAmplitude - waveCurrentAmplitude) * 0.08;
  var r, g, b;
  if (waveState === 'speaking')       { r=255; g=70;  b=170; wavePhase += 0.12; }
  else if (waveState === 'listening') { r=0;   g=210; b=255; wavePhase += 0.08; }
  else if (waveState === 'thinking')  { r=180; g=0;   b=255; wavePhase += 0.06; }
  else                                { r=255; g=70;  b=170; wavePhase += 0.02; }
  var bars = 48, barW = w / bars, centerY = h / 2;
  for (var i = 0; i < bars; i++) {
    var t = i / bars;
    var amp = (Math.sin(t*Math.PI*4+wavePhase)*waveCurrentAmplitude
             + Math.sin(t*Math.PI*6+wavePhase*1.3)*waveCurrentAmplitude*0.5
             + Math.sin(t*Math.PI*2+wavePhase*0.7)*waveCurrentAmplitude*0.3) * Math.sin(t*Math.PI);
    var barH = Math.max(2, Math.abs(amp));
    var alpha = Math.min(1, 0.4 + Math.abs(amp)/(h*0.4)*0.6);
    waveCtx.fillStyle = 'rgba('+r+','+g+','+b+','+alpha+')';
    waveCtx.beginPath(); waveCtx.roundRect(i*barW+barW*0.1, centerY-barH, barW*0.7, barH*2, 2); waveCtx.fill();
  }
  requestAnimationFrame(drawWaveform);
}
drawWaveform();

// ─── UI STATE ───────────────────────────────────────────────────────────────
var statusDot    = document.getElementById('status-dot');
var statusLabel  = document.getElementById('status-label');
var termDot      = document.getElementById('term-dot');
var termStatus   = document.getElementById('term-status');
var log          = document.getElementById('log');
var statusColors = { standby:'rgba(255,70,170,0.4)', listening:'rgba(0,210,255,0.9)', thinking:'rgba(180,0,255,0.9)', speaking:'rgba(255,70,170,1.0)', muted:'rgba(80,80,80,0.6)' };
var statusLabels = { standby:'STANDING BY', listening:'LISTENING', thinking:'THINKING', speaking:'TRANSMITTING', muted:'MUTED' };
var lastCypherText = '', lastUserText = '', currentMode = 'home';

function addLog(cls, text) {
  var el = document.createElement('div'); el.className = 'log-entry ' + cls; el.textContent = text;
  log.appendChild(el); log.scrollTop = log.scrollHeight;
  while (log.children.length > 20) log.removeChild(log.firstChild);
}

function applyState(data) {
  var col = statusColors[data.status] || statusColors.standby;
  var lbl = statusLabels[data.status] || 'STANDING BY';
  if (statusDot)   statusDot.style.background = col;
  if (termDot)     termDot.style.background = col;
  if (statusLabel) statusLabel.textContent = lbl;
  if (termStatus)  termStatus.textContent = lbl;
  speaking  = data.status === 'speaking';
  listening = data.status === 'listening';
  thinking  = data.status === 'thinking';
  waveState = data.status;
  if      (data.status === 'speaking')  waveTargetAmplitude = 18;
  else if (data.status === 'listening') waveTargetAmplitude = 12;
  else if (data.status === 'thinking')  waveTargetAmplitude = 8;
  else                                  waveTargetAmplitude = 3;
  if (data.user_text   && data.user_text   !== lastUserText)   { lastUserText   = data.user_text;   addLog('log-nine',   '> ' + data.user_text); }
  if (data.cypher_text && data.cypher_text !== lastCypherText) { lastCypherText = data.cypher_text; addLog('log-cypher', data.cypher_text); }
  if (data.mode && data.mode !== currentMode) setMode(data.mode);
}

// ─── SOCKET ─────────────────────────────────────────────────────────────────
var socket = io();
socket.on('connect',    function() { addLog('log-system', 'BLACKWALL LINK ESTABLISHED'); });
socket.on('disconnect', function() { addLog('log-system', 'CONNECTION LOST'); });

// ─── STATE POLLING ──────────────────────────────────────────────────────────
setInterval(function() {
  fetch('/state').then(function(r) { return r.json(); }).then(applyState).catch(function(){});
}, 200);

// ─── TIMER POLLING ──────────────────────────────────────────────────────────
var lastTimerTs = 0;
setInterval(function() {
  fetch('/timer/state').then(function(r) { return r.json(); }).then(function(data) {
    if (data.ts && data.ts > 0 && data.ts !== lastTimerTs) {
      lastTimerTs = data.ts;
      if (data.seconds > 0) { if (window.timerSet) window.timerSet(data.seconds, data.label); }
      else                  { if (window.timerReset) window.timerReset(); }
    }
  }).catch(function(){});
}, 500);

// ─── DUAL CLOCKS ────────────────────────────────────────────────────────────
function updateClocks() {
  var now = new Date();
  document.getElementById('clock-est').textContent = now.toLocaleTimeString('en-US', { timeZone:'America/New_York', hour:'2-digit', minute:'2-digit', second:'2-digit', hour12:false });
  document.getElementById('clock-th').textContent  = now.toLocaleTimeString('en-US', { timeZone:'Asia/Bangkok',      hour:'2-digit', minute:'2-digit', second:'2-digit', hour12:false });
  document.getElementById('date-th').textContent   = now.toLocaleDateString('en-US', { timeZone:'Asia/Bangkok',      year:'numeric', month:'2-digit', day:'2-digit' });
}
updateClocks(); setInterval(updateClocks, 1000);

// ─── WEATHER ICONS ──────────────────────────────────────────────────────────
function drawWeatherIcon(canvasId, desc) {
  var c = document.getElementById(canvasId); if (!c) return;
  var ctx = c.getContext('2d'), w = c.width, h = c.height; ctx.clearRect(0,0,w,h);
  var d = desc.toLowerCase(), cx = w/2, cy = h/2;
  function nL(x1,y1,x2,y2,col,lw){ctx.shadowColor=col;ctx.shadowBlur=10;ctx.strokeStyle=col;ctx.lineWidth=lw||2;ctx.lineCap='round';ctx.beginPath();ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);ctx.stroke();ctx.shadowBlur=0;}
  function nC(x,y,r,col,lw,fill){ctx.shadowColor=col;ctx.shadowBlur=12;if(fill){ctx.fillStyle=fill;ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fill();}ctx.strokeStyle=col;ctx.lineWidth=lw||2;ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.stroke();ctx.shadowBlur=0;}
  function nA(x,y,r,s,e,col,lw){ctx.shadowColor=col;ctx.shadowBlur=10;ctx.strokeStyle=col;ctx.lineWidth=lw||2;ctx.lineCap='round';ctx.beginPath();ctx.arc(x,y,r,s,e);ctx.stroke();ctx.shadowBlur=0;}
  if(d.includes('sunny')||d.includes('clear')){
    var sun='rgba(255,220,0,0.95)';nC(cx,cy,9,sun,2,'rgba(255,200,0,0.12)');
    for(var i=0;i<8;i++){var a=i*Math.PI/4;nL(cx+Math.cos(a)*12,cy+Math.sin(a)*12,cx+Math.cos(a)*17,cy+Math.sin(a)*17,sun,2);}
  }else if(d.includes('cloud')&&(d.includes('sun')||d.includes('partial')||d.includes('partly'))){
    var s2='rgba(255,200,0,0.85)';nC(15,15,6,s2,1.5,'rgba(255,200,0,0.1)');for(var i=0;i<6;i++){var a=i*Math.PI/3;nL(15+Math.cos(a)*9,15+Math.sin(a)*9,15+Math.cos(a)*12,15+Math.sin(a)*12,s2,1.2);}
    var cl='rgba(0,200,255,0.9)';nA(20,32,7,Math.PI,0,cl,2);nA(30,29,5,Math.PI,0,cl,2);nL(13,32,13,36,cl,2);nL(13,36,35,36,cl,2);nL(35,36,35,29,cl,2);
  }else if(d.includes('overcast')||d.includes('cloud')){
    var cl2='rgba(0,200,255,0.9)';nA(19,27,8,Math.PI,0,cl2,2.5);nA(30,24,6,Math.PI,0,cl2,2.5);nL(11,27,11,33,cl2,2.5);nL(11,33,36,33,cl2,2.5);nL(36,33,36,24,cl2,2.5);
  }else if(d.includes('rain')||d.includes('drizzle')||d.includes('shower')){
    var rc='rgba(255,60,180,0.85)';nA(19,22,7,Math.PI,0,rc,2);nA(29,19,5,Math.PI,0,rc,2);nL(12,22,12,27,rc,2);nL(12,27,34,27,rc,2);nL(34,27,34,19,rc,2);
    [[15,31,13,39],[23,30,21,38],[31,31,29,39]].forEach(function(l){nL(l[0],l[1],l[2],l[3],'rgba(0,200,255,0.9)',2);});
  }else if(d.includes('thunder')||d.includes('storm')){
    var sc='rgba(180,0,255,0.85)';nA(19,19,7,Math.PI,0,sc,2.5);nA(29,16,5,Math.PI,0,sc,2.5);nL(12,19,12,24,sc,2.5);nL(12,24,34,24,sc,2.5);nL(34,24,34,16,sc,2.5);
    var lt='rgba(255,220,0,0.95)';ctx.shadowColor=lt;ctx.shadowBlur=14;ctx.fillStyle=lt;ctx.beginPath();ctx.moveTo(27,26);ctx.lineTo(21,36);ctx.lineTo(24,36);ctx.lineTo(22,46);ctx.lineTo(31,33);ctx.lineTo(28,33);ctx.closePath();ctx.fill();ctx.shadowBlur=0;
  }else if(d.includes('snow')||d.includes('blizzard')){
    var sn='rgba(150,220,255,0.9)';[[cx,4,cx,48],[4,cy,48,cy],[8,8,44,44],[44,8,8,44]].forEach(function(l){nL(l[0],l[1],l[2],l[3],sn,1.5);});nC(cx,cy,4,sn,2,'rgba(150,220,255,0.2)');
  }else if(d.includes('fog')||d.includes('mist')||d.includes('haze')){
    [10,18,26,34,42].forEach(function(y,i){nL(i%2===0?6:10,y,i%2===0?46:42,y,i===2?'rgba(0,200,255,0.7)':'rgba(180,200,220,0.7)',i===2?2.5:1.5);});
  }else{
    var df='rgba(255,80,180,0.9)';nL(cx,4,48,cy,df,2);nL(48,cy,cx,48,df,2);nL(cx,48,4,cy,df,2);nL(4,cy,cx,4,df,2);nC(cx,cy,4,df,2,'rgba(255,80,180,0.15)');
  }
}

// ─── WEATHER & SUNRISE ──────────────────────────────────────────────────────
function fetchWeather(location, tempEl, descEl, iconCanvasId) {
  fetch('/weather/' + location).then(function(r){return r.text();}).then(function(data){
    var clean = data.trim().replace(/\+/g,'').replace(/\xb0/g,'').replace(/\xc2/g,'');
    var parts = clean.split(' ').filter(function(p){return p.length>0;});
    var temp = parts[0]||'--'; var desc = parts.slice(1).join(' ')||'--';
    if (temp.indexOf('<')!==-1||temp.length>8) { tempEl.textContent='--'; descEl.textContent='--'; return; }
    tempEl.textContent = temp; descEl.textContent = desc.toUpperCase().substring(0,16);
    if (iconCanvasId) drawWeatherIcon(iconCanvasId, desc);
  }).catch(function(){ tempEl.textContent='--'; descEl.textContent='--'; });
}
function fetchSunrise(location, riseEl, setEl) {
  fetch('/sunrise/' + location).then(function(r){return r.json();}).then(function(data){
    if (riseEl) riseEl.textContent = data.sunrise||'--:--';
    if (setEl)  setEl.textContent  = data.sunset ||'--:--';
  }).catch(function(){ if(riseEl)riseEl.textContent='--:--'; if(setEl)setEl.textContent='--:--'; });
}
function updateWeather() {
  fetchWeather('Marietta,PA',        document.getElementById('weather-home'), document.getElementById('weather-home-desc'), 'weather-icon-home');
  fetchWeather('Chiang+Mai,Thailand',document.getElementById('weather-thai'), document.getElementById('weather-thai-desc'), 'weather-icon-thai');
  fetchSunrise('Marietta,PA',        document.getElementById('sunrise-home'), document.getElementById('sunset-home'));
  fetchSunrise('Chiang+Mai,Thailand',document.getElementById('sunrise-thai'), document.getElementById('sunset-thai'));
}
updateWeather(); setInterval(updateWeather, 600000);

// ─── MODE SYSTEM ────────────────────────────────────────────────────────────
var sportsPollInterval = null;
function setMode(mode) {
  currentMode = mode;
  var sportsPanel = document.getElementById('sports-panel');
  var leftPanel   = document.getElementById('home-left-panel');
  var homePanel   = document.getElementById('home-right-panel');
  var ticker      = document.getElementById('scores-ticker');
  var inSports    = mode === 'sports';

  // Sports panel visibility
  if (sportsPanel) sportsPanel.classList[inSports ? 'add' : 'remove']('active');

  // Home panels — opacity + pointer events only, no hidden class conflict
  if (leftPanel)  { leftPanel.style.opacity  = inSports ? '0' : '1'; leftPanel.style.pointerEvents  = inSports ? 'none' : 'all'; leftPanel.classList.remove('hidden'); }
  if (homePanel)  { homePanel.style.opacity  = inSports ? '0' : '1'; homePanel.style.pointerEvents = inSports ? 'none' : 'all'; homePanel.classList.remove('hidden'); }

  // Ticker
  if (ticker) ticker.classList[inSports ? 'add' : 'remove']('active');

  // Sports polling
  if (inSports) {
    if (window.fetchSportsData) { setTimeout(window.fetchSportsData, 500); setTimeout(window.fetchSportsData, 2000); }
    if (!sportsPollInterval) sportsPollInterval = setInterval(function(){ if(window.fetchSportsData) window.fetchSportsData(); }, 30000);
  } else {
    if (sportsPollInterval) { clearInterval(sportsPollInterval); sportsPollInterval = null; }
  }
}

// ─── CALENDAR ───────────────────────────────────────────────────────────────
var calViewYear, calViewMonth, calSelectedDate, calAllEvents = [];
function calInit() {
  var now = new Date(); calViewYear = now.getFullYear(); calViewMonth = now.getMonth();
  calSelectedDate = now.toLocaleDateString('en-US',{timeZone:'America/New_York'});
  var dateEl = document.getElementById('cal-date');
  if (dateEl) dateEl.textContent = now.toLocaleDateString('en-US',{timeZone:'America/New_York',weekday:'short',month:'short',day:'numeric'}).toUpperCase();
  document.getElementById('cal-prev').addEventListener('click',function(){ calViewMonth--; if(calViewMonth<0){calViewMonth=11;calViewYear--;} calRenderGrid(); });
  document.getElementById('cal-next').addEventListener('click',function(){ calViewMonth++; if(calViewMonth>11){calViewMonth=0;calViewYear++;} calRenderGrid(); });
  calFetchEvents();
}
function calFetchEvents() {
  fetch('/calendar').then(function(r){return r.json();}).then(function(data){ calAllEvents=data.events||[]; calRenderGrid(); calRenderEvents(calSelectedDate); }).catch(function(){ calRenderGrid(); });
}
function calRenderGrid() {
  var months=['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'];
  var lbl = document.getElementById('cal-month-label'); if(lbl) lbl.textContent = months[calViewMonth]+' '+calViewYear;
  var grid = document.getElementById('cal-grid'); if(!grid) return;
  var firstDay = new Date(calViewYear,calViewMonth,1).getDay();
  var daysInMonth = new Date(calViewYear,calViewMonth+1,0).getDate();
  var today = new Date().toLocaleDateString('en-US',{timeZone:'America/New_York'});
  var eventDates = new Set(); calAllEvents.forEach(function(e){eventDates.add(e.date);});
  var html = ''; for(var i=0;i<firstDay;i++) html+='<div></div>';
  for(var d=1;d<=daysInMonth;d++){
    var ds=(calViewMonth+1)+'/'+d+'/'+calViewYear;
    var isT=ds===today,isS=ds===calSelectedDate,hasE=eventDates.has(ds);
    var bg=isS?'rgba(0,200,255,0.25)':isT?'rgba(255,60,180,0.2)':'transparent';
    var col=isS?'rgba(0,200,255,1)':isT?'rgba(255,200,230,1)':'rgba(255,200,230,0.5)';
    var bdr=isS?'1px solid rgba(0,200,255,0.6)':isT?'1px solid rgba(255,60,180,0.4)':'1px solid transparent';
    html+='<div onclick="calSelectDate(\''+ds+'\')" style="text-align:center;font-size:9px;cursor:pointer;border-radius:2px;padding:2px 0;background:'+bg+';color:'+col+';border:'+bdr+';position:relative;line-height:1.4;">'+d+(hasE?'<div style="width:4px;height:4px;border-radius:50%;background:rgba(255,80,180,0.9);margin:0 auto;"></div>':'')+'</div>';
  }
  grid.innerHTML = html;
}
function calSelectDate(ds) {
  calSelectedDate=ds; var parts=ds.split('/'); calViewMonth=parseInt(parts[0])-1; calViewYear=parseInt(parts[2]);
  calRenderGrid(); calRenderEvents(ds);
  var d=new Date(parseInt(parts[2]),parseInt(parts[0])-1,parseInt(parts[1]));
  var lbl=document.getElementById('cal-day-label'); var today=new Date().toLocaleDateString('en-US',{timeZone:'America/New_York'});
  if(lbl) lbl.textContent=ds===today?'TODAY':d.toLocaleDateString('en-US',{weekday:'short',month:'short',day:'numeric'}).toUpperCase();
}
function calRenderEvents(ds) {
  var el=document.getElementById('cal-body'); if(!el) return;
  var events=calAllEvents.filter(function(e){return e.date===ds;});
  events.sort(function(a,b){return a.time.localeCompare(b.time);});
  if(!events.length){el.innerHTML='<div style="font-size:10px;color:rgba(255,200,230,0.25);padding:4px 0;">No events.</div>';return;}
  el.innerHTML=events.map(function(e){
    var gi=calAllEvents.indexOf(e);
    return '<div style="display:flex;align-items:flex-start;gap:8px;padding:5px 0;border-bottom:1px solid rgba(255,60,180,0.08);">'+
      '<span style="font-size:10px;color:rgba(0,200,255,0.8);min-width:36px;font-weight:bold;flex-shrink:0;">'+e.time+'</span>'+
      '<span style="font-size:11px;color:rgba(255,200,230,0.9);line-height:1.4;flex:1;">'+e.title+'</span>'+
      '<span onclick="calDeleteEvent('+gi+')" style="font-size:10px;color:rgba(255,50,50,0.5);cursor:pointer;flex-shrink:0;">✕</span>'+
    '</div>';
  }).join('');
}
function calDeleteEvent(idx) {
  fetch('/calendar/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({index:idx})})
    .then(function(r){return r.json();}).then(function(){calFetchEvents();}).catch(function(e){console.error('Delete failed:',e);});
}
window.calDeleteEvent = calDeleteEvent; window.calSelectDate = calSelectDate;
calInit(); setInterval(calFetchEvents, 60000);

// ─── TIMER ──────────────────────────────────────────────────────────────────
var timerInterval=null,timerTotal=0,timerRemaining=0,timerRunning=false;
function timerFormat(s){var m=Math.floor(s/60),sec=s%60;return(m<10?'0':'')+m+':'+(sec<10?'0':'')+sec;}
function timerSet(seconds,label){
  timerClear(); timerTotal=seconds; timerRemaining=seconds; timerRunning=true;
  var dEl=document.getElementById('timer-display'),lEl=document.getElementById('timer-label'),sEl=document.getElementById('timer-status'),bEl=document.getElementById('timer-bar');
  if(lEl)lEl.textContent=label||'TIMER RUNNING';
  if(sEl){sEl.textContent='RUNNING';sEl.style.color='rgba(50,255,100,0.8)';}
  timerInterval=setInterval(function(){
    if(!timerRunning)return; timerRemaining--;
    var pct=((timerTotal-timerRemaining)/timerTotal)*100;
    if(dEl)dEl.textContent=timerFormat(timerRemaining); if(bEl)bEl.style.width=pct+'%';
    if(timerRemaining<=60){if(dEl)dEl.style.color='rgba(255,50,50,0.95)';if(bEl)bEl.style.background='rgba(255,50,50,0.9)';}
    if(timerRemaining<=0)timerDone();
  },1000);
  if(dEl){dEl.textContent=timerFormat(timerRemaining);dEl.style.color='rgba(255,200,230,0.95)';}
  if(bEl){bEl.style.width='0%';bEl.style.background='rgba(255,80,180,0.8)';}
}
function timerDone(){
  timerClear();
  var dEl=document.getElementById('timer-display'),lEl=document.getElementById('timer-label'),sEl=document.getElementById('timer-status'),bEl=document.getElementById('timer-bar');
  if(dEl){dEl.textContent='00:00';dEl.style.color='rgba(255,50,50,0.9)';}
  if(lEl)lEl.textContent='TIMER COMPLETE';
  if(sEl){sEl.textContent='DONE';sEl.style.color='rgba(255,50,50,0.9)';}
  if(bEl){bEl.style.width='100%';bEl.style.background='rgba(255,50,50,0.8)';}
  try{
    var actx=new(window.AudioContext||window.webkitAudioContext)();
    [{freq:880,start:0.0,dur:0.12},{freq:880,start:0.18,dur:0.12},{freq:1320,start:0.36,dur:0.3}].forEach(function(b){
      var osc=actx.createOscillator(),gain=actx.createGain();osc.connect(gain);gain.connect(actx.destination);osc.type='square';
      osc.frequency.setValueAtTime(b.freq,actx.currentTime+b.start);gain.gain.setValueAtTime(0,actx.currentTime+b.start);
      gain.gain.linearRampToValueAtTime(0.18,actx.currentTime+b.start+0.01);gain.gain.exponentialRampToValueAtTime(0.001,actx.currentTime+b.start+b.dur);
      osc.start(actx.currentTime+b.start);osc.stop(actx.currentTime+b.start+b.dur+0.05);
    });
  }catch(e){}
  var fl=0,fi=setInterval(function(){if(dEl)dEl.style.opacity=fl%2===0?'0.2':'1';fl++;if(fl>8){clearInterval(fi);if(dEl)dEl.style.opacity='1';}},300);
}
function timerClear(){if(timerInterval){clearInterval(timerInterval);timerInterval=null;}timerRunning=false;}
function timerPause(){
  if(!timerInterval)return; timerRunning=!timerRunning;
  var sEl=document.getElementById('timer-status');
  if(sEl){sEl.textContent=timerRunning?'RUNNING':'PAUSED';sEl.style.color=timerRunning?'rgba(50,255,100,0.8)':'rgba(255,180,50,0.8)';}
}
function timerReset(){
  timerClear();
  var dEl=document.getElementById('timer-display'),lEl=document.getElementById('timer-label'),sEl=document.getElementById('timer-status'),bEl=document.getElementById('timer-bar');
  if(dEl){dEl.textContent='00:00';dEl.style.color='rgba(255,200,230,0.95)';}
  if(lEl)lEl.textContent='SET A TIMER VIA VOICE';
  if(sEl){sEl.textContent='STANDBY';sEl.style.color='rgba(255,80,180,0.5)';}
  if(bEl){bEl.style.width='0%';bEl.style.background='rgba(255,80,180,0.8)';}
  timerTotal=0; timerRemaining=0;
}
function sendVoiceCmd(cmd){console.log('Voice cmd:',cmd);}
window.timerSet=timerSet; window.timerReset=timerReset; window.timerPause=timerPause; window.sendVoiceCmd=sendVoiceCmd;

// ════════════════════════════════════════════════════════════════════════════
// ─── LEFT PANEL WIDGETS ─────────────────────────────────────────────────────
// ════════════════════════════════════════════════════════════════════════════

// ── Helper: draw a donut ring ──────────────────────────────────────────────
function drawDonut(canvasId, pct, color, trackColor) {
  var c = document.getElementById(canvasId); if(!c) return;
  var ctx = c.getContext('2d');
  var cx = c.width/2, cy = c.height/2, r = cx - 6;
  ctx.clearRect(0,0,c.width,c.height);
  // Track
  ctx.beginPath(); ctx.arc(cx,cy,r,0,Math.PI*2);
  ctx.strokeStyle = trackColor||'rgba(255,60,180,0.1)'; ctx.lineWidth=7; ctx.stroke();
  // Fill
  var startAngle = -Math.PI/2;
  var endAngle   = startAngle + (Math.PI*2*(pct/100));
  ctx.beginPath(); ctx.arc(cx,cy,r,startAngle,endAngle);
  ctx.strokeStyle = color; ctx.lineWidth=7; ctx.lineCap='round'; ctx.stroke();
}

// ── Helper: temp color ─────────────────────────────────────────────────────
function tempColor(t) {
  if (t === null || t === undefined) return { ring:'rgba(255,60,180,0.3)', text:'rgba(255,200,230,0.3)', label:'N/A', status:'NO DATA' };
  if (t >= 80) return { ring:'rgba(255,50,50,0.9)',   text:'rgba(255,50,50,0.95)',  label:t+'°C', status:'● HOT'  };
  if (t >= 65) return { ring:'rgba(255,160,40,0.85)', text:'rgba(255,160,40,0.95)', label:t+'°C', status:'● WARM' };
  return           { ring:'rgba(50,220,120,0.85)',   text:'rgba(50,220,120,0.95)', label:t+'°C', status:'● COOL' };
}

// ── Helper: donut % for temp (0-100°C mapped) ─────────────────────────────
function tempPct(t) { return t ? Math.min(100, Math.round((t/100)*100)) : 0; }

// ─── SYS MONITOR ────────────────────────────────────────────────────────────
var _lastSysInfo = {};
function updateSysMonitor() {
  fetch('/sysinfo').then(function(r){return r.json();}).then(function(d){
    _lastSysInfo = d;
    var barCol = function(v){ return v>80?'rgba(255,50,50,0.9)':v>50?'rgba(255,160,40,0.85)':'rgba(255,80,180,0.75)'; };

    // CPU donut
    drawDonut('lp-donut-cpu', d.cpu_percent||0, barCol(d.cpu_percent||0));
    var cpuValEl = document.getElementById('lp-donut-cpu-val'); if(cpuValEl) cpuValEl.textContent=(d.cpu_percent||0)+'%';
    var cpuSubEl = document.getElementById('lp-cpu-sub'); if(cpuSubEl) cpuSubEl.textContent=(d.cpu_name||'CPU').substring(0,24);

    // RAM donut
    drawDonut('lp-donut-ram', d.ram_percent||0, barCol(d.ram_percent||0));
    var ramValEl = document.getElementById('lp-donut-ram-val'); if(ramValEl) ramValEl.textContent=(d.ram_percent||0)+'%';
    var ramSubEl = document.getElementById('lp-ram-sub'); if(ramSubEl) ramSubEl.textContent=(d.ram_used_gb||'--')+' / '+(d.ram_total_gb||'--')+' GB';

    // GPU donut
    drawDonut('lp-donut-gpu', d.gpu_percent||0, barCol(d.gpu_percent||0));
    var gpuValEl = document.getElementById('lp-donut-gpu-val'); if(gpuValEl) gpuValEl.textContent=(d.gpu_percent||0)+'%';
    var gpuSubEl = document.getElementById('lp-gpu-sub'); if(gpuSubEl) gpuSubEl.textContent=(d.gpu_name||'GPU').substring(0,20);

    // Disk I/O donut (read as % of 500 MB/s cap)
    var diskPct = Math.min(100, Math.round(((d.disk_read_mbs||0)+(d.disk_write_mbs||0))/5));
    drawDonut('lp-donut-disk', diskPct, 'rgba(0,200,255,0.75)');
    var diskREl = document.getElementById('lp-disk-read');  if(diskREl) diskREl.textContent='R '+(d.disk_read_mbs||0)+' MB/s';
    var diskWEl = document.getElementById('lp-disk-write'); if(diskWEl) diskWEl.textContent='W '+(d.disk_write_mbs||0)+' MB/s';

    // Uptime
    var upEl = document.getElementById('lp-uptime'); if(upEl) upEl.textContent = d.uptime||'--';

    // Spike alert
    var alertEl = document.getElementById('lp-spike-alert');
    if (alertEl) {
      var cpu=d.cpu_percent||0, ram=d.ram_percent||0, gpu=d.gpu_percent||0;
      if (cpu>85||ram>85||gpu>85) {
        var who=cpu>85?'CPU':ram>85?'RAM':'GPU';
        alertEl.textContent='⚠ '+who+' SPIKE '+Math.max(cpu,ram,gpu)+'%';
        alertEl.style.display='block';
      } else { alertEl.style.display='none'; }
    }

    // Update temps widget too since we have the data
    updateTempsFromCache(d);
  }).catch(function(){});
}
updateSysMonitor(); setInterval(updateSysMonitor, 2000);

// ─── TEMPS ──────────────────────────────────────────────────────────────────
function updateTempsFromCache(d) {
  // CPU temp
  var cpuT = d.cpu_temp;
  var cpuCol = tempColor(cpuT);
  drawDonut('lp-temp-cpu', tempPct(cpuT), cpuCol.ring);
  var el = document.getElementById('lp-temp-cpu-val');   if(el) { el.textContent=cpuCol.label; el.style.color=cpuCol.text; }
  el = document.getElementById('lp-temp-cpu-status');    if(el) { el.textContent=cpuCol.status; el.style.color=cpuCol.text; }

  // GPU temp
  var gpuT = d.gpu_temp;
  var gpuCol = tempColor(gpuT||0);
  drawDonut('lp-temp-gpu', tempPct(gpuT), gpuCol.ring);
  el = document.getElementById('lp-temp-gpu-val');   if(el) { el.textContent=gpuCol.label; el.style.color=gpuCol.text; }
  el = document.getElementById('lp-temp-gpu-status');if(el) { el.textContent=gpuCol.status; el.style.color=gpuCol.text; }

  // GPU fan
  var fan = d.gpu_fan||0;
  var fanPct = Math.min(100, fan); // fan is already 0-100%
  drawDonut('lp-temp-fan', fanPct, 'rgba(0,200,255,0.75)');
  el = document.getElementById('lp-temp-fan-val');   if(el) { el.textContent=fan+'%'; el.style.color='rgba(0,200,255,0.9)'; }
  el = document.getElementById('lp-temp-fan-status');if(el) { el.textContent='GPU FAN'; el.style.color='rgba(0,200,255,0.5)'; }

  // VRAM temp — nvidia-smi doesn't always expose this, use vram usage % instead
  var vramPct = d.gpu_vram_total>0 ? Math.round((d.gpu_vram_used/d.gpu_vram_total)*100) : 0;
  var vramCol = vramPct>85?'rgba(255,50,50,0.9)':vramPct>60?'rgba(255,160,40,0.85)':'rgba(255,80,180,0.75)';
  drawDonut('lp-temp-vram', vramPct, vramCol);
  el = document.getElementById('lp-temp-vram-val');   if(el) { el.textContent=(d.gpu_vram_used||'--')+' GB'; el.style.color=vramPct>85?'rgba(255,50,50,0.9)':vramPct>60?'rgba(255,160,40,0.9)':'rgba(255,200,230,0.9)'; }
  el = document.getElementById('lp-temp-vram-status');if(el) { el.textContent='VRAM'; el.style.color='rgba(255,200,230,0.4)'; }
}

// ─── NETWORK ────────────────────────────────────────────────────────────────
function updateNetwork() {
  fetch('/network').then(function(r){return r.json();}).then(function(d){
    var upEl  = document.getElementById('lp-net-up');     if(upEl)  upEl.textContent  = (d.upload||0).toFixed(1);
    var dnEl  = document.getElementById('lp-net-dn');     if(dnEl)  dnEl.textContent  = (d.download||0).toFixed(1);
    var pgEl  = document.getElementById('lp-net-ping');
    if (pgEl) {
      if (d.ping!==null&&d.ping!==undefined) { pgEl.textContent=d.ping+'ms'; pgEl.style.color=d.ping<30?'rgba(50,255,100,0.9)':d.ping<80?'rgba(255,160,40,0.8)':'rgba(255,50,50,0.9)'; }
      else pgEl.textContent='—';
    }
    var stEl  = document.getElementById('lp-net-status'); if(stEl)  { stEl.textContent=d.connected?'● ONLINE':'● OFFLINE'; stEl.style.color=d.connected?'rgba(50,255,100,0.8)':'rgba(255,50,50,0.8)'; }
    var supEl = document.getElementById('lp-net-sup');    if(supEl) supEl.textContent = '↑ '+(d.session_up||'0 MB');
    var sdnEl = document.getElementById('lp-net-sdn');    if(sdnEl) sdnEl.textContent = '↓ '+(d.session_down||'0 MB');
  }).catch(function(){});
}
updateNetwork(); setInterval(updateNetwork, 3000);

// ─── STORAGE ────────────────────────────────────────────────────────────────
function updateStorage() {
  fetch('/sysinfo').then(function(r){return r.json();}).then(function(d){
    var el = document.getElementById('lp-storage-list'); if(!el) return;
    var disks = d.disks||[];
    if (!disks.length) { el.innerHTML='<div style="font-size:10px;color:rgba(255,200,230,0.2);">No disk data</div>'; return; }
    el.innerHTML = disks.map(function(disk){
      var col = disk.percent>85?'rgba(255,50,50,0.9)':disk.percent>60?'rgba(255,160,40,0.8)':'rgba(255,80,180,0.7)';
      return '<div style="margin-bottom:8px;">'+
        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:3px;">'+
          '<span style="font-size:9px;color:rgba(255,80,180,0.7);letter-spacing:0.1em;">'+disk.drive+':</span>'+
          '<span style="font-size:9px;color:rgba(255,200,230,0.5);">'+disk.used_gb+' / '+disk.total_gb+' GB</span>'+
          '<span style="font-size:10px;font-weight:bold;color:'+col+';">'+disk.percent+'%</span>'+
        '</div>'+
        '<div style="height:4px;background:rgba(255,60,180,0.1);border-radius:2px;overflow:hidden;">'+
          '<div style="height:100%;width:'+disk.percent+'%;background:'+col+';border-radius:2px;transition:width 0.5s ease;"></div>'+
        '</div>'+
      '</div>';
    }).join('');
  }).catch(function(){});
}
updateStorage(); setInterval(updateStorage, 5000);

// ─── PROCESSES ──────────────────────────────────────────────────────────────
function updateProcesses() {
  fetch('/processes').then(function(r){return r.json();}).then(function(d){
    var el = document.getElementById('lp-processes'); if(!el||!d.processes) return;
    if(!d.processes.length){ el.innerHTML='<div style="font-size:10px;color:rgba(255,200,230,0.2);">No active processes</div>'; return; }
    el.innerHTML = d.processes.map(function(p){
      var col = p.cpu>50?'rgba(255,50,50,0.9)':p.cpu>20?'rgba(255,160,40,0.8)':'rgba(255,200,230,0.75)';
      var mem = p.mem_mb>=1024?(p.mem_mb/1024).toFixed(1)+' GB':p.mem_mb+' MB';
      return '<div style="display:flex;justify-content:space-between;align-items:center;padding:4px 0;border-bottom:1px solid rgba(255,60,180,0.06);">'+
        '<span style="font-size:10px;color:rgba(255,200,230,0.8);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:120px;">'+p.name+'</span>'+
        '<div style="display:flex;gap:8px;flex-shrink:0;">'+
          '<span style="font-size:10px;font-weight:bold;color:'+col+';">'+p.cpu+'%</span>'+
          '<span style="font-size:10px;color:rgba(255,200,230,0.35);min-width:52px;text-align:right;">'+mem+'</span>'+
        '</div>'+
      '</div>';
    }).join('');
  }).catch(function(){});
}
updateProcesses(); setInterval(updateProcesses, 4000);

// ─── SESSION LOG ────────────────────────────────────────────────────────────
function updateSessionLog() {
  fetch('/session-log').then(function(r){return r.json();}).then(function(d){
    var el = document.getElementById('lp-session-log'); if(!el||!d.log) return;
    if(!d.log.length){ el.innerHTML='<div style="font-size:10px;color:rgba(255,200,230,0.2);">No activity yet.</div>'; return; }
    el.innerHTML = d.log.slice(0,6).map(function(entry){
      return '<div style="display:flex;gap:8px;padding:3px 0;border-bottom:1px solid rgba(255,60,180,0.06);">'+
        '<span style="font-size:9px;color:rgba(255,80,180,0.5);flex-shrink:0;min-width:44px;">'+entry.time+'</span>'+
        '<span style="font-size:10px;color:rgba(255,200,230,0.65);line-height:1.4;">'+entry.text+'</span>'+
      '</div>';
    }).join('');
  }).catch(function(){});
}
updateSessionLog(); setInterval(updateSessionLog, 5000);

// ─── DAILY GOALS ────────────────────────────────────────────────────────────
function goalsRender() {
  fetch('/goals').then(function(r){return r.json();}).then(function(d){
    var el=document.getElementById('lp-goals-list'); var cntEl=document.getElementById('lp-goals-count'); if(!el) return;
    var goals=d.goals||[]; var done=goals.filter(function(g){return g.done;}).length;
    if(cntEl) cntEl.textContent=done+'/'+goals.length;
    if(!goals.length){ el.innerHTML='<div style="font-size:10px;color:rgba(255,200,230,0.2);padding:3px 0;">Say "add a goal: ..."</div>'; return; }
    el.innerHTML=goals.map(function(g,i){
      var col=g.done?'rgba(50,255,100,0.5)':'rgba(255,200,230,0.85)';
      var deco=g.done?'line-through':'none';
      var dotBg=g.done?'rgba(50,255,100,0.15)':'transparent';
      var dotBdr=g.done?'rgba(50,255,100,0.8)':'rgba(255,60,180,0.4)';
      return '<div style="display:flex;align-items:center;gap:7px;padding:5px 0;border-bottom:1px solid rgba(255,60,180,0.08);">'+
        '<div onclick="goalsToggle('+i+')" style="width:12px;height:12px;border-radius:2px;border:1px solid '+dotBdr+';background:'+dotBg+';flex-shrink:0;cursor:pointer;display:flex;align-items:center;justify-content:center;">'+
          (g.done?'<div style="width:6px;height:6px;background:rgba(50,255,100,0.8);border-radius:1px;"></div>':'')+
        '</div>'+
        '<span style="font-size:10px;color:'+col+';text-decoration:'+deco+';line-height:1.4;flex:1;">'+g.text+'</span>'+
      '</div>';
    }).join('');
  }).catch(function(){});
}
function goalsToggle(idx) {
  fetch('/goals/toggle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({index:idx})})
    .then(function(){goalsRender();}).catch(function(){});
}
window.goalsToggle=goalsToggle;
goalsRender(); setInterval(goalsRender, 30000);

// ─── COUNTDOWN ──────────────────────────────────────────────────────────────
function countdownRender() {
  fetch('/countdown').then(function(r){return r.json();}).then(function(d){
    var el=document.getElementById('lp-countdown-list'); if(!el) return;
    var cds=d.countdowns||[];
    if(!cds.length){ el.innerHTML='<div style="font-size:10px;color:rgba(255,200,230,0.2);padding:4px 0;">Say "count down to [event] on [date]"</div>'; return; }
    var now=new Date();
    el.innerHTML=cds.map(function(cd,i){
      var target=new Date(cd.date);
      var diff=Math.ceil((target-now)/(1000*60*60*24));
      var col=diff<=3?'rgba(255,50,50,0.9)':diff<=7?'rgba(255,160,40,0.9)':'rgba(0,200,255,0.9)';
      var label=diff<0?'PAST':diff===0?'TODAY':diff+'D';
      return '<div style="display:flex;align-items:center;justify-content:space-between;padding:6px 10px;border-right:1px solid rgba(255,60,180,0.1);flex:1;">'+
        '<span style="font-size:10px;color:rgba(255,200,230,0.7);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:80px;">'+cd.label+'</span>'+
        '<div style="display:flex;align-items:center;gap:6px;flex-shrink:0;">'+
          '<span style="font-size:16px;font-weight:bold;color:'+col+';">'+label+'</span>'+
          '<span onclick="countdownDelete('+i+')" style="font-size:10px;color:rgba(255,50,50,0.4);cursor:pointer;">✕</span>'+
        '</div>'+
      '</div>';
    }).join('');
    // Wrap in flex row
    el.style.display='flex'; el.style.flexWrap='wrap';
  }).catch(function(){});
}
function countdownDelete(idx) {
  fetch('/countdown/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({index:idx})})
    .then(function(){countdownRender();}).catch(function(){});
}
window.countdownDelete=countdownDelete;
countdownRender(); setInterval(countdownRender, 60000);

// ─── PERIPHERALS ────────────────────────────────────────────────────────────
function drawBatteryRing(canvasId, pct, charging, wired) {
  var c = document.getElementById(canvasId); if(!c) return;
  var ctx = c.getContext('2d'), cx=c.width/2, cy=c.height/2, r=cx-5;
  ctx.clearRect(0,0,c.width,c.height);
  if (wired) {
    // Draw plug icon
    ctx.strokeStyle='rgba(0,200,255,0.6)'; ctx.lineWidth=2; ctx.lineCap='round';
    ctx.beginPath(); ctx.arc(cx,cy,r,0,Math.PI*2); ctx.stroke();
    ctx.fillStyle='rgba(0,200,255,0.7)'; ctx.font='bold 14px Courier New'; ctx.textAlign='center'; ctx.textBaseline='middle';
    ctx.fillText('⚡', cx, cy);
    return;
  }
  var col = pct===null?'rgba(255,60,180,0.2)':pct<=20?'rgba(255,50,50,0.9)':pct<=50?'rgba(255,160,40,0.85)':'rgba(50,220,120,0.85)';
  // Track
  ctx.beginPath(); ctx.arc(cx,cy,r,0,Math.PI*2); ctx.strokeStyle='rgba(255,60,180,0.1)'; ctx.lineWidth=6; ctx.stroke();
  // Fill
  if (pct!==null) {
    ctx.beginPath(); ctx.arc(cx,cy,r,-Math.PI/2,-Math.PI/2+(Math.PI*2*(pct/100)));
    ctx.strokeStyle=col; ctx.lineWidth=6; ctx.lineCap='round'; ctx.stroke();
  }
  // Charging bolt
  if (charging) {
    ctx.fillStyle='rgba(255,220,0,0.9)'; ctx.font='10px Courier New'; ctx.textAlign='center'; ctx.textBaseline='middle';
    ctx.fillText('⚡',cx,cy);
  }
}

function updatePeripherals() {
  fetch('/peripherals').then(function(r){return r.json();}).then(function(d){
    var devices = d.devices||[];
    devices.forEach(function(dev){
      var ring = document.getElementById('lp-peri-ring-'+dev.id);
      var val  = document.getElementById('lp-peri-val-'+dev.id);
      var stat = document.getElementById('lp-peri-status-'+dev.id);
      if (!ring) return;
      drawBatteryRing('lp-peri-ring-'+dev.id, dev.battery, dev.charging, dev.wired);
      if (dev.wired) {
        if(val)  { val.textContent='WIRED'; val.style.color='rgba(0,200,255,0.8)'; }
        if(stat) { stat.textContent='CONNECTED'; stat.style.color='rgba(0,200,255,0.5)'; }
      } else if (!dev.connected) {
        if(val)  { val.textContent='OFF'; val.style.color='rgba(255,200,230,0.3)'; }
        if(stat) { stat.textContent='OFFLINE'; stat.style.color='rgba(255,200,230,0.25)'; }
      } else {
        var pct = dev.battery;
        var col = pct===null?'rgba(255,200,230,0.3)':pct<=20?'rgba(255,50,50,0.9)':pct<=50?'rgba(255,160,40,0.9)':'rgba(50,220,120,0.9)';
        if(val)  { val.textContent=pct!==null?pct+'%':'--'; val.style.color=col; }
        if(stat) {
          stat.textContent=dev.charging?'● CHARGING':pct<=20?'● LOW':pct<=50?'● MED':'● GOOD';
          stat.style.color=dev.charging?'rgba(255,220,0,0.8)':col;
        }
      }
    });
  }).catch(function(){});
}
updatePeripherals(); setInterval(updatePeripherals, 30000);

// ─── FPS ────────────────────────────────────────────────────────────────────
function updateFPS() {
  fetch('/fps').then(function(r){return r.json();}).then(function(d){
    var fpsEl = document.getElementById('lp-fps-val');
    var appEl = document.getElementById('lp-fps-app');
    var barEl = document.getElementById('lp-fps-bar');
    if (!fpsEl) return;
    if (d.fps > 0) {
      fpsEl.textContent = d.fps;
      fpsEl.style.color = d.fps>=120?'rgba(50,220,120,0.9)':d.fps>=60?'rgba(255,200,230,0.95)':'rgba(255,160,40,0.9)';
      if(appEl) appEl.textContent = d.app ? d.app.replace('.exe','').toUpperCase().substring(0,20) : '';
      if(barEl) {
        var pct = Math.min(100, Math.round((d.fps/165)*100));
        barEl.style.width=pct+'%';
        barEl.style.background=d.fps>=120?'rgba(50,220,120,0.7)':d.fps>=60?'rgba(255,80,180,0.7)':'rgba(255,160,40,0.7)';
      }
    } else {
      fpsEl.textContent = '--';
      fpsEl.style.color = 'rgba(255,200,230,0.2)';
      if(appEl) appEl.textContent = d.source==='hint'?'INSTALL RIVATUNER FOR FPS':'NO GAME DETECTED';
      if(barEl) barEl.style.width='0%';
    }
  }).catch(function(){});
}
updateFPS(); setInterval(updateFPS, 1000);
