from copy import deepcopy

import pytest

import app as app_module
import db
from sample_data.bulletin_data import STANDING, WEEKLY
from sample_data.insert_data import INSERT
from schema import normalize_blob


@pytest.fixture
def sample_blob():
    return normalize_blob(
        db.make_blob(deepcopy(WEEKLY), deepcopy(STANDING), deepcopy(INSERT))
    )


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "bulletin.sqlite3")
    app_module.app.config.update(TESTING=True, MAX_CONTENT_LENGTH=1024 * 1024)
    with app_module.app.test_client() as test_client:
        yield test_client
