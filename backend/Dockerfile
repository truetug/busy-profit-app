FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend \
    SHOPIFY_STATS_HISTORY_PATH=/data/history.csv \
    SHOPIFY_STATS_PUBLISH_PATH=/data/public/history.csv

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir --disable-pip-version-check \
    -r /app/backend/requirements.txt

COPY backend/busy_shopify_stats /app/backend/busy_shopify_stats

RUN mkdir -p /data/public && chown -R 1001:1003 /data
USER 1001:1003

CMD ["python", "-m", "busy_shopify_stats.collector"]
