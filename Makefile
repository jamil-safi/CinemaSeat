.PHONY: up down test logs

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f

test:
	python -m pytest tests/integration

