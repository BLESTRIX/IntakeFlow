FROM python:3.12.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.10 /uv /uvx /bin/
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
RUN useradd --create-home intakeflow && chown -R intakeflow:intakeflow /app
USER intakeflow
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
