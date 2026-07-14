from copy import deepcopy
from io import BytesIO

import pytest
from pypdf import PdfReader

from render import (
    PDFLayoutError,
    render_bulletin_html,
    render_bulletin_pdf,
    render_insert_pdf,
)


def _page_sizes(pdf):
    reader = PdfReader(BytesIO(pdf))
    return [
        (float(page.mediabox.width), float(page.mediabox.height))
        for page in reader.pages
    ]


def _font_names(pdf):
    names = set()
    for page in PdfReader(BytesIO(pdf)).pages:
        fonts = page["/Resources"].get("/Font", {}).get_object()
        for font_ref in fonts.values():
            names.add(str(font_ref.get_object().get("/BaseFont", "")))
    return names


def test_sample_pdfs_have_exact_print_geometry_and_text(sample_blob):
    bulletin = render_bulletin_pdf(sample_blob["weekly"], sample_blob["standing"])
    insert = render_insert_pdf(sample_blob["insert"])

    assert _page_sizes(bulletin) == [(792.0, 612.0)]
    assert _page_sizes(insert) == [(396.0, 612.0), (396.0, 612.0)]
    assert "SUNDAY MORNING WORSHIP" in PdfReader(BytesIO(bulletin)).pages[0].extract_text()
    assert "Message & Notes" in PdfReader(BytesIO(insert)).pages[1].extract_text()
    assert any("Liberation-Sans" in name for name in _font_names(bulletin))
    assert any("Liberation-Serif" in name for name in _font_names(insert))


def test_rich_text_allowlist_escapes_non_formatting_markup(sample_blob):
    weekly = deepcopy(sample_blob["weekly"])
    weekly["special_music"] = "<b>Allowed</b><img src=x><script>bad()</script>"

    html = render_bulletin_html(weekly, sample_blob["standing"])

    assert "<b>Allowed</b>" in html
    assert "&lt;img src=x&gt;" in html
    assert "&lt;script&gt;bad()&lt;/script&gt;" in html


def test_bulletin_overflow_fails_closed(sample_blob):
    weekly = deepcopy(sample_blob["weekly"])
    weekly["grace_events"] = [
        [f"Day {day}", [["Very long event name " * 4, "11:59 PM"]] * 5]
        for day in range(20)
    ]

    with pytest.raises(PDFLayoutError, match="too long"):
        render_bulletin_pdf(weekly, sample_blob["standing"])


def test_insert_overflow_fails_closed(sample_blob):
    insert = deepcopy(sample_blob["insert"])
    insert["announcements"] = [
        {"heading": f"Announcement {number}", "body": "Long body " * 400}
        for number in range(12)
    ]

    with pytest.raises(PDFLayoutError, match="exactly two"):
        render_insert_pdf(insert)
