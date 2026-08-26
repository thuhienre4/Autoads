from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG is True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    # Production deployments should run migrations; this lightweight hook validates connectivity only.
    async with engine.begin() as connection:
        await connection.run_sync(lambda sync_conn: None)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
