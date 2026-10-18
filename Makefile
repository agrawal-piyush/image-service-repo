# Convenience targets. Run `make help` to list them.

.PHONY: help setup test up down bootstrap deploy clean

help:
	@echo "Targets:"
	@echo "  setup      Create venv and install dependencies"
	@echo "  test       Run unit tests (no Docker needed)"
	@echo "  up         Start LocalStack (docker compose up -d)"
	@echo "  down       Stop LocalStack"
	@echo "  bootstrap  Provision S3/DynamoDB/Lambda/API Gateway in LocalStack"
	@echo "  deploy     up + bootstrap"
	@echo "  clean      Remove venv, build artifacts, caches"

setup:
	python3 -m venv .venv
	. .venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt

test:
	. .venv/bin/activate && python -m pytest

up:
	docker compose up -d

down:
	docker compose down

bootstrap:
	./scripts/bootstrap.sh

deploy: up
	@echo "Waiting for LocalStack to be ready..."
	@sleep 8
	./scripts/bootstrap.sh

clean:
	rm -rf .venv build .pytest_cache .api_base_url
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
