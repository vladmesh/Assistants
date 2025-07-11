# Админ-панель Smart Assistant

## Общее описание
Админ-панель представляет собой веб-интерфейс на Streamlit для управления всеми аспектами Smart Assistant. Панель обеспечивает удобный доступ к управлению пользователями, ассистентами, инструментами и настройками системы.

## Основные разделы

### 1. Управление пользователями
- Просмотр списка всех пользователей
- Фильтрация и поиск пользователей
- Детальная информация о пользователе:
  - Основные данные (ID, Telegram ID, username)
  - История взаимодействий
  - Назначенные ассистенты
  - Статистика использования
- Возможность блокировки/разблокировки пользователей
- Управление правами доступа

### 2. Управление ассистентами
- Создание новых ассистентов
- Редактирование существующих ассистентов:
  - Название и описание
  - Модель OpenAI
  - Инструкции
  - Тип ассистента
  - Статус активности
- Назначение инструментов ассистентам
- Просмотр статистики использования
- Тестирование ассистентов в реальном времени

### 3. Управление инструментами
- Создание новых инструментов
- Редактирование существующих инструментов:
  - Название и описание
  - Схема входных данных
  - Тип инструмента
  - Статус активности
- Назначение инструментов ассистентам
- Тестирование инструментов

### 4. Мониторинг системы
- Статистика использования:
  - Количество активных пользователей
  - Количество сообщений
  - Время отклика
  - Использование ресурсов
- Логи системы
- Статус всех сервисов
- Ошибки и предупреждения

### 5. Настройки системы
- Конфигурация OpenAI:
  - API ключи
  - Модели
  - Лимиты
- Настройки Redis
- Настройки базы данных
- Общие настройки системы

### 6. Глобальные настройки системы
- Управление общими параметрами работы ассистентов:
  - **Промпт суммаризации:** Редактирование промпта, используемого для создания саммари истории диалога.
  - **Размер контекстного окна:** Установка максимального количества токенов, передаваемых в LLM.

### 7. Управление задачами
- Просмотр запланированных задач
- Создание новых задач
- Редактирование существующих задач
- Мониторинг выполнения задач
- История выполнения

## Технические требования

### Безопасность
- Аутентификация администраторов
- Разграничение прав доступа
- Логирование действий администраторов
- Защита от CSRF и XSS атак

### Производительность
- Кэширование данных
- Пагинация для больших списков
- Асинхронная загрузка данных
- Оптимизация запросов к базе данных

### Интерфейс
- Адаптивный дизайн
- Темная/светлая тема
- Интуитивно понятная навигация
- Информативные сообщения об ошибках
- Подтверждение важных действий

## Интеграция
- REST API для всех операций
- WebSocket для real-time обновлений
- Интеграция с системой логирования
- Экспорт данных в различные форматы

## Дополнительные функции
- Резервное копирование данных
- Восстановление из резервной копии
- Экспорт/импорт конфигураций
- Массовые операции с данными
- Система уведомлений для администраторов

```bash
# Start the service
docker compose up -d admin_service

# View logs
docker compose logs -f admin_service
```

## Development

### Project Structure

```
admin_service/
├── src/                    # Source code
│   ├── admin_service/      # Service package
│   ├── config.py           # Configuration
│   ├── main.py             # Entry point
│   └── rest_client.py      # REST API client
├── tests/                  # Tests
├── Dockerfile              # Production Dockerfile
├── Dockerfile.test         # Test Dockerfile
├── docker-compose.test.yml # Test configuration
└── pyproject.toml          # Poetry dependencies and settings
```

### Running Tests

```bash
# Run tests
docker compose -f admin_service/docker-compose.test.yml up --build
```

## Interaction with Other Services

### REST Service

Admin Service interacts with the REST Service to obtain data about users, assistants, tools, and tasks.

## Configuration

The service uses the following environment variables:

- `REST_SERVICE_URL`: REST API URL (default: http://rest_service:8000)
- `LOG_LEVEL`: Logging level (default: INFO) 