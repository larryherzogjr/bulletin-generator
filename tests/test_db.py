import sqlite3
import stat

import db
import manage


def test_crud_clone_and_snapshot_independence(tmp_path, sample_blob):
    conn = db.get_connection(tmp_path / "weeks.sqlite3")
    try:
        db.init_db(conn)
        source_id = db.create_week(conn, sample_blob)
        clone_id = db.clone_week(conn, source_id)

        source = db.get_week(conn, source_id)
        clone = db.get_week(conn, clone_id)
        assert clone["data"] == source["data"]

        changed = source["data"]
        changed["weekly"]["date"] = "June 7, 2026"
        assert db.update_week(conn, source_id, changed)
        assert db.get_week(conn, clone_id)["data"]["weekly"]["date"] == "May 31, 2026"

        assert db.delete_week(conn, source_id)
        assert db.get_week(conn, source_id) is None
        assert [week["id"] for week in db.list_weeks(conn)] == [clone_id]
    finally:
        conn.close()


def test_backup_command_creates_consistent_database(tmp_path, monkeypatch, sample_blob):
    source = tmp_path / "source.sqlite3"
    destination = tmp_path / "backups" / "copy.sqlite3"
    monkeypatch.setattr(db, "DB_PATH", source)
    conn = db.get_connection()
    try:
        db.init_db(conn)
        db.create_week(conn, sample_blob)
        assert manage.cmd_backup(conn, [str(destination)]) == 0
    finally:
        conn.close()

    copy = sqlite3.connect(destination)
    try:
        assert copy.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert copy.execute("SELECT COUNT(*) FROM weeks").fetchone()[0] == 1
    finally:
        copy.close()
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600


def test_migrate_command_backs_up_and_persists_current_version(tmp_path, monkeypatch):
    source = tmp_path / "legacy.sqlite3"
    monkeypatch.setattr(db, "DB_PATH", source)
    conn = db.get_connection()
    try:
        db.init_db(conn)
        week_id = db.create_week(
            conn,
            {
                "weekly": {
                    "date": "May 31, 2026",
                    "opening_hymn": {"grace": "12", "title": "Old", "zion": "34"},
                },
                "standing": {},
                "insert": {"prayer": {"home": ["Alex"]}},
            },
        )

        assert manage.cmd_migrate(conn, []) == 0
        migrated = db.get_week(conn, week_id)["data"]
        assert migrated["schema_version"] == 1
        assert migrated["weekly"]["opening_hymn"]["grace"]["title"] == "Old"
    finally:
        conn.close()

    assert len(list((tmp_path / "backups").glob("bulletin-*.sqlite3"))) == 1
