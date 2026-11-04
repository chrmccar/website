import * as maplibregl from 'https://unpkg.com/maplibre-gl@6.16.0/dist/maplibre-gl.mjs';
const $=id=>document.getElementById(id);
const params=new URLSearchParams(location.search);
let map,manifest,imageURL=null,photoWidth=0,photoHeight=0;
let photos=[],selected=null,revision=null,placing=false,applying=false,cameraMode=false,applied=null,undo=[];
const fields=['longitude','latitude','altitude','bearing','pitch','fov'];
const root=new URL(params.get('data')||'./data/',location.href);
if(!root.pathname.endsWith('/'))root.pathname+='/';
const fail=error=>{$('error').hidden=false;$('error').textContent=String(error.message||error);};
const clearError=()=>{$('error').hidden=true;};
function url(name){return new URL(name,root).href;}
function escapeHTML(text){return String(text).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
async function json(name){const response=await fetch(url(name),{cache:'no-store'});if(!response.ok)throw Error(`Missing ${name}. Install the regional terrain update first.`);return response.json();}
function hasCoverage(lng,lat){
  if(!Number.isFinite(lng)||!Number.isFinite(lat)||Math.abs(lat)>=85)return false;
  const z=manifest.maxzoom,n=2**z;
  const x=Math.floor((lng+180)/360*n),y=Math.floor((1-Math.asinh(Math.tan(lat*Math.PI/180))/Math.PI)/2*n);
  return Object.hasOwn(manifest.tiles,`${z}/${x}/${y}`);
}
function groundHeight(lng,lat){
  if(!hasCoverage(lng,lat))throw Error('This location is outside the terrain pack.');
  const z=manifest.maxzoom,n=2**z,x=Math.floor((lng+180)/360*n),y=Math.floor((1-Math.asinh(Math.tan(lat*Math.PI/180))/Math.PI)/2*n);
  const tile=manifest.tiles[`${z}/${x}/${y}`],height=map.queryTerrainElevation([lng,lat]);
  // MapLibre can return 0 for an unloaded tile. Do not mistake that for supplied terrain.
  if(height==null||!Number.isFinite(height)||height<tile.elevation_min_m-.01||height>tile.elevation_max_m+.01)throw Error('Wait for the elevation tile at this location to load.');
  return height;
}
function frame(){
  if(!photoWidth)return;
  const view=$('view').getBoundingClientRect(),scale=Math.min(view.width/photoWidth,view.height/photoHeight);
  const width=photoWidth*scale,height=photoHeight*scale;
  Object.assign($('overlay').style,{width:`${width}px`,height:`${height}px`,left:`${(view.width-width)/2}px`,top:`${(view.height-height)/2}px`});
}
function viewportFov(){
  const photoFov=Number($('fov').value);
  const height=photoHeight?photoHeight*Math.min($('view').clientWidth/photoWidth,$('view').clientHeight/photoHeight):$('view').clientHeight;
  return 2*Math.atan(Math.tan(photoFov*Math.PI/360)*$('view').clientHeight/height)*180/Math.PI;
}
async function source(delivery){
  // The regional viewer uses the finest complete tiles only. Missing coarse tiles
  // must never expose a flat fallback inside otherwise valid fine coverage.
  const common={type:'raster-dem',encoding:'terrarium',tileSize:256,minzoom:manifest.maxzoom,maxzoom:manifest.maxzoom,
    bounds:manifest.bounds,attribution:escapeHTML(manifest.attribution)};
  if(delivery==='pmtiles'){
    const response=await fetch(url('terrain.pmtiles'),{headers:{Range:'bytes=0-126'}});
    if(response.status!==206||!/^bytes 0-126\/\d+$/.test(response.headers.get('Content-Range')||'')){
      if(response.body)await response.body.cancel();
      throw Error('This host does not support archive byte ranges. Choose PNG tiles.');
    }
    await response.arrayBuffer();
    return {...common,url:`pmtiles://${url('terrain.pmtiles')}`};
  }
  return {...common,tiles:[url('tiles/{z}/{x}/{y}.png').replace(/%7B/g,'{').replace(/%7D/g,'}') ]};
}
function values(){return Object.fromEntries(fields.map(id=>[id,$(id).value]));}
function fillValues(v){for(const id of fields)$(id).value=v[id];}
function poseValues(p){return {longitude:p.lng,latitude:p.lat,altitude:p.elevation_m,bearing:p.bearing,pitch:p.pitch,fov:p.vertical_fov};}
function pose(){
  if(fields.some(id=>$(id).value.trim()===''))throw Error('Fill in every camera and field-of-view value.');
  return {lng:Number($('longitude').value),lat:Number($('latitude').value),elevation_m:Number($('altitude').value),bearing:Number($('bearing').value),pitch:Number($('pitch').value),vertical_fov:Number($('fov').value)};
}
function actualCamera(){
  // Invert the pinned renderer's Mercator perspective using public map getters.
  // No private MapLibre camera fields or assumed fixed field of view.
  const centre=maplibregl.MercatorCoordinate.fromLngLat(map.getCenter());
  const distance=$('map').clientHeight/(2*Math.tan(map.getVerticalFieldOfView()*Math.PI/360))/(512*2**map.getZoom());
  const bearing=map.getBearing()*Math.PI/180,pitch=map.getPitch()*Math.PI/180;
  const eye=new maplibregl.MercatorCoordinate(centre.x-Math.sin(bearing)*Math.sin(pitch)*distance,centre.y+Math.cos(bearing)*Math.sin(pitch)*distance).toLngLat();
  return {lng:eye.lng,lat:eye.lat,elevation_m:map.getCameraTargetElevation()+Math.cos(pitch)*distance/centre.meterInMercatorCoordinateUnits(),bearing:(map.getBearing()+360)%360,pitch:map.getPitch(),vertical_fov:Number($('fov').value)};
}
function closeEnough(a,b){
  return Math.hypot((a.lng-b.lng)*Math.cos(a.lat*Math.PI/180),a.lat-b.lat)*111320<2 && Math.abs(a.elevation_m-b.elevation_m)<.5 && Math.abs(a.pitch-b.pitch)<.01;
}
function applyView(recordUndo=true){
  const p=pose();
  if(!Object.values(p).every(Number.isFinite)||!hasCoverage(p.lng,p.lat)||p.pitch<0||p.pitch>89.9||p.vertical_fov<10||p.vertical_fov>100||p.bearing<0||p.bearing>360)throw Error('Use a camera inside the terrain coverage, pitch 0–89.9°, bearing 0–360°, and photo vertical FOV 10–100°.');
  const ground=groundHeight(p.lng,p.lat);
  if(p.elevation_m<=ground+1)throw Error('Camera elevation must be more than one metre above the terrain in the same height datum.');
  const fov=viewportFov();if(fov>=150)throw Error('This panorama needs a smaller photo vertical field of view.');
  if(recordUndo&&applied&&fields.some(id=>Number(applied[id])!==Number(poseValues(p)[id])))undo.push(applied);
  applying=true;
  try{
    map.setVerticalFieldOfView(fov);map.setCenterClampedToGround(false);
    map.jumpTo(map.calculateCameraOptionsFromCameraLngLatAltRotation([p.lng,p.lat],p.elevation_m,p.bearing,p.pitch,0));
    if(!closeEnough(p,actualCamera()))throw Error('This viewpoint was constrained by the renderer. Raise the camera or reduce its tilt before saving.');
    applied=poseValues(p);cameraMode=true;clearError();
  }finally{applying=false;}
}
async function overlay(src){
  const image=new Image();image.src=src;await image.decode();
  photoWidth=image.naturalWidth;photoHeight=image.naturalHeight;
  $('overlay').src=src;$('overlay').hidden=false;frame();
  $('image-info').textContent=`${photoWidth} × ${photoHeight} pixels. Field of view refers to the full photograph height; letterboxing is accounted for.`;
}
function opacity(value){$('opacity').value=value;$('overlay').style.opacity=Number(value)/100;$('opacity-value').textContent=`${value}%`;}
async function selectPhoto(id){
  selected=photos.find(p=>p.id===id)||null;revision=selected?.alignment?.revision??null;
  $('saving-controls').hidden=!selected;undo=[];applied=null;cameraMode=false;$('approve').checked=false;
  if(!selected)return;
  const path=(selected.published?'/tasmania-through-time/images/':'/photo-assets/')+selected.image.split('/').pop();
  await overlay(path);$('alignment-controls').open=true;
  const original=selected.camera;
  $('original-position').textContent=original?`Existing camera: ${original.lat}, ${original.lng} (${selected.location_accuracy||'estimated'}). Alignment saves separately.`:'No existing camera position. Subject coordinates stay separate.';
  const draft=selected.alignment?.draft;
  $('notes').value=draft?.notes||'';$('confidence').value=draft?.confidence||'low';opacity(draft?.opacity??50);
  if(draft){fillValues(poseValues(draft.pose));}
  else if(original){$('longitude').value=original.lng;$('latitude').value=original.lat;$('bearing').value=original.bearing??0;}
  const focus=draft?.pose||original;
  if(focus&&hasCoverage(focus.lng,focus.lat))map.jumpTo({center:[focus.lng,focus.lat],zoom:manifest.maxzoom,pitch:0,bearing:0});
  if(!hasCoverage(Number($('longitude').value),Number($('latitude').value)))fail('This photo is outside the Lilydale / Mount Arthur terrain pack. Its entry is unchanged.');else clearError();
  $('save-status').textContent=selected.alignment?.accepted?'An accepted alignment will be included with this photo in the next approved website export. Draft edits stay private.':draft?'Saved private draft loaded. Click Apply viewpoint to inspect it.':'Choose the camera position, adjust the view, then save a private draft.';
}
async function save(action){
  if(!selected)throw Error('Select a saved photograph from your collection first.');
  const body={id:selected.id,revision,action};
  if(action==='save'){
    applyView();
    body.pose=pose();body.opacity=Number($('opacity').value);body.confidence=$('confidence').value;body.notes=$('notes').value;
  }
  if(action==='accept'&&!$('approve').checked)throw Error('Tick approval to accept the saved draft.');
  const response=await fetch('/api/alignment',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const result=await response.json();if(!response.ok)throw Error(result.error||'Unable to save alignment');
  selected=result.photo;photos[photos.findIndex(p=>p.id===selected.id)]=selected;revision=selected.alignment.revision;
  if(action==='undo'){fillValues(poseValues(selected.alignment.draft.pose));$('notes').value=selected.alignment.draft.notes;opacity(selected.alignment.draft.opacity);applyView();}
  $('approve').checked=false;
  $('save-status').textContent={save:'Alignment draft saved privately. Existing camera and subject coordinates are unchanged.',accept:'Saved draft accepted. Download the website update in Photo Manager to export approved pose metadata.',withdraw:'Alignment is private. It will be excluded from the next website update.',undo:'Previous saved draft restored. Any accepted pose remains unchanged.'}[action];clearError();
}
async function collection(){
  if(!['127.0.0.1','localhost'].includes(location.hostname))return;
  const response=await fetch('/api/photos',{cache:'no-store'});if(!response.ok)return;
  const data=await response.json();if(!Array.isArray(data.photos))return;
  photos=data.photos;$('collection-controls').hidden=false;
  for(const photo of photos){const option=document.createElement('option');option.value=photo.id;option.textContent=photo.title;$('collection').append(option);}
  $('collection').addEventListener('change',()=>selectPhoto($('collection').value).catch(fail));
  if(params.get('photo')){$('collection').value=params.get('photo');await selectPhoto(params.get('photo'));}
}
async function start(){
  if(root.origin!==location.origin)throw Error('Elevation data must be served from this project-controlled origin.');
  manifest=await json('manifest.json');
  if(manifest.encoding!=='terrarium'||manifest.exaggeration!==1)throw Error('Unsupported terrain build manifest');
  $('dataset-status').textContent=manifest.kind==='synthetic-test'?'SYNTHETIC TEST DATA — not Tasmanian terrain':'LIST 25 m · regional terrain · height datum unconfirmed';
  $('credit').textContent=manifest.attribution;
  const licence=new URL(manifest.licence_url);if(!['https:','http:'].includes(licence.protocol))throw Error('Invalid licence URL');$('licence').href=licence.href;
  $('measurements').textContent=`${Object.keys(manifest.tiles).length} tiles · PNG ${manifest.png_bytes.toLocaleString()} bytes · archive ${manifest.pmtiles_bytes.toLocaleString()} bytes · ${manifest.vertical_datum}`;
  if(!window.pmtiles)throw Error('PMTiles browser library could not load.');
  const protocol=new window.pmtiles.Protocol();maplibregl.addProtocol('pmtiles',protocol.tile);
  const mask=await json('nodata-mask.geojson');
  const tileCentre=key=>{const [z,x,y]=key.split('/').map(Number);return [(x+.5)/2**z*360-180,Math.atan(Math.sinh(Math.PI*(1-2*(y+.5)/2**z)))*180/Math.PI];};
  const target=[(manifest.requested_bounds[0]+manifest.requested_bounds[2])/2,(manifest.requested_bounds[1]+manifest.requested_bounds[3])/2];
  const [key]=Object.keys(manifest.tiles).filter(key=>key.startsWith(`${manifest.maxzoom}/`)).sort((a,b)=>tileCentre(a).reduce((s,v,i)=>s+(v-target[i])**2,0)-tileCentre(b).reduce((s,v,i)=>s+(v-target[i])**2,0));
  if(!key)throw Error('No valid terrain tiles');const centre=tileCentre(key);
  $('longitude').value=centre[0];$('latitude').value=centre[1];$('altitude').value=Math.ceil(manifest.tiles[key].elevation_max_m+300);
  const delivery=params.get('delivery')==='pmtiles'?'pmtiles':'png';$('delivery').value=delivery;
  // The ready-to-use local update carries PNGs only; keep archive experiments in the pilot server.
  if(location.port==='8765')$('delivery').closest('label').hidden=true;
  map=new maplibregl.Map({container:'map',center:centre,zoom:manifest.maxzoom,pitch:0,bearing:0,
    maxPitch:89.9,minZoom:manifest.maxzoom,maxZoom:24,attributionControl:true,trackResize:false,
    style:{version:8,sources:{terrain:await source(delivery),mask:{type:'geojson',data:mask}},layers:[
      {id:'background',type:'background',paint:{'background-color':'#c9ceca'}},
      {id:'relief',type:'hillshade',source:'terrain',paint:{'hillshade-exaggeration':.5,'hillshade-shadow-color':'#303b37','hillshade-highlight-color':'#f4f5ee'}},
      {id:'unavailable',type:'fill',source:'mask',paint:{'fill-color':'#999f9d','fill-opacity':1}}
    ]}});
  map.addControl(new maplibregl.NavigationControl());
  map.on('error',event=>{
    const missing=String(event.error?.url||'').match(/tiles\/(\d+)\/(\d+)\/(\d+)\.png/);
    if(event.error?.status===404&&missing&&!Object.hasOwn(manifest.tiles,missing.slice(1).join('/')))return;
    if(!/abort/i.test(String(event.error?.message)))fail(event.error||'Terrain could not load');
  });
  function enableTerrain(){
    map.setTerrain({source:'terrain',exaggeration:1});
    // Pinned MapLibre 6.16 normally renders RTT tiles below the DEM's minimum
    // level, which invents flat terrain for regional datasets. Omit those tiles.
    // Fail visibly if a future renderer changes this adapter.
    if(!map.terrain?.tileManager)throw Error('This renderer cannot constrain the regional terrain footprint.');
    map.terrain.tileManager.minzoom=manifest.maxzoom;map.triggerRepaint();
  }
  map.on('load',()=>{try{enableTerrain();collection().catch(fail);}catch(error){fail(error);}});
  map.on('moveend',()=>{
    if(applying||!cameraMode)return;
    const current=actualCamera();fillValues(poseValues(current));applied=values();
  });
  map.on('click',event=>{
    if(!hasCoverage(event.lngLat.lng,event.lngLat.lat)){$('coverage-status').textContent='No elevation data at this location.';return;}
    let elevation;try{elevation=groundHeight(event.lngLat.lng,event.lngLat.lat);}catch(error){$('coverage-status').textContent=error.message;return;}
    $('coverage-status').textContent=elevation==null?'Elevation tile is not loaded yet.':`Elevation ${elevation.toFixed(2)} m (supplied LIST heights); not a survey measurement.`;
    if(placing&&elevation!=null){
      $('longitude').value=event.lngLat.lng;$('latitude').value=event.lngLat.lat;$('altitude').value=(elevation+1.7).toFixed(2);
      placing=false;$('set-camera').setAttribute('aria-pressed','false');$('set-camera').textContent='Place camera on map';
      $('coverage-status').textContent+=' Camera placed 1.7 m above the DEM. Click Apply viewpoint.';
    }
  });
  $('set-camera').addEventListener('click',()=>{placing=!placing;$('set-camera').setAttribute('aria-pressed',String(placing));$('set-camera').textContent=placing?'Click the camera location on the map…':'Place camera on map';});
  $('use-camera').addEventListener('click',()=>{
    try{
      const p=selected?.camera;if(!p)throw Error('This photograph has no saved camera location. Place the camera on the map or enter coordinates.');
      if(!hasCoverage(p.lng,p.lat))throw Error('The saved camera is outside this regional terrain pack.');
      const height=groundHeight(p.lng,p.lat);
      $('longitude').value=p.lng;$('latitude').value=p.lat;$('altitude').value=(height+1.7).toFixed(2);$('bearing').value=p.bearing??0;$('pitch').value=89;
      $('coverage-status').textContent='Using the saved horizontal location with an estimated eye height of 1.7 m and near-horizontal view. Click Apply viewpoint.';clearError();
    }catch(error){fail(error);}
  });
  $('delivery').addEventListener('change',async()=>{
    try{
      const next=await source($('delivery').value);
      map.setTerrain(null);map.removeLayer('relief');map.removeSource('terrain');map.addSource('terrain',next);
      map.addLayer({id:'relief',type:'hillshade',source:'terrain',paint:{'hillshade-exaggeration':.5}},'unavailable');
      enableTerrain();clearError();
    }catch(error){fail(error);}
  });
  $('photo').addEventListener('change',async event=>{
    const file=event.target.files[0];if(!file)return;
    try{
      // A loose file cannot accidentally save a pose against the previously selected record.
      selected=null;$('collection').value='';$('saving-controls').hidden=true;
      if(imageURL)URL.revokeObjectURL(imageURL);imageURL=URL.createObjectURL(file);await overlay(imageURL);
    }catch(error){fail(error);}
  });
  $('opacity').addEventListener('input',()=>opacity($('opacity').value));
  $('apply').addEventListener('click',()=>{try{applyView();}catch(error){fail(error);}});
  $('undo-view').addEventListener('click',()=>{try{if(!undo.length)throw Error('No earlier applied viewpoint.');fillValues(undo.pop());applyView(false);}catch(error){fail(error);}});
  $('reset').addEventListener('click',()=>{cameraMode=false;map.setCenterClampedToGround(true);map.setVerticalFieldOfView(36.87);map.jumpTo({center:centre,zoom:manifest.maxzoom,pitch:0,bearing:0});});
  for(const [id,action] of [['save-draft','save'],['accept','accept'],['withdraw','withdraw'],['undo-saved','undo']])$(id).addEventListener('click',()=>save(action).catch(fail));
  new ResizeObserver(()=>{
    const previous=applied;
    applying=true;frame();map.resize();applying=false;
    if(cameraMode&&previous){fillValues(previous);try{applyView(false);}catch(error){fail(error);}}
  }).observe($('view'));
}
start().catch(fail);
