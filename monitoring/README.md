# Monitoring Stack

## Quick Start

```bash
# 1. Create network (if not exists)
docker network create assistants_app_network

# 2. Start main services (creates logs for Promtail)
docker compose up -d

# 3. Start monitoring stack (includes Prometheus, Loki, Grafana + exporters)
cd monitoring
docker compose -f docker-compose.monitoring.yml --env-file ../.env up -d
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

## Alerting

Alerts are configured via Grafana Unified Alerting and can send notifications to Telegram.

### Setup Telegram Alerts

1. Create a Telegram bot via [@BotFather](https://t.me/BotFather)
2. **Important:** Send `/start` to your bot first
3. Get the chat ID:
   ```bash
   curl https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
4. Create contact points config:
   ```bash
   cd monitoring/grafana/provisioning/alerting
   cp contactpoints.yml.template contactpoints.yml
   # Edit contactpoints.yml with your bot token and chat ID
   ```
5. Start/restart monitoring stack:
   ```bash
   cd monitoring
   docker compose -f docker-compose.monitoring.yml --env-file ../.env up -d
   ```

### Alert Rules

Pre-configured alerts in `grafana/provisioning/alerting/rules.yml`:

| Alert | Severity | Condition | For |
|-------|----------|-----------|-----|
| Service Down | critical | Any service unreachable | 2m |
| PostgreSQL Down | critical | Database unreachable | 1m |
| Redis Down | critical | Redis unreachable | 1m |
| High Error Rate | critical | >10 errors in 5m | 5m |
| Cron Job Failures | warning | >5 failures in 1h | 0s |
| Queue Backlog | warning | >100 messages pending | 10m |
| LLM API Errors | critical | >10 errors in 5m | 0s |
| High HTTP Error Rate | warning | >5% 5xx errors | 5m |

### Test Alerts

```bash
# View alert rules in Grafana
open http://localhost:3000/alerting/list

# Manually trigger test notification (via Grafana UI)
# Go to: Alerting -> Contact points -> telegram-alerts -> Test
```

## Troubleshooting

**No logs in Loki:**
- Verify Promtail can access Docker socket
- Check project label filter matches: `com.docker.compose.project=assistants`

**Prometheus targets down:**
- Services need `/metrics` endpoint (Фаза 5)
- Check network connectivity between containers

**Alerts not sending to Telegram:**
- Verify `TELEGRAM_ALERT_BOT_TOKEN` and `TELEGRAM_ALERT_CHAT_ID` are set
- Check Grafana logs: `docker logs grafana`
- Test contact point in Grafana UI: Alerting -> Contact points -> Test
