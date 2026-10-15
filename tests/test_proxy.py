"""Both URL mounts must work against the same data without leaking root URLs."""

import re

import pytest

import app as app_module


@pytest.mark.parametrize("prefix", ["", "/bulletin"])
def test_mount_workflow(client, sample_blob, monkeypatch, prefix):
    base = "https://home.grace"
    headers = {"Origin": base, "Sec-Fetch-Site": "same-origin"}
    created = client.post(prefix + "/weeks/new", base_url=base, headers=headers)
    assert created.status_code == 302
    edit_url = created.headers["Location"]
    assert re.fullmatch(re.escape(prefix) + r"/weeks/\d+/edit", edit_url)
    week_url = edit_url.removesuffix("/edit")

    for path in ["/", "/healthz", "/static/style.css", "/static/form.js",
                 "/static/data/ambassador_hymns.json"]:
        assert client.get(prefix + path, base_url=base).status_code == 200

    edit = client.get(edit_url, base_url=base)
    assert edit.status_code == 200
    for attribute, path in [("href", "/"), ("data-save-url", week_url[len(prefix):]),
                            ("data-esv-url", "/api/esv/passages"),
                            ("data-hymn-library-url", "/static/data/ambassador_hymns.json")]:
        assert f'{attribute}="{prefix}{path}"'.encode() in edit.data
    saved = client.post(week_url, base_url=base, headers=headers, json=sample_blob)
    assert saved.status_code == 200
    assert client.post(week_url, base_url=base, json=sample_blob,
                       headers={"Origin": "https://other.example"}).status_code == 403

    generate = client.get(week_url + "/generate", base_url=base)
    assert f'href="{week_url}/bulletin.pdf?dl=1"'.encode() in generate.data
    monkeypatch.setattr(app_module, "render_bulletin_pdf", lambda *args, **kwargs: b"%PDF-test")
    pdf = client.get(week_url + "/bulletin.pdf?dl=1", base_url=base)
    assert pdf.status_code == 200
    assert pdf.headers["Content-Disposition"].startswith("attachment;")

    # The other mount reads the very same week, and generates its own URLs.
    other_prefix = "" if prefix else "/bulletin"
    other_url = other_prefix + week_url[len(prefix):]
    assert client.get(other_url + "/edit", base_url=base).status_code == 200
    deleted = client.post(week_url + "/delete", base_url=base, headers=headers)
    assert deleted.headers["Location"] == prefix + "/"


def test_direct_access_does_not_trust_forwarded_prefix_or_host(client):
    response = client.get("/", headers={"X-Forwarded-Prefix": "/attacker",
                                        "X-Forwarded-Host": "other.example"})
    assert b'action="/weeks/new"' in response.data
    assert b"/attacker" not in response.data
    assert client.get("/bulletin-other/").status_code == 404
