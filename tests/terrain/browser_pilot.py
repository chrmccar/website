"""Browser delivery/calibration proof; use TERRAIN_KIND=list for real built data."""
import json
import io
import math
from PIL import Image
import os
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
source=(ROOT/'pilots/terrain/pilot.js').read_text()+'\nwindow.terrainPilot=()=>({map,manifest,hasCoverage,viewportFov,actualCamera,applyView});'
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,
        proxy={'server':os.environ['HTTPS_PROXY'],'bypass':'127.0.0.1,localhost'},args=['--no-sandbox','--enable-unsafe-swiftshader'])
    try:
        page=browser.new_page(viewport={'width':1440,'height':900});page.set_default_timeout(30000)
        errors=[];responses=[]
        page.on('pageerror',lambda err:errors.append(str(err)))
        page.on('response',lambda r:responses.append((r.url,r.status)))
        page.route('**/pilot.js',lambda route:route.fulfill(body=source,content_type='text/javascript'))
        page.goto('http://127.0.0.1:8766/pilots/terrain/')
        page.wait_for_function('window.terrainPilot && terrainPilot().map && terrainPilot().map.getTerrain()',timeout=45000)
        page.wait_for_function('terrainPilot().map.loaded()',timeout=45000)
        result=page.evaluate('''()=>{const {map}=terrainPilot();return {terrain:map.getTerrain(),elevation:map.queryTerrainElevation(map.getCenter()),sources:map.getStyle().sources,status:document.getElementById('error').textContent}}''')
        print('PNG terrain:',json.dumps({'terrain':result['terrain'],'elevation':result['elevation'],'encoding':result['sources']['terrain']['encoding']}),flush=True)
        assert result['terrain']['exaggeration']==1
        assert result['elevation']>200,result
        expected_kind=os.environ.get('TERRAIN_KIND','synthetic-test')
        assert page.evaluate('terrainPilot().manifest.kind')==expected_kind
        assert ('SYNTHETIC TEST DATA' in page.locator('#dataset-status').inner_text())==(expected_kind=='synthetic-test')
        assert result['sources']['terrain']['encoding']=='terrarium'
        assert all('openfreemap' not in url and 'mapterhorn' not in url for url,status in responses)
        page.screenshot(path='/workspace/scratch/terrain-png.png')
        first=result['elevation']
        page.locator('#delivery').select_option('pmtiles')
        page.wait_for_function('terrainPilot().map.getSource("terrain").url?.startsWith("pmtiles://")')
        page.wait_for_function('terrainPilot().map.loaded()',timeout=45000)
        elevation=page.evaluate('terrainPilot().map.queryTerrainElevation(terrainPilot().map.getCenter())')
        assert abs(elevation-first)<1,(first,elevation)
        assert any('.pmtiles' in url and status==206 for url,status in responses)
        assert not page.locator('#error').is_visible(),page.locator('#error').inner_text()
        print(f'PASS true-scale {expected_kind} 3D terrain, local PNG/PMTiles equivalence, real 206 requests, no external terrain sources')
        # A locally selected wide photograph stays letterboxed and uses photo-vertical FOV.
        page.get_by_text('Align photograph',exact=True).click()
        buffer=io.BytesIO();Image.new('RGB',(1200,400),'white').save(buffer,format='PNG')
        page.locator('#photo').set_input_files({'name':'test.png','mimeType':'image/png','buffer':buffer.getvalue()})
        page.wait_for_selector('#overlay',state='visible')
        page.locator('#opacity').evaluate('(el)=>{el.value=25;el.dispatchEvent(new Event("input",{bubbles:true}));}')
        assert page.locator('#overlay').evaluate('(img)=>getComputedStyle(img).opacity')=='0.25'
        page.locator('#apply').click()
        assert not page.locator('#error').is_visible(),page.locator('#error').inner_text()
        size=page.locator('#view').bounding_box();frame_height=min(size['width']/3,size['height'])
        expected=2*math.atan(math.tan(math.radians(45/2))*size['height']/frame_height)*180/math.pi
        assert abs(page.evaluate('terrainPilot().map.getVerticalFieldOfView()')-expected)<.1
        actual=page.evaluate('''()=>{const {map,actualCamera}=terrainPilot();const tr=map._camera.transform,p=tr.getCameraLngLat();return {calculated:actualCamera(),drawn:{lng:p.lng,lat:p.lat,alt:tr.getCameraAltitude()}}}''')
        assert abs(actual['calculated']['lat']-actual['drawn']['lat'])<1e-8,actual
        assert abs(actual['calculated']['lng']-actual['drawn']['lng'])<1e-8,actual
        assert abs(actual['calculated']['elevation_m']-actual['drawn']['alt'])<.001,actual
        before=page.evaluate('terrainPilot().actualCamera()')
        page.set_viewport_size({'width':1200,'height':800})
        page.wait_for_timeout(250)
        after=page.evaluate('terrainPilot().actualCamera()')
        assert abs(before['lat']-after['lat'])<1e-6,(before,after)
        assert abs(before['elevation_m']-after['elevation_m'])<.5,(before,after)
        page.locator('#reset').click()
        assert page.evaluate('terrainPilot().map.getPitch()')==0
        page.set_viewport_size({'width':390,'height':844})
        page.wait_for_timeout(100)
        assert page.evaluate('document.documentElement.scrollWidth')==390
        assert not errors,errors
        print('PASS local photo opacity, explicit vertical FOV, camera apply/reset and mobile layout')
    finally:browser.close()
