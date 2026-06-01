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

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def render_bulletin_html(weekly: dict, standing: dict) -> str:
    """Render the bulletin inside (left: Order of Worship, right: Coming Events)."""
    return _env.get_template("bulletin_template.html").render(w=weekly, s=standing)


def render_insert_html(insert: dict) -> str:
    """Render the two-page duplex insert (front: announcements, back: Message & Notes)."""
    return _env.get_template("insert_template.html").render(i=insert)


def render_bulletin_pdf(weekly: dict, standing: dict) -> bytes:
    """Bulletin -> PDF bytes. One page, 11x8.5 landscape, single-sided."""
    html = render_bulletin_html(weekly, standing)
    return HTML(string=html, base_url=str(BASE_DIR)).write_pdf()


def render_insert_pdf(insert: dict) -> bytes:
    """Insert -> PDF bytes. Two pages, 5.5x8.5 portrait, print duplex / long-edge flip."""
    html = render_insert_html(insert)
    return HTML(string=html, base_url=str(BASE_DIR)).write_pdf()
