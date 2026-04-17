FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN pip install --upgrade pip uv

COPY pyproject.toml ./
RUN uv pip install --system --no-cache -r pyproject.toml

COPY app ./app
COPY alembic.ini ./
COPY alembic/ ./alembic/

EXPOSE 4318

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "4318"]
