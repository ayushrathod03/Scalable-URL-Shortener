import json
import logging
import aio_pika
from app.config import settings

logger = logging.getLogger(__name__)

class QueueClient:
    def __init__(self, rabbitmq_url: str):
        self.rabbitmq_url = rabbitmq_url
        self.connection = None
        self.channel = None

    async def connect(self) -> None:
        """Establishes robust connection to RabbitMQ broker and declares target queue."""
        try:
            self.connection = await aio_pika.connect_robust(self.rabbitmq_url)
            self.channel = await self.connection.channel()
            # Queue must be durable to survive broker restarts
            await self.channel.declare_queue("link-clicks", durable=True)
            logger.info("Successfully established connection to RabbitMQ broker.")
        except Exception as e:
            logger.error(f"Failed to establish RabbitMQ connection: {e}")
            # Fail fast on init, but we'll try to reconnect on publish if needed
            self.connection = None
            self.channel = None

    async def publish_click(self, short_token: str, timestamp: int, ip_address: str, user_agent: str) -> None:
        """Dispatches click event JSON payload asynchronously to the link-clicks queue."""
        payload = {
            "short_token": short_token,
            "timestamp": timestamp,
            "ip_address": ip_address,
            "user_agent": user_agent
        }
        
        try:
            # Reconnect if channel is closed or connection is not established
            if not self.channel or self.channel.is_closed:
                await self.connect()
                
            if not self.channel:
                raise RuntimeError("RabbitMQ channel not initialized.")

            message = aio_pika.Message(
                body=json.dumps(payload).encode("utf-8"),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            )
            
            await self.channel.default_exchange.publish(
                message,
                routing_key="link-clicks"
            )
        except Exception as e:
            # Critical decoupling boundary: log failure, but DO NOT block redirection execution path
            logger.critical(f"Async analytics pipeline dropped payload for token {short_token}: {e}")

queue_client = QueueClient(settings.RABBITMQ_URL)
