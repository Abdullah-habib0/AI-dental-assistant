"""One rule for time, used everywhere in the app.

Everything stored in the database is UTC with no timezone label attached. Convert to
clinic local time only when showing a time to a person.

The label is stripped on the way in because Python refuses to compare a time that has
one against a time that does not, and that error is confusing when it turns up deep
inside a query. Keeping every stored time the same shape avoids it entirely.
"""

from datetime import UTC, datetime


def utcnow() -> datetime:
    """The current time in UTC, with the timezone label stripped off."""
    return datetime.now(UTC).replace(tzinfo=None)
