FROM python:3.13-slim AS landing

WORKDIR /build
RUN pip install --no-cache-dir --disable-pip-version-check 'markdown-it-py>=3,<5'
COPY README.md /build/README.md
COPY screenshots /build/screenshots
COPY website /build/website
RUN python /build/website/build.py

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend/src \
    SHOPIFY_STATS_HISTORY_PATH=/data/history.csv \
    SHOPIFY_STATS_PUBLISH_PATH=/data/public/history.csv

WORKDIR /app

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --disable-pip-version-check \
    -r /app/requirements.txt

COPY backend/src/busy_profit /app/backend/src/busy_profit
COPY --from=landing /build/website/dist /app/landing

RUN mkdir -p /data/public && chown -R 1001:1003 /data
USER 1001:1003

CMD ["python", "-m", "busy_profit"]
