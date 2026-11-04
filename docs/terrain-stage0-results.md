# Regional LIST terrain and private alignment results

The network/source blocker recorded in the first prototype is resolved. Real LIST terrain
is built and supplied in `downloads/Photo-Manager-Terrain-Update.zip` for local review.
The existing public website has not been deployed or changed. Statewide terrain and
optional public 3D/assisted landmark fitting are not claimed as complete.

## Source verification

Retrieved 4 November 2026 from the official LIST open-data origin. The Launceston chat
upload exceeded the executor's 32 MiB transfer limit, so the same named official package
was retrieved directly. It is not claimed to be byte-identical to the inaccessible upload.
Launceston, Dorset and George Town cover the regional pilot across municipal boundaries.
All archive CRCs passed. Exact URLs, SHA256s, metadata XML and attribution-PDF hashes,
verified facts and remaining uncertainties are in [the source record](terrain/list-source-record.json).

The package README, PRJ and official ISO19139 metadata agree on **GDA94 / MGA zone 55,
EPSG:28355**. Actual source raster cells are 25 m; nodata is -9999. Source generation is
the third edition, July 2007; package extraction is January 2021, while the metadata was
revised March 2025. These are different dates, not a claim of a 2025 elevation survey.

**The supplied metadata does not name a vertical datum.** The PRJ has `Zunits NO`.
Native metre elevations are retained without a geoid or ellipsoid conversion. The
manifest's complete-metadata-verification flag remains false for that reason; individual
confirmed facts are recorded separately. Camera heights use these same supplied values.

Licence: [CC BY 3.0 Australia](https://creativecommons.org/licenses/by/3.0/au/).
Digital attribution: “LIST Tasmania 25 metre Digital Elevation Model from theLIST
© State of Tasmania”; reprojection and Terrarium encoding are identified as modifications.
The CC BY badge is extracted unchanged from the official attribution PDF and links to the source licence.
The official source states 90% of elevations are within 5 m of true elevation, with
exceptions in steep/obscured areas. 25 m is grid spacing, not survey-grade positioning.

## Measured real regional build

Requested bounds: west 147.05, south -41.36, east 147.4, north -41.08. Tile-edge envelope:
147.041015625, -41.37680856570234, 147.48046875, -41.04621681452063. The valid footprint
has gaps; the envelope is not a promise of complete rectangular coverage.

| Measurement | Real LIST build |
| --- | ---: |
| Input ZIP bytes: Launceston | 39,531,813 |
| Input ZIP bytes: Dorset | 83,427,041 |
| Input ZIP bytes: George Town | 17,784,881 |
| Fully valid output tiles | 27 |
| Zoom 11 / zoom 12 tiles | 4 / 23 |
| PNG payload | 3,064,636 bytes |
| PMTiles archive | 3,065,159 bytes |
| Archive overhead | 523 bytes |
| Conversion time, one run here | 3.612 seconds |
| Largest encoding error | 0.001953125 m |
| Supplied height range in generated tiles | 10 to approximately 1,405 m |
| Vertical exaggeration | 1 |

Every PNG checksum and every PMTiles tile payload was verified. Five fixed regional
reference positions were independently transformed back into the native rasters;
output values lie within their native neighbourhood elevation envelopes. See
[the numerical report](terrain/regional-validation.json). These are source-consistency
checks, **not independently surveyed control points**. Analytic-ramp tests separately
check reprojection within 0.05 m, north/east orientation, encoding precision and no-data.

Incomplete tiles are omitted, never filled with zero or transparent RGB. The viewer
uses the finest complete level and an opaque no-data mask to avoid coarse missing-tile
fallback being mistaken for valid fine terrain. Unknown or unloaded heights cannot be
used to place a camera. The scene loads this project's generated elevation files only,
with no hosted terrain fallback. CDN access supplies renderer code, not elevation data.

## Hosting decision

PNG is the supported local distribution: the complete regional update serves elevation
from the user's computer through Photo Manager. It needs no GDAL on the user's computer.
PMTiles is tested separately through the range-capable loopback pilot server; it is
excluded from the local program update because the normal manager needs only PNG files.
There is little payload saving in this pilot; PMTiles mainly reduces file count.

A read-only request to an **existing** project-hosted image returned HTTP 206, exactly
127 bytes, `Content-Range: bytes 0-126/278096`, CORS `*`, and no content encoding.
[Recorded headers](terrain/hosting-probe.json) establish binary range support on that
response; they do not certify an unhosted PMTiles archive. No new terrain was deployed
for this check. The archive must still be probed at its actual approved deployed URL.

The [official Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)
were reachable and confirm a **1 GB published-site ceiling**. A broad Tasmania/island
rectangle (143.4, -44.3, 149, -39) contains 6,683 z11/z12 tiles. At this regional sample's
mean compression, that illustrates approximately **758,554,163 bytes** of PNG payload,
before metadata, packaging, existing site files and overviews. The rectangle includes
sea and is not the official coverage footprint. Other regions can compress differently;
this is not a verified statewide budget or approval to upload the state.

Recommendation: retain PNG for local/regional review; benchmark several more representative
regions and whole-state coverage before choosing a dedicated static terrain repository
or a verified range-enabled PMTiles host. Do not put raw source masters in public Git.

## Local Photo Manager integration

The optional alignment view selects existing saved photographs, adjusts opacity,
position/elevation, bearing, pitch and photo vertical FOV. Letterboxing and viewport
resizing are accounted for. A requested eye position is checked against the realised
renderer camera rather than silently saving a constrained viewpoint. Existing camera
and subject coordinates stay intact. A camera-location shortcut uses an explicitly
estimated 1.7 m eye height above the supplied DEM.

Private drafts, notes, bounded undo history, original positions, image/terrain hashes,
confidence and revision IDs live in the local catalogue. Alignment writes save lossless
private catalogue snapshots. Ordinary photograph edits preserve alignment fields.
Only explicit acceptance of the last saved draft permits `camera_pose` metadata into
a rights-approved public photograph export. Drafts/notes/history never enter exports;
replacing the image invalidates its old pose. The public map remains 2D and keeps its
existing marker coordinates and year filtering.

See [simple installation/use/backup instructions](PHOTO-ALIGNMENT-START.txt).
The update contains program files and derived terrain, never the user's catalogue or photos.

## Validation and remaining limits

- Seventeen repository tests: public file integrity, rights/draft exclusion, place dates,
  catalogue preservation, private alignment acceptance/withdrawal, undo, stale revision
  rejection, invalid pose rejection and image-replacement invalidation.
- Eight geospatial tests: reprojection, orientation, encoding, no-data holes, ZIP safety,
  ASC/PRJ handling, non-overwrite behaviour and PNG/PMTiles equivalence.
- Browser checks cover actual rendering, both terrain delivery modes, photo framing,
  realised camera position, opacity, resize, reset/undo, mobile layout and installed
  private draft save/reopen/accept/export/withdraw behaviour.
- Absolute height datum and independent survey/photo-pose validation remain unknown.
- Statewide conversion/hosting, optional landmark solving and public read-only 3D remain
  later stages. A functioning regional editor is not represented as statewide completion.
- All work is on the review branch; no merge, live deployment or environment publication.
