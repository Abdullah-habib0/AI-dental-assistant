"""Shared setup for every test.

Tests never touch clinic.db. They use their own database file, which is wiped and
refilled with the demo clinic data before every single test, so no test can be affected
by what another one left behind.
"""

import os
import tempfile
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

# These must be set BEFORE anything from `app` is imported, because the app reads its
# settings and creates its database connection the moment it is imported.
_TEST_DB = os.path.join(tempfile.gettempdir(), "dental_assistant_test.db")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_DB}"
os.environ["SECRET_KEY"] = "test-only-secret-key-not-used-anywhere-real"

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.rate_limiting import ALL_LIMITS  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.init_db import create_tables  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from scripts.seed import DENTISTS, FAQS, SERVICES  # noqa: E402

_CLINIC_TZ = ZoneInfo(settings.clinic_timezone)


def _fresh_copy(row):
    """A new, unsaved copy of a seed row. The originals are shared between tests, so
    they must never be added to a session themselves."""
    cls = type(row)
    return cls(**{c.key: getattr(row, c.key) for c in cls.__table__.columns if c.key != "id"})


@pytest.fixture(autouse=True)
async def db():
    """Runs before every test: empty database, clinic data loaded, nothing booked, and
    rate limits back to zero."""
    for limit in ALL_LIMITS:
        limit.reset()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await create_tables(engine)

    async with SessionLocal() as session:
        async with session.begin():
            session.add_all(_fresh_copy(row) for row in SERVICES + DENTISTS + FAQS)

    yield

    # Each test runs on its own event loop. Database connections belong to the loop
    # that opened them, so close them all before the next test starts a new one.
    await engine.dispose()


@pytest.fixture
async def client():
    """Talks to the app the way a browser would, without starting a real server."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# --- Dates that never go stale ------------------------------------------------------
# Booking refuses the past and anything over 90 days ahead. Fixed dates like
# "5 October 2026" would make these tests start failing on 6 October. So tests book on
# "the Monday at least a week from today", whatever today is.


def next_monday() -> date:
    day = date.today() + timedelta(days=7)
    return day + timedelta(days=(7 - day.weekday()) % 7)


def clinic_time(day: date, hour: int, minute: int = 0) -> datetime:
    """A clinic-local time on `day`, as stored in the database: UTC, no label."""
    local = datetime(day.year, day.month, day.day, hour, minute, tzinfo=_CLINIC_TZ)
    return local.astimezone(UTC).replace(tzinfo=None)


def clinic_time_iso(day: date, hour: int, minute: int = 0) -> str:
    """The same time as the API expects it: with its timezone, e.g. '...T13:00:00+01:00'."""
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=_CLINIC_TZ).isoformat()


def utc_iso(moment: datetime) -> str:
    """A stored time as the API sends it back: '...Z'."""
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")
