# Stage 0 evidence — 4 November 2026

## Current result

**Partial Stage 0 implementation; not a completed real-LIST pilot.** The isolated
conversion pipeline and rendering scene work with explicitly synthetic test data.
Official LIST metadata and data downloads are blocked by this environment's enforced
HTTP allowlist. No master DEM has been retrieved, no actual LIST terrain has been
validated, no statewide dataset has been built, and no live site deployment has occurred.
Stage 1 production editor, Stage 2 statewide rollout and Stage 3 assisted alignment
are not complete and are not represented as delivered.

Existing project audit: MapLibre 6.16.0, separate static map and standard-library local
Photo Manager. Published photo fields distinguish camera, subject and camera bearing;
there is no accepted 3D pose schema. Optional places use a separate catalogue. The
current builder exposes the extension points without changing these contracts. The
existing tracked site/source footprint measured 13,643,281 bytes, including downloadable
editor archives. Raw DEM and generated terrain outputs stay outside tracked source.

## Measured local test dataset

The input is a generated 25 m EPSG:7855 mathematical surface centred near the intended
pilot coordinates. This geographic placement does **not** make it real Tasmanian terrain.
Its height datum is explicitly synthetic, not AHD. Requested bounds are
147.08, -41.34, 147.32, -41.16, expanded to full tile edges.

| Measurement | Actual synthetic run |
| --- | ---: |
| Fully valid tiles | 22 |
| Zoom 11 tiles / PNG bytes | 6 / 469,581 |
| Zoom 12 tiles / PNG bytes | 16 / 1,230,756 |
| Total PNG bytes | 1,700,337 |
| PMTiles bytes | 1,700,806 |
| Archive overhead over PNG payload | 469 bytes |
| Initial build duration in this instance | 3.543 s |
| Browser centre height, either delivery mode | approximately 928.663 m (synthetic) |
| Terrain vertical exaggeration | 1 |

The archive contained byte-identical PNGs at every z/x/y address. Source CRS was actually
reprojected from EPSG:7855 to EPSG:3857. Known independent east/north height ramps matched
sampled output to within 0.05 m, while encoding alone stayed within 1/512 m. Raster grid
orientation, missing-data handling and source units must still be validated against LIST.
Timing is one machine/run, not a performance guarantee or cross-platform benchmark.

The local test server returned **206**, `Content-Range: bytes 0-126/1700806`, exactly 127
header bytes, `Access-Control-Allow-Origin: *`, and no content encoding. The browser
successfully switched between local PNG and PMTiles terrain. The host probe also correctly rejected an ordinary static server that ignored Range
and returned HTTP 200, stopping after 128 bytes instead of downloading its full archive.
This proves the local server/library path only. It does **not** establish GitHub Pages range/CORS readiness.

## Hosting decision and sizing limits

Individual PNGs are the conservative baseline pending real-host checks; PMTiles is a
supported experimental alternative, not an automatic deployment choice. In this sample
PMTiles reduced file count, not payload bytes. It needs real range responses, byte-stable
content encoding and appropriate cross-origin headers if a separate host is chosen.
Use `tools/terrain/check_host.py` on an actual approved hosted archive before accepting it.
No matching archive is deployed to the public site, and its origin cannot currently be
reached from this environment, so the hosting check remains unrun there.

The handover's GitHub Pages published-site ceiling is 1 GB. Its current official wording
could not be fetched because docs.github.com is also blocked. We have not assumed a
statewide archive fits. An illustrative main-Tasmania/island rectangle (143.4, -44.3,
149, -39) gives 1,353 z11 tiles and 5,330 z12 tiles: **6,683 tiles**. This rectangle includes
sea and is not a verified LIST footprint. Uncompressed RGB pixel payload would be
**1,313,931,264 bytes**, before packaging/metadata. Applying the *synthetic* sample's mean
compression gives 516,516,008 bytes, but this is not a defensible estimate for actual LIST
heights. Source entropy, coast/gap exclusions, overview requirements, tile duplication,
archive packaging and the existing site all matter. No statewide upload is justified yet.

Reproduce geometric budgeting (no data downloads):

```sh
python tools/terrain/estimate.py --manifest pilots/terrain/data/manifest.json \
  --bounds 143.4 -44.3 149 -39 --max-zoom 12
```

## Checks and concrete limits

- Existing 12 repository tests passed; no tracked homepage, CNAME, catalogue, editor,
  download archive or public map files were changed by this terrain branch.
- Eight geospatial tests passed, covering Terrarium values/errors, actual CRS reprojection, XYZ orientation,
  omission of incomplete data, PMTiles byte equivalence, unknown CRS rejection,
  non-overwrite behaviour, safe ZIP extraction and ASC/PRJ handling.
- Chromium rendered real 3D from local **synthetic** height tiles and exercised local
  photo opacity, letterboxed vertical FOV, camera apply/reset and narrow layout.
- No actual LIST heights, official known-point comparisons, coastline, statewide source
  mosaics, Mac/Windows execution, real-photo camera-pose calibration or public-host archive
  behaviour have been verified. No silent alternate DEM source was used.

## External prerequisite and next actions

The existing custom network entries were unpkg.com and tiles.openfreemap.org. Required
additions were saved to the environment draft, preserving those entries:

- www.thelist.tas.gov.au — official metadata
- listdata.thelist.tas.gov.au — official open-data downloads
- maplibre.org, docs.protomaps.com, docs.github.com — authoritative format/hosting docs
- christophermccarthy.au, chrmccar.github.io — read-only checks of project-controlled hosting

Saving a draft did not apply these rules. Current runtime access remained blocked.
After the user saves/publishes the environment settings, recheck connectivity, obtain a
single official regional package, record its metadata/CRS/vertical datum/licence and SHA,
run the converter on that real input, verify known points and no-data edges, and replace
this synthetic-only measurement section with real results. Do not download the entire
state first, or commit raw regional ZIPs/ASC grids. Keep data in the private master folder.

Then review the Stage 0 pilot and hosting evidence before production work. Stage 1 should
use a separately versioned pose draft in the local Photo Manager, preserve the original
camera/subject coordinates, require explicit acceptance before applying a match, support
undo and retain confidence/source/landmark evidence. Confirm pitch/FOV/height conventions
on real terrain before exporting approved poses. Stage 2 requires measured statewide
storage and boundary/coverage tests; Stage 3 landmark assistance/public 3D remains later.

## Review delivery

The code and report are saved on `terrain/stage-0-pilot`, with no merge or deployment.
Git push succeeded. Creating a draft pull request through the available GitHub CLI
failed with HTTP 403 at the GraphQL API; no token was requested or extracted. The
branch remains reviewable through GitHub's compare view. This API limitation does not
prevent continuing local work once the official data hosts become accessible.
