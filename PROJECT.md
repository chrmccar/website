# Tasmania Through Time

A small, read-only historical photographic atlas at `/tasmania-through-time/`, hosted
alongside the existing homepage in `chrmccar/website`. Use plain static HTML/CSS/JavaScript,
MapLibre GL JS and OpenFreeMap. No accounts, public uploads, backend or paid API.

Preserve the homepage's animated forest. Its palette is `#0b1014`, `#dbe4d6`, `#a3b3a7`,
`#6f8078` and `#ecd24a`, with the JetBrains Mono/Fira Code/Menlo/Consolas monospace stack.
Keep the map understated and responsive, with a light OpenFreeMap Positron basemap for legibility and the existing dark header/photo details. The minimal header contains home, a year display, a single year slider and the existing information button, without branding or subtitles. The slider starts at All time (far left); single-year steps filter photographs by overlapping date intervals. There is no year-range mode or floating timeline panel. Undated photographs appear only in All time.

Public files live only in the lowercase root `tasmania-through-time/`. Clicking a marker
opens a photograph, date, location confidence and source/rights details without changing
the map centre or zoom. Use identical solid dots at exact stored coordinates; marker
containers must stay absolutely positioned so they never stack or drift when zooming.
When a camera bearing is recorded, show a tiny same-colour direction stroke; omit it
when direction is unknown. Keep its size constant while zooming and align it with the map. Preserve the
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

The desktop Photo Manager must fit within the viewport as the collection grows.
Its photo list and form scroll independently; scrolling either must not move the map
or hide the save controls. Existing installations receive interface-only updates that
never replace working catalogues or images.

Places/buildings are optional dated records in `places.json` (`version`, `places`).
Each has an id, title, description, location {lat,lng}, required start year for publication,
optional inclusive end year, optional source URL, and publication flag. Public places have
no image requirement; they are separate from photo rights review. All time shows all
approved places, individual years only those then present. Group exact shared coordinates
across photos/places so all entries remain accessible by cycling a dot. Editor map markers
are noninteractive references: only the library selects another entry. Existing private
catalogues/photos must survive all program updates and place edits without replacement.
