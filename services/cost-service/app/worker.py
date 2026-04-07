"""
CloudPulse AI - Cost Service Worker
Background worker for processing asynchronous tasks (Syncing, Forecasting, etc.).
"""
import asyncio
import json
import logging
import signal
from typing import Any

from aio_pika import connect_robust, IncomingMessage

from app.core.cache import cache
from app.core.config import get_settings
from app.core.database import async_session_factory, engine, init_db
from app.core.tracing import (
    extract_trace_context,
    get_span_kind,
    get_tracer,
    setup_tracing,
)
from app.models import CloudAccount
from app.services.cost_sync import CostSyncService

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("worker")
settings = get_settings()
tracer = get_tracer(__name__)


class Worker:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.queue = None
        self.should_exit = False
        self.flush_traces = lambda: None

    async def connect(self):
        """Connect to RabbitMQ."""
        logger.info("Connecting to RabbitMQ at %s", settings.rabbitmq_url)
        self.connection = await connect_robust(settings.rabbitmq_url)
        self.channel = await self.connection.channel()
        
        # Declare queue
        self.queue = await self.channel.declare_queue(
            "cost_sync_tasks", 
            durable=True,
            auto_delete=False
        )
        await self.channel.set_qos(prefetch_count=1)

    async def process_message(self, message: IncomingMessage):
        """Process incoming sync task."""
        trace_context = extract_trace_context(message.headers)
        with tracer.start_as_current_span(
            "rabbitmq.process_sync_task",
            context=trace_context,
            kind=get_span_kind("consumer"),
        ) as span:
            span.set_attribute("messaging.system", "rabbitmq")
            span.set_attribute("messaging.destination.name", "cost_sync_tasks")
            span.set_attribute("messaging.operation", "process")
            span.set_attribute("messaging.message.payload_size_bytes", len(message.body))

            async with message.process():
                try:
                    body = message.body.decode()
                    data = json.loads(body)
                    task_type = data.get("type", "unknown")

                    span.set_attribute("cloudpulse.task.type", task_type)
                    logger.info("Received task: %s", data)

                    if task_type == "sync_account":
                        await self.handle_sync_account(data)
                    elif task_type == "sync_all":
                        await self.handle_sync_all(data)
                    else:
                        logger.warning("Unknown task type: %s", task_type)

                except Exception as e:
                    span.record_exception(e)
                    logger.error("Error processing message: %s", e, exc_info=True)

    async def handle_sync_account(self, data: dict[str, Any]):
        """Handle single account sync."""
        account_id = data.get("account_id")
        days = data.get("days", 30)
        
        async with async_session_factory() as db:
            cost_service = CostSyncService(db, cache)
            
            # Fetch account
            from sqlalchemy import select
            result = await db.execute(select(CloudAccount).where(CloudAccount.id == account_id))
            account = result.scalar_one_or_none()
            
            if not account:
                logger.error("Account %s not found", account_id)
                return

            logger.info(
                "Starting sync for account %s (%s)",
                account.account_name,
                account.provider,
            )
            try:
                result = await cost_service.sync_account_costs(account, days=days)
                await db.commit()
                logger.info("Sync completed: %s", result)
            except Exception as e:
                await db.commit()
                logger.error("Sync failed for %s: %s", account.account_name, e)
                await self._notify_sync_failure(db, account, str(e))

    async def handle_sync_all(self, data: dict[str, Any]):
        """Handle sync for all accounts in organization."""
        org_id = data.get("organization_id")
        days = data.get("days", 30)
        
        async with async_session_factory() as db:
            cost_service = CostSyncService(db, cache)
            logger.info("Starting sync for organization %s", org_id)
            results = await cost_service.sync_all_accounts(org_id, days=days)
            await db.commit()
            logger.info("Organization sync completed. Processed %s accounts.", len(results))

    async def _notify_sync_failure(self, db, account, error: str):
        """Send notifications to channels subscribed to sync_failure events."""
        from app.services.notification_service import (
            build_sync_failure_payload,
            get_notification_service,
        )

        try:
            channels = await self._get_event_channels(db, account.organization_id, "sync_failure")
            if not channels:
                return

            svc = get_notification_service()
            payload = build_sync_failure_payload(account.account_name, account.provider, error)
            for ch in channels:
                await svc.send(ch.channel_type, ch.config, "sync_failure", payload)
        except Exception as e:
            logger.warning("Failed to send sync-failure notification: %s", e)

    async def _notify_anomaly(self, db, org_id: str, anomaly: dict, account_name: str):
        """Send notifications to channels subscribed to anomaly events."""
        from app.services.notification_service import (
            build_anomaly_payload,
            get_notification_service,
        )

        try:
            channels = await self._get_event_channels(db, org_id, "anomaly")
            if not channels:
                return

            svc = get_notification_service()
            payload = build_anomaly_payload(anomaly, account_name)
            for ch in channels:
                await svc.send(ch.channel_type, ch.config, "anomaly", payload)
        except Exception as e:
            logger.warning("Failed to send anomaly notification: %s", e)

    @staticmethod
    async def _get_event_channels(db, org_id: str, event: str):
        """Return active notification channels subscribed to a given event."""
        from sqlalchemy import select
        from app.models import NotificationChannel

        result = await db.execute(
            select(NotificationChannel).where(
                NotificationChannel.organization_id == org_id,
                NotificationChannel.is_active.is_(True),
            )
        )
        return [ch for ch in result.scalars().all() if event in (ch.events or [])]

    async def run(self):
        """Run the worker loop."""
        await init_db()
        await cache.connect()
        self.flush_traces = setup_tracing(
            engine=engine,
            instrument_redis=True,
            service_name="cloudpulse-cost-worker",
        )
        await self.connect()
        
        logger.info("Worker started. Waiting for messages...")
        
        async with self.queue.iterator() as queue_iter:
            async for message in queue_iter:
                await self.process_message(message)
                
                if self.should_exit:
                    break

    async def shutdown(self):
        """Cleanup resources."""
        logger.info("Shutting down worker...")
        if self.connection:
            await self.connection.close()
        self.flush_traces()
        await cache.disconnect()


async def main():
    worker = Worker()
    
    # Handle signals
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(worker.shutdown()))
    
    try:
        await worker.run()
    except asyncio.CancelledError:
        pass
    finally:
        await worker.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
