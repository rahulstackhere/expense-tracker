import os
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


BACKEND_DIRECTORY = Path(__file__).resolve().parent


def resolve_database_url(database_url: str) -> str:
    url = make_url(database_url)
    if url.get_backend_name() == "sqlite" and url.database not in (None, "", ":memory:"):
        database_path = Path(url.database)
        if not database_path.is_absolute():
            database_path = BACKEND_DIRECTORY / database_path
        url = url.set(database=str(database_path.resolve()))
    return url.render_as_string(hide_password=False)


def _database_url() -> str:
    return resolve_database_url(os.getenv("DATABASE_URL", "sqlite:///./expense_tracker.db"))


DATABASE_URL = _database_url()


def create_database_engine(database_url: str) -> Engine:
    resolved_url = resolve_database_url(database_url)
    connect_args = {"check_same_thread": False} if resolved_url.startswith("sqlite") else {}
    pool_options = {"poolclass": StaticPool} if database_url == "sqlite://" else {}
    database_engine = create_engine(resolved_url, connect_args=connect_args, **pool_options)

    if resolved_url.startswith("sqlite"):

        @event.listens_for(database_engine, "connect")
        def enable_sqlite_foreign_keys(connection, _connection_record) -> None:
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
            connection.create_function(
                "unicode_casefold",
                1,
                lambda value: value.casefold() if isinstance(value, str) else "",
                deterministic=True,
            )
            connection.create_function(
                "unicode_length",
                1,
                lambda value: len(value) if isinstance(value, str) else 0,
                deterministic=True,
            )
            connection.create_function(
                "unicode_is_blank",
                1,
                lambda value: int(not value.strip()) if isinstance(value, str) else 1,
                deterministic=True,
            )

    return database_engine


def initialize_database(database_engine: Engine) -> None:
    from models import Base

    try:
        Base.metadata.create_all(bind=database_engine)
    except IntegrityError as error:
        if "uq_categories_name_casefold" in str(error.orig):
            raise RuntimeError(
                "Existing category names collide under Unicode case-insensitive comparison. "
                "Resolve the duplicate names before starting the API."
            ) from error
        raise

    if database_engine.dialect.name != "sqlite":
        return

    integrity_objects = (
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_categories_name_casefold
        ON categories (unicode_casefold(name))
        """,
        """
        CREATE TRIGGER IF NOT EXISTS categories_validate_insert
        BEFORE INSERT ON categories
        WHEN unicode_is_blank(NEW.name) OR unicode_length(NEW.name) > 100
        BEGIN
            SELECT RAISE(ABORT, 'Category name must be nonblank and at most 100 characters.');
        END
        """,
        """
        CREATE TRIGGER IF NOT EXISTS categories_validate_update
        BEFORE UPDATE OF name ON categories
        WHEN unicode_is_blank(NEW.name) OR unicode_length(NEW.name) > 100
        BEGIN
            SELECT RAISE(ABORT, 'Category name must be nonblank and at most 100 characters.');
        END
        """,
        """
        CREATE TRIGGER IF NOT EXISTS expenses_validate_insert
        BEFORE INSERT ON expenses
        WHEN unicode_is_blank(NEW.title)
          OR unicode_length(NEW.title) > 200
          OR NEW.amount <= 0
          OR NEW.amount > 9999999999.99
          OR NEW.amount != round(NEW.amount, 2)
        BEGIN
            SELECT RAISE(ABORT, 'Expense title or amount violates database constraints.');
        END
        """,
        """
        CREATE TRIGGER IF NOT EXISTS expenses_validate_update
        BEFORE UPDATE OF title, amount ON expenses
        WHEN unicode_is_blank(NEW.title)
          OR unicode_length(NEW.title) > 200
          OR NEW.amount <= 0
          OR NEW.amount > 9999999999.99
          OR NEW.amount != round(NEW.amount, 2)
        BEGIN
            SELECT RAISE(ABORT, 'Expense title or amount violates database constraints.');
        END
        """,
    )
    try:
        with database_engine.begin() as connection:
            for statement in integrity_objects:
                connection.exec_driver_sql(statement)
    except IntegrityError as error:
        if "uq_categories_name_casefold" in str(error.orig):
            raise RuntimeError(
                "Existing category names collide under Unicode case-insensitive comparison. "
                "Resolve the duplicate names before starting the API."
            ) from error
        raise


engine = create_database_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
