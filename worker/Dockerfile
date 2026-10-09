FROM python:3.11-slim

WORKDIR /workspace

# Install system dependencies for PostgreSQL and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements (worker shares codebase)
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r ./backend/requirements.txt

# Copy backend, worker, and knowledge files
COPY backend/ ./backend/
COPY worker/ ./worker/
COPY knowledge/ ./knowledge/
COPY .env.example ./.env

ENV PYTHONPATH=/workspace

CMD ["python", "worker/worker.py"]
