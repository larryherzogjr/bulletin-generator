"""Flask app for the Grace & Zion bulletin generator.

Routes
  GET  /                      list weeks (newest first)
  POST /weeks/new             create a blank week            -> redirect to edit
  POST /weeks/new-from-sample seed a week from sample_data   -> redirect to edit
  POST /weeks/<id>/clone      clone a week                   -> redirect to edit
  POST /weeks/<id>/delete     delete a week                  -> redirect to index
  GET  /weeks/<id>/edit       the sectioned edit form
  POST /weeks/<id>            save the form (JSON body)      -> JSON {ok, id}
  GET  /weeks/<id>/generate   the download screen (two PDFs + print reminders)
  GET  /weeks/<id>/bulletin.pdf   [?dl=1 -> attachment]
  GET  /weeks/<id>/insert.pdf     [?dl=1 -> attachment]

The form posts the whole blob as JSON (built client-side by form.js), which
keeps deeply-nested, variable-length structures — events, lessons,
announcements — straightforward versus flat form-encoded names. The server
normalizes defensively (schema.normalize_blob) before persisting.

Download policy: the secretary downloads the two PDFs separately (no
bundle — confirmed with the user, since they print on different paper/settings).
Plain PDF routes render inline for quick preview; add ``?dl=1`` to force a
download with a friendly, week-stamped filename.
"""

from __future__ import annotations

import os
import re
from urllib.parse import urlsplit

from flask import (
    Flask, Response, abort, jsonify, redirect, render_template, request, url_for,
)

import db
from schema import CREEDS, SchemaVersionError, blank_blob, normalize_blob
from render import PDFLayoutError, render_bulletin_pdf, render_insert_pdf

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = int(
    os.environ.get("BULLETIN_MAX_CONTENT_LENGTH", 1024 * 1024)
)


def _same_host(url: str) -> bool:
    """Compare an Origin/Referer URL to the request host."""
    try:
        return urlsplit(url).netloc.lower() == request.host.lower()
    except ValueError:
        return False


@app.before_request
def _reject_cross_origin_writes():
    """Block browser-driven cross-site writes to the unauthenticated LAN app.

    There is no user session to bind a traditional CSRF token to. Modern
    browsers send Fetch Metadata and/or Origin/Referer on form and fetch POSTs,
    so rejecting a cross-site value prevents a public web page from creating,
    cloning, overwriting, or deleting weeks on the private service.
    """
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return None
    if request.headers.get("Sec-Fetch-Site", "").lower() == "cross-site":
        abort(403, description="cross-site writes are not allowed")
    origin = request.headers.get("Origin")
    if origin and not _same_host(origin):
        abort(403, description="cross-origin writes are not allowed")
    referer = request.headers.get("Referer")
    if not origin and referer and not _same_host(referer):
        abort(403, description="cross-origin writes are not allowed")
    return None


@app.after_request
def _security_headers(response: Response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "img-src 'self' data:; object-src 'none'; base-uri 'self'; "
        "frame-ancestors 'none'; form-action 'self'",
    )
    if request.endpoint != "static":
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.errorhandler(PDFLayoutError)
def _layout_error(exc: PDFLayoutError):
    return render_template(
        "error.html",
        title=f"{exc.kind.title()} does not fit",
        message=str(exc),
    ), 422


@app.errorhandler(SchemaVersionError)
def _schema_error(exc: SchemaVersionError):
    if request.method != "GET" or request.is_json:
        return jsonify(ok=False, error=str(exc)), 409
    return render_template(
        "error.html",
        title="Week data needs a newer application",
        message=str(exc),
    ), 409


@app.errorhandler(413)
def _too_large(_exc):
    message = "The submitted week is too large. Shorten the content and try again."
    if request.is_json:
        return jsonify(ok=False, error=message), 413
    return render_template(
        "error.html", title="Submission too large", message=message
    ), 413


def _slug(text: str) -> str:
    """Filename-safe slug from a week label, e.g. 'Trinity Sunday — May 31, 2026'
    -> 'trinity-sunday-may-31-2026'. Falls back to empty string."""
    s = (text or "").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def _pdf_response(pdf: bytes, kind: str, label: str) -> Response:
    """Build a PDF response. ``?dl=1`` -> attachment with a stamped filename;
    otherwise inline for in-browser preview."""
    download = request.args.get("dl") == "1"
    disposition = "attachment" if download else "inline"
    slug = _slug(label)
    filename = f"{kind}-{slug}.pdf" if slug else f"{kind}.pdf"
    return Response(
        pdf,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
    )


@app.before_request
def _ensure_schema():
    # Cheap and idempotent; keeps first-run from 500ing on a missing table.
    conn = db.get_connection()
    try:
        db.init_db(conn)
    finally:
        conn.close()


def _get_week_or_404(conn, week_id: int) -> dict:
    week = db.get_week(conn, week_id)
    if week is None:
        abort(404)
    # Normalize on read so weeks saved before a schema addition still have the
    # full canonical shape (new optional sections, etc.) — old rows render and
    # edit without error, and pick up new fields the next time they're saved.
    week["data"] = normalize_blob(week["data"])
    return week


@app.route("/healthz")
def healthz():
    """Liveness + DB-reachability check for deploy scripts / systemd."""
    try:
        conn = db.get_connection()
        try:
            # Verify that the application schema is queryable, not merely that
            # SQLite can open the path.
            conn.execute("SELECT COUNT(*) FROM weeks").fetchone()
        finally:
            conn.close()
    except Exception as exc:  # pragma: no cover - defensive
        return jsonify(ok=False, error=str(exc)), 503
    return jsonify(ok=True)


@app.route("/")
def index():
    conn = db.get_connection()
    try:
        weeks = db.list_weeks(conn)
    finally:
        conn.close()
    return render_template("index.html", weeks=weeks)


@app.route("/weeks/new", methods=["POST"])
def new_week():
    conn = db.get_connection()
    try:
        week_id = db.create_week(conn, normalize_blob(blank_blob()), label="New week")
    finally:
        conn.close()
    return redirect(url_for("edit_week", week_id=week_id))


@app.route("/weeks/new-from-sample", methods=["POST"])
def new_from_sample():
    from sample_data.bulletin_data import STANDING, WEEKLY
    from sample_data.insert_data import INSERT
    conn = db.get_connection()
    try:
        blob = normalize_blob(db.make_blob(WEEKLY, STANDING, INSERT))
        week_id = db.create_week(conn, blob)
    finally:
        conn.close()
    return redirect(url_for("edit_week", week_id=week_id))


@app.route("/weeks/<int:week_id>/clone", methods=["POST"])
def clone(week_id: int):
    conn = db.get_connection()
    try:
        source = _get_week_or_404(conn, week_id)
        new_id = db.create_week(conn, source["data"], label=source["label"])
    finally:
        conn.close()
    return redirect(url_for("edit_week", week_id=new_id))


@app.route("/weeks/<int:week_id>/delete", methods=["POST"])
def delete(week_id: int):
    conn = db.get_connection()
    try:
        db.delete_week(conn, week_id)
    finally:
        conn.close()
    return redirect(url_for("index"))


@app.route("/weeks/<int:week_id>/edit")
def edit_week(week_id: int):
    conn = db.get_connection()
    try:
        week = _get_week_or_404(conn, week_id)
    finally:
        conn.close()
    return render_template(
        "form.html",
        week=week,
        data=week["data"],
        creeds=CREEDS,
    )


@app.route("/weeks/<int:week_id>", methods=["POST"])
def save_week(week_id: int):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(ok=False, error="expected a JSON object"), 400
    blob = normalize_blob(payload)
    conn = db.get_connection()
    try:
        _get_week_or_404(conn, week_id)
        db.update_week(conn, week_id, blob)
    finally:
        conn.close()
    return jsonify(ok=True, id=week_id, label=db.derive_label(blob))


@app.route("/weeks/<int:week_id>/generate")
def generate(week_id: int):
    conn = db.get_connection()
    try:
        week = _get_week_or_404(conn, week_id)
    finally:
        conn.close()
    return render_template("generate.html", week=week)


@app.route("/weeks/<int:week_id>/bulletin.pdf")
def bulletin_pdf(week_id: int):
    conn = db.get_connection()
    try:
        week = _get_week_or_404(conn, week_id)
    finally:
        conn.close()
    d = week["data"]
    pdf = render_bulletin_pdf(d["weekly"], d["standing"])
    return _pdf_response(pdf, "bulletin", week["label"])


@app.route("/weeks/<int:week_id>/insert.pdf")
def insert_pdf(week_id: int):
    conn = db.get_connection()
    try:
        week = _get_week_or_404(conn, week_id)
    finally:
        conn.close()
    pdf = render_insert_pdf(week["data"]["insert"])
    return _pdf_response(pdf, "insert", week["label"])


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
