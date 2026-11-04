#!/usr/bin/env python3
"""Conservative regional DEM -> XYZ Terrarium PNG + PMTiles. Raw data stays outside Git.
Requires GDAL Python bindings, NumPy, Pillow and pmtiles==3.8.1.
"""
import argparse
from collections import Counter
import hashlib
import io
import json
import math
from pathlib import Path
import tempfile
import time
import zipfile

import numpy as np
from PIL import Image
from osgeo import gdal, ogr, osr

gdal.UseExceptions()
osr.UseExceptions()
gdal.SetCacheMax(64 * 1024 * 1024)
RADIUS = 6378137.0
WORLD = math.pi * RADIUS
SIZE = 256


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def encode(elevations):
    a = np.asarray(elevations, dtype=np.float64)
    if not np.isfinite(a).all() or a.min() < -32768 or a.max() > 32767.99609375:
        raise ValueError('Only valid finite elevations in the Terrarium range may be encoded')
    values = np.rint((a + 32768) * 256).astype(np.uint32)
    return np.stack([(values >> 16) & 255, (values >> 8) & 255, values & 255], axis=-1).astype(np.uint8)


def decode(rgb):
    a = np.asarray(rgb, dtype=np.float64)
    return a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768


def tile_lonlat(z, x, y):
    n = 2 ** z
    return x / n * 360 - 180, math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))


def tile_bounds(z, x, y):
    step = 2 * WORLD / 2 ** z
    return [-WORLD + x * step, WORLD - (y + 1) * step,
            -WORLD + (x + 1) * step, WORLD - y * step]


def tile_xy(lon, lat, z):
    n = 2 ** z
    return (lon + 180) / 360 * n, (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n


def tiles_for(bounds, zoom):
    west, south, east, north = bounds
    a, b = tile_xy(west, north, zoom)
    c, d = tile_xy(east, south, zoom)
    for x in range(math.floor(a), math.ceil(c)):
        for y in range(math.floor(b), math.ceil(d)):
            yield zoom, x, y


def polygon(z, x, y):
    w, n = tile_lonlat(z, x, y)
    e, s = tile_lonlat(z, x + 1, y + 1)
    return [[w, s], [e, s], [e, n], [w, n], [w, s]]


def unpack_sources(inputs, temp):
    """Only extract ASC + PRJ sidecars; reject path traversal and excessive archives."""
    paths = []
    for number, source in enumerate(inputs):
        source = Path(source).resolve()
        if source.suffix.lower() != '.zip':
            if source.suffix.lower() not in ('.asc', '.tif', '.tiff'):
                raise ValueError('Inputs must be ASC, GeoTIFF or ZIP files')
            paths.append(source)
            continue
        target = Path(temp) / str(number)
        with zipfile.ZipFile(source) as archive:
            if sum(f.file_size for f in archive.infolist()) > 16 * 1024 ** 3:
                raise ValueError('Archive exceeds the regional pilot extraction limit (16 GiB)')
            for info in archive.infolist():
                name = Path(info.filename)
                if name.is_absolute() or '..' in name.parts or '\\' in info.filename:
                    raise ValueError('Unsafe ZIP member path')
                if name.suffix.lower() not in ('.asc', '.prj'):
                    continue
                out = target / name
                out.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as incoming, out.open('wb') as dest:
                    import shutil
                    shutil.copyfileobj(incoming, dest)
                if name.suffix.lower() == '.asc':
                    paths.append(out)
    if not paths:
        raise ValueError('No elevation rasters found')
    return paths


def inspect_sources(paths, override):
    metadata = []
    reference = None
    for path in paths:
        ds = gdal.Open(str(path))
        if ds is None or ds.RasterCount != 1:
            raise ValueError('Each input must be a single-band elevation raster')
        wkt = ds.GetProjectionRef()
        srs = osr.SpatialReference()
        if override:
            srs.SetFromUserInput(override)
            if wkt:
                actual = osr.SpatialReference(wkt=wkt)
                if not actual.IsSame(srs):
                    raise ValueError('Explicit CRS conflicts with embedded raster CRS')
        elif wkt:
            srs.ImportFromWkt(wkt)
        else:
            raise ValueError('Raster has no CRS: supply --source-crs from its verified metadata')
        if reference is not None and not reference.IsSame(srs):
            raise ValueError('Input CRS mismatch: reproject deliberately before mosaicking')
        if srs.IsCompound():
            raise ValueError('Compound vertical CRS is not supported: provide a verified horizontal CRS and unchanged metre heights')
        unit = ds.GetRasterBand(1).GetUnitType().lower()
        if unit and unit not in ('m', 'metre', 'metres', 'meter', 'meters'):
            raise ValueError('Elevation units must be metres; do not silently reinterpret feet')
        reference = srs
        metadata.append({'name': path.name, 'sha256': digest(path), 'size': [ds.RasterXSize, ds.RasterYSize],
                         'geotransform': list(ds.GetGeoTransform()), 'crs_wkt': srs.ExportToWkt(),
                         'nodata': (lambda v: v if v is None or math.isfinite(v) else 'NaN')(ds.GetRasterBand(1).GetNoDataValue())})
    return reference.ExportToWkt(), metadata


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')


def package_pmtiles(output, tiles, bounds, attribution, metadata):
    from pmtiles.tile import Compression, TileType, zxy_to_tileid
    from pmtiles.writer import write
    header = {'tile_type': TileType.PNG, 'tile_compression': Compression.NONE,
              'min_lon_e7': round(bounds[0] * 1e7), 'min_lat_e7': round(bounds[1] * 1e7),
              'max_lon_e7': round(bounds[2] * 1e7), 'max_lat_e7': round(bounds[3] * 1e7)}
    with write(str(output / 'terrain.pmtiles')) as writer:
        for z, x, y in sorted(tiles, key=lambda t: zxy_to_tileid(*t)):
            writer.write_tile(zxy_to_tileid(z, x, y), (output / 'tiles' / str(z) / str(x) / f'{y}.png').read_bytes())
        writer.finalize(header, {'name': 'Regional terrain pilot', 'format': 'png', 'encoding': 'terrarium',
                                 'attribution': attribution, 'bounds': ','.join(map(str, bounds)),
                                 'source_kind': metadata['kind']})


def build(args):
    started = time.monotonic()
    west, south, east, north = args.bounds
    if not (-180 < west < east < 180 and -85 < south < north < 85):
        raise ValueError('Invalid WGS84 bounds: west south east north')
    if east - west > 1 or north - south > 1:
        raise ValueError('Stage 0 is limited to a region of at most one degree in each direction')
    if not 0 <= args.min_zoom <= args.max_zoom <= 14:
        raise ValueError('Pilot zooms must be ordered and within 0..14')
    candidates = [t for z in range(args.min_zoom, args.max_zoom + 1) for t in tiles_for(args.bounds, z)]
    if len(candidates) > args.max_tiles:
        raise ValueError(f'{len(candidates)} candidate tiles exceeds --max-tiles {args.max_tiles}')
    output = Path(args.output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError('Output directory must be empty; existing results are never overwritten')
    output.mkdir(parents=True, exist_ok=True)
    tiles, skipped, stats = [], Counter(), {}
    sources = [{'name': Path(p).name, 'sha256': digest(p)} for p in args.input]
    with tempfile.TemporaryDirectory(prefix='terrain-build-') as temp:
        paths = unpack_sources(args.input, temp)
        wkt, raster_metadata = inspect_sources(paths, args.source_crs)
        vrt = gdal.BuildVRT(str(Path(temp) / 'mosaic.vrt'), [str(p) for p in paths],
                            options=gdal.BuildVRTOptions(outputSRS=wkt, allowProjectionDifference=False))
        if vrt is None:
            raise ValueError('Could not build the regional source mosaic')
        mask_source = gdal.Translate(str(Path(temp)/'validity.vrt'), vrt, options=gdal.TranslateOptions(format='VRT', bandList=['mask']))
        mask_source.GetRasterBand(1).DeleteNoDataValue()
        for z, x, y in candidates:
            tile = gdal.Warp('', vrt, format='MEM', dstSRS='EPSG:3857',
                             outputBounds=tile_bounds(z, x, y), width=SIZE, height=SIZE,
                             outputType=gdal.GDT_Float32, dstNodata=float('nan'),
                             resampleAlg='bilinear', multithread=False)
            heights = tile.ReadAsArray()
            validity = gdal.Warp('', mask_source, format='MEM', dstSRS='EPSG:3857',
                                 outputBounds=tile_bounds(z,x,y), width=SIZE, height=SIZE,
                                 outputType=gdal.GDT_Byte, dstNodata=0, resampleAlg='min').ReadAsArray()
            if not np.isfinite(heights).all() or not (validity == 255).all():
                # MapLibre ignores PNG alpha when decoding DEM RGB. Never encode
                # nodata as zero or -32768 m: reject the entire incomplete tile.
                skipped[z] += 1
                continue
            dest = output / 'tiles' / str(z) / str(x) / f'{y}.png'
            dest.parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(encode(heights)).save(dest, optimize=False, compress_level=9)
            decoded = decode(np.array(Image.open(dest)))
            error = float(np.max(np.abs(decoded - heights)))
            stats[f'{z}/{x}/{y}'] = {'bytes': dest.stat().st_size, 'sha256': digest(dest),
                                    'elevation_min_m': float(heights.min()), 'elevation_max_m': float(heights.max()),
                                    'max_encoding_error_m': error}
            tiles.append((z, x, y))
        mask_source.FlushCache();mask_source=None
        vrt.FlushCache();vrt=None
    if not tiles:
        raise ValueError('No fully valid tiles. Expand source coverage or use a finer regional zoom; do not fill nodata')
    minzoom, maxzoom = min(t[0] for t in tiles), max(t[0] for t in tiles)
    full = [polygon(*t) for t in tiles if t[0] == maxzoom]
    coverage_geom = ogr.CreateGeometryFromJson(json.dumps({'type': 'MultiPolygon', 'coordinates': [[p] for p in full]})).UnionCascaded()
    envelope = coverage_geom.GetEnvelope()
    bounds = [envelope[0], envelope[2], envelope[1], envelope[3]]
    outer = ogr.CreateGeometryFromJson(json.dumps({'type': 'Polygon', 'coordinates': [[
        [-180, -85], [180, -85], [180, 85], [-180, 85], [-180, -85]]]}))
    mask = outer.Difference(coverage_geom)
    coverage = {'type': 'Feature', 'properties': {}, 'geometry': json.loads(coverage_geom.ExportToJson())}
    write_json(output / 'coverage.geojson', coverage)
    write_json(output / 'nodata-mask.geojson', {'type': 'Feature', 'properties': {}, 'geometry': json.loads(mask.ExportToJson())})
    attribution = args.attribution
    manifest = {'version': 1, 'kind': args.kind, 'source_url': args.source_url, 'source_metadata_verified': False,
                'licence_url': args.licence_url, 'attribution': attribution,
                'vertical_datum': args.vertical_datum, 'units': 'metres', 'sources': sources, 'rasters': raster_metadata,
                'gdal_version': gdal.VersionInfo('--version'), 'encoding': 'terrarium', 'scheme': 'xyz',
                'tile_size': SIZE, 'exaggeration': 1, 'requested_bounds': args.bounds, 'bounds': bounds,
                'minzoom': minzoom, 'maxzoom': maxzoom, 'rejected_incomplete_tiles_by_zoom': dict(skipped),
                'tile_count_by_zoom': dict(Counter(t[0] for t in tiles)), 'tiles': stats,
                'nodata_policy': 'Omit incomplete tiles; opaque mask outside fully valid max-zoom footprint. No zero fill.',
                'build_seconds': round(time.monotonic() - started, 3)}
    if getattr(args, 'source_record', None):
        record = json.loads(Path(args.source_record).read_text())
        if record.get('archives') != sources:
            raise ValueError('Source record must identify every input archive by name and SHA256, in input order')
        manifest['source_record'] = record
    package_pmtiles(output, tiles, bounds, attribution, manifest)
    manifest['png_bytes'] = sum(s['bytes'] for s in stats.values())
    manifest['pmtiles_bytes'] = (output / 'terrain.pmtiles').stat().st_size
    write_json(output / 'tilejson.json', {'tilejson': '3.0.0', 'name': 'Regional terrain pilot', 'tiles': ['tiles/{z}/{x}/{y}.png'],
                                         'bounds': bounds, 'minzoom': minzoom, 'maxzoom': maxzoom, 'attribution': attribution,
                                         'encoding': 'terrarium', 'scheme': 'xyz', 'tileSize': SIZE})
    write_json(output / 'manifest.json', manifest)
    return manifest


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', nargs='+', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--bounds', nargs=4, type=float, required=True, metavar=('WEST', 'SOUTH', 'EAST', 'NORTH'))
    p.add_argument('--min-zoom', type=int, default=10)
    p.add_argument('--max-zoom', type=int, default=12)
    p.add_argument('--max-tiles', type=int, default=400)
    p.add_argument('--source-crs', help='Only supply from verified metadata; never guessed')
    p.add_argument('--vertical-datum', required=True)
    p.add_argument('--elevation-units', choices=('metres',), required=True)
    p.add_argument('--kind', choices=('list', 'synthetic-test'), required=True)
    p.add_argument('--source-url', required=True)
    p.add_argument('--licence-url', required=True)
    p.add_argument('--attribution', required=True)
    p.add_argument('--source-record', help='Reviewed metadata/attribution record; archive names and SHA256 must match inputs')
    return p

if __name__ == '__main__':
    args = parser().parse_args()
    try:
        result = build(args)
    except (ValueError, RuntimeError, OSError, ImportError) as error:
        parser().exit(1, f'Terrain build failed: {error}\n')
    print(json.dumps({k: result[k] for k in ('kind', 'bounds', 'tile_count_by_zoom', 'png_bytes', 'pmtiles_bytes', 'build_seconds')}, indent=2))
