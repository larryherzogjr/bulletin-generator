# Grace & Zion Bulletin Generator

Internal Flask application for editing weekly Grace & Zion worship content and
generating the three print-ready PDFs and Grace worship PowerPoint used each Sunday.

## Current status

The application supports week creation/cloning, a sectioned editor, SQLite
persistence, PDF preview/download, Grace PowerPoint download, and a
systemd/Gunicorn deployment. The
sample build and automated suite verify the required page sizes and fail if
content would produce an invalid print layout.

One external artifact is still needed for full visual acceptance:

- the original Publisher/PDF output for a true reference-image comparison.

## Architecture

| Layer | Files | Responsibility |
|---|---|---|
| HTTP | `app.py`, `wsgi.py` | Flask routes, request protection, file responses |
| Editing UI | `templates/form.html`, `static/form.js`, `static/style.css` | Dynamic nested form and serialized saves |
| Data contract | `schema.py` | Versioned canonical shape, cleanup, legacy migration |
| Persistence | `db.py` | One SQLite row and JSON snapshot per week |
| PDF rendering | `render.py`, `templates/*_template.html` | Jinja + WeasyPrint layouts plus booklet imposition |
| PowerPoint rendering | `presentation.py`, `scripts/generate_grace_presentation.mjs`, `presentation_templates/` | Template-based editable Grace service deck |
| Operations | `manage.py`, `deploy/` | Checks, backups, rendering, systemd deployment |

Standing information is snapshotted into every week. Editing a current week
therefore never changes an already-published bulletin. Stored JSON includes a
`schema_version`; data created by an unknown newer application is rejected
instead of being silently truncated.

## Development setup

The validated runtime is Python 3.12 plus Node.js 18 or newer. WeasyPrint also needs native Pango/Cairo
libraries and Liberation Sans/Serif. On macOS:

```sh
brew install pango cairo gdk-pixbuf libffi
brew install node
brew install --cask font-liberation
/opt/homebrew/opt/python@3.12/bin/python3.12 -m venv .venv
make install-dev
```

`constraints.txt` pins the complete validated dependency set. Use
`requirements.txt` for runtime dependencies and `requirements-dev.txt` for the
runtime plus pytest/PDF inspection tools.

## Validation and build

```sh
make test      # pytest suite: schema, DB, HTTP/security, PDF and PPTX contracts
make build     # PDFs and Grace PowerPoint under out/
make verify    # tests followed by the sample build
make check     # active DB integrity/schema plus sample/latest output render
```

The output contracts are strict:

- bulletin: exactly one 11 x 8.5 inch landscape page. Its right panel places
  Communion notices under the selected Grace/Zion events heading and the
  Baptized Today announcement under Grace;
- insert: exactly one 11 x 8.5 inch landscape page with two half-sheet panels.
- large-print booklet: exactly four 17 x 11 inch landscape pages, imposed as
  two duplex Tabloid sheets in `8|1, 2|7, 6|3, 4|5` logical-page order.
- Grace PowerPoint: editable 4:3 slides cloned from the supplied service
  examples, including the selected creed, inferred lesson headings, optional
  baptism and Grace Communion, long-stanza splitting, blank slides, and fade
  transitions.

The bulletin retains its minimum legible scale. The large-print booklet applies
one uniform font scale to all full-text worship content and keeps reducing it as
needed to preserve every Psalm, hymn, lesson, response, and creed within the
four allocated reading pages. Pathological content still returns an actionable
layout error rather than a clipped or extra-page PDF.

## Run locally

```sh
./.venv/bin/python app.py
# http://127.0.0.1:5000
```

The home page lists weeks by service date and highlights the upcoming Sunday.
Undated drafts stay at the top. Open **More → Protect from deletion** to protect
a week from both manual deletion and the production cleanup job. Clone a
comparable week and use the sticky section navigation to edit the changed content.
The bottom bar shows save status beside **Save**; **Preview & download** also
saves pending changes before opening the four output cards.

Hymn lyrics expand directly below each Grace hymn; full Scripture passages expand
beside their references in the Scripture section. Standing responses and creed
wording live under **Standing info**. Select text and use the **B**, **I**, or **U**
buttons to insert formatting; additional syntax is explained in **Editing help**.
Automatic ESV passages display as formatted read-only previews.

Entering a Grace hymn number loads all verses from the Ambassador hymn library
into the corresponding editable lyrics field.
Untouched library text is replaced automatically when a cloned week's hymn
number changes; manually edited verse selections require an explicit replace.
Selecting **Automatic ESV** loads the Call to Worship, Memory Verse, and first
two Scripture lessons from Crossway's official API. The API key stays on the
server, generated files omit visible verse numbers, and automatic ESV text is
fetched transiently instead of being accumulated in SQLite. Register for a key
at [api.esv.org](https://api.esv.org/) and set it before starting the app:

```sh
export ESV_API_KEY='your-key-from-Crossway'
./.venv/bin/python app.py
```

Print the large-print booklet double-sided on two Tabloid
sheets, flipping on the short edge; nest the second sheet inside the first
before folding.

The checked-in browser library is generated from the source RTF rather than
parsed at application runtime:

```sh
python3 scripts/import_ambassador_hymns.py source.rtf static/data/ambassador_hymns.json
```

RTF conversion uses macOS `textutil`; the importer also accepts a previously
converted UTF-8 text file. It validates all 634 positions and repairs the known
combined source block for hymns 254 and 255.

## Database operations

```sh
./.venv/bin/python manage.py init
./.venv/bin/python manage.py seed
./.venv/bin/python manage.py list
./.venv/bin/python manage.py show 1
./.venv/bin/python manage.py clone
./.venv/bin/python manage.py render 1
./.venv/bin/python manage.py check --render
./.venv/bin/python manage.py backup
./.venv/bin/python manage.py backup /safe/path/bulletin.sqlite3
./.venv/bin/python manage.py migrate
```

Backups use SQLite's online backup API and are safe while the service is
running. With the production `BULLETIN_DB`, the default destination is a
timestamped file under `/var/lib/bulletin/backups/`.

## Security boundary

The app intentionally has no built-in user accounts. The production unit makes
the existing service available on port 8000 of the trusted homelab LAN; ESV
lookup does not create another service or port. Browser cross-site writes are
rejected and JSON submissions default to a 1 MiB ceiling, configurable with
`BULLETIN_MAX_CONTENT_LENGTH`.

Restrict port 8000 to the intended LAN/VPN and do not expose it to the public
internet. If the app is later placed behind nginx or Caddy, bind Gunicorn to
loopback and require HTTPS and authentication at the reverse proxy.

See `DEPLOY.md` for installation, automated backup/preflight/rollback behavior,
and recovery commands. `SPEC.md` records the print and product decisions.
