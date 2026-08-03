# This week's bulletin = the data a web form would collect.
# Split conceptually into WEEKLY (changes every Sunday) and STANDING (rarely changes).

WEEKLY = {
    "liturgical_day": "Trinity Sunday",
    "date": "May 31, 2026",

    "prelude": [
        ("Grace", "Alex Morgan, Jordan Lee"),
        ("Zion", "Taylor Reed"),
    ],
    "call_to_worship": "Psalm 8",
    "order_of_service": "Grace-<i>Ambassador</i> Pg. 2; Zion-<i>Concordia</i> Pg. 408",
    "confession_of_faith": "Athanasian Creed",

    "memory_verse_ref": "1 Peter 5:6-7",
    "memory_verse_text": (
        "<sup>6</sup>Humble yourselves, therefore, under the mighty hand of God so "
        "that at the proper time he may exalt you, <sup>7</sup>casting all your "
        "anxieties on him, because he cares for you."
    ),

    "scripture_lessons": [
        ("Acts 2:14a, 22-36", "G-pg 1081; Z-pg 1140"),
        ("Matthew 28:16-20", "G-pg 993; Z-pg 1044"),
    ],

    # Optional sections (off by default). Baptism prints before Order of
    # Service; Confirmation/Holy Communion after the closing hymn.
    "baptism": {"enabled": False, "text": ""},

    # Each hymn has a Grace and a Zion entry, each {num, title}. The Zion title
    # is filled only when Zion sings a different song; it then prints
    # right-justified under the Grace hymn name.
    "opening_hymn": {"grace": {"num": "183", "title": "All Creatures of Our God and King"},
                     "zion":  {"num": "59 (Green)", "title": ""}},
    "sermon_hymn":  {"grace": {"num": "181", "title": "O for a Thousand Tongues to Sing"},
                     "zion":  {"num": "90 (Green)", "title": ""}},
    "closing_hymn": {"grace": {"num": "184", "title": "Immortal, Invisible, God Only Wise"},
                     "zion":  {"num": "35 (Green)", "title": ""}},

    "confirmation": {"enabled": False, "text": ""},
    "communion": {"enabled": False, "grace": False, "zion": False},

    "special_music": "",   # optional text rendered after "SPECIAL MUSIC ~ "
    "preacher": "Pastor Jordan Ellis",
    "sermon_text": "Genesis 1:1-2:4a (G-pg 1; Z-pg 1)",

    # Coming events — banner is an optional full-width line above the day list
    "grace_events_banner": "May 31-June 1\u2013 VBS 5:30-8:30pm",
    "grace_events": [
        ("Wednesday, June 3", [("Adult Bible Study", "7:00 PM")]),
        ("Thursday, June 4",  [("Deacons Meet", "6:30 PM"),
                                ("Boards Meet", "7:00 PM"),
                                ("Council Meets", "8:00 PM")]),
        ("Saturday, June 6",  [("Men\u2019s Prayer at Community Center", "7:00 AM")]),
        ("Sunday, June 7",    [("Lake Chapel", "9:00 AM"),
                                ("Divine Worship with Holy Communion", "10:30 AM")]),
    ],
    "between_events": "",
    "zion_events_banner": "",
    "zion_events": [
        ("Wednesday, June 3", [("Adult Bible Study at Grace", "7:00 PM")]),
        ("Sunday, June 7",    [("Divine Worship with Holy Communion", "9:00 AM")]),
    ],
    "below_events": "",
}

STANDING = {
    "service_title": "SUNDAY MORNING WORSHIP",
    "welcome": "We Welcome All Who Worship Here",
    "radio": "Lift High the Cross   KOVC (1490) <u>10 AM</u>   KSJB (600) <u>8 AM</u>",
    "listen_live": "Sunday Mornings at 10:30 AM at church.example.org",
    "office_hours": "Church office hours are 8:00 AM \u2013 12:00 PM, Mon-Fri",
    "contact_lines": [
        "Phone\u2013 (701) 555-0100   E-mail office@example.org",
        "Website church.example.org",
    ],
    "staff": [
        ("Senior Pastor Jordan Ellis", "(C) (701) 555-0101 pastor@example.org"),
        ("Administrative Assistant- Casey Morgan", "(C) (701) 555-0102 office@example.org"),
        ("Children\u2019s Ministry Leader\u2013 Riley Taylor", "(C) (701) 555-0103"),
    ],
}
