FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system deps for psycopg2.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install the shared package first, then the compiler. This lets the
# compiler depend on the shared package without publishing it.
COPY shared/ /app/shared/
RUN pip install /app/shared

COPY compiler/ /app/compiler/
RUN pip install /app/compiler

EXPOSE 8001

# Apply migrations on start, then run the API.
CMD ["sh", "-c", "python -m compiler.db.migrate && uvicorn compiler.main:app --host 0.0.0.0 --port 8001"]
