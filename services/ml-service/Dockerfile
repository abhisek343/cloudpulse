FROM python:3.11-slim

WORKDIR /app

ENV PIP_DEFAULT_TIMEOUT=120 PIP_RETRIES=5

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml README.md ./
COPY app/ ./app/
ARG INSTALL_INFERENCE=false
RUN python -m pip install --no-cache-dir --disable-pip-version-check 'hatchling>=1.25,<2' \
    && if [ "$INSTALL_INFERENCE" = "true" ]; then \
      apt-get update && apt-get install -y --no-install-recommends git && \
      python -m pip install --no-cache-dir --disable-pip-version-check --no-build-isolation --extra-index-url https://download.pytorch.org/whl/cpu '.[inference]' && \
      rm -rf /var/lib/apt/lists/*; \
    else \
      python -m pip install --no-cache-dir --disable-pip-version-check --no-build-isolation .; \
    fi

# Copy application code
# Create models directory
RUN mkdir -p models

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Run with uvicorn
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
