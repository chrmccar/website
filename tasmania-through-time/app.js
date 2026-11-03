import * as maplibregl from 'https://unpkg.com/maplibre-gl@6.16.0/dist/maplibre-gl.mjs';

const $ = id => document.getElementById(id);
const mapError = $('error-state');
const ui = { panel: $('photo-panel'), empty: $('empty-state') };
let allPhotos = [], visiblePhotos = [], groups = [], selectedId = null;
let markers = [], lastMarker = null;
let allPlaces=[],visiblePlaces=[];
const entries=()=>[...visiblePhotos,...visiblePlaces];

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
    mapError.dataset.source = 'map';
    mapError.textContent = 'Map tiles could not load. Check your internet connection and reload the page.';
    mapError.hidden = false;
  }
});
map.on('load', () => {
  if (mapError.dataset.source === 'map') mapError.hidden = true;
  map.fitBounds([[143.45,-44.25],[149.1,-39.05]],{padding:{top:25,bottom:50,left:25,right:25},duration:0,maxZoom:7});
});

function coords(photo) {
  const c = photo.camera || photo.subject || photo.location;
  return c && Number.isFinite(c.lat) && Number.isFinite(c.lng) && Math.abs(c.lat)<=90 && Math.abs(c.lng)<=180 ? [c.lng, c.lat] : null;
}
const yearSlider = $('year-slider');
let firstYear = 1800, lastYear = new Date().getFullYear();
function photoYears(photo) {
  const start = Number.isInteger(photo.year_start) ? photo.year_start : photo.year_end;
  const end = Number.isInteger(photo.year_end) ? photo.year_end : start;
  return Number.isInteger(start) && Number.isInteger(end) ? [Math.min(start,end), Math.max(start,end)] : null;
}
function matchesTime(photo) {
  const year = Number(yearSlider.value);
  if (year === firstYear - 1) return true;
  const years = photoYears(photo);
  // A photograph with an uncertain date interval matches any overlapping year.
  return years !== null && years[0] <= year && years[1] >= year;
}
function setupTimeline() {
  const years = [...allPhotos,...allPlaces].flatMap(photo => photoYears(photo) || []);
  firstYear = Math.min(1800, ...years);
  lastYear = Math.max(new Date().getFullYear(), ...years);
  yearSlider.min = firstYear - 1;
  yearSlider.max = lastYear;
  yearSlider.value = firstYear - 1;
  yearSlider.disabled = false;
}
function updateTimeControls() {
  const year = Number(yearSlider.value);
  const label = year === firstYear - 1 ? 'All time' : `${year}`;
  $('time-label').textContent = label;
  yearSlider.setAttribute('aria-valuetext', label);
}
yearSlider.addEventListener('input', () => {
  updateTimeControls();
  updateFilter();
});
function groupPhotos(photos) {
  const buckets = new Map();
  for (const p of photos) {
    const loc = coords(p);
    if (!loc) continue;
    const key = loc.join(':');
    if (!buckets.has(key)) buckets.set(key, {coord:loc,photos:[]});
    buckets.get(key).photos.push(p);
  }
  return [...buckets.values()];
}
function makeMarker(group) {
  const index = group.photos.findIndex(p=>p.id === selectedId);
  const chosen = group.photos[Math.max(0,index)];
  const el = document.createElement('button');
  el.dataset.lng=group.coord[0];
  el.type = 'button'; el.className = 'photo-marker'+(chosen.kind==='place'?' place-marker':'');
  el.setAttribute('aria-pressed', String(index >= 0));
  el.setAttribute('aria-label',group.photos.length===1 ? `View ${chosen.title}` : `View ${group.photos.length} entries at this location`);
  const bearing = chosen.camera?.bearing;
  const hasDirection = Number.isFinite(bearing) && bearing >= 0 && bearing <= 360;
  if (hasDirection) {
    const tick = document.createElement('span');
    tick.className = 'direction-tick';
    tick.setAttribute('aria-hidden', 'true');
    el.append(tick);
  }
  const pin = document.createElement('span'); pin.className='pin';
  el.append(pin);
  el.addEventListener('click', () => {
    lastMarker = el;
    if (index >= 0 && group.photos.length > 1) selectPhoto(group.photos[(index+1)%group.photos.length].id);
    else selectPhoto(group.photos[0].id);
  });
  return new maplibregl.Marker({element:el,anchor:'center',subpixelPositioning:true,rotation:hasDirection ? bearing : 0,rotationAlignment:'map'}).setLngLat(group.coord).addTo(map);
}
function updateMarkers() {
  markers.forEach(marker => marker.remove()); markers=[];
  groups = groupPhotos(entries());
  groups.forEach(g => markers.push(makeMarker(g)));
}
function updateFilter() {
  visiblePhotos=allPhotos.filter(matchesTime);
  const year=Number(yearSlider.value);
  visiblePlaces=allPlaces.filter(p=>year===firstYear-1 || (year>=p.year_start && (p.year_end==null || year<=p.year_end)));
  ui.empty.hidden = entries().length > 0;
  ui.empty.textContent = allPhotos.length+allPlaces.length ? 'No entries for this year.' : 'No entries here yet.';
  if (selectedId && !entries().some(p=>p.id===selectedId)) closePanel(false);
  else if (selectedId) renderPhoto(entries().find(p=>p.id===selectedId));
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
  if(p.kind==='place'){renderPlace(p);return;}
  ui.panel.setAttribute('aria-label','Photograph details');
  $('photo-image-wrap').hidden=false;$('photo-bearing').hidden=false;$('rights-details').hidden=false;
  $('photo-credit').closest('.meta-block').hidden=false;
  $('panel-kind').textContent='FROM THE COLLECTION';
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
  const idx=entries().findIndex(item=>item.id===p.id);
  put('photo-position',`${idx+1} / ${entries().length}`);
  $('prev-photo').disabled=entries().length<2;
  $('next-photo').disabled=entries().length<2;
}
function renderPlace(p){
  ui.panel.setAttribute('aria-label','Place details');$('panel-kind').textContent='PLACE / BUILDING';
  $('photo-image-wrap').hidden=true;$('photo-image').removeAttribute('src');
  $('photo-bearing').hidden=true;$('rights-details').hidden=true;
  put('photo-title',p.title);put('photo-description',p.description);
  put('photo-date',p.year_end==null?`From ${p.year_start}`:`${p.year_start}–${p.year_end}`);
  put('photo-location','Place / building');
  const link=$('photo-source-link'),hasSource=/^https?:\/\//i.test(p.source_url||'');
  $('photo-credit').closest('.meta-block').hidden=!hasSource;put('photo-credit','');
  link.hidden=!hasSource;if(hasSource)link.href=p.source_url;else link.removeAttribute('href');
  put('photo-position',`${entries().findIndex(item=>item.id===p.id)+1} / ${entries().length}`);
  $('prev-photo').disabled=$('next-photo').disabled=entries().length<2;
}
function selectPhoto(id) {
  const p=entries().find(item=>item.id===id);
  if(!p)return;
  selectedId=id;renderPhoto(p);
  ui.panel.inert=false;ui.panel.classList.add('open');ui.panel.setAttribute('aria-hidden','false');
  $('close-panel').focus({preventScroll:true});
  updateMarkers();

}
function closePanel(restoreFocus=true){const restore=!!selectedId && restoreFocus;selectedId=null;ui.panel.classList.remove('open');ui.panel.setAttribute('aria-hidden','true');ui.panel.inert=true;updateMarkers();if(restore){const marker=markers.find(m=>m.getLngLat().lng===Number(lastMarker?.dataset.lng));(marker?.getElement()||document.querySelector('.photo-marker')||$('about-button')).focus({preventScroll:true});}}
function stepPhoto(direction){
  if(!entries().length)return;
  const idx=Math.max(0,entries().findIndex(p=>p.id===selectedId));
  selectPhoto(entries()[(idx+direction+entries().length)%entries().length].id);
}
$('close-panel').addEventListener('click',closePanel);
$('prev-photo').addEventListener('click',()=>stepPhoto(-1));
$('next-photo').addEventListener('click',()=>stepPhoto(1));
const about=$('about-modal');
$('about-button').addEventListener('click',()=>{about.hidden=false;$('close-about').focus();});
function closeAbout(){about.hidden=true;$('about-button').focus();}
$('close-about').addEventListener('click',closeAbout);
about.addEventListener('click',ev=>{if(ev.target===about)closeAbout();});
document.addEventListener('keydown',ev=>{
  if(ev.key==='Escape'){if(!about.hidden)closeAbout();else closePanel();}
  if(!about.hidden){if(ev.key==='Tab'){ev.preventDefault();$('close-about').focus();}return;}
  if(!selectedId || ev.target.matches('input, select, textarea, button'))return;
  if(ev.key==='ArrowRight')stepPhoto(1);
  if(ev.key==='ArrowLeft')stepPhoto(-1);
});
async function loadPhotos(){
  try{
    const res=await fetch('./photos.json',{cache:'no-store'});
    if(!res.ok)throw new Error(`HTTP ${res.status}`);
    const data=await res.json();
    if(!Array.isArray(data.photos))throw new Error('Invalid photo catalogue');
    allPhotos=data.photos.filter(p=>p.published && p.rights?.reviewed && coords(p) && p.image && p.id);
    try {
      const placesRes=await fetch('./places.json',{cache:'no-store'});
      if(placesRes.ok){
        const data=await placesRes.json();if(!Array.isArray(data.places))throw Error('Invalid places catalogue');
        allPlaces=data.places.filter(p=>p.published && p.id && p.title && coords(p) && Number.isInteger(p.year_start) && (p.year_end==null || (Number.isInteger(p.year_end) && p.year_end>=p.year_start))).map(p=>({...p,kind:'place'}));
      }else if(placesRes.status!==404){throw Error('Could not load places');}
    }catch(error){
      allPlaces=[];mapError.dataset.source='places';mapError.textContent='Could not load places. Photographs are still available.';mapError.hidden=false;console.error('Places:',error);
    }
    setupTimeline();
    updateTimeControls();
    updateFilter();
  } catch(err){
    ui.empty.hidden=true;
    mapError.dataset.source='catalogue';
    mapError.textContent='Could not open the photograph catalogue. Reload or check photos.json.';
    mapError.hidden=false;
    console.error('Photo catalogue:',err);
  }
}
loadPhotos();
