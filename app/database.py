from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings

settings = get_settings()

# Convert Railway's MySQL URL to aiomysql format
database_url = settings.database_url
if database_url.startswith("mysql://"):
    database_url = "mysql+aiomysql://" + database_url[8:]
elif not database_url.startswith("mysql+aiomysql://"):
    # Handle any other format
    database_url = database_url.replace("mysql+mysqldb://", "mysql+aiomysql://")
    database_url = database_url.replace("mysql+pymysql://", "mysql+aiomysql://")

# Create engine - works with both MySQL and PostgreSQL
engine = create_async_engine(
    database_url,
    echo=True,
    pool_pre_ping=True,  # Reconnect on stale connections
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
