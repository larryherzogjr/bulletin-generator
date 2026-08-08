# Grace & Zion Bulletin Generator — Build Spec

A small internal web app that lets the church secretary fill a weekly form and
download print-ready PDFs for the Sunday bulletin, insert, and large-print
booklet. Replaces the
current MS Publisher workflow at Grace & Zion Free Lutheran (Valley City, ND).

This is a **dual-parish** bulletin: Grace and Zion share one document. That shapes
the data model throughout (hymns carry two references, readings carry two page
numbers, events split into two sections).

## Stack
- Flask (single internal app, no auth — runs on the office machine / homelab LAN)
- Jinja2 templates → HTML
- WeasyPrint → PDF (strong print-CSS support; requires Pango/Cairo native libraries)
- SQLite for week-to-week persistence (clone-last-week)
- Deploy pattern mirrors Sermon Broadcaster: systemd service, git pull on prod, restart

## Output specs (do not change without re-checking print fit)
**Bulletin** — the *inside* of a half-folded sheet; outside is pre-printed stock.
- One page, **11×8.5 landscape**, single-sided.
- Two 5.5in panels: left = Order of Worship, right = Coming Events.
- Print single-sided onto the pre-printed bulletin stock.

**Insert** — both half-sheet sides imposed on one full-size sheet.
- One page, **11×8.5 landscape**.
- Left panel = announcements; right panel = "Message & Notes".
- Print **single-sided** on Letter paper in landscape orientation.

**Large-print booklet** — the bulletin and insert plus complete worship text.
- Four PDF pages, each **17×11 landscape**.
- Print in PDF order on two Tabloid sheets, duplex, flipping on the short edge.
- Nest the second sheet inside the first and fold both sheets together.
- Eight logical portrait pages are imposed as `8|1, 2|7, 6|3, 4|5`.
- Logical pages 1, 2, 7, and 8 enlarge the verified bulletin/insert panels.
- Logical pages 3-6 contain, in reading order: Call to Worship Psalm; first
  hymn; response; first and second lessons; response; selected creed; response;
  second hymn; third hymn; and doxology.
- The expanded worship text starts at 16pt, grows as large as 20pt when space
  permits, and reduces uniformly across all four reading pages until every
  Psalm, hymn, lesson, response, and creed fits. A 4pt emergency floor exists
  only to reject pathological input rather than loop indefinitely.

## Fonts
Originals were **Arial** (body/sans) and **Times New Roman** (the prayer box + notes
heading). Liberation Sans / Liberation Serif are metric-compatible fallbacks for dev;
on the church's Windows machine the real fonts render identically. Keep the
sans/serif split exactly as in the templates.

## Templates (included, verified)
- `templates/bulletin_template.html` — renders the bulletin inside from a `WEEKLY`
  and `STANDING` dict (passed as `w` and `s`).
- `templates/insert_template.html` — renders the two-panel landscape insert from an
  `INSERT` dict (passed as `i`).
- `templates/large_print_content_template.html` — renders the portrait,
  full-text worship stream before it is combined with enlarged panels and
  imposed by `render.py`.
Both use embedded print CSS and have been visually confirmed against the originals.
Treat them as the source of truth for layout; the Flask app's job is to collect the
data and hand it to these templates.

## Data model
Sample data files under `sample_data/` are this week's real content and define the
exact shape. Split conceptually into:

**WEEKLY (the form — changes every Sunday):**
- liturgical_day, date
- prelude (list of (who, names))
- call_to_worship
- order_of_service (page refs; varies by setting — italicize hymnal names)
- confession_of_faith (rotates: Apostles' / Nicene / Athanasian)
- memory_verse_ref + memory_verse_text (shared with the insert)
- scripture_lessons (list of (ref, "G-pg …; Z-pg …"))
- opening_hymn / sermon_hymn / closing_hymn, each with independent
  `{grace: {num, title}, zion: {num, title}}` entries
- large_print: full Psalm, three hymn texts, two lesson texts, and editable
  lesson labels
- preacher, sermon_text
- grace_events / zion_events (list of (day, [(name, time), …])), optional banner line
- Insert: ordered editable prayer categories (`[{label, names[]}]`), next_date,
  next_readings (list of (label, ref)), announcements (variable list of
  {heading, body} with inline bold allowed), bold_notes ([str])

**STANDING (template defaults — rarely edited, but editable and snapshotted):**
- service_title, welcome, radio, listen_live, office_hours, contact_lines, staff
- editable large-print responses and wording for all three creeds
- Insert-standing fields are stored in the insert section: prayer_tail,
  missionaries, congregations, sick_notice, notes_heading

Hymnal note: Grace uses *Ambassador*; Zion uses *Concordia* plus a "Green" hymnal
(numbers tagged "(Green)"). Memory verse is shared between bulletin and insert in a
given week — collect once, render in both.

## Completed product decisions

- PDFs are downloaded separately because they use different paper and printer
  settings.
- Standing fields remain editable and are copied into each week's immutable
  snapshot.
- Versioned JSON blobs preserve legacy prayer/hymn data; blobs from a newer
  unsupported version fail safely.
- The renderer must return exactly one bulletin page, one landscape insert
  page, and four imposed Tabloid large-print pages. It reports a layout error
  when content cannot fit at a legible size.
- The service is unauthenticated only inside its loopback/reverse-proxy trust
  boundary. The proxy must provide authentication before wider exposure.

## Original build plan (completed)
1. App skeleton + the two render functions wrapping the existing templates
   (port the `build.py` / `build_insert.py` logic). Confirm PDFs still match.
2. SQLite schema: one row per week (a JSON blob of the field set is fine), with a
   "new week = clone most recent" action so the secretary only edits what changed.
3. Form UI: one page grouped by section (Worship / Hymns / Readings / Events /
   Insert). Keep it boring and obvious — repeatable rows for events, lessons, and
   announcements (add/remove). frontend-design matters here for the secretary's sake.
4. Generate: buttons to download bulletin + insert (decide one-click bundle vs two
   downloads — ask the user). Include the Letter/landscape reminder near the insert download.
5. Package as a systemd service; document the dev→prod loop like Sermon Broadcaster.

## Remaining external acceptance items
- Add original output files to a private reference location and establish the
  approved visual-diff tolerance. They are not committed today.
