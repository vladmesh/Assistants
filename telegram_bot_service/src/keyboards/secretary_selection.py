from typing import Dict, List

# Import shared models for type hints
from shared_models.api_schemas import AssistantRead

# Define the structure of a button row for clarity
ButtonRow = List[Dict[str, str]]
Keyboard = List[ButtonRow]


def create_secretary_selection_keyboard(secretaries: List[AssistantRead]) -> Keyboard:
    """Creates an inline keyboard for selecting a secretary.

    Args:
        secretaries: A list of secretary objects (AssistantRead).

    Returns:
        A list of button rows suitable for Telegram's inline keyboard.
    """
    keyboard_buttons: Keyboard = []
    for secretary in secretaries:
        # Use attribute access for schema objects
        # description = secretary.description or "(Нет описания)" # No longer needed for button text
        # Truncate description to avoid overly long buttons
        # display_description = ( # No longer needed for button text
        #     f"{description[:50]}{\'...\' if len(description) > 50 else \'\'}"
        # )
        # button_text = f"{secretary.name} - {display_description}" # OLD VERSION
        button_text = secretary.name  # NEW VERSION: Only name on the button
        callback_data = f"select_secretary_{secretary.id}"
        keyboard_buttons.append([{"text": button_text, "callback_data": callback_data}])
    return keyboard_buttons
