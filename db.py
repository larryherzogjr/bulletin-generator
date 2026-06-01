"""SQLite persistence for the bulletin generator (milestone 2).

Design (settled — see memory: bulletin-schema-decisions):
  * One row per week.
  * Each row stores the *entire* field set as a single JSON blob with three
    top-level keys: ``weekly``, ``standing``, ``insert`` — the same dicts the
    render functions consume. STANDING is snapshotted into every week (not a
    shared/global table), so editing one week never changes past weeks and an
    old bulletin always reprints exactly as it was.
  * "New week = clone the most recent" copies the latest blob into a new row;
    the secretary then edits only what changed.

Why a JSON blob instead of normalized tables: the content is full of
variable-length, nested lists (events -> days -> (name, time); announcements;
lessons). A blob keeps the schema stable as those vary and needs no migrations
when a field is added. Querying/ordering needs are tiny (list weeks, get one,
get latest), so the relational cost isn't worth it here.

Note on tuples: the sample data uses tuples (prelude, lessons, staff, events,
next_readings). JSON has no tuple type, so they persist as arrays and load back
as lists. The templates unpack with ``{% for a, b in ... %}``, which works
identically on 2-element lists, so rendering is unaffected.
"""

from __future__ import annotations

import json
import sqlite3
import os
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# DB location. In production the systemd unit sets BULLETIN_DB to a path OUTSIDE
# the git checkout (e.g. /var/lib/bulletin/bulletin.sqlite3) so `git pull` never
# clobbers it; in dev it defaults to bulletin.sqlite3 beside the code.
DB_PATH = Path(os.environ.get("BULLETIN_DB") or (BASE_DIR / "bulletin.sqlite3"))

# The three sections that make up a week's full field set.
SECTIONS = ("weekly", "standing", "insert")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS weeks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    label      TEXT NOT NULL DEFAULT '',
    data       TEXT NOT NULL,           -- JSON: {"weekly":{...},"standing":{...},"insert":{...}}
    created_at TEXT NOT NULL,           -- ISO-8601 UTC
    updated_at TEXT NOT NULL            -- ISO-8601 UTC
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Open a connection with sensible defaults (Row factory, FK enforcement).

    ``db_path`` defaults to the module-level ``DB_PATH`` resolved at call time
    (not import time), so tests/config can reassign ``db.DB_PATH`` and have it
    honored.
    """
    if db_path is None:
        db_path = DB_PATH
    db_path = Path(db_path)
    # Ensure the parent dir exists (e.g. a fresh /var/lib/bulletin on prod).
    if db_path.parent and not db_path.parent.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create the schema if it doesn't exist. Safe to call repeatedly."""
    conn.executescript(_SCHEMA)
    conn.commit()


# ---------------------------------------------------------------------------
# Blob <-> sections helpers
# ---------------------------------------------------------------------------

def make_blob(weekly: dict, standing: dict, insert: dict) -> dict:
    """Assemble the canonical week dict from the three section dicts."""
    return {"weekly": weekly, "standing": standing, "insert": insert}


def derive_label(blob: dict) -> str:
    """Human-readable label for week lists, e.g. 'Trinity Sunday — May 31, 2026'.

    Falls back gracefully if either field is missing.
    """
    w = blob.get("weekly", {})
    day = (w.get("liturgical_day") or "").strip()
    date = (w.get("date") or "").strip()
    if day and date:
        return f"{day} — {date}"
    return day or date or "Untitled week"


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def create_week(conn: sqlite3.Connection, blob: dict, label: str | None = None) -> int:
    """Insert a new week from a full blob ({weekly, standing, insert}). Returns id."""
    if label is None:
        label = derive_label(blob)
    ts = _now()
    cur = conn.execute(
        "INSERT INTO weeks (label, data, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (label, json.dumps(blob), ts, ts),
    )
    conn.commit()
    return int(cur.lastrowid)


def get_week(conn: sqlite3.Connection, week_id: int) -> dict | None:
    """Return a week as a dict {id, label, data, created_at, updated_at} or None.

    ``data`` is the parsed blob (with ``weekly``/``standing``/``insert`` keys).
    """
    row = conn.execute("SELECT * FROM weeks WHERE id = ?", (week_id,)).fetchone()
    return _row_to_week(row) if row else None


def list_weeks(conn: sqlite3.Connection) -> list[dict]:
    """All weeks, newest first, as lightweight rows (no parsed blob)."""
    rows = conn.execute(
        "SELECT id, label, created_at, updated_at FROM weeks ORDER BY id DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def latest_week(conn: sqlite3.Connection) -> dict | None:
    """The most recently created week (highest id), or None if the table is empty."""
    row = conn.execute("SELECT * FROM weeks ORDER BY id DESC LIMIT 1").fetchone()
    return _row_to_week(row) if row else None


def update_week(
    conn: sqlite3.Connection,
    week_id: int,
    blob: dict,
    label: str | None = None,
) -> bool:
    """Overwrite a week's blob. Returns True if a row was updated."""
    if label is None:
        label = derive_label(blob)
    cur = conn.execute(
        "UPDATE weeks SET data = ?, label = ?, updated_at = ? WHERE id = ?",
        (json.dumps(blob), label, _now(), week_id),
    )
    conn.commit()
    return cur.rowcount > 0


def delete_week(conn: sqlite3.Connection, week_id: int) -> bool:
    """Delete a week. Returns True if a row was removed."""
    cur = conn.execute("DELETE FROM weeks WHERE id = ?", (week_id,))
    conn.commit()
    return cur.rowcount > 0


def clone_week(conn: sqlite3.Connection, week_id: int) -> int | None:
    """Clone a specific week into a brand-new row. Returns the new id, or None
    if the source doesn't exist."""
    src = get_week(conn, week_id)
    if src is None:
        return None
    return create_week(conn, src["data"], label=src["label"])


def clone_latest(conn: sqlite3.Connection) -> int | None:
    """'New week = clone the most recent.' Returns the new id, or None if empty."""
    src = latest_week(conn)
    if src is None:
        return None
    return create_week(conn, src["data"], label=src["label"])


def _row_to_week(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["data"] = json.loads(d["data"])
    return d
