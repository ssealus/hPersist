FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    HPERSIST_DATA_DIR=/data \
    HPERSIST_SERVER__HOST=0.0.0.0 \
    HPERSIST_SERVER__PORT=8765

RUN apt-get update \
 && apt-get install -y --no-install-recommends tini curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app           ./app
COPY frontend      ./frontend
COPY migrations    ./migrations
COPY alembic.ini   ./alembic.ini
COPY start.sh      ./start.sh
RUN chmod +x ./start.sh

RUN groupadd --system --gid 10001 hpersist \
 && useradd  --system --uid 10001 --gid hpersist --home-dir /app --shell /usr/sbin/nologin hpersist \
 && mkdir -p /data /data/logs /data/archives /data/uploads \
 && chown -R hpersist:hpersist /app /data

USER hpersist

VOLUME ["/data"]
EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=4s --start-period=15s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8765/api/v1/health || exit 1

ENTRYPOINT ["/usr/bin/tini", "--", "./start.sh"]
