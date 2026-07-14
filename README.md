# Grace & Zion Bulletin Generator

Internal Flask application for editing weekly Grace & Zion worship content and
generating the two print-ready PDFs used each Sunday.

## Current status

The application supports week creation/cloning, a sectioned editor, SQLite
persistence, PDF preview/download, and a systemd/Gunicorn deployment. The
sample build and automated suite verify the required page sizes and fail if
content would produce an invalid print layout.

Two external artifacts are still needed for full visual acceptance:

- the original Publisher/PDF output for a true reference-image comparison;
- the real "Please be Praying for..." graphic, which is still a styled text
  placeholder in the insert template.

## Architecture

| Layer | Files | Responsibility |
|---|---|---|
| HTTP | `app.py`, `wsgi.py` | Flask routes, request protection, PDF responses |
| Editing UI | `templates/form.html`, `static/form.js`, `static/style.css` | Dynamic nested form and serialized saves |
| Data contract | `schema.py` | Versioned canonical shape, cleanup, legacy migration |
| Persistence | `db.py` | One SQLite row and JSON snapshot per week |
| PDF rendering | `render.py`, `templates/*_template.html` | Jinja + WeasyPrint fixed-page layouts |
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
make build     # out/bulletin.pdf and out/insert.pdf
make verify    # tests followed by the sample build
make check     # active DB integrity/schema plus sample/latest PDF render
```

The print contracts are strict:

- bulletin: exactly one 11 x 8.5 inch landscape page;
- insert: exactly two 5.5 x 8.5 inch portrait pages.

The bulletin shrinks only to its minimum legible scale. If either document
still does not fit, generation returns an actionable layout error rather than
a clipped or extra-page PDF.

## Run locally

```sh
./.venv/bin/python app.py
# http://127.0.0.1:5000
```

The home page lists saved weeks. Clone the most recent comparable week, edit
the changed sections, save, and open Generate. The editor waits for an active
save before navigating to the generated files and warns while changes or a
save are pending.

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
