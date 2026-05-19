.PHONY: help up down build logs shell test migrate audit

help:
	@echo ""
	@echo "  Inventory Manager — available commands"
	@echo "  ──────────────────────────────────────"
	@echo "  make up         Start all services"
	@echo "  make down       Stop all services"
	@echo "  make build      Rebuild images from scratch"
	@echo "  make logs       Follow live logs from all services"
	@echo "  make shell      Open a bash shell inside the API container"
	@echo "  make test       Run the full test suite"
	@echo "  make migrate    Apply all pending Alembic migrations"
	@echo "  make audit      Scan dependencies for known vulnerabilities"
	@echo "  make audit-dev  Scan development dependencies for vulnerabilities"
	@echo ""

up:
	docker compose up

down:
	docker compose down

build:
	docker compose up --build

logs:
	docker compose logs -f

shell:
	docker compose exec api bash

test:
	docker compose exec api pytest tests -v

migrate:
	docker compose exec api alembic upgrade head

audit:
	docker compose exec api pip-audit -r requirements.txt

audit-dev:
	pip-audit -r backend/requirements-dev.txt