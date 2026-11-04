"""Install the real terrain update over an existing collection; exercise private/public boundaries.
Run after building downloads/Photo-Manager-Terrain-Update.zip. No user collection is read.
"""
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import tempfile
import threading
from http.server import ThreadingHTTPServer
import zipfile
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix='alignment-install-') as scratch:
    with zipfile.ZipFile(ROOT/'downloads/Tasmania-Photo-Manager.zip') as z:z.extractall(scratch)
    base=Path(scratch)/'Tasmania-Photo-Manager'
    spec=importlib.util.spec_from_file_location('install_alignment',base/'photo_manager.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.initialise_collection()
    before=m.CATALOGUE.read_bytes();photos=m.load_catalogue()['photos']
    with zipfile.ZipFile(ROOT/'downloads/Photo-Manager-Terrain-Update.zip') as z:
        assert not any('LOCAL_COLLECTION' in n or 'photo-assets/' in n or '/images/' in n for n in z.namelist())
        z.extractall(base)
    assert m.CATALOGUE.read_bytes()==before
    manifest=json.loads((base/'terrain/data/manifest.json').read_text())
    assert manifest['kind']=='list'
    def covered(p):
        if not p.get('camera'):return False
        lng=p['camera']['lng'];lat=p['camera']['lat'];z=manifest['maxzoom'];n=2**z
        x=math.floor((lng+180)/360*n);y=math.floor((1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*n)
        return f'{z}/{x}/{y}' in manifest['tiles']
    photo=next(p for p in photos if covered(p));original=json.loads(json.dumps(photo));photo_id=photo['id']
    source=(base/'terrain/pilot.js').read_text()+'\nwindow.terrainPilot=()=>({map,manifest,actualCamera,hasCoverage});'
    server=ThreadingHTTPServer(('127.0.0.1',8765),m.Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,proxy={'server':os.environ['HTTPS_PROXY'],'bypass':'127.0.0.1,localhost'},args=['--no-sandbox','--enable-unsafe-swiftshader'])
            try:
                page=browser.new_page(viewport={'width':1440,'height':900});page.set_default_timeout(45000)
                errors=[];terrain_responses=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.on('response',lambda r:terrain_responses.append(r.url) if '/tiles/' in r.url else None)
                page.route('**/pilot.js',lambda route:route.fulfill(body=source,content_type='text/javascript'))
                page.goto(f'http://127.0.0.1:8765/terrain/?photo={photo_id}')
                page.wait_for_selector('#overlay',state='visible');page.wait_for_function('terrainPilot().map.loaded()')
                assert 'LIST 25 m' in page.locator('#dataset-status').inner_text()
                assert page.evaluate('terrainPilot().map.getTerrain().exaggeration')==1
                assert page.evaluate('terrainPilot().map.terrain.tileManager.getRenderableTiles().every(t=>t.tileID.canonical.z>=terrainPilot().manifest.maxzoom)')
                assert all(u.startswith('http://127.0.0.1:8765/terrain/data/') for u in terrain_responses)
                # Independent real DEM sample at the known Lilydale camera coordinates.
                eye=photo['camera']
                page.wait_for_function('(p)=>terrainPilot().map.queryTerrainElevation([p.lng,p.lat])>0',arg=eye)
                ground=page.evaluate('(p)=>terrainPilot().map.queryTerrainElevation([p.lng,p.lat])',eye)
                assert ground is not None and 0<ground<1500,ground
                page.locator('#use-camera').click();page.locator('#apply').click()
                assert not page.locator('#error').is_visible(),page.locator('#error').inner_text()
                standing=page.evaluate('terrainPilot().actualCamera()')
                assert abs(standing['elevation_m']-ground-1.7)<.5,(standing,ground)
                page.locator('#altitude').fill(str(ground+300));page.locator('#bearing').fill('35');page.locator('#pitch').fill('80')
                page.locator('#apply').click()
                assert not page.locator('#error').is_visible(),page.locator('#error').inner_text()
                real=page.evaluate('terrainPilot().actualCamera()')
                assert abs(real['lng']-eye['lng'])<1e-5,(real,eye)
                assert abs(real['lat']-eye['lat'])<1e-5,(real,eye)
                assert abs(real['elevation_m']-(ground+300))<.5,(real,ground)
                page.locator('#opacity').fill('30');page.locator('#notes').fill('PRIVATE browser alignment notes')
                page.locator('#save-draft').click();page.wait_for_function('document.querySelector("#save-status").textContent.includes("draft saved privately")')
                saved=next(p for p in m.load_catalogue()['photos'] if p['id']==photo_id)
                assert saved['camera']==original['camera'] and saved['subject']==original['subject']
                exported=json.loads(m.PUBLIC_CATALOGUE.read_text());assert 'PRIVATE' not in json.dumps(exported)
                assert 'camera_pose' not in next(p for p in exported['photos'] if p['id']==photo_id)
                assert list((base/'alignment-backups').glob('*.json'))
                page.reload();page.wait_for_selector('#overlay',state='visible');page.wait_for_function('terrainPilot().map.loaded()')
                assert page.locator('#notes').input_value()=='PRIVATE browser alignment notes'
                assert abs(float(page.locator('#altitude').input_value())-ground-300)<.5
                page.locator('#approve').check();page.locator('#accept').click();page.wait_for_function('document.querySelector("#save-status").textContent.includes("draft accepted")')
                with zipfile.ZipFile(io.BytesIO(m.website_update())) as archive:
                    public=json.loads(archive.read('tasmania-through-time/photos.json'))
                    assert 'PRIVATE' not in json.dumps(public)
                    assert not any('alignment' in name or 'terrain' in name for name in archive.namelist())
                    approved=next(p for p in public['photos'] if p['id']==photo_id)
                    assert approved['camera_pose']['bearing']==35
                    assert approved['camera']==original['camera']
                page.locator('#apply').click();page.screenshot(path='/workspace/scratch/terrain-real-alignment.png')
                page.locator('#withdraw').click();page.wait_for_function('document.querySelector("#save-status").textContent.includes("Alignment is private")')
                assert 'camera_pose' not in next(p for p in json.loads(m.PUBLIC_CATALOGUE.read_text())['photos'] if p['id']==photo_id)
                assert not errors,errors
                print('PASS real LIST terrain, lossless update install, correct rendered eye, private save/reopen, approval/export exclusion, withdrawal, snapshots, unchanged old coordinates',flush=True)
                print(json.dumps({'photo':photo_id,'ground_m':ground,'eye':real,'png_tiles_requested':len(set(terrain_responses))}),flush=True)
            finally:browser.close()
    finally:server.shutdown();server.server_close();thread.join()
