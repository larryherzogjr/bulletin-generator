from copy import deepcopy
import re

import app as app_module
import db
from render import PDFLayoutError
from presentation import PresentationGenerationError
from esv import ESVConfigurationError, ESVPassage


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


def test_food_at_grace_checkbox_is_shown_and_preserves_checked_state(client, sample_blob):
    week_id = _seed(client)
    edit = client.get(f"/weeks/{week_id}/edit")
    assert b"Food at Grace?" in edit.data
    assert b'data-key="weekly.food_at_grace"' in edit.data

    payload = deepcopy(sample_blob)
    payload["weekly"]["food_at_grace"] = True
    assert client.post(f"/weeks/{week_id}", json=payload).status_code == 200

    checked = client.get(f"/weeks/{week_id}/edit")
    assert re.search(
        rb'<input type="checkbox" data-key="weekly\.food_at_grace"[^>]*checked',
        checked.data,
    )


def test_week_can_be_protected_and_then_cannot_be_deleted(client):
    week_id = _seed(client)

    protected = client.post(
        f"/weeks/{week_id}/protection", json={"protected": True}
    )
    assert protected.status_code == 200
    assert protected.get_json()["protected"] is True

    index = client.get("/")
    assert b'class="week-row is-protected"' in index.data
    assert b'class="protect-week-checkbox"' in index.data
    assert re.search(rb'class="btn small danger"[^>]*disabled', index.data)

    rejected = client.post(f"/weeks/{week_id}/delete")
    assert rejected.status_code == 409
    conn = db.get_connection()
    try:
        assert conn.execute(
            "SELECT protected FROM weeks WHERE id = ?", (week_id,)
        ).fetchone()[0] == 1
    finally:
        conn.close()

    assert client.post(
        f"/weeks/{week_id}/protection", json={"protected": False}
    ).status_code == 200
    assert client.post(f"/weeks/{week_id}/delete").status_code == 302


def test_protection_endpoint_requires_a_boolean(client):
    week_id = _seed(client)
    response = client.post(
        f"/weeks/{week_id}/protection", json={"protected": "yes"}
    )
    assert response.status_code == 400


def test_baptism_announcement_is_an_editable_value_not_placeholder(client):
    week_id = _seed(client)
    edit = client.get(f"/weeks/{week_id}/edit")

    assert b"Johnny Smith, son of Doug &amp; Wanda Smith will be brought" in edit.data
    assert b'placeholder="Benjamin Ernest Melvin' not in edit.data


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


def test_grace_powerpoint_download_headers(client, monkeypatch):
    _seed(client)
    monkeypatch.setattr(
        app_module,
        "render_grace_presentation",
        lambda _data: b"PK\x03\x04presentation",
    )

    response = client.get("/weeks/1/grace-presentation.pptx")

    assert response.status_code == 200
    assert response.content_type == (
        "application/vnd.openxmlformats-officedocument."
        "presentationml.presentation"
    )
    assert response.headers["Content-Disposition"].startswith("attachment;")
    assert "grace-presentation-trinity-sunday" in response.headers["Content-Disposition"]


def test_powerpoint_generation_error_is_actionable(client, monkeypatch):
    _seed(client)

    def fail(_data):
        raise PresentationGenerationError("Add two scripture lesson references.")

    monkeypatch.setattr(app_module, "render_grace_presentation", fail)
    response = client.get("/weeks/1/grace-presentation.pptx")

    assert response.status_code == 422
    assert response.content_type.startswith("text/html")
    assert b"Add two scripture lesson references" in response.data


def test_esv_lookup_endpoint_returns_transient_passages(client, monkeypatch):
    _seed(client)

    def lookup(references):
        return [
            ESVPassage(reference, reference, f"<sup>{index}</sup>{reference} text. (ESV)")
            for index, reference in enumerate(references, start=1)
        ]

    monkeypatch.setattr(app_module, "lookup_esv_passages", lookup)
    response = client.post(
        "/api/esv/passages",
        json={"references": ["Psalm 8", "John 3:16", "Romans 8:1", "Mark 1:1"]},
    )

    assert response.status_code == 200
    passages = response.get_json()["passages"]
    assert len(passages) == 4
    assert passages[2]["heading"] == "Epistle Lesson"
    assert passages[3]["heading"] == "Gospel Lesson"
    assert passages[0]["text"].endswith("(ESV)")


def test_esv_lookup_configuration_error_is_json(client, monkeypatch):
    _seed(client)

    def fail(_references):
        raise ESVConfigurationError("Set ESV_API_KEY on the server.")

    monkeypatch.setattr(app_module, "lookup_esv_passages", fail)
    response = client.post("/api/esv/passages", json={"references": ["Psalm 8"]})

    assert response.status_code == 503
    assert response.is_json
    assert "ESV_API_KEY" in response.get_json()["error"]


def test_saving_automatic_esv_mode_does_not_store_passage_text(client, sample_blob):
    week_id = _seed(client)
    payload = deepcopy(sample_blob)
    payload["weekly"]["scripture_text_source"] = "esv"

    response = client.post(f"/weeks/{week_id}", json=payload)
    assert response.status_code == 200

    conn = db.get_connection()
    try:
        stored = db.get_week(conn, week_id)["data"]
    finally:
        conn.close()
    assert stored["weekly"]["scripture_text_source"] == "esv"
    assert stored["weekly"]["memory_verse_text"] == ""
    assert stored["weekly"]["large_print"]["first_lesson_text"] == ""
    assert stored["insert"]["memory_verse_text"] == ""
