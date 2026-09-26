from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Every table in the app inherits from this."""
