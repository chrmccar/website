import * as maplibregl from 'https://unpkg.com/maplibre-gl@6.16.0/dist/maplibre-gl.mjs';
const $=id=>document.getElementById(id);
let catalogue=[],currentId=null,pendingImage=null,placement='camera',mapReady=false,previewUrl=null;
let placementMarkers=[],otherMarkers=[];
const form=$('photo-form'),saveMessage=$('save-message');
const map=new maplibregl.Map({container:'editor-map',style:'https://tiles.openfreemap.org/styles/positron',center:[146.55,-42.05],zoom:6.15,minZoom:4.4,maxZoom:18,attributionControl:false,dragRotate:false,touchPitch:false});
map.addControl(new maplibregl.NavigationControl({showCompass:false}),'top-right');
map.addControl(new maplibregl.AttributionControl({compact:true}),'bottom-right');
map.on('load',()=>{mapReady=true;refreshMap();});
map.on('error',e=>{if(/style|fetch/i.test(e?.error?.message||''))showMessage('The map tiles could not load; you can still enter coordinates manually.',true);});
const imageUrl=p=>(p.published?'/tasmania-through-time/images/':'/photo-assets/')+(p.image||'').split('/').pop();
const thumbUrl=p=>(p.published?'/tasmania-through-time/images/':'/photo-assets/')+(p.thumbnail||p.image||'').split('/').pop();
const value=id=>$(id).value.trim();
const set=(id,v)=>{$(id).value=v ?? '';};
const num=id=>value(id)===''?null:Number(value(id));
function showMessage(msg,isError=false){saveMessage.textContent=msg;saveMessage.classList.toggle('error',isError);}
function setStatus(text,live=false){$('draft-status').textContent=text;$('draft-status').classList.toggle('live',live);}
function setMode(mode){placement=mode;document.querySelectorAll('.mode').forEach(el=>el.classList.toggle('active',el.dataset.mode===mode));const messages={camera:'Camera mode: click where the photographer was standing.',subject:'Subject mode: click the place shown in the photograph.',direction:'Direction mode: click a landmark the camera was facing. Place the camera first.'};$('map-status').textContent=messages[mode];}
document.querySelectorAll('.mode').forEach(b=>b.addEventListener('click',()=>setMode(b.dataset.mode)));
function bearingDegrees(a,b){const r=Math.PI/180;const lat1=a[1]*r,lat2=b[1]*r,dlon=(b[0]-a[0])*r;return (Math.atan2(Math.sin(dlon)*Math.cos(lat2),Math.cos(lat1)*Math.sin(lat2)-Math.sin(lat1)*Math.cos(lat2)*Math.cos(dlon))*180/Math.PI+360)%360;}
map.on('click',event=>{
  const {lng,lat}=event.lngLat;
  if(placement==='direction'){
    if(num('camera-lat')===null||num('camera-lng')===null){showMessage('Set the camera position first, then choose direction.',true);return;}
    set('camera-bearing',Math.round(bearingDegrees([num('camera-lng'),num('camera-lat')],[lng,lat])));
    setMode('camera');
  }else if(placement==='camera'){
    set('camera-lat',lat.toFixed(6));set('camera-lng',lng.toFixed(6));
  }else{
    set('subject-lat',lat.toFixed(6));set('subject-lng',lng.toFixed(6));
  }
  showMessage('Location updated. Click Save photograph to keep your changes.');refreshMap();
});
function createPoint(lat,lng,type,bearing){
  if(lat==null||lng==null||!Number.isFinite(lat)||!Number.isFinite(lng))return;
  const el=document.createElement('div');el.className='editing-marker '+(type==='subject'?'subject':'');
  if(type==='camera'&&bearing!=null&&Number.isFinite(bearing)){
    const arrow=document.createElement('span');arrow.className='orientation';arrow.style.transform=`rotate(${bearing}deg)`;el.append(arrow);
  }
  placementMarkers.push(new maplibregl.Marker({element:el}).setLngLat([lng,lat]).addTo(map));
}
function refreshMap(){
  if(!mapReady)return;
  placementMarkers.forEach(m=>m.remove());placementMarkers=[];
  otherMarkers.forEach(m=>m.remove());otherMarkers=[];
  const lat=num('camera-lat'),lng=num('camera-lng');
  createPoint(lat,lng,'camera',num('camera-bearing'));
  createPoint(num('subject-lat'),num('subject-lng'),'subject');
  for(const p of catalogue){
    if(p.id===currentId)continue;
    const c=p.camera||p.subject;
    if(!c)continue;
    const el=document.createElement('div');el.className='other-marker';el.title=p.title;
    el.addEventListener('click',e=>{e.stopPropagation();editPhoto(p.id);});
    otherMarkers.push(new maplibregl.Marker({element:el}).setLngLat([c.lng,c.lat]).addTo(map));
  }
}
function locateForm(){
  const lat=num('camera-lat')??num('subject-lat');const lng=num('camera-lng')??num('subject-lng');
  if(lat!==null&&lng!==null)map.easeTo({center:[lng,lat],zoom:Math.max(10,map.getZoom()),duration:350});
}
for(const id of ['camera-lat','camera-lng','camera-bearing','subject-lat','subject-lng'])$(id).addEventListener('change',refreshMap);
function renderList(){
  $('library-count').textContent=`${catalogue.length} photo${catalogue.length===1?'':'s'}`;
  const list=$('library-list');list.replaceChildren();
  if(!catalogue.length){const el=document.createElement('div');el.className='library-empty';el.textContent='No photographs yet. Add your first image to get started.';list.append(el);return;}
  catalogue.forEach(p=>{
    const button=document.createElement('button');button.type='button';button.className=`photo-item${currentId===p.id?' active':''}`;
    const image=document.createElement('img');image.loading='lazy';image.src=thumbUrl(p);image.alt='';
    const info=document.createElement('span');const title=document.createElement('strong');title.textContent=p.title;
    const place=document.createElement('small');place.textContent=p.place||'Location not named';
    const status=document.createElement('small');status.className='state'+(p.published?'':' draft');status.textContent=p.published?'● Ready for website':'● Draft';
    info.append(title,place,status);button.append(image,info);button.addEventListener('click',()=>editPhoto(p.id));list.append(button);
  });
}
function setPreview(src){
  const img=$('image-preview'),placeholder=$('image-placeholder');
  if(src){img.src=src;img.hidden=false;placeholder.hidden=true;}
  else{img.removeAttribute('src');img.hidden=true;placeholder.hidden=false;}
}
function resetForNew(){
  currentId=null;pendingImage=null;form.reset();$('image-input').value='';$('published').checked=true;
  setPreview(null);$('form-heading').textContent='New photograph';$('delete-button').hidden=true;
  setStatus('Not saved');showMessage('');setMode('camera');renderList();refreshMap();
}
$('new-button').addEventListener('click',resetForNew);
function editPhoto(id){
  const p=catalogue.find(x=>x.id===id);if(!p)return;
  currentId=id;pendingImage=null;$('image-input').value='';
  for(const name of ['title','place','description','date-display'])set(name,p[name==='date-display'?'date_display':name]);
  set('year-start',p.year_start);set('year-end',p.year_end);set('image-type',p.image_type||'ground');
  set('camera-lat',p.camera?.lat);set('camera-lng',p.camera?.lng);set('camera-bearing',p.camera?.bearing);
  set('subject-lat',p.subject?.lat);set('subject-lng',p.subject?.lng);set('accuracy',p.location_accuracy||'estimated');
  const r=p.rights||{};
  for(const [id,key] of [['creator','creator'],['source','source'],['source-url','source_url'],['archive-id','archive_id'],['rights-status','status'],['rights-statement','statement'],['licence-url','licence_url'],['rights-notes','notes']])set(id,r[key]);
  $('reviewed').checked=!!r.reviewed;$('published').checked=!!p.published;
  setPreview(imageUrl(p));
  $('form-heading').textContent='Edit photograph';$('delete-button').hidden=false;
  setStatus(p.published?'Ready for website':'Draft',p.published);showMessage('');setMode('camera');renderList();refreshMap();locateForm();
}
async function loadPhotos(){
  try{
    const res=await fetch('/api/photos',{cache:'no-store'});if(!res.ok)throw Error('Could not read photo catalogue');
    const data=await res.json();catalogue=data.photos||[];renderList();refreshMap();
  }catch(e){showMessage(e.message,true);}
}
function updateImageFromFile(file){
  if(!file)return;
  if(!file.type.startsWith('image/')){showMessage('Please select an image file.',true);return;}
  if(file.size>60*1024*1024){showMessage('This image is too large to process. Please use one under 60 MB.',true);return;}
  pendingImage=file;
  if(previewUrl)URL.revokeObjectURL(previewUrl);
  previewUrl=URL.createObjectURL(file);setPreview(previewUrl);
  if(!value('title'))set('title',file.name.replace(/\.[^.]+$/,'').replace(/[_-]/g,' '));
  showMessage('Photograph selected. It will be optimised when you click Save.');
}
$('image-input').addEventListener('change',e=>updateImageFromFile(e.target.files[0]));
const drop=$('image-drop');
drop.addEventListener('dragover',e=>{e.preventDefault();drop.classList.add('dragging');});
drop.addEventListener('dragleave',()=>drop.classList.remove('dragging'));
drop.addEventListener('drop',e=>{e.preventDefault();drop.classList.remove('dragging');const file=e.dataTransfer.files[0];updateImageFromFile(file);});
function renderImage(file,maxDimension,quality){
  return new Promise((resolve,reject)=>{
    const url=URL.createObjectURL(file);const img=new Image();
    img.onload=()=>{
      try{
        const scale=Math.min(1,maxDimension/Math.max(img.naturalWidth,img.naturalHeight));
        const canvas=document.createElement('canvas');canvas.width=Math.max(1,Math.round(img.naturalWidth*scale));canvas.height=Math.max(1,Math.round(img.naturalHeight*scale));
        canvas.getContext('2d').drawImage(img,0,0,canvas.width,canvas.height);
        let data=canvas.toDataURL('image/webp',quality);
        if(!data.startsWith('data:image/webp'))data=canvas.toDataURL('image/jpeg',quality);
        resolve(data);
      }catch(e){reject(e);}finally{URL.revokeObjectURL(url);}
    };
    img.onerror=()=>{URL.revokeObjectURL(url);reject(Error('Unable to read this image. Convert it to JPG or PNG and retry.'));};
    img.src=url;
  });
}
function point(latId,lngId,withBearing=false){
  const lat=num(latId),lng=num(lngId);
  if(lat==null&&lng==null)return null;
  const obj={lat,lng};if(withBearing)obj.bearing=num('camera-bearing');return obj;
}
function payload(){
  const r={creator:value('creator'),source:value('source'),source_url:value('source-url'),archive_id:value('archive-id'),status:value('rights-status'),licence_url:value('licence-url'),statement:value('rights-statement'),notes:value('rights-notes'),reviewed:$('reviewed').checked};
  return {id:currentId,title:value('title'),description:value('description'),place:value('place'),date_display:value('date-display'),year_start:num('year-start'),year_end:num('year-end'),image_type:value('image-type'),camera:point('camera-lat','camera-lng',true),subject:point('subject-lat','subject-lng'),location_accuracy:value('accuracy'),rights:r,published:$('published').checked};
}
form.addEventListener('submit',async event=>{
  event.preventDefault();showMessage('');
  if(!value('title')){showMessage('Please enter a photograph title.',true);$('title').focus();return;}
  if(!pendingImage&&!currentId){showMessage('Choose a photograph first.',true);return;}
  if($('published').checked&&!$('reviewed').checked){showMessage('Tick the rights confirmation, or untick Show on public map to save a draft.',true);return;}
  if($('published').checked&&value('rights-status')==='not_verified'){showMessage('Choose the rights status before publishing, or save this as a draft.',true);return;}
  if($('published').checked&&!(point('camera-lat','camera-lng')||point('subject-lat','subject-lng'))){showMessage('Click the map to set a camera or subject location, or save as a draft.',true);return;}
  const button=$('save-button');button.disabled=true;button.textContent='Saving…';
  try{
    const data=payload();
    if(pendingImage){data.image_data=await renderImage(pendingImage,2200,.86);data.thumb_data=await renderImage(pendingImage,520,.79);}
    const res=await fetch('/api/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
    const response=await res.json();if(!res.ok)throw Error(response.error||'Could not save');
    catalogue=catalogue.filter(p=>p.id!==response.photo.id);catalogue.push(response.photo);catalogue.sort((a,b)=>a.title.localeCompare(b.title));
    pendingImage=null;currentId=response.photo.id;
    setPreview(imageUrl(response.photo)+'?v='+Date.now());
    $('image-input').value='';$('delete-button').hidden=false;$('form-heading').textContent='Edit photograph';
    setStatus(response.photo.published?'Ready for website':'Draft',response.photo.published);
    renderList();refreshMap();showMessage(response.photo.published?'Saved on this computer. Click Download website update, then upload the extracted folder to GitHub to update the live map.':'Draft saved locally. It will not appear on the public map.');
  }catch(e){showMessage(e.message,true);}
  finally{button.disabled=false;button.textContent='Save photograph';}
});
$('delete-button').addEventListener('click',async()=>{
  if(!currentId)return;
  const photo=catalogue.find(p=>p.id===currentId);
  if(!confirm(`Permanently delete "${photo?.title||'this photograph'}" and its website image files?`))return;
  try{
    const res=await fetch('/api/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:currentId})});
    const result=await res.json();if(!res.ok)throw Error(result.error||'Could not delete');
    catalogue=catalogue.filter(p=>p.id!==currentId);resetForNew();showMessage('Photograph deleted locally. Download and upload the website update to remove its map marker. Earlier public image URLs and Git history may remain accessible.');
  }catch(e){showMessage(e.message,true);}
});
resetForNew();loadPhotos();
