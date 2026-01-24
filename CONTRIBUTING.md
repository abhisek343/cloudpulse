# Contributing to CloudPulse AI

First off, thanks for taking the time to contribute!

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Pull Request Process](#pull-request-process)
- [Style Guidelines](#style-guidelines)

---

## Code of Conduct

This project follows the [Contributor Covenant](https://www.contributor-covenant.org/). By participating, you are expected to uphold this code. Please report unacceptable behavior to the maintainers.

---

## Getting Started

### Good First Issues

Looking for something to work on? Check out issues labeled:
- `good first issue` - Great for newcomers
- `help wanted` - We'd love community help here
- `documentation` - Improve docs and examples

### Project Areas

| Area | Description | Skills Needed |
|------|-------------|---------------|
| **Cost Service** | AWS/Azure/GCP integrations | Python, Cloud APIs |
| **ML Service** | Forecasting & anomaly detection | Python, ML/AI |
| **Frontend** | Dashboard and visualizations | React, TypeScript |
| **DevOps** | Docker, CI/CD, monitoring | Docker, GitHub Actions |

---

## Development Setup

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose

### Local Development

```bash
# Clone the repo
git clone https://github.com/abhisek343/cloudpulse.git
cd cloudpulse

# Start infrastructure (DB, Redis, RabbitMQ)
docker-compose up -d db redis rabbitmq

# Backend: Cost Service
cd services/cost-service
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -e ".[dev]"
pytest  # Run tests

# Backend: ML Service
cd ../ml-service
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
pytest

# Frontend
cd ../../frontend
npm install
npm run dev
```

### Running Everything

```bash
# Full stack with Docker
docker-compose up -d

# Generate demo data
docker-compose exec cost-service python scripts/seed_data.py
```

---

## How to Contribute

### Reporting Bugs

Before creating a bug report, please check existing issues. When filing a bug:

1. Use the bug report template
2. Include steps to reproduce
3. Include expected vs actual behavior
4. Add logs/screenshots if relevant

### Suggesting Features

1. Check if the feature is already on the [Roadmap](README.md#roadmap)
2. Open an issue using the feature request template
3. Describe the use case, not just the solution

### Code Contributions

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Write/update tests
5. Run linting and tests
6. Commit with conventional commits
7. Push and open a Pull Request

---

## Pull Request Process

### Before Submitting

- [ ] Tests pass locally (`pytest`)
- [ ] Linting passes (`ruff check .`)
- [ ] Type checking passes (`mypy app/`)
- [ ] New code has tests
- [ ] Documentation updated if needed

### PR Title Format

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add Azure cost provider
fix: handle empty cost data gracefully
docs: update API documentation
refactor: simplify provider factory pattern
test: add integration tests for sync service
```

### Review Process

1. Maintainer will review within 48 hours
2. Address any requested changes
3. Once approved, maintainer will merge
4. Your contribution will be in the next release!

---

## Style Guidelines

### Python

- Follow PEP 8 (enforced by Ruff)
- Use type hints for all function signatures
- Docstrings for public functions (Google style)
- Max line length: 100 characters

```python
async def sync_account_costs(
    self,
    cloud_account: CloudAccount,
    days: int = 30,
) -> dict[str, Any]:
    """
    Sync cost data from cloud provider.
    
    Args:
        cloud_account: The cloud account to sync
        days: Number of days to sync (default: 30)
        
    Returns:
        Sync result with record counts
    """
```

### TypeScript/React

- Use functional components with hooks
- Prefer TypeScript strict mode
- Use Tailwind CSS for styling
- Component files: PascalCase (`CostChart.tsx`)

### Commits

- Use present tense ("add feature" not "added feature")
- Use imperative mood ("move cursor" not "moves cursor")
- Keep first line under 72 characters
- Reference issues when relevant (`fixes #123`)

---

## Adding a New Cloud Provider

One of the most impactful contributions! Here's how:

1. Create provider adapter in `services/cost-service/app/services/providers/`
2. Implement the `BaseCostProvider` interface
3. Register in `ProviderFactory`
4. Add tests
5. Update documentation

```python
# services/cost-service/app/services/providers/azure.py
from .base import BaseCostProvider

class AzureCostProvider(BaseCostProvider):
    """Azure Cost Management provider."""
    
    async def get_cost_data(
        self,
        start_date: datetime,
        end_date: datetime,
        granularity: str = "DAILY",
    ) -> list[dict[str, Any]]:
        # Implementation here
        pass
```

---

## Questions?

- Open a [Discussion](https://github.com/abhisek343/cloudpulse/discussions)
- Tag maintainers in issues

Thank you for contributing!
