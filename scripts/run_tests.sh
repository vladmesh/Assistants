#!/bin/bash

set -euo pipefail

# Resolve repository root
SCRIPT_DIR="$(cd -- "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

# Colored output helper
print_colored() {
    local color=$1
    local text=$2
    echo -e "\e[${color}m${text}\e[0m"
}

# Usage helper
print_help() {
    echo "Usage: $0 [service1 service2 ...]"
    echo "If no services specified, runs tests for all services"
    echo "Available services: rest_service, cron_service, telegram_bot_service, assistant_service, google_calendar_service, admin_service, rag_service, shared_models"
    exit 1
}

# Run tests for a service
run_service_tests() {
    local service=$1
    print_colored "36" "\n=== Running ${service} tests ===\n"

    if [ "${service}" = "shared_models" ]; then
        docker run --rm -v "${REPO_ROOT}/shared_models:/app" -w /app python:3.11 bash -c "pip install poetry && poetry install --no-root && PYTHONPATH=/app/src poetry run pytest"
        test_exit_code=$?
    elif [ -d "${REPO_ROOT}/${service}" ] && [ -f "${REPO_ROOT}/${service}/Dockerfile.test" ]; then
        pushd "${REPO_ROOT}/${service}" >/dev/null
        docker compose --progress=quiet -f docker-compose.test.yml build >/dev/null

        mapfile -t compose_services < <(docker compose -f docker-compose.test.yml config --services)
        no_attach_args=()
        for svc in "${compose_services[@]}"; do
            if [[ "${svc}" =~ (^redis$|^.*db.*$|^.*qdrant.*$) ]]; then
                no_attach_args+=(--no-attach "${svc}")
            fi
        done

        docker compose -f docker-compose.test.yml up --abort-on-container-exit --no-build "${no_attach_args[@]}"
        test_exit_code=${PIPESTATUS[0]}
        docker compose -f docker-compose.test.yml down -v >/dev/null 2>&1 || true
        popd >/dev/null
    else
        print_colored "33" "⚠️ No Dockerfile.test found for ${service}\n"
        return
    fi

    if [ ${test_exit_code} -eq 0 ]; then
        print_colored "32" "✅ ${service} tests passed!\n"
    else
        print_colored "31" "❌ ${service} tests failed!\n"
        failed_services+=("${service}")
    fi
}

# Track failed services
failed_services=()

# Available services
all_services=("rest_service" "cron_service" "telegram_bot_service" "assistant_service" "google_calendar_service" "admin_service" "rag_service" "shared_models")

# Parse arguments
if [ $# -eq 0 ]; then
    services_to_run=("${all_services[@]}")
else
    services_to_run=()
    for service in "$@"; do
        if [[ " ${all_services[*]} " =~ " ${service} " ]]; then
            services_to_run+=("${service}")
        else
            print_colored "31" "❌ Unknown service: ${service}\n"
            print_help
        fi
    done
fi

# Run requested services
for service in "${services_to_run[@]}"; do
    run_service_tests "${service}"
done

# Final summary
if [ ${#failed_services[@]} -ne 0 ]; then
    print_colored "31" "\n=== Tests failed for the following services: ${failed_services[*]} ===\n"
    exit 1
fi
