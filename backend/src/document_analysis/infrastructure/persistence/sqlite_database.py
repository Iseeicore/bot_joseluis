import sqlite3
from pathlib import Path

CONNECTION_PRAGMAS = ("PRAGMA journal_mode = WAL", "PRAGMA foreign_keys = ON")


def open_database(database_file: Path) -> sqlite3.Connection:
    database_file.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_file)
    for pragma in CONNECTION_PRAGMAS:
        connection.execute(pragma)
    return connection
