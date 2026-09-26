from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All app settings. Values can be overridden in a .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./clinic.db"

    clinic_name: str = "Bright Smile Dental"
    clinic_phone: str = "+44 20 7946 0123"
    clinic_email: str = "hello@brightsmile.example"
    clinic_address: str = "12 High Street, London W1A 1AA"
    clinic_timezone: str = "Europe/London"
    currency_symbol: str = "£"

    # Opening hours, in clinic local time.
    opening_hour: int = 9
    closing_hour: int = 17
    open_weekdays: tuple[int, ...] = (0, 1, 2, 3, 4)  # Monday=0 ... Sunday=6
    slot_minutes: int = 30


settings = Settings()
