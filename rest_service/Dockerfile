FROM python:3.12-slim

WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода приложения
COPY ./app ./app
COPY ./alembic ./alembic
COPY ./alembic.ini .
COPY ./manage.py .

# Установка переменных окружения
ENV PYTHONPATH=/app

# Сделаем manage.py исполняемым
RUN chmod +x manage.py

# Команда для запуска FastAPI
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
