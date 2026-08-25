import json
from pathlib import Path

import pytest

from scripts.import_ambassador_hymns import (
    HYMN_COUNT,
    HYMNS_254_255_MARKER,
    build_library,
)


BASE_DIR = Path(__file__).resolve().parents[1]
LIBRARY_PATH = BASE_DIR / "static" / "data" / "ambassador_hymns.json"


def _representative_source() -> str:
    blocks = [f"1 Representative hymn {number}" for number in range(1, HYMN_COUNT + 1)]
    blocks[0] = "1 Lift up your heads, ye mighty gates,\nFirst hymn text"
    blocks[253] = ""
    blocks[254] = (
        "1 Abide in grace, Lord Jesus,\nHymn 254 text\n\n"
        f"{HYMNS_254_255_MARKER}\nHymn 255 text"
    )
    blocks[255] = "1 The day Thou gavest, Lord, is ended,\nHymn 256 text"
    blocks[633] = "1 O Canada! our home and native land!\nLast hymn text"
    return "\f".join(blocks)


def test_importer_repairs_the_combined_254_and_255_source_block():
    library = build_library(_representative_source())

    assert list(library) == [str(number) for number in range(1, HYMN_COUNT + 1)]
    assert library["254"] == "1 Abide in grace, Lord Jesus,\nHymn 254 text"
    assert library["255"] == f"{HYMNS_254_255_MARKER}\nHymn 255 text"
    assert library["256"].startswith("1 The day Thou gavest")


def test_importer_rejects_an_unexpected_source_structure():
    source = _representative_source().replace("\f\f", "\fUnexpected\f", 1)

    with pytest.raises(ValueError, match="blank source position 254"):
        build_library(source)


def test_generated_ambassador_library_is_complete_and_numbered():
    library = json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))

    assert list(library) == [str(number) for number in range(1, HYMN_COUNT + 1)]
    assert all(text.strip() for text in library.values())
    assert library["1"].startswith("1 Lift up your heads, ye mighty gates,")
    assert library["254"].startswith("1 Abide in grace, Lord Jesus,")
    assert library["255"].startswith(HYMNS_254_255_MARKER)
    assert library["256"].startswith("1 The day Thou gavest, Lord, is ended,")
    assert library["634"].startswith("1 O Canada! our home and native land!")


def test_editor_exposes_only_grace_hymn_lookup_controls(client):
    client.post("/weeks/new")

    response = client.get("/weeks/1/edit")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'data-hymn-library-url="/static/data/ambassador_hymns.json"' in html
    assert html.count("data-hymn-number") == 3
    assert "weekly.large_print.opening_hymn_text" in html
    assert "weekly.large_print.sermon_hymn_text" in html
    assert "weekly.large_print.closing_hymn_text" in html
    assert "weekly.opening_hymn.zion.num\" data-hymn-number" not in html
    assert html.count("data-zion-hymn-row") == 3
    assert html.count("data-zion-hymnal") == 3

    static_response = client.get("/static/data/ambassador_hymns.json")
    assert static_response.status_code == 200
    assert len(static_response.get_json()) == HYMN_COUNT


def test_editor_splits_existing_zion_hymn_number_and_hymnal(client):
    client.post("/weeks/new-from-sample")

    response = client.get("/weeks/1/edit")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'data-zion-hymn-key="weekly.opening_hymn.zion.num"' in html
    assert 'placeholder="Zion #" value="59"' in html
    assert '<option value="Green" selected>Green</option>' in html
