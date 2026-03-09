# Build frontend
FROM node:20-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Python runtime
FROM python:3.13-slim AS runtime
WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY pyproject.toml ./
RUN pip install --no-cache-dir ".[api]"

# Copy application
COPY taa/ ./taa/

# Copy built frontend
COPY --from=frontend /app/frontend/dist ./frontend/dist

# Create non-root user
RUN useradd -m -r taa && chown -R taa:taa /app
USER taa

EXPOSE 8000

CMD ["uvicorn", "taa.presentation.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
