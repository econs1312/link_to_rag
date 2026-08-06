# ==============================================================================
# Stage 1: Builder — compile Python dependencies
# ==============================================================================
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ==============================================================================
# Stage 2: Runtime — lean production image
# ==============================================================================
FROM python:3.11-slim

WORKDIR /app

# Install only runtime system dependencies (no build-essential)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    tesseract-ocr \
    tesseract-ocr-por \
    tesseract-ocr-eng \
    poppler-utils \
    libmagic1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy pre-built Python packages from builder stage
COPY --from=builder /install /usr/local

COPY . .

# Ensure start.sh is executable
RUN chmod +x start.sh

EXPOSE 8000

CMD ["./start.sh"]
