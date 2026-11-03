"""Check real marker projection and camera stability. Serve the repo on port 8000 first."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
photos = json.loads((ROOT/'tasmania-through-time/photos.json').read_text())['photos']
coords = [p.get('camera') or p['subject'] for p in photos]
source = (ROOT/'tasmania-through-time/app.js').read_text()
# The extra accessor exists only in this test response, never in the published app.
source += '\nwindow.markerTestState=()=>({map,markers});'

with sync_playwright() as p:
    proxy = {'server':os.environ['HTTPS_PROXY'],'bypass':'127.0.0.1,localhost'} if os.environ.get('HTTPS_PROXY') else None
    browser = p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,proxy=proxy,
                               args=['--no-sandbox','--enable-unsafe-swiftshader'])
    try:
        page=browser.new_page(viewport={'width':1440,'height':900})
        page.set_default_timeout(15000)
        errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.route('**/app.js?v=*',lambda route:route.fulfill(body=source,content_type='text/javascript'))
        page.goto('http://127.0.0.1:8000/tasmania-through-time/')
        page.wait_for_function('window.markerTestState && !document.getElementById("year-slider").disabled',timeout=45000)
        page.wait_for_function('markerTestState().map.isStyleLoaded()',timeout=45000)
        def camera():
            return page.evaluate('()=>{const m=markerTestState().map;return [m.getCenter().toArray(),m.getZoom(),m.getPadding(),m.getBearing(),m.getPitch()]}')
        def check_positions():
            measurements=page.evaluate('''()=>{const {map,markers}=markerTestState(),box=map.getContainer().getBoundingClientRect();
              return markers.map(marker=>{const el=marker.getElement(),point=map.project(marker.getLngLat()),r=el.getBoundingClientRect(),pin=el.querySelector('.pin'),style=getComputedStyle(pin);
                return {coord:marker.getLngLat().toArray(),position:getComputedStyle(el).position,
                  dx:r.x+r.width/2-box.x-point.x,dy:r.y+r.height/2-box.y-point.y,
                  width:pin.getBoundingClientRect().width,height:pin.getBoundingClientRect().height,
                  color:style.backgroundColor,border:style.borderWidth,shadow:style.boxShadow,
                  children:el.children.length};});}''')
            self_coords={(c['lng'],c['lat']) for c in coords}
            assert len(measurements)==len(self_coords)
            for m in measurements:
                assert tuple(m['coord']) in self_coords
                assert m['position']=='absolute',m
                assert abs(m['dx'])<1 and abs(m['dy'])<1,m
                assert m['width']==m['height']==10,m
                assert m['border']=='0px' and m['shadow']=='none' and m['children']==1,m
            assert len({m['color'] for m in measurements})==1
        for width in (1440,390):
            page.set_viewport_size({'width':width,'height':900})
            for zoom in (4,7,10,14):
                page.evaluate('(zoom)=>markerTestState().map.jumpTo({center:[147.17,-41.25],zoom})',zoom)
                page.wait_for_timeout(100)
                check_positions()
            page.evaluate('markerTestState().map.panBy([100,-80],{duration:0})')
            page.wait_for_timeout(100);check_positions()
            page.get_by_role('button',name='Zoom in',exact=True).click()
            page.wait_for_function('!markerTestState().map.isMoving()')
            check_positions()
            first=coords[0]
            page.evaluate('(c)=>markerTestState().map.jumpTo({center:[c.lng,c.lat],zoom:12})',first)
            page.wait_for_timeout(100)
            before=camera()
            page.locator('.photo-marker').first.click()
            page.wait_for_selector('.photo-panel.open')
            page.wait_for_timeout(500)
            assert camera()==before,'Opening a photograph moved or zoomed the map'
            check_positions()
            assert page.locator('#photo-title').inner_text()==photos[0]['title']
            page.locator('#close-panel').click()
            page.wait_for_timeout(500)
            assert camera()==before,'Closing a photograph moved or zoomed the map'
            check_positions()
            page.screenshot(path=f'/workspace/scratch/fixed-dots-{width}.png')
        assert not errors,errors
        print(f'PASS {len(photos)} real photographs: exact coordinates at zooms 4/7/10/14, pan, manual zoom, identical solid dots, and unchanged camera on photo open/close at desktop/mobile widths')
    finally:
        browser.close()
