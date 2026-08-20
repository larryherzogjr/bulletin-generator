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
    "confession_of_faith": "Nicene Creed",
    "food_at_grace": False,

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

    # Optional sections (off by default). Baptism's short text prints before
    # Order of Service; bulletin_text prints under Coming Events at Grace.
    # Confirmation/Holy Communion print after the closing hymn.
    "baptism": {
        "enabled": False,
        "text": "",
        "bulletin_text": (
            "Johnny Smith, son of Doug & Wanda Smith will be brought to the Lord "
            "in Baptism. Sponsors are Frank & Susan Petersen."
        ),
    },

    # Each hymn has a Grace and a Zion entry, each {num, title}. The Zion title
    # is filled only when Zion sings a different song; it then prints on the
    # same row as Zion's hymn number.
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
    "large_print": {
        "call_to_worship_text": (
            "O Lord our Lord, how excellent is thy name in all the earth! "
            "When I consider thy heavens, the work of thy fingers, the moon and "
            "the stars, which thou hast ordained; What is man, that thou art "
            "mindful of him? O Lord our Lord, how excellent is thy name in all the earth!"
        ),
        "opening_hymn_text": (
            "1 All creatures of our God and King, lift up your voice and with us sing.\n\n"
            "2 Thou rushing wind that art so strong, praise Him and magnify the Lord.\n\n"
            "3 Let all things their Creator bless, and worship Him in humbleness."
        ),
        "first_lesson_label": "Epistle Lesson",
        "first_lesson_text": (
            "<sup>14</sup>Peter, standing up with the eleven, lifted up his voice and said: "
            "<sup>22</sup>Jesus of Nazareth, a man approved of God among you by miracles and "
            "wonders and signs, was delivered by the determinate counsel and "
            "foreknowledge of God. <sup>32</sup>This Jesus hath God raised up, whereof we all "
            "are witnesses. <sup>36</sup>Therefore let all the house of Israel know assuredly, "
            "that God hath made that same Jesus both Lord and Christ."
        ),
        "second_lesson_label": "Gospel Lesson",
        "second_lesson_text": (
            "<sup>16</sup>Then the eleven disciples went away into Galilee, into a mountain "
            "where Jesus had appointed them. And Jesus came and spake unto them, "
            "<sup>18</sup>saying, All power is given unto me in heaven and in earth. <sup>19</sup>Go ye "
            "therefore, and teach all nations, baptizing them in the name of the "
            "Father, and of the Son, and of the Holy Ghost; <sup>20</sup>and, lo, I am with "
            "you alway, even unto the end of the world. Amen."
        ),
        "sermon_hymn_text": (
            "1 O for a thousand tongues to sing my great Redeemer's praise.\n\n"
            "2 Jesus! the name that charms our fears, that bids our sorrows cease.\n\n"
            "3 He breaks the power of canceled sin; He sets the prisoner free."
        ),
        "closing_hymn_text": (
            "1 Immortal, invisible, God only wise, in light inaccessible hid from our eyes.\n\n"
            "2 Unresting, unhasting, and silent as light, nor wanting, nor wasting, Thou rulest in might.\n\n"
            "3 Great Father of glory, pure Father of light, Thine angels adore Thee, all veiling their sight."
        ),
    },
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
