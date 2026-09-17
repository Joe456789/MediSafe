# Use an official lightweight Python runtime as a parent image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend and frontend source directories
# (No .env copy: secrets are injected at runtime via Cloud Run env vars,
# never baked into the image.)
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Cloud Run defaults to injecting the PORT environment variable (default 8080)
EXPOSE 8080

# Command to run uvicorn server, binding dynamically to the Cloud Run PORT variable
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
