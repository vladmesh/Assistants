# Smart Assistant

An intelligent assistant powered by LangChain and OpenAI Assistants API, designed to help manage various aspects of daily life through natural language interaction.

## Features

- 🗓️ Calendar Management
- 🌤️ Weather Information
- ✅ Task Management
- ❤️ Health Device Integration
- 📍 Geofencing Features

## Technologies

- Python
- LangChain with OpenAI Assistants API
- OpenAI Models:
  - GPT-4 (main assistant)
  - GPT-3.5-turbo (simple queries)
  - GPT-3.5-turbo-16k (large context)
- FastAPI
- Redis
- PostgreSQL
- Docker

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd Assistants
```

2. Create `.env` file with required environment variables:
```bash
OPENAI_API_KEY=your_openai_api_key
TELEGRAM_TOKEN=your_telegram_bot_token
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=your_db_name
DATABASE_URL=postgresql://user:password@db:5432/dbname
```

3. Start services with Docker Compose:
```bash
docker compose up -d
```

## Project Structure

```
.
├── assistant/          # Assistant service
│   ├── src/           # Source code
│   │   ├── models/    # Data models
│   │   ├── tools/     # LangChain tools
│   │   └── utils/     # Helper functions
│   ├── Dockerfile     
│   └── requirements.txt
├── rest_service/      # REST API service
├── tg_bot/           # Telegram bot
├── notification_service/ # Notification service
├── cron_service/     # Scheduled tasks service
└── docker-compose.yml
```

## Development

For local development:

1. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows
```

2. Install dependencies:
```bash
pip install -r assistant/requirements.txt
```

3. Start services in development mode:
```bash
docker compose up -d db redis
python assistant/src/main.py
```

## Testing

Run all tests:
```bash
./run_tests.sh
```

Individual service tests:
```bash
# REST Service tests
cd rest_service && pytest tests/

# Notification Service tests
cd notification_service && pytest tests/

# Cron Service tests
cd cron_service && pytest tests/
```

Test status:
| Service | Tests | Status |
|---------|-------|--------|
| REST Service | 21 | ✅ |
| Notification Service | 12 | ✅ |
| Cron Service | 6 | ✅ |
| Assistant Service | - | 🚧 |
| Telegram Bot | - | 🚧 |

## Documentation

For detailed documentation, see [project_overview.md](project_overview.md). 