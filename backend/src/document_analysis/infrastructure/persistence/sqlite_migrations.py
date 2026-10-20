import sqlite3
from dataclasses import dataclass
from pathlib import Path

from src.shared.constants.regex.migrations import MIGRATION_FILE_PATTERN
from src.shared.enums.migration_problem import MigrationProblem
from src.shared.errors.migration_error import MigrationError

MIGRATION_SUFFIX = ".sql"
FIRST_VERSION = 1
READ_VERSION_SQL = "PRAGMA user_version"
MIGRATION_SCRIPT_TEMPLATE = "BEGIN;\n{body}\n;\nPRAGMA user_version = {version};\nCOMMIT;"


@dataclass(frozen=True)
class Migration:
    version: int
    path: Path


def parse_migration(path: Path) -> Migration:
    match = MIGRATION_FILE_PATTERN.fullmatch(path.name)
    if match is None:
        raise MigrationError(MigrationProblem.MALFORMED_NAME, path.name)
    return Migration(version=int(match["version"]), path=path)


def ensure_contiguous(migrations: list[Migration]) -> None:
    for expected, migration in enumerate(migrations, start=FIRST_VERSION):
        if migration.version < expected:
            raise MigrationError(MigrationProblem.DUPLICATE_VERSION, migration.path.name)
        if migration.version > expected:
            raise MigrationError(MigrationProblem.VERSION_GAP, migration.path.name)


def discover_migrations(migrations_dir: Path) -> list[Migration]:
    candidates = [path for path in migrations_dir.iterdir() if path.suffix == MIGRATION_SUFFIX]
    migrations = sorted((parse_migration(path) for path in candidates), key=lambda migration: (migration.version, migration.path.name))
    ensure_contiguous(migrations)
    return migrations


def current_version(connection: sqlite3.Connection) -> int:
    return connection.execute(READ_VERSION_SQL).fetchone()[0]


def apply_migration(connection: sqlite3.Connection, migration: Migration) -> None:
    script = MIGRATION_SCRIPT_TEMPLATE.format(body=migration.path.read_text(encoding="utf-8"), version=migration.version)
    try:
        connection.executescript(script)
    except sqlite3.Error as error:
        connection.rollback()
        raise MigrationError(MigrationProblem.EXECUTION_FAILED, migration.path.name) from error


def apply_migrations(connection: sqlite3.Connection, migrations_dir: Path) -> tuple[int, ...]:
    applied_version = current_version(connection)
    pending = [migration for migration in discover_migrations(migrations_dir) if migration.version > applied_version]
    for migration in pending:
        apply_migration(connection, migration)
    return tuple(migration.version for migration in pending)
