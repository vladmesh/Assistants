# Smart Assistant

Умный ассистент с поддержкой естественного языка, построенный на LangChain и различных моделях OpenAI.

## Возможности

- 🗓️ Управление календарем
- 🌤️ Информация о погоде
- ✅ Управление задачами
- ❤️ Интеграция с устройствами здоровья
- 📍 Геолокационные функции

## Технологии

- Python
- LangChain
- OpenAI Models:
  - GPT-4
  - GPT-3.5-turbo
  - GPT-3.5-turbo-16k
- FastAPI
- Redis
- PostgreSQL
- Docker

## Установка

1. Клонируйте репозиторий:
```bash
git clone <repository-url>
cd Assistants
```

2. Создайте файл `.env` с необходимыми переменными окружения:
```bash
OPENAI_API_KEY=your_openai_api_key
TELEGRAM_TOKEN=your_telegram_bot_token
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=your_db_name
DATABASE_URL=postgresql://user:password@db:5432/dbname
```

3. Запустите сервисы через Docker Compose:
```bash
docker compose up -d
```

## Структура проекта

```
.
├── assistant/          # Сервис ассистента
│   ├── src/           # Исходный код
│   │   ├── models/    # Модели данных
│   │   ├── tools/     # Инструменты LangChain
│   │   └── utils/     # Вспомогательные функции
│   ├── Dockerfile     
│   └── requirements.txt
├── rest_service/      # REST API сервис
├── tg_bot/           # Telegram бот
├── notification_service/ # Сервис уведомлений
├── cron_service/     # Сервис для выполнения задач по расписанию
└── docker-compose.yml
```

## Разработка

Для локальной разработки:

1. Создайте виртуальное окружение:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows
```

2. Установите зависимости:
```bash
pip install -r assistant/requirements.txt
```

3. Запустите сервисы в режиме разработки:
```bash
docker compose up -d db redis
python assistant/src/main.py
```

## Тестирование

Каждый сервис содержит свой набор тестов. Для запуска всех тестов используйте:

```bash
# Запуск всех тестов
./run_tests.sh
```

### REST Service
- Тесты для CRUD операций с задачами
- Тесты для управления пользователями
- Тесты для работы с cron-задачами
```bash
cd rest_service
docker compose -f docker-compose.test.yml up --build --abort-on-container-exit
```

### Notification Service
- Тесты отправки уведомлений
- Тесты обработки приоритетов
- Тесты работы с Redis
```bash
cd notification_service
./run_tests.sh
```

### Cron Service
- Тесты парсинга cron-выражений
- Тесты отправки уведомлений
- Тесты получения запланированных задач
```bash
cd cron_service
docker compose -f docker-compose.test.yml up --build --abort-on-container-exit
```

### Статус тестов
| Сервис | Кол-во тестов | Статус |
|--------|---------------|---------|
| REST Service | 21 | ✅ |
| Notification Service | 12 | ✅ |
| Cron Service | 6 | ✅ |
| Telegram Bot | - | ⚠️ В разработке |
| Assistant Service | - | ⚠️ В разработке |

## Документация

Подробная документация доступна в [project_overview.md](project_overview.md). 