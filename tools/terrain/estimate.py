#!/usr/bin/env python3
"""Geometric storage budget, not an assertion about LIST coverage or compression."""
import argparse
import importlib.util
import json
from pathlib import Path
spec=importlib.util.spec_from_file_location('build',Path(__file__).with_name('build.py'));terrain=importlib.util.module_from_spec(spec);spec.loader.exec_module(terrain)
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--manifest',required=True);p.add_argument('--bounds',nargs=4,type=float,required=True);p.add_argument('--max-zoom',type=int,default=12)
a=p.parse_args();m=json.loads(Path(a.manifest).read_text())
counts={z:len(list(terrain.tiles_for(a.bounds,z))) for z in range(m['minzoom'],a.max_zoom+1)}
values=[s['bytes'] for s in m['tiles'].values()];count=sum(counts.values());average=sum(values)/len(values)
print(json.dumps({'bounds':a.bounds,'rectangular_tile_counts':counts,'total_rectangular_tiles':count,
 'measured_input_kind':m['kind'],'measured_mean_png_bytes':average,
 'illustrative_bytes_using_sample_mean':round(count*average),
 'uncompressed_RGB_pixel_bytes':count*256*256*3,
 'warning':'Rectangle includes sea and is not official LIST coverage. Sample compression is not a verified statewide estimate. Existing site and packaging/metadata consume additional space.'},indent=2))
