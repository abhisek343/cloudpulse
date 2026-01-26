FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir -e .
RUN pip install "git+https://github.com/amazon-science/chronos-forecasting.git"

# Copy application code
COPY app/ ./app/

# Create models directory
RUN mkdir -p models

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Run with uvicorn
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}
