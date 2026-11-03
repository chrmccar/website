"""Run with python3 -m unittest discover -s tests -v. No packages required."""
import json
import hashlib
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'tasmania-through-time'

class PublicSiteTests(unittest.TestCase):
    def test_homepage_links_to_correct_map(self):
        html = (ROOT / 'index.html').read_text()
        self.assertIn('href="/tasmania-through-time/"', html)
        self.assertIn('id="tree"', html)
        self.assertIn('href="#about"', html)
        self.assertIn('href="#contact"', html)

    def test_public_catalogue_and_assets(self):
        data = json.loads((SITE / 'photos.json').read_text())
        self.assertIsInstance(data['photos'], list)
        ids = set()
        for p in data['photos']:
            self.assertNotIn(p['id'], ids)
            ids.add(p['id'])
            self.assertTrue(p['published'])
            self.assertTrue(p['rights']['reviewed'])
            self.assertNotIn(p['rights']['status'], ('', 'not_verified'))
            location = p.get('camera') or p.get('subject')
            self.assertIsNotNone(location)
            self.assertTrue(-90 <= location['lat'] <= 90)
            self.assertTrue(-180 <= location['lng'] <= 180)
            for field in ('image', 'thumbnail'):
                self.assertRegex(p[field], r'^images/photo-[0-9a-f]{14}(?:-thumb)?\.(?:webp|jpg)$')
                self.assertGreater((SITE / p[field]).stat().st_size, 0)

    def test_public_tree_has_only_site_files(self):
        for path in SITE.rglob('*'):
            if not path.is_file():
                continue
            rel = path.relative_to(SITE).as_posix()
            self.assertTrue(rel in {'index.html', 'app.js', 'style.css', 'photos.json'} or
                            re.fullmatch(r'images/(?:README\.txt|photo-[0-9a-f]{14}(?:-thumb)?\.(?:webp|jpg))', rel), rel)
        self.assertFalse((ROOT / 'Tasmania-Through-Time').exists())
        self.assertFalse((ROOT / '01-024.jpg').exists())
        for name in ('LOCAL_COLLECTION.json', 'photo-assets', 'photo-originals', 'editor.html', 'photo_manager.py'):
            self.assertFalse((ROOT / name).exists())

    def test_asset_urls_match_current_contents(self):
        # HTML must request fresh assets when code changes: older cached scripts
        # can reference removed controls and prevent the catalogue from loading.
        html = (SITE / 'index.html').read_text()
        for name in ('app.js', 'style.css'):
            version = hashlib.sha256((SITE / name).read_bytes()).hexdigest()[:12]
            self.assertIn(f'./{name}?v={version}', html,
                          'Run python3 tools/update_asset_versions.py after editing map assets')

    def test_map_entrypoints_exist(self):
        html = (SITE / 'index.html').read_text()
        for name in ('app.js', 'style.css'):
            self.assertIn('./' + name, html)
            self.assertTrue((SITE / name).is_file())
        self.assertIn('href="/"', html)
        self.assertIn('/styles/positron', (SITE / 'app.js').read_text())

if __name__ == '__main__':
    unittest.main()
