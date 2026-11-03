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
            page.wait_for_function('(n)=>document.querySelectorAll(".photo-marker").length===n',arg=n)
        def year(value):
            page.locator('#year-slider').evaluate('(el,value)=>{el.value=value;el.dispatchEvent(new Event("input",{bubbles:true}));}',str(value))
        def reset():
            page.locator('#year-slider').focus()
            page.keyboard.press('Home')
            count(5)
            assert page.locator('#time-label').inner_text()=='All time'
        count(5)
        assert page.locator('#time-label').inner_text()=='All time'
        assert page.locator('#range-mode, #end-year-slider, .identity, .timeline, #photo-count').count()==0
        year(1900);count(2)
        assert page.locator('#time-label').inner_text()=='1900'
        assert page.locator('#year-slider').get_attribute('aria-valuetext')=='1900'
        page.locator('#year-slider').focus();page.keyboard.press('ArrowRight');count(2)
        assert page.locator('#time-label').inner_text()=='1901'
        year(1906);count(0)
        assert page.locator('#empty-state').is_visible()
        year(1910);count(1)
        reset()
        year(1900)
        page.locator('.photo-marker').last.click()
        assert page.locator('#photo-panel').get_attribute('aria-hidden')=='false'
        page.locator('#year-slider').focus();year(1911);count(0)
        assert page.locator('#year-slider').evaluate('(el)=>el===document.activeElement')
        assert page.locator('#photo-panel').get_attribute('aria-hidden')=='true'
        reset()
        page.wait_for_timeout(2500)
        assert not page.locator('#error-state').is_visible(),page.locator('#error-state').inner_text()
        for width in (1920,1440,390,320):
            page.set_viewport_size({'width':width,'height':900})
            page.wait_for_timeout(100)
            header=page.locator('.masthead').bounding_box()
            slider=page.locator('#year-slider').bounding_box()
            label=page.locator('#time-label').bounding_box()
            map_box=page.locator('#map').bounding_box()
            header_bottom=header['y']+header['height']
            assert slider['y']>=header['y'] and slider['y']+slider['height']<=header_bottom
            assert label['x']+label['width']<=slider['x']
            assert map_box['y']>=header_bottom
            assert page.locator('.maplibregl-ctrl-top-right').bounding_box()['y']>=header_bottom
            assert page.evaluate('document.documentElement.scrollWidth')==width
            assert page.locator('.masthead').inner_text().splitlines()==['home','All time','ⓘ']
            page.locator('#year-slider').blur()
            page.screenshot(path=f'/workspace/scratch/minimal-header-{width}.png')
        page.route('**/photos.json',lambda route:route.fulfill(json={'version':1,'photos':[]}))
        page.reload();page.wait_for_selector('#empty-state',state='visible');count(0)
        assert page.locator('#time-label').inner_text()=='All time'
        assert not errors,errors
        print('PASS header-only slider and year, no branding/range controls, all-time default including undated, year steps, date intervals, reset, empty states, focus, desktop and mobile layouts')
    finally:
        browser.close()
