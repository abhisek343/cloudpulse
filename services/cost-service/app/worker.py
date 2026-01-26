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
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.database import async_session_factory, init_db
from app.core.cache import cache
from app.models import CloudAccount
from app.services.cost_sync import CostSyncService

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("worker")
settings = get_settings()


class Worker:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.queue = None
        self.should_exit = False

    async def connect(self):
        """Connect to RabbitMQ."""
        logger.info(f"Connecting to RabbitMQ at {settings.rabbitmq_url}")
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
        async with message.process():
            try:
                body = message.body.decode()
                data = json.loads(body)
                logger.info(f"Received task: {data}")

                task_type = data.get("type")
                
                if task_type == "sync_account":
                    await self.handle_sync_account(data)
                elif task_type == "sync_all":
                    await self.handle_sync_all(data)
                else:
                    logger.warning(f"Unknown task type: {task_type}")

            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)

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
                logger.error(f"Account {account_id} not found")
                return

            logger.info(f"Starting sync for account {account.account_name} ({account.provider})")
            result = await cost_service.sync_account_costs(account, days=days)
            logger.info(f"Sync completed: {result}")

    async def handle_sync_all(self, data: dict[str, Any]):
        """Handle sync for all accounts in organization."""
        org_id = data.get("organization_id")
        days = data.get("days", 30)
        
        async with async_session_factory() as db:
            cost_service = CostSyncService(db, cache)
            logger.info(f"Starting sync for organization {org_id}")
            results = await cost_service.sync_all_accounts(org_id, days=days)
            logger.info(f"Organization sync completed. Processed {len(results)} accounts.")

    async def run(self):
        """Run the worker loop."""
        await init_db()
        await cache.connect()
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
