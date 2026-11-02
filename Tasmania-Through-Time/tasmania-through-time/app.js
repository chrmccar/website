import * as maplibregl from 'https://unpkg.com/maplibre-gl@6.16.0/dist/maplibre-gl.mjs';

const $ = id => document.getElementById(id);
const mapError = $('error-state');
const ui = { panel: $('photo-panel'), filter: $('era-filter'), empty: $('empty-state'), count: $('photo-count') };
let allPhotos = [], visiblePhotos = [], groups = [], selectedId = null;
let markers = [];

const map = new maplibregl.Map({
  container: 'map',
  style: 'https://tiles.openfreemap.org/styles/positron',
  center: [146.55, -42.05], zoom: 6.2,
  minZoom: 4.4, maxZoom: 18,
  attributionControl: false,
  dragRotate: false, touchPitch: false, pitchWithRotate: false
});
map.addControl(new maplibregl.NavigationControl({showCompass:false}), 'top-right');
map.addControl(new maplibregl.AttributionControl({compact:true}), 'bottom-right');
map.on('error', err => {
  const msg = String(err?.error?.message || '');
  if (/style|failed to fetch/i.test(msg)) {
    mapError.textContent = 'Map tiles could not load. Check your internet connection and reload the page.';
    mapError.hidden = false;
  }
});
map.on('load', () => {
  mapError.hidden = true;
  map.fitBounds([[143.45,-44.25],[149.1,-39.05]],{padding:{top:125,bottom:50,left:25,right:25},duration:0,maxZoom:7});
});

function coords(photo) {
  const c = photo.camera || photo.subject;
  return c && Number.isFinite(+c.lat) && Number.isFinite(+c.lng) ? [+c.lng, +c.lat] : null;
}
function markerType(photo) {
  return photo.camera ? (photo.location_accuracy === 'known' ? 'known' : 'estimated') : 'subject';
}
function isInEra(photo, era) {
  if (era === 'all') return true;
  const a = Number.isFinite(photo.year_start) ? photo.year_start : null;
  const b = Number.isFinite(photo.year_end) ? photo.year_end : a;
  if (era === 'undated') return a === null;
  if (a === null) return false;
  if (era === 'pre1900') return a < 1900;
  if (era === '1900-1949') return a <= 1949 && b >= 1900;
  if (era === '1950-1999') return a <= 1999 && b >= 1950;
  if (era === '2000plus') return b >= 2000;
  return true;
}
function groupPhotos(photos) {
  const buckets = new Map();
  for (const p of photos) {
    const loc = coords(p);
    if (!loc) continue;
    const key = loc.map(n=>n.toFixed(5)).join(':');
    if (!buckets.has(key)) buckets.set(key, {coord:loc,photos:[]});
    buckets.get(key).photos.push(p);
  }
  return [...buckets.values()];
}
function makeMarker(group) {
  const index = group.photos.findIndex(p=>p.id === selectedId);
  const chosen = group.photos[Math.max(0,index)];
  const el = document.createElement('button');
  el.type = 'button'; el.className = `photo-marker ${markerType(chosen)}${index>=0?' active':''}`;
  el.setAttribute('aria-label',group.photos.length===1 ? `View ${chosen.title}` : `View ${group.photos.length} photographs at this location`);
  const arrow = document.createElement('span'); arrow.className = 'bearing-arrow';
  if (index >= 0 && Number.isFinite(chosen.camera?.bearing)) arrow.style.transform = `rotate(${chosen.camera.bearing}deg)`;
  else arrow.style.display='none';
  const pin = document.createElement('span'); pin.className='pin';
  el.append(arrow,pin);
  if (group.photos.length > 1){ const badge=document.createElement('span'); badge.className='pin-count';badge.textContent=group.photos.length;el.append(badge); }
  el.addEventListener('click', () => {
    if (index >= 0 && group.photos.length > 1) selectPhoto(group.photos[(index+1)%group.photos.length].id);
    else selectPhoto(group.photos[0].id);
  });
  return new maplibregl.Marker({element:el,anchor:'center'}).setLngLat(group.coord).addTo(map);
}
function updateMarkers() {
  markers.forEach(marker => marker.remove()); markers=[];
  groups = groupPhotos(visiblePhotos);
  groups.forEach(g => markers.push(makeMarker(g)));
}
function updateFilter() {
  visiblePhotos=allPhotos.filter(p=>isInEra(p,ui.filter.value));
  ui.count.textContent = `${visiblePhotos.length} photograph${visiblePhotos.length===1?'':'s'}`;
  ui.empty.hidden = visiblePhotos.length > 0;
  if (selectedId && !visiblePhotos.some(p=>p.id===selectedId)) closePanel();
  updateMarkers();
}
function put(id,value){ $(id).textContent=value || ''; }
function appendTextLine(target, value) {
  if (!value) return;
  const line=document.createElement('div');line.textContent=value;target.append(line);
}
function formatDate(p) {
  if(p.date_display) return p.date_display;
  if (p.year_start == null) return 'Date unknown';
  if (p.year_end != null && p.year_end !== p.year_start) return `${p.year_start}–${p.year_end}`;
  return `${p.year_start}`;
}
function renderPhoto(p) {
  const image=$('photo-image');
  image.src=p.image; image.alt=p.title ? `Historical photograph: ${p.title}` : 'Historical photograph';
  image.onerror=()=>{ image.alt='Photograph could not be loaded'; image.removeAttribute('src'); };
  put('photo-date',formatDate(p));put('photo-title',p.title);
  put('photo-description',p.description);
  const where=p.place || 'Tasmania';
  const qualifier=p.camera ? (p.location_accuracy==='known'?'Camera position':'Estimated camera position') : 'Depicted location (camera position unknown)';
  put('photo-location',`${where} · ${qualifier}`);
  put('photo-bearing',Number.isFinite(p.camera?.bearing) ? `Facing approximately ${Math.round(p.camera.bearing)}° clockwise from north` : 'Viewing direction unknown');
  const rights=p.rights || {};
  put('photo-credit', [rights.creator,rights.source].filter(Boolean).join(' · ') || 'Source not specified');
  const srcLink=$('photo-source-link');
  if (/^https?:\/\//i.test(rights.source_url||'')) {srcLink.href=rights.source_url;srcLink.hidden=false;}
  else { srcLink.hidden=true;srcLink.removeAttribute('href'); }
  const block=$('photo-rights'); block.replaceChildren();
  const rightLabels={not_verified:'Rights not verified',all_rights_reserved:'All rights reserved',permission:'Reproduced with permission',public_domain:'Public domain',cc_by:'Creative Commons Attribution',cc_by_sa:'Creative Commons Attribution-ShareAlike',cc0:'CC0',other:'Other rights arrangement'};
  appendTextLine(block,rights.statement || rightLabels[rights.status] || 'Rights information unavailable');
  appendTextLine(block,rights.source ? `Source: ${rights.source}`:'');
  appendTextLine(block,rights.archive_id ? `Reference: ${rights.archive_id}` : '');
  appendTextLine(block,rights.notes);
  if (/^https?:\/\//i.test(rights.licence_url||'')) {
    const link=document.createElement('a'); link.href=rights.licence_url;link.target='_blank';link.rel='noopener noreferrer';link.textContent='View licence ↗';block.append(link);
  }
  const idx=visiblePhotos.findIndex(item=>item.id===p.id);
  put('photo-position',`${idx+1} / ${visiblePhotos.length}`);
  $('prev-photo').disabled=visiblePhotos.length<2;
  $('next-photo').disabled=visiblePhotos.length<2;
}
function selectPhoto(id) {
  const p=visiblePhotos.find(item=>item.id===id);
  if(!p)return;
  selectedId=id;renderPhoto(p);
  ui.panel.classList.add('open');ui.panel.setAttribute('aria-hidden','false');
  updateMarkers();
  const c=coords(p);
  if(c){
    const mobile=window.matchMedia('(max-width:700px)').matches;
    map.easeTo({center:c,zoom:Math.max(map.getZoom(),mobile?8:8.5),padding:mobile?{bottom:230,top:65,left:20,right:20}:{top:60,bottom:20,left:20,right:Math.min(450,window.innerWidth*.43)},duration:400});
  }
}
function closePanel(){selectedId=null;ui.panel.classList.remove('open');ui.panel.setAttribute('aria-hidden','true');updateMarkers();map.easeTo({padding:{top:0,bottom:0,left:0,right:0},duration:200});}
function stepPhoto(direction){
  if(!visiblePhotos.length)return;
  const idx=Math.max(0,visiblePhotos.findIndex(p=>p.id===selectedId));
  selectPhoto(visiblePhotos[(idx+direction+visiblePhotos.length)%visiblePhotos.length].id);
}
$('close-panel').addEventListener('click',closePanel);
$('prev-photo').addEventListener('click',()=>stepPhoto(-1));
$('next-photo').addEventListener('click',()=>stepPhoto(1));
ui.filter.addEventListener('change',updateFilter);
const about=$('about-modal');
$('about-button').addEventListener('click',()=>{about.hidden=false;$('close-about').focus();});
$('close-about').addEventListener('click',()=>about.hidden=true);
about.addEventListener('click',ev=>{if(ev.target===about)about.hidden=true;});
document.addEventListener('keydown',ev=>{
  if(ev.key==='Escape'){if(!about.hidden)about.hidden=true;else closePanel();}
  if(!about.hidden || !selectedId)return;
  if(ev.key==='ArrowRight')stepPhoto(1);
  if(ev.key==='ArrowLeft')stepPhoto(-1);
});
async function loadPhotos(){
  try{
    const res=await fetch('./photos.json',{cache:'no-store'});
    if(!res.ok)throw new Error(`HTTP ${res.status}`);
    const data=await res.json();
    if(!Array.isArray(data.photos))throw new Error('Invalid photo catalogue');
    allPhotos=data.photos.filter(p=>p.published && (p.camera || p.subject) && p.image && p.id);
    updateFilter();
  } catch(err){
    ui.empty.hidden=true;
    mapError.textContent='Could not open the photograph catalogue. Reload or check photos.json.';
    mapError.hidden=false;
    console.error('Photo catalogue:',err);
  }
}
loadPhotos();
