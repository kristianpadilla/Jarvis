// ─── CYPHER-VRM.JS ───
// Three.js scene, VRM loader, animations, particles, scanlines, grid

// ─── RENDERER ───
var canvas = document.getElementById('three-canvas');
var renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true });
renderer.setPixelRatio(window.devicePixelRatio);
renderer.outputEncoding = THREE.sRGBEncoding;

var scene = new THREE.Scene();
var camera = new THREE.PerspectiveCamera(30, window.innerWidth / window.innerHeight, 0.1, 100);
camera.position.set(0, 0.5, 5.0);

function resize() {
  renderer.setSize(window.innerWidth, window.innerHeight);
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
}
resize();
window.addEventListener('resize', resize);

// ─── LIGHTING ───
scene.add(new THREE.AmbientLight(0xffffff, 0.6));
var frontLight = new THREE.DirectionalLight(0xff88cc, 1.2);
frontLight.position.set(0, 2, 3); scene.add(frontLight);
var fillLight = new THREE.DirectionalLight(0x88ccff, 0.5);
fillLight.position.set(-2, 1, 1); scene.add(fillLight);
var rimLight = new THREE.DirectionalLight(0xff44aa, 0.8);
rimLight.position.set(0, 3, -2); scene.add(rimLight);

// ─── RAIN PARTICLES ───
var rainGeo = new THREE.BufferGeometry();
var rainPos = new Float32Array(300 * 3);
var rainVel = new Float32Array(300);
for (var i = 0; i < 300; i++) {
  rainPos[i*3]   = (Math.random()-0.5)*12;
  rainPos[i*3+1] = (Math.random()-0.5)*8;
  rainPos[i*3+2] = -2+Math.random();
  rainVel[i] = Math.random()*0.015+0.005;
}
rainGeo.setAttribute('position', new THREE.BufferAttribute(rainPos, 3));
var rainMat = new THREE.PointsMaterial({ size:0.015, color:new THREE.Color(0,0.5,1), transparent:true, opacity:0.15 });
scene.add(new THREE.Points(rainGeo, rainMat));

// ─── FLOAT PARTICLES ───
var floatGeo = new THREE.BufferGeometry();
var floatPos = new Float32Array(80*3);
var floatVel = new Float32Array(80*3);
for (var i = 0; i < 80; i++) {
  floatPos[i*3]   = (Math.random()-0.5)*3;
  floatPos[i*3+1] = Math.random()*3;
  floatPos[i*3+2] = (Math.random()-0.5)*1.5;
  floatVel[i*3]   = (Math.random()-0.5)*0.002;
  floatVel[i*3+1] = Math.random()*0.003+0.001;
  floatVel[i*3+2] = (Math.random()-0.5)*0.001;
}
floatGeo.setAttribute('position', new THREE.BufferAttribute(floatPos, 3));
var floatMat = new THREE.PointsMaterial({ size:0.025, color:new THREE.Color(1,0.3,0.7), transparent:true, opacity:0.4 });
scene.add(new THREE.Points(floatGeo, floatMat));

// ─── ANIMATED GRID ───
var gridLines = [];
var gridSize = 10; var gridDivisions = 20;
var animatedGrid = new THREE.Group();
scene.add(animatedGrid);
var gridStep = gridSize/gridDivisions;
for (var gi = 0; gi <= gridDivisions; gi++) {
  var pos = -gridSize/2 + gi*gridStep;
  var geoX = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(-gridSize/2,0,pos),new THREE.Vector3(gridSize/2,0,pos)]);
  var matX = new THREE.LineBasicMaterial({color:0x330022,transparent:true,opacity:0.6});
  var lineX = new THREE.Line(geoX,matX); lineX.position.y=-1.0; lineX.userData.offset=gi*0.3;
  animatedGrid.add(lineX); gridLines.push(lineX);
  var geoZ = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(pos,0,-gridSize/2),new THREE.Vector3(pos,0,gridSize/2)]);
  var matZ = new THREE.LineBasicMaterial({color:0x330022,transparent:true,opacity:0.6});
  var lineZ = new THREE.Line(geoZ,matZ); lineZ.position.y=-1.0; lineZ.userData.offset=gi*0.3+0.15;
  animatedGrid.add(lineZ); gridLines.push(lineZ);
}
function animateGrid(t) {
  for (var gl=0;gl<gridLines.length;gl++) {
    var line=gridLines[gl];
    line.material.opacity=0.3+Math.sin(t*0.8+line.userData.offset)*0.25;
    var r=0.2+Math.sin(t*0.5+line.userData.offset)*0.1;
    var b=0.1+Math.sin(t*0.4+line.userData.offset+1.5)*0.08;
    line.material.color.setRGB(r,0,b);
  }
}

// ─── VRM STATE (shared globals) ───
var currentVrm = null;
var speaking   = false;
var listening  = false;
var thinking   = false;
var cypherTargetX = 0;

// ─── HAND STATE MACHINE ───
var handState='open', handStateTime=0, handCurl=0;
var OPEN_MIN=4.0, OPEN_MAX=9.0, CLOSE_DUR=1.2, CLOSED_MIN=1.5, CLOSED_MAX=3.5, OPEN_ANIM=1.0;
var nextStateChange=OPEN_MIN+Math.random()*(OPEN_MAX-OPEN_MIN);
function easeInOut(t){return t<0.5?2*t*t:-1+(4-2*t)*t;}
function updateHandState(delta) {
  handStateTime+=delta;
  if(handState==='open'){handCurl=0;if(handStateTime>=nextStateChange){handState='closing';handStateTime=0;}}
  else if(handState==='closing'){var t=Math.min(handStateTime/CLOSE_DUR,1.0);handCurl=easeInOut(t);if(t>=1.0){handState='closed';handStateTime=0;nextStateChange=CLOSED_MIN+Math.random()*(CLOSED_MAX-CLOSED_MIN);}}
  else if(handState==='closed'){handCurl=1.0;if(handStateTime>=nextStateChange){handState='opening';handStateTime=0;}}
  else if(handState==='opening'){var t=Math.min(handStateTime/OPEN_ANIM,1.0);handCurl=easeInOut(1.0-t);if(t>=1.0){handState='open';handStateTime=0;nextStateChange=OPEN_MIN+Math.random()*(OPEN_MAX-OPEN_MIN);}}
}
function applyFingers(h,curl) {
  var fg=[['leftIndexProximal','leftIndexIntermediate','leftIndexDistal'],['leftMiddleProximal','leftMiddleIntermediate','leftMiddleDistal'],['leftRingProximal','leftRingIntermediate','leftRingDistal'],['leftLittleProximal','leftLittleIntermediate','leftLittleDistal'],['rightIndexProximal','rightIndexIntermediate','rightIndexDistal'],['rightMiddleProximal','rightMiddleIntermediate','rightMiddleDistal'],['rightRingProximal','rightRingIntermediate','rightRingDistal'],['rightLittleProximal','rightLittleIntermediate','rightLittleDistal']];
  var oC=[0.2,0.15,0.1],cC=[1.5,1.7,1.3];
  for(var gi=0;gi<fg.length;gi++){var group=fg[gi];var fd=gi*0.04;var ac=Math.max(0,Math.min(1,curl-fd));for(var si=0;si<3;si++){var bone=h.getBoneNode(group[si]);if(bone){var micro=Math.sin(time*0.8+gi*0.6+si*0.3)*0.015*(1.0-curl);var cv=oC[si]+(cC[si]-oC[si])*ac+micro;if(group[0].indexOf('left')!==-1){bone.rotation.z=cv;bone.rotation.x=0;}else{bone.rotation.z=-cv;bone.rotation.x=0;}}}}
  var tg=[['leftThumbProximal','leftThumbIntermediate','leftThumbDistal',1],['rightThumbProximal','rightThumbIntermediate','rightThumbDistal',-1]];
  var to=[0.3,0.2,0.15],tc=[0.8,0.7,0.6];
  for(var ti=0;ti<tg.length;ti++){for(var si=0;si<3;si++){var bone=h.getBoneNode(tg[ti][si]);if(bone){var cv=to[si]+(tc[si]-to[si])*curl;bone.rotation.z=0;bone.rotation.x=-cv;}}}
}

// ─── BODY GLITCH ───
var bodyGlitch={active:false,timer:0,nextTrigger:6+Math.random()*10,phase:0,phaseTime:0,snapX:0,snapY:0,armSnap:0,headSnap:0};
function updateBodyGlitch(delta) {
  bodyGlitch.timer+=delta; bodyGlitch.phaseTime+=delta;
  if(bodyGlitch.phase===0&&bodyGlitch.timer>bodyGlitch.nextTrigger){bodyGlitch.phase=1;bodyGlitch.phaseTime=0;bodyGlitch.timer=0;bodyGlitch.nextTrigger=5+Math.random()*12;bodyGlitch.snapX=(Math.random()-0.5)*0.3;bodyGlitch.snapY=(Math.random()-0.5)*0.2;bodyGlitch.armSnap=(Math.random()-0.5)*0.8;bodyGlitch.headSnap=(Math.random()-0.5)*0.6;}
  if(bodyGlitch.phase===1){bodyGlitch.active=true;if(bodyGlitch.phaseTime>0.06+Math.random()*0.08){bodyGlitch.snapX=(Math.random()-0.5)*0.25;bodyGlitch.snapY=(Math.random()-0.5)*0.15;bodyGlitch.armSnap=(Math.random()-0.5)*0.6;bodyGlitch.headSnap=(Math.random()-0.5)*0.5;bodyGlitch.phaseTime=0;}if(bodyGlitch.timer>0.18){bodyGlitch.phase=2;bodyGlitch.phaseTime=0;bodyGlitch.active=false;}}
  if(bodyGlitch.phase===2){if(bodyGlitch.phaseTime<0.05){bodyGlitch.active=true;bodyGlitch.snapX=(Math.random()-0.5)*0.1;bodyGlitch.snapY=(Math.random()-0.5)*0.08;bodyGlitch.armSnap=(Math.random()-0.5)*0.2;bodyGlitch.headSnap=(Math.random()-0.5)*0.15;}else{bodyGlitch.active=false;}if(bodyGlitch.phaseTime>0.25){bodyGlitch.phase=0;bodyGlitch.phaseTime=0;bodyGlitch.active=false;}}
}

function lerp(a,b,t){return a+(b-a)*t;}

// ─── VRM LOADER ───
var gltfLoader = new THREE.GLTFLoader();
gltfLoader.load('/model',
  function(gltf) {
    THREE.VRM.from(gltf).then(function(vrm) {
      currentVrm=vrm; scene.add(vrm.scene);
      vrm.scene.rotation.y=Math.PI; vrm.scene.position.set(0,-0.1,0);
      vrm.scene.traverse(function(obj){obj.frustumCulled=false;});
      if(vrm.humanoid){var lA=vrm.humanoid.getBoneNode('leftUpperArm');var rA=vrm.humanoid.getBoneNode('rightUpperArm');if(lA)lA.rotation.z=1.25;if(rA)rA.rotation.z=-1.25;}
      if(vrm.springBoneManager){vrm.springBoneManager.springBoneGroupList=[];}
      if(vrm.humanoid){console.log('VRM bones:',Object.keys(vrm.humanoid.humanBones).join(', '));}
      console.log('VRM loaded!');
    }).catch(function(err){console.warn('VRM parse failed:',err);});
  },
  function(p){console.log('Loading: '+Math.round((p.loaded/p.total)*100)+'%');},
  function(err){console.warn('Load error:',err);}
);

// ─── ANIMATION CLOCK ───
var clock = new THREE.Clock();
var time  = 0;

function animate() {
  requestAnimationFrame(animate);
  var delta=clock.getDelta(); time+=delta;
  var rp=rainGeo.attributes.position.array;
  for(var i=0;i<300;i++){rp[i*3+1]-=rainVel[i]*(speaking?2.5:1);if(rp[i*3+1]<-4)rp[i*3+1]=4;}
  rainGeo.attributes.position.needsUpdate=true;
  var fp=floatGeo.attributes.position.array;
  for(var i=0;i<80;i++){fp[i*3]+=floatVel[i*3];fp[i*3+1]+=floatVel[i*3+1];fp[i*3+2]+=floatVel[i*3+2];if(fp[i*3+1]>3.5){fp[i*3+1]=0;fp[i*3]=(Math.random()-0.5)*3;}if(Math.abs(fp[i*3])>2)floatVel[i*3]*=-1;if(Math.abs(fp[i*3+2])>1.5)floatVel[i*3+2]*=-1;}
  floatGeo.attributes.position.needsUpdate=true;
  floatMat.opacity=0.3+(speaking?Math.sin(time*6)*0.2+0.2:0);
  updateHandState(delta); updateBodyGlitch(delta);
  if(currentVrm&&currentVrm.humanoid){
    var h=currentVrm.humanoid;
    var hoverY=Math.sin(time*0.8)*0.04;
    var gy=bodyGlitch.active?bodyGlitch.snapY:0;
    currentVrm.scene.position.y=-0.18+hoverY+gy;
    currentVrm.scene.position.x=0;
    currentVrm.scene.rotation.z=Math.sin(time*0.6)*0.012;
    var lookY=Math.sin(time*0.2)*0.35; var lookX=Math.sin(time*0.15+1.2)*0.12;
    var cy2=Math.cos(lookY/2);var sy2=Math.sin(lookY/2);var cx2=Math.cos(lookX/2);var sx2=Math.sin(lookX/2);
    var headX=sx2*cy2;var headY2=cx2*sy2;var headZ=-sx2*sy2;var headW=cx2*cy2;
    if(speaking){headX=lerp(headX,0,0.06);headY2=lerp(headY2,0,0.06);headZ=lerp(headZ,0,0.06);headW=lerp(headW,1,0.06);}
    currentVrm.update(delta);
    currentVrm.humanoid.setPose({head:{rotation:[headX,headY2,headZ,headW]}});
    var lArm=h.getBoneNode('leftUpperArm');var rArm=h.getBoneNode('rightUpperArm');
    if(lArm){lArm.rotation.z=1.15;lArm.rotation.x=0.05;lArm.rotation.y=0.05;}
    if(rArm){rArm.rotation.z=-1.15;rArm.rotation.x=0.05;rArm.rotation.y=-0.05;}
    var lForearm=h.getBoneNode('leftLowerArm');var rForearm=h.getBoneNode('rightLowerArm');
    if(lForearm){lForearm.rotation.z=0.04;lForearm.rotation.x=0.1;lForearm.rotation.y=0.05;}
    if(rForearm){rForearm.rotation.z=-0.04;rForearm.rotation.x=0.1;rForearm.rotation.y=-0.05;}
    var hips=h.getBoneNode('hips');
    if(hips){hips.rotation.x=0;hips.rotation.z=0;hips.rotation.y=0;}
    var lUL=h.getBoneNode('leftUpperLeg');var lLL=h.getBoneNode('leftLowerLeg');var lFt=h.getBoneNode('leftFoot');
    if(lUL){lUL.rotation.x=1.0;lUL.rotation.y=0;lUL.rotation.z=0;}
    if(lLL){lLL.rotation.x=-1.1;lLL.rotation.y=0;lLL.rotation.z=0;}
    if(lFt){lFt.rotation.x=-0.5;lFt.rotation.y=0;lFt.rotation.z=0;}
    var rUL=h.getBoneNode('rightUpperLeg');var rLL=h.getBoneNode('rightLowerLeg');var rFt=h.getBoneNode('rightFoot');
    if(rUL){rUL.rotation.x=0;rUL.rotation.y=0;rUL.rotation.z=0;}
    if(rLL){rLL.rotation.x=0;rLL.rotation.y=0;rLL.rotation.z=0;}
    if(rFt){rFt.rotation.x=-0.5;rFt.rotation.y=0;rFt.rotation.z=0;}
    applyFingers(h,handCurl);
    if(currentVrm.blendShapeProxy){
      if(speaking){var lip=Math.abs(Math.sin(time*7))*0.5+Math.abs(Math.sin(time*11))*0.2;currentVrm.blendShapeProxy.setValue('A',lip*0.7);currentVrm.blendShapeProxy.setValue('O',lip*0.3);}
      else{currentVrm.blendShapeProxy.setValue('A',0);currentVrm.blendShapeProxy.setValue('O',0);}
      var bt=time%5;
      if(bt>4.75&&bt<4.92){currentVrm.blendShapeProxy.setValue('Blink',(bt-4.75)/0.085);}
      else{currentVrm.blendShapeProxy.setValue('Blink',0);}
    }
  }
  if(currentVrm){currentVrm.scene.position.x=lerp(currentVrm.scene.position.x,cypherTargetX,0.04);}
  if(gridLines.length>0)animateGrid(time);
  renderer.render(scene,camera);
}
animate();

// ─── SCANLINES ───
var scanCanvas=document.getElementById('scanline-canvas');
var scanCtx=scanCanvas.getContext('2d');
var scanOffset=0,glitchTimer=0,glitchPhase=0,glitchPhaseTime=0,glitchNextTrigger=4+Math.random()*8;
function resizeScanCanvas(){scanCanvas.width=window.innerWidth;scanCanvas.height=window.innerHeight;}
resizeScanCanvas(); window.addEventListener('resize',resizeScanCanvas);
function drawScanlines(){
  var w=scanCanvas.width,h=scanCanvas.height;
  scanCtx.clearRect(0,0,w,h);
  scanOffset=(scanOffset+0.5)%5;
  scanCtx.fillStyle='rgba(0,0,0,0.15)';
  for(var y=scanOffset;y<h;y+=5)scanCtx.fillRect(0,y,w,1.5);
  glitchTimer+=0.016; glitchPhaseTime+=0.016;
  if(glitchPhase===0&&glitchTimer>glitchNextTrigger){glitchPhase=1;glitchPhaseTime=0;glitchNextTrigger=5+Math.random()*10;glitchTimer=0;}
  if(glitchPhase===1){if(Math.random()>0.4){scanCtx.fillStyle='rgba(120,255,160,0.04)';scanCtx.fillRect(0,0,w,h);}if(glitchPhaseTime>0.08){glitchPhase=2;glitchPhaseTime=0;}}
  if(glitchPhase===2){var sl=4+Math.floor(Math.random()*6);for(var s=0;s<sl;s++){var sy2=Math.random()*h;var sh=3+Math.random()*20;var sdx=(Math.random()-0.5)*40;scanCtx.fillStyle='rgba(0,255,120,'+(0.08+Math.random()*0.12)+')';scanCtx.fillRect(sdx,sy2,w,sh);scanCtx.fillStyle='rgba(255,0,80,'+(0.04+Math.random()*0.06)+')';scanCtx.fillRect(sdx+3,sy2+1,w,sh*0.5);}if(Math.random()>0.5){scanCtx.fillStyle='rgba(120,255,180,0.25)';scanCtx.fillRect(0,Math.random()*h,w,2);}if(glitchPhaseTime>0.12+Math.random()*0.1){glitchPhase=3;glitchPhaseTime=0;}}
  if(glitchPhase===3){if(Math.random()>0.6){scanCtx.fillStyle='rgba(0,255,120,0.06)';scanCtx.fillRect((Math.random()-0.5)*10,Math.random()*h,w,2+Math.random()*4);}if(glitchPhaseTime>0.2){glitchPhase=0;glitchPhaseTime=0;}}
  var vignette=scanCtx.createRadialGradient(w/2,h/2,h*0.3,w/2,h/2,h*0.85);
  vignette.addColorStop(0,'rgba(0,0,0,0)'); vignette.addColorStop(1,'rgba(0,0,0,0.5)');
  scanCtx.fillStyle=vignette; scanCtx.fillRect(0,0,w,h);
  requestAnimationFrame(drawScanlines);
}
drawScanlines();
