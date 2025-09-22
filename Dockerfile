# ---------- base ----------
FROM python:3.12-slim

# ---------- runtime opts ----------
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# ---------- workdir ----------
WORKDIR /app

# ---------- install deps ----------
COPY requirements.txt .
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq-dev gcc build-essential && \
    pip install --no-cache-dir -r requirements.txt && \
    apt-get purge -y --auto-remove libpq-dev gcc build-essential && \
    rm -rf /var/lib/apt/lists*

COPY . .

