import * as maplibregl from 'https://unpkg.com/maplibre-gl@6.16.0/dist/maplibre-gl.mjs';
const $=id=>document.getElementById(id);
const params=new URLSearchParams(location.search);
let map,manifest,imageURL=null,photoWidth=0,photoHeight=0;
const root=new URL(params.get('data')||'./data/',location.href);
if(!root.pathname.endsWith('/'))root.pathname+='/';
const fail=error=>{$('error').hidden=false;$('error').textContent=String(error.message||error);};
function url(name){return new URL(name,root).href;}
function escapeHTML(text){return String(text).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
async function json(name){const response=await fetch(url(name),{cache:'no-store'});if(!response.ok)throw Error(`Missing ${name}. Build a regional dataset first; see the terrain pilot instructions.`);return response.json();}
function hasCoverage(lng,lat){
  if(!Number.isFinite(lng)||!Number.isFinite(lat)||Math.abs(lat)>=85)return false;
  const z=manifest.maxzoom,n=2**z;
  const x=Math.floor((lng+180)/360*n),y=Math.floor((1-Math.asinh(Math.tan(lat*Math.PI/180))/Math.PI)/2*n);
  return Object.hasOwn(manifest.tiles,`${z}/${x}/${y}`);
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
  const common={type:'raster-dem',encoding:'terrarium',tileSize:256,minzoom:manifest.minzoom,maxzoom:manifest.maxzoom,
    bounds:manifest.bounds,attribution:escapeHTML(manifest.attribution)};
  if(delivery==='pmtiles'){
    const response=await fetch(url('terrain.pmtiles'),{headers:{Range:'bytes=0-126'}});
    if(response.status!==206||!/^bytes 0-126\/\d+$/.test(response.headers.get('Content-Range')||'')){
      if(response.body)await response.body.cancel();
      throw Error('This host did not honour the archive byte-range request. PMTiles is unavailable; choose PNG tiles.');
    }
    await response.arrayBuffer();
    return {...common,url:`pmtiles://${url('terrain.pmtiles')}`};
  }
  return {...common,tiles:[url('tiles/{z}/{x}/{y}.png').replace(/%7B/g,'{').replace(/%7D/g,'}')]};
}
async function start(){
  if(root.origin!==location.origin)throw Error('Pilot elevation data must be served from this project-controlled origin.');
  manifest=await json('manifest.json');
  if(manifest.encoding!=='terrarium'||manifest.exaggeration!==1)throw Error('Unsupported terrain build manifest');
  const status=manifest.kind==='synthetic-test'?'SYNTHETIC TEST DATA — not Tasmanian terrain':'LIST input — source metadata verification still required';
  $('dataset-status').textContent=status;
  $('credit').textContent=manifest.attribution;
  const licence=new URL(manifest.licence_url);if(!['https:','http:'].includes(licence.protocol))throw Error('Invalid licence URL');
  $('licence').href=licence.href;
  $('measurements').textContent=`${Object.keys(manifest.tiles).length} valid tiles · PNG ${manifest.png_bytes.toLocaleString()} bytes · archive ${manifest.pmtiles_bytes.toLocaleString()} bytes · elevation datum: ${manifest.vertical_datum}`;
  if(!window.pmtiles)throw Error('PMTiles browser library could not load.');
  const protocol=new window.pmtiles.Protocol();maplibregl.addProtocol('pmtiles',protocol.tile);
  const coverage=await json('coverage.geojson'),mask=await json('nodata-mask.geojson');
  const [key]=Object.keys(manifest.tiles).filter(key=>key.startsWith(`${manifest.maxzoom}/`)).sort((a,b)=>{
    const centre=key=>{const [z,x,y]=key.split('/').map(Number);return [(x+.5)/2**z*360-180,Math.atan(Math.sinh(Math.PI*(1-2*(y+.5)/2**z)))*180/Math.PI];};
    const target=[(manifest.requested_bounds[0]+manifest.requested_bounds[2])/2,(manifest.requested_bounds[1]+manifest.requested_bounds[3])/2];
    return centre(a).reduce((s,v,i)=>s+(v-target[i])**2,0)-centre(b).reduce((s,v,i)=>s+(v-target[i])**2,0);
  });
  if(!key)throw Error('No valid terrain tiles');
  const [z,x,y]=key.split('/').map(Number);
  const centre=[(x+.5)/2**z*360-180,Math.atan(Math.sinh(Math.PI*(1-2*(y+.5)/2**z)))*180/Math.PI];
  $('longitude').value=centre[0];$('latitude').value=centre[1];
  $('altitude').value=Math.ceil(manifest.tiles[key].elevation_max_m+300);
  const delivery=params.get('delivery')==='pmtiles'?'pmtiles':'png';$('delivery').value=delivery;
  map=new maplibregl.Map({container:'map',center:centre,zoom:Math.max(manifest.minzoom,manifest.maxzoom-.5),pitch:60,bearing:0,
    maxPitch:85,minZoom:manifest.minzoom,maxZoom:18,maxBounds:manifest.bounds,attributionControl:true,
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
  map.on('load',()=>{map.setTerrain({source:'terrain',exaggeration:1});});
  map.on('click',event=>{
    if(!hasCoverage(event.lngLat.lng,event.lngLat.lat)){$('coverage-status').textContent='No elevation data at this location.';return;}
    const elevation=map.queryTerrainElevation(event.lngLat);
    $('coverage-status').textContent=elevation==null?'Elevation tile is not loaded yet.':`Elevation ${elevation.toFixed(2)} m (${manifest.vertical_datum}); not a survey measurement.`;
  });
  $('delivery').addEventListener('change',async()=>{
    try{
      const next=await source($('delivery').value);
      map.setTerrain(null);map.removeLayer('relief');map.removeSource('terrain');map.addSource('terrain',next);
      map.addLayer({id:'relief',type:'hillshade',source:'terrain',paint:{'hillshade-exaggeration':.5}},'unavailable');
      map.setTerrain({source:'terrain',exaggeration:1});$('error').hidden=true;
    }catch(error){fail(error);}
  });
  $('photo').addEventListener('change',async event=>{
    const file=event.target.files[0];if(!file)return;
    try{
      const bitmap=await createImageBitmap(file);photoWidth=bitmap.width;photoHeight=bitmap.height;bitmap.close();
      if(imageURL)URL.revokeObjectURL(imageURL);imageURL=URL.createObjectURL(file);
      $('overlay').src=imageURL;$('overlay').hidden=false;frame();
      $('image-info').textContent=`${photoWidth} × ${photoHeight} pixels. FOV below refers to the full photo height; letterboxing is accounted for.`;
    }catch(error){fail(error);}
  });
  $('opacity').addEventListener('input',()=>{$('overlay').style.opacity=Number($('opacity').value)/100;$('opacity-value').textContent=`${$('opacity').value}%`;});
  $('apply').addEventListener('click',()=>{
    try{
      const lng=Number($('longitude').value),lat=Number($('latitude').value),alt=Number($('altitude').value),bearing=Number($('bearing').value),pitch=Number($('pitch').value),fov=Number($('fov').value);
      if(![lng,lat,alt,bearing,pitch,fov].every(Number.isFinite)||!hasCoverage(lng,lat)||pitch<0||pitch>85||fov<10||fov>100)throw Error('Enter a valid camera position inside the terrain coverage, pitch 0–85°, and photo vertical FOV 10–100°.');
      const ground=map.queryTerrainElevation([lng,lat]);if(ground==null)throw Error('Wait for the camera elevation tile to load.');
      if(alt<=ground+1)throw Error('Camera elevation must be above the terrain in the same height datum.');
      const verticalFov=viewportFov();if(verticalFov>=150)throw Error('This panorama needs a smaller photo vertical FOV.');
      map.setVerticalFieldOfView(verticalFov);map.setCenterClampedToGround(false);
      map.jumpTo(map.calculateCameraOptionsFromCameraLngLatAltRotation([lng,lat],alt,bearing,pitch,0));
      $('error').hidden=true;
    }catch(error){fail(error);}
  });
  $('reset').addEventListener('click',()=>{map.setCenterClampedToGround(true);map.setVerticalFieldOfView(36.87);map.jumpTo({center:centre,zoom:Math.max(manifest.minzoom,manifest.maxzoom-.5),pitch:60,bearing:0});});
  new ResizeObserver(()=>{frame();map.resize();}).observe($('view'));
}
start().catch(fail);
