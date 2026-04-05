.PHONY: up down logs seed

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

seed:
	docker compose run --rm simulator python main.py --once
