from telegram import Update
from telegram.ext import ContextTypes
from app.utils.keyboard import get_main_menu_keyboard, format_task_message
from app.handlers.base import BaseHandler, require_user
import logging

logger = logging.getLogger(__name__)


class TaskHandler(BaseHandler):
    """Обработчик для работы с задачами."""
    
    @require_user
    async def add_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик добавления новой задачи."""
        try:
            query = update.callback_query
            await query.answer()
            
            self.set_user_state(context, {"state": "waiting_for_task_name"})
            await query.message.reply_text("Введите название задачи:")
        except Exception as e:
            await self.handle_error(update, context, e)
    
    @require_user
    async def handle_new_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик ввода новой задачи."""
        try:
            state = self.get_user_state(context)
            text = update.message.text
            
            if not self.validate_input(text):
                await update.message.reply_text(
                    "Название задачи должно содержать от 1 до 100 символов."
                )
                return
            
            if state.get("state") == "waiting_for_task_name":
                state["task_name"] = text
                state["state"] = "waiting_for_task_description"
                await update.message.reply_text("Введите описание задачи (или отправьте /skip):")
            elif state.get("state") == "waiting_for_task_description":
                state["task_description"] = text
                await self._create_task(update, context)
        except Exception as e:
            await self.handle_error(update, context, e)
    
    @require_user
    async def skip_description(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик пропуска описания задачи."""
        try:
            state = self.get_user_state(context)
            if state.get("state") == "waiting_for_task_description":
                state["task_description"] = "Нет описания"
                await self._create_task(update, context)
        except Exception as e:
            await self.handle_error(update, context, e)
    
    async def _create_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Создает новую задачу."""
        state = self.get_user_state(context)
        
        # Получаем или создаем пользователя
        user = self.rest_client.get_or_create_user(
            telegram_id=update.effective_user.id,
            username=update.effective_user.username
        )
        
        # Создаем задачу
        task = self.rest_client.create_task(
            user_id=user["id"],
            name=state["task_name"],
            description=state["task_description"]
        )
        
        logger.info(f"Created task {task['id']} for user {user['id']}")
        
        await update.message.reply_text(
            "✅ Задача создана!",
            reply_markup=get_main_menu_keyboard()
        )
        self.clear_user_state(context)
    
    @require_user
    async def list_tasks(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Показывает список задач."""
        try:
            query = update.callback_query
            await query.answer()
            
            # Получаем задачи пользователя
            user = self.rest_client.get_or_create_user(
                telegram_id=update.effective_user.id,
                username=update.effective_user.username
            )
            tasks_list = self.rest_client.get_user_tasks(user["id"])
            
            if not tasks_list:
                await query.message.reply_text(
                    "У вас пока нет задач.",
                    reply_markup=get_main_menu_keyboard()
                )
                return
            
            message = "📋 Ваши задачи:\n\n"
            for task in tasks_list:
                message += format_task_message(task) + "\n\n"
            
            await query.message.reply_text(
                message,
                reply_markup=get_main_menu_keyboard(),
                parse_mode="Markdown"
            )
        except Exception as e:
            await self.handle_error(update, context, e)
    
    @require_user
    async def update_task_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обновляет статус задачи."""
        try:
            query = update.callback_query
            await query.answer()
            
            _, task_id, status = query.data.split("_")
            
            # Обновляем статус задачи
            task = self.rest_client.update_task_status(task_id, status)
            logger.info(f"Updated task {task_id} status to {status}")
            
            await query.message.reply_text(
                f"✅ Статус задачи обновлен на: {status}",
                reply_markup=get_main_menu_keyboard()
            )
        except Exception as e:
            await self.handle_error(update, context, e) 