from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings
from app.models.models import Base
from loguru import logger


def get_database_url() -> str:
    url = settings.DATABASE_URL
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


engine = create_async_engine(
    get_database_url(),
    echo=False,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=5,
    max_overflow=10,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")
    await seed_default_data()


async def seed_default_data():
    from app.core.security import hash_password
    from app.models.models import User, UserRole
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.username == "SOnyango"))
        if result.scalar_one_or_none():
            logger.info("Default user already exists")
            return

        logger.info("Creating default user: Samuel Onyango Okeyo...")
        user = User(
            username="SOnyango",
            email="samuel@okeyoanalytics.com",
            full_name="Samuel Onyango Okeyo",
            hashed_password=hash_password("Salvy2016!"),
            role=UserRole.administrator,
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        await db.commit()
        logger.info("Samuel Onyango Okeyo created successfully")
