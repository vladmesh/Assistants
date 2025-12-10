# Project Backlog

## Tasks

- [x] Remove milliseconds from timestamps in assistant messages to save tokens. 
- [ ] Убрать обязательность поля startup_message в схеме shared_models.api_schemas.AssistantCreate (сделать Optional[str] = None). Рассмотреть изменение shared_models.api_schemas.AssistantBase, чтобы поле startup_message стало Optional[str] = None.
- [ ] Настроить кэширование при деплое на сервер 
- [ ] Продумать поддержку Markdown в сообщениях ассистента: обеспечить корректное форматирование текста (например, списки, жирный шрифт) и корректное отображение URL-адресов, содержащих спецсимволы (например, подчеркивания), без их преобразования в элементы разметки. 
- [ ] Пофиксить уязвимости безопасности, на которые указывает GitHub. 
- [ ] Реализовать индикацию процесса обработки запроса ассистентом (например, сообщение "Ассистент думает..." или анимация) для улучшения UX. 
- [x] Исправить timezone awareness в REST API: модели должны возвращать aware datetime (с tzinfo=UTC) вместо naive datetime. Затронутые места:
    - `rest_service`: модели `Assistant`, `Message` и другие с полями `created_at`, `updated_at` должны возвращать timezone-aware datetime.
    - `shared_models`: схемы API должны корректно сериализовать datetime с timezone.
    - После исправления можно удалить defensive code в `assistant_service/src/assistants/factory.py` (`_check_and_update_assistant_cache`).
- [x] Реализовать полную поддержку часовых поясов для регулярных напоминаний. Это включает:
    - Сохранение часового пояса вместе с CRON-выражением в `rest_service` (потребуется миграция БД).
    - Передачу часового пояса из `rest_service` в `cron_service`.
    - Использование часового пояса в `cron_service` при планировании задач APScheduler (например, `CronTrigger(..., timezone=...)`).
    - Обновление `shared_models` для поддержки поля `timezone` в схемах напоминаний.
    - Корректную обработку `timezone` в `ReminderCreateTool` в `assistant_service`.