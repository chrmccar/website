"""Optional integration check: serve the repo on port 8000; requires Playwright/Chromium."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
photo = json.loads((ROOT / 'tasmania-through-time/photos.json').read_text())['photos'][0]
fixtures = []
for i, (start, end) in enumerate([(1900,1900),(1901,1901),(1900,1905),(1910,1910),(None,None)]):
    fixtures.append(dict(photo, id=f'fixture-{i}', title=f'Test photo {i}', year_start=start,
                         year_end=end, date_display='', camera=None,
                         subject={'lat':-42+i*.05,'lng':147+i*.05}))

with sync_playwright() as p:
    proxy = {'server':os.environ['HTTPS_PROXY'],'bypass':'127.0.0.1,localhost'} if os.environ.get('HTTPS_PROXY') else None
    browser = p.chromium.launch(executable_path='/usr/bin/chromium', headless=True, proxy=proxy,
                               args=['--no-sandbox','--enable-unsafe-swiftshader'])
    try:
        page = browser.new_page(viewport={'width':1440,'height':900})
        page.set_default_timeout(15000)
        errors=[]
        page.on('pageerror', lambda err: errors.append(str(err)))
        page.route('**/photos.json',lambda route:route.fulfill(json={'version':1,'photos':fixtures}))
        page.goto('http://127.0.0.1:8000/tasmania-through-time/')
        page.wait_for_selector('.photo-marker')
        def count(n):
            page.wait_for_function('(n)=>document.getElementById("photo-count").textContent.startsWith(`${n} photograph`)',arg=n)
            assert page.locator('.photo-marker').count()==n
        def year(selector,value):
            page.locator(selector).evaluate('(el,value)=>{el.value=value;el.dispatchEvent(new Event("input",{bubbles:true}));}',str(value))
        count(5)
        assert page.locator('#time-label').inner_text()=='All time'
        assert not page.locator('#range-mode').is_checked()
        assert not page.locator('#end-year-row').is_visible()
        year('#year-slider',1900);count(2)
        assert page.locator('#time-label').inner_text()=='1900'
        page.locator('#year-slider').focus();page.keyboard.press('ArrowRight');count(2)
        assert page.locator('#time-label').inner_text()=='1901'
        year('#year-slider',1906);count(0)
        assert page.locator('#empty-state').is_visible()
        year('#year-slider',1900);page.locator('#range-mode').check()
        year('#end-year-slider',1901);count(3)
        assert page.locator('#time-label').inner_text()=='1900–1901'
        year('#end-year-slider',1899);count(0)
        assert page.locator('#year-slider').input_value()=='1899'
        year('#year-slider',1910);count(1)
        assert page.locator('#end-year-slider').input_value()=='1910'
        page.locator('#all-time').click();count(5)
        assert not page.locator('#range-mode').is_checked()
        assert page.locator('#time-label').inner_text()=='All time'
        year('#year-slider',1900)
        page.locator('.photo-marker').first.click()
        assert page.locator('#photo-panel').get_attribute('aria-hidden')=='false'
        page.locator('#year-slider').focus();year('#year-slider',1911);count(0)
        assert page.locator('#year-slider').evaluate('(el)=>el===document.activeElement')
        assert page.locator('#photo-panel').get_attribute('aria-hidden')=='true'
        page.locator('#all-time').click()
        # Real style and tile requests must succeed, not just mocked HTML.
        page.wait_for_function('()=>!!document.querySelector(".maplibregl-canvas")')
        page.wait_for_timeout(2500)
        assert not page.locator('#error-state').is_visible(),page.locator('#error-state').inner_text()
        page.screenshot(path='/workspace/scratch/timeline-desktop.png')
        for width in (390,320):
            page.set_viewport_size({'width':width,'height':844})
            page.locator('#range-mode').check()
            box=page.locator('.timeline').bounding_box()
            assert box['x']>=0 and box['x']+box['width']<=width
            assert page.evaluate('document.documentElement.scrollWidth')==width
            assert page.locator('#end-year-slider').is_visible()
            page.wait_for_timeout(100)
            assert page.locator('.maplibregl-ctrl-top-right').bounding_box()['y'] >= box['y']+box['height']
            page.screenshot(path=f'/workspace/scratch/timeline-mobile-{width}.png')
            page.locator('#all-time').click()
        page.route('**/photos.json',lambda route:route.fulfill(json={'version':1,'photos':[]}))
        page.reload();page.wait_for_selector('#empty-state',state='visible');count(0)
        assert page.locator('#time-label').inner_text()=='All time'
        assert not errors,errors
        print('PASS all-time default including undated, year steps, inclusive intervals/ranges, crossing handles, reset, empty results/collection, focus and 320/390px layouts')
    finally:
        browser.close()
