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

## Alerting

Alerts are configured via Grafana Unified Alerting and can send notifications to Telegram.

### Setup Telegram Alerts

1. Create a Telegram bot via [@BotFather](https://t.me/BotFather) or use existing bot
2. **Important:** Send `/start` to your bot first to initialize the chat
3. Get the chat ID (send any message to bot, then check `https://api.telegram.org/bot<TOKEN>/getUpdates`)
4. Add environment variables to `.env`:

```bash
TELEGRAM_ALERT_BOT_TOKEN=your_bot_token_here
TELEGRAM_ALERT_CHAT_ID=your_chat_id_here
```

5. Start monitoring stack with env file:
```bash
cd monitoring
docker compose -f docker-compose.monitoring.yml --env-file ../.env up -d
```

**Note:** Due to Grafana's env var handling, you may need to configure the contact point via UI:
1. Open Grafana -> Alerting -> Contact points
2. Edit `telegram-alerts` and set bot token + chat ID manually

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
