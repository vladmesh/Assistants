#!/bin/bash

# Функция для вывода сообщений с цветом
print_message() {
    GREEN='\033[0;32m'
    RED='\033[0;31m'
    NC='\033[0m'
    
    if [ "$2" = "success" ]; then
        echo -e "${GREEN}$1${NC}"
    else
        echo -e "${RED}$1${NC}"
    fi
}

cd "$(dirname "$0")"

# Запускаем тесты через docker compose
print_message "=== Running tests ===" "success"
docker compose -f docker-compose.test.yml up --build --abort-on-container-exit

# Сохраняем результат тестов
TEST_RESULT=$?

# Останавливаем и удаляем контейнеры
print_message "=== Cleaning up ===" "success"
docker compose -f docker-compose.test.yml down

# Возвращаем результат тестов
if [ $TEST_RESULT -eq 0 ]; then
    print_message "=== Tests passed successfully! ===" "success"
else
    print_message "=== Tests failed! ===" "error"
fi

exit $TEST_RESULT 