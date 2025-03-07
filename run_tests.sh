#!/bin/bash

# Функция для вывода цветного текста
print_colored() {
    local color=$1
    local text=$2
    echo -e "\e[${color}m${text}\e[0m"
}

# Функция для запуска тестов сервиса
run_service_tests() {
    service=$1
    print_colored "36" "\n=== Running $service tests ===\n"
    
    if [ -d "$service" ] && [ -f "$service/Dockerfile.test" ]; then
        # Запускаем тесты в Docker
        cd $service
        # Фильтруем вывод, оставляя только строки с результатами тестов и ошибками
        docker compose -f docker-compose.test.yml up --build --abort-on-container-exit 2>&1 | grep -E "collected|PASSED|FAILED|ERROR|===.*test session starts|===.*in [0-9]+\.[0-9]+s|ImportError|ModuleNotFoundError|SyntaxError|Exception|Traceback"
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

# Запускаем тесты для каждого сервиса
for service in rest_service notification_service cron_service tg_bot assistant; do
    run_service_tests "$service"
done

# Выводим итоговый результат
if [ ${#failed_services[@]} -ne 0 ]; then
    print_colored "31" "\n=== Tests failed for the following services: ${failed_services[*]} ===\n"
    exit 1
fi 