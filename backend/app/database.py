import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from app.config import settings

logger = logging.getLogger(__name__)

# Create Async Engine for PostgreSQL
engine = create_async_engine(settings.DATABASE_URL, echo=False)

# Session factory for route handlers
AsyncSessionLocal = async_sessionmaker(
    bind=engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

async def get_db():
    """Dependency to provide database session to endpoints."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def create_partition_for_date(conn, dt: datetime):
    """Generates monthly partition for the click_analytics table."""
    year = dt.year
    month = dt.month
    partition_name = f"click_analytics_y{year:04d}m{month:02d}"
    
    start_date = f"{year:04d}-{month:02d}-01 00:00:00+00"
    
    if month == 12:
        n_year = year + 1
        n_month = 1
    else:
        n_year = year
        n_month = month + 1
    end_date = f"{n_year:04d}-{n_month:02d}-01 00:00:00+00"
    
    query = text(f"""
    CREATE TABLE IF NOT EXISTS {partition_name} 
    PARTITION OF click_analytics 
    FOR VALUES FROM ('{start_date}') TO ('{end_date}');
    """)
    try:
        await conn.execute(query)
        logger.info(f"Verified existence of partition: {partition_name}")
    except Exception as e:
        logger.error(f"Failed to create partition {partition_name}: {e}")

async def init_db():
    """Initializes schema and indexes, and provisions current/next monthly partitions."""
    async with engine.begin() as conn:
        logger.info("Initializing database schemas...")
        
        # 1. Create urls table
        await conn.execute(text("""
        CREATE TABLE IF NOT EXISTS urls (
            id BIGSERIAL PRIMARY KEY,
            short_token VARCHAR(10) UNIQUE NOT NULL,
            long_url TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP WITH TIME ZONE
        );
        """))
        
        # 2. Create index on urls.short_token
        await conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_urls_token ON urls(short_token);
        """))
        
        # 3. Create partitioned click_analytics table
        await conn.execute(text("""
        CREATE TABLE IF NOT EXISTS click_analytics (
            id BIGSERIAL,
            short_token VARCHAR(10) NOT NULL,
            clicked_at TIMESTAMP WITH TIME ZONE NOT NULL,
            ip_address VARCHAR(45),
            user_agent TEXT,
            country_code VARCHAR(3),
            PRIMARY KEY (id, clicked_at),
            FOREIGN KEY (short_token) REFERENCES urls(short_token) ON DELETE CASCADE
        ) PARTITION BY RANGE (clicked_at);
        """))
        
        # 4. Create index on click_analytics
        await conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_analytics_token_time ON click_analytics(short_token, clicked_at);
        """))
        
        # 5. Provision partitions (Current Month & Next Month)
        now = datetime.utcnow()
        await create_partition_for_date(conn, now)
        
        if now.month == 12:
            next_month = datetime(now.year + 1, 1, 1)
        else:
            next_month = datetime(now.year, now.month + 1, 1)
        await create_partition_for_date(conn, next_month)
        
        logger.info("Database schemas initialization completed successfully.")
