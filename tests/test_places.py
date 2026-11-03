"""Test dated places against existing photo catalogues in a disposable working folder."""
import importlib.util
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]

class PlaceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        with zipfile.ZipFile(ROOT/'downloads/Tasmania-Photo-Manager.zip') as z:z.extractall(self.temp.name)
        base=Path(self.temp.name)/'Tasmania-Photo-Manager'
        spec=importlib.util.spec_from_file_location('places_manager',base/'photo_manager.py')
        self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)
        self.m.initialise_collection();self.photos=self.m.load_catalogue()['photos']

    def test_places_save_export_drafts_and_photo_preservation(self):
        m=self.m
        public=m.save_place({'title':'Test building','location':{'lat':-41.25,'lng':147.2},'year_start':1880,'year_end':1945,'published':True})
        m.save_place({'title':'Private draft','published':False})
        with zipfile.ZipFile(io.BytesIO(m.website_update())) as z:
            places=json.loads(z.read('tasmania-through-time/places.json'))['places']
            self.assertEqual(places,[public]);self.assertEqual(json.loads(z.read('tasmania-through-time/photos.json'))['photos'],self.photos)
        self.assertEqual(m.load_catalogue()['photos'],self.photos)
        public['published']=False;m.save_place(public)
        self.assertEqual(json.loads(m.PUBLIC_PLACES.read_text())['places'],[])
        self.assertEqual(len(m.load_catalogue()['places']),2)

    def test_validation_does_not_change_existing_collection(self):
        baseline=self.m.CATALOGUE.read_bytes()
        for fields in ({'year_start':None},{'year_end':1800},{'location':None},{'location':{'lat':95,'lng':147}}):
            obj={'title':'Building','location':{'lat':-41,'lng':147},'year_start':1880,'published':True,**fields}
            with self.assertRaises(ValueError):self.m.save_place(obj)
            self.assertEqual(self.m.CATALOGUE.read_bytes(),baseline)

    def test_update_package_cannot_replace_catalogues_or_images(self):
        with zipfile.ZipFile(ROOT/'downloads/Photo-Manager-Update.zip') as z:
            self.assertEqual(set(z.namelist()),{'photo_manager.py','editor.html','editor.js','editor.css','UPDATE-INSTRUCTIONS.txt','tasmania-through-time/index.html','tasmania-through-time/app.js','tasmania-through-time/style.css'})
            for name in z.namelist():
                self.assertNotIn('json',name);self.assertNotIn('images/',name)
                source = ROOT/name if name.startswith('tasmania-through-time/') else ROOT/'tools/photo-manager'/name
                self.assertEqual(z.read(name),source.read_bytes())
            for name in ('editor.js','editor.css'):
                version=hashlib.sha256(z.read(name)).hexdigest()[:12]
                self.assertIn(f'./{name}?v={version}',z.read('editor.html').decode())
