"""Tiny management CLI for the bulletin database (milestone 2).

    python manage.py init            # create the schema
    python manage.py seed            # insert one week from sample_data (if empty)
    python manage.py seed --force    # insert even if weeks already exist
    python manage.py list            # list weeks, newest first
    python manage.py show <id>       # show a week's label + section summary
    python manage.py clone           # clone the most recent week -> new row
    python manage.py render <id>     # write out/bulletin_<id>.pdf + insert_<id>.pdf

This is a developer/ops convenience; the web form (M3) will drive the same db.py
functions. Kept dependency-light so `init`/`seed`/`list`/`clone` work even if
WeasyPrint's native libs aren't present (only `render` imports it, lazily).
"""

from __future__ import annotations

import sys
from pathlib import Path

import db

BASE_DIR = Path(__file__).resolve().parent


def _load_sample_blob() -> dict:
    from sample_data.bulletin_data import STANDING, WEEKLY
    from sample_data.insert_data import INSERT
    return db.make_blob(WEEKLY, STANDING, INSERT)


def cmd_init(conn, args) -> int:
    db.init_db(conn)
    print(f"initialized schema at {db.DB_PATH}")
    return 0


def cmd_seed(conn, args) -> int:
    db.init_db(conn)
    force = "--force" in args
    existing = db.list_weeks(conn)
    if existing and not force:
        print(f"{len(existing)} week(s) already present; use --force to seed anyway")
        return 0
    blob = _load_sample_blob()
    week_id = db.create_week(conn, blob)
    print(f"seeded week id={week_id} label={db.derive_label(blob)!r}")
    return 0


def cmd_list(conn, args) -> int:
    weeks = db.list_weeks(conn)
    if not weeks:
        print("(no weeks yet)")
        return 0
    for w in weeks:
        print(f"  [{w['id']}] {w['label']}  (created {w['created_at']}, updated {w['updated_at']})")
    return 0


def cmd_show(conn, args) -> int:
    if not args:
        print("usage: manage.py show <id>")
        return 2
    week = db.get_week(conn, int(args[0]))
    if week is None:
        print(f"no week with id {args[0]}")
        return 1
    print(f"[{week['id']}] {week['label']}")
    for section in db.SECTIONS:
        data = week["data"].get(section, {})
        keys = ", ".join(sorted(data.keys()))
        print(f"  {section}: {len(data)} fields ({keys})")
    return 0


def cmd_clone(conn, args) -> int:
    new_id = db.clone_latest(conn)
    if new_id is None:
        print("nothing to clone (no weeks yet)")
        return 1
    week = db.get_week(conn, new_id)
    print(f"cloned latest -> new week id={new_id} label={week['label']!r}")
    return 0


def cmd_render(conn, args) -> int:
    if not args:
        print("usage: manage.py render <id>")
        return 2
    week = db.get_week(conn, int(args[0]))
    if week is None:
        print(f"no week with id {args[0]}")
        return 1
    from render import render_bulletin_pdf, render_insert_pdf  # lazy: needs WeasyPrint
    out = BASE_DIR / "out"
    out.mkdir(exist_ok=True)
    blob = week["data"]
    b = out / f"bulletin_{week['id']}.pdf"
    i = out / f"insert_{week['id']}.pdf"
    b.write_bytes(render_bulletin_pdf(blob["weekly"], blob["standing"]))
    i.write_bytes(render_insert_pdf(blob["insert"]))
    print(f"wrote {b} ({b.stat().st_size:,} B)")
    print(f"wrote {i} ({i.stat().st_size:,} B)")
    return 0


COMMANDS = {
    "init": cmd_init,
    "seed": cmd_seed,
    "list": cmd_list,
    "show": cmd_show,
    "clone": cmd_clone,
    "render": cmd_render,
}


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in COMMANDS:
        print("usage: manage.py {%s} [args]" % "|".join(COMMANDS))
        return 2
    conn = db.get_connection()
    try:
        return COMMANDS[argv[0]](conn, argv[1:])
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
