"""Run in the GDAL environment: python -m unittest discover -s tests/terrain -v."""
import argparse
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
import numpy as np
from PIL import Image
from osgeo import gdal, osr
from pmtiles.reader import Reader, MemorySource

ROOT=Path(__file__).resolve().parents[2]
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
terrain=module('terrain',ROOT/'tools/terrain/build.py')
fixture=module('fixture',ROOT/'tools/terrain/synthetic_fixture.py')

class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name)
        cls.source=cls.root/'ramp.tif';cls.info=fixture.make(cls.source,'ramp',hole=True)
        cls.args=argparse.Namespace(input=[str(cls.source)],output=str(cls.root/'out'),bounds=[147.08,-41.34,147.32,-41.16],
            min_zoom=10,max_zoom=12,max_tiles=400,source_crs=None,vertical_datum='SYNTHETIC',kind='synthetic-test',
            elevation_units='metres',source_url='https://example.invalid/test',licence_url='https://creativecommons.org/publicdomain/zero/1.0/',attribution='SYNTHETIC')
        cls.result=terrain.build(cls.args)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_terrarium_roundtrip_and_invalid_values(self):
        elevations=np.array([[-32768,-10.125,0,1/256,256,1234.567,32767.99609375]])
        np.testing.assert_allclose(terrain.decode(terrain.encode(elevations)),elevations,atol=1/512)
        for value in (float('nan'),float('inf'),-32769,32768):
            with self.assertRaises(ValueError):terrain.encode(np.array([[value]]))

    def test_xyz_north_up_and_real_crs_reprojection(self):
        projected=osr.SpatialReference();projected.ImportFromEPSG(7855);projected.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        mercator=osr.SpatialReference();mercator.ImportFromEPSG(3857);mercator.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        transform=osr.CoordinateTransformation(mercator,projected)
        z,x,y=map(int,next(iter(self.result['tiles'])).split('/'))
        rgb=np.array(Image.open(self.root/'out/tiles'/str(z)/str(x)/f'{y}.png'))
        heights=terrain.decode(rgb);left,bottom,right,top=terrain.tile_bounds(z,x,y)
        for row,col in ((10,10),(128,128),(245,245)):
            e,n,_=transform.TransformPoint(left+(col+.5)*(right-left)/256,top-(row+.5)*(top-bottom)/256)
            x0,y0=self.info['origin'];span=50000
            expected=200+(e-x0)*.01+(n-(y0-span))*.02
            self.assertAlmostEqual(heights[row,col],expected,delta=.05)
        self.assertGreater(heights[10,128],heights[245,128], 'Northern row must have the higher northward ramp')
        self.assertGreater(heights[128,245],heights[128,10], 'Eastern column must have the higher eastward ramp')

    def test_nodata_rejected_without_filling_sea_level(self):
        self.assertGreater(sum(self.result['rejected_incomplete_tiles_by_zoom'].values()),0)
        for key,stats in self.result['tiles'].items():
            self.assertGreater(stats['elevation_min_m'],150)
            self.assertLessEqual(stats['max_encoding_error_m'],1/512)
        self.assertTrue((self.root/'out/nodata-mask.geojson').is_file())

    def test_known_nodata_hole_has_no_tile_or_claimed_coverage(self):
        source=osr.SpatialReference();source.ImportFromEPSG(7855);source.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        target=osr.SpatialReference();target.ImportFromEPSG(4326);target.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        x0,y0=self.info['origin']
        lon,lat,_=osr.CoordinateTransformation(source,target).TransformPoint(x0+740.5*25,y0-740.5*25)
        x,y=terrain.tile_xy(lon,lat,self.result['maxzoom'])
        self.assertNotIn(f"{self.result['maxzoom']}/{int(x)}/{int(y)}",self.result['tiles'])
        from osgeo import ogr
        coverage=ogr.CreateGeometryFromJson(json.dumps(json.loads((self.root/'out/coverage.geojson').read_text())['geometry']))
        point=ogr.Geometry(ogr.wkbPoint);point.AddPoint(lon,lat)
        self.assertFalse(coverage.Contains(point))

    def test_valid_asc_zip_and_prj_sidecar(self):
        folder=self.root/'archive-test';folder.mkdir()
        srs=osr.SpatialReference();srs.ImportFromEPSG(7855);srs.MorphToESRI()
        archive=self.root/'valid.zip'
        with zipfile.ZipFile(archive,'w') as z:
            z.writestr('region/grid.asc','ncols 2\nnrows 2\nxllcorner 500000\nyllcorner 5400000\ncellsize 25\nNODATA_value -9999\n1 2\n3 4\n')
            z.writestr('region/grid.prj',srs.ExportToWkt())
        files=terrain.unpack_sources([archive],folder)
        self.assertEqual(len(files),1)
        wkt,metadata=terrain.inspect_sources(files,None)
        self.assertEqual(metadata[0]['size'],[2,2])
        self.assertEqual(metadata[0]['nodata'],-9999)

    def test_pmtiles_every_tile_identical_to_png(self):
        reader=Reader(MemorySource((self.root/'out/terrain.pmtiles').read_bytes()))
        self.assertEqual(reader.metadata()['encoding'],'terrarium')
        self.assertEqual(reader.header()['addressed_tiles_count'],len(self.result['tiles']))
        for key in self.result['tiles']:
            z,x,y=map(int,key.split('/'))
            self.assertEqual(reader.get(z,x,y),(self.root/'out/tiles'/str(z)/str(x)/f'{y}.png').read_bytes())

    def test_existing_output_and_unknown_crs_are_rejected(self):
        with self.assertRaises(ValueError):terrain.build(self.args)
        asc=self.root/'unknown.asc'
        asc.write_text('ncols 2\nnrows 2\nxllcorner 0\nyllcorner 0\ncellsize 25\nNODATA_value -9999\n1 2\n3 4\n')
        with self.assertRaisesRegex(ValueError,'no CRS'):terrain.inspect_sources([asc],None)

    def test_zip_traversal_rejected(self):
        archive=self.root/'unsafe.zip'
        with zipfile.ZipFile(archive,'w') as z:z.writestr('../escaped.asc','no')
        with self.assertRaises(ValueError):terrain.unpack_sources([archive],self.root/'extract')
