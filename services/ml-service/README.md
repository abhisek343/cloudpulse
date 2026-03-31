# ML Service

FastAPI microservice for CloudPulse forecasting and anomaly detection.

## What It Does

- Forecasts cloud spend with Amazon Chronos when the optional inference stack is installed
- Detects unusual spend patterns with Isolation Forest
- Verifies JWTs issued by the cost-service before serving ML endpoints

## Local Development

```bash
pip install -e ".[dev]"
pytest -q
```

Install the heavier inference dependencies only when you need live Chronos inference:

```bash
pip install -e ".[inference]"
```

## API Surface

- `POST /api/v1/ml/train`
- `POST /api/v1/ml/predict`
- `POST /api/v1/ml/detect`
- `GET /api/v1/ml/status`

The service is intentionally lightweight in CI and local tests; the default test path validates request/response behavior without downloading Chronos weights.
