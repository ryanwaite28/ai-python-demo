# syntax=docker/dockerfile:1

# ── Build stage: install deps and run tests ──────────────────────────────────
FROM python:3.11-slim AS build

ARG SKIP_TESTS=false

WORKDIR /app

RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN if [ "$SKIP_TESTS" = "true" ]; then \
      echo "WARNING: tests skipped (SKIP_TESTS=true)"; \
    else \
      pytest tests/ -q; \
    fi

# ── Runtime stage: lean final image ──────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /app /app
COPY --from=build /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=build /usr/local/bin /usr/local/bin

ENV PORT=8080
EXPOSE ${PORT}

CMD gunicorn -w 4 -b 0.0.0.0:${PORT} "app:create_app()"
