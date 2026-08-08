from copy import deepcopy

import app as app_module
import db
from render import PDFLayoutError


def _seed(client):
    response = client.post("/weeks/new-from-sample")
    assert response.status_code == 302
    return 1


def test_full_http_flow_and_download_headers(client, sample_blob):
    assert client.get("/healthz").get_json() == {"ok": True}
    index = client.get("/")
    assert index.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in index.headers["Content-Security-Policy"]
    assert index.headers["Cache-Control"] == "no-store"
    week_id = _seed(client)

    assert client.get(f"/weeks/{week_id}/edit").status_code == 200
    assert client.get(f"/weeks/{week_id}/generate").status_code == 200

    payload = deepcopy(sample_blob)
    payload["weekly"]["liturgical_day"] = "First Sunday"
    saved = client.post(f"/weeks/{week_id}", json=payload)
    assert saved.status_code == 200
    assert saved.get_json()["label"] == "First Sunday — May 31, 2026"

    inline = client.get(f"/weeks/{week_id}/bulletin.pdf")
    assert inline.status_code == 200
    assert inline.content_type == "application/pdf"
    assert inline.headers["Content-Disposition"].startswith("inline;")

    download = client.get(f"/weeks/{week_id}/insert.pdf?dl=1")
    assert download.status_code == 200
    assert download.headers["Content-Disposition"].startswith("attachment;")
    assert "first-sunday-may-31-2026" in download.headers["Content-Disposition"]

    large_print = client.get(f"/weeks/{week_id}/large-print.pdf?dl=1")
    assert large_print.status_code == 200
    assert large_print.content_type == "application/pdf"
    assert large_print.headers["Content-Disposition"].startswith("attachment;")
    assert "large-print-booklet-first-sunday" in large_print.headers["Content-Disposition"]

    assert client.get("/weeks/999/edit").status_code == 404


def test_cross_origin_write_is_rejected(client):
    rejected = client.post(
        "/weeks/new",
        headers={"Origin": "https://attacker.example", "Sec-Fetch-Site": "cross-site"},
    )
    assert rejected.status_code == 403

    conn = db.get_connection()
    try:
        db.init_db(conn)
        assert db.list_weeks(conn) == []
    finally:
        conn.close()

    accepted = client.post("/weeks/new", headers={"Origin": "http://localhost"})
    assert accepted.status_code == 302


def test_json_request_size_limit_returns_actionable_error(client):
    _seed(client)
    old_limit = app_module.app.config["MAX_CONTENT_LENGTH"]
    app_module.app.config["MAX_CONTENT_LENGTH"] = 100
    try:
        response = client.post("/weeks/1", json={"weekly": {"date": "x" * 1000}})
    finally:
        app_module.app.config["MAX_CONTENT_LENGTH"] = old_limit

    assert response.status_code == 413
    assert response.get_json()["ok"] is False


def test_pdf_layout_error_is_shown_instead_of_bad_pdf(client, monkeypatch):
    _seed(client)

    def fail(*_args, **_kwargs):
        raise PDFLayoutError("bulletin", "Shorten the content.")

    monkeypatch.setattr(app_module, "render_bulletin_pdf", fail)
    response = client.get("/weeks/1/bulletin.pdf")

    assert response.status_code == 422
    assert response.content_type.startswith("text/html")
    assert b"Shorten the content" in response.data
