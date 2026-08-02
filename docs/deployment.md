# Deployment Guide

## Objectives

- Run the cost-service, worker, ml-service, and frontend with explicit environment configuration
- Apply Alembic migrations before serving traffic
- Use non-default secrets for PostgreSQL, RabbitMQ, JWT signing, and account-credential encryption
- Preserve ML detector state on a persistent volume mounted at the ML service model path
- Export OTLP traces to an OpenTelemetry Collector or compatible backend

## Required Secrets

Set these before deploying outside local development:

```env
JWT_SECRET_KEY=<32+ char unique secret>
ACCOUNT_CREDENTIALS_KEY=<fernet key from python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
DATABASE_URL=postgresql+asyncpg://...
RABBITMQ_URL=amqp://...
LLM_API_KEY=<optional but required for chat>
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
```

## Cost Service

1. Build and deploy the container image.
2. Run Alembic migrations:

```bash
cd services/cost-service
alembic upgrade head
```

3. Start the API service.
4. Start the worker as a separate process using `python -m app.worker`.

Set `ENABLE_STARTUP_MIGRATIONS=false` in multi-replica deployments after this step. The local Compose stack follows this same pattern using a single `migrate` job, so the API and worker never race on schema migration.

### Live provider prerequisites

The repository's `docker-compose.yml` is a safe synthetic-demo environment, not
a live-provider deployment profile. It always sets `CLOUD_SYNC_MODE=demo` and
`ALLOW_LIVE_CLOUD_SYNC=false`; values in a root `.env` do not override those
container settings. Do not attach that stack to production provider accounts or
datastores.

For a live deployment, explicitly configure **both** the API and worker with:

```env
CLOUD_SYNC_MODE=live
ALLOW_LIVE_CLOUD_SYNC=true
```

Use a dedicated deployment manifest or orchestrator configuration that excludes
the demo seed job. Supply provider credentials using the platform's secret
manager, scope them to the minimum billing-read permissions, and verify the
relevant `/api/v1/health/preflight/{provider}` response before enabling a sync.
AWS needs Cost Explorer access; Azure needs Cost Management reader access and
service-principal details; GCP needs a readable BigQuery billing export. This
repository does not provide a production-live Compose override or represent the
demo stack as validated against real provider accounts.

## ML Service

1. Mount a persistent volume to the configured `model_path` so the persisted anomaly-detector state survives restarts.
2. Install the `inference` extra if you need live Chronos inference. The default container purposefully omits the heavy optional model dependencies so the deterministic demo remains reproducible without downloading a foundation model:

```bash
pip install -e ".[inference]"
```

3. Deploy the service and scrape `/metrics`.

## Monitoring

- Prometheus scrapes `/metrics` from both backend services.
- Alert rules live in `monitoring/prometheus/alerts.yml`.
- The local Compose stack runs Alertmanager with a no-op receiver so alert state and routing are observable without emitting external notifications.
- Configure a durable receiver (for example, PagerDuty, Slack, email, or a secured webhook) before treating alerts as production notifications.

## Tracing

- Point both backend services and the worker at an OTLP collector using `OTEL_EXPORTER_OTLP_ENDPOINT`.
- Keep the collector and trace backend separate from the app containers so exporter retries do not block deploys.
- The local stack in `docker-compose.yml` uses an OpenTelemetry Collector in front of Tempo and provisions Tempo into Grafana automatically.

## Rollback

- Roll back code and then run `alembic downgrade -1` only if the release introduced a migration that must be reverted.
- Avoid manual table creation; schema state should be managed exclusively through Alembic revisions.
