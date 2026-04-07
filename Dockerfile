# Build from the environment root (directory that contains pyproject.toml and server/):
#   docker build -f server/Dockerfile -t sql-debug-env .
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md openenv.yaml inference.py uv.lock ./
COPY __init__.py models.py client.py ./
COPY server ./server/

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "sql_debug_env.server.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
