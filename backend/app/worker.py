import asyncio
import json
import logging
import time
import hashlib
from datetime import datetime, timezone
import aio_pika
from sqlalchemy import insert
from app.config import settings
from app.database import AsyncSessionLocal
from app.models import ClickAnalytics

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("telemetry_worker")

async def resolve_country_code(ip: str) -> str:
    """
    Simulates a fast, non-blocking Geo-IP lookup.
    - Tags local loopback addresses as 'LCL'.
    - Hash-maps public IPs to standard ISO country codes for simulated metrics.
    """
    if not ip or ip in ("127.0.0.1", "localhost", "::1", "0.0.0.0"):
        return "LCL"
    
    # Deterministic hash mapping for visualization simulation
    h = int(hashlib.md5(ip.encode("utf-8")).hexdigest(), 16)
    countries = ["US", "GB", "DE", "CA", "IN", "FR", "JP", "AU", "SG", "BR", "ZA", "NL", "AE", "KR"]
    return countries[h % len(countries)]


class BatchTelemetryConsumer:
    def __init__(self, rabbitmq_url: str):
        self.rabbitmq_url = rabbitmq_url
        self.batch = []
        self.lock = asyncio.Lock()
        self.max_batch_size = 500
        self.flush_interval = 2.0  # seconds
        self.last_flush = time.time()
        self.running = True

    async def start(self) -> None:
        """Starts the RabbitMQ queue consumer and batch timer."""
        # Wait a bit for RabbitMQ to fully boot up in docker environments
        retries = 10
        connection = None
        while retries > 0:
            try:
                connection = await aio_pika.connect_robust(self.rabbitmq_url)
                break
            except Exception as e:
                logger.warning(f"Waiting for RabbitMQ to become reachable... ({retries} retries left)")
                retries -= 1
                await asyncio.sleep(3)
        
        if not connection:
            logger.critical("Could not connect to RabbitMQ. Exiting worker.")
            return

        async with connection:
            channel = await connection.channel()
            # Set QOS (prefetch count) to ensure we don't choke on high throughput
            await channel.set_qos(prefetch_count=1000)
            
            queue = await channel.declare_queue("link-clicks", durable=True)
            logger.info("Connected to RabbitMQ. Waiting for telemetry clicks on 'link-clicks' queue...")
            
            # Launch periodic flushing loop
            asyncio.create_task(self.timer_loop())
            
            # Consume loop
            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    if not self.running:
                        break
                    
                    async with self.lock:
                        self.batch.append(message)
                    
                    # Flush immediately if capacity met
                    if len(self.batch) >= self.max_batch_size:
                        await self.flush_batch()

    async def timer_loop(self) -> None:
        """Periodic checker that triggers a flush if the flush interval elapsed."""
        while self.running:
            await asyncio.sleep(0.5)
            if time.time() - self.last_flush >= self.flush_interval:
                await self.flush_batch()

    async def flush_batch(self) -> None:
        """Executes bulk insert of the buffered events into PostgreSQL."""
        async with self.lock:
            if not self.batch:
                return
            
            messages_to_process = list(self.batch)
            self.batch.clear()
            self.last_flush = time.time()

        logger.info(f"Processing batch of {len(messages_to_process)} analytics clicks...")
        
        records = []
        for msg in messages_to_process:
            try:
                payload = json.loads(msg.body.decode("utf-8"))
                short_token = payload["short_token"]
                ts = payload["timestamp"]
                ip = payload["ip_address"]
                ua = payload["user_agent"]
                
                # Parse timestamp epoch to datetime
                if ts > 1e11:  # Milliseconds check
                    dt = datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc)
                else:
                    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                
                country = await resolve_country_code(ip)
                
                records.append({
                    "short_token": short_token,
                    "clicked_at": dt,
                    "ip_address": ip,
                    "user_agent": ua,
                    "country_code": country
                })
            except Exception as e:
                logger.error(f"Failed to parse event message, dropping: {e}")
                # Acknowledge broken messages to prevent queue locking
                try:
                    await msg.ack()
                except Exception:
                    pass

        if not records:
            return

        # Perform optimized bulk SQL insertion
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    # SQLAlchemy 2.0 Bulk Insertion API
                    await session.execute(insert(ClickAnalytics), records)
                await session.commit()
                
            logger.info(f"Committed {len(records)} telemetry logs to PostgreSQL.")
            
            # Acknowledge all processed messages
            for msg in messages_to_process:
                try:
                    await msg.ack()
                except Exception as ack_err:
                    logger.error(f"Ack failed: {ack_err}")
        except Exception as db_err:
            logger.error(f"PostgreSQL database bulk insert failed: {db_err}")
            # On database failure, restore messages to buffer for retry and sleep
            async with self.lock:
                self.batch = messages_to_process + self.batch
            logger.warning("Postponed batch processing; sleeping for 3 seconds...")
            await asyncio.sleep(3.0)


if __name__ == "__main__":
    consumer = BatchTelemetryConsumer(settings.RABBITMQ_URL)
    try:
        asyncio.run(consumer.start())
    except KeyboardInterrupt:
        logger.info("Worker daemon terminated by user request.")
