FROM python:3.11-slim

WORKDIR /app/env

RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
COPY . .

RUN uv pip install --system --no-cache openenv-core && \
    uv pip install --system --no-cache -e .

ENV PYTHONPATH="/app/env:$PYTHONPATH"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
