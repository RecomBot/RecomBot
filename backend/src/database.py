# backend/src/database.py
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from shared.config import config

# Создаем асинхронный движок БД
engine = create_async_engine(
    config.DATABASE_URL,
    echo=True,  # В продакшене установить False
    future=True,
)

# Фабрика сессий
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_db() -> AsyncSession:
    """Dependency для получения сессии БД"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def create_tables():
    """Создание таблиц (только для dev/test)"""
    import shared.models
    async with engine.begin() as conn:
        await conn.run_sync(shared.models.Base.metadata.create_all)