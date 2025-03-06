#!/bin/bash

# Запускаем тестовую базу данных
docker compose -f docker-compose.test.yml up -d

# Ждем, пока база данных будет готова
echo "Waiting for database to be ready..."
sleep 5

# Запускаем тесты
echo "Running tests..."
python -m pytest tests/ -v

# Сохраняем результат тестов
TEST_RESULT=$?

# Останавливаем и удаляем контейнеры
echo "Cleaning up..."
docker compose -f docker-compose.test.yml down

# Возвращаем результат тестов
exit $TEST_RESULT 