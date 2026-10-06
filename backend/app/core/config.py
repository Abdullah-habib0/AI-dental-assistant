from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All app settings. Values can be overridden in a .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./clinic.db"

    # Websites allowed to call this API from a browser. Add the deployed frontend's
    # address here (in .env as a JSON list: CORS_ORIGINS=["https://my-site.vercel.app"]).
    cors_origins: list[str] = ["http://localhost:3000"]

    # No default on purpose. If this is missing from .env the app refuses to start,
    # which is far better than quietly signing tokens with a key everyone can guess.
    secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7

    # AI agent, via Groq. The key is optional so the app and tests run without it; only
    # the chat needs it, and it says so clearly if it's missing.
    groq_api_key: str | None = None
    llm_model: str = "openai/gpt-oss-120b"
    safety_model: str = "openai/gpt-oss-20b"  # smaller and faster; it only sorts messages
    agent_max_steps: int = 8  # tool calls allowed for one message, so a confused model can't loop forever

    # Knowledge base (RAG). Changing the embedding model means running the ingest script
    # again - search refuses to mix vectors from two different models.
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    knowledge_dir: str = "./data/knowledge"
    qdrant_path: str = "./qdrant_data"
    knowledge_collection: str = "clinic_knowledge"
    knowledge_max_chunk_tokens: int = 400  # the model reads 512 at most; room left for the label
    # Measured on 24 test questions with bge-small-en-v1.5: answerable ones scored 0.595-0.890,
    # unanswerable ones 0.381-0.694. The ranges overlap, so this only filters out clearly
    # off-topic questions without losing real answers. The agent must still check that the
    # passages it gets actually answer the question. Re-measure if the model changes.
    knowledge_min_score: float = 0.55

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
