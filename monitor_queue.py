import redis
import json
import sys

def monitor_queue(queue_name="assistant_output_queue"):
    r = redis.Redis(host='redis', port=6379, decode_responses=True)
    
    print(f"Мониторинг очереди {queue_name}. Для выхода нажмите Ctrl+C")
    try:
        while True:
            try:
                # Wait for message
                result = r.brpop(queue_name, timeout=5)
                if result:
                    _, message = result
                    data = json.loads(message)
                    
                    # Pretty print
                    print("\n=== Новое сообщение ===")
                    print(f"От пользователя: {data.get('user_id')}")
                    print(f"Чат: {data.get('chat_id')}")
                    print(f"Статус: {data.get('status')}")
                    print(f"Ответ: {data.get('response')}")
                    if data.get('error'):
                        print(f"Ошибка: {data.get('error')}")
                    print("=====================\n")
            except json.JSONDecodeError:
                print(f"Ошибка декодирования JSON: {message}")
            except Exception as e:
                print(f"Ошибка: {e}")
                
    except KeyboardInterrupt:
        print("\nМониторинг завершен")

if __name__ == "__main__":
    queue_name = sys.argv[1] if len(sys.argv) > 1 else "assistant_output_queue"
    monitor_queue(queue_name) 