"""
CloudPulse AI - Cost Service
Event publishing utilities.
"""
import json
import logging
from typing import Any

from aio_pika import Message, connect_robust

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

async def publish_sync_task(task: dict[str, Any]) -> None:
    """
    Publish a sync task to RabbitMQ.
    """
    try:
        connection = await connect_robust(settings.rabbitmq_url)
        async with connection:
            channel = await connection.channel()
            
            # Ensure queue exists
            queue = await channel.declare_queue(
                "cost_sync_tasks", 
                durable=True,
                auto_delete=False
            )
            
            await channel.default_exchange.publish(
                Message(
                    body=json.dumps(task).encode(),
                    content_type="application/json",
                ),
                routing_key=queue.name,
            )
            logger.info(f"Published task: {task}")
            
    except Exception as e:
        logger.error(f"Failed to publish task: {e}")
        # We might want to re-raise or handle gracefully depending on requirements
        # For now, just log it so API doesn't crash
