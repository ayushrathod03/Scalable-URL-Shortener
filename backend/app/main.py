import time
import logging
import asyncio
from typing import Optional
from datetime import datetime, timezone

from fastapi import FastAPI, Depends, HTTPException, Request, Response, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from sqlalchemy import text, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db, init_db, AsyncSessionLocal
from app.models import URL, ClickAnalytics
from app.schemas import (
    URLShortenRequest, 
    URLResponse, 
    URLAnalyticsResponse, 
    GlobalAnalyticsResponse,
    DailyClickCount,
    CountryClickCount
)
from app.encoding import Base62Encoder
from app.cache import get_cached_url, set_cached_url, redis_client
from app.queue_client import queue_client
from app.rate_limiter import RedisRateLimiter
from app.metrics import (
    HTTP_REQUEST_DURATION_SECONDS, 
    track_rabbitmq_queue_depth
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("api_gateway")

# Lifespan context manager for startup/shutdown actions
async def lifespan(app: FastAPI):
    # 1. Initialize databases and partitions
    await init_db()
    
    # 2. Warm up Bloom Filter
    async with AsyncSessionLocal() as session:
        try:
            logger.info("Warming up Bloom Filter...")
            result = await session.execute(select(URL.short_token))
            tokens = [row[0] for row in result.all()]
            if tokens:
                from app.cache import bloom_filter
                await bloom_filter.add_multi(tokens)
                logger.info(f"Bloom Filter warmed up with {len(tokens)} existing tokens.")
            else:
                logger.info("Bloom Filter warm up skipped (no URLs in database).")
        except Exception as e:
            logger.critical(f"Could not warm up Bloom Filter: {e}")

    # 3. Connect queue publisher
    await queue_client.connect()
    
    # 4. Start Prometheus queue-depth monitor
    asyncio.create_task(track_rabbitmq_queue_depth(settings.RABBITMQ_URL))
    
    yield
    
    # Close resources
    await redis_client.close()

app = FastAPI(
    title="Scalable URL Shortener & Telemetry Pipeline",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for frontend dashboard connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict to frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Process latency tracking middleware
@app.middleware("http")
async def track_latency_middleware(request: Request, call_next):
    start_time = time.time()
    
    # Match route for prometheus label
    handler = request.url.path
    # Clean up variables inside path (e.g., replace actual short_token with placeholder)
    if "/api/v1/redirect/" in handler:
        handler = "/api/v1/redirect/{short_token}"
    elif "/api/v1/analytics/" in handler:
        handler = "/api/v1/analytics/{short_token}"
        
    method = request.method
    
    try:
        response = await call_next(request)
    finally:
        latency = time.time() - start_time
        HTTP_REQUEST_DURATION_SECONDS.labels(method=method, handler=handler).observe(latency)
        
    return response


# --- 1. Fast Path: The Redirection Engine ---
@app.get("/api/v1/redirect/{short_token}")
async def redirect_url(
    short_token: str, 
    request: Request, 
    background_tasks: BackgroundTasks, 
    db: AsyncSession = Depends(get_db)
):
    """
    Sub-millisecond redirection engine path (Fast Path).
    1. Queries Redis cache.
    2. Fallback to Bloom Filter lookup on cache miss.
    3. Query Postgres only if Bloom Filter registers a potential hit.
    4. Queues click telemetry asynchronously to RabbitMQ.
    """
    # Step A: Cache Lookup
    cached_url = await get_cached_url(short_token)
    
    if cached_url == "__NOT_FOUND__":
        # Bloom Filter validated key non-existence; terminate immediately (prevents DB scraping)
        raise HTTPException(status_code=404, detail="Short URL not found (Bloom Filter check)")
    
    if cached_url:
        # Cache hit: Trigger telemetry push and return redirect
        background_tasks.add_task(
            log_click_telemetry, 
            short_token, 
            request
        )
        return RedirectResponse(url=cached_url, status_code=302)
        
    # Step B: Cache Miss - Query Database
    logger.info(f"Redirection cache miss for token: {short_token}. Querying database...")
    result = await db.execute(
        select(URL).where(URL.short_token == short_token)
    )
    url_record = result.scalar_one_or_none()
    
    if not url_record:
        raise HTTPException(status_code=404, detail="Short URL not found")
        
    # Check expiration
    if url_record.expires_at and url_record.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Short URL has expired")
        
    # Step C: Populate Cache for subsequent requests
    background_tasks.add_task(
        set_cached_url, 
        short_token, 
        url_record.long_url, 
        settings.CACHE_TTL
    )
    
    # Step D: Log telemetry asynchronously
    background_tasks.add_task(
        log_click_telemetry, 
        short_token, 
        request
    )
    
    return RedirectResponse(url=url_record.long_url, status_code=302)


# --- 2. Write Path: URL Shortening ---
@app.post("/api/v1/shorten", response_model=URLResponse)
async def shorten_url(payload: URLShortenRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """
    Saves a long URL target, generates sequential Base62 short token, and updates Cache.
    Requires Redis sliding-window rate limit validation.
    """
    # 1. Enforce Sliding-Window Rate Limit
    client_ip = request.client.host if request.client else "unknown_client"
    # Can extract API key from header if present
    client_key = request.headers.get("x-api-key", client_ip)
    
    allowed = await RedisRateLimiter.is_allowed(client_key)
    if not allowed:
        raise HTTPException(
            status_code=429, 
            detail="Rate limit exceeded. Maximum 10 writes per minute allowed."
        )
        
    # 2. Validate URL Format
    try:
        validated_url = payload.validate_url()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    # 3. Retrieve database sequence key (Postgres sequence nextval)
    try:
        result = await db.execute(text("SELECT nextval('urls_id_seq')"))
        next_id = result.scalar()
    except Exception as e:
        logger.error(f"Failed to fetch ID sequence from database: {e}")
        raise HTTPException(status_code=500, detail="Database sequence generation failed.")
        
    # 4. Generate Base62 token
    short_token = Base62Encoder.encode(next_id)
    
    # 5. Insert row in single optimized call
    expires_utc = payload.expires_at.astimezone(timezone.utc) if payload.expires_at else None
    
    new_url = URL(
        id=next_id,
        short_token=short_token,
        long_url=validated_url,
        expires_at=expires_utc
    )
    
    db.add(new_url)
    await db.commit()
    await db.refresh(new_url)
    
    # 6. Populate Cache & Bloom Filter asynchronously
    await set_cached_url(short_token, validated_url, settings.CACHE_TTL)
    
    # Construct response
    base_url = str(request.base_url)
    # Ensure redirects target our API redirection path
    short_url = f"{base_url}api/v1/redirect/{short_token}"
    
    return URLResponse(
        short_token=short_token,
        short_url=short_url,
        long_url=new_url.long_url,
        created_at=new_url.created_at,
        expires_at=new_url.expires_at
    )


# --- 3. Analytics Retrieval Endpoints ---
@app.get("/api/v1/analytics/{short_token}", response_model=URLAnalyticsResponse)
async def get_url_analytics(short_token: str, db: AsyncSession = Depends(get_db)):
    """Retrieves access statistics for a specific URL token."""
    # Verify URL exists
    result = await db.execute(select(URL).where(URL.short_token == short_token))
    url_record = result.scalar_one_or_none()
    if not url_record:
        raise HTTPException(status_code=404, detail="Short URL not found")
        
    # 1. Total Clicks
    clicks_count_res = await db.execute(
        select(func.count(ClickAnalytics.id)).where(ClickAnalytics.short_token == short_token)
    )
    total_clicks = clicks_count_res.scalar() or 0
    
    # 2. Timeline Aggregations (Last 30 Days)
    timeline_query = text("""
        SELECT clicked_at::date as day, COUNT(*) as count 
        FROM click_analytics 
        WHERE short_token = :token 
          AND clicked_at >= NOW() - INTERVAL '30 days'
        GROUP BY day 
        ORDER BY day ASC
    """)
    timeline_res = await db.execute(timeline_query, {"token": short_token})
    timeline_data = [
        DailyClickCount(date=str(row[0]), clicks=row[1]) 
        for row in timeline_res.all()
    ]
    
    # 3. Geographical Country Aggregations
    geo_query = text("""
        SELECT country_code, COUNT(*) as count 
        FROM click_analytics 
        WHERE short_token = :token 
        GROUP BY country_code 
        ORDER BY count DESC
    """)
    geo_res = await db.execute(geo_query, {"token": short_token})
    geo_data = [
        CountryClickCount(country=row[0], clicks=row[1]) 
        for row in geo_res.all()
    ]
    
    return URLAnalyticsResponse(
        short_token=short_token,
        long_url=url_record.long_url,
        created_at=url_record.created_at,
        expires_at=url_record.expires_at,
        total_clicks=total_clicks,
        clicks_over_time=timeline_data,
        geo_distribution=geo_data
    )

@app.get("/api/v1/analytics", response_model=GlobalAnalyticsResponse)
async def get_global_analytics(db: AsyncSession = Depends(get_db)):
    """Retrieves overall dashboard aggregation statistics across all links."""
    # 1. Total URLs Count
    urls_count_res = await db.execute(select(func.count(URL.id)))
    total_urls = urls_count_res.scalar() or 0
    
    # 2. Total Clicks Count
    clicks_count_res = await db.execute(select(func.count(ClickAnalytics.id)))
    total_clicks = clicks_count_res.scalar() or 0
    
    # 3. Global Timeline Aggregations (Last 30 Days)
    timeline_query = text("""
        SELECT clicked_at::date as day, COUNT(*) as count 
        FROM click_analytics 
        WHERE clicked_at >= NOW() - INTERVAL '30 days'
        GROUP BY day 
        ORDER BY day ASC
    """)
    timeline_res = await db.execute(timeline_query)
    timeline_data = [
        DailyClickCount(date=str(row[0]), clicks=row[1]) 
        for row in timeline_res.all()
    ]
    
    # 4. Global Geo Distribution
    geo_query = text("""
        SELECT country_code, COUNT(*) as count 
        FROM click_analytics 
        GROUP BY country_code 
        ORDER BY count DESC
    """)
    geo_res = await db.execute(geo_query)
    geo_data = [
        CountryClickCount(country=row[0], clicks=row[1]) 
        for row in geo_res.all()
    ]
    
    return GlobalAnalyticsResponse(
        total_urls=total_urls,
        total_clicks=total_clicks,
        clicks_over_time=timeline_data,
        geo_distribution=geo_data
    )


# --- 4. Observability Metrics Endpoint ---
@app.get("/metrics")
def expose_metrics():
    """Endpoint scraped by Prometheus server."""
    return Response(
        content=generate_latest(), 
        media_type=CONTENT_TYPE_LATEST
    )


# --- Helper Methods ---
async def log_click_telemetry(short_token: str, request: Request) -> None:
    """Extracts HTTP headers and publishes telemetry to RabbitMQ queue."""
    ip_addr = request.client.host if request.client else "0.0.0.0"
    user_agent = request.headers.get("user-agent", "unknown")
    timestamp = int(time.time())
    
    # Dispatch non-blocking call to queue
    await queue_client.publish_click(
        short_token=short_token,
        timestamp=timestamp,
        ip_address=ip_addr,
        user_agent=user_agent
    )
