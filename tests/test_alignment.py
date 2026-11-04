"""Private pose drafts must survive editing and never leak into public exports."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]

class AlignmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        with zipfile.ZipFile(ROOT/'downloads/Tasmania-Photo-Manager.zip') as z:z.extractall(self.temp.name)
        self.base = Path(self.temp.name)/'Tasmania-Photo-Manager'
        spec=importlib.util.spec_from_file_location('alignment_test_manager',self.base/'photo_manager.py')
        self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)
        self.m.initialise_collection();self.original=self.m.load_catalogue()
        p=self.original['photos'][0];self.id=p['id']
        terrain=self.base/'terrain/data';terrain.mkdir(parents=True)
        (terrain/'manifest.json').write_text(json.dumps({'kind':'list','encoding':'terrarium','exaggeration':1,'maxzoom':0,'tiles':{'0/0/0':{}},'vertical_datum':'Unconfirmed supplied heights'}))
        self.obj={'id':self.id,'revision':None,'pose':{'lat':-41.25,'lng':147.21,'elevation_m':180,'bearing':30,'pitch':89,'vertical_fov':40},'confidence':'low','notes':'PRIVATE alignment notes','opacity':50}

    def change(self,action,obj=None):
        data=self.m.load_catalogue()
        p=self.m.alignment.update(data,obj or self.obj,self.base,action)
        self.m.atomic_catalogue(data)
        self.obj['revision']=p['alignment']['revision']
        return p

    def export(self):
        with zipfile.ZipFile(io.BytesIO(self.m.website_update())) as z:
            return json.loads(z.read('tasmania-through-time/photos.json'))['photos']

    def test_draft_private_acceptance_explicit_old_positions_unchanged(self):
        p=self.change('save');original=next(p for p in self.original['photos'] if p['id']==self.id)
        self.assertEqual(self.export(),self.original['photos'])
        self.assertEqual(p['camera'],original['camera']);self.assertEqual(p['subject'],original['subject'])
        self.change('accept');out=next(p for p in self.export() if p['id']==self.id)
        self.assertEqual(out['camera_pose']['pitch'],89)
        self.assertNotIn('alignment',out);self.assertNotIn('PRIVATE',json.dumps(self.export()))
        self.assertEqual(out['camera'],original['camera'])
        self.obj['pose']['bearing']=100;self.change('save')
        self.assertEqual(next(p for p in self.export() if p['id']==self.id)['camera_pose']['bearing'],30)
        self.change('withdraw');self.assertEqual(self.export(),self.original['photos'])

    def test_regular_photo_save_preserves_alignment_and_undo(self):
        self.change('save');self.obj['pose']['bearing']=60;second=self.change('save')
        edited=copy.deepcopy(second);edited['title']='New title'
        result=self.m.save_photo(edited)
        expected=copy.deepcopy(second['alignment']);expected['revision']=result['alignment']['revision']
        self.assertEqual(result['alignment'],expected)
        self.assertNotEqual(result['alignment']['revision'],second['alignment']['revision'])
        self.obj['revision']=result['alignment']['revision']
        restored=self.change('undo');self.assertEqual(restored['alignment']['draft']['pose']['bearing'],30)
        self.assertEqual(restored['title'],'New title')
        self.assertEqual(len(self.m.load_catalogue()['photos']),len(self.original['photos']))

    def test_stale_writes_invalid_pose_and_rights_are_rejected_without_changes(self):
        self.change('save');baseline=self.m.CATALOGUE.read_bytes()
        stale=copy.deepcopy(self.obj);stale['revision']=None
        with self.assertRaises(ValueError):self.change('save',stale)
        for value in (float('nan'),True,100):
            invalid=copy.deepcopy(self.obj);invalid['pose']['pitch']=value
            with self.assertRaises(ValueError):self.change('save',invalid)
        self.assertEqual(self.m.CATALOGUE.read_bytes(),baseline)
        data=self.m.load_catalogue();p=next(p for p in data['photos'] if p['id']==self.id)
        p['published']=False;p['rights']['reviewed']=False;self.m.atomic_catalogue(data)
        with self.assertRaises(ValueError):self.change('accept')
        self.assertNotIn(self.id,[p['id'] for p in self.export()])

    def test_image_replacement_invalidates_old_accepted_pose(self):
        self.change('save');p=self.change('accept')
        path=self.base/'photo-assets'/Path(p['image']).name
        path.write_bytes(path.read_bytes()+b'changed')
        out=next(p for p in self.export() if p['id']==self.id)
        self.assertNotIn('camera_pose',out)
        with self.assertRaises(ValueError):self.change('accept')

    def test_approved_pose_survives_public_starter_roundtrip(self):
        self.change('save');self.change('accept');public=self.export()
        self.m.CATALOGUE.unlink()  # disposable test working folder only
        self.m.initialise_collection()
        self.assertEqual(self.export(),public)
        self.assertNotIn('PRIVATE',json.dumps(public))

if __name__=='__main__':unittest.main()
