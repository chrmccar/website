#!/usr/bin/env python3
"""Generate unmistakably synthetic terrain for tests only; never represents Tasmania."""
import argparse
from pathlib import Path
import numpy as np
from osgeo import gdal, osr

def make(path, profile='mountain', hole=False):
    gdal.UseExceptions();osr.UseExceptions()
    wgs=osr.SpatialReference();wgs.ImportFromEPSG(4326);wgs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    mga=osr.SpatialReference();mga.ImportFromEPSG(7855);mga.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    transform=osr.CoordinateTransformation(wgs,mga)
    cx,cy,_=transform.TransformPoint(147.2,-41.25)
    size=2000;resolution=25;x0=cx-size*resolution/2;y0=cy+size*resolution/2
    east=x0+(np.arange(size)+.5)*resolution;north=y0-(np.arange(size)+.5)*resolution
    if profile=='ramp':
        heights=200+(east[None,:]-x0)*.01+(north[:,None]-(y0-size*resolution))*.02
    else:
        heights=180+900*np.exp(-((east[None,:]-cx)**2+(north[:,None]-cy)**2)/(2*6000**2))
    heights=heights.astype('float32')
    if hole:heights[700:780,700:780]=-9999
    ds=gdal.GetDriverByName('GTiff').Create(str(path),size,size,1,gdal.GDT_Float32,options=['COMPRESS=DEFLATE','TILED=YES'])
    ds.SetGeoTransform((x0,resolution,0,y0,0,-resolution));ds.SetProjection(mga.ExportToWkt())
    band=ds.GetRasterBand(1);band.SetNoDataValue(-9999);band.SetUnitType('m');band.WriteArray(heights);ds=None
    return {'kind':'synthetic-test','centre':[147.2,-41.25],'profile':profile,'crs':'EPSG:7855','grid_metres':25,
            'origin':[x0,y0],'shape':[size,size]}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output');p.add_argument('--profile',choices=('ramp','mountain'),default='mountain');p.add_argument('--hole',action='store_true')
    args=p.parse_args();print(make(Path(args.output),args.profile,args.hole))
