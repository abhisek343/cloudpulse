"""
CloudPulse AI Cost Worker.

Messages are acknowledged only after a sync succeeds, a duplicate is proven
idempotent, or a task has been durably marked failed after bounded retries.
"""
import asyncio
import json
import logging
import signal
from datetime import UTC, datetime
from typing import Any, Callable

from aio_pika import connect_robust
from aio_pika.abc import AbstractIncomingMessage, AbstractRobustConnection, AbstractRobustChannel, AbstractRobustQueue
from sqlalchemy import select

from app.core.cache import cache
from app.core.config import get_settings
from app.core.database import async_session_factory, engine, init_db
from app.core.events import publish_sync_task
from app.core.logging import sanitize_error
from app.core.tracing import (
    extract_trace_context,
    get_span_kind,
    get_tracer,
    setup_tracing,
)
from app.models import CloudAccount, SyncTask
from app.services.cost_sync import CostSyncService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("worker")
settings = get_settings()
tracer = get_tracer(__name__)


class Worker:
    def __init__(self) -> None:
        self.connection: AbstractRobustConnection | None = None
        self.channel: AbstractRobustChannel | None = None
        self.queue: AbstractRobustQueue | None = None
        self.should_exit = False
        self.flush_traces: Callable[[], bool | None] = lambda: None

    async def connect(self) -> None:
        """Connect to RabbitMQ and declare the durable task queue."""
        logger.info("Connecting to RabbitMQ")
        connection = await connect_robust(settings.rabbitmq_url)
        channel = await connection.channel()
        self.queue = await channel.declare_queue(
            "cost_sync_tasks",
            durable=True,
            auto_delete=False,
        )
        await channel.set_qos(prefetch_count=1)
        self.connection = connection
        self.channel = channel

    async def process_message(self, message: AbstractIncomingMessage) -> None:
        """Process one message and keep broker acknowledgment semantics explicit."""
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

            # Any unhandled infrastructure error leaves the message unacked and
            # requeues it. Business/provider failures are handled below and are
            # either retried as a new message or marked failed before ack.
            async with message.process(requeue=True):
                data = json.loads(message.body.decode())
                task_type = data.get("type", "unknown")
                span.set_attribute("cloudpulse.task.type", task_type)
                logger.info(
                    "Received task %s for account %s",
                    data.get("task_id", "unknown"),
                    data.get("account_id", "unknown"),
                )

                if task_type == "sync_account":
                    result = await self.handle_sync_account(data)
                    if not result.get("success"):
                        await self._handle_task_failure(data, result.get("error", "Sync failed"))
                elif task_type == "sync_all":
                    await self.handle_sync_all(data)
                else:
                    logger.error("Unknown task type: %s", task_type)

    async def handle_sync_account(self, data: dict[str, Any]) -> dict[str, Any]:
        """Run a single sync and persist success/error state."""
        task_id = data.get("task_id")
        account_id = data.get("account_id")
        organization_id = data.get("organization_id")
        if not task_id or not account_id or not organization_id:
            return {"success": False, "error": "Sync task is missing ownership metadata."}

        attempt = int(data.get("attempt", 0)) + 1
        async with async_session_factory() as db:
            task_result = await db.execute(
                select(SyncTask).where(
                    SyncTask.id == task_id,
                    SyncTask.organization_id == organization_id,
                    SyncTask.cloud_account_id == account_id,
                )
            )
            sync_task = task_result.scalar_one_or_none()
            if sync_task is None:
                logger.error("Sync task %s does not exist", task_id)
                return {"success": True, "duplicate": True}
            if sync_task.status == "succeeded":
                logger.info("Ignoring duplicate delivery of completed task %s", task_id)
                return {"success": True, "duplicate": True}

            account_result = await db.execute(
                select(CloudAccount).where(
                    CloudAccount.id == account_id,
                    CloudAccount.organization_id == organization_id,
                )
            )
            account = account_result.scalar_one_or_none()
            if account is None:
                return {"success": False, "error": "Sync account no longer exists."}

            sync_task.status = "running"
            sync_task.attempt = max(sync_task.attempt, attempt)
            sync_task.started_at = datetime.now(UTC)
            sync_task.error = None
            account.last_sync_status = "running"
            account.last_sync_started_at = sync_task.started_at
            account.last_sync_completed_at = None
            await db.commit()

            try:
                service = CostSyncService(db, cache)
                result = await service.sync_account_costs(account, days=int(data.get("days", 30)))
                error = result.get("error")
                if error:
                    await db.commit()
                    return {"success": False, "error": str(error)}

                sync_task.status = "succeeded"
                sync_task.records_imported = int(
                    result.get("records_processed", result.get("total_records", 0))
                )
                sync_task.completed_at = datetime.now(UTC)
                sync_task.error = None
                await db.commit()
                logger.info("Sync task %s succeeded", task_id)
                return {"success": True, "records_imported": sync_task.records_imported}
            except Exception as exc:
                await db.rollback()
                logger.error("Sync task %s raised: %s", task_id, sanitize_error(exc))
                return {"success": False, "error": sanitize_error(exc)}

    async def _persist_task_state(
        self,
        *,
        task_id: str,
        organization_id: str,
        status: str,
        error: str | None,
        attempt: int | None = None,
        completed: bool = False,
    ) -> None:
        """Persist failure/retry state in a fresh transaction after rollback."""
        async with async_session_factory() as db:
            result = await db.execute(
                select(SyncTask).where(
                    SyncTask.id == task_id,
                    SyncTask.organization_id == organization_id,
                )
            )
            sync_task = result.scalar_one_or_none()
            if sync_task is None:
                return
            sync_task.status = status
            sync_task.error = error
            if attempt is not None:
                sync_task.attempt = max(sync_task.attempt, attempt)
            if completed:
                sync_task.completed_at = datetime.now(UTC)
            account_result = await db.execute(
                select(CloudAccount).where(
                    CloudAccount.id == sync_task.cloud_account_id,
                    CloudAccount.organization_id == organization_id,
                )
            )
            account = account_result.scalar_one_or_none()
            if account is not None:
                account.last_sync_status = status
                account.last_sync_error = error
                if completed:
                    account.last_sync_completed_at = datetime.now(UTC)
            await db.commit()

    async def _handle_task_failure(self, data: dict[str, Any], error: str) -> None:
        """Retry a failed task with a new message, or durably mark it failed."""
        task_id = str(data.get("task_id", ""))
        organization_id = str(data.get("organization_id", ""))
        if not task_id or not organization_id:
            logger.error("Unowned sync task failed: %s", sanitize_error(RuntimeError(error)))
            return

        safe_error = sanitize_error(RuntimeError(error))
        attempt = int(data.get("attempt", 0))
        next_attempt = attempt + 1
        if next_attempt < settings.sync_max_attempts:
            retry_data = dict(data)
            retry_data["attempt"] = next_attempt
            await self._persist_task_state(
                task_id=task_id,
                organization_id=organization_id,
                status="queued",
                error=safe_error,
                attempt=next_attempt,
            )
            try:
                await publish_sync_task(retry_data)
            except Exception:
                await self._persist_task_state(
                    task_id=task_id,
                    organization_id=organization_id,
                    status="failed",
                    error="Retry publication failed.",
                    attempt=next_attempt,
                    completed=True,
                )
                raise
            logger.warning(
                "Retrying sync task %s (attempt %d/%d)",
                task_id,
                next_attempt + 1,
                settings.sync_max_attempts,
            )
            return

        await self._persist_task_state(
            task_id=task_id,
            organization_id=organization_id,
            status="failed",
            error=safe_error,
            attempt=attempt + 1,
            completed=True,
        )
        logger.error("Sync task %s failed after %d attempts", task_id, attempt + 1)

    async def handle_sync_all(self, data: dict[str, Any]) -> None:
        """Handle the legacy organization-wide task path."""
        organization_id = data.get("organization_id")
        if not organization_id:
            raise ValueError("sync_all task is missing organization ownership")
        async with async_session_factory() as db:
            service = CostSyncService(db, cache)
            results = await service.sync_all_accounts(organization_id, days=int(data.get("days", 30)))
            await db.commit()
            if any(result.get("error") for result in results):
                raise RuntimeError("One or more account syncs failed")
            logger.info("Organization sync completed for %s accounts", len(results))

    async def run(self) -> None:
        await init_db()
        await cache.connect()
        self.flush_traces = setup_tracing(
            engine=engine,
            instrument_redis=True,
            service_name="cloudpulse-cost-worker",
        )
        await self.connect()
        logger.info("Worker started. Waiting for messages...")
        if self.queue is None:
            raise RuntimeError("Worker queue was not initialized")
        async with self.queue.iterator() as queue_iter:
            async for message in queue_iter:
                await self.process_message(message)
                if self.should_exit:
                    break

    async def shutdown(self) -> None:
        logger.info("Shutting down worker...")
        if self.connection:
            await self.connection.close()
        self.flush_traces()
        await cache.disconnect()


async def main() -> None:
    worker = Worker()
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
