FROM node:20-alpine AS builder

WORKDIR /app

ARG NEXT_PUBLIC_COST_SERVICE_URL=http://localhost:8001
ARG NEXT_PUBLIC_ML_SERVICE_URL=http://localhost:8002
ARG NEXT_PUBLIC_DEFAULT_ACCOUNT_PROVIDER=demo
ARG NEXT_PUBLIC_DEFAULT_DEMO_SCENARIO=saas

ENV NEXT_PUBLIC_COST_SERVICE_URL=${NEXT_PUBLIC_COST_SERVICE_URL}
ENV NEXT_PUBLIC_ML_SERVICE_URL=${NEXT_PUBLIC_ML_SERVICE_URL}
ENV NEXT_PUBLIC_DEFAULT_ACCOUNT_PROVIDER=${NEXT_PUBLIC_DEFAULT_ACCOUNT_PROVIDER}
ENV NEXT_PUBLIC_DEFAULT_DEMO_SCENARIO=${NEXT_PUBLIC_DEFAULT_DEMO_SCENARIO}

# Install dependencies
COPY package*.json ./
RUN npm ci

# Copy source
COPY . .

# Build
RUN npm run build

# Production image
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

# Create non-root user
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy built assets
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
