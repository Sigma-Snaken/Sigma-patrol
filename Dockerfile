FROM python:3.10-slim
LABEL org.opencontainers.image.source=https://github.com/sigma-snaken/sigma-patrol
# Prevent Python from writing pyc files to disc
ENV PYTHONDONTWRITEBYTECODE=1
# Prevent Python from buffering stdout and stderr
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies if needed (e.g. for some python packages)
# RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY src/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the source code
COPY src /app/src

# Set locale
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# Set working directory to backend where app.py resides
WORKDIR /app/src/backend

# Expose the Flask port
EXPOSE 5000

# Command to run the application
CMD ["python", "app.py"]