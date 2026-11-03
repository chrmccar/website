"""The public starter must contain no private data and preserve the existing photo."""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / 'downloads/Tasmania-Photo-Manager.zip'
PREFIX = 'Tasmania-Photo-Manager/'

class PhotoManagerDownloadTests(unittest.TestCase):
    def test_archive_contains_only_source_and_public_site(self):
        source_names = {'photo_manager.py', 'editor.html', 'editor.js', 'editor.css',
                        'START-HERE.txt', 'START-MAC.command', 'START-WINDOWS.bat'}
        with zipfile.ZipFile(ARCHIVE) as z:
            self.assertIsNone(z.testzip())
            for name in z.namelist():
                self.assertTrue(name.startswith(PREFIX))
                rel = name.removeprefix(PREFIX)
                if rel in source_names:
                    self.assertEqual(z.read(name), (ROOT/'tools/photo-manager'/rel).read_bytes())
                else:
                    self.assertTrue(rel.startswith('tasmania-through-time/'), rel)
                    self.assertEqual(z.read(name), (ROOT/rel).read_bytes())
                self.assertNotIn('LOCAL_COLLECTION', name)
                self.assertNotIn('photo-assets', name)
                self.assertNotIn('photo-originals', name)
            mode = z.getinfo(PREFIX+'START-MAC.command').external_attr >> 16
            self.assertTrue(mode & 0o100)

    def test_first_launch_seeds_public_collection_and_never_replaces_existing(self):
        with tempfile.TemporaryDirectory() as d:
            with zipfile.ZipFile(ARCHIVE) as z:
                z.extractall(d)
            base = Path(d)/'Tasmania-Photo-Manager'
            spec = importlib.util.spec_from_file_location('starter_manager', base/'photo_manager.py')
            manager = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(manager)
            self.assertFalse(manager.CATALOGUE.exists())
            manager.initialise_collection()
            self.assertEqual(manager.load_catalogue(), json.loads((ROOT/'tasmania-through-time/photos.json').read_text()))
            for photo in manager.load_catalogue()['photos']:
                self.assertTrue((manager.PRIVATE_IMAGES / Path(photo['image']).name).is_file())
            with zipfile.ZipFile(io.BytesIO(manager.website_update())) as z:
                self.assertTrue(all(name.startswith('tasmania-through-time/') for name in z.namelist()))
                self.assertIn('tasmania-through-time/photos.json',z.namelist())
                self.assertFalse(any(name.endswith(('.js','.css','.html','.py')) for name in z.namelist()))
            private = {'version':1,'photos':[{'id':'test-private-draft','published':False}]}
            manager.CATALOGUE.write_text(json.dumps(private))
            manager.initialise_collection()
            self.assertEqual(manager.load_catalogue(), private)

if __name__ == '__main__':
    unittest.main()
