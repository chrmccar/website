#!/usr/bin/env python3
"""Check real tiles against source rasters; reports source consistency, not survey control."""
import argparse
import io
import json
import math
from pathlib import Path
import hashlib
import numpy as np
from PIL import Image
from osgeo import gdal, osr
from pmtiles.reader import Reader, MemorySource
from build import decode, tile_xy, tile_lonlat

gdal.UseExceptions()
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--data',required=True);p.add_argument('--source',nargs='+',required=True)
p.add_argument('--output',required=True)
a=p.parse_args();root=Path(a.data);manifest=json.loads((root/'manifest.json').read_text())
sources=[gdal.Open(path) for path in a.source]
wgs=osr.SpatialReference();wgs.ImportFromEPSG(4326);wgs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
transforms=[]
for ds in sources:
 s=osr.SpatialReference(wkt=ds.GetProjection());s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
 transforms.append(osr.CoordinateTransformation(wgs,s))
reader=Reader(MemorySource((root/'terrain.pmtiles').read_bytes()))
for key,info in manifest['tiles'].items():
 raw=(root/'tiles'/(key+'.png')).read_bytes();z,x,y=map(int,key.split('/'))
 assert hashlib.sha256(raw).hexdigest()==info['sha256']
 assert reader.get(z,x,y)==raw
 assert np.array(Image.open(io.BytesIO(raw))).shape==(256,256,3)

# Fixed regional reference coordinates, not asserted summit/survey control points.
points=[('Lilydale',147.214,-41.25),('southern high ridge',147.28975,-41.2769),('Karoola',147.17,-41.24),('northeast',147.35,-41.15),('south',147.25,-41.33)]
rows=[]
for name,lon,lat in points:
 z=manifest['maxzoom'];tx,ty=tile_xy(lon,lat,z);x,y=int(tx),int(ty)
 assert f'{z}/{x}/{y}' in manifest['tiles'],(name,'not covered')
 pixels=decode(np.array(Image.open(root/'tiles'/str(z)/str(x)/f'{y}.png')))
 col,row=int((tx-x)*256),int((ty-y)*256)
 # Reproject the OUTPUT PIXEL CENTRE to the native source, avoiding half-pixel bias.
 plon,plat=tile_lonlat(z,x+(col+.5)/256,y+(row+.5)/256)
 value=float(pixels[row,col]);near=[];source_names=[]
 for path,ds,tr in zip(a.source,sources,transforms):
  ex,ny,_=tr.TransformPoint(plon,plat);gt=ds.GetGeoTransform()
  ix=int(math.floor((ex-gt[0])/gt[1]));iy=int(math.floor((ny-gt[3])/gt[5]))
  if 2<=ix<ds.RasterXSize-2 and 2<=iy<ds.RasterYSize-2:
   array=ds.GetRasterBand(1).ReadAsArray(ix-2,iy-2,5,5);valid=array[array!=ds.GetRasterBand(1).GetNoDataValue()]
   if valid.size:near.extend(map(float,valid));source_names.append(Path(path).name)
 assert near and min(near)-.002<=value<=max(near)+.002,(name,value,near)
 rows.append({'label':name,'requested_lon_lat':[lon,lat],'output_pixel_centre_lon_lat':[plon,plat],'decoded_elevation_m':value,'nearby_native_min_m':min(near),'nearby_native_max_m':max(near),'source_rasters':source_names})
report={'kind':'source-consistency-not-survey-control','sample_points':rows,'verified_png_pmtiles_tiles':len(manifest['tiles']),'max_encoding_error_m':max(t['max_encoding_error_m'] for t in manifest['tiles'].values()),'datum_warning':manifest['vertical_datum'],'method':'All PNG SHA256s and PMTiles payloads checked. Five fixed regional output pixel centres independently transformed to GDA94 native rasters; decoded bilinear values lie within their native 5x5 neighbourhood envelope. Analytic-ramp tests separately constrain reprojection accuracy and axis orientation.'}
Path(a.output).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
