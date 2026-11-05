# Multi-stage production Dockerfile for Smart Invoice & Receipt Scanner
FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Install essential system dependencies for Docling, Poppler, and OCR engines
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libgl1 \
    libglib2.0-0 \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-fas \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency manifests first to leverage Docker layer caching
COPY requirements.txt pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy source code and configuration
COPY . .

# Ensure storage directories exist
RUN mkdir -p /app/storage/consume \
             /app/storage/archive \
             /app/storage/error \
             /app/storage/output \
             /app/storage/logs \
             /app/storage/.cache/docling

EXPOSE 8000

# Default command runs both FastAPI and Folder Watcher concurrently
CMD ["python", "main.py", "run-all", "--host", "0.0.0.0", "--port", "8000"]
