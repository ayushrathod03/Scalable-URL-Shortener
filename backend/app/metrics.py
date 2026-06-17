import asyncio
import logging
import aio_pika
from prometheus_client import Counter, Histogram, Gauge

logger = logging.getLogger(__name__)

# Cache Hit/Miss Counter
CACHE_REQUESTS_TOTAL = Counter(
    "cache_requests_total",
    "Total number of redirection cache lookups",
    ["result"] # "hit" or "miss"
)

# API Request Latency Histogram
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "handler"]
)

# RabbitMQ Queue Size Gauge
RABBITMQ_QUEUE_DEPTH = Gauge(
    "rabbitmq_queue_depth",
    "Number of click analytics telemetry items buffered in RabbitMQ",
    ["queue"]
)

async def track_rabbitmq_queue_depth(rabbitmq_url: str, interval: int = 5):
    """Periodically queries RabbitMQ to update the queue size gauge."""
    while True:
        try:
            connection = await aio_pika.connect_robust(rabbitmq_url)
            async with connection:
                channel = await connection.channel()
                # Passive declaration checks the queue stats without modifying/creating
                queue = await channel.declare_queue("link-clicks", passive=True)
                RABBITMQ_QUEUE_DEPTH.labels(queue="link-clicks").set(queue.message_count)
        except Exception as e:
            # Queue might not be created yet, or RabbitMQ might be initializing
            RABBITMQ_QUEUE_DEPTH.labels(queue="link-clicks").set(0)
            logger.debug(f"Could not fetch RabbitMQ queue size: {e}")
        
        await asyncio.sleep(interval)
