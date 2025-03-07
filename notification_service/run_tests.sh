#!/bin/bash

# Остановить и удалить существующие контейнеры
docker compose -f docker-compose.test.yml down

# Запустить тесты
docker compose -f docker-compose.test.yml up --build --abort-on-container-exit

# Получить статус выполнения тестов
TEST_EXIT_CODE=$(docker compose -f docker-compose.test.yml ps -q tests | xargs docker inspect -f '{{.State.ExitCode}}')

# Очистка
docker compose -f docker-compose.test.yml down

# Выход с кодом завершения тестов
exit $TEST_EXIT_CODE 