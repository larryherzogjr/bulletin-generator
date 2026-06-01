# Grace & Zion Bulletin Generator

Internal web app to generate the weekly Sunday bulletin + insert PDFs for
Grace & Zion Free Lutheran (Valley City, ND). See [SPEC.md](SPEC.md) for the
full brief and milestone plan.

## Status

**Milestone 1 — render functions (done & verified).** The two verified
templates are wired into render functions and a minimal Flask app.

- [`render.py`](render.py) — `render_bulletin_pdf(weekly, standing)` and
  `render_insert_pdf(insert)` (plus `_html` variants). The single source of
  truth for turning data dicts into PDFs; everything else funnels through here.
- [`app.py`](app.py) — Flask skeleton serving `/`, `/bulletin.pdf`,
  `/insert.pdf` from the sample data. SQLite (M2) and the form (M3) swap out the
  data source later; the download routes keep this shape.
- [`build_samples.py`](build_samples.py) — renders the sample data to
  `out/bulletin.pdf` and `out/insert.pdf` for eyeballing against the originals.

Verified output (via `build_samples.py`):

| Output   | Pages | Size          | Print                                       |
|----------|-------|---------------|---------------------------------------------|
| Bulletin | 1     | 11 × 8.5 in   | single-sided onto the pre-printed stock     |
| Insert   | 2     | 5.5 × 8.5 in  | duplex, **flip on LONG edge**, ½-letter     |

> Note: no original PDFs were included in the repo to diff against, so "matches
> the originals" was confirmed structurally — correct page sizes/counts and a
> visual check that every field lands where the templates place it. Drop the
> original PDFs in `reference/` if you want a pixel diff.

**Milestone 2 — SQLite persistence + clone-last-week (done & verified).**

- [`db.py`](db.py) — one row per week; each row stores the full field set as a
  single JSON blob with `weekly` / `standing` / `insert` keys. CRUD plus
  `clone_latest()` / `clone_week()`. **STANDING is snapshotted per week**, so
  editing one week never alters past weeks and old bulletins reprint exactly.
- [`manage.py`](manage.py) — CLI: `init`, `seed`, `list`, `show <id>`,
  `clone`, `render <id>`.
- Verified: 24 unit checks (round-trip fidelity incl. `|safe` HTML and nested
  event tuples→lists, clone equality, **snapshot independence**, CRUD) all pass;
  a week rendered straight from the DB matches the M1 sample build.

**Milestone 3 — form UI (done & verified).** A DB-backed web app to edit weeks.

- [`schema.py`](schema.py) — canonical blob shape: `blank_blob()`,
  `normalize_blob()` (defensive cleanup on save — trims scalars, drops blank
  rows, resets invalid creed, **mirrors the shared memory verse** weekly→insert),
  and the `CREEDS` constant for the radio.
- [`app.py`](app.py) — rebuilt DB-backed: week list, create/clone/delete, the
  sectioned edit form, JSON save (`POST /weeks/<id>`), and per-week PDF routes.
- [`templates/index.html`](templates/index.html),
  [`templates/form.html`](templates/form.html) — week list + the sectioned form
  (Worship / Memory Verse / Hymns / Readings / Events / Insert / Standing).
  Confession of Faith is a **radio**; hymns/lessons/verse are free-form;
  events, lessons, announcements, prayer lists are **repeatable add/remove rows**.
- [`static/form.js`](static/form.js) — serializes the DOM back into the exact
  nested blob and POSTs it (Ctrl/Cmd-S to save; unsaved-changes guard).
- [`static/style.css`](static/style.css) — styling; sticky save bar carries the
  duplex reminder.
- Verified: 31 checks (schema normalization edge cases + full HTTP flow via the
  Flask test client) all pass; live-server end-to-end (clone → edit → fetch both
  PDFs at the correct 11×8.5 / 5.5×8.5 dimensions) confirmed.

**Milestone 4 — generate / download screen (done & verified).**

- [`templates/generate.html`](templates/generate.html) — per-week download
  screen with two cards (bulletin / insert). **Two separate downloads** (no
  bundle — confirmed with the user). The **duplex reminder sits next to the
  insert download** (long-edge flip, ½-letter) per the spec.
- [`app.py`](app.py) — `/weeks/<id>/generate` route; PDF routes now take
  `?dl=1` to force an attachment with a friendly week-stamped filename
  (e.g. `bulletin-trinity-sunday-may-31-2026.pdf`); plain routes stay inline
  for preview. Linked from both the week list and the form's save bar.
- Verified: 19 checks (slug helper, generate screen content, inline-vs-attachment
  disposition, stamped filenames, nav links, 404) pass; visual check of the
  generate screen confirms the layout and duplex callout placement.

## Dev setup (macOS)

WeasyPrint renders through native libs (pango, cairo, glib, …). Install them
with Homebrew and use a Homebrew Python for the venv:

```sh
brew install pango cairo gdk-pixbuf libffi   # native deps for WeasyPrint
brew install --cask font-liberation          # metric-compatible Arial/Times stand-ins
/opt/homebrew/opt/python@3.12/bin/python3.12 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
```

> **Fonts matter for fit.** The templates ask for Liberation Sans / Liberation
> Serif (metric-compatible with Arial / Times New Roman). If they aren't
> installed, WeasyPrint silently substitutes another face and line breaks can
> drift, so the PDF won't match the original spacing. Install `font-liberation`
> (above) on the dev machine; the church's Windows box has the real Arial /
> Times and renders identically. Check with `fc-list | grep -i liberation`.

## Use

Regenerate the reference PDFs:

```sh
./.venv/bin/python build_samples.py
# -> out/bulletin.pdf  (1 page, 11x8.5 landscape)
# -> out/insert.pdf    (2 pages, 5.5x8.5 portrait)
```

Run the app:

```sh
./.venv/bin/python app.py     # http://127.0.0.1:5000
```

Then in the browser: the home page lists weeks. **+ New week** (or **Clone**)
opens the editor; fill the sections and **Save** (or Ctrl/Cmd-S). The
**Bulletin PDF** / **Insert PDF** buttons open the print-ready files; the save
bar carries the duplex-printing reminder for the insert.

Database (week storage):

```sh
./.venv/bin/python manage.py init      # create schema (bulletin.sqlite3, gitignored)
./.venv/bin/python manage.py seed      # insert one week from sample_data
./.venv/bin/python manage.py list      # list weeks, newest first
./.venv/bin/python manage.py clone     # new week = clone the most recent
./.venv/bin/python manage.py render 1  # -> out/bulletin_1.pdf + out/insert_1.pdf
```
