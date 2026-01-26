# CloudPulse AI

<div align="center">

![CloudPulse AI](https://img.shields.io/badge/CloudPulse-AI-blue?style=for-the-badge&logo=cloud)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python)](https://www.python.org/)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-black?style=for-the-badge&logo=next.js)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)

### Predict cloud costs before they satisfyyou. Ask questions in plain English.

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
- Privacy-first: billing data is summarized locally before LLM calls

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
    
         [Frontend]              [Monitoring]           [Metrics]
          Next.js                 Prometheus             Grafana
           :3000                    :9090                 :3001
              |                       |                     |
    ----------|=======================|=====================|------
              |                       |                     |
              v                       v                     v
    ================================================================
                              API Gateway
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

### One Command Setup

```bash
# Clone and start
git clone https://github.com/abhisek343/cloudpulse.git
cd cloudpulse
docker-compose up -d

# Generate demo data (no AWS account needed!)
docker-compose exec cost-service python scripts/seed_data.py
```

### Access Points

| Service | URL | Notes |
|---------|-----|-------|
| **Dashboard** | http://localhost:3005 | Main UI |
| **Cost API** | http://localhost:8001/docs | Swagger docs |
| **ML API** | http://localhost:8002/docs | Swagger docs |
| **Grafana** | http://localhost:3001 | admin / cloudpulse |
| **Prometheus** | http://localhost:9090 | Metrics |

---

## Tech Stack

| Layer | Technology | Why |
|-------|------------|-----|
| **ML/AI** | Amazon Chronos (T5), scikit-learn | Foundation model for zero-shot forecasting |
| **Backend** | FastAPI, SQLAlchemy 2.0, Pydantic | Async-first, type-safe Python |
| **Frontend** | Next.js 14, TypeScript, Tailwind | Modern React with App Router |
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
| `/costs/by-service` | GET | Breakdown by AWS service |
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
# Backend (cost-service)
cd services/cost-service
pip install -e ".[dev]"
pytest -v --cov=app

# Backend (ml-service)
cd services/ml-service
pip install -e ".[dev]"
pytest -v --cov=app

# Frontend
cd frontend
npm install
npm run dev
```

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

---

## Author

**Abhisek Behera**

[![GitHub](https://img.shields.io/badge/GitHub-@abhisek343-black?style=flat-square&logo=github)](https://github.com/abhisek343)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-abhiske343-blue?style=flat-square&logo=linkedin)](https://www.linkedin.com/in/abhiske343/)

---

<div align="center">

**If this helped you understand cloud costs better, consider giving it a star!**

</div>
