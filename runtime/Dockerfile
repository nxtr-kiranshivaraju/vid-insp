FROM python:3.12-slim

# OpenCV runtime libs (headless variant minimises footprint).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install the shared package first (path dep), then runtime.
COPY shared /app/shared
RUN pip install --no-cache-dir /app/shared

COPY runtime /app/runtime
RUN pip install --no-cache-dir /app/runtime

ENV API_HOST=0.0.0.0 \
    API_PORT=8080

EXPOSE 8080

ENTRYPOINT ["vlm-runtime"]
CMD ["run", "--dsl", "/app/dsl/active.yaml"]
