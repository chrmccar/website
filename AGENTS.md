# Repository guidance

Read PROJECT.md and README.md first. Inspect actual files and Git status before edits.
Use this checkout; cloud tasks are isolated, so do not create worktrees unless requested.

- Preserve the root homepage's animated forest and CNAME. Change navigation only within
  the user's scope. Public map files belong at root `tasmania-through-time/` (lowercase).
- Match the homepage palette and monospace typography. Keep plain static HTML/CSS/JS;
  avoid frameworks, accounts, backends or paid services without a concrete need.
- Never commit private catalogues, drafts, originals, private editor working folders,
  Drive snapshots or backups. Keep private tooling outside the checkout. Do not assume
  Drive access. Targeted ignores are a guard, not a substitute for checking tracked files.
- Do not delete or overwrite photos/catalogue entries without authorisation and a
  verified lossless copy outside the public tree. No force pushes or history rewriting.
- Only reviewed, approved photos with valid camera/subject locations may be exported.
  Preserve the catalogue schema. Do not fabricate unknown metadata or rights claims.
- Use safe DOM text APIs and accessible controls. Test public paths, JSON/image integrity,
  draft exclusion and empty collection behaviour. Exercise browser map rendering when
  network access permits; do not call a map working from HTTP status alone.
- Run `python3 -m unittest discover -s tests -v` and the JavaScript syntax check in README.
  Explain which changes and checks succeeded and what remains unverified. Publish or
  merge only within the user's authorised scope; never silently rewrite history.
