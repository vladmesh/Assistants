#!/bin/bash

# Функция для вывода цветного текста
print_colored() {
    local color=$1
    local text=$2
    echo -e "\e[${color}m${text}\e[0m"
}

# Функция для вывода справки
print_help() {
    echo "Usage: $0 [service1 service2 ...]"
    echo "If no services specified, runs tests for all services"
    echo "Available services: rest_service, cron_service, telegram_bot_service, assistant_service, google_calendar_service, admin_service, rag_service"
    exit 1
}

# Функция для запуска тестов сервиса
run_service_tests() {
    service=$1
    print_colored "36" "\n=== Running $service tests ===\n"
    
    if [ -d "$service" ] && [ -f "$service/Dockerfile.test" ]; then
        # Запускаем тесты в Docker
        cd $service
        # Фильтруем вывод, оставляя только строки с результатами тестов и ошибками
        # docker compose -f docker-compose.test.yml up --build --abort-on-container-exit 2>&1 | grep -E "collected|PASSED|FAILED|ERROR|===.*test session starts|===.*in [0-9]+\.[0-9]+s|ImportError|ModuleNotFoundError|SyntaxError|Exception|Traceback"
        # Run without grep to see full output
        docker compose -f docker-compose.test.yml up --build --abort-on-container-exit
        test_exit_code=${PIPESTATUS[0]}
        docker compose -f docker-compose.test.yml down -v > /dev/null 2>&1
        cd ..
        
        # Проверяем результат
        if [ $test_exit_code -eq 0 ]; then
            print_colored "32" "✅ $service tests passed!\n"
        else
            print_colored "31" "❌ $service tests failed!\n"
            failed_services+=($service)
        fi
    else
        print_colored "33" "⚠️ No Dockerfile.test found for $service\n"
    fi
}

# Массив для хранения сервисов с упавшими тестами
failed_services=()

# Список всех доступных сервисов
all_services=("rest_service" "cron_service" "telegram_bot_service" "assistant_service" "google_calendar_service" "admin_service" "rag_service")

# Проверяем, есть ли аргументы командной строки
if [ $# -eq 0 ]; then
    # Если аргументов нет, запускаем все сервисы
    services_to_run=("${all_services[@]}")
else
    # Если есть аргументы, проверяем их валидность
    services_to_run=()
    for service in "$@"; do
        if [[ " ${all_services[@]} " =~ " ${service} " ]]; then
            services_to_run+=("$service")
        else
            print_colored "31" "❌ Unknown service: $service\n"
            print_help
        fi
    done
fi

# Запускаем тесты для выбранных сервисов
for service in "${services_to_run[@]}"; do
    run_service_tests "$service"
done

# Выводим итоговый результат
if [ ${#failed_services[@]} -ne 0 ]; then
    print_colored "31" "\n=== Tests failed for the following services: ${failed_services[*]} ===\n"
    exit 1
fi 