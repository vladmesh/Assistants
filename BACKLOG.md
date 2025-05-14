# Project Backlog

## Tasks

- [ ] Remove milliseconds from timestamps in assistant messages to save tokens. 
- [ ] Убрать обязательность поля startup_message в схеме shared_models.api_schemas.AssistantCreate (сделать Optional[str] = None). Рассмотреть изменение shared_models.api_schemas.AssistantBase, чтобы поле startup_message стало Optional[str] = None.
- [ ] Настроить кэширование при деплое на сервер 
- [ ] Продумать поддержку Markdown в сообщениях ассистента: обеспечить корректное форматирование текста (например, списки, жирный шрифт) и корректное отображение URL-адресов, содержащих спецсимволы (например, подчеркивания), без их преобразования в элементы разметки. 