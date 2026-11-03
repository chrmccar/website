# Christopher McCarthy's website

The homepage is `index.html`. The photo map is at
[christophermccarthy.au/tasmania-through-time/](https://christophermccarthy.au/tasmania-through-time/).
The site uses plain HTML, CSS and JavaScript; no build or package installation is required.

The timeline starts at **All time**. Drag the slider to select a year, or tick **Year range**
to choose From and To years (inclusive). **All time** resets it. Approximate photo date
ranges match overlapping years; undated photographs appear only in All time.

## Add photographs to the map

Use the **private Tasmania Photo Manager** download supplied with the website update.
Keep that whole folder on your computer, ideally in your private Google Drive folder.
Do not upload the manager folder to GitHub.

1. Extract the private manager ZIP once. Open `START-WINDOWS.bat` on Windows or
   `START-MAC.command` on Mac. It needs Python 3 from <https://www.python.org/downloads/>;
   no extra Python packages are needed. Keep its terminal window open.
2. In the editor, click **Add photograph**, choose an image, and enter its title and date.
3. Click **Camera** and mark where the photographer stood. If you only know the place
   shown, choose **Subject** instead. Leave unknown positions and directions blank.
4. Fill in **Rights & attribution**. Tick **I have checked the rights** and
   **Show on public map** only when the photograph is approved for publication.
   Untick **Show on public map** to keep a private draft.
5. Click **Save photograph**, then **Preview website** to check it.
6. Click **Download website update**. Extract the downloaded `website-update.zip`.
7. Open <https://github.com/chrmccar/website>, on the `main` branch. Click
   **Add file → Upload files**. Drag the **`tasmania-through-time` folder from the
   extracted website update** into the upload area. Click **Commit changes**.
8. Wait for GitHub Pages to deploy, then refresh the map. Saving in the editor alone
   does not change the live website. Check **Actions** in GitHub if an update does not appear.

Upload the complete exported folder each time: it contains the current public catalogue
and approved image derivatives. It excludes drafts, originals and the private manager.
Do not upload the outer private manager folder or its `LOCAL_COLLECTION.json`.

A photo deleted or made private locally disappears from the map after the next update.
GitHub's browser upload does not delete older image files: previously published image URLs
and Git history can remain accessible. Removing a public image completely requires a
separate GitHub cleanup; making a draft is not a way to retract an already published image.

On two computers, close the manager and wait for Google Drive to finish syncing before
opening it on the other computer. Do not edit the collection simultaneously. Keep occasional
dated backups of the whole private manager folder on your external drive.

## Local development

From the repository root, run `python3 -m http.server 8000 --bind 127.0.0.1`.
The root serves the homepage and `/tasmania-through-time/` serves the map.
MapLibre and OpenFreeMap need internet access; the editor is a separate local-only tool.

Checks:

```sh
python3 -m unittest discover -s tests -v
node --check --input-type=module < tasmania-through-time/app.js
# Optional browser integration test (Playwright + Chromium, server on port 8000):
python3 tests/browser_timeline.py
```

See `PROJECT.md` for project boundaries and `AUDIT.md` for the corrected layout and
historical private-file exposure. `CNAME` must remain unchanged.
