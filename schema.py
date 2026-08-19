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
    scripture_text_source ("manual" or transient "esv"),
    memory_verse_ref, memory_verse_text,                  # shared w/ insert
    grace_events_banner, zion_events_banner               # str
    prelude:           [[who, names], ...]
    scripture_lessons: [[ref, pages], ...]
    opening_hymn/sermon_hymn/closing_hymn:
      {grace: {num, title}, zion: {num, title}}
    grace_events/zion_events: [[day, [[name, time], ...]], ...]
    large_print:
      call_to_worship_text, opening_hymn_text,
      first_lesson_label, first_lesson_text,
      second_lesson_label, second_lesson_text,
      sermon_hymn_text, closing_hymn_text

  standing:
    service_title, welcome, radio, listen_live, office_hours
    contact_lines: [str, ...]
    staff:         [[name, detail], ...]
    large_print_responses: {kyrie, gospel, gloria_patri, doxology}
    creed_texts: {apostles, nicene, athanasian}

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
CURRENT_SCHEMA_VERSION = 3


class SchemaVersionError(ValueError):
    """Raised when this application cannot safely normalize a stored blob."""


# Confession of Faith rotates among these three (radio button in the form).
CREEDS = ["Apostles' Creed", "Nicene Creed", "Athanasian Creed"]

# Stable storage keys for the editable creed wording. The display names remain
# the existing radio-button values so old weeks continue to select correctly.
CREED_KEYS = {
    "Apostles' Creed": "apostles",
    "Nicene Creed": "nicene",
    "Athanasian Creed": "athanasian",
}

DEFAULT_LARGE_PRINT_RESPONSES = {
    "kyrie": (
        "O God the Father in heaven, have mercy upon us!\n"
        "O God the Son, Redeemer of the world, have mercy upon us!\n"
        "O God the Holy Ghost, true Comforter, have mercy upon us!"
    ),
    "gospel": "God be praised for\nHis glad tidings!",
    "gloria_patri": (
        "Glory be to the Father,\n"
        "And to the Son,\n"
        "And to the Holy Ghost!\n"
        "As it was in the beginning\n"
        "is now and ever shall be,\n"
        "world without end.\n"
        "Amen. Amen."
    ),
    "doxology": (
        "Praise God from Whom all blessings flow\n"
        "Praise Him, all creatures here below\n"
        "Praise Him above, ye heavenly hosts\n"
        "Praise Father, Son, and Holy Ghost.\n"
        "Amen."
    ),
}

# These are standing, editable defaults. Churches use small wording and
# capitalization variants, so the editor exposes all three texts instead of
# baking them permanently into the PDF template.
DEFAULT_CREED_TEXTS = {
    "apostles": (
        "I believe in God the Father Almighty, Maker of heaven and earth.\n\n"
        "And in Jesus Christ, His only Son, our Lord; Who was conceived by the "
        "Holy Spirit, Born of the virgin Mary; Suffered under Pontius Pilate, "
        "Was crucified, died, and was buried; He descended into hell; The third "
        "day He rose again from the dead; He ascended into heaven, And is seated "
        "on the right hand of God the Father Almighty; From where He shall come "
        "to judge the living and the dead.\n\n"
        "I believe in the Holy Spirit; The holy Christian Church; The Communion "
        "of Saints; The Forgiveness of sins; The Resurrection of the body; And "
        "the Life everlasting. Amen."
    ),
    "nicene": (
        "I believe in one God, the Father Almighty, Maker of heaven and earth, "
        "And of all things visible and invisible.\n\n"
        "And in one Lord Jesus Christ, the only-begotten Son of God, Begotten of "
        "His Father before all worlds, God of God, Light of Light, Very God of "
        "Very God, Begotten, not made, Being of one substance with the Father, "
        "By whom all things were made; Who for us and for our salvation, came "
        "down from heaven, And was incarnate by the Holy Spirit of the virgin "
        "Mary, And was made man; And was crucified also for us under Pontius "
        "Pilate. He suffered and was buried; And the third day He rose again "
        "according to the Scriptures, And ascended into heaven, And is seated on "
        "the right hand of the Father. And He shall come again with glory to "
        "judge both the living and the dead: Whose kingdom shall have no end.\n\n"
        "And I believe in the Holy Spirit, The Lord and Giver of Life, Who "
        "proceeds from the Father and the Son, Who with the Father and the Son "
        "together is worshiped and glorified, Who spoke by the Prophets. And I "
        "believe one holy Christian and apostolic Church. I acknowledge one "
        "Baptism for the remission of sins. And I look for the Resurrection of "
        "the dead. And the Life of the world to come. Amen."
    ),
    "athanasian": (
        "Whosoever will be saved, before all things it is necessary that he hold "
        "the Christian faith. Which faith except everyone do keep whole and "
        "undefiled, without doubt he shall perish everlastingly. And the "
        "Christian faith is this: That we worship one God in Trinity, and "
        "Trinity in Unity; Neither confounding the Persons, nor dividing the "
        "Substance. For there is one Person of the Father, another of the Son, "
        "and another of the Holy Spirit. But the Godhead of the Father, of the "
        "Son, and of the Holy Spirit is all one: the glory equal, the majesty "
        "coeternal. Such as the Father is, such is the Son, and such is the Holy "
        "Spirit. The Father uncreated, the Son uncreated, and the Holy Spirit "
        "uncreated. The Father incomprehensible, the Son incomprehensible, and "
        "the Holy Spirit incomprehensible. The Father eternal, the Son eternal, "
        "and the Holy Spirit eternal. And yet they are not three Eternals, but "
        "one Eternal. As there are not three Uncreated nor three "
        "Incomprehensibles, but one Uncreated and one Incomprehensible. So "
        "likewise the Father is almighty, the Son almighty, and the Holy Spirit "
        "almighty. And yet they are not three Almighties, but one Almighty. So "
        "the Father is God, the Son is God, and the Holy Spirit is God. And yet "
        "they are not three Gods, but one God. So likewise the Father is Lord, "
        "the Son Lord, and the Holy Spirit Lord. And yet not three Lords, but one "
        "Lord. For as we are compelled by the Christian verity to acknowledge "
        "every Person by Himself to be both God and Lord, so are we forbidden by "
        "the Christian faith to say that there are three Gods or three Lords. "
        "The Father is made of none: neither created nor begotten. The Son is of "
        "the Father alone: not made nor created, but begotten. The Holy Spirit is "
        "of the Father and of the Son: neither made nor created nor begotten, but "
        "proceeding. So there is one Father, not three Fathers; one Son, not "
        "three Sons; one Holy Spirit, not three Holy Spirits. And in this Trinity "
        "none is before or after another; none is greater or less than another. "
        "But the whole three Persons are coeternal together and coequal, so that "
        "in all things, as is aforesaid, the Unity in Trinity and the Trinity in "
        "Unity is to be worshiped. He, therefore, that will be saved must thus "
        "think of the Trinity.\n\n"
        "Furthermore, it is necessary to everlasting salvation that he also "
        "believe faithfully the incarnation of our Lord Jesus Christ. For the "
        "right faith is that we believe and confess that our Lord Jesus Christ, "
        "the Son of God, is God and Man; God of the Substance of the Father, "
        "begotten before the worlds; and Man of the substance of His mother, born "
        "in the world; Perfect God and perfect Man, of a reasonable soul and "
        "human flesh subsisting; Equal to the Father as touching His Godhead, and "
        "inferior to the Father as touching His manhood; Who, although He is God "
        "and Man, yet He is not two, but one Christ: One, not by conversion of "
        "the Godhead into flesh, but by taking the manhood into God; One "
        "altogether, not by confusion of Substance, but by unity of Person. For "
        "as the reasonable soul and flesh is one man, so God and Man is one "
        "Christ; Who suffered for our salvation; descended into hell; rose again "
        "the third day from the dead; He ascended into heaven; He is seated on "
        "the right hand of the Father, God Almighty; from where He shall come to "
        "judge the living and the dead. At whose coming all men shall rise again "
        "with their bodies and shall give an account of their own works. And they "
        "that have done good shall go into life everlasting; and they that have "
        "done evil, into everlasting fire. This is the Christian faith; which "
        "except a man believe faithfully and firmly, he cannot be saved."
    ),
}

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
            # Manual text is stored with the week. Automatic ESV text is
            # fetched transiently from Crossway and never persisted.
            "scripture_text_source": "manual",
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
            "large_print": {
                "call_to_worship_text": "",
                "opening_hymn_text": "",
                "first_lesson_label": "First Scripture Lesson",
                "first_lesson_text": "",
                "second_lesson_label": "Second Scripture Lesson",
                "second_lesson_text": "",
                "sermon_hymn_text": "",
                "closing_hymn_text": "",
            },
        },
        "standing": {
            "service_title": "",
            "welcome": "",
            "radio": "",
            "listen_live": "",
            "office_hours": "",
            "contact_lines": [],
            "staff": [],
            "large_print_responses": deepcopy(DEFAULT_LARGE_PRINT_RESPONSES),
            "creed_texts": deepcopy(DEFAULT_CREED_TEXTS),
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


def _migrate_v1_to_v2(migrated: dict) -> dict:
    """Add the optional large-print content and standing wording defaults."""
    migrated["schema_version"] = 2
    return migrated


def _migrate_v2_to_v3(migrated: dict) -> dict:
    """Keep existing weeks on their stored/manual Scripture wording."""
    weekly = migrated.get("weekly")
    if isinstance(weekly, dict):
        weekly.setdefault("scripture_text_source", "manual")
    migrated["schema_version"] = 3
    return migrated


_MIGRATIONS = {
    0: _migrate_v0_to_v1,
    1: _migrate_v1_to_v2,
    2: _migrate_v2_to_v3,
}


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
    source = _s(w_in.get("scripture_text_source")).lower()
    w["scripture_text_source"] = source if source in {"manual", "esv"} else "manual"
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
    lp_in = w_in.get("large_print", {}) if isinstance(w_in.get("large_print"), dict) else {}
    for k in w["large_print"]:
        w["large_print"][k] = _s(lp_in.get(k, w["large_print"][k]))

    s = b["standing"]
    for k in ("service_title", "welcome", "radio", "listen_live", "office_hours"):
        s[k] = _s(s_in.get(k))
    s["contact_lines"] = _str_list(s_in.get("contact_lines"))
    s["staff"] = _pairs(s_in.get("staff"))
    responses_in = (
        s_in.get("large_print_responses", {})
        if isinstance(s_in.get("large_print_responses"), dict) else {}
    )
    for k in s["large_print_responses"]:
        s["large_print_responses"][k] = _s(
            responses_in.get(k, s["large_print_responses"][k])
        )
    creed_texts_in = (
        s_in.get("creed_texts", {})
        if isinstance(s_in.get("creed_texts"), dict) else {}
    )
    for k in s["creed_texts"]:
        s["creed_texts"][k] = _s(creed_texts_in.get(k, s["creed_texts"][k]))

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
