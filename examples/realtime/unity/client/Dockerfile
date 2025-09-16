# syntax=docker/dockerfile:1
FROM python:3.13.7-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src

RUN pip install --upgrade pip \
    && pip install --no-cache-dir \
        ".[realtime]" \
        "fastapi>=0.115,<1" \
        "uvicorn>=0.30,<1"

COPY examples/realtime/unity ./examples/realtime/unity

WORKDIR /app/examples/realtime/unity

EXPOSE 8000

CMD ["python", "server.py"]
