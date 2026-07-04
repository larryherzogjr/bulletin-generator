"""Render the Grace & Zion bulletin and insert templates into print-ready PDFs.

This is the milestone-1 core: it wires the two verified Jinja2 templates
(``templates/bulletin_template.html`` and ``templates/insert_template.html``)
into plain functions that take the data dicts and return PDF bytes. The Flask
app and, later, the SQLite-backed form all funnel through these functions, so
the layout has exactly one source of truth.

Template variable contract (matches the templates as written):
  * bulletin_template.html expects ``w`` (the WEEKLY dict) and ``s`` (STANDING).
  * insert_template.html   expects ``i`` (the INSERT dict).

Autoescaping is ON for .html templates. The templates opt specific HTML-bearing
fields back in with the ``|safe`` filter (memory verse ``<sup>``, hymnal ``<i>``,
radio ``<u>``, announcement ``<b>``); everything else is escaped. Keep it that
way so secretary-entered text can't break the markup.
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
# busy week (baptism, lots of events, long announcements) would spill to a second
# page, we re-render at a smaller scale until it fits. MIN_SCALE keeps it legible
# (~84% -> about 8.8pt body); STEP is the shrink increment per attempt.
_MIN_SCALE = 0.84
_SCALE_STEP = 0.02


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


def _fits_one_page(html: str) -> bool:
    return len(HTML(string=html, base_url=str(BASE_DIR)).render().pages) <= 1


def render_bulletin_pdf(weekly: dict, standing: dict) -> bytes:
    """Bulletin -> PDF bytes. One page, 11x8.5 landscape, single-sided.

    Auto shrink-to-fit: render at full size; if the content overflows onto a
    second page, step the scale down (to _MIN_SCALE) until it fits on one page.
    The common case (already fits) renders once at scale 1.0 with no extra cost.
    """
    scale = 1.0
    html = render_bulletin_html(weekly, standing, scale)
    while not _fits_one_page(html) and scale > _MIN_SCALE:
        scale = max(_MIN_SCALE, round(scale - _SCALE_STEP, 3))
        html = render_bulletin_html(weekly, standing, scale)
    # If still overflowing at _MIN_SCALE we stop shrinking and let it run long
    # rather than render unreadably small — a signal to trim content.
    return HTML(string=html, base_url=str(BASE_DIR)).write_pdf()


def render_insert_pdf(insert: dict) -> bytes:
    """Insert -> PDF bytes. Two pages, 5.5x8.5 portrait, print duplex / long-edge flip."""
    html = render_insert_html(insert)
    return HTML(string=html, base_url=str(BASE_DIR)).write_pdf()
