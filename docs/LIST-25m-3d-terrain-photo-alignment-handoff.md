# Codex handover — Tasmania 3D terrain and historical photograph alignment

**Project:** Tasmania Through Time, in `chrmccar/website`  
**Prepared:** 4 November 2026  
**Status:** Planning decisions agreed; implementation NOT yet started.

## Read first / existing constraints

Read `AGENTS.md`, `PROJECT.md`, `README.md`, and inspect the actual checkout before changing anything. This is an enhancement to the *existing* static website and local Photo Manager, not a new website or a replacement for the working map.

- Homepage has an animated forest, `CNAME`, existing palette and typography; preserve them.
- Public map lives in root `tasmania-through-time/` (lowercase). It currently uses **MapLibre GL JS** with OpenFreeMap. Keep existing markers, year slider, photo details, places, map interaction, rights review, and accessibility.
- The private, local-only Photo Manager and full catalogue are **outside the public repository**, in a private Google Drive-synced working directory. Never commit original photos, private catalogues, drafts, Drive backups or credentials.
- Existing public catalogue contract: `photos.json` is `{"version":1,"photos":[...]}`; camera and subject coordinates are distinct and must never be conflated. Do not fabricate camera coordinates, dates, image rights, direction or accuracy.
- No backend, commercial APIs, accounts, obligatory cloud processing, Cesium ion, Mapterhorn or external terrain service for the Tasmanian DEM. Use open-source tools; prefer the existing static HTML/CSS/JS setup.
- Changes to the Photo Manager must be **lossless** for existing user data and compatible with the current public-only export workflow.

## Agreed goal

Enable historical photographs to be matched to their original viewpoints by navigating true-scale 3D topography of Tasmania and transparently overlaying each image. A saved alignment should preserve the photographer's estimated position, the viewing direction, camera inclination and field of view, and its confidence. The *terrain elevation data* must be self-hosted by this project and not fetched from a hosted provider.

The screenshot motivating this work showed a semi-transparent historical photograph superimposed on 3D mountains (similar to a Cesium ion example). Reproduce the *functionality*, not Cesium branding, dependence or unrelated UI styling.

## Decisions already made (do not re-ask)

1. **Elevation source:** Official **LIST Tasmania 25 metre Digital Elevation Model** (25 m grid), not Mapterhorn, Cesium ion or paid Google terrain. Coverage is Tasmania and most associated islands, **excluding Macquarie Island**. Treat gaps outside the coverage as no-data, not sea-level land. Its original format is `.asc`, provided in local-government-area packages; inspect metadata/CRS and validate the mosaic.
2. **Renderer:** Existing **MapLibre GL JS**. Its `raster-dem` terrain source accepts Terrarium-encoded height images.
3. **Terrain delivery:** Fully project-controlled static hosting. **Prefer GitHub Pages if practical**, subject to measured archive/tile sizes and range/CORS support. Do not assume the entirety of statewide terrain will fit within Pages limits. Investigate a separate static terrain repository/site only if needed, and keep deployment independent of paid services. Do not commit a massive tile collection to the current repository as a shortcut.
4. **Data format:** Prove a small Terrarium raster-dem prototype, then evaluate **PMTiles** packaging against individual image tiles for size, performance, GitHub Pages restrictions, and browser support. Use data-driven selection rather than treating PMTiles as decided or automatically compatible.
5. **Terrain appearance:** Neutral **shaded relief**, with **no vertical exaggeration** in photograph alignment (`exaggeration:1`). A self-hosted aerial image layer is optional *later* and is NOT required for the initial release. No imagery-service dependency for the core alignment.
6. **Photo alignment:** Begin with **manual camera positioning**, with a semi-transparent photo overlay and controls for latitude/longitude, elevation/height, bearing, tilt/pitch and horizontal or vertical field of view (explicitly define which). Later add **assisted landmark/ridgeline matching** as a separate phase, without premature automatic matching.
7. **Editor location:** A **separate private/local-only editing experience**, preferably *integrated into or launched by the existing Photo Manager*, rather than putting curator controls on the public map. No public user uploads or authentication system.
8. **Storage:** Published static assets and approved metadata in GitHub, raw elevation grids and private originals/master files in the user's private synced Google Drive folder; optional external-disk backups by the user. The build process should be reproducible across Mac and Windows and must not require raw data to be checked into Git.
9. **Public UX:** Keep the familiar 2D map by default. A visitor-facing 3D perspective is a later optional feature, not a reason to disturb current site layout.

## Authoritative source material

- Official LIST 25 m DEM metadata: https://www.thelist.tas.gov.au/app/content/data/geo-meta-data-record?detailRecordUID=47b71113-a99d-4a9c-82c0-ba92c8313e79
- LIST open-data downloads (local-government-area ZIPs): https://listdata.thelist.tas.gov.au/opendata/
- Licence indicated by LIST metadata: **Creative Commons Attribution 3.0 Australia**; check current attribution guidance and display source credit in UI and documentation.
- MapLibre raster-dem format: https://maplibre.org/maplibre-style-spec/sources/
- PMTiles raster/terrain MapLibre integration: https://docs.protomaps.com/pmtiles/maplibre
- GitHub Pages limitations: https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits

**Accuracy caution:** 25 m is grid spacing, not 25 m position accuracy. LIST data derives substantially from 1:25,000 maps, contours and spot heights. Do not promise survey-grade results: nearby buildings/vegetation or hidden terrain may not match. Store match confidence and retain the original manually supplied photo location until a match is accepted.

## Implementation stages

### Stage 0 — audit, sample and deployment proof (first Codex task)

- Inspect current public map code and private Photo Manager *source* in this repo; determine extension points and existing camera/subject schema. Do not touch private user data.
- Retrieve the official download/metadata info and document the source coverage, CRS/projection, elevations/vertical datum as supplied, licence, data-generation commands and missing-data policy. **Do not download the whole state into the repository.**
- Build a **small, reproducible regional pilot** (prefer an area where the public catalogue already has distant mountain photos, e.g. Lilydale / Mount Arthur), with a documented script taking a user-provided LIST DEM ZIP/ASC as input. Use GDAL and other open-source tooling; respect no-data pixels and coastline boundaries.
- Render that pilot as real-scale MapLibre 3D terrain from *project-controlled* terrain tiles, with neutral hillshading. Confirm `exaggeration: 1`, correct orientation, DEM decoding and elevation at sample known points.
- Compare static PNG tile delivery and PMTiles archives for size/hosting compatibility. Check HTTP range responses and CORS if PMTiles is hosted on a different project-controlled origin. **GitHub Pages published-site limit is 1 GB**; avoid assuming the statewide archive will fit. No move to a paid hosted DEM.
- Show measured prototype sizes, projected statewide storage/requests and supported hosting strategy **before** committing or publishing the statewide terrain.
- Keep pilot changes isolated, reversible and non-disruptive to the current public map; use a branch/PR for review when appropriate.

**First-stage acceptance:** A reproducible build script, one functioning self-hosted test terrain scene, source and attribution documentation, reported actual size/performance/coverage, tests, and a clear next-step implementation recommendation. No destructive editor migrations, no full statewide upload yet.

### Stage 1 — local Photo Manager alignment interface

- Add a separate local-only view/tool for choosing a photo from the existing private collection and inspecting the 3D terrain.
- Adjustable 3D camera position/orientation, horizontal/vertical FOV with clear conventions, photo opacity slider (0–100%), adjustable visual alignment against the mountains, reset/undo, and saved drafts.
- Preserve provenance: distinguish known vs estimated camera position, coordinate vs view target (subject), input/edited position, confidence and any notes about matched landmarks. **Never overwrite existing camera data silently.**
- Implement a backward-compatible schema strategy after auditing existing manager, public-only export and validation. For instance, optional camera pose parameters could live alongside current `camera.lat`, `camera.lng`, `camera.bearing`; choose field names only after checking source. Existing entries without pose parameters must continue working unchanged.
- Store private drafts only in the user's private collection. Export only curator-approved public data under current rights-review rules.

### Stage 2 — statewide terrain rollout

- Convert the remaining official LIST regions, merge boundaries with correct handling of overlaps/no-data, optimise tile zoom levels (avoid oversampling implied precision), and add coverage validation.
- Store raw source and reproducible build manifests in the private master folder, public derived tiles in the approved project-controlled static host. Include upstream dataset version, retrieval date, licence, build parameters and attribution.
- Validate real-world mountain alignment at several sites around Tasmania and the offshore islands actually covered.

### Stage 3 — assisted matching and optional public 3D viewing

- Optional manual control points on identifiable summits/ridgelines to help solve/adjust camera pose and quantify residual error; retain manual corrections.
- Consider a public read-only 'view in 3D' action for photos that have an approved camera pose, without shifting existing marker location or altering year filtering. Only if performance, accessibility and visual design are satisfactory.
- Automatic skyline recognition is **not required** for the first release.

## Quality and validation

- Coordinate/projection checks, elevations and no-data decoding; accuracy of camera pitch/bearing/FOV conventions and horizon overlay.
- Browser performance on desktop and mobile; low-bandwidth graceful loading; zero distortion from vertical exaggeration.
- Preserve homepage animated forest, `CNAME`, public map's default behaviour, year slider, places, marker drift protection, photo panel, existing catalogue, rights exclusion, and accessible controls.
- Follow `AGENTS.md` / `README.md` tests; after map or editor JS/CSS edits run `python3 tools/update_asset_versions.py` and existing Python + JS checks.
- Only reviewed/approved photographs enter the public map; do not publish private or unpublished materials.
- Make no assertion that an upstream elevation tile service is 'self-hosted'. No silent fallback to Mapterhorn/Cesium ion, and no user-visible secrets.
- Document uncertain data facts and blockers rather than guessing.

## Desired Codex execution

**Start with Stage 0 now.** Read this handover with `AGENTS.md`, `PROJECT.md`, `README.md`. Inspect the actual repository, create an isolated and testable pilot, and report what is working, what is not yet verified, measured tile sizes, storage/hosting decision and what remains for Stage 1. Do not ask the user to redo planning already captured here. No live public deployment until the pilot has been reviewed.
