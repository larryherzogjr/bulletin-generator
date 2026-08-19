"""Render the Grace & Zion bulletin and insert templates into print-ready PDFs.

This module wires the two verified Jinja2 templates
(``templates/bulletin_template.html`` and ``templates/insert_template.html``)
into plain functions that take the data dicts and return PDF bytes. The Flask
app and SQLite-backed form all funnel through these functions, so
the layout has exactly one source of truth.

Template variable contract (matches the templates as written):
  * bulletin_template.html expects ``w`` (the WEEKLY dict) and ``s`` (STANDING).
  * insert_template.html   expects ``i`` (the INSERT dict).

Autoescaping is ON for .html templates. A finalizer escapes every string, then
re-enables only a small attribute-free formatting allowlist (``b``, ``i``,
``u``, ``sup``, and related tags). Secretary-entered text therefore supports
the documented inline formatting without allowing arbitrary markup.
"""

import re
from copy import copy
from io import BytesIO
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup
from pypdf import PdfReader, PdfWriter, PageObject, Transformation
from pypdf.generic import RectangleObject
from weasyprint import HTML

from schema import CREED_KEYS

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"

# --- Rich text: allow a small set of inline formatting tags in ANY field ------
#
# The secretary can type <b>bold</b>, <i>italic</i>, <u>underline</u>,
# <sup>/<sub>, etc. in any text field. Everything else is escaped, so a stray
# "<" or a pasted "<script>..." is shown literally and never interpreted — the
# layout can't be broken and no markup can be injected. Attributes are not
# allowed (e.g. "<b onclick=...>" won't match and stays escaped as text).
_RICH_TAGS = ("b", "i", "u", "sup", "sub", "strong", "em", "s", "small", "br")

# Escape a "&" only when it does NOT already begin a valid entity, so existing
# data like "Todd &amp; Barb" or "&ldquo;" is preserved (not double-escaped)
# while a typed "Jim & Sharon" still becomes a safe &amp;.
_BARE_AMP = re.compile(r"&(?!(?:[a-zA-Z][a-zA-Z0-9]*|#[0-9]+|#x[0-9a-fA-F]+);)")

# After escaping, re-enable ONLY the allowlisted tags: <b>, </b>, <br>, <br/>…
_RICH_RE = re.compile(
    r"&lt;\s*(/?)\s*(%s)\s*/?\s*&gt;" % "|".join(_RICH_TAGS), re.IGNORECASE
)

_SCRIPTURE_VERSE_TAG = re.compile(
    r"<sup\b[^>]*>\s*\d{1,3}[a-z]?\s*</sup>", re.IGNORECASE
)
_SCRIPTURE_VERSE_SPAN = re.compile(
    r"<span\b[^>]*class\s*=\s*['\"][^'\"]*\bverse(?:-number|-num|num)?\b"
    r"[^'\"]*['\"][^>]*>[\s\S]*?</span>",
    re.IGNORECASE,
)
_SCRIPTURE_BRACKET_NUMBER = re.compile(r"\[\s*\d{1,3}[a-z]?\s*\]", re.IGNORECASE)
_SCRIPTURE_SUPERSCRIPT_NUMBER = re.compile(r"[⁰¹²³⁴⁵⁶⁷⁸⁹]+")


def rich(value) -> Markup:
    """Escape user text, then re-enable an allowlist of inline formatting tags.

    Returns Markup so the (now-safe) result isn't escaped again downstream.
    """
    if value is None:
        return Markup("")
    s = str(value)
    s = _BARE_AMP.sub("&amp;", s)
    s = s.replace("<", "&lt;").replace(">", "&gt;")
    s = _RICH_RE.sub(lambda m: "<%s%s>" % (m.group(1), m.group(2).lower()), s)
    return Markup(s)


def scripture_visible(value) -> Markup:
    """Render Scripture wording while keeping verse markers out of print."""
    text = str(value or "")
    text = _SCRIPTURE_VERSE_TAG.sub("", text)
    text = _SCRIPTURE_VERSE_SPAN.sub("", text)
    text = _SCRIPTURE_BRACKET_NUMBER.sub("", text)
    text = _SCRIPTURE_SUPERSCRIPT_NUMBER.sub("", text)
    return rich(text)


def _finalize(value):
    """Applied to every {{ }} output: give plain strings rich formatting, but
    leave Markup untouched so rendered fragments (e.g. the hymn macro, or values
    already marked |safe) are not re-escaped."""
    if isinstance(value, str) and not isinstance(value, Markup):
        return rich(value)
    return value


_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
    finalize=_finalize,
)
_env.filters["rich"] = rich
_env.filters["scripture_visible"] = scripture_visible


# Shrink-to-fit bounds for the bulletin. The inside must stay on ONE sheet; if a
# busy week (baptism, lots of events, long standing text) would spill to a second
# page, we re-render at a smaller scale until it fits. MIN_SCALE keeps it legible
# (~84% -> about 8.8pt body); STEP is the shrink increment per attempt.
_MIN_SCALE = 0.84
_SCALE_STEP = 0.02

# CSS pixels (WeasyPrint uses 96px/in). These are part of the print contract,
# not incidental template details.
_PAGE_HEIGHT = 8.5 * 96
_BULLETIN_WIDTH = 11 * 96
_INSERT_WIDTH = 11 * 96

# PDF points used by the imposed large-print booklet. Its four physical PDF
# pages are 17 x 11 inches; each contains two 8.5 x 11 logical pages.
_LETTER_WIDTH_PT = 8.5 * 72
_LETTER_HEIGHT_PT = 11 * 72
_TABLOID_WIDTH_PT = 17 * 72
_TABLOID_HEIGHT_PT = 11 * 72

# Keep every full-text page at one consistent scale. Unlike the original
# bulletin/insert panels, completeness is more important here than enforcing a
# conventional large-print floor, so the renderer may continue below 12.8pt
# when a long Psalm, set of readings, or creed requires it. The emergency floor
# only prevents pathological input from causing an unbounded render loop.
_LARGE_PRINT_MIN_SCALE = 0.25   # 4pt emergency floor for pathological input
_LARGE_PRINT_MAX_SCALE = 1.25   # 20pt expanded-content body
_LARGE_PRINT_SCALE_STEP = 0.025


class PDFLayoutError(RuntimeError):
    """Raised when content cannot satisfy the fixed print layout contract."""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind


def render_bulletin_html(weekly: dict, standing: dict, scale: float = 1.0) -> str:
    """Render the bulletin inside (left: Order of Worship, right: Coming Events).

    ``scale`` (<= 1.0) uniformly shrinks the font and vertical spacing; 1.0 is
    full size. Normally you don't pass this — render_bulletin_pdf picks it.
    """
    return _env.get_template("bulletin_template.html").render(
        w=weekly, s=standing, scale=scale
    )


def render_insert_html(insert: dict) -> str:
    """Render both half-sheet insert sides on one landscape letter sheet."""
    return _env.get_template("insert_template.html").render(i=insert)


def render_large_print_content_html(
    weekly: dict, standing: dict, scale: float = 1.0
) -> str:
    """Render the full-text worship material in normal reading order.

    WeasyPrint paginates this portrait-letter stream naturally. The resulting
    pages become logical booklet pages 3-6 before the final imposition step.
    """
    creed_key = CREED_KEYS.get(weekly.get("confession_of_faith", ""))
    creed_text = standing.get("creed_texts", {}).get(creed_key, "") if creed_key else ""
    return _env.get_template("large_print_content_template.html").render(
        w=weekly,
        lp=weekly.get("large_print", {}),
        lessons=weekly.get("scripture_lessons", []),
        responses=standing.get("large_print_responses", {}),
        creed_text=creed_text,
        scale=scale,
    )


def _iter_boxes(box):
    yield box
    for child in getattr(box, "children", ()) or ():
        yield from _iter_boxes(child)


# Text may consume the bottom padding when needed (better than shrinking the
# whole bulletin), but must stay this far (px, ~0.1in) off the physical panel
# edge so nothing prints flush against the fold/cut line.
_CLIP_SAFETY = 9.6


def _class_box_overflows(document, class_name: str) -> bool:
    """True if text inside a fixed-height class would clip at the bottom.

    The bulletin and insert panels have a fixed 8.5in height. Content can
    therefore cross a physical edge without page-count alone detecting it. We
    allow content to use the bottom padding and retain a small print-safe edge.
    """
    # WeasyPrint has no public clipping-inspection API. This internal traversal
    # is covered by regression tests and WeasyPrint is pinned in constraints.txt.
    from weasyprint.formatting_structure import boxes as _b

    for page in document.pages:
        for box in _iter_boxes(page._page_box):
            el = getattr(box, "element", None)
            classes = (el.get("class") or "").split() if el is not None else []
            if class_name not in classes:
                continue
            edge = (box.position_y + box.padding_top + box.height
                    + box.padding_bottom) - _CLIP_SAFETY
            for inner in _iter_boxes(box):
                if isinstance(inner, (_b.LineBox, _b.TextBox)):
                    if inner.position_y + inner.height > edge:
                        return True
    return False


def _panel_overflows(document) -> bool:
    """Backward-compatible name for the bulletin-specific fit check."""
    return _class_box_overflows(document, "panel")


def _has_expected_geometry(document, pages: int, width: float, height: float) -> bool:
    """Validate page count and physical size before returning printable bytes."""
    if len(document.pages) != pages:
        return False
    return all(
        abs(page.width - width) < 0.01 and abs(page.height - height) < 0.01
        for page in document.pages
    )


def _bulletin_fits(document) -> bool:
    """The inside must be ONE page with nothing clipped out of either panel."""
    return (
        _has_expected_geometry(document, 1, _BULLETIN_WIDTH, _PAGE_HEIGHT)
        and not _panel_overflows(document)
    )


def render_bulletin_pdf(weekly: dict, standing: dict) -> bytes:
    """Bulletin -> PDF bytes. One page, 11x8.5 landscape, single-sided.

    Auto shrink-to-fit: render at full size; if the content spills to a second
    page OR overflows a panel's fixed height (which would clip at print time),
    step the scale down (to _MIN_SCALE) until it fits. The common case (already
    fits) renders once at scale 1.0 with no extra cost.
    """
    scale = 1.0
    document = HTML(
        string=render_bulletin_html(weekly, standing, scale), base_url=str(BASE_DIR)
    ).render()
    while not _bulletin_fits(document) and scale > _MIN_SCALE:
        scale = max(_MIN_SCALE, round(scale - _SCALE_STEP, 3))
        document = HTML(
            string=render_bulletin_html(weekly, standing, scale), base_url=str(BASE_DIR)
        ).render()
    if not _bulletin_fits(document):
        raise PDFLayoutError(
            "bulletin",
            "The bulletin content is too long to fit on one 11 x 8.5 inch "
            "sheet at the minimum legible size. Shorten the worship, events, "
            "or standing text and try again.",
        )
    return document.write_pdf()


def render_insert_pdf(insert: dict) -> bytes:
    """Insert -> PDF bytes. One 11x8.5 landscape sheet with two side-by-side panels."""
    html = render_insert_html(insert)
    document = HTML(string=html, base_url=str(BASE_DIR)).render()
    if (
        not _has_expected_geometry(document, 1, _INSERT_WIDTH, _PAGE_HEIGHT)
        or _class_box_overflows(document, "page")
    ):
        raise PDFLayoutError(
            "insert",
            "The insert content is too long to fit on one 11 x 8.5 inch "
            "landscape sheet. Shorten the prayer list, readings, announcements, "
            "or bold notes and try again.",
        )
    return document.write_pdf()


def _required_large_print_text(weekly: dict, standing: dict) -> None:
    """Fail with an editor-oriented message instead of making empty panels."""
    lp = weekly.get("large_print", {})
    fields = (
        ("call_to_worship_text", "Call to Worship"),
        ("opening_hymn_text", "first hymn"),
        ("first_lesson_text", "first scripture lesson"),
        ("second_lesson_text", "second scripture lesson"),
        ("sermon_hymn_text", "second hymn"),
        ("closing_hymn_text", "third hymn"),
    )
    missing = [label for key, label in fields if not str(lp.get(key, "")).strip()]
    creed = weekly.get("confession_of_faith", "")
    creed_key = CREED_KEYS.get(creed)
    if creed_key and not str(standing.get("creed_texts", {}).get(creed_key, "")).strip():
        missing.append(creed)
    if missing:
        raise PDFLayoutError(
            "large-print booklet",
            "Add the full large-print text for " + ", ".join(missing) + " and try again.",
        )


def _render_large_print_content(weekly: dict, standing: dict):
    """Choose one uniform full-text scale that stays within four pages."""
    def render_at(scale):
        return HTML(
            string=render_large_print_content_html(weekly, standing, scale),
            base_url=str(BASE_DIR),
        ).render()

    scale = 1.0
    document = render_at(scale)

    if len(document.pages) > 4:
        # Back off quickly so a very long week does not require dozens of
        # expensive full-document renders. Once a fitting lower bound is found,
        # bisect back toward the last overflowing size to retain the largest
        # uniform type that fits.
        overflow_scale = scale
        while len(document.pages) > 4 and scale > _LARGE_PRINT_MIN_SCALE:
            overflow_scale = scale
            scale = max(_LARGE_PRINT_MIN_SCALE, round(scale / 2, 3))
            document = render_at(scale)

        if len(document.pages) > 4:
            raise PDFLayoutError(
                "large-print booklet",
                "The Psalm, hymns, scripture lessons, and creed are too long to fit "
                "in the four reading pages even after reducing the full-text font "
                "across the entire inner sheet. Shorten the included text and try again.",
            )

        fitting_scale = scale
        while overflow_scale - fitting_scale > _LARGE_PRINT_SCALE_STEP:
            candidate_scale = round((fitting_scale + overflow_scale) / 2, 3)
            candidate = render_at(candidate_scale)
            if len(candidate.pages) <= 4:
                fitting_scale, document = candidate_scale, candidate
            else:
                overflow_scale = candidate_scale
        scale = fitting_scale

    # Short readings can leave usable room. Increase only the full-text portion
    # until the next step would exceed the four allocated logical pages.
    while scale < _LARGE_PRINT_MAX_SCALE:
        candidate_scale = min(
            _LARGE_PRINT_MAX_SCALE,
            round(scale + _LARGE_PRINT_SCALE_STEP, 3),
        )
        candidate = render_at(candidate_scale)
        if len(candidate.pages) > 4:
            break
        scale, document = candidate_scale, candidate

    return document


def _panel_to_letter(source_page, panel_index: int) -> PageObject:
    """Enlarge one 5.5 x 8.5 source panel onto a portrait Letter page."""
    source_width = float(source_page.mediabox.width)
    source_height = float(source_page.mediabox.height)
    panel_width = source_width / 2
    x0 = panel_index * panel_width
    panel = copy(source_page)
    panel.cropbox = RectangleObject((x0, 0, x0 + panel_width, source_height))

    scale = _LETTER_HEIGHT_PT / source_height
    rendered_width = panel_width * scale
    left_margin = (_LETTER_WIDTH_PT - rendered_width) / 2
    transform = Transformation().scale(scale).translate(
        tx=left_margin - x0 * scale,
        ty=0,
    )
    logical = PageObject.create_blank_page(
        width=_LETTER_WIDTH_PT, height=_LETTER_HEIGHT_PT
    )
    logical.merge_transformed_page(panel, transform, expand=False)
    return logical


def _logical_fixed_pages(bulletin_pdf: bytes, insert_pdf: bytes) -> tuple:
    """Return logical pages 1, 2, 7, and 8 from the existing two outputs."""
    bulletin_page = PdfReader(BytesIO(bulletin_pdf)).pages[0]
    insert_page = PdfReader(BytesIO(insert_pdf)).pages[0]
    return (
        _panel_to_letter(bulletin_page, 0),  # 1: Order of Service
        _panel_to_letter(bulletin_page, 1),  # 2: Coming Events
        _panel_to_letter(insert_page, 0),    # 7: Insert/announcements
        _panel_to_letter(insert_page, 1),    # 8: Message & Notes
    )


def _impose_large_print_pages(logical_pages: list[PageObject]) -> bytes:
    """Impose eight portrait logical pages on four duplex 17 x 11 sides.

    The side pairs are 8|1, 2|7, 6|3, and 4|5. Printing in order, duplex with
    short-edge binding, then nesting the second sheet inside the first produces
    normal reading order after the two sheets are folded together.
    """
    if len(logical_pages) != 8:  # defensive: this is the physical print contract
        raise ValueError("large-print imposition requires exactly eight logical pages")
    pairs = ((7, 0), (1, 6), (5, 2), (3, 4))
    writer = PdfWriter()
    for left_index, right_index in pairs:
        sheet = PageObject.create_blank_page(
            width=_TABLOID_WIDTH_PT, height=_TABLOID_HEIGHT_PT
        )
        sheet.merge_page(logical_pages[left_index])
        sheet.merge_translated_page(
            logical_pages[right_index], tx=_LETTER_WIDTH_PT, ty=0, expand=False
        )
        writer.add_page(sheet)
    stream = BytesIO()
    writer.write(stream)
    return stream.getvalue()


def render_large_print_pdf(weekly: dict, standing: dict, insert: dict) -> bytes:
    """Four-page, 17 x 11 landscape, duplex-ready large-print booklet."""
    _required_large_print_text(weekly, standing)

    # Reusing the verified existing outputs keeps every bulletin and insert
    # field in one source of truth. Each half is enlarged from 5.5 x 8.5 to a
    # portrait Letter logical page before booklet imposition.
    bulletin_pdf = render_bulletin_pdf(weekly, standing)
    insert_pdf = render_insert_pdf(insert)
    order, events, announcements, notes = _logical_fixed_pages(
        bulletin_pdf, insert_pdf
    )

    content_pdf = _render_large_print_content(weekly, standing).write_pdf()
    content_pages = list(PdfReader(BytesIO(content_pdf)).pages)
    while len(content_pages) < 4:
        content_pages.append(
            PageObject.create_blank_page(
                width=_LETTER_WIDTH_PT, height=_LETTER_HEIGHT_PT
            )
        )

    logical_pages = [
        order,
        events,
        *content_pages,
        announcements,
        notes,
    ]
    return _impose_large_print_pages(logical_pages)
