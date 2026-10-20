import sqlite3
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

import pytest

from src.document_analysis.infrastructure.persistence.sqlite_database import open_database
from src.document_analysis.infrastructure.persistence.sqlite_migrations import apply_migrations
from src.shared.constants.config import MIGRATIONS_DIR
from src.shared.enums.migration_problem import MigrationProblem
from src.shared.errors.migration_error import MigrationError

CREATE_ITEMS = "CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT NOT NULL);"
ADD_ITEM = "INSERT INTO items (name) VALUES ('primero');"
CREATE_TAGS = "CREATE TABLE tags (id INTEGER PRIMARY KEY)"


@pytest.fixture
def migrations_dir(tmp_path: Path) -> Path:
    path = tmp_path / "migrations"
    path.mkdir()
    return path


@pytest.fixture
def connection(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    with closing(open_database(tmp_path / "data" / "app.db")) as opened:
        yield opened


def write(migrations_dir: Path, name: str, sql: str) -> None:
    (migrations_dir / name).write_text(sql, encoding="utf-8")


def user_version(connection: sqlite3.Connection) -> int:
    return connection.execute("PRAGMA user_version").fetchone()[0]


def table_names(connection: sqlite3.Connection) -> set[str]:
    return {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def test_applies_pending_migrations_in_order(migrations_dir: Path, connection: sqlite3.Connection):
    write(migrations_dir, "0002_add_first_item.sql", ADD_ITEM)
    write(migrations_dir, "0001_create_items.sql", CREATE_ITEMS)
    assert apply_migrations(connection, migrations_dir) == (1, 2)
    assert user_version(connection) == 2
    assert connection.execute("SELECT name FROM items").fetchall() == [("primero",)]


def test_second_run_is_idempotent(migrations_dir: Path, connection: sqlite3.Connection):
    write(migrations_dir, "0001_create_items.sql", CREATE_ITEMS)
    apply_migrations(connection, migrations_dir)
    assert apply_migrations(connection, migrations_dir) == ()
    assert user_version(connection) == 1


def test_skips_migrations_that_were_already_applied(migrations_dir: Path, connection: sqlite3.Connection):
    write(migrations_dir, "0001_create_items.sql", CREATE_ITEMS)
    apply_migrations(connection, migrations_dir)
    write(migrations_dir, "0002_add_first_item.sql", ADD_ITEM)
    assert apply_migrations(connection, migrations_dir) == (2,)
    assert user_version(connection) == 2


def test_accepts_a_migration_without_trailing_semicolon(migrations_dir: Path, connection: sqlite3.Connection):
    write(migrations_dir, "0001_create_tags.sql", CREATE_TAGS)
    apply_migrations(connection, migrations_dir)
    assert "tags" in table_names(connection)


def test_ignores_files_that_are_not_sql(migrations_dir: Path, connection: sqlite3.Connection):
    write(migrations_dir, ".gitkeep", "")
    write(migrations_dir, "LEEME.txt", "notas")
    assert apply_migrations(connection, migrations_dir) == ()
    assert user_version(connection) == 0


@pytest.mark.parametrize("name", ["1_create_items.sql", "0001-create-items.sql", "0001_Create_Items.sql", "0001_.sql", "00001_items.sql"])
def test_rejects_a_malformed_file_name(migrations_dir: Path, connection: sqlite3.Connection, name: str):
    write(migrations_dir, name, CREATE_ITEMS)
    with pytest.raises(MigrationError) as raised:
        apply_migrations(connection, migrations_dir)
    assert raised.value.problem == MigrationProblem.MALFORMED_NAME
    assert raised.value.file_name == name


def test_rejects_a_duplicate_version(migrations_dir: Path, connection: sqlite3.Connection):
    write(migrations_dir, "0001_create_items.sql", CREATE_ITEMS)
    write(migrations_dir, "0001_create_tags.sql", CREATE_TAGS)
    with pytest.raises(MigrationError) as raised:
        apply_migrations(connection, migrations_dir)
    assert raised.value.problem == MigrationProblem.DUPLICATE_VERSION
    assert raised.value.file_name == "0001_create_tags.sql"


@pytest.mark.parametrize("names", [("0001_create_items.sql", "0003_create_tags.sql"), ("0002_create_items.sql",)])
def test_rejects_a_gap_in_the_numbering_before_applying_anything(
    migrations_dir: Path, connection: sqlite3.Connection, names: tuple[str, ...]
):
    for name in names:
        write(migrations_dir, name, CREATE_ITEMS if name.endswith("items.sql") else CREATE_TAGS)
    with pytest.raises(MigrationError) as raised:
        apply_migrations(connection, migrations_dir)
    assert raised.value.problem == MigrationProblem.VERSION_GAP
    assert raised.value.file_name == names[-1]
    assert user_version(connection) == 0
    assert table_names(connection) == set()


def test_failing_migration_is_rolled_back_without_bumping_the_version(migrations_dir: Path, connection: sqlite3.Connection):
    write(migrations_dir, "0001_create_items.sql", CREATE_ITEMS)
    write(migrations_dir, "0002_broken.sql", f"{CREATE_TAGS};\nINSERT INTO missing_table VALUES (1);")
    with pytest.raises(MigrationError) as raised:
        apply_migrations(connection, migrations_dir)
    assert raised.value.problem == MigrationProblem.EXECUTION_FAILED
    assert raised.value.file_name == "0002_broken.sql"
    assert isinstance(raised.value.__cause__, sqlite3.Error)
    assert user_version(connection) == 1
    assert table_names(connection) == {"items"}
    assert not connection.in_transaction


def test_error_message_names_the_offending_file(migrations_dir: Path, connection: sqlite3.Connection):
    write(migrations_dir, "init.sql", CREATE_ITEMS)
    with pytest.raises(MigrationError, match="init.sql"):
        apply_migrations(connection, migrations_dir)


def test_repository_migrations_folder_is_valid(connection: sqlite3.Connection):
    assert MIGRATIONS_DIR.is_dir()
    applied = apply_migrations(connection, MIGRATIONS_DIR)
    assert user_version(connection) == len(applied)
