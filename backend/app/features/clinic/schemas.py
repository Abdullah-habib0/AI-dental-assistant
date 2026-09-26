from pydantic import BaseModel, ConfigDict


class ServiceSummary(BaseModel):
    """A service as shown in the services list."""

    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str
    summary: str
    duration_minutes: int
    price_cents: int


class ServiceDetail(ServiceSummary):
    """A service as shown on its own page. Same as above, plus the full text."""

    description: str


class DentistOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str
    qualifications: str
    speciality: str
    bio: str
    photo_url: str


class FaqOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category: str
    question: str
    answer: str


class ClinicInfo(BaseModel):
    """The clinic's own details, for the contact page."""

    name: str
    phone: str
    email: str
    address: str
    timezone: str
    opening_hour: int
    closing_hour: int
    open_weekdays: list[int]
