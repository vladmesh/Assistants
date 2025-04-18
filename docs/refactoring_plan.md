# План рефакторинга проекта

## 1. Стандартизация именования ✅

### 1.1. Текущие проблемы
- ✅ Несогласованность в именовании сервисов (например, `rest_service` vs `tg_bot`)
- ✅ Разные форматы именования в docker-compose.yml и реальных директориях
- ✅ Отсутствие единого стиля для именования контейнеров и образов

### 1.2. План действий
1. ✅ Создать документ с правилами именования:
   - Сервисы: snake_case, с префиксом `smart_assistant_` (например, `smart_assistant_rest`)
   - Контейнеры: kebab-case (например, `smart-assistant-rest`)
   - Образы: snake_case с префиксом `smart_assistant_` (например, `smart_assistant_rest`)
   - Директории: snake_case (например, `smart_assistant_rest`)

2. ✅ Обновить все имена в:
   - docker-compose.yml
   - Директориях сервисов
   - Скриптах управления
   - Документации

## 2. Стандартизация структуры сервисов ✅

### 2.1. Текущие проблемы
- ✅ Разные корневые папки в сервисах (где-то `src/`, где-то `app/`)
- ✅ Несогласованность в структуре импортов
- ✅ Отсутствие единого подхода к организации кода
- ✅ Несогласованность в структуре тестовых директорий

### 2.2. План действий
1. ✅ Создать шаблон структуры сервиса
2. ✅ Стандартизировать тестовое окружение
3. ✅ Обновить Dockerfile'ы и docker-compose файлы всех сервисов
4. ✅ Обновить каждый сервис:
   - Переименовать директории
   - Реорганизовать структуру
   - Обновить импорты
   - Настроить тестовое окружение

## 3. Внедрение линтеров ✅

### 3.1. Текущие проблемы
- ✅ Отсутствие линтеров
- ✅ Неоптимальный код
- ✅ Несогласованность стиля

### 3.2. План действий
1. ✅ Создать базовую конфигурацию для:
   - ✅ black (форматирование)
   - ✅ isort (сортировка импортов)
   - ✅ flake8 (проверка стиля)
   - ✅ autoflake (удаление неиспользуемых импортов)
   - ✅ mypy (проверка типов)

2. ✅ Настроить pre-commit хуки:
   - ✅ Добавить в существующий pre-commit конфиг
   - ✅ Настроить автоматическое форматирование
   - ✅ Добавить проверку типов

3. ✅ Создать правила для:
   - Максимальной длины строки (88 символов, как в black)
   - Стиля импортов
   - Документации
   - Типизации

## 4. Улучшение управления зависимостями 🔄

### 4.1. Текущие проблемы
- ✅ Разные версии зависимостей в разных сервисах
- ✅ Отсутствие централизованного управления версиями
- ✅ Отсутствие проверки совместимости версий
- 🔄 Уязвимости в зависимостях (осталось обновить некритичные)

### 4.2. План действий
1. ✅ Создать центральный файл с версиями зависимостей
2. ✅ Внедрить Poetry для управления зависимостями
3. ✅ Обновить Dockerfile'ы
4. 🔄 Обновить зависимости:
   - ✅ Обновить критические зависимости
   - ⏳ Обновить остальные уязвимые зависимости
   - ⏳ Проверить совместимость версий

## 5. Улучшение конфигурации ⏳

### 5.1. Текущие проблемы
- Разбросанные переменные окружения
- Отсутствие валидации конфигурации
- Сложность управления разными окружениями
- Передача всего .env файла в сервисы (проблема безопасности и наглядности)

### 5.2. План действий
1. Внедрить систему конфигурации:
   - Внедрить pydantic для валидации
   - Создать базовые классы конфигурации
   - Разделить по окружениям (dev, test, prod)

2. Реорганизовать переменные окружения:
   - Создать `.env.example`
   - Разделить `.env` на логические блоки
   - Добавить валидацию при запуске
   - Отказаться от передачи .env файла целиком в сервисы:
     - Определить необходимые переменные для каждого сервиса
     - Явно указать их в docker-compose.yml
     - Удалить env_file из конфигурации сервисов
     - Обновить документацию

3. Улучшить управление секретами:
   - Внедрить vault или аналог
   - Добавить ротацию секретов
   - Улучшить безопасность хранения

## 6. Улучшение тестирования ⏳

### 6.1. Текущие проблемы
- Отсутствие единого подхода к тестированию
- Неполное покрытие тестами
- Сложность запуска тестов

### 6.2. План действий
1. Стандартизировать тестирование:
   - Создать базовые фикстуры
   - Добавить factory_boy
   - Настроить pytest-cov

2. Улучшить CI/CD:
   - Добавить проверку покрытия кода
   - Настроить автоматический запуск тестов
   - Добавить проверку безопасности

3. Добавить интеграционные тесты:
   - Создать тестовое окружение
   - Добавить тесты взаимодействия сервисов
   - Настроить автоматическое тестирование API

## 7. Улучшение мониторинга и логирования ⏳

### 7.1. Текущие проблемы
- Отсутствие централизованного логирования
- Нет мониторинга производительности
- Сложность отладки

### 7.2. План действий
1. Настроить логирование:
   - Внедрить structlog
   - Добавить контекстное логирование
   - Настроить ротацию логов

2. Добавить мониторинг:
   - Внедрить Prometheus метрики
   - Настроить Grafana дашборды
   - Добавить алерты

3. Улучшить отладку:
   - Добавить трассировку запросов
   - Настроить профилирование
   - Добавить инструменты для анализа

## 8. Обновление документации ⏳

### 8.1. План действий
1. Обновить файлы контекста:
   - llm_context.md
   - llm_context_assistant.md
   - Другие контекстные файлы

2. Обновить README.md:
   - Добавить информацию о новых правилах
   - Обновить инструкции по разработке
   - Добавить информацию о линтерах и форматировании

## 9. Порядок выполнения оставшихся задач

1. 🔄 Завершить обновление зависимостей
2. ⏳ Улучшить систему конфигурации
3. ⏳ Обновить каждый сервис:
   - assistant
   - rest_service
   - google_calendar_service
   - cron_service
   - tg_bot
4. ⏳ Настроить тестирование и CI/CD
5. ⏳ Добавить мониторинг и логирование
6. ⏳ Обновить документацию
7. ⏳ Провести финальное тестирование

## 10. Критерии успеха

- ✅ Все сервисы следуют единому стилю именования
- ✅ Структура всех сервисов соответствует шаблону
- ✅ Линтеры настроены и работают
- 🔄 Зависимости централизованы и безопасны
- ⏳ Конфигурация валидируется при запуске
- ⏳ Тестовое покрытие > 80%
- ⏳ Настроен мониторинг и логирование
- ⏳ CI/CD пайплайн успешно проходит
- ⏳ Все сервисы используют единый подход к логированию
- ⏳ Документация полная и актуальная 