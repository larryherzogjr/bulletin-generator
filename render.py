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
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup
from weasyprint import HTML

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
_INSERT_WIDTH = 5.5 * 96


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
    """Render the two-page duplex insert (front: announcements, back: Message & Notes)."""
    return _env.get_template("insert_template.html").render(i=insert)


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

    The bulletin panels and insert pages have a fixed 8.5in height. Content can
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
    """Insert -> PDF bytes. Two pages, 5.5x8.5 portrait, print duplex / long-edge flip."""
    html = render_insert_html(insert)
    document = HTML(string=html, base_url=str(BASE_DIR)).render()
    if (
        not _has_expected_geometry(document, 2, _INSERT_WIDTH, _PAGE_HEIGHT)
        or _class_box_overflows(document, "page")
    ):
        raise PDFLayoutError(
            "insert",
            "The insert content is too long to fit on exactly two 5.5 x 8.5 "
            "inch pages. Shorten the prayer list, readings, announcements, "
            "or bold notes and try again.",
        )
    return document.write_pdf()
