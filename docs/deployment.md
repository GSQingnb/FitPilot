# FitPilot Deployment Guide

## Architecture

The production deployment uses Docker Compose to orchestrate 8 services behind a single Nginx reverse proxy.

```
Browser → http://localhost:80
  ├── /           → Next.js frontend (:3000)
  ├── /api/       → FastAPI backend (:8000)  [prefix stripped]
  ├── /metrics    → Prometheus (:9090)       [internal only]
  └── /nginx-health → Nginx self-check
```

## Services

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| `postgres` | postgres:16-alpine | 5432 | Business data |
| `redis` | redis:7-alpine | 6379 | Tokens, locks, sessions |
| `chromadb` | chromadb/chroma:0.5.23 | 8000 | Knowledge base RAG |
| `prometheus` | prom/prometheus:latest | 9090 | Monitoring |
| `db-init` | fitpilot-echomind:local | — | One-shot: migrations + seed |
| `echomind` | fitpilot-echomind:local | 8000 | FastAPI backend |
| `frontend` | fitpilot-frontend | 3000 | Next.js app |
| `nginx` | nginx:alpine | 80 | Reverse proxy |

## Data Volumes

| Volume | Purpose | Warning |
|--------|---------|---------|
| `postgres-data` | Database files | **Do not delete** |
| `redis-data` | Redis persistence | Safe to delete |
| `chromadb-data` | Knowledge base vectors | Safe to delete |
| `prometheus-data` | Metrics history | Safe to delete |
| `nginx-logs` | Access/error logs | Safe to delete |

> **Warning**: Never run `docker compose down -v` on a production database. It permanently deletes `postgres-data`.

## Database Initialization

The `db-init` service runs once on startup:
1. `alembic upgrade head` — applies all pending migrations
2. `python -m database.seed` — seeds the exercise library (idempotent)

It uses the same image as `echomind` so no extra build is needed. If `db-init` exits with code 0, the application starts. If it fails, `echomind` will not start.

## Nginx Configuration

The Nginx config (`config/nginx/nginx.conf`) does two things:
1. **API proxy**: `location /api/` proxies to `echomind:8000/` — the trailing slash strips the `/api` prefix
2. **Frontend proxy**: `location /` proxies to `frontend:3000`

Cookie path is set to `/api/auth` via `AUTH_COOKIE_PATH` so refresh cookies are sent on API requests.

## Environment Variables

See `.env.example` for the full list. Key variables for deployment:

| Variable | Docker Default | Notes |
|----------|---------------|-------|
| `POSTGRES_PASSWORD` | — | Must match database |
| `JWT_SECRET_KEY` | — | Must be strong random string |
| `ANTHROPIC_API_KEY` | — | Required for AI features |
| `AUTH_COOKIE_PATH` | `/api/auth` | Must match Nginx proxy |
| `AUTH_COOKIE_SECURE` | `false` | Set `true` for HTTPS |
| `FRONTEND_ORIGINS` | `http://localhost` | CORS allowed origins |

## Frontend Build

The frontend is built with `NEXT_PUBLIC_API_BASE_URL=/api` during Docker build. This value is baked into the JavaScript bundle — the browser makes API calls to the same origin. Changing it requires rebuilding the frontend image.

## Health Checks

All services have health checks:

| Service | Method | Endpoint |
|---------|--------|----------|
| postgres | pg_isready | — |
| redis | redis-cli ping | — |
| chromadb | HTTP | /api/v1/heartbeat |
| prometheus | HTTP | /-/healthy |
| echomind | Python urllib | /health |
| frontend | wget | /login |
| nginx | wget | /nginx-health |

The backend health check uses Python stdlib (`urllib.request`) — no curl dependency.

## Common Commands

```bash
# Start all services
docker compose up -d

# Rebuild and restart
docker compose up -d --build

# View service status
docker compose ps -a

# View logs
docker compose logs -f echomind
docker compose logs -f frontend

# Restart a specific service
docker compose restart echomind

# Run database migrations manually
docker compose run --rm db-init

# Run smoke test
python scripts/smoke_test.py
```

## Troubleshooting

**db-init failed**: Check logs with `docker compose logs db-init`. Common causes:
- Database not healthy yet (wait and retry)
- Migration error (check alembic logs)
- Wrong DATABASE_URL

**Frontend returns 404**: Check that Nginx is running and frontend service is healthy.

**AI features return 502**: Check that `ANTHROPIC_API_KEY` is set and valid in `.env`.

**Login/refresh not working**: Verify `AUTH_COOKIE_PATH=/api/auth` is set in Docker environment.
