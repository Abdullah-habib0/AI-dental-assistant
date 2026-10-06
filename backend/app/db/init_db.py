from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.base import Base

# These imports look unused, but they are not. Importing a models file is how the app
# learns that its tables exist. Without this, create_tables() would make nothing at all.
from app.features.auth import models as _auth_models  # noqa: F401
from app.features.chat import models as _chat_models  # noqa: F401
from app.features.clinic import models as _clinic_models  # noqa: F401
from app.features.scheduling import models as _scheduling_models  # noqa: F401


async def create_tables(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
