# Используем базовый образ Python
FROM python:3.10-slim
ENV PYTHONUNBUFFERED=1
# Устанавливаем зависимости
WORKDIR /src
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY src /src

# Указываем команду запуска
CMD ["python", "main.py"]
