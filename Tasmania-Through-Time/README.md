# Tasmania Through Time

A minimal, map-first historical photograph atlas of Tasmania. This bundle contains:

- `tasmania-through-time/` — **the only folder to upload to GitHub Pages**. It includes the public full-screen MapLibre map, the image assets and the generated `photos.json` catalogue.
- `photo_manager.py`, `editor.html`, `editor.js`, `editor.css` — the local photo manager (not for publication). It runs on Python 3's standard library, serving `127.0.0.1:8765` and opening the editor in the default browser.
- `START-MAC.command`, `START-WINDOWS.bat` — launchers that start the local manager.
- `LOCAL_COLLECTION.json` and `photo-assets/` — private catalogue and images. Includes unpublished drafts. **Never upload either to your public repository.**
- `START-HERE.txt` — short user-facing setup guide.

## Quick start

Unzip the bundle, double-click your platform's `START-...` launcher, add a photograph in the editor, and click **Save photograph**. Click **Preview website** to inspect the live local map. Then drag only the **`tasmania-through-time`** folder into the **root** of [chrmccar/website](https://github.com/chrmccar/website) using GitHub's **Add file → Upload files** control. Once GitHub Pages deploys, open `https://christophermccarthy.au/tasmania-through-time/`.

The existing homepage and `CNAME` file remain unchanged.

## Workflow

The editor compresses newly selected JPG/PNG/WebP files into an optimised display image (maximum dimension 2200 px) and a thumbnail (maximum dimension 520 px); your source file is unchanged. The editor saves updates in the private catalogue and generates a public subset automatically. An item is published only if:

1. Its **Show on public map** option is enabled.
2. **I have checked the rights** is checked and a rights status has been chosen.
3. It has a camera position or a subject position.

The map displays known and estimated camera positions differently and handles a location representing the subject alone. A direction arrow is optional. The catalogue preserves year ranges for date filtering and a separate display date. Only the published subset and its images are exported to `tasmania-through-time/`.

## Photography rights

Rights fields include creator, source, source link, archive reference, rights status, licensing URL, attribution/copyright statement and additional public notes. All published image data and rights text are public, so don't store private permission emails or personal data in these fields. Keep such documentation separately. Owning a print or scan does **not** necessarily mean owning copyright; check reuse rights image by image.

## Technical notes

- The map uses [MapLibre GL JS](https://maplibre.org/) v6.16.0 from a CDN and the [OpenFreeMap Positron style](https://openfreemap.org/). Map attribution is displayed within the map. Both require network access.
- The public page has no account system or server backend. Hosting is ordinary static GitHub Pages.
- The local Python manager is intentionally private and bound to `127.0.0.1`; closing its terminal session stops it.
- To publish updates, repeat the GitHub folder upload. For frequent publishing, using a local clone and GitHub Desktop is an optional future improvement.
- The site starts with **zero photographs** by design. No unlicensed or fabricated example archive imagery is included.
- Do not edit `photos.json` manually while using the editor; it is generated from the private catalogue.

## What has been tested

The local HTTP API, creating/updating/deleting photo records, and draft/published export separation were tested. JavaScript syntax was checked. Remote map rendering could not be exercised in the build environment; browser rendering should be checked when first running the editor on your own computer.
