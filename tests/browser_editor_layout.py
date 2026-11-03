"""Exercise the actual downloadable editor with a large collection and real wheel scrolling."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import threading
import zipfile
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as d:
    with zipfile.ZipFile(ROOT/'downloads/Tasmania-Photo-Manager.zip') as z:
        z.extractall(d)
    base=Path(d)/'Tasmania-Photo-Manager'
    spec=importlib.util.spec_from_file_location('layout_manager',base/'photo_manager.py')
    manager=importlib.util.module_from_spec(spec);spec.loader.exec_module(manager)
    manager.initialise_collection()
    photo=json.loads((base/'tasmania-through-time/photos.json').read_text())['photos'][0]
    fixtures=[dict(photo,id=f'layout-{i}',title=f'Photograph {i}: A long historical photograph title for testing the collection panel') for i in range(200)]
    server=manager.ThreadingHTTPServer(('127.0.0.1',0),manager.Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as p:
            proxy={'server':os.environ['HTTPS_PROXY'],'bypass':'127.0.0.1,localhost'} if os.environ.get('HTTPS_PROXY') else None
            browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,proxy=proxy,
                                     args=['--no-sandbox','--enable-unsafe-swiftshader'])
            try:
                page=browser.new_page(viewport={'width':1920,'height':1080})
                errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                page.route('**/api/photos',lambda route:route.fulfill(json={'version':1,'photos':fixtures}))
                page.goto(f'http://127.0.0.1:{server.server_port}/editor.html')
                page.wait_for_function('document.querySelectorAll(".photo-item").length===200',timeout=45000)
                for width,height in ((1920,1080),(1440,900),(1024,768),(900,600),(1280,480)):
                    page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(100)
                    assert page.evaluate('document.documentElement.scrollHeight')<=height+1
                    assert page.evaluate('window.scrollY')==0
                    library=page.locator('.library-list')
                    assert library.evaluate('(el)=>el.scrollHeight>el.clientHeight')
                    box=page.locator('#editor-map').bounding_box()
                    assert box['height']>100 and box['y']+box['height']<=height
                    assert page.locator('#save-button').is_visible()
                    library.evaluate('(el)=>el.scrollTop=0')
                    library.hover();page.mouse.wheel(0,600)
                    page.wait_for_function('document.querySelector(".library-list").scrollTop>0')
                    assert page.locator('#editor-map').bounding_box()==box
                    assert page.evaluate('window.scrollY')==0
                    library_scroll=library.evaluate('(el)=>el.scrollTop')
                    form=page.locator('.form-content:visible')
                    assert form.evaluate('(el)=>el.scrollHeight>el.clientHeight')
                    form.evaluate('(el)=>el.scrollTop=0');form.hover();page.mouse.wheel(0,500)
                    page.wait_for_function('document.querySelector(".form-content").scrollTop>0')
                    assert library.evaluate('(el)=>el.scrollTop')==library_scroll
                    assert page.locator('#editor-map').bounding_box()==box
                    assert page.evaluate('window.scrollY')==0
                    library.evaluate('(el)=>el.scrollTop=el.scrollHeight')
                    page.locator('.photo-item').last.click()
                    assert page.locator('#title').input_value()==fixtures[-1]['title']
                    assert page.locator('#save-button').is_visible()
                    assert page.evaluate('document.documentElement.scrollHeight')<=height+1
                    page.screenshot(path=f'/workspace/scratch/editor-scroll-{width}.png')
                # Narrow layouts retain the existing horizontal collection strip.
                page.set_viewport_size({'width':820,'height':900});page.wait_for_timeout(100)
                library=page.locator('.library-list')
                assert library.evaluate('(el)=>el.scrollWidth>el.clientWidth')
                assert page.locator('.library').bounding_box()['height']<350
                assert not errors,errors
                print('PASS 200 entries: fixed desktop page, independent list/form wheel scrolling, stationary map, accessible last entry/save button, short-height windows and narrow layout')
            finally:
                browser.close()
    finally:
        server.shutdown();server.server_close()
