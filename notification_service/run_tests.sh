#!/bin/bash

# Создаем сеть, если её нет
docker network create notification_service_default 2>/dev/null || true

# Запускаем Redis для тестов
docker run -d --name notification_service-test-redis \
  --network notification_service_default \
  redis:7-alpine

# Ждем, пока Redis будет готов
echo "Waiting for Redis to be ready..."
sleep 2

# Запускаем тесты
echo "Running tests..."
pytest tests/ -v

# Очищаем
echo "Cleaning up..."
docker rm -f notification_service-test-redis
docker network rm notification_service_default 