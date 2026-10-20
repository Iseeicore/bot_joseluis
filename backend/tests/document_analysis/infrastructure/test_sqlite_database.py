import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from src.document_analysis.infrastructure.persistence.sqlite_database import open_database


def test_creates_the_parent_directory_and_the_database_file(tmp_path: Path):
    database_file = tmp_path / "nested" / "dir" / "app.db"
    with closing(open_database(database_file)):
        assert database_file.is_file()


def test_enables_write_ahead_log_and_foreign_keys(tmp_path: Path):
    with closing(open_database(tmp_path / "app.db")) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_rejects_rows_that_break_a_foreign_key(tmp_path: Path):
    with closing(open_database(tmp_path / "app.db")) as connection:
        connection.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
        connection.execute("CREATE TABLE child (parent_id INTEGER REFERENCES parent (id))")
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            connection.execute("INSERT INTO child (parent_id) VALUES (?)", (7,))
