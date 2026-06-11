# PitchProof Vigil - Deployment

Full stack via Docker Compose: Postgres + Redis + Arize Phoenix + FastAPI
backend + React/nginx frontend. The committed `docker-compose.yml` is the source
of truth; host ports and secrets are environment-specific and supplied at
deploy time (never committed).

## Quick deploy (single host)

```bash
git clone https://github.com/vsenthil7/PitchProofVigil
cd PitchProofVigil

# 1) Secrets + CORS (mocks-first; flip USE_MOCKS=false to wire live Gemini)
cat > .env <<EOF
USE_MOCKS=true
JWT_SECRET=$(openssl rand -hex 32)
CORS_ORIGINS=http://YOUR_HOST:FRONTEND_PORT
EOF

# 2) (Optional) Remap host ports if the defaults collide with other apps.
#    Internal service ports are unchanged; only host mappings move.
cat > docker-compose.override.yml <<EOF
services:
  db:       { ports: ["5433:5432"] }
  backend:  { ports: ["8091:8000"] }
  frontend: { ports: ["8090:80"] }
EOF

docker compose up -d --build
docker compose ps
```

## Default vs. remapped host ports

| Service  | Internal | Default host | Example remap |
|----------|----------|--------------|---------------|
| frontend | 80       | 8080         | 8090          |
| backend  | 8000     | 8000         | 8091          |
| postgres | 5432     | 5432         | 5433          |
| redis    | 6379     | 6379         | 6379          |
| phoenix  | 6006     | 6006         | 6006          |

The frontend (nginx) proxies `/api/` to the backend by service name
(`backend:8000`) inside the compose network, so the frontend host port is the
only one users need. Demo URL = `http://YOUR_HOST:FRONTEND_PORT`.

## One-click demo

The login page has an **Explore the live demo** button (`POST /api/auth/demo`)
that idempotently seeds a multi-role org and signs in as owner. Seeded users
(password `demo-pass-1234`):

| Role     | Email                   |
|----------|-------------------------|
| owner    | owner@demo.worldcup     |
| admin    | admin@demo.worldcup     |
| operator | operator@demo.worldcup  |
| viewer   | viewer@demo.worldcup    |

## Health

```bash
curl -s -o /dev/null -w "%{http_code}\\n" http://localhost:FRONTEND_PORT
curl -s http://localhost:BACKEND_PORT/health
curl -s http://localhost:BACKEND_PORT/ready
```

## Live mode (Vertex AI / Gemini)

Set in `.env`: `USE_MOCKS=false`, `GOOGLE_CLOUD_PROJECT=<project-id>`, and mount
Application Default Credentials. Arize Phoenix runs as a container (free); the
optional Arize AX cloud (`ARIZE_API_KEY`, `ARIZE_SPACE_ID`) degrades to mock if
unset and is NOT required.
