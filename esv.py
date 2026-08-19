"""Official ESV API integration for transient Scripture text.

The database stores references and the selected source mode, not ESV passage
text.  ESV text is fetched when the editor previews it or an output is
generated.  This keeps the API key server-side and avoids growing a permanent
local ESV corpus as weekly records accumulate.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import html
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ESV_API_URL = "https://api.esv.org/v3/passage/text/"
ESV_SOURCE = "esv"


class ESVError(RuntimeError):
    """An editor-oriented ESV configuration or lookup failure."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


class ESVConfigurationError(ESVError):
    """The server has not been configured with a usable ESV API key."""

    def __init__(self, message: str):
        super().__init__(message, status_code=503)


class ESVLookupError(ESVError):
    """A reference could not be retrieved from the ESV API."""


@dataclass(frozen=True)
class ESVPassage:
    query: str
    canonical: str
    text: str


_VERSE_MARKER = re.compile(r"\[(\d{1,3}[a-z]?)\]", re.IGNORECASE)


def esv_is_configured() -> bool:
    return bool(os.environ.get("ESV_API_KEY", "").strip())


def _api_timeout() -> float:
    raw = os.environ.get("BULLETIN_ESV_TIMEOUT", "15")
    try:
        timeout = float(raw)
    except (TypeError, ValueError):
        timeout = 15.0
    return min(30.0, max(1.0, timeout))


def _editor_text(raw: str) -> str:
    """Convert API ``[16]`` markers to the editor's safe ``<sup>`` markers."""
    normalized = str(raw or "").replace("\r\n", "\n").replace("\r", "\n")
    # A compound reference can produce more than one passage string, each with
    # its own short copyright. Present one attribution after the whole quote.
    normalized = re.sub(r"\s*\(ESV\)\s*", " ", normalized, flags=re.IGNORECASE)
    normalized = "\n".join(line.strip() for line in normalized.splitlines())
    normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()

    pieces: list[str] = []
    cursor = 0
    for marker in _VERSE_MARKER.finditer(normalized):
        pieces.append(html.escape(normalized[cursor:marker.start()], quote=False))
        pieces.append(f"<sup>{marker.group(1)}</sup>")
        cursor = marker.end()
    pieces.append(html.escape(normalized[cursor:], quote=False))
    text = "".join(pieces).strip()
    text = re.sub(r"(</sup>)[ \t]+", r"\1", text, flags=re.IGNORECASE)
    if text:
        text += " (ESV)"
    return text


def _http_error(reference: str, error: HTTPError) -> ESVError:
    if error.code == 400:
        return ESVLookupError(
            f'The ESV API did not recognize the reference "{reference}".',
            status_code=422,
        )
    if error.code in {401, 403}:
        return ESVConfigurationError(
            "The ESV API rejected the configured key. Check ESV_API_KEY and try again."
        )
    if error.code == 429:
        return ESVLookupError(
            "The ESV API rate limit was reached. Wait briefly and try again.",
            status_code=503,
        )
    if error.code >= 500:
        return ESVLookupError(
            "The ESV API is temporarily unavailable. Try again in a few minutes.",
            status_code=502,
        )
    return ESVLookupError(
        f'The ESV API could not load "{reference}" (HTTP {error.code}).'
    )


def fetch_esv_passage(
    reference: str,
    *,
    api_key: str | None = None,
    opener=None,
) -> ESVPassage:
    """Fetch one reference from Crossway's official plain-text endpoint."""
    reference = str(reference or "").strip()
    if not reference:
        raise ESVLookupError("Enter a Scripture reference before loading ESV text.", 422)
    if len(reference) > 120:
        raise ESVLookupError("The Scripture reference is too long.", 422)

    key = (api_key if api_key is not None else os.environ.get("ESV_API_KEY", "")).strip()
    if not key:
        raise ESVConfigurationError(
            "Automatic ESV text is not configured. Set ESV_API_KEY on the server."
        )

    parameters = {
        "q": reference,
        "include-passage-references": "false",
        "include-verse-numbers": "true",
        "include-first-verse-numbers": "true",
        "include-footnotes": "false",
        "include-footnote-body": "false",
        "include-headings": "false",
        "include-short-copyright": "true",
        "include-copyright": "false",
        "include-passage-horizontal-lines": "false",
        "include-heading-horizontal-lines": "false",
        "include-selahs": "true",
        "indent-paragraphs": "0",
        "indent-poetry": "false",
        "line-length": "0",
    }
    request = Request(
        f"{ESV_API_URL}?{urlencode(parameters)}",
        headers={
            "Accept": "application/json",
            "Authorization": f"Token {key}",
            "User-Agent": "Grace-Bulletin-Generator/1",
        },
    )
    open_url = opener or urlopen
    try:
        with open_url(request, timeout=_api_timeout()) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise _http_error(reference, exc) from exc
    except URLError as exc:
        raise ESVLookupError(
            "The ESV API could not be reached. Check the server's network connection."
        ) from exc
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ESVLookupError("The ESV API returned an unreadable response.") from exc

    passages = payload.get("passages") if isinstance(payload, dict) else None
    if not isinstance(passages, list) or not passages:
        raise ESVLookupError(
            f'The ESV API did not return text for "{reference}".', status_code=422
        )
    text = _editor_text("\n\n".join(str(item) for item in passages if item))
    if not text:
        raise ESVLookupError(
            f'The ESV API did not return text for "{reference}".', status_code=422
        )
    return ESVPassage(
        query=str(payload.get("query") or reference),
        canonical=str(payload.get("canonical") or reference),
        text=text,
    )


def lookup_esv_passages(references: list[str]) -> list[ESVPassage]:
    if not isinstance(references, list) or not 1 <= len(references) <= 4:
        raise ESVLookupError("Request between one and four Scripture references.", 400)
    return [fetch_esv_passage(reference) for reference in references]


_OLD_TESTAMENT_BOOKS = {
    "genesis", "exodus", "leviticus", "numbers", "deuteronomy", "joshua",
    "judges", "ruth", "1 samuel", "2 samuel", "1 kings", "2 kings",
    "1 chronicles", "2 chronicles", "ezra", "nehemiah", "esther", "job",
    "psalm", "psalms", "proverbs", "ecclesiastes", "song of solomon",
    "song of songs", "isaiah", "jeremiah", "lamentations", "ezekiel",
    "daniel", "hosea", "joel", "amos", "obadiah", "jonah", "micah",
    "nahum", "habakkuk", "zephaniah", "haggai", "zechariah", "malachi",
}
_GOSPEL_BOOKS = {"matthew", "mark", "luke", "john"}
_EPISTLE_BOOKS = {
    "romans", "1 corinthians", "2 corinthians", "galatians", "ephesians",
    "philippians", "colossians", "1 thessalonians", "2 thessalonians",
    "1 timothy", "2 timothy", "titus", "philemon", "hebrews", "james",
    "1 peter", "2 peter", "1 john", "2 john", "3 john", "jude",
}
_BOOK_ALIASES = {
    "gen": "genesis", "ex": "exodus", "exod": "exodus", "lev": "leviticus",
    "num": "numbers", "deut": "deuteronomy", "josh": "joshua",
    "judg": "judges", "1 sam": "1 samuel", "2 sam": "2 samuel",
    "1 kgs": "1 kings", "2 kgs": "2 kings", "1 chr": "1 chronicles",
    "2 chr": "2 chronicles", "neh": "nehemiah", "esth": "esther",
    "ps": "psalm", "prov": "proverbs", "eccl": "ecclesiastes",
    "song": "song of songs", "isa": "isaiah", "jer": "jeremiah",
    "lam": "lamentations", "ezek": "ezekiel", "dan": "daniel",
    "hos": "hosea", "obad": "obadiah", "hab": "habakkuk",
    "zeph": "zephaniah", "zech": "zechariah", "mal": "malachi",
    "matt": "matthew", "mk": "mark", "lk": "luke", "jn": "john",
    "rom": "romans", "1 cor": "1 corinthians", "2 cor": "2 corinthians",
    "gal": "galatians", "eph": "ephesians", "phil": "philippians",
    "col": "colossians", "1 thess": "1 thessalonians",
    "2 thess": "2 thessalonians", "1 tim": "1 timothy",
    "2 tim": "2 timothy", "tit": "titus", "phlm": "philemon",
    "heb": "hebrews", "jas": "james", "1 pet": "1 peter",
    "2 pet": "2 peter", "1 jn": "1 john", "2 jn": "2 john",
    "3 jn": "3 john", "rev": "revelation",
}


def _book_name(reference: str) -> str:
    cleaned = re.sub(r"<[^>]*>", "", str(reference or "")).lower()
    cleaned = cleaned.replace("–", "-").replace("—", "-").replace(".", "")
    cleaned = re.sub(r"^the\s+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    match = re.match(
        r"^((?:[123]\s*)?[a-z]+(?:\s+of\s+[a-z]+|\s+[a-z]+)?)(?=\s+\d|\s*$)",
        cleaned,
    )
    candidate = match.group(1) if match else cleaned
    candidate = re.sub(r"^(\d)([a-z])", r"\1 \2", candidate)
    return _BOOK_ALIASES.get(candidate, candidate)


def lesson_heading(reference: str) -> str:
    book = _book_name(reference)
    if book in _GOSPEL_BOOKS:
        return "Gospel Lesson"
    if book in _EPISTLE_BOOKS:
        return "Epistle Lesson"
    if book in _OLD_TESTAMENT_BOOKS:
        return "Old Testament Lesson"
    return "New Testament Lesson"


def uses_esv_text(data: dict) -> bool:
    weekly = data.get("weekly", {}) if isinstance(data, dict) else {}
    return weekly.get("scripture_text_source") == ESV_SOURCE


def strip_transient_esv_text(data: dict) -> dict:
    """Clear fetched fields before persistence when automatic ESV mode is on."""
    if not uses_esv_text(data):
        return data
    cleaned = deepcopy(data)
    weekly = cleaned["weekly"]
    weekly["memory_verse_text"] = ""
    large_print = weekly.get("large_print", {})
    for key in (
        "call_to_worship_text",
        "first_lesson_text",
        "second_lesson_text",
    ):
        large_print[key] = ""
    cleaned.get("insert", {})["memory_verse_text"] = ""
    return cleaned


def hydrate_esv_scripture(data: dict, lookup=None) -> dict:
    """Return a copy with transient ESV text populated for rendering."""
    if not uses_esv_text(data):
        return data
    weekly = data.get("weekly", {})
    lessons = weekly.get("scripture_lessons", [])
    if not isinstance(lessons, list) or len(lessons) < 2:
        raise ESVLookupError(
            "Add two Scripture lesson references before loading ESV text.", 422
        )
    references = [
        str(weekly.get("call_to_worship", "")).strip(),
        str(weekly.get("memory_verse_ref", "")).strip(),
        str(lessons[0][0] if isinstance(lessons[0], (list, tuple)) and lessons[0] else "").strip(),
        str(lessons[1][0] if isinstance(lessons[1], (list, tuple)) and lessons[1] else "").strip(),
    ]
    labels = (
        "Call to Worship reference",
        "Memory Verse reference",
        "First Scripture lesson reference",
        "Second Scripture lesson reference",
    )
    missing = [label for label, reference in zip(labels, references) if not reference]
    if missing:
        raise ESVLookupError("Add " + ", ".join(missing) + " and try again.", 422)

    passages = (lookup or lookup_esv_passages)(references)
    if len(passages) != 4:
        raise ESVLookupError("The ESV API returned an incomplete Scripture response.")

    hydrated = deepcopy(data)
    weekly_out = hydrated["weekly"]
    weekly_out["memory_verse_text"] = passages[1].text
    weekly_out["large_print"]["call_to_worship_text"] = passages[0].text
    weekly_out["large_print"]["first_lesson_label"] = lesson_heading(references[2])
    weekly_out["large_print"]["first_lesson_text"] = passages[2].text
    weekly_out["large_print"]["second_lesson_label"] = lesson_heading(references[3])
    weekly_out["large_print"]["second_lesson_text"] = passages[3].text
    hydrated["insert"]["memory_verse_text"] = passages[1].text
    return hydrated
