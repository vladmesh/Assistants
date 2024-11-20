import os
import time

import openai

def main():
    # Чтение токена OpenAI из переменных окружения
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        print("Ошибка: Переменная окружения OPENAI_API_KEY не задана!")
        return

    # Задай ID ассистента
    assistant_id = os.getenv("OPENAI_ASSISTANT_ID")  # Укажи ID ассистента, созданного через OpenAI платформу
    if not assistant_id:
        print("ОШИБКААА")
        return
    client = openai.OpenAI(api_key=openai_api_key)

    thread = client.beta.threads.create()

    message = client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content="I need to solve the equation `3x + 11 = 14`. Can you help me?"
    )

    run = client.beta.threads.runs.create_and_poll(
        thread_id=thread.id,
        assistant_id=assistant_id,
        instructions="Please address the user as Jane Doe. The user has a premium account."
    )

    time.sleep(15) #rewrite

    if run.status == 'completed':
        messages = client.beta.threads.messages.list(
            thread_id=thread.id
        )
        print(messages)
    else:
        print(run.status)


if __name__ == "__main__":
    #main()
    print("Dummy assistant")
