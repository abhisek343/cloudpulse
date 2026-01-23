# CloudPulse AI

> **AI-Powered Cloud Cost Prediction & Optimization Platform**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org/)

## 🎯 What is CloudPulse AI?

CloudPulse AI is a **predictive FinOps platform** that goes beyond traditional cost monitoring. Instead of just showing you what you've already spent, it **predicts future costs, detects anomalies in real-time, and automatically suggests optimizations**.

### Key Features

- 🔮 **AI Cost Prediction** - Forecast next 30/60/90 days using ML models
- 💻 **PR Cost Analyzer** - Estimate cost impact before merging code
- 🔍 **Anomaly Detection** - Real-time ML-based spike detection
- 👥 **Team Attribution** - Link costs to developers and projects
- 🤖 **Auto-Remediation** - Automated optimization suggestions
- 📊 **Real-time Dashboard** - WebSocket-powered live updates

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      CloudPulse AI                          │
├─────────────────────────────────────────────────────────────┤
│  Frontend (Next.js)  │  API Gateway  │  Monitoring          │
├──────────────────────┼───────────────┼──────────────────────┤
│  Cost Service   │  AI/ML Service   │  Alert Service        │
├──────────────────────┴───────────────┴──────────────────────┤
│  PostgreSQL  │  Redis  │  RabbitMQ  │  TimescaleDB          │
└─────────────────────────────────────────────────────────────┘
```

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 14, TypeScript, Tailwind CSS |
| Backend | FastAPI (Python), Microservices |
| Database | PostgreSQL, TimescaleDB, Redis |
| Message Queue | RabbitMQ |
| AI/ML | scikit-learn, Prophet |
| Cloud | AWS (Cost Explorer, Lambda) |
| DevOps | Docker, GitHub Actions |
| Monitoring | Prometheus, Grafana |

## 🚀 Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/cloudpulse-ai.git
cd cloudpulse-ai

# Start with Docker Compose
docker-compose up -d

# Access the dashboard
open http://localhost:3000
```

## 📁 Project Structure

```
cloudpulse-ai/
├── services/
│   ├── cost-service/       # Cost data ingestion & processing
│   ├── ml-service/         # AI predictions & anomaly detection
│   └── alert-service/      # Notifications & webhooks
├── frontend/               # Next.js dashboard
├── docker/                 # Docker configurations
├── .github/workflows/      # CI/CD pipelines
└── docs/                   # Documentation
```

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

Built with ❤️ by [Abhisek Behera](https://github.com/abhiske343)
