FROM python:3.12-slim

WORKDIR /src

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода приложения
COPY ./src/ .
COPY ./alembic ./alembic
COPY ./alembic.ini .
COPY ./manage.py .

# Установка переменных окружения
ENV PYTHONPATH=/src

# Сделаем manage.py исполняемым
RUN chmod +x manage.py

# Команда для запуска FastAPI
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
