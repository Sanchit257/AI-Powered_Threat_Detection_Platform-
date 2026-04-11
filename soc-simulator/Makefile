.PHONY: up down logs seed bootstrap

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

seed:
	bash scripts/seed.sh

bootstrap:
	docker compose up --build -d
	@echo "Waiting for API healthcheck..."
	@sleep 8
	bash scripts/seed.sh
