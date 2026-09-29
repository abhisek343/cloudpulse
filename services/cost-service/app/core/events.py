"""
CloudPulse AI - Cost Service
Event publishing utilities.
"""
import json
import logging
from typing import Any

from aio_pika import Message, connect_robust

from app.core.config import get_settings
from app.core.logging import sanitize_error
from app.core.observability import SYNC_TASKS_PUBLISHED
from app.core.tracing import get_span_kind, get_tracer, inject_trace_headers

logger = logging.getLogger(__name__)
settings = get_settings()
tracer = get_tracer(__name__)

async def publish_sync_task(task: dict[str, Any]) -> None:
    """
    Publish a sync task to RabbitMQ.
    """
    try:
        with tracer.start_as_current_span(
            "rabbitmq.publish_sync_task",
            kind=get_span_kind("producer"),
        ) as span:
            span.set_attribute("messaging.system", "rabbitmq")
            span.set_attribute("messaging.destination.name", "cost_sync_tasks")
            span.set_attribute("messaging.operation", "publish")
            span.set_attribute("cloudpulse.task.type", task.get("type", "unknown"))

            connection = await connect_robust(settings.rabbitmq_url)
            async with connection:
                channel = await connection.channel()

                queue = await channel.declare_queue(
                    "cost_sync_tasks",
                    durable=True,
                    auto_delete=False,
                )

                message_headers = {
                    "x-cloudpulse-attempt": str(task.get("attempt", 0)),
                }
                await channel.default_exchange.publish(
                    Message(
                        body=json.dumps(task).encode(),
                        content_type="application/json",
                        headers=dict[str, Any](inject_trace_headers(message_headers)),
                    ),
                    routing_key=queue.name,
                )
                SYNC_TASKS_PUBLISHED.labels(task_type=task.get("type", "unknown"), status="published").inc()
                logger.info(
                    "Published sync task %s for account %s",
                    task.get("task_id", "unknown"),
                    task.get("account_id", "unknown"),
                )

    except Exception as exc:
        SYNC_TASKS_PUBLISHED.labels(task_type=task.get("type", "unknown"), status="failed").inc()
        logger.error("Failed to publish task: %s", sanitize_error(exc))
        raise RuntimeError("Failed to publish sync task to the message broker.") from exc
