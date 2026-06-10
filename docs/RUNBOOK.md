# PitchProof Vigil - Operations Runbook

## SLOs

| Endpoint | SLO | Alert |
|---|---|---|
| `POST /api/ask` | p99 < 2 s | `AskAPIHighLatency` |
| `POST /api/evaluate` | p99 < 5 s | - |
| Gate decision availability | >= 99.5% | `GateBlockRateSpike` |

## On-Call Checklist

### Alert: HighEvalFailureRate
1. Check `GET /ready` - all checks healthy?
2. Check Phoenix MCP: `docker compose logs phoenix`
3. Check Gemini quota: GCP Console -> APIs & Services -> Gemini
4. Roll back to last known-good model version.

### Alert: GateBlockRateSpike
1. Inspect gate decisions: `GET /api/gate?limit=20` (as ADMIN)
2. Check which evaluator is blocking: `GET /api/stats` (verdict_breakdown)
3. Consider relaxing the gate threshold temporarily via the Policy Editor.
4. Page the ML team if `llm_judge` is the blocking evaluator.

### Alert: AskAPIHighLatency
1. Check Redis: `redis-cli -u $REDIS_URL info stats | grep commands_processed`
2. Check the DB slow-query log.
3. Scale backend: `docker compose up --scale backend=3`

## Database Backup

### Postgres WAL-based backup (pgBackRest)
```bash
pgbackrest --stanza=pitchproof stanza-create
pgbackrest --stanza=pitchproof --type=full backup
pgbackrest --stanza=pitchproof --target-timeline=latest restore
alembic -c /app/alembic.ini check
```

### Cloud SQL (managed)
Enable automated backups in the Cloud SQL console; point-in-time recovery within
the 7-day retention window.

## Horizontal Scaling
```bash
# Run 4 backend replicas sharing Postgres and Redis.
# Redis is REQUIRED for distributed rate limiting when replicas > 1.
REDIS_URL=redis://redis:6379/0 docker compose up --scale backend=4
```
With `REDIS_URL` set, rate-limit state is shared across all replicas. Without it,
each replica keeps an independent token bucket (tenants get N x capacity) - fine
for single-worker dev, not for production.
