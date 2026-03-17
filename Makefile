SHELL := /bin/bash

.PHONY: up down logs migrate seed test backend frontend

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f --tail=100

migrate:
	docker compose exec backend alembic -c alembic.ini upgrade head

seed:
	docker compose exec backend python scripts/seed.py

test:
	docker compose exec backend pytest -q

backend:
	docker compose up --build backend worker beat db redis

frontend:
	docker compose up --build frontend
