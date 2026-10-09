FROM python:3.11-slim

WORKDIR /workspace

# Install system dependencies for PostgreSQL and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r ./backend/requirements.txt

# Copy backend code, knowledge base and configs
COPY backend/ ./backend/
COPY knowledge/ ./knowledge/
COPY .env.example ./.env

ENV PYTHONPATH=/workspace
EXPOSE 8000

# Start script running alembic migrations, seeding demo cases, then running FastAPI
CMD ["sh", "-c", "python -m alembic -c backend/alembic.ini upgrade head && python backend/app/scripts/seed.py && uvicorn backend.app.main:app --host 0.0.0.0 --port 8000"]
