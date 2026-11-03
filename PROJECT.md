# Tasmania Through Time

A small, read-only historical photographic atlas at `/tasmania-through-time/`, hosted
alongside the existing homepage in `chrmccar/website`. Use plain static HTML/CSS/JavaScript,
MapLibre GL JS and OpenFreeMap. No accounts, public uploads, backend or paid API.

Preserve the homepage's animated forest. Its palette is `#0b1014`, `#dbe4d6`, `#a3b3a7`,
`#6f8078` and `#ecd24a`, with the JetBrains Mono/Fira Code/Menlo/Consolas monospace stack.
Keep the map understated and responsive, with a light OpenFreeMap Positron basemap for legibility and the existing dark header/photo details. A year slider starts at All time; single-year steps and an optional year-range mode filter photographs by overlapping date intervals. Undated photographs appear only in All time.

Public files live only in the lowercase root `tasmania-through-time/`. Clicking a marker
opens a photograph, date, location confidence and source/rights details. Preserve the
`photos.json` contract: `{ "version": 1, "photos": [...] }`, permanent IDs, optional dates,
optional camera/bearing and subject coordinates, rights review and publication flag.
Do not invent dates, geography, bearings or attribution. A subject location is not a known
camera position. An empty catalogue must remain usable.

The private Python-standard-library manager, full catalogue, original images and drafts
belong outside the public repository, in the user's private synced working folder. The
manager supplies an explicit public-only ZIP for manual GitHub upload. Do not assume
Codex has Google Drive access. Wait for sync before switching computers; concurrent
editing is unsupported. Approved public images stay in the public catalogue.

Manual rights review belongs to the curator. Publish only reviewed and approved records
with valid locations, never private permission correspondence. Rights notes in public
records are public. Keep originals and all existing catalogue entries losslessly preserved.

Validate case-sensitive routes, homepage animation/navigation, published images, empty
state, mobile/keyboard behaviour and draft exclusion. See README.md for running and
publishing. Keep changes small and report actual tests and deployment status accurately.
