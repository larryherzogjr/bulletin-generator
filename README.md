# Grace & Zion Bulletin Generator

Internal Flask application for editing weekly Grace & Zion worship content and
generating the three print-ready PDFs used each Sunday.

## Current status

The application supports week creation/cloning, a sectioned editor, SQLite
persistence, PDF preview/download, and a systemd/Gunicorn deployment. The
sample build and automated suite verify the required page sizes and fail if
content would produce an invalid print layout.

One external artifact is still needed for full visual acceptance:

- the original Publisher/PDF output for a true reference-image comparison.

## Architecture

| Layer | Files | Responsibility |
|---|---|---|
| HTTP | `app.py`, `wsgi.py` | Flask routes, request protection, PDF responses |
| Editing UI | `templates/form.html`, `static/form.js`, `static/style.css` | Dynamic nested form and serialized saves |
| Data contract | `schema.py` | Versioned canonical shape, cleanup, legacy migration |
| Persistence | `db.py` | One SQLite row and JSON snapshot per week |
| PDF rendering | `render.py`, `templates/*_template.html` | Jinja + WeasyPrint layouts plus booklet imposition |
| Operations | `manage.py`, `deploy/` | Checks, backups, rendering, systemd deployment |

Standing information is snapshotted into every week. Editing a current week
therefore never changes an already-published bulletin. Stored JSON includes a
`schema_version`; data created by an unknown newer application is rejected
instead of being silently truncated.

## Development setup

The validated runtime is Python 3.12. WeasyPrint also needs native Pango/Cairo
libraries and Liberation Sans/Serif. On macOS:

```sh
brew install pango cairo gdk-pixbuf libffi
brew install --cask font-liberation
/opt/homebrew/opt/python@3.12/bin/python3.12 -m venv .venv
make install-dev
```

`constraints.txt` pins the complete validated dependency set. Use
`requirements.txt` for runtime dependencies and `requirements-dev.txt` for the
runtime plus pytest/PDF inspection tools.

## Validation and build

```sh
make test      # pytest suite: schema, DB, HTTP/security, PDF contracts
make build     # bulletin, insert, and large-print booklet under out/
make verify    # tests followed by the sample build
make check     # active DB integrity/schema plus sample/latest PDF render
```

The print contracts are strict:

- bulletin: exactly one 11 x 8.5 inch landscape page;
- insert: exactly one 11 x 8.5 inch landscape page with two half-sheet panels.
- large-print booklet: exactly four 17 x 11 inch landscape pages, imposed as
  two duplex Tabloid sheets in `8|1, 2|7, 6|3, 4|5` logical-page order.

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

The home page lists saved weeks. Clone the most recent comparable week, edit
the changed sections, save, and open Generate. The editor waits for an active
save before navigating to the generated files and warns while changes or a
save are pending. Entering a Grace hymn number loads all verses from the
Ambassador hymn library into the corresponding editable large-print field.
Untouched library text is replaced automatically when a cloned week's hymn
number changes; manually edited verse selections require an explicit replace.
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

The app intentionally has no built-in user accounts and the production unit
binds only to `127.0.0.1`. Browser cross-site writes are rejected and JSON
submissions default to a 1 MiB ceiling, configurable with
`BULLETIN_MAX_CONTENT_LENGTH`.

If the app is exposed through nginx or Caddy, keep Gunicorn loopback-only, use
HTTPS, and require authentication at the reverse proxy. Do not publish the
Gunicorn port directly to an untrusted network.

See `DEPLOY.md` for installation, automated backup/preflight/rollback behavior,
and recovery commands. `SPEC.md` records the print and product decisions.
