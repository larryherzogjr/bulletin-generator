from copy import deepcopy
from io import BytesIO
import json

import pytest
from pypdf import PdfReader
from weasyprint import HTML

from render import (
    BASE_DIR,
    PDFLayoutError,
    _iter_boxes,
    render_bulletin_html,
    render_bulletin_pdf,
    render_insert_html,
    render_insert_pdf,
    render_large_print_content_html,
    render_large_print_pdf,
)
from schema import DEFAULT_BAPTISM_BULLETIN_TEXT


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


def _outer_height_for_class(html, class_name):
    document = HTML(string=html, base_url=str(BASE_DIR)).render()
    for box in _iter_boxes(document.pages[0]._page_box):
        element = getattr(box, "element", None)
        classes = (element.get("class") or "").split() if element is not None else []
        if class_name in classes:
            return (
                box.height
                + box.padding_top
                + box.padding_bottom
                + box.border_top_width
                + box.border_bottom_width
            )
    raise AssertionError(f"class not found in rendered document: {class_name}")


def test_sample_pdfs_have_exact_print_geometry_and_text(sample_blob):
    bulletin = render_bulletin_pdf(sample_blob["weekly"], sample_blob["standing"])
    insert = render_insert_pdf(sample_blob["insert"])

    assert _page_sizes(bulletin) == [(792.0, 612.0)]
    assert _page_sizes(insert) == [(792.0, 612.0)]
    assert "SUNDAY MORNING WORSHIP" in PdfReader(BytesIO(bulletin)).pages[0].extract_text()
    insert_text = PdfReader(BytesIO(insert)).pages[0].extract_text()
    assert "Please be" not in insert_text
    assert "Pray" in insert_text
    assert "HOME:" in insert_text
    assert "Message & Notes" in insert_text
    assert any("Liberation-Sans" in name for name in _font_names(bulletin))
    assert any("Liberation-Serif" in name for name in _font_names(insert))


def test_large_print_booklet_has_tabloid_imposition_and_full_text(sample_blob):
    booklet = render_large_print_pdf(
        sample_blob["weekly"], sample_blob["standing"], sample_blob["insert"]
    )

    assert _page_sizes(booklet) == [(1224.0, 792.0)] * 4
    text = "\n".join(
        page.extract_text() for page in PdfReader(BytesIO(booklet)).pages
    )
    assert "Message & Notes" in text
    assert "SUNDAY MORNING WORSHIP" in text
    assert "COMING EVENTS AT GRACE" in text
    assert "Call to Worship: Psalm 8" in text
    assert "O God the Father in heaven" in text
    assert "Confession of Faith: Nicene Creed" in text
    assert "Glory be to the Father" in text
    assert "Praise God from Whom all blessings flow" in text


def test_large_print_uses_the_selected_editable_creed(sample_blob):
    weekly = deepcopy(sample_blob["weekly"])
    standing = deepcopy(sample_blob["standing"])
    weekly["confession_of_faith"] = "Apostles' Creed"
    standing["creed_texts"]["apostles"] = "CUSTOM APOSTLES WORDING"

    html = render_large_print_content_html(weekly, standing)

    assert "Confession of Faith: Apostles' Creed" in html
    assert "CUSTOM APOSTLES WORDING" in html


def test_large_print_scripture_lessons_wrap_as_continuous_prose(sample_blob):
    weekly = deepcopy(sample_blob["weekly"])
    weekly["large_print"]["first_lesson_text"] = "First verse.\nSecond verse."

    html = render_large_print_content_html(weekly, sample_blob["standing"])

    assert ".text.scripture-text { white-space: normal; }" in html
    assert '<div class="text scripture-text">First verse.\nSecond verse.</div>' in html
    assert '<div class="text">' in html


def test_large_print_renders_text_from_the_ambassador_library(sample_blob):
    library_path = BASE_DIR / "static" / "data" / "ambassador_hymns.json"
    library = json.loads(library_path.read_text(encoding="utf-8"))
    weekly = deepcopy(sample_blob["weekly"])
    weekly["opening_hymn"]["grace"]["num"] = "254"
    weekly["large_print"]["opening_hymn_text"] = library["254"]

    html = render_large_print_content_html(weekly, sample_blob["standing"])

    assert "Hymn #254" in html
    assert "Abide in grace, Lord Jesus" in html
    assert "Print Thine image" not in html


def test_large_print_uniformly_reduces_below_the_old_floor_until_content_fits(
    sample_blob,
):
    weekly = deepcopy(sample_blob["weekly"])
    weekly["large_print"]["call_to_worship_text"] += (
        " Additional full-text sentence for fitting." * 300
        + " FINAL DENSE CONTENT"
    )
    at_old_floor = HTML(
        string=render_large_print_content_html(
            weekly, sample_blob["standing"], scale=0.80
        ),
        base_url=str(BASE_DIR),
    ).render()
    assert len(at_old_floor.pages) > 4

    booklet = render_large_print_pdf(
        weekly, sample_blob["standing"], sample_blob["insert"]
    )

    assert _page_sizes(booklet) == [(1224.0, 792.0)] * 4
    assert "FINAL DENSE CONTENT" in "\n".join(
        page.extract_text() for page in PdfReader(BytesIO(booklet)).pages
    )


def test_insert_prayer_box_has_larger_minimum_and_can_grow_to_half_page(sample_blob):
    insert = deepcopy(sample_blob["insert"])
    minimum_height = _outer_height_for_class(render_insert_html(insert), "praybox")
    assert minimum_height >= 3.19 * 96

    insert["announcements"] = []
    insert["bold_notes"] = []
    insert["next_readings"] = []
    insert["prayer_tail"] += " Additional prayer request." * 25
    expanded_height = _outer_height_for_class(render_insert_html(insert), "praybox")
    assert expanded_height >= 4.2 * 96
    assert _page_sizes(render_insert_pdf(insert)) == [(792.0, 612.0)]


def test_service_notices_render_under_their_bulletin_event_headings(sample_blob):
    weekly = deepcopy(sample_blob["weekly"])
    weekly["communion"] = {"enabled": True, "grace": True, "zion": True}
    weekly["baptism"] = {
        "enabled": True,
        "text": "Melvin Family",
        "bulletin_text": "Benjamin Ernest Melvin will be brought to the Lord in Baptism.",
    }

    html = render_bulletin_html(weekly, sample_blob["standing"])

    grace = html.index("COMING EVENTS AT GRACE")
    first_communion = html.index("Today is Communion Sunday.", grace)
    baptism = html.index("Baptized Today ~", first_communion)
    grace_banner = html.index(weekly["grace_events_banner"], baptism)
    zion = html.index("COMING EVENTS AT ZION", grace_banner)
    second_communion = html.index("Today is Communion Sunday.", zion)
    assert grace < first_communion < baptism < grace_banner < zion < second_communion
    assert html.count("Today is Communion Sunday.") == 2
    assert "Benjamin Ernest Melvin will be brought" in html
    assert "Today is Communion Sunday." not in render_insert_html(sample_blob["insert"])
    assert _page_sizes(render_bulletin_pdf(weekly, sample_blob["standing"])) == [
        (792.0, 612.0)
    ]


def test_default_baptism_announcement_renders_once_below_grace_heading(sample_blob):
    weekly = deepcopy(sample_blob["weekly"])
    weekly["baptism"]["enabled"] = True

    html = render_bulletin_html(weekly, sample_blob["standing"])

    assert html.count("Baptized Today ~") == 1
    assert "Johnny Smith, son of Doug &amp; Wanda Smith will be brought" in html
    assert DEFAULT_BAPTISM_BULLETIN_TEXT.replace("&", "&amp;") in html


def test_communion_notice_respects_each_parish_checkbox(sample_blob):
    weekly = deepcopy(sample_blob["weekly"])

    weekly["communion"] = {"enabled": True, "grace": True, "zion": False}
    grace_only = render_bulletin_html(weekly, sample_blob["standing"])
    assert grace_only.count("Today is Communion Sunday.") == 1
    assert grace_only.index("COMING EVENTS AT GRACE") < grace_only.index(
        "Today is Communion Sunday."
    ) < grace_only.index("COMING EVENTS AT ZION")

    weekly["communion"] = {"enabled": True, "grace": False, "zion": True}
    zion_only = render_bulletin_html(weekly, sample_blob["standing"])
    assert zion_only.count("Today is Communion Sunday.") == 1
    assert zion_only.index("COMING EVENTS AT ZION") < zion_only.index(
        "Today is Communion Sunday."
    )


def test_different_zion_hymn_title_shares_its_number_row(sample_blob):
    weekly = deepcopy(sample_blob["weekly"])
    weekly["opening_hymn"] = {
        "grace": {"num": "", "title": "Yet Not I, But Christ in Me"},
        "zion": {"num": "35 (Green)", "title": "Immortal, Invisible, God Only Wise"},
    }

    html = render_bulletin_html(weekly, sample_blob["standing"])
    row_start = html.index('<div class="hymn-line zion-line">')
    row_end = html.index("</div>", row_start)
    zion_row = html[row_start:row_end]

    assert "Zion #35 (Green)" in zion_row
    assert "Immortal, Invisible, God Only Wise" in zion_row


def test_rich_text_allowlist_escapes_non_formatting_markup(sample_blob):
    weekly = deepcopy(sample_blob["weekly"])
    weekly["special_music"] = "<b>Allowed</b><img src=x><script>bad()</script>"

    html = render_bulletin_html(weekly, sample_blob["standing"])

    assert "<b>Allowed</b>" in html
    assert "&lt;img src=x&gt;" in html
    assert "&lt;script&gt;bad()&lt;/script&gt;" in html


def test_generated_scripture_hides_verse_numbers_but_keeps_esv_attribution(sample_blob):
    weekly = deepcopy(sample_blob["weekly"])
    weekly["memory_verse_text"] = "<sup>6</sup>Humble yourselves. (ESV)"
    weekly["large_print"]["first_lesson_text"] = (
        "<sup>14</sup>Peter stood and spoke. (ESV)"
    )

    bulletin_html = render_bulletin_html(weekly, sample_blob["standing"])
    large_print_html = render_large_print_content_html(weekly, sample_blob["standing"])

    assert "<sup>6</sup>" not in bulletin_html
    assert "Humble yourselves. (ESV)" in bulletin_html
    assert "<sup>14</sup>" not in large_print_html
    assert "Peter stood and spoke. (ESV)" in large_print_html


def test_bulletin_overflow_fails_closed(sample_blob):
    weekly = deepcopy(sample_blob["weekly"])
    weekly["grace_events"] = [
        [f"Day {day}", [["Very long event name " * 4, "11:59 PM"]] * 5]
        for day in range(20)
    ]

    with pytest.raises(PDFLayoutError, match="too long"):
        render_bulletin_pdf(weekly, sample_blob["standing"])


def test_bulletin_uses_holy_communion_wording(sample_blob):
    weekly = deepcopy(sample_blob["weekly"])
    weekly["communion"] = {"enabled": True, "grace": True, "zion": True}

    pdf = render_bulletin_pdf(weekly, sample_blob["standing"])
    text = PdfReader(BytesIO(pdf)).pages[0].extract_text()

    assert "HOLY COMMUNION ~ Grace and Zion" in text


def test_insert_overflow_fails_closed(sample_blob):
    insert = deepcopy(sample_blob["insert"])
    insert["announcements"] = [
        {"heading": f"Announcement {number}", "body": "Long body " * 400}
        for number in range(12)
    ]

    with pytest.raises(PDFLayoutError, match="one 11 x 8.5"):
        render_insert_pdf(insert)


def test_large_print_requires_full_text_and_rejects_overflow(sample_blob):
    weekly = deepcopy(sample_blob["weekly"])
    weekly["large_print"]["opening_hymn_text"] = ""
    with pytest.raises(PDFLayoutError, match="first hymn"):
        render_large_print_pdf(weekly, sample_blob["standing"], sample_blob["insert"])

    weekly = deepcopy(sample_blob["weekly"])
    weekly["large_print"]["call_to_worship_text"] = "Very long Psalm text. " * 8000
    with pytest.raises(PDFLayoutError, match="four reading pages"):
        render_large_print_pdf(weekly, sample_blob["standing"], sample_blob["insert"])
