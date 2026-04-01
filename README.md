# CloudPulse AI

<div align="center">

![CloudPulse AI](https://img.shields.io/badge/CloudPulse-AI-blue?style=for-the-badge&logo=cloud)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python)](https://www.python.org/)
[![Next.js 16](https://img.shields.io/badge/Next.js-16-black?style=for-the-badge&logo=next.js)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)

### Predict cloud costs before they surprise you. Ask questions in plain English.

*An open-source, privacy-first FinOps platform with AI-powered forecasting and natural language queries.*

[Quick Start](#-quick-start) | [Features](#-features) | [Architecture](#-architecture) | [Contributing](CONTRIBUTING.md)

</div>

---

## Why I Built This

Existing FinOps tools show you what you **already spent**. That's not helpful when your bill arrives.

I wanted a tool that:
- **Predicts** next month's costs using foundation models (Amazon Chronos)
- **Explains** cost spikes in plain English ("Why did EC2 costs jump last Tuesday?")
- **Simulates** savings scenarios before you commit ("What if I move 40% to Spot?")
- **Runs locally** - your billing data never leaves your VPC

CloudPulse AI is my answer to: *"What if FinOps tools were actually proactive?"*

---

## Demo

<!-- Add your screenshots/GIFs here -->
<div align="center">

| **Mission Control** | **AI Predictions** |
|:---:|:---:|
| ![Dashboard](docs/screenshots/dashboard.png) | ![Predictions](docs/screenshots/predictions.png) |

| **Cloud Accounts** | **FinOps Analyst** |
|:---:|:---:|
| ![Accounts](docs/screenshots/accounts.png) | ![Chat](docs/screenshots/chat.png) |

</div>

---

## Features

### AI-Powered Cost Forecasting
- **Amazon Chronos** (T5-based foundation model) for zero-shot time-series prediction
- Confidence intervals (10th-90th percentile) for risk assessment
- No training required - works out of the box with your data

### Natural Language Queries
- *"Why did my costs spike last week?"*
- *"Which service is growing fastest?"*
- Works with OpenAI, Claude, Gemini, or local models (Ollama)
- Uses cost data already stored in CloudPulse as chat context

### What-If Cost Simulator
- Interactive scenarios: *"What if I move 40% to Spot Instances?"*
- Real-time savings projections
- Client-side calculations - no backend latency

### Anomaly Detection
- Isolation Forest algorithm detects unusual spending patterns
- Configurable sensitivity (low/medium/high)
- Automatic alerts for cost spikes

### Multi-Cloud Ready
- Unified provider abstraction layer
- AWS Cost Explorer integration (Azure, GCP: PRs welcome!)
- Extensible for custom/on-prem providers

---

## Architecture

```
                              CloudPulse AI
    ================================================================
    
         [Frontend]              [Monitoring]         [Tracing]
          Next.js            Prometheus / Grafana    OTel / Tempo
           :3005                :9090 / :3001       :4317 / :3200
              |                       |                   |
    ----------|=======================|===================|------
              |                       |                   |
              v                       v                   v
    ================================================================
               Next.js Same-Origin API Proxy Layer
    ================================================================
              |                                           |
              v                                           v
    +-------------------+                     +-------------------+
    |   Cost Service    |                     |    ML Service     |
    |     (FastAPI)     |                     |     (FastAPI)     |
    |       :8001       |                     |       :8002       |
    |                   |                     |                   |
    | - Cost aggregation|                     | - Chronos (T5)    |
    | - Provider sync   |                     | - Isolation Forest|
    | - K8s attribution |                     | - LLM integration |
    +-------------------+                     +-------------------+
              |                                           |
    ----------|===========================================|----------
              |                  |                        |
              v                  v                        v
    +----------+  +---------+  +------------+  +------------------+
    | Postgres |  |  Redis  |  |  RabbitMQ  |  | Cloud Provider   |
    |   :5432  |  |  :6379  |  |   :5672    |  | APIs (AWS, etc.) |
    +----------+  +---------+  +------------+  +------------------+
                                     ^
                                     |
                          +-------------------+
                          |    Cost Worker    |
                          | (Background Job)  |
                          | - Data Syncing    |
                          +-------------------+
```

---

## Quick Start

### Prerequisites
- Docker & Docker Compose
- 4GB RAM (Chronos model is ~400MB)

### 1. Configure Environment

```bash
git clone https://github.com/abhisek343/cloudpulse.git
cd cloudpulse
cp .env.example .env
```

### 2. Start The Stack

```bash
docker compose up --build -d
```

By default, CloudPulse runs in safe demo mode:
- no real cloud API calls
- no cloud credentials required
- local-only synthetic billing data paths
- the cost-service applies Alembic migrations on startup before serving traffic

### 3. Seed The Demo Tenant

```bash
docker compose exec cost-service python /app/scripts/seed_data.py --reset
```

This creates:
- a demo admin user
- four demo accounts across AWS, Azure, and GCP-shaped workloads
- deterministic cost history with spikes, credits, tag gaps, service-mix shifts, and seasonality

### Demo Login

```text
Email:    demo@cloudpulse.local
Password: DemoPass123!
```

### Access Points

| Service | URL | Notes |
|---------|-----|-------|
| **Dashboard** | http://localhost:3005 | Main UI |
| **Settings** | http://localhost:3005/settings | Demo/live mode and provider readiness |
| **Cost API** | http://localhost:8001/docs | Swagger docs |
| **ML API** | http://localhost:8002/docs | Swagger docs |
| **Grafana** | http://localhost:3001 | admin / cloudpulse |
| **Prometheus** | http://localhost:9090 | Metrics |
| **Tempo** | http://localhost:3200 | Trace backend API |

### Distributed Tracing

- `cost-service`, `cost-worker`, and `ml-service` export OTLP traces to the local OpenTelemetry Collector.
- The collector forwards traces to Tempo, which is pre-provisioned in Grafana Explore.
- RabbitMQ sync tasks propagate W3C trace context so API-triggered sync work stays on the same trace in the worker.

### Common Local Commands

```bash
# Stop services
docker compose down

# Rebuild after backend/frontend changes
docker compose up --build -d

# Reseed demo data
docker compose exec cost-service python /app/scripts/seed_data.py --reset
```

### Switch To Real Cloud Data Later

CloudPulse is demo-first, but the live-provider path is env-driven. You should not
need code changes to switch from demo to real sync.

1. Update `.env` to enable live sync:

```env
CLOUD_SYNC_MODE=live
ALLOW_LIVE_CLOUD_SYNC=true
NEXT_PUBLIC_DEFAULT_ACCOUNT_PROVIDER=aws
```

2. Add provider credentials through environment variables or account credentials.

Provider readiness today:
- AWS: live sync plus in-app preflight validation
- Azure: live sync plus in-app tenant/API preflight validation
- GCP: live path works through a standard BigQuery billing export

AWS:

```env
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_REGION=us-east-1
```

Azure:

```env
AZURE_SUBSCRIPTION_ID=your-subscription-id
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret
NEXT_PUBLIC_DEFAULT_ACCOUNT_PROVIDER=azure
```

GCP:

```env
GCP_PROJECT_ID=your-project-id
GCP_BILLING_ACCOUNT_ID=your-billing-account-id
GCP_SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"..."}
GCP_BILLING_EXPORT_TABLE=your-project.your_dataset.gcp_billing_export_v1
NEXT_PUBLIC_DEFAULT_ACCOUNT_PROVIDER=gcp
```

3. Rebuild the stack so frontend `NEXT_PUBLIC_*` settings are baked into the app:

```bash
docker compose up --build -d
```

4. Add a real cloud account from the UI and trigger sync.

5. Open `Settings` and run provider preflight checks to verify credentials, API access,
   and the cost source before you trust a live sync.

For supported live providers, CloudPulse falls back to env-backed provider credentials
when the account record itself does not include credential fields. That keeps the OSS
setup plug-and-play while still allowing per-account overrides.

The runtime mode and provider readiness snapshot is available at `/api/v1/health/runtime`
and surfaced in the Settings page so users can verify their live/demo state immediately.
CloudPulse also exposes `/api/v1/health/preflight/{provider}` for AWS, Azure, and GCP,
which runs a lightweight live smoke test and reports missing env vars or access issues.

---

## Tech Stack

| Layer | Technology | Why |
|-------|------------|-----|
| **ML/AI** | Amazon Chronos (T5), scikit-learn | Foundation model for zero-shot forecasting |
| **Backend** | FastAPI, SQLAlchemy 2.0, Pydantic | Async-first, type-safe Python |
| **Frontend** | Next.js 16, TypeScript, Tailwind | Modern React with App Router |
| **Data** | PostgreSQL, Redis, RabbitMQ | Battle-tested infrastructure |
| **Observability** | Prometheus, Grafana | Production-ready monitoring |

---

## Project Structure

```
cloudpulse-ai/
├── services/
│   ├── cost-service/          # Cost data ingestion & aggregation
│   │   ├── app/
│   │   │   ├── api/           # REST endpoints
│   │   │   ├── services/      # Business logic + provider adapters
│   │   │   └── models/        # SQLAlchemy models
│   │   ├── worker.py          # Background task worker
│   │   └── tests/
│   │
│   └── ml-service/            # Predictions & anomaly detection
│       ├── app/
│       │   ├── api/           # ML endpoints
│       │   └── services/      # Chronos + Isolation Forest
│       └── tests/
│
├── frontend/                  # Next.js dashboard
├── monitoring/                # Prometheus + Grafana configs
├── docker-compose.yml
└── README.md
```

---

## API Reference

### Cost Service (`/api/v1`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/costs/summary` | GET | Aggregated cost summary |
| `/costs/trend` | GET | Historical cost trend |
| `/costs/by-service` | GET | Breakdown by cloud service |
| `/accounts/` | POST | Register cloud account |
| `/accounts/{id}/sync` | POST | Trigger cost sync |

### ML Service (`/api/v1/ml`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/predict` | POST | Generate cost forecast |
| `/detect` | POST | Run anomaly detection |
| `/train` | POST | Initialize models with data |
| `/status` | GET | Model health check |

---

## Development

```bash
# Root env used by docker-compose
cp .env.example .env

# Backend (cost-service)
cd services/cost-service
pip install -e ".[dev]"
pytest -v --cov=app

# Backend (ml-service)
cd services/ml-service
pip install -e ".[dev]"
pytest -v --cov=app

# Install the Chronos/Torch inference stack only when you need real model inference
pip install -e ".[inference]"

# Frontend
cd frontend
npm install
npm run dev
```

### Verification

```bash
# Frontend
cd frontend
npm run lint
npm run test
npm run build

# Cost service
cd services/cost-service
pytest -q

# ML service
cd services/ml-service
pytest -q
```

### Deployment

- Deployment guide: [docs/deployment.md](docs/deployment.md)
- Cost-service schema changes are managed through Alembic in `services/cost-service/alembic/versions`.
- Prometheus alert rules live in `monitoring/prometheus/alerts.yml`.

### Environment Notes

- Root `.env.example` is the easiest starting point for local Docker usage.
- Cost-service-specific defaults also live in `services/cost-service/.env.example`.
- Real provider sync is disabled by default. Set `ALLOW_LIVE_CLOUD_SYNC=true` and `CLOUD_SYNC_MODE=live` before calling real cloud billing APIs.
- Chat defaults to OpenRouter's free router (`openrouter/free`). Add your OpenRouter key to `LLM_API_KEY` to enable the analyst chat.
- The ML service keeps heavy Chronos/Torch dependencies behind the `inference` extra so tests and CI stay lightweight.

---

## Roadmap

- [x] AWS Cost Explorer integration
- [x] Amazon Chronos for forecasting
- [x] Anomaly detection with Isolation Forest
- [x] Natural language chat interface
- [ ] Azure Cost Management integration
- [ ] GCP Billing integration
- [ ] Kubernetes namespace cost attribution
- [ ] Slack/Teams alerting
- [ ] Terraform cost estimation (pre-deploy)

---

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Good first issues:**
- Add Azure provider adapter
- Add GCP provider adapter
- Improve anomaly detection sensitivity tuning
- Add more chart visualizations

---

## License

MIT License - see [LICENSE](LICENSE) for details.



<div align="center">

**If this helped you understand cloud costs better, consider giving it a star!**

</div>
