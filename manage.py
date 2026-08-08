"""Management CLI for the bulletin database.

    python manage.py init            # create the schema
    python manage.py seed            # insert one week from sample_data (if empty)
    python manage.py seed --force    # insert even if weeks already exist
    python manage.py list            # list weeks, newest first
    python manage.py show <id>       # show a week's label + section summary
    python manage.py clone           # clone the most recent week -> new row
    python manage.py render <id>     # write the three print-ready PDFs
    python manage.py backup [path]   # online SQLite backup (safe while app runs)
    python manage.py check [--render]# DB integrity/schema + optional PDF preflight
    python manage.py migrate         # back up, then persist current blob version

This is a developer/ops convenience; the web form drives the same db.py
functions. Kept dependency-light so `init`/`seed`/`list`/`clone` work even if
WeasyPrint's native libs aren't present (only `render` imports it, lazily).
"""

from __future__ import annotations

import sys
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import db
from schema import normalize_blob

BASE_DIR = Path(__file__).resolve().parent


def _load_sample_blob() -> dict:
    from sample_data.bulletin_data import STANDING, WEEKLY
    from sample_data.insert_data import INSERT
    return normalize_blob(db.make_blob(WEEKLY, STANDING, INSERT))


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
    print(f"  schema_version: {week['data'].get('schema_version', 0)}")
    for section in db.SECTIONS:
        data = week["data"].get(section, {})
        keys = ", ".join(sorted(data.keys()))
        print(f"  {section}: {len(data)} fields ({keys})")
    return 0


def cmd_clone(conn, args) -> int:
    source = db.latest_week(conn)
    if source is None:
        print("nothing to clone (no weeks yet)")
        return 1
    new_id = db.create_week(
        conn, normalize_blob(source["data"]), label=source["label"]
    )
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
    from render import (  # lazy: needs WeasyPrint
        render_bulletin_pdf,
        render_insert_pdf,
        render_large_print_pdf,
    )
    out = BASE_DIR / "out"
    out.mkdir(exist_ok=True)
    blob = normalize_blob(week["data"])
    b = out / f"bulletin_{week['id']}.pdf"
    i = out / f"insert_{week['id']}.pdf"
    lp = out / f"large_print_{week['id']}.pdf"
    b.write_bytes(render_bulletin_pdf(blob["weekly"], blob["standing"]))
    i.write_bytes(render_insert_pdf(blob["insert"]))
    lp.write_bytes(
        render_large_print_pdf(blob["weekly"], blob["standing"], blob["insert"])
    )
    print(f"wrote {b} ({b.stat().st_size:,} B)")
    print(f"wrote {i} ({i.stat().st_size:,} B)")
    print(f"wrote {lp} ({lp.stat().st_size:,} B)")
    return 0


def cmd_backup(conn, args) -> int:
    """Create a consistent online backup using SQLite's backup API."""
    db.init_db(conn)
    if args:
        destination = Path(args[0]).expanduser()
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        destination = Path(db.DB_PATH).parent / "backups" / f"bulletin-{stamp}.sqlite3"
    source = Path(db.DB_PATH).expanduser()
    if destination.resolve() == source.resolve():
        print("backup destination must differ from the active database")
        return 2
    if destination.exists():
        print(f"backup destination already exists: {destination}")
        return 2
    destination.parent.mkdir(parents=True, exist_ok=True)
    target = sqlite3.connect(str(destination))
    try:
        conn.backup(target)
    finally:
        target.close()
    destination.chmod(0o600)
    print(f"backed up {source} -> {destination} ({destination.stat().st_size:,} B)")
    return 0


def cmd_check(conn, args) -> int:
    """Validate DB integrity, all stored blob versions, and optional rendering."""
    db.init_db(conn)
    result = conn.execute("PRAGMA integrity_check").fetchone()[0]
    if result != "ok":
        print(f"database integrity check failed: {result}")
        return 1

    weeks = db.list_weeks(conn)
    normalized = []
    for summary in weeks:
        week = db.get_week(conn, summary["id"])
        normalized.append(normalize_blob(week["data"]))

    if "--render" in args:
        from render import (
            render_bulletin_pdf,
            render_insert_pdf,
            render_large_print_pdf,
        )

        targets = [("sample", _load_sample_blob())]
        if normalized:
            targets.append((f"latest week {weeks[0]['id']}", normalized[0]))
        for label, blob in targets:
            render_bulletin_pdf(blob["weekly"], blob["standing"])
            render_insert_pdf(blob["insert"])
            render_large_print_pdf(blob["weekly"], blob["standing"], blob["insert"])
            print(f"render check ok: {label}")

    print(f"database check ok: {len(weeks)} week(s), stored blobs compatible")
    return 0


def cmd_migrate(conn, args) -> int:
    """Back up the DB, then persist normalized blobs at the current version."""
    if cmd_backup(conn, []) != 0:
        return 1
    changed = 0
    for summary in db.list_weeks(conn):
        week = db.get_week(conn, summary["id"])
        normalized = normalize_blob(week["data"])
        if normalized != week["data"]:
            db.update_week(conn, week["id"], normalized)
            changed += 1
    print(f"migration complete: {changed} week(s) updated")
    return 0


COMMANDS = {
    "init": cmd_init,
    "seed": cmd_seed,
    "list": cmd_list,
    "show": cmd_show,
    "clone": cmd_clone,
    "render": cmd_render,
    "backup": cmd_backup,
    "check": cmd_check,
    "migrate": cmd_migrate,
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
