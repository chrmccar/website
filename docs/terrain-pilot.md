# Regional terrain pilot — Stage 0 work in progress

This work implements the conversion and isolated scene requested in
[the agreed handover](LIST-25m-3d-terrain-photo-alignment-handoff.md).
The official Launceston, Dorset and George Town packages now supply real regional
terrain. Read [the measured results](terrain-stage0-results.md) for source verification,
coverage, sizes and remaining limits. The ready-to-use local update includes the derived
PNGs; the user does not need GDAL or a conversion step. Installation and use are in
[PHOTO-ALIGNMENT-START.txt](PHOTO-ALIGNMENT-START.txt).

Work remains on `terrain/stage-0-pilot` for review. No live deployment or statewide upload
has been made. Existing public photos, places, homepage and marker behaviour are preserved.
The private manager gains an optional separate alignment tool and optional accepted pose
metadata; private drafts never enter the website export.

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

The official package README, PRJ and full metadata confirm GDA94 / MGA zone 55
(EPSG:28355). The source grid is 25 m and nodata is -9999. The package README and full
metadata do **not** name a vertical datum (`Zunits NO` in the PRJ). Retain the supplied
height values; do not claim an AHD or ellipsoid transform. Source, licence and checksum
evidence are in `docs/terrain/list-source-record.json`.

```sh
python tools/terrain/build.py \
  --input /private/path/LIST_DEM_25M_LAUNCESTON.zip /private/path/LIST_DEM_25M_DORSET.zip /private/path/LIST_DEM_25M_GEORGE_TOWN.zip \
  --output /private/path/lilydale-terrain \
  --bounds 147.05 -41.36 147.4 -41.08 --min-zoom 10 --max-zoom 12 \
  --source-crs EPSG:28355 --kind list --elevation-units metres \
  --vertical-datum 'Supplied LIST heights; vertical datum not stated in supplied metadata' \
  --source-url https://listdata.thelist.tas.gov.au/opendata/data/LIST_DEM_25M_LAUNCESTON.zip \
  --licence-url https://creativecommons.org/licenses/by/3.0/au/ \
  --attribution 'LIST Tasmania 25 metre Digital Elevation Model from theLIST © State of Tasmania; CC BY 3.0 AU. Reprojected and Terrarium encoded.' \
  --source-record docs/terrain/list-source-record.json
python tools/terrain/package_update.py --data /private/path/lilydale-terrain
```

The source record is tied to the recorded archive SHA256s. A new upstream archive needs
a newly checked record; the builder rejects mismatches.

If an ASC has no embedded CRS or recognised PRJ, supply `--source-crs` only after
checking its metadata. A conflicting CRS, non-metre unit, compound vertical CRS,
nonempty output folder, excessive region or excessive tile count is rejected. There
is no silent CRS guess, height-unit conversion, geoid conversion or overwrite. The
explicit vertical-datum label describes the supplied heights, not a verified transform.
The manifest intentionally keeps `source_metadata_verified: false`; complete vertical-datum verification remains unavailable; individual verified source facts
are recorded separately rather than inferred from filenames.

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
absent even where finer tiles are valid. The local viewer uses the finest complete level and limits regional zoom-out;
it does not expose missing coarser tiles inside fine coverage. Grey masked areas and missing tiles are **unavailable data**, not zero-height land.
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

The local photo overlay uses the existing saved collection when served by Photo Manager,
or a browser-local file for an unsaved experiment. Opacity 0–100%, camera coordinates,
elevation, clockwise bearing, pitch (0° down / 90° horizontal; supported to 89.9°), and
photo vertical FOV are explicit. Letterboxing is included in the photo/viewport FOV
conversion; resizing reapplies the same eye position. The eye position is independently
reconstructed from public renderer getters, checking for camera constraints rather than
saving a requested pose that was not rendered.

Private `alignment` stores drafts, bounded undo history, source camera/subject snapshots,
image hash, terrain-manifest hash, confidence, private notes and revision IDs. Ordinary
photo saves preserve these fields. An explicit acceptance copies the last saved draft;
only a numerical `camera_pose` plus confidence/source provenance enters an approved
photo export. Private notes, originals, undo history and unaccepted drafts are stripped.
A changed image invalidates its accepted pose. Rights approval is required; camera and
subject fields are never overwritten. Revisions reject stale alignment windows. Writes
are serialised, and alignment changes take private catalogue snapshots in
`alignment-backups/`. These snapshots belong in the user's whole-folder backup.

The current public map remains 2D. It does not interpret accepted pose metadata yet.
The regional renderer starts overhead. A small adapter to the pinned MapLibre 6.16
terrain tile manager prevents rendering terrain below the available DEM level; unavailable
coarse geometry is omitted rather than presented as flat land. The adapter fails visibly
if that renderer interface changes. Upgrade tests must cover this rule as well as the
camera/framing checks; it is not a renderer-version-independent extension.
Statewide processing, independent survey controls and assisted landmark fitting are
later work; this regional delivery does not claim them.

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

That browser test defaults to synthetic data in `pilots/terrain/data`; use
`TERRAIN_KIND=list python tests/terrain/browser_pilot.py` for the real regional build.
It checks true-scale elevation, both delivery modes, real 206 requests, no external
terrain fallback, local photo opacity, letterboxed FOV, camera apply/reset and mobile
layout. It does not validate LIST heights or a photograph's real-world viewpoint.
See [measured results and remaining acceptance work](terrain-stage0-results.md).
