# Smart Assistant

Интеллектуальный ассистент, построенный на OpenAI Assistants API, предназначенный для управления различными аспектами повседневной жизни через естественный язык.

## Архитектура

### Сервисы
- **assistant** - Основной сервис ассистента
  - Использует OpenAI Assistants API
  - Управляет контекстом и историей диалогов
  - Координирует работу инструментов
- **rest_service** - REST API сервис
  - Управляет данными пользователей
  - Хранит конфигурации ассистентов
  - Обрабатывает запросы от других сервисов
- **google_calendar_service** - Сервис для работы с Google Calendar
  - Управление событиями
  - Интеграция с Google API
- **cron_service** - Сервис для выполнения периодических задач
  - Планировщик задач
  - Обработка напоминаний
- **tg_bot** - Telegram бот
  - Пользовательский интерфейс
  - Обработка сообщений

### Технологии
- Python 3.11+
- FastAPI
- PostgreSQL
- Redis
- Docker
- OpenAI Assistants API
- Telegram Bot API
- Google Calendar API

## Установка

1. Клонируйте репозиторий:
```bash
git clone <repository-url>
cd Assistants
```

2. Создайте `.env` файл с необходимыми переменными окружения:
```bash
OPENAI_API_KEY=your_openai_api_key
TELEGRAM_TOKEN=your_telegram_bot_token
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=your_db_name
DATABASE_URL=postgresql://user:password@db:5432/dbname
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=your_google_redirect_uri
```

3. Запустите сервисы с помощью Docker Compose:
```bash
docker compose up -d
```

## Разработка

### Локальная разработка
1. Создайте виртуальное окружение:
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# или
.venv\Scripts\activate  # Windows
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Запустите сервисы в режиме разработки:
```bash
docker compose up -d db redis
python assistant/src/main.py
```

### Тестирование
Запуск всех тестов:
```bash
./run_tests.sh
```

Запуск тестов для конкретного сервиса:
```bash
./run_tests.sh rest_service
./run_tests.sh google_calendar_service
./run_tests.sh cron_service
```

### Структура проекта
```
.
├── assistant/          # Сервис ассистента
│   ├── src/           # Исходный код
│   │   ├── assistants/ # Реализации ассистентов
│   │   ├── tools/     # Инструменты
│   │   ├── core/      # Основные компоненты
│   │   ├── messages/  # Обработка сообщений
│   │   └── storage/   # Хранение данных
│   └── tests/         # Тесты
├── rest_service/      # REST API сервис
├── google_calendar_service/ # Сервис календаря
├── cron_service/     # Сервис планировщика
├── tg_bot/          # Telegram бот
└── shared_models/   # Общие модели данных
```

## Взаимодействие между сервисами

### Поток запросов
1. Пользователь отправляет сообщение через Telegram бот
2. Сообщение обрабатывается сервисом ассистента
3. Ассистент определяет необходимые инструменты
4. Инструменты взаимодействуют с соответствующими сервисами через REST API
5. Результаты возвращаются пользователю через Telegram

### Очереди сообщений
- Redis используется для:
  - Хранения истории диалогов
  - Кэширования результатов инструментов
  - Очередей сообщений между сервисами

### База данных
- PostgreSQL используется для:
  - Хранения данных пользователей
  - Конфигураций ассистентов
  - Истории взаимодействий

## Мониторинг

### Логирование
- Каждый сервис использует структурированное логирование
- Логи доступны через Docker logs
- Поддерживается централизованный сбор логов

### Мониторинг очередей
```bash
python monitor_queue.py
```

## Документация

Подробное описание реализации и архитектуры доступно в [project_overview.md](project_overview.md). 