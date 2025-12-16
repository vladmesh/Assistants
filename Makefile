SERVICES := admin_service assistant_service cron_service google_calendar_service rag_service rest_service telegram_bot_service
RUFF_IMAGE := ghcr.io/astral-sh/ruff:0.14.8
PWD_DIR := $(shell pwd)

# Services that have unit tests
TESTABLE_SERVICES := $(SERVICES)

.PHONY: help lint lint-fast format format-check test-unit test-unit-changed test-integration test-all build-test-base migrate upgrade history changed-services

help:
	@echo "Targets: lint, format, format-check, test-unit, test-integration, test-all, build-test-base"
	@echo "Use SERVICE=<name> or positional arg to target a specific service"
	@echo ""
	@echo "Testing:"
	@echo "  make build-test-base                  # Build base test image (run once)"
	@echo "  make test-unit [SERVICE=<name>]       # Fast unit tests (no DB/Redis)"
	@echo "  make test-unit <service>              # Same as above (e.g. make test-unit assistant_service)"
	@echo "  make test-integration [SERVICE=<name>]  # Integration tests (with DB/Redis)"
	@echo "  make test-integration <service>       # Same as above"
	@echo "  make test-all                         # Run all unit + integration tests"

# Support positional arguments: make test-unit assistant_service
# Extract SERVICE from command line arguments if not set explicitly
ifndef SERVICE
  # Get all goals that are not known targets
  POSITIONAL_ARGS := $(filter-out help lint format format-check test-unit test-integration test-all build-test-base migrate upgrade history,$(MAKECMDGOALS))
  ifneq ($(POSITIONAL_ARGS),)
    # Take first positional arg as SERVICE if it's a valid service name
    CANDIDATE := $(firstword $(POSITIONAL_ARGS))
    ifneq ($(filter $(CANDIDATE),$(SERVICES) shared_models),)
      SERVICE := $(CANDIDATE)
    else
      SERVICE := all
    endif
  else
    SERVICE := all
  endif
endif

# Prevent Make from trying to run positional args as targets
%:
	@:

# Fast lint - single docker container for all services (used by pre-push hook)
lint-fast:
	@echo "Running lint for all services in single container..."
	@docker run --rm -v $(PWD_DIR):/workspace -w /workspace $(RUFF_IMAGE) check \
		admin_service assistant_service cron_service google_calendar_service \
		rag_service rest_service telegram_bot_service shared_models

lint:
ifeq ($(SERVICE),all)
	@$(MAKE) lint-fast
else
	@echo "started linter for $(SERVICE)"
	@$(MAKE) _ruff SERVICE=$(SERVICE) ARGS="check"
endif

format:
ifeq ($(SERVICE),all)
	@for s in $(SERVICES) shared_models; do $(MAKE) format SERVICE=$$s; done
else
	@$(MAKE) _ruff SERVICE=$(SERVICE) ARGS="format"
	@$(MAKE) _ruff SERVICE=$(SERVICE) ARGS="check --fix --exit-zero"
endif

format-check:
ifeq ($(SERVICE),all)
	@for s in $(SERVICES) shared_models; do $(MAKE) format-check SERVICE=$$s; done
else
	@$(MAKE) _ruff SERVICE=$(SERVICE) ARGS="format --check"
endif

_ruff:
	@if [ "$(SERVICE)" = "shared_models" ]; then \
		SRC_PATH=$(PWD_DIR)/shared_models; \
	elif [ "$(SERVICE)" = "rag_service" ]; then \
		SRC_PATH=$(PWD_DIR)/rag_service; \
	else \
		SRC_PATH=$(PWD_DIR)/$(SERVICE); \
	fi; \
	docker run --rm -v $$SRC_PATH:/workspace -w /workspace $(RUFF_IMAGE) $(ARGS)

# Unit tests - fast, no DB/Redis, uses base test image
build-test-base:
	@echo "Building base test image..."
	@docker build -f Dockerfile.test-base -t assistants-test-base .
	@echo "Base test image built: assistants-test-base:latest"

# Detect changed services (compares to origin/main or HEAD~1)
changed-services:
	@CHANGED=$$(git diff --name-only $${BASE_REF:-origin/main}...HEAD 2>/dev/null || git diff --name-only HEAD~1 2>/dev/null || echo ""); \
	if [ -z "$$CHANGED" ]; then echo ""; exit 0; fi; \
	echo "$$CHANGED" | cut -d/ -f1 | sort -u | while read dir; do \
		for svc in $(TESTABLE_SERVICES) shared_models; do \
			if [ "$$dir" = "$$svc" ]; then echo "$$svc"; fi; \
		done; \
	done

test-unit:
ifeq ($(SERVICE),all)
	@docker image inspect assistants-test-base:latest >/dev/null 2>&1 || $(MAKE) build-test-base
	@echo "Running unit tests for all services..."
	@for s in $(SERVICES); do \
		echo ""; \
		echo "=== Unit tests: $$s ==="; \
		SERVICE=$$s docker compose -f docker-compose.unit-test.yml run --rm unit-test || exit 1; \
	done
else
	@docker image inspect assistants-test-base:latest >/dev/null 2>&1 || $(MAKE) build-test-base
	@echo "=== Unit tests: $(SERVICE) ==="
	@SERVICE=$(SERVICE) docker compose -f docker-compose.unit-test.yml run --rm unit-test
endif

# Run unit tests only for changed services (used by pre-push hook)
test-unit-changed:
	@docker image inspect assistants-test-base:latest >/dev/null 2>&1 || $(MAKE) build-test-base
	@CHANGED=$$($(MAKE) -s changed-services); \
	if [ -z "$$CHANGED" ]; then \
		echo "No service changes detected, skipping unit tests."; \
		exit 0; \
	fi; \
	echo "Changed services: $$CHANGED"; \
	for svc in $$CHANGED; do \
		if [ "$$svc" = "shared_models" ]; then \
			echo "shared_models changed - running all unit tests"; \
			$(MAKE) test-unit SERVICE=all; \
			exit $$?; \
		fi; \
	done; \
	for svc in $$CHANGED; do \
		echo ""; \
		echo "=== Unit tests: $$svc ==="; \
		SERVICE=$$svc docker compose -f docker-compose.unit-test.yml run --rm unit-test || exit 1; \
	done

# Integration tests - with DB/Redis, uses base test image + shared infra
INTEGRATION_SERVICES := rest_service assistant_service telegram_bot_service

test-integration:
ifeq ($(SERVICE),all)
	@echo "Running integration tests for all services..."
	@for s in $(INTEGRATION_SERVICES); do \
		echo ""; \
		echo "=== Integration tests: $$s ==="; \
		STATUS=0; \
		SERVICE=$$s docker compose -f docker-compose.integration.yml run --rm integration-test || STATUS=$$?; \
		docker compose -f docker-compose.integration.yml down -v 2>/dev/null || true; \
		if [ $$STATUS -ne 0 ]; then exit $$STATUS; fi; \
	done
else
	@echo "=== Integration tests: $(SERVICE) ==="
	@STATUS=0; \
	SERVICE=$(SERVICE) docker compose -f docker-compose.integration.yml run --rm integration-test || STATUS=$$?; \
	docker compose -f docker-compose.integration.yml down -v 2>/dev/null || true; \
	if [ $$STATUS -ne 0 ]; then exit $$STATUS; fi
endif

# Run all tests (unit + integration)
test-all:
	@echo "=========================================="
	@echo "Running all tests"
	@echo "=========================================="
	@echo ""
	@echo ">>> UNIT TESTS <<<"
	@$(MAKE) test-unit
	@echo ""
	@echo ">>> INTEGRATION TESTS <<<"
	@$(MAKE) test-integration
	@echo ""
	@echo "All tests completed."

# Migrations for rest_service (manage.py removed; adjust when new command available)
migrate:
	@if [ -z "$(MESSAGE)" ]; then echo "MESSAGE is required. Usage: make migrate MESSAGE='your message'"; exit 1; fi
	@docker compose exec --user $$(id -u):$$(id -g) rest_service alembic revision --autogenerate -m "$(MESSAGE)"

upgrade:
	@docker compose exec rest_service alembic upgrade head

history:
	@docker compose exec rest_service alembic history
