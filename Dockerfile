# Stage 1: Build stage
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime stage
FROM python:3.12-slim AS runner

# Create non-root system user and group
RUN groupadd -r cdnapp && useradd -r -g cdnapp -u 1001 cdnapp

WORKDIR /app

# Copy installed python packages from builder
COPY --from=builder /root/.local /home/cdnapp/.local
ENV PATH=/home/cdnapp/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Copy application source code
COPY . .

# Ensure app directory permissions
RUN chown -R cdnapp:cdnapp /app

USER cdnapp

EXPOSE 5000

# Healthcheck testing network API endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/network').read()" || exit 1

CMD ["python", "dashboard/app.py"]
