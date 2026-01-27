# Citatum

Production-ready research reproducibility assistant that ingests documents, chunks and embeds them, and serves retrieval with provenance via a FastAPI API and Celery workers. It ships with Alembic migrations, idempotent task tracking, structured logging/metrics, Docker Compose stack, and a Cloud Run CI/CD workflow.

**Tech & services**: FastAPI, Uvicorn, Celery, PostgreSQL + pgvector, SQLAlchemy, Alembic, RabbitMQ, Redis, Prometheus, Grafana, nginx (proxy in compose), Docker/Compose, GitHub Actions, Google Cloud Run + Artifact Registry (blueprint), Secret Manager/Workload Identity, LLM providers (OpenAI/Anthropic/Cohere), uv/pip, Python 3.12.

## Architecture

- **API**: FastAPI (`src/core/app.py`) with routers in `src/routes/`.
- **Workers**: Celery tasks (`src/tasks/`) for document ingestion/indexing and maintenance.
- **Data**: PostgreSQL + pgvector; ORM models under `src/models/`.
- **Vector DB**: pgvector default (switch via `VECTOR_DB_TYPE`).
- **Queue/Cache**: RabbitMQ as broker, Redis as result backend.
- **Observability**: Prometheus + Grafana; metrics middleware exposes `/TrhBVe_m5gg2002_E5VVqS`.
- **Reverse proxy (local/compose)**: nginx maps host `8080 -> fastapi:8000`.
- **Migrations**: Alembic in `src/models/db_schemas/citatum/alembic/`.

## Prerequisites

- Python 3.12
- Docker + Docker Compose (for the full stack)
- Postgres, RabbitMQ, Redis (or use compose services)
- LLM API keys (OpenAI/Anthropic/Cohere)

## Environment configuration

From repo root:

```bash
cd docker/env
cp .env.example .env
cp .env.example.postgres .env.postgres
cp .env.example.redis .env.redis
cp .env.example.rabbitmq .env.rabbitmq
cp .env.example.grafana .env.grafana
cp .env.example.postgres-exporter .env.postgres-exporter
```

Fill real secrets and credentials. Top-level `docker/.env` can mirror `docker/env/.env`.

Key variables: `POSTGRES_*`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `OPENAI_API_KEY`, `LLM_PROVIDER`, `VECTOR_DB_TYPE`, `FILE_ALLOWED_TYPES`, `FILE_MAX_SIZE_MB`.

## Local development (without Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt  # or uv pip install -r requirements.txt
export $(cat docker/env/.env | xargs)   # or set envs manually
uvicorn src.core.main:app --reload --port 8000
# Worker
celery -A src.core.celery_app worker --queues=default --loglevel=info
# Optional beat
celery -A src.core.celery_app beat --loglevel=info
# Migrations
alembic -c alembic.ini upgrade head
```

## Docker / Compose

```bash
cd docker
docker compose up --build -d
```

Exposed ports (defaults):

- API via nginx: `8080`
- FastAPI direct (if mapped): `${API_PORT}` -> 8000
- Flower: `5555`
- Postgres: `${POSTGRES_PORT}` -> 5432
- Redis: `6380` -> 6379
- RabbitMQ UI: `15672`
- Prometheus: `9090`
- Grafana: `3000`
- Postgres exporter: `9187`
- Node exporter: `9100`

The compose stack also runs Celery worker/beat, Prometheus, Grafana, exporters, and nginx.

## Key endpoints

- `GET /api/v1/` – welcome
- `GET|HEAD /api/v1/health` – health check
- `GET /TrhBVe_m5gg2002_E5VVqS` – Prometheus metrics
- Swagger UI: `/docs`

## Background processing

- Document ingest: `tasks.document_tasks.document_upload_and_process`
- Idempotency tracking table: `celery_task_executions`
- Maintenance task: `tasks.maintenance.clean_celery_executions_table` (hourly via Celery beat)

## Migrations

- Config: `alembic.ini`
- Scripts: `src/models/db_schemas/citatum/alembic/versions/`
- Run: `alembic -c alembic.ini upgrade head` (uses app config in `env.py` to derive DB URL when not set).

## Monitoring

- Prometheus scrape config: `docker/prometheus/prometheus.yml` (targets metrics path above).
- Grafana loads settings from `docker/env/.env.grafana`; import dashboards for FastAPI/Node/Postgres as needed.
- Metrics middleware: `src/utils/metrics.py`.

## Deployment (Cloud Run via GitHub Actions)

Workflow: `.github/workflows/deploy.yml`

- On pushes to `main`: build Docker image, push to Artifact Registry, deploy to Cloud Run.
- Secrets required: `GCP_PROJECT_ID`, `GCP_SA_KEY` (service account JSON).
- Defaults: repo `containers`, image `citatum-api`, region `us-central1`, service `citatum-api`.

### Production-ready GCP blueprint (end-to-end)

- **Compute**: Cloud Run service for FastAPI; Cloud Run Job or second service for Celery worker/beat (same image, different command).
- **Database**: Cloud SQL for PostgreSQL with pgvector extension enabled.
- **Broker/Backend**: Memorystore for Redis (use as Celery broker and result backend to avoid self-hosting RabbitMQ).
- **Storage**: GCS bucket for uploaded documents if persistence outside DB is needed.
- **Networking**: Serverless VPC Access connector so Cloud Run/Jobs reach Cloud SQL and Memorystore privately; restrict ingress to internal + HTTPS.
- **Identity/Secrets**: Workload Identity + Secret Manager for API keys/DB creds; mount via env vars.
- **Observability**: Cloud Logging/Monitoring; optionally export custom metrics from the Prometheus endpoint into Cloud Monitoring.
- **TLS**: Cloud Run provides HTTPS; map a custom domain with managed certs.
- **CI/CD**: Existing GitHub Actions workflow; set env vars `DATABASE_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, and `PORT=$PORT` for Cloud Run.
- **Example deploy commands**:
  - API: `gcloud run deploy citatum-api --image <IMAGE_URI> --region us-central1 --allow-unauthenticated --set-env-vars PORT=8080,DATABASE_URL=postgresql+asyncpg://...,CELERY_BROKER_URL=redis://...,CELERY_RESULT_BACKEND=redis://...`
  - Worker: `gcloud run deploy citatum-worker --image <IMAGE_URI> --region us-central1 --command "celery" --args "-A","src.core.celery_app","worker","--queues=default","--loglevel=info" --set-env-vars (same as above) --no-allow-unauthenticated`
  - Beat (optional): same image, command `celery ... beat`.

## Repo layout (high level)

- `src/core/` – app factory, celery app, middleware
- `src/routes/` – API routers
- `src/tasks/` – Celery tasks (ingest, maintenance)
- `src/models/` – ORM models and Alembic metadata
- `docker/` – compose stack, Dockerfiles, nginx config, Prometheus config
- `.github/workflows/` – CI/CD to Cloud Run

## Common commands

- Apply migrations: `alembic -c alembic.ini upgrade head`
- Run worker: `celery -A src.core.celery_app worker --loglevel=info`
- Run beat: `celery -A src.core.celery_app beat --loglevel=info`
- Compose logs: `docker compose logs -f fastapi celery-worker nginx`
