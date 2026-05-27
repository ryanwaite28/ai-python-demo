#!/usr/bin/env bash
# Local migration smoke test — ephemeral containers only, nothing persisted.
# Usage: ./scripts/test-migration-local.sh
# Optional env overrides:
#   DB_NAME, DB_USER, DB_PASS   — default to values below
#   SKIP_BUILD                  — set to 1 to reuse an existing local image build

set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
DB_NAME="${DB_NAME:-blog_db}"
DB_USER="${DB_USER:-blog_user}"
DB_PASS="${DB_PASS:-localtest}"

NETWORK_NAME="migration-test-net"
DB_CONTAINER="migration-test-postgres"
APP_IMAGE="ai-python-demo:migration-test"
MIGRATE_CONTAINER="migration-test-runner"

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RESET='\033[0m'
info()    { echo -e "${GREEN}[migration-test]${RESET} $*"; }
warn()    { echo -e "${YELLOW}[migration-test]${RESET} $*"; }
fail()    { echo -e "${RED}[migration-test] FAILED:${RESET} $*" >&2; exit 1; }

# ── Cleanup (runs on EXIT for any reason) ─────────────────────────────────────
cleanup() {
    info "Cleaning up..."
    docker rm -f "$MIGRATE_CONTAINER" 2>/dev/null || true
    docker rm -f "$DB_CONTAINER"      2>/dev/null || true
    docker network rm "$NETWORK_NAME" 2>/dev/null || true
    if [[ "${SKIP_BUILD:-0}" != "1" ]]; then
        docker rmi "$APP_IMAGE" 2>/dev/null || true
    fi
    info "Cleanup complete."
}
trap cleanup EXIT

# ── Step 1: Isolated network ──────────────────────────────────────────────────
info "Creating isolated Docker network: $NETWORK_NAME"
docker network create "$NETWORK_NAME"

# ── Step 2: Ephemeral Postgres ────────────────────────────────────────────────
# POSTGRES_USER=$DB_USER makes blog_user the superuser for this ephemeral
# container — avoids a separate CREATE USER step and the auth issues that come
# with it (scram-sha-256 timing, pg_hba ordering, etc.).
info "Starting ephemeral Postgres container: $DB_CONTAINER"
docker run -d \
    --name "$DB_CONTAINER" \
    --network "$NETWORK_NAME" \
    -e POSTGRES_DB="$DB_NAME" \
    -e POSTGRES_USER="$DB_USER" \
    -e POSTGRES_PASSWORD="$DB_PASS" \
    --tmpfs /var/lib/postgresql/data \
    postgres:15-alpine

# ── Step 3: Wait for Postgres to be ready ─────────────────────────────────────
info "Waiting for Postgres to accept connections..."
RETRIES=30
until docker exec "$DB_CONTAINER" \
        pg_isready -U "$DB_USER" -d "$DB_NAME" -q 2>/dev/null; do
    RETRIES=$((RETRIES - 1))
    [[ $RETRIES -le 0 ]] && fail "Postgres did not become ready in time."
    sleep 1
done
info "Postgres is ready."

# ── Step 4: Replicate postgres-init-configmap.yaml setup ─────────────────────
info "Initialising database schema (replicating cluster init.sql)..."
docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" \
    -c "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";" \
    -c "SET timezone = 'UTC';" \
    -c "CREATE SCHEMA IF NOT EXISTS blog;" \
    -c "ALTER DATABASE ${DB_NAME} SET search_path TO blog, public;"
info "Schema initialised."

# ── Step 5: Build the app image ───────────────────────────────────────────────
if [[ "${SKIP_BUILD:-0}" == "1" ]]; then
    warn "SKIP_BUILD=1 — reusing existing image: $APP_IMAGE"
    docker image inspect "$APP_IMAGE" > /dev/null 2>&1 \
        || fail "SKIP_BUILD=1 but image '$APP_IMAGE' not found locally. Run without SKIP_BUILD first."
else
    info "Building app image (tests skipped — migration test only)..."
    docker build \
        --build-arg SKIP_TESTS=true \
        -t "$APP_IMAGE" \
        "$(dirname "$0")/.."
    info "Image built: $APP_IMAGE"
fi

# ── Step 6: Run flask db upgrade ──────────────────────────────────────────────
DATABASE_URL="postgresql://${DB_USER}:${DB_PASS}@${DB_CONTAINER}:5432/${DB_NAME}"

info "Running 'flask db upgrade' against ephemeral Postgres..."
docker run --rm \
    --name "$MIGRATE_CONTAINER" \
    --network "$NETWORK_NAME" \
    -e DATABASE_URL="$DATABASE_URL" \
    -e SECRET_KEY="local-test-secret" \
    -e FLASK_APP="app.py" \
    -e FLASK_ENV="production" \
    "$APP_IMAGE" \
    flask db upgrade

# ── Step 7: Verify alembic_version table exists and is populated ──────────────
info "Verifying migration state..."
REVISION=$(docker exec "$DB_CONTAINER" \
    psql -U "$DB_USER" -d "$DB_NAME" -At \
    -c "SELECT version_num FROM blog.alembic_version LIMIT 1;")

[[ -z "$REVISION" ]] && fail "alembic_version is empty — migration may not have applied."
info "Migration verified. Current revision: $REVISION"

# ── Step 8: Spot-check tables ─────────────────────────────────────────────────
info "Checking tables exist in blog schema..."
TABLES=$(docker exec "$DB_CONTAINER" \
    psql -U "$DB_USER" -d "$DB_NAME" -At \
    -c "SELECT tablename FROM pg_tables WHERE schemaname = 'blog' ORDER BY tablename;")

if [[ -z "$TABLES" ]]; then
    fail "No tables found in blog schema after migration."
fi

echo ""
echo "  Tables in blog schema:"
echo "$TABLES" | while read -r t; do echo "    - $t"; done
echo ""

info "Migration smoke test PASSED."
