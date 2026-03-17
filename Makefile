SHELL := /bin/bash

.PHONY: up down logs migrate seed test backend frontend clean doctor

PROJECT_NAME := judiciary_accountibility
FRONTEND_URL := http://localhost:3000
BACKEND_URL := http://localhost:8000
API_DOCS_URL := http://localhost:8000/docs
HEALTH_URL := http://localhost:8000/health

check-docker:
	@command -v docker >/dev/null 2>&1 || (echo "Docker is required. Install Docker Desktop and retry." && exit 1)
	@docker info >/dev/null 2>&1 || (echo "Docker daemon is not running. Start Docker Desktop and retry." && exit 1)

ensure-env:
	@[ -f .env ] || cp .env.example .env

check-ports:
	@busy=""; \
	for p in 3000 6379 8000 55433; do \
		if lsof -iTCP:$$p -sTCP:LISTEN -n -P >/dev/null 2>&1; then \
			busy="$$busy $$p"; \
		fi; \
	done; \
	if [ -n "$$busy" ]; then \
		echo "Warning: ports already in use:$$busy. Docker may fail to bind these ports."; \
	fi


up: check-docker ensure-env check-ports
	docker compose up --build -d --remove-orphans
	@echo "Waiting for backend readiness..."
	@for i in {1..60}; do \
		if curl -fsS $(HEALTH_URL) >/dev/null 2>&1; then \
			echo ""; \
			echo "Stack ready:"; \
			echo "  Frontend: $(FRONTEND_URL)"; \
			echo "  Backend API: $(BACKEND_URL)"; \
			echo "  API docs: $(API_DOCS_URL)"; \
			echo "  Health: $(HEALTH_URL)"; \
			echo "  Postgres: postgres/postgres @ localhost:55433"; \
			exit 0; \
		fi; \
		echo -n "."; \
		sleep 2; \
	done; \
	echo ""; \
	echo "Backend did not become healthy in time. Run 'make logs' to inspect."; \
	exit 1

down:
	docker compose down

logs:
	docker compose logs -f --tail=100

migrate:
	docker compose exec backend sh -lc 'cd /app && PYTHONPATH=/app alembic -c alembic.ini upgrade head'

seed:
	docker compose exec backend sh -lc 'cd /app && PYTHONPATH=/app python scripts/seed.py'

test:
	docker compose exec backend pytest -q

backend:
	docker compose up --build backend celery-worker celery-beat db redis

frontend:
	docker compose up --build frontend

clean:
	docker compose down -v --remove-orphans

doctor: check-docker check-ports
	@echo "Docker + local port preflight checks passed."
