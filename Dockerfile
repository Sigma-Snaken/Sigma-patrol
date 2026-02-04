FROM python:3.10-slim
LABEL org.opencontainers.image.source=https://github.com/sigma-snaken/visual-patrol
# Prevent Python from writing pyc files to disc
ENV PYTHONDONTWRITEBYTECODE=1
# Prevent Python from buffering stdout and stderr
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies if needed (e.g. for some python packages)
# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    python3-dev \
    cmake \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy requirements first for better caching
COPY src/backend/requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

# Copy the source code
COPY src /app/src

# Download Chart.js for frontend (After COPY to avoid overwrite)
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /app/src/frontend/static/js && \
    curl -L https://cdn.jsdelivr.net/npm/chart.js -o /app/src/frontend/static/js/chart.min.js && \
    curl -L https://cdn.jsdelivr.net/npm/marked/marked.min.js -o /app/src/frontend/static/js/marked.min.js

# Set locale
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# Set working directory to backend where app.py resides
WORKDIR /app/src/backend

# Create non-root user (UID 1000 to match typical host user for volume mounts)
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g 1000 -r -s /bin/false appuser && \
    mkdir -p /app/data /app/logs && \
    chown -R appuser:appuser /app/data /app/logs
USER appuser

# Expose the Flask port
EXPOSE 5000

# Command to run the application
CMD ["python", "app.py"]