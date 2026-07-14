"""Canonical shape of a week's data blob.

The form (and any future importer) must produce a blob with these exact keys.
``blank_blob()`` gives an empty-but-complete starting point for a brand-new week;
``normalize_blob()`` is defensive cleanup applied on save so a malformed or
partial POST can't corrupt the stored shape (missing keys are filled, scalars
coerced to str, list fields forced to lists, nested rows trimmed of blanks).

Shape (three sections, matching the render functions):

  schema_version: integer used for safe data migrations

  weekly:
    liturgical_day, date, call_to_worship, order_of_service,
    confession_of_faith (one of CREEDS), preacher, sermon_text,
    memory_verse_ref, memory_verse_text,                  # shared w/ insert
    grace_events_banner, zion_events_banner               # str
    prelude:           [[who, names], ...]
    scripture_lessons: [[ref, pages], ...]
    opening_hymn/sermon_hymn/closing_hymn:
      {grace: {num, title}, zion: {num, title}}
    grace_events/zion_events: [[day, [[name, time], ...]], ...]

  standing:
    service_title, welcome, radio, listen_live, office_hours
    contact_lines: [str, ...]
    staff:         [[name, detail], ...]

  insert:
    prayer_tail, missionaries, congregations, sick_notice, notes_heading,
    memory_verse_ref, memory_verse_text,                  # mirror of weekly
    next_date
    prayer: [{label, names: [str]}, ...]
    next_readings: [[label, ref], ...]
    announcements: [{heading, body}, ...]
    bold_notes:    [str, ...]
"""

from __future__ import annotations

from copy import deepcopy

# Stored blobs without a version are legacy version 0. Normalizing them applies
# the existing prayer/hymn migrations and upgrades them to this version. A blob
# from a newer application is rejected instead of silently losing unknown data.
CURRENT_SCHEMA_VERSION = 1


class SchemaVersionError(ValueError):
    """Raised when this application cannot safely normalize a stored blob."""


# Confession of Faith rotates among these three (radio button in the form).
CREEDS = ["Apostles' Creed", "Nicene Creed", "Athanasian Creed"]

# Hymn sub-dict keys.
_HYMNS = ("opening_hymn", "sermon_hymn", "closing_hymn")


def blank_blob() -> dict:
    """A complete, empty week blob — every key present, lists empty."""
    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "weekly": {
            "liturgical_day": "",
            "date": "",
            "prelude": [],
            "call_to_worship": "",
            "order_of_service": "",
            "confession_of_faith": CREEDS[0],
            "memory_verse_ref": "",
            "memory_verse_text": "",
            "scripture_lessons": [],
            # Optional sections. Each has an `enabled` flag; when off they don't
            # render at all. Baptism/Confirmation carry a free-form line (names);
            # a blank line renders the heading alone (no "~ ").
            "baptism": {"enabled": False, "text": ""},        # before ORDER OF SERVICE
            # Each hymn carries a Grace and a Zion entry, each {num, title}.
            # The Zion hymnal sometimes lists a different song; its title renders
            # under the Grace title only when present.
            "opening_hymn": {"grace": {"num": "", "title": ""}, "zion": {"num": "", "title": ""}},
            "sermon_hymn": {"grace": {"num": "", "title": ""}, "zion": {"num": "", "title": ""}},
            "closing_hymn": {"grace": {"num": "", "title": ""}, "zion": {"num": "", "title": ""}},
            "special_music": "",   # optional text after "SPECIAL MUSIC~ "
            # after the closing hymn:
            "confirmation": {"enabled": False, "text": ""},
            "communion": {"enabled": False, "grace": False, "zion": False},
            "preacher": "",
            "sermon_text": "",
            # Free-form notes around the events lists (all optional, multi-line).
            "grace_events_banner": "",   # top of "Coming Events at Grace"
            "grace_events": [],
            "between_events": "",        # between the Grace and Zion sections
            "zion_events_banner": "",    # top of "Coming Events at Zion"
            "zion_events": [],
            "below_events": "",          # below the Zion section
        },
        "standing": {
            "service_title": "",
            "welcome": "",
            "radio": "",
            "listen_live": "",
            "office_hours": "",
            "contact_lines": [],
            "staff": [],
        },
        "insert": {
            # Ordered, fully editable prayer categories: [{label, names: [str]}].
            # Labels are renamable and categories can be added/removed in the form.
            "prayer": [
                {"label": "HOME", "names": []},
                {"label": "CARE CENTER", "names": []},
                {"label": "ELIM FARGO", "names": []},
            ],
            "prayer_tail": "",
            "missionaries": "",
            "congregations": "",
            "sick_notice": "",
            "memory_verse_ref": "",
            "memory_verse_text": "",
            "next_date": "",
            "next_readings": [],
            "announcements": [],
            "bold_notes": [],
            "notes_heading": "",
        },
    }


def _s(v) -> str:
    """Coerce a scalar to a stripped string (None -> '')."""
    if v is None:
        return ""
    return str(v).strip()


def _pairs(rows) -> list:
    """Normalize a list of 2-tuples; drop rows where both cells are blank."""
    out = []
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        a, b = _s(row[0]), _s(row[1])
        if a or b:
            out.append([a, b])
    return out


def _str_list(items) -> list:
    out = []
    if not isinstance(items, list):
        return out
    for it in items:
        s = _s(it)
        if s:
            out.append(s)
    return out


def _events(rows) -> list:
    """Normalize [[day, [[name, time], ...]], ...]; drop empty days/items."""
    out = []
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        day = _s(row[0])
        items = _pairs(row[1])
        if day or items:
            out.append([day, items])
    return out


def _hymn(d) -> dict:
    """Normalize a hymn to {grace: {num, title}, zion: {num, title}}.

    Migrates the old shape {grace, title, zion} (grace/zion were bare numbers,
    one shared title) -> the Grace entry keeps num+title; the Zion entry keeps
    its number with no title (old data had no separate Zion title).
    """
    d = d if isinstance(d, dict) else {}

    def side(v):
        v = v if isinstance(v, dict) else {}
        return {"num": _s(v.get("num")), "title": _s(v.get("title"))}

    grace, zion = d.get("grace"), d.get("zion")
    # Old shape: grace/zion are strings (numbers) and there's a top-level title.
    if not isinstance(grace, dict) and not isinstance(zion, dict):
        return {
            "grace": {"num": _s(grace), "title": _s(d.get("title"))},
            "zion": {"num": _s(zion), "title": ""},
        }
    return {"grace": side(grace), "zion": side(zion)}


def _bool(v) -> bool:
    """Coerce form/JSON truthiness (handles "on", "true", "1", booleans)."""
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "on", "yes")
    return bool(v)


def _text_section(d) -> dict:
    """Optional {enabled, text} section (Baptism, Confirmation)."""
    d = d if isinstance(d, dict) else {}
    return {"enabled": _bool(d.get("enabled")), "text": _s(d.get("text"))}


def _communion(d) -> dict:
    """Optional {enabled, grace, zion} section."""
    d = d if isinstance(d, dict) else {}
    return {
        "enabled": _bool(d.get("enabled")),
        "grace": _bool(d.get("grace")),
        "zion": _bool(d.get("zion")),
    }


# Legacy fixed prayer keys -> default display labels, for migrating old blobs
# (stored before prayer became an editable list of categories).
_LEGACY_PRAYER = [("home", "HOME"), ("care_center", "CARE CENTER"),
                  ("elim_fargo", "ELIM FARGO")]


def _prayer(value) -> list:
    """Normalize the prayer list: [{label, names: [str]}, ...].

    Accepts the current list form, and migrates the old fixed-dict form
    ({home, care_center, elim_fargo}) so weeks saved before this change keep
    their entries. A category with neither a label nor any names is dropped.
    """
    cats = []
    if isinstance(value, dict):
        # Legacy migration: known keys first (stable order), then any extras.
        ordered = list(_LEGACY_PRAYER) + [
            (k, k.replace("_", " ").upper())
            for k in value if k not in dict(_LEGACY_PRAYER)
        ]
        for key, label in ordered:
            if key in value:
                cats.append({"label": label, "names": _str_list(value.get(key))})
    elif isinstance(value, list):
        for cat in value:
            if not isinstance(cat, dict):
                continue
            cats.append({"label": _s(cat.get("label")),
                         "names": _str_list(cat.get("names"))})
    # Drop fully-empty categories (no label and no names).
    return [c for c in cats if c["label"] or c["names"]]


def _schema_version(blob: dict) -> int:
    raw_version = blob.get("schema_version", 0)
    try:
        return int(raw_version)
    except (TypeError, ValueError):
        return 0


def _migrate_v0_to_v1(migrated: dict) -> dict:
    """Add versions and upgrade legacy hymn/prayer structures."""
    weekly = migrated.get("weekly")
    if isinstance(weekly, dict):
        for hymn in _HYMNS:
            if hymn in weekly:
                weekly[hymn] = _hymn(weekly[hymn])
    insert = migrated.get("insert")
    if isinstance(insert, dict) and "prayer" in insert:
        insert["prayer"] = _prayer(insert["prayer"])
    migrated["schema_version"] = 1
    return migrated


_MIGRATIONS = {0: _migrate_v0_to_v1}


def migrate_blob(blob: dict) -> dict:
    """Upgrade a blob through explicit version steps without mutating input."""
    migrated = deepcopy(blob) if isinstance(blob, dict) else {}
    version = _schema_version(migrated)
    if version > CURRENT_SCHEMA_VERSION:
        raise SchemaVersionError(
            f"week data uses schema version {version}; this application supports "
            f"up to version {CURRENT_SCHEMA_VERSION}"
        )
    while version < CURRENT_SCHEMA_VERSION:
        migrate = _MIGRATIONS.get(version)
        if migrate is None:
            raise SchemaVersionError(f"no migration is available from schema version {version}")
        migrated = migrate(migrated)
        version = _schema_version(migrated)
    return migrated


def normalize_blob(blob: dict) -> dict:
    """Return a clean blob with the canonical shape, merging over blank_blob().

    Also enforces the shared memory verse: weekly's value wins and is mirrored
    into insert (the form collects it once; the spec renders it in both).
    """
    src = migrate_blob(blob)

    b = blank_blob()
    w_in = src.get("weekly", {}) if isinstance(src.get("weekly"), dict) else {}
    s_in = src.get("standing", {}) if isinstance(src.get("standing"), dict) else {}
    i_in = src.get("insert", {}) if isinstance(src.get("insert"), dict) else {}

    w = b["weekly"]
    for k in ("liturgical_day", "date", "call_to_worship", "order_of_service",
              "special_music", "preacher", "sermon_text",
              "memory_verse_ref", "memory_verse_text",
              "grace_events_banner", "between_events",
              "zion_events_banner", "below_events"):
        w[k] = _s(w_in.get(k))
    # Confession of Faith: one of CREEDS, or "" for "None" (renders the heading
    # alone, no "~ Creed" suffix). Any other value falls back to the default.
    creed = _s(w_in.get("confession_of_faith"))
    w["confession_of_faith"] = creed if creed in CREEDS or creed == "" else CREEDS[0]
    w["prelude"] = _pairs(w_in.get("prelude"))
    w["scripture_lessons"] = _pairs(w_in.get("scripture_lessons"))
    w["baptism"] = _text_section(w_in.get("baptism"))
    for h in _HYMNS:
        w[h] = _hymn(w_in.get(h))
    w["confirmation"] = _text_section(w_in.get("confirmation"))
    w["communion"] = _communion(w_in.get("communion"))
    w["grace_events"] = _events(w_in.get("grace_events"))
    w["zion_events"] = _events(w_in.get("zion_events"))

    s = b["standing"]
    for k in ("service_title", "welcome", "radio", "listen_live", "office_hours"):
        s[k] = _s(s_in.get(k))
    s["contact_lines"] = _str_list(s_in.get("contact_lines"))
    s["staff"] = _pairs(s_in.get("staff"))

    i = b["insert"]
    for k in ("prayer_tail", "missionaries", "congregations", "sick_notice",
              "notes_heading", "next_date"):
        i[k] = _s(i_in.get(k))
    i["prayer"] = _prayer(i_in.get("prayer"))
    i["next_readings"] = _pairs(i_in.get("next_readings"))
    anns = []
    for a in (i_in.get("announcements") or []):
        if not isinstance(a, dict):
            continue
        heading, body = _s(a.get("heading")), _s(a.get("body"))
        if heading or body:
            anns.append({"heading": heading, "body": body})
    i["announcements"] = anns
    i["bold_notes"] = _str_list(i_in.get("bold_notes"))

    # Shared memory verse: weekly is the single source; mirror into insert.
    i["memory_verse_ref"] = w["memory_verse_ref"]
    i["memory_verse_text"] = w["memory_verse_text"]

    return b
