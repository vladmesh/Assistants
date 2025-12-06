SERVICES := admin_service assistant_service cron_service google_calendar_service rag_service rest_service telegram_bot_service
RUFF_IMAGE := ghcr.io/astral-sh/ruff:0.14.8
PWD_DIR := $(shell pwd)

.PHONY: help lint format format-check test migrate upgrade history

help:
	@echo "Targets: lint, format, format-check, test, migrate, upgrade, history"
	@echo "Use SERVICE=<name> or make test <service> to target a specific service"

SERVICE ?= all

# Allow `make test <service>` to set SERVICE and avoid extra targets
ifneq ($(firstword $(MAKECMDGOALS)),)
ifeq ($(firstword $(MAKECMDGOALS)),test)
ifneq ($(word 2,$(MAKECMDGOALS)),)
override SERVICE := $(word 2,$(MAKECMDGOALS))
override MAKECMDGOALS := test
endif
endif
endif

lint:
ifeq ($(SERVICE),all)
	@set -e; for s in $(SERVICES) shared_models; do echo "started linter for $$s"; $(MAKE) lint SERVICE=$$s; done
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

test:
ifeq ($(SERVICE),all)
	@./scripts/run_tests.sh
else
	@./scripts/run_tests.sh $(SERVICE)
endif

test-%:
	@./scripts/run_tests.sh $*

# Migrations for rest_service (manage.py removed; adjust when new command available)
migrate:
	@if [ -z "$(MESSAGE)" ]; then echo "MESSAGE is required. Usage: make migrate MESSAGE='your message'"; exit 1; fi
	@docker compose exec --user $$(id -u):$$(id -g) rest_service alembic revision --autogenerate -m "$(MESSAGE)"

upgrade:
	@echo "manage.py removed; add upgrade command implementation"

history:
	@echo "manage.py removed; add history command implementation"
