# Grace & Zion Bulletin Generator — Build Spec

A small internal web app that lets the church secretary fill a weekly form and
download print-ready PDFs for the Sunday bulletin and its insert. Replaces the
current MS Publisher workflow at Grace & Zion Free Lutheran (Valley City, ND).

This is a **dual-parish** bulletin: Grace and Zion share one document. That shapes
the data model throughout (hymns carry two references, readings carry two page
numbers, events split into two sections).

## Stack
- Flask (single internal app, no auth — runs on the office machine / homelab LAN)
- Jinja2 templates → HTML
- WeasyPrint → PDF (pure Python, strong print-CSS support; already proven on this layout)
- SQLite for week-to-week persistence (clone-last-week)
- Deploy pattern mirrors Sermon Broadcaster: systemd service, git pull on prod, restart

## Output specs (do not change without re-checking print fit)
**Bulletin** — the *inside* of a half-folded sheet; outside is pre-printed stock.
- One page, **11×8.5 landscape**, single-sided.
- Two 5.5in panels: left = Order of Worship, right = Coming Events.
- Print single-sided onto the pre-printed bulletin stock.

**Insert** — a half-size sheet printed both sides.
- Two pages, **5.5×8.5 portrait**.
- Page 1 (front) = announcements; page 2 (back) = "Message & Notes".
- Print **two-sided / duplex, flip on LONG edge**, paper size Statement / Half-Letter.
  Surface this as a one-line reminder on the generate screen — long-edge flip keeps
  the back upright; short-edge prints it upside down (the most common mistake).

## Fonts
Originals were **Arial** (body/sans) and **Times New Roman** (the prayer box + notes
heading). Liberation Sans / Liberation Serif are metric-compatible fallbacks for dev;
on the church's Windows machine the real fonts render identically. Keep the
sans/serif split exactly as in the templates.

## Templates (included, verified)
- `templates/bulletin_template.html` — renders the bulletin inside from a `WEEKLY`
  and `STANDING` dict (passed as `w` and `s`).
- `templates/insert_template.html` — renders the two-page duplex insert from an
  `INSERT` dict (passed as `i`).
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
- opening_hymn / sermon_hymn / closing_hymn, each `{grace, title, zion}`
- preacher, sermon_text
- grace_events / zion_events (list of (day, [(name, time), …])), optional banner line
- Insert: prayer list (home[], care_center[], elim_fargo[]), next_date,
  next_readings (list of (label, ref)), announcements (variable list of
  {heading, body} with inline bold allowed), bold_notes ([str])

**STANDING (template defaults — rarely edited, but make them editable):**
- service_title, welcome, radio, listen_live, office_hours, contact_lines, staff
- prayer_tail, missionaries, congregations, sick_notice, notes_heading

Hymnal note: Grace uses *Ambassador*; Zion uses *Concordia* plus a "Green" hymnal
(numbers tagged "(Green)"). Memory verse is shared between bulletin and insert in a
given week — collect once, render in both.

## Build plan (suggested milestones)
1. App skeleton + the two render functions wrapping the existing templates
   (port the `build.py` / `build_insert.py` logic). Confirm PDFs still match.
2. SQLite schema: one row per week (a JSON blob of the field set is fine), with a
   "new week = clone most recent" action so the secretary only edits what changed.
3. Form UI: one page grouped by section (Worship / Hymns / Readings / Events /
   Insert). Keep it boring and obvious — repeatable rows for events, lessons, and
   announcements (add/remove). frontend-design matters here for the secretary's sake.
4. Generate: buttons to download bulletin + insert (decide one-click bundle vs two
   downloads — ask the user). Include the duplex reminder near the insert download.
5. Package as a systemd service; document the dev→prod loop like Sermon Broadcaster.

## Open items to confirm with the user
- The "Please be Praying for…" prayer-box graphic is a styled placeholder in the
  template; swap in the real image asset when available.
- One-click bundled download vs. two separate PDF downloads.
- Whether any "standing" fields should be locked vs. editable in the form.
