import logging
from datetime import UTC, datetime
from pathlib import Path

from langchain_core.messages import BaseMessage, RemoveMessage

logger = logging.getLogger(__name__)

# Ensure the log directory exists
LOG_DIR = Path("logs/message_logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_LOG_FILE_PATH = "/src/messages_log.txt"


async def log_messages_to_file(
    assistant_id: str,
    user_id: str,
    messages: list[BaseMessage],
    total_tokens: int,
    context_limit: int,
    log_file_path: str = DEFAULT_LOG_FILE_PATH,
    step_name: str = "Unknown Step",
):
    """Logs assistant messages, token count, and context info to a file."""

    log_extra = {
        "user_id": user_id,
        "assistant_id": assistant_id,
        "step_name": step_name,
    }

    try:
        timestamp = datetime.now(UTC).isoformat()
        context_percentage = (
            (total_tokens / context_limit) * 100 if context_limit > 0 else 0
        )
        thread_id = f"user_{user_id}_assistant_{assistant_id}"

        # Use separate write calls for robustness
        with open(log_file_path, "a", encoding="utf-8") as f:
            f.write(f"--- Log Entry: {timestamp} (Thread: {thread_id}) ---\n")
            f.write(f"Step        : {step_name}\n")
            f.write(f"Assistant ID: {assistant_id}\n")
            f.write(f"User ID     : {user_id}\n")
            context_line = (
                "Context Info: "
                f"Total={total_tokens}, Limit={context_limit}, "
                f"Usage={context_percentage:.2f}%\n"
            )
            f.write(context_line)
            f.write(f"Messages ({len(messages)} total):\n")

            # Filter out RemoveMessage before logging
            logged_messages = 0
            for i, msg in enumerate(messages):
                if isinstance(msg, RemoveMessage):
                    # Optionally log that a RemoveMessage was skipped
                    # await f.write(f"  [{i}] Skipped RemoveMessage(id={msg.id})\n")
                    continue  # Skip RemoveMessage

                logged_messages += 1
                try:
                    # Basic representation
                    msg_type = type(msg).__name__
                    msg_content_preview = str(getattr(msg, "content", ""))[
                        :500
                    ].replace("\n", " ")
                    msg_id = getattr(msg, "id", "N/A")
                    msg_name = getattr(msg, "name", None)
                    msg_repr = (
                        f"[{i}] {msg_type}: {msg_content_preview}... (ID: {msg_id})"
                    )
                    if msg_name:
                        msg_repr += f" (Name: {msg_name})"
                    f.write(f"  {msg_repr}\n")

                    # Optional: log full content if needed
                    # if isinstance(msg, ToolMessage) or (
                    #     isinstance(msg, AIMessage) and msg.tool_calls
                    # ):
                    #     await f.write(f"    Full Repr: {repr(msg)}\n")

                except Exception as log_err:
                    f.write(f"  [{i}] Error logging message details: {log_err}\n")
                    f.write(f"    Fallback Repr: {repr(msg)}\n")
            f.write("---" * 10 + "\n\n")  # Separator

        # Optional: Keep the small delay if needed, otherwise remove
        # await asyncio.sleep(0.001)

    except Exception as e:
        logger.error(
            f"Failed to write messages log to {log_file_path}: {e}",
            exc_info=True,
            extra=log_extra,
        )
