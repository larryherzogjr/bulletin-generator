# Insert content. Same WEEKLY vs STANDING split idea as the bulletin.

INSERT = {
    # ---- Prayer box (top-left, bordered) ----
    "prayer": {
        "home": ["Laverne Leach", "Jim & Sharon Jensen", "Etta Pritchett",
                 "Gerri Knutson", "Cheryll Borg", "Jan Kjelland",
                 "Kathleen Schierkolk", "Eldwyn Van Bruggen", "Alton Himmerick"],
        "care_center": ["Wanda Niess", "Ronda Richards", "Bette Munkeby", "Paul Rieth"],
        "elim_fargo": ["Gary Skramstad"],
    },
    # Standing prayer tail (rarely edited)
    "prayer_tail": (
        "Our nation\u2019s leaders, military &amp; families, local elected officials. "
        "Our church leaders. Pray for wisdom and guidance for the deacons as they "
        "consider God\u2019s direction in caring for the needs of the congregation. "
        "AFLTS &amp; AFLBS Students. Pastor Norby &amp; family"
    ),
    "missionaries": "Todd &amp; Barb Schierkolk",
    "congregations": "Grace &amp; Zion Free Lutheran, Valley City",
    "sick_notice": "If you know of someone who is sick or hospitalized please contact the church office.",
    "memory_verse_ref": "1 Peter 5:6-7",
    "memory_verse_text": (
        "<sup>6</sup>Humble yourselves, therefore, under the mighty hand of God so "
        "that at the proper time he may exalt you, <sup>7</sup>casting all your "
        "anxieties on him, because he cares for you."
    ),

    # ---- Next Sunday's readings (weekly) ----
    "next_date": "Sunday, June 7, 2026",
    "next_readings": [
        ("Call to Worship", "Psalm 119:65-72"),
        ("Scripture Lesson", "Hosea 5:15-6:6; Romans 4:13-25"),
        ("Sermon Text", "Matthew 9:9-13"),
    ],

    # ---- Rotating announcements: each is heading + free-form body (inline bold ok) ----
    "announcements": [
        {
            "heading": "NEW INFORMATION REGARDING THE CHURCH DIRECTORY UPDATE...",
            "body": (
                "The target date for printing an updated photo directory is <b>July 15.</b> "
                "The directory will be printed using information currently on file in the "
                "online directory. Please stop by the table in the fellowship hall to verify "
                "your information on file and for instructions on how to log into the online "
                "directory and submit a photo. <b>If you wish to have a photo included in the "
                "directory, you must submit one online or email a digital copy of a photo to "
                "Sarah Meester at gracefree@msn.com</b> If you have any questions, please talk "
                "to Sarah in the church office."
            ),
        },
        {
            "heading": "Annual Conference-",
            "body": (
                "The AFLC Annual Conference is happening June 10-13 in Moorhead, MN. St. Paul\u2019s "
                "in Fargo is heading up the organization for the conference and is looking for "
                "volunteers for various tasks, especially VBS and nursery helpers on Friday, "
                "June 12. There are sign up sheets in the fellowship hall if you are available "
                "to serve. Pre-registration to attend the conference is due May 31. Any "
                "questions, please ask Pastor Dennis."
            ),
        },
    ],
    # A bold standalone block (no heading)
    "bold_notes": [
        "FaHoCha Teen Camp will be held July 26-31.",
        "Pre-Teen Camp will be held August 2-6.",
        "Registration forms are available on the kiosk.",
    ],

    "notes_heading": "Message &amp; Notes",
}
