#!/bin/bash
set -euo pipefail

echo "=========================================="
echo "Citatum FastAPI Container Startup"
echo "=========================================="

log()  { echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] $*"; }
warn() { echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] WARNING: $*" >&2; }
err()  { echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] ERROR: $*" >&2; }

# ----------------------------
# Database configuration
# ----------------------------
# Prefer discrete vars; fallback to parsing DATABASE_URL via Python.
# Required: DB_HOST, DB_PORT, DB_NAME. Optional: DB_USER, DB_PASS (auth dependent).
if [ -n "${DB_HOST:-}" ] && [ -n "${DB_PORT:-}" ] && [ -n "${DB_NAME:-}" ]; then
  log "Using discrete database environment variables"
else
  if [ -z "${DATABASE_URL:-}" ]; then
    err "Database connection not configured. Set either:"
    err "  - Discrete vars: DB_HOST, DB_PORT, DB_NAME (DB_USER/DB_PASS optional)"
    err "  - Or: DATABASE_URL"
    exit 1
  fi

  log "Parsing DATABASE_URL using Python (urllib.parse)..."

  PY_STDERR="$(mktemp)"
  chmod 600 "$PY_STDERR" || true
  trap 'rm -f "$PY_STDERR"' EXIT

  while IFS='=' read -r key value; do
    [ -z "${key:-}" ] && continue
    case "$key" in
      DB_HOST) DB_HOST="$value" ;;
      DB_PORT) DB_PORT="$value" ;;
      DB_USER) DB_USER="$value" ;;
      DB_PASS) DB_PASS="$value" ;;
      DB_NAME) DB_NAME="$value" ;;
      *) : ;; # ignore unexpected keys
    esac
  done < <(python3 - << 'PYEOF' 2>"$PY_STDERR"
import os, sys
from urllib.parse import urlparse, unquote

db_url = os.environ.get("DATABASE_URL", "")
if not db_url:
    sys.stderr.write("DATABASE_URL is empty\n")
    sys.exit(1)

# Normalize common SQLAlchemy/driver schemes to a scheme urlparse reliably handles.
normalized = db_url
normalized = normalized.replace("postgresql+asyncpg://", "postgresql://", 1)
normalized = normalized.replace("postgresql+psycopg2://", "postgresql://", 1)
normalized = normalized.replace("postgres://", "postgresql://", 1)

try:
    p = urlparse(normalized)

    if (p.scheme or "").lower() not in ("postgresql",):
        raise ValueError(f"Unsupported scheme '{p.scheme}'. Expected postgresql.")

    host = p.hostname or ""
    port = str(p.port) if p.port else "5432"
    user = unquote(p.username) if p.username else ""
    pwd  = unquote(p.password) if p.password else ""
    db   = unquote(p.path.lstrip("/")) if p.path else ""

    if not host:
        raise ValueError("Missing hostname in DATABASE_URL")
    if not db:
        raise ValueError("Missing database name in DATABASE_URL")

    # Hardening: forbid control characters that can break shell parsing/logs
    def no_ctl(name, s):
        if any(c in s for c in ("\r", "\n", "\t", "\x00")):
            raise ValueError(f"Invalid control character in {name}")
        return s

    host = no_ctl("hostname", host)
    port = no_ctl("port", port)
    user = no_ctl("username", user)
    pwd  = no_ctl("password", pwd)
    db   = no_ctl("database", db)

    print(f"DB_HOST={host}")
    print(f"DB_PORT={port}")
    print(f"DB_USER={user}")
    print(f"DB_PASS={pwd}")
    print(f"DB_NAME={db}")

except Exception as e:
    sys.stderr.write(f"Failed to parse DATABASE_URL: {e}\n")
    sys.exit(1)
PYEOF
  ) || {
    msg="$(cat "$PY_STDERR" || true)"
    err "Failed to parse DATABASE_URL: ${msg:-unknown error}"
    exit 1
  }

  rm -f "$PY_STDERR"
  trap - EXIT

  log "DATABASE_URL parsed successfully"
fi

# Validate required values (DB_USER/DB_PASS optional)
if [ -z "${DB_HOST:-}" ] || [ -z "${DB_PORT:-}" ] || [ -z "${DB_NAME:-}" ]; then
  err "Missing required database connection values: DB_HOST, DB_PORT, DB_NAME"
  exit 1
fi

if [ -z "${DB_USER:-}" ]; then
  warn "DB_USER not set. Some authentication methods may not work."
fi

# ----------------------------
# Wait for database readiness
# ----------------------------
# Skip database check if SKIP_DB_CHECK is set (e.g., for Flower which doesn't need DB)
if [ "${SKIP_DB_CHECK:-0}" = "1" ]; then
  log "Skipping database readiness check (SKIP_DB_CHECK=1)"
else
  MAX_WAIT_SECONDS="${MAX_WAIT_SECONDS:-60}"
  WAIT_INTERVAL="${WAIT_INTERVAL:-1}"
  ELAPSED=0

  # Optional jitter to reduce thundering herd in scaled deployments
  if [ "${JITTER_ON_STARTUP:-1}" = "1" ]; then
    JITTER=$((RANDOM % 3))
    if [ "$JITTER" -gt 0 ]; then
      log "Startup jitter: sleeping ${JITTER}s"
      sleep "$JITTER"
    fi
  fi

  log "Waiting for database to be ready (max ${MAX_WAIT_SECONDS}s)..."

  # Set PGPASSWORD only if provided (optional)
  if [ -n "${DB_PASS:-}" ]; then
    export PGPASSWORD="$DB_PASS"
  fi

  PSQL_ARGS=(-h "$DB_HOST" -p "$DB_PORT" -d "$DB_NAME" -c '\q')
  if [ -n "${DB_USER:-}" ]; then
    PSQL_ARGS=(-h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c '\q')
  fi

  until psql "${PSQL_ARGS[@]}" 2>/dev/null; do
    if [ "$ELAPSED" -ge "$MAX_WAIT_SECONDS" ]; then
      err "Database connection timeout after ${MAX_WAIT_SECONDS}s"
      if [ "${DEBUG:-0}" = "1" ]; then
        err "  Host: $DB_HOST"
        err "  Port: $DB_PORT"
        err "  User: ${DB_USER:-<not set>}"
        err "  Database: $DB_NAME"
      else
        err "  Check database configuration, credentials, and network connectivity."
      fi
      exit 1
    fi

    log "Database unavailable - sleeping (${ELAPSED}/${MAX_WAIT_SECONDS}s)"
    sleep "$WAIT_INTERVAL"
    ELAPSED=$((ELAPSED + WAIT_INTERVAL))
  done

  log "Database is ready!"

  # Reduce exposure surface: remove password from environment after readiness check
  unset PGPASSWORD || true
  unset DB_PASS || true
fi

# ----------------------------
# Migrations
# ----------------------------
# Recommended for production multi-replica: set SKIP_MIGRATIONS=1 and run migrations as a one-off job/step.
if [ "${SKIP_MIGRATIONS:-0}" != "1" ]; then
  log "Running database migrations..."
  PYTHONPATH="${PYTHONPATH:-.}" uv run alembic upgrade head
  log "Database migrations completed successfully!"
else
  log "Skipping migrations (SKIP_MIGRATIONS=1)"
fi

# ----------------------------
# Start the application
# ----------------------------
log "Starting FastAPI application..."
exec "$@"
