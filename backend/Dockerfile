# syntax=docker/dockerfile:1.7

FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

RUN apt-get update && \
    apt-get install --yes --no-install-recommends \
        libgl1 \
        libglib2.0-0t64 \
        libx11-6 \
        libxcb1 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.lock ./

RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --requirement requirements.lock

RUN useradd --create-home --uid 10001 racevault && \
    mkdir -p /home/racevault/.cache/huggingface && \
    chown -R racevault:racevault /home/racevault

COPY pyproject.toml alembic.ini ./
COPY migrations ./migrations
COPY src ./src

ARG RACEVAULT_INSTALL_OBSERVABILITY=false
RUN if [ "$RACEVAULT_INSTALL_OBSERVABILITY" = "true" ]; then \
        python -m pip install --no-cache-dir \
          opentelemetry-api==1.44.0 \
          opentelemetry-exporter-otlp-proto-http==1.44.0 \
          opentelemetry-sdk==1.44.0; \
    fi && \
    python -m pip install --no-deps . && python -m pip check

USER racevault

EXPOSE 8000

CMD ["uvicorn", "racevault.main:app", "--host", "0.0.0.0", "--port", "8000"]
