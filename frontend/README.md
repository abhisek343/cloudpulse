# CloudPulse Frontend

Next.js dashboard for CloudPulse AI.

## Local Development

```bash
npm install
npm run dev
```

Use `http://localhost:3000` for local `next dev`, or `http://localhost:3005` when the app is started through the root `docker-compose.yml`.

## Required Environment

The frontend reads only public runtime settings:

```env
NEXT_PUBLIC_COST_SERVICE_URL=http://localhost:8001
NEXT_PUBLIC_ML_SERVICE_URL=http://localhost:8002
NEXT_PUBLIC_DEFAULT_ACCOUNT_PROVIDER=demo
NEXT_PUBLIC_DEFAULT_DEMO_SCENARIO=saas
```

## Quality Checks

```bash
npm run lint
npm run typecheck
npm run test
```

## Notes

- Authentication is handled against the cost-service JWT endpoints.
- The dashboard is demo-first: seed the backend demo tenant before expecting charts or forecasts.
- The chat panel analyzes cost data already stored in CloudPulse rather than calling provider APIs directly from the browser.
