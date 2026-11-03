"""Regression: a cached pre-header script must not break the current page.
Requires Playwright/Chromium; starts its own local server and uses the real catalogue.
"""
import os
import json
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import threading
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PHOTOS = json.loads((ROOT/'tasmania-through-time/photos.json').read_text())['photos']
PHOTO_COUNT = len({(c['lng'], c['lat']) for p in PHOTOS for c in [p.get('camera') or p['subject']]})
PHOTO_YEAR = next((p['year_start'] for p in PHOTOS if isinstance(p.get('year_start'), int)), None)
legacy_requests = []

class UpgradeHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, *args):
        pass

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == '/prime-cache':
            body = b'''<link rel="stylesheet" href="/tasmania-through-time/style.css">
              <input id="range-mode" type="checkbox">
              <script type="module" src="/tasmania-through-time/app.js"></script>'''
            mime = 'text/html'
        elif not url.query and url.path in ('/tasmania-through-time/app.js', '/tasmania-through-time/style.css'):
            legacy_requests.append(url.path)
            if url.path.endswith('.js'):
                # This is the removed-control dependency from the previous header.
                body = b"document.getElementById('range-mode').addEventListener('change',()=>{});window.legacyLoaded=true;"
                mime = 'text/javascript'
            else:
                body = b'.header-timeline{display:none}'
                mime = 'text/css'
        else:
            return super().do_GET()
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'public, max-age=3600')
        self.end_headers()
        self.wfile.write(body)

server = ThreadingHTTPServer(('127.0.0.1', 0), UpgradeHandler)
threading.Thread(target=server.serve_forever, daemon=True).start()
base = f'http://127.0.0.1:{server.server_port}'
try:
    with sync_playwright() as p:
        proxy = {'server':os.environ['HTTPS_PROXY'],'bypass':'127.0.0.1,localhost'} if os.environ.get('HTTPS_PROXY') else None
        browser = p.chromium.launch(executable_path='/usr/bin/chromium', headless=True,
                    proxy=proxy, args=['--no-sandbox','--enable-unsafe-swiftshader'])
        try:
            page = browser.new_page()
            errors=[]
            page.on('pageerror',lambda err:errors.append(str(err)))
            page.goto(base+'/prime-cache')
            page.wait_for_function('window.legacyLoaded===true')
            assert len(legacy_requests)==2
            page.goto(base+'/tasmania-through-time/')
            page.wait_for_selector('.photo-marker',timeout=45000)
            assert len(legacy_requests)==2, 'New HTML requested unversioned cached assets'
            assert not page.locator('#year-slider').is_disabled()
            assert page.locator('#year-slider').is_visible()
            assert page.locator('#time-label').inner_text()=='All time'
            assert page.locator('.photo-marker').count()==PHOTO_COUNT
            # Actual pointer interaction must change the year and filter the photo.
            slider=page.locator('#year-slider').bounding_box()
            page.mouse.click(slider['x']+slider['width']-1,slider['y']+slider['height']/2)
            assert page.locator('#time-label').inner_text()==page.locator('#year-slider').get_attribute('max')
            assert page.locator('.photo-marker').count()==0
            page.locator('#year-slider').focus();page.keyboard.press('Home')
            assert page.locator('#time-label').inner_text()=='All time'
            assert page.locator('.photo-marker').count()==PHOTO_COUNT
            if PHOTO_YEAR is not None:
                page.locator('#year-slider').evaluate('(el,year)=>{el.value=year;el.dispatchEvent(new Event("input",{bubbles:true}));}',PHOTO_YEAR)
                assert page.locator('#time-label').inner_text()==str(PHOTO_YEAR)
            page.locator('.photo-marker').first.focus();page.keyboard.press('Enter')
            page.wait_for_function('document.getElementById("photo-image").naturalWidth>0')
            assert page.locator('#photo-title').inner_text()
            assert not errors,errors
            print('PASS cached old JS/CSS upgrade, pointer/keyboard slider, All time/year filtering and actual public photograph')
        finally:
            browser.close()
finally:
    server.shutdown()
    server.server_close()
