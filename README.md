# CloudPulse AI

<div align="center">

![CloudPulse AI](https://img.shields.io/badge/CloudPulse-AI-blue?style=for-the-badge&logo=cloud)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python)](https://www.python.org/)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-black?style=for-the-badge&logo=next.js)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)

**AI-Powered Cloud Cost Prediction & Optimization Platform**

*Predict cloud costs before they happen. Detect anomalies automatically. Optimize spending with AI.*

[Features](#-features) • [Architecture](#-architecture) • [Quick Start](#-quick-start) • [API Docs](#-api-documentation) • [Tech Stack](#-tech-stack)

</div>

---

## 🎯 What is CloudPulse AI?

CloudPulse AI is a **predictive FinOps platform** that goes beyond traditional cost monitoring. Instead of just showing you what you've already spent, it:

- 🔮 **Predicts future costs** using ML time-series forecasting
- 🔍 **Detects anomalies** in real-time with Isolation Forest
- 📊 **Visualizes trends** with interactive dashboards
- 💡 **Suggests optimizations** to reduce cloud spending

### Why CloudPulse AI?

| Traditional FinOps Tools | CloudPulse AI |
|--------------------------|---------------|
| Shows past costs ❌ | Predicts future costs ✅ |
| Manual anomaly review ❌ | AI-powered detection ✅ |
| Basic dashboards ❌ | Real-time visualizations ✅ |
| Reactive approach ❌ | Proactive optimization ✅ |

---

## ✨ Features

### 📈 Cost Prediction
- **30/60/90 day forecasts** using Facebook Prophet
- **95% confidence intervals** for budget planning
- **Seasonality detection** (weekly, monthly, yearly patterns)
- **Trend analysis** and growth projections

### 🚨 Anomaly Detection
- **Real-time monitoring** with Isolation Forest algorithm
- **Severity classification** (low, medium, high, critical)
- **Root cause analysis** suggestions
- **Configurable sensitivity** levels

### 📊 Interactive Dashboard
- **Modern dark theme** with glassmorphism design
- **Real-time charts** (cost trends, service breakdown, regions)
- **KPI cards** with trend indicators
- **Responsive design** for all devices

### 🔧 Cloud Integration
- **AWS Cost Explorer** integration
- Multi-account support
- Tag-based cost allocation
- Scheduled data sync

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CloudPulse AI                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐       │
│   │  Frontend   │     │  Prometheus │     │   Grafana   │       │
│   │  (Next.js)  │     │  Monitoring │     │  Dashboards │       │
│   │   :3000     │     │    :9090    │     │    :3001    │       │
│   └──────┬──────┘     └─────────────┘     └─────────────┘       │
│          │                                                       │
│   ───────┴───────────────────────────────────────────────────   │
│                           API Gateway                            │
│   ───────────────────────────────────────────────────────────   │
│          │                    │                                  │
│   ┌──────┴──────┐      ┌──────┴──────┐                          │
│   │ Cost Service│      │ ML Service  │                          │
│   │  (FastAPI)  │      │  (FastAPI)  │                          │
│   │   :8001     │      │   :8002     │                          │
│   └──────┬──────┘      └──────┬──────┘                          │
│          │                    │                                  │
│   ───────┴────────────────────┴─────────────────────────────    │
│                                                                  │
│   ┌────────┐  ┌───────┐  ┌──────────┐  ┌───────────────┐        │
│   │Postgres│  │ Redis │  │ RabbitMQ │  │ AWS Cost      │        │
│   │  :5432 │  │ :6379 │  │  :5672   │  │ Explorer API  │        │
│   └────────┘  └───────┘  └──────────┘  └───────────────┘        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Node.js 20+ (for local frontend dev)
- Python 3.11+ (for local backend dev)

### Using Docker Compose (Recommended)

```bash
# Clone the repository
git clone https://github.com/abhisek343/cloudpulse.git
cd cloudpulse

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f
```

### Access the Application

| Service | URL | Credentials |
|---------|-----|-------------|
| **Frontend** | http://localhost:3000 | - |
| **Cost Service API** | http://localhost:8001/docs | - |
| **ML Service API** | http://localhost:8002/docs | - |
| **Grafana** | http://localhost:3001 | admin / cloudpulse |
| **Prometheus** | http://localhost:9090 | - |
| **RabbitMQ** | http://localhost:15672 | guest / guest |

---

## 📖 API Documentation

### Cost Service API (`/api/v1`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/costs/summary` | GET | Get aggregated cost summary |
| `/costs/trend` | GET | Get cost trend data |
| `/costs/by-service` | GET | Get costs grouped by service |
| `/costs/by-region` | GET | Get costs grouped by region |
| `/accounts/` | GET | List cloud accounts |
| `/accounts/` | POST | Add cloud account |
| `/accounts/{id}/sync` | POST | Trigger cost sync |

### ML Service API (`/api/v1/ml`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/train` | POST | Train prediction models |
| `/predict` | POST | Get cost predictions |
| `/detect` | POST | Detect anomalies in data |
| `/detect/single` | POST | Check single record |
| `/status` | GET | Get model status |

---

## 🛠 Tech Stack

### Backend
- **FastAPI** - High-performance async Python framework
- **PostgreSQL** - Primary database
- **Redis** - Caching and session storage
- **RabbitMQ** - Message queue for async tasks
- **SQLAlchemy 2.0** - Async ORM

### Machine Learning
- **Facebook Prophet** - Time-series forecasting
- **scikit-learn** - Anomaly detection (Isolation Forest)
- **Pandas & NumPy** - Data processing

### Frontend
- **Next.js 14** - React framework with App Router
- **TypeScript** - Type-safe JavaScript
- **Tailwind CSS** - Utility-first styling
- **Recharts** - Interactive charts
- **React Query** - Data fetching

### DevOps
- **Docker & Docker Compose** - Containerization
- **GitHub Actions** - CI/CD pipeline
- **Prometheus** - Metrics collection
- **Grafana** - Visualization & alerting

---

## 📁 Project Structure

```
cloudpulse-ai/
├── services/
│   ├── cost-service/          # Cost data service
│   │   ├── app/
│   │   │   ├── api/           # FastAPI routes
│   │   │   ├── core/          # Config, DB, cache
│   │   │   ├── models/        # SQLAlchemy models
│   │   │   ├── schemas/       # Pydantic schemas
│   │   │   └── services/      # Business logic
│   │   └── tests/             # Pytest tests
│   │
│   └── ml-service/            # ML prediction service
│       ├── app/
│       │   ├── api/           # ML endpoints
│       │   ├── core/          # Configuration
│       │   ├── models/        # Schemas
│       │   └── services/      # Predictor & Detector
│       └── tests/             # ML tests
│
├── frontend/                  # Next.js dashboard
│   └── src/
│       ├── app/               # Pages (App Router)
│       ├── components/        # React components
│       └── lib/               # Utilities & API client
│
├── monitoring/
│   ├── prometheus/            # Prometheus config
│   └── grafana/               # Grafana dashboards
│
├── .github/workflows/         # CI/CD pipelines
├── docker-compose.yml         # Docker orchestration
└── README.md
```

---

## 🧪 Running Tests

```bash
# Cost Service Tests
cd services/cost-service
pip install -e ".[dev]"
pytest -v --cov=app

# ML Service Tests
cd services/ml-service
pip install -e ".[dev]"
pytest -v --cov=app
```

---

## 🔧 Configuration

Create a `.env` file in the root directory:

```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/cloudpulse

# Redis
REDIS_URL=redis://localhost:6379/0

# AWS (Optional)
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1

# JWT
JWT_SECRET_KEY=your-secret-key
```

---

## 📊 Dashboard Preview

The dashboard features:

- **Real-time KPI cards** showing total costs, predictions, and anomalies
- **Interactive trend charts** with historical and predicted data
- **Service breakdown** with cost allocation
- **Anomaly alerts** with severity indicators
- **Dark mode** with modern glassmorphism design

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'feat: add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 👨‍💻 Author

**Abhisek Behera**

- GitHub: [@abhisek343](https://github.com/abhisek343)
- LinkedIn: [abhiske343](https://www.linkedin.com/in/abhiske343/)

---

<div align="center">

**Built with ❤️ using FastAPI, Next.js, and AI/ML**

⭐ Star this repo if you found it helpful!

</div>
