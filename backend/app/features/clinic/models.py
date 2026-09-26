from sqlalchemy import CheckConstraint, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Service(Base):
    """A treatment the clinic offers."""

    __tablename__ = "services"
    __table_args__ = (
        # Appointments are built from 30-minute blocks. A 45-minute service could not be
        # placed on that grid, so the database refuses to store one.
        CheckConstraint("duration_minutes > 0", name="duration_positive"),
        CheckConstraint("duration_minutes % 30 = 0", name="duration_fits_slot_grid"),
        CheckConstraint("price_cents >= 0", name="price_not_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    summary: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    price_cents: Mapped[int] = mapped_column(Integer)


class Dentist(Base):
    """A member of the clinical team."""

    __tablename__ = "dentists"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    qualifications: Mapped[str] = mapped_column(String(120))
    speciality: Mapped[str] = mapped_column(String(120))
    bio: Mapped[str] = mapped_column(Text)
    photo_url: Mapped[str] = mapped_column(String(300))


class Faq(Base):
    """A question and answer shown on the FAQ page."""

    __tablename__ = "faqs"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(60), index=True)
    question: Mapped[str] = mapped_column(String(300))
    answer: Mapped[str] = mapped_column(Text)
