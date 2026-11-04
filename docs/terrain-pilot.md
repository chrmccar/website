# Regional terrain pilot — Stage 0 work in progress

This work implements the conversion and isolated scene requested in
[the agreed handover](LIST-25m-3d-terrain-photo-alignment-handoff.md).
**The real LIST regional pilot is not yet validated.** Official LIST metadata/download
access is blocked by the current cloud network policy. The working local dataset is
explicitly synthetic, generated for tests, and excluded from Git. It is not a substitute
for LIST elevation and must not be presented as Tasmanian topography.

Nothing links the pilot from the public map. The homepage, public catalogues, places,
Photo Manager, export format and camera/subject fields are unchanged. No terrain has
been merged to main or deployed. Work is on `terrain/stage-0-pilot` for review.

## Install tools

The ordinary website still needs no build. These are separate optional terrain tools.
GDAL Python bindings, GDAL CLI, NumPy and Pillow must use the same Python environment.
Use the open-source conda-forge environment on Windows/macOS/Linux:

```sh
conda env create -f tools/terrain/environment.yml
conda activate tasmania-terrain
python -m pip install -r tools/terrain/requirements.txt
```

The multiline commands below use POSIX `\` continuation. On Windows PowerShell or
Anaconda Prompt, put each command on a single line and remove those continuation
backslashes. Quoted paths may use forward slashes on both systems.

The current Linux machine already provides GDAL 3.10.3, NumPy 2.2.4 and Pillow 11.1.0
through `/usr/bin/python3`. PMTiles 3.8.1 was installed separately under
`/workspace/terrain-work/vendor`; validation here used
`PYTHONPATH=/workspace/terrain-work/vendor /usr/bin/python3 ...`.
This is task-local setup, not a portable path to copy onto a user's computer.

## Build from official input

Keep downloaded ZIPs, `.asc`, `.prj`, original metadata and source masters outside the
checkout (e.g. in the private working folder). Input ZIPs may contain several ASC grids;
the builder extracts only ASC and PRJ files into temporary storage, checks paths and
size, and mosaics them with GDAL. Multiple adjacent regional inputs are supported.

First inspect the supplied raster and official metadata:

```sh
gdalinfo /private/path/to/region.asc
python tools/terrain/build.py --help
```

The handover specifies LIST 25 m DEM local-government packages and refers to CC BY 3.0
Australia, but **the current download URL, coverage, CRS and vertical datum have not
been independently retrieved in this task**. Do not copy an assumed EPSG code or datum
into the following command. Fill them from the actual source metadata. Grid spacing is
not a claim of survey accuracy.

```sh
python tools/terrain/build.py \
  --input /private/path/to/official-region.zip \
  --output pilots/terrain/data \
  --bounds 147.08 -41.34 147.32 -41.16 \
  --min-zoom 10 --max-zoom 12 \
  --kind list --elevation-units metres \
  --vertical-datum 'REPLACE WITH VERIFIED SOURCE DATUM' \
  --source-url 'REPLACE WITH EXACT OFFICIAL DOWNLOAD URL' \
  --licence-url 'REPLACE WITH VERIFIED LICENCE URL' \
  --attribution 'REPLACE WITH REQUIRED LIST ATTRIBUTION'
```

If an ASC has no embedded CRS or recognised PRJ, supply `--source-crs` only after
checking its metadata. A conflicting CRS, non-metre unit, compound vertical CRS,
nonempty output folder, excessive region or excessive tile count is rejected. There
is no silent CRS guess, height-unit conversion, geoid conversion or overwrite. The
explicit vertical-datum label describes the supplied heights, not a verified transform.
The manifest intentionally keeps `source_metadata_verified: false`; independent source
verification is an outstanding acceptance step, not something the converter can infer.

Defaults cap a regional build at 400 candidate tiles, a one-degree extent per axis and
zoom 14. Bounds expand to the intersecting XYZ tile edges. Do not use this as a shortcut
to uploading statewide data. Start with the Lilydale/Mount Arthur region, inspect the
actual covered footprint, and add neighbouring input grids if required.

## No-data and orientation policy

Output is north-up **XYZ**, EPSG:3857, 256 × 256 PNG, Terrarium:

`height metres = R × 256 + G + B / 256 − 32768`.

Maximum quantisation error is 1/512 m; this is encoding precision, **not DEM accuracy**.
Heights are reprojected with GDAL bilinear interpolation, with a separately warped
minimum-validity mask. Any incomplete output tile is omitted, never painted as sea level.
This is deliberate: MapLibre 6.16.0's DEM decoder reads RGB and ignores PNG alpha.
Transparent nodata would otherwise decode to false terrain. This behaviour was checked
in the checksum-verified MapLibre package's `src/data/dem_data.ts`.

`coverage.geojson` describes fully valid tiles at the highest generated zoom;
`nodata-mask.geojson` visibly masks unavailable areas. Incomplete coarse tiles may be
absent even where finer tiles are valid. The viewer starts no lower than the first valid
zoom. Grey masked areas and missing tiles are **unavailable data**, not zero-height land.
The overlay experiment refuses a camera outside the valid footprint or without a loaded
height sample. Regional edge/coast behaviour must be rechecked with real source data.

Outputs are ignored by Git: `manifest.json`, per-tile PNGs, TileJSON, coverage/mask
GeoJSON and a PMTiles v3 archive. The manifest records input SHA-256s, actual source CRS,
GDAL version, source geotransforms/nodata, selected zooms, tile byte sizes/digests,
encoding errors, rejected tiles and timings. Absolute private paths are not recorded.

## Run the isolated scene

```sh
python tools/terrain/serve.py --directory . --port 8766
```

Open the local server's `/pilots/terrain/` route in a browser. The server binds only to
loopback. It has no upload, authentication or catalogue API. Both elevation delivery
modes use this project's own generated files; no hosted DEM or basemap is requested.
The scene uses MapLibre 6.16.0 and PMTiles JS 4.3.0 from the same allowed CDN already used
by the website, neutral hillshading, `encoding: terrarium`, and terrain exaggeration 1.

The selector switches between PNG files and the local archive. PMTiles first requires
an actual 206 byte-range response. Unsupported archive serving produces an error,
rather than silently fetching an entire archive or changing elevation providers.
The manifest, licence link and attribution remain visible. Synthetic inputs are labelled
**SYNTHETIC TEST DATA — not Tasmanian terrain** in the header.

The optional local photo experiment reads a file through a browser object URL. It is
not uploaded or stored in the repository. Opacity, camera position/elevation, clockwise
bearing, pitch (0° down; 90° horizontal) and **photo vertical** FOV are explicit. Letterbox
height is accounted for when converting photo FOV to viewport FOV. Camera height uses
the DEM's declared datum. Apply/reset controls are tested, but this is **not** the Stage 1
Photo Manager alignment editor: no pose is saved, no source camera is overwritten,
accepted-pose provenance/undo/landmark fitting are not implemented, and real-terrain
camera calibration remains unverified. Apply the viewpoint again after resizing.

## Reproduce the synthetic test scene

Synthetic data exists to exercise real projection/encoding/rendering code without
misrepresenting source access. It is generated at 25 m spacing in EPSG:7855, with a
known mathematical height surface and synthetic vertical datum.

```sh
python tools/terrain/synthetic_fixture.py /private/scratch/synthetic.tif
python tools/terrain/build.py \
  --input /private/scratch/synthetic.tif --output pilots/terrain/data \
  --bounds 147.08 -41.34 147.32 -41.16 --min-zoom 10 --max-zoom 12 \
  --kind synthetic-test --elevation-units metres --vertical-datum 'Synthetic test datum; not AHD' \
  --source-url https://example.invalid/synthetic-test-only \
  --licence-url https://creativecommons.org/publicdomain/zero/1.0/ \
  --attribution 'SYNTHETIC TEST DATA — not LIST Tasmania elevation'
python -m unittest discover -s tests/terrain -v
python tools/terrain/check_host.py http://127.0.0.1:8766/pilots/terrain/data/terrain.pmtiles --origin https://example.test
```

With the loopback server running, the existing Playwright/Chromium environment can run:

```sh
python tests/terrain/browser_pilot.py
```

That browser test explicitly depends on synthetic data in `pilots/terrain/data`.
It checks true-scale elevation, both delivery modes, real 206 requests, no external
terrain fallback, local photo opacity, letterboxed FOV, camera apply/reset and mobile
layout. It does not validate LIST heights or a photograph's real-world viewpoint.
See [measured results and remaining acceptance work](terrain-stage0-results.md).
