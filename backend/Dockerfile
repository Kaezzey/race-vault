FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml alembic.ini ./
COPY migrations ./migrations
COPY src ./src

RUN python -m pip install ".[semantic,extraction]"

RUN useradd --create-home --uid 10001 racevault && \
    mkdir -p /home/racevault/.cache/huggingface && \
    chown -R racevault:racevault /app /home/racevault

USER racevault

EXPOSE 8000

CMD ["uvicorn", "racevault.main:app", "--host", "0.0.0.0", "--port", "8000"]
