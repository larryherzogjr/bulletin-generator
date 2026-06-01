"""Flask app for the Grace & Zion bulletin generator (milestones 3–4).

Routes
  GET  /                      list weeks (newest first)
  POST /weeks/new             create a blank week            -> redirect to edit
  POST /weeks/new-from-sample seed a week from sample_data   -> redirect to edit
  POST /weeks/<id>/clone      clone a week                   -> redirect to edit
  POST /weeks/<id>/delete     delete a week                  -> redirect to index
  GET  /weeks/<id>/edit       the sectioned edit form
  POST /weeks/<id>            save the form (JSON body)      -> JSON {ok, id}
  GET  /weeks/<id>/generate   the download screen (two PDFs + duplex reminder)
  GET  /weeks/<id>/bulletin.pdf   [?dl=1 -> attachment]
  GET  /weeks/<id>/insert.pdf     [?dl=1 -> attachment]

The form posts the whole blob as JSON (built client-side by form.js), which
keeps deeply-nested, variable-length structures — events, lessons,
announcements — straightforward versus flat form-encoded names. The server
normalizes defensively (schema.normalize_blob) before persisting.

Download policy (M4): the secretary downloads the two PDFs separately (no
bundle — confirmed with the user, since they print on different paper/settings).
Plain PDF routes render inline for quick preview; add ``?dl=1`` to force a
download with a friendly, week-stamped filename.
"""

from __future__ import annotations

import re

from flask import (
    Flask, Response, abort, jsonify, redirect, render_template, request, url_for,
)

import db
from schema import CREEDS, blank_blob, normalize_blob
from render import render_bulletin_pdf, render_insert_pdf

app = Flask(__name__)


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
    return week


@app.route("/healthz")
def healthz():
    """Liveness + DB-reachability check for deploy scripts / systemd."""
    try:
        conn = db.get_connection()
        try:
            conn.execute("SELECT 1").fetchone()
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
        _get_week_or_404(conn, week_id)
        new_id = db.clone_week(conn, week_id)
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
