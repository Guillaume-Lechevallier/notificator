import os
import os
from pathlib import Path
from typing import Iterable

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


def _build_database_url() -> str:
    default_url = "mysql+mysqlconnector://notificator:notificator@localhost:3306/notificator"
    return os.getenv("DATABASE_URL", default_url)


database_url = _build_database_url()
connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
engine = create_engine(database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
Base = declarative_base()

_SCHEMA_FILE = Path(__file__).resolve().parent.parent / "last_update.sql"


def _load_sql_statements() -> Iterable[str]:
    """Yield SQL statements from the schema update file, stripping comments."""

    if not _SCHEMA_FILE.exists():
        return []

    try:
        raw_sql = _SCHEMA_FILE.read_text(encoding="utf-8")
    except OSError:
        return []

    statements: list[str] = []
    for raw_statement in raw_sql.split(";"):
        cleaned_lines = []
        for line in raw_statement.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("--"):
                continue
            cleaned_lines.append(line)
        statement = "\n".join(cleaned_lines).strip()
        if statement:
            statements.append(statement)
    return statements


def apply_schema_updates() -> None:
    """Apply idempotent schema updates for MySQL deployments.

    The SQL script `last_update.sql` is executed on startup to align the
    database with the current models (notably the `subscribers.label` column
    and Web Push fields). SQLite deployments are left untouched to avoid
    syntax incompatibilities.
    """

    if not database_url.startswith("mysql"):
        return

    statements = list(_load_sql_statements())
    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.exec_driver_sql(statement)


def init_database() -> None:
    """Ensure schema migrations and table creation are applied."""

    apply_schema_updates()
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
