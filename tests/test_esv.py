from copy import deepcopy
import json

import pytest

from esv import (
    ESVConfigurationError,
    ESVPassage,
    fetch_esv_passage,
    hydrate_esv_scripture,
    lesson_heading,
    strip_transient_esv_text,
)


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_official_esv_request_keeps_markers_for_layout_and_attribution():
    captured = {}

    def opener(request, timeout):
        captured["url"] = request.full_url
        captured["authorization"] = request.get_header("Authorization")
        captured["timeout"] = timeout
        return _Response(
            {
                "query": "John 3:16-17",
                "canonical": "John 3:16–17",
                "passages": [
                    "  [16] For God so loved the world, & gave his only Son. (ESV)",
                    "  [17] For God did not send his Son to condemn. (ESV)",
                ],
            }
        )

    passage = fetch_esv_passage("John 3:16-17", api_key="secret", opener=opener)

    assert captured["authorization"] == "Token secret"
    assert "include-verse-numbers=true" in captured["url"]
    assert "include-headings=false" in captured["url"]
    assert passage.canonical == "John 3:16–17"
    assert passage.text.startswith("<sup>16</sup>For God")
    assert "<sup>17</sup>For God" in passage.text
    assert "&amp;" in passage.text
    assert passage.text.endswith("(ESV)")
    assert passage.text.count("(ESV)") == 1


def test_esv_key_is_required_without_exposing_a_browser_credential(monkeypatch):
    monkeypatch.delenv("ESV_API_KEY", raising=False)
    with pytest.raises(ESVConfigurationError, match="ESV_API_KEY"):
        fetch_esv_passage("John 11:35")


def test_automatic_esv_text_is_transient_and_hydrated_for_output(sample_blob):
    blob = deepcopy(sample_blob)
    blob["weekly"]["scripture_text_source"] = "esv"
    stripped = strip_transient_esv_text(blob)

    assert stripped["weekly"]["memory_verse_text"] == ""
    assert stripped["weekly"]["large_print"]["call_to_worship_text"] == ""
    assert stripped["weekly"]["large_print"]["first_lesson_text"] == ""
    assert stripped["weekly"]["large_print"]["second_lesson_text"] == ""
    assert stripped["insert"]["memory_verse_text"] == ""

    references = []

    def lookup(values):
        references.extend(values)
        return [
            ESVPassage(value, value, f"<sup>{index}</sup>Text {index}. (ESV)")
            for index, value in enumerate(values, start=1)
        ]

    hydrated = hydrate_esv_scripture(stripped, lookup=lookup)

    assert references == [
        "Psalm 8",
        "1 Peter 5:6-7",
        "Acts 2:14a, 22-36",
        "Matthew 28:16-20",
    ]
    assert hydrated["weekly"]["memory_verse_text"].endswith("(ESV)")
    assert hydrated["weekly"]["large_print"]["first_lesson_label"] == "New Testament Lesson"
    assert hydrated["weekly"]["large_print"]["second_lesson_label"] == "Gospel Lesson"
    assert stripped["weekly"]["memory_verse_text"] == ""


@pytest.mark.parametrize(
    ("reference", "heading"),
    [
        ("Genesis 1:1", "Old Testament Lesson"),
        ("Matthew 28:16", "Gospel Lesson"),
        ("1 Peter 5:6", "Epistle Lesson"),
        ("Acts 2:14", "New Testament Lesson"),
    ],
)
def test_python_lesson_heading_matches_presentation_rules(reference, heading):
    assert lesson_heading(reference) == heading
