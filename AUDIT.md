# Repository audit — 3 November 2026

The starting commit was `d123a78f4658f21a836af0285bd23f13ed0ea5db`.
Its root homepage had only about/contact links. The real map was at
`Tasmania-Through-Time/tasmania-through-time/`, so the intended lowercase root route
returned 404. There was no build configuration or dependency manifest. The repository
has a custom-domain CNAME. GitHub Pages configuration/API could not be read with the
available API access; Git read access worked. Existing history contains manual uploads.

The capitalised parent also tracked the private manager, full `LOCAL_COLLECTION.json`
and `photo-assets/`. The root contained an unreferenced source photograph `01-024.jpg`.
The private catalogue contained one record already marked published and rights-reviewed;
that approved record and its public derivative images were preserved unchanged. No new
historical photographs, locations or rights claims were created.

Before changes, a full archive of the checkout (including Git history) was created and
verified byte-for-byte outside the repository. A separate private manager working copy
preserves the original catalogue, all private image assets and the root source photograph.
It is supplied privately with the task, not hosted on the website.

The public map now lives at the lowercase root path. Private working files and the source
original have been removed from the latest public tree. Targeted ignore rules discourage
accidental recommits. This removal does not erase historical commits or copies already
made: private files and the original image may have been accessible through the repository
or Pages previously, and remain in Git history. No history was rewritten. Consider any
previously committed material historically exposed; there is no claim of retroactive erasure.

MapLibre remains pinned at 6.16.0; OpenFreeMap's dark style replaces the light Positron
style. The homepage animation is unchanged, with only the map navigation link added.
See README.md for the public-only publishing process and its limits for previously
published images.
