FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    fonts-dejavu \
    build-essential \
    g++ \
    pkg-config \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libavfilter-dev \
    libswscale-dev \
    libswresample-dev \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install numpy and Cython first
RUN pip install --no-cache-dir "numpy>=1.26.0" Cython

# Install pkuseg separately with no-build-isolation
RUN pip install --no-cache-dir --no-build-isolation pkuseg

# Copy and install remaining dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY video /app/video
COPY server.py /app/server.py
COPY assets /app/assets

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["fastapi", "run", "server.py", "--host", "0.0.0.0", "--port", "8000"]