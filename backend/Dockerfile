FROM python:3.10-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt || true
RUN pip install --no-cache-dir fastapi uvicorn pydantic pydantic-settings sqlalchemy aiosqlite python-multipart python-dotenv httpx pytest pytest-asyncio

# Copy application
COPY . .

# Create data directories
RUN mkdir -p /app/data/chroma_db

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
