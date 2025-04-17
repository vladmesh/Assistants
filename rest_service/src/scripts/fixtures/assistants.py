"""Assistant fixtures for database initialization"""
import os
from typing import List

from models.assistant import Assistant, AssistantType


def create_secretary_assistant() -> Assistant:
    """Create Secretary assistant fixture"""
    return Assistant(
        name="secretary",
        assistant_type=AssistantType.OPENAI_API,
        is_secretary=True,
        model="gpt-4-turbo-preview",
        description="Вы - полезный ассистент-секретарь",
        instructions="""Вы - умный ассистент-секретарь. Вы можете:
1. Отвечать на вопросы
2. Помогать с планированием
3. Создавать напоминания
4. Делегировать творческие задачи писателю

Вы должны быть дружелюбным и профессиональным.""",
        openai_assistant_id=os.getenv("OPEN_API_SECRETAR_ID"),
        is_active=True,
    )


def create_writer_assistant() -> Assistant:
    """Create Writer assistant fixture"""
    return Assistant(
        name="writer",
        assistant_type=AssistantType.LLM,
        is_secretary=False,
        model="gpt-4-turbo-preview",
        description=(
            "Вы - специализированный ассистент для написания " "художественных текстов"
        ),
        instructions=(
            "Вы - специализированный ассистент для написания "
            "художественных текстов.\n"
            "Вы должны:\n"
            "1. Писать креативный и увлекательный контент\n"
            "2. Следовать стилю и тону, указанному пользователем\n"
            "3. Поддерживать согласованность в тексте\n"
            "4. Оказывать высококачественную помощь в написании"
        ),
        is_active=True,
    )


def get_all_assistants() -> list[Assistant]:
    """Get all assistant fixtures"""
    return [create_secretary_assistant(), create_writer_assistant()]
