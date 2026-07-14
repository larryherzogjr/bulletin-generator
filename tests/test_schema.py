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
    assert len(blob["insert"]["prayer"]) == 3
    assert "notes_heading" in blob["insert"]


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


def test_newer_schema_is_rejected_instead_of_discarded():
    blob = blank_blob()
    blob["schema_version"] = CURRENT_SCHEMA_VERSION + 1

    with pytest.raises(SchemaVersionError, match="newer|supports"):
        normalize_blob(blob)
