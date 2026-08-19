import pytest

from schema import (
    CURRENT_SCHEMA_VERSION,
    CREEDS,
    SchemaVersionError,
    blank_blob,
    normalize_blob,
)


def test_blank_blob_has_complete_versioned_shape():
    blob = blank_blob()
    assert blob["schema_version"] == CURRENT_SCHEMA_VERSION
    assert set(blob) == {"schema_version", "weekly", "standing", "insert"}
    assert blob["weekly"]["confession_of_faith"] == CREEDS[0]
    assert blob["weekly"]["scripture_text_source"] == "manual"
    assert len(blob["insert"]["prayer"]) == 3
    assert "notes_heading" in blob["insert"]
    assert blob["weekly"]["baptism"]["insert_text"] == ""
    assert blob["insert"]["communion_sunday"] is False
    assert blob["insert"]["baptism_announcement"] == ""
    assert set(blob["weekly"]["large_print"]) == {
        "call_to_worship_text",
        "opening_hymn_text",
        "first_lesson_label",
        "first_lesson_text",
        "second_lesson_label",
        "second_lesson_text",
        "sermon_hymn_text",
        "closing_hymn_text",
    }
    assert "God be praised" in blob["standing"]["large_print_responses"]["gospel"]
    assert "apostles" in blob["standing"]["creed_texts"]


def test_normalization_trims_rows_and_mirrors_memory_verse():
    blob = blank_blob()
    blob["weekly"].update(
        memory_verse_ref="  John 3:16  ",
        memory_verse_text="  For God so loved...  ",
        prelude=[[" Grace ", " Alex "], ["", ""]],
    )
    blob["insert"]["memory_verse_ref"] = "stale"

    normalized = normalize_blob(blob)

    assert normalized["weekly"]["prelude"] == [["Grace", "Alex"]]
    assert normalized["insert"]["memory_verse_ref"] == "John 3:16"
    assert normalized["insert"]["memory_verse_text"] == "For God so loved..."


def test_legacy_hymn_and_prayer_shapes_are_upgraded():
    legacy = {
        "weekly": {
            "opening_hymn": {"grace": "12", "title": "A Hymn", "zion": "34"}
        },
        "insert": {"prayer": {"home": [" Alex "], "care_center": []}},
    }

    normalized = normalize_blob(legacy)

    assert normalized["schema_version"] == CURRENT_SCHEMA_VERSION
    assert normalized["weekly"]["opening_hymn"] == {
        "grace": {"num": "12", "title": "A Hymn"},
        "zion": {"num": "34", "title": ""},
    }
    assert normalized["insert"]["prayer"] == [
        {"label": "HOME", "names": ["Alex"]},
        {"label": "CARE CENTER", "names": []},
    ]
    assert normalized["weekly"]["large_print"]["first_lesson_label"] == "First Scripture Lesson"
    assert normalized["standing"]["creed_texts"]["nicene"]


def test_large_print_text_and_standing_wording_are_normalized():
    blob = blank_blob()
    blob["weekly"]["large_print"]["opening_hymn_text"] = "  Verse one  "
    blob["standing"]["large_print_responses"]["gospel"] = "  Thanks be to God.  "
    blob["standing"]["creed_texts"]["apostles"] = "  I believe...  "

    normalized = normalize_blob(blob)

    assert normalized["weekly"]["large_print"]["opening_hymn_text"] == "Verse one"
    assert normalized["standing"]["large_print_responses"]["gospel"] == "Thanks be to God."
    assert normalized["standing"]["creed_texts"]["apostles"] == "I believe..."


def test_newer_schema_is_rejected_instead_of_discarded():
    blob = blank_blob()
    blob["schema_version"] = CURRENT_SCHEMA_VERSION + 1

    with pytest.raises(SchemaVersionError, match="newer|supports"):
        normalize_blob(blob)


def test_invalid_scripture_source_falls_back_to_manual():
    blob = blank_blob()
    blob["weekly"]["scripture_text_source"] = "unknown"

    assert normalize_blob(blob)["weekly"]["scripture_text_source"] == "manual"


def test_service_options_are_mirrored_to_insert_notices():
    blob = blank_blob()
    blob["weekly"]["communion"] = {"enabled": True, "grace": True, "zion": False}
    blob["weekly"]["baptism"] = {
        "enabled": True,
        "text": "Melvin Family",
        "insert_text": "Benjamin Melvin will be brought to the Lord in Baptism.",
    }

    normalized = normalize_blob(blob)

    assert normalized["insert"]["communion_sunday"] is True
    assert normalized["insert"]["baptism_announcement"] == (
        "Benjamin Melvin will be brought to the Lord in Baptism."
    )

    normalized["weekly"]["baptism"]["enabled"] = False
    normalized = normalize_blob(normalized)
    assert normalized["weekly"]["baptism"]["insert_text"].startswith("Benjamin")
    assert normalized["insert"]["baptism_announcement"] == ""
