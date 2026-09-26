from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(settings.database_url)


@event.listens_for(engine.sync_engine, "connect")
def _configure_sqlite(dbapi_connection, _record) -> None:
    """Runs once every time a new connection to the database file is opened."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")  # readers don't block the writer
    cursor.execute("PRAGMA busy_timeout=5000")  # wait 5s for a lock instead of failing
    cursor.execute("PRAGMA foreign_keys=ON")  # SQLite ignores foreign keys unless asked
    cursor.close()

    # Stop the driver opening transactions by itself, so we can open them ourselves below.
    dbapi_connection.isolation_level = None


@event.listens_for(engine.sync_engine, "begin")
def _begin_immediate(conn) -> None:
    """Take the write lock at the START of a transaction, not halfway through.

    This is what stops two people booking the same slot at the same moment.
    """
    conn.exec_driver_sql("BEGIN IMMEDIATE")


SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Gives each request its own session, and closes it afterwards."""
    async with SessionLocal() as session:
        yield session
