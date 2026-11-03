"""End-to-end editor protection, place saving/export, and public time filtering."""
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import zipfile
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as d:
    with zipfile.ZipFile(ROOT/'downloads/Tasmania-Photo-Manager.zip') as z:z.extractall(d)
    base=Path(d)/'Tasmania-Photo-Manager'
    spec=importlib.util.spec_from_file_location('browser_places',base/'photo_manager.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.initialise_collection()
    original=m.load_catalogue()['photos'];point=original[0].get('camera') or original[0]['subject']
    server=m.ThreadingHTTPServer(('127.0.0.1',0),m.Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    url=f'http://127.0.0.1:{server.server_port}'
    try:
        with sync_playwright() as p:
            proxy={'server':os.environ['HTTPS_PROXY'],'bypass':'127.0.0.1,localhost'} if os.environ.get('HTTPS_PROXY') else None
            b=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,proxy=proxy,args=['--no-sandbox','--enable-unsafe-swiftshader'])
            try:
                page=b.new_page(viewport={'width':1440,'height':900});page.set_default_timeout(20000)
                errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                editor=(base/'editor.js').read_text()+'\nwindow.entryTest=()=>({map,mapReady,currentId,pendingImage,entryMode});'
                page.route('**/editor.js?v=*',lambda r:r.fulfill(body=editor,content_type='text/javascript'))
                page.goto(url+'/editor.html')
                page.wait_for_function('window.entryTest && entryTest().mapReady && document.querySelectorAll(".photo-item").length>0',timeout=45000)
                page.locator('#image-input').set_input_files(str(base/'tasmania-through-time'/original[0]['image']))
                page.locator('#title').fill('Unsaved new photograph')
                page.locator('#description').fill('Keep this description')
                page.evaluate('(c)=>entryTest().map.jumpTo({center:[c.lng,c.lat],zoom:15})',point)
                page.wait_for_timeout(100)
                def click_location():
                    xy=page.evaluate('(c)=>{const map=entryTest().map,p=map.project([c.lng,c.lat]),r=map.getContainer().getBoundingClientRect();return [r.x+p.x,r.y+p.y]}',point)
                    page.mouse.click(*xy)
                for _ in range(2):
                    click_location()
                    assert page.locator('#title').input_value()=='Unsaved new photograph'
                    assert page.locator('#description').input_value()=='Keep this description'
                    assert page.evaluate('entryTest().currentId===null && entryTest().pendingImage!==null')
                    assert abs(float(page.locator('#camera-lat').input_value())-point['lat'])<.00003
                    page.wait_for_timeout(400)
                page.locator('#published').uncheck();page.locator('#save-button').click()
                page.wait_for_function('entryTest().currentId!==null')
                assert m.load_catalogue()['photos'][:-1]==original
                assert json.loads(m.PUBLIC_CATALOGUE.read_text())['photos']==original
                page.locator('#new-place-button').click();page.locator('#place-title').fill('Test historical building')
                click_location()
                assert page.locator('#place-title').input_value()=='Test historical building'
                assert page.evaluate('entryTest().entryMode')=='place'
                page.locator('#place-lat').fill(str(point['lat']));page.locator('#place-lng').fill(str(point['lng']))
                page.locator('#place-year-start').fill('1880');page.locator('#place-year-end').fill('1945')
                page.locator('#place-description').fill('A test building with a known lifespan.')
                page.locator('#place-save').click()
                page.wait_for_function('document.getElementById("place-heading").textContent==="Edit place"')
                with zipfile.ZipFile(io.BytesIO(m.website_update())) as z:
                    self_places=json.loads(z.read('tasmania-through-time/places.json'))['places']
                    assert len(self_places)==1 and self_places[0]['year_start']==1880
                    assert json.loads(z.read('tasmania-through-time/photos.json'))['photos']==original
                public=(base/'tasmania-through-time/app.js').read_text()+'\nwindow.placesTest=()=>({map,markers,groups});'
                page.route('**/app.js?v=*',lambda r:r.fulfill(body=public,content_type='text/javascript'))
                page.goto(url+'/tasmania-through-time/')
                page.wait_for_function('window.placesTest && !document.getElementById("year-slider").disabled',timeout=45000)
                def year(value):
                    page.locator('#year-slider').evaluate('(el,n)=>{el.value=n;el.dispatchEvent(new Event("input",{bubbles:true}));}',value)
                for value,expected in ((1879,0),(1880,1),(1945,1),(1946,0)):
                    year(value)
                    assert page.locator('.place-marker').count()==expected,(value,expected)
                page.locator('#year-slider').focus();page.keyboard.press('Home')
                page.evaluate('(c)=>placesTest().map.jumpTo({center:[c.lng,c.lat],zoom:15})',point);page.wait_for_timeout(100)
                index=page.evaluate('(c)=>placesTest().groups.findIndex(g=>Math.abs(g.coord[0]-c.lng)<.00003 && Math.abs(g.coord[1]-c.lat)<.00003)',point)
                assert index>=0
                # At identical coordinates the shared dot cycles entries rather than hiding either.
                for _ in range(4):
                    page.locator('.photo-marker').nth(index).focus();page.keyboard.press('Enter')
                    if page.locator('#photo-title').inner_text()=='Test historical building':break
                assert page.locator('#photo-title').inner_text()=='Test historical building'
                assert page.locator('#photo-image-wrap').is_hidden()
                assert page.locator('#photo-date').inner_text()=='1880–1945'
                before=page.evaluate('placesTest().map.getCenter().toArray().concat(placesTest().map.getZoom())')
                page.locator('.photo-marker').nth(index).focus();page.keyboard.press('Enter')
                assert page.locator('#photo-image-wrap').is_visible()
                assert page.locator('#rights-details').is_visible()
                assert page.evaluate('placesTest().map.getCenter().toArray().concat(placesTest().map.getZoom())')==before
                # An open-ended place continues to appear after its construction year.
                ongoing=dict(self_places[0],year_end=None)
                response=page.request.post(url+'/api/place/save',data=ongoing)
                assert response.ok
                page.reload();page.wait_for_function('window.placesTest && !document.getElementById("year-slider").disabled')
                year(2026);assert page.locator('.place-marker').count()==1
                year(1879);assert page.locator('.place-marker').count()==0
                # A failed optional places file must never disable the existing photos.
                page.route('**/places.json',lambda r:r.fulfill(status=500,body='unavailable'))
                page.reload();page.wait_for_function('window.placesTest && !document.getElementById("year-slider").disabled')
                assert page.locator('.photo-marker').count()>0
                assert 'Photographs are still available' in page.locator('#error-state').inner_text()
                assert not errors,errors
                print('PASS repeated clicks at an existing marker preserve unsaved photo/image; place save/export; dates before/from/until/after; shared-location cycling and place details')
            finally:b.close()
    finally:server.shutdown();server.server_close()
