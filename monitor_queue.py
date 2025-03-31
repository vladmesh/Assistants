import json
import os
import sys

import redis


def monitor_queue(queue_name=None):
    """Monitor Redis queue for messages."""
    if queue_name is None:
        queue_name = os.getenv("REDIS_QUEUE_TO_TELEGRAM", "queue:to_telegram")

    print(f"Мониторинг очереди {queue_name}. Для выхода нажмите Ctrl+C")

    r = redis.Redis(host="localhost", port=6379, db=0)

    try:
        while True:
            result = r.brpop(queue_name, timeout=5)
            if result:
                channel, data = result
                try:
                    message = json.loads(data)
                    print("\nПолучено сообщение:")
                    print(json.dumps(message, indent=2, ensure_ascii=False))
                except json.JSONDecodeError:
                    print("\nПолучены данные (не JSON):")
                    print(data.decode("utf-8"))
    except KeyboardInterrupt:
        print("\nМониторинг остановлен")
    finally:
        r.close()


if __name__ == "__main__":
    # Если передано имя очереди как аргумент, используем его
    queue_name = sys.argv[1] if len(sys.argv) > 1 else None
    monitor_queue(queue_name)
