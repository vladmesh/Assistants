# Monitoring Stack

## Quick Start

```bash
# 1. Create network (if not exists)
docker network create assistants_app_network

# 2. Start main services (creates logs for Promtail)
docker compose up -d

# 3. Start monitoring stack
cd monitoring
docker compose -f docker-compose.monitoring.yml up -d

# 4. (Optional) Start exporters for Redis/Postgres metrics
docker compose --profile monitoring up -d redis_exporter postgres_exporter
```

## Access

| Service | URL | Credentials |
|---------|-----|-------------|
| Grafana | http://localhost:3000 | admin / admin (or GRAFANA_ADMIN_PW) |
| Prometheus | http://localhost:9090 | - |
| Loki | http://localhost:3100 | - |

## Grafana Dashboards

Pre-provisioned dashboards in folder "Smart Assistant":
- **Overview** - Error rates, request counts, service health
- **Logs** - Log viewer with service/level filters

## Verify Setup

```bash
# Check services
docker compose -f docker-compose.monitoring.yml ps

# Check Loki is receiving logs
curl -s http://localhost:3100/loki/api/v1/labels | jq

# Check Prometheus targets
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[].labels.job'
```

## Troubleshooting

**No logs in Loki:**
- Verify Promtail can access Docker socket
- Check project label filter matches: `com.docker.compose.project=assistants`

**Prometheus targets down:**
- Services need `/metrics` endpoint (Фаза 5)
- Check network connectivity between containers
