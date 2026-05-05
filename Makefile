# Makefile — convenience commands for the Portfolio Builder project.
#
# Make is used here purely as a task runner. None of these targets
# actually compile anything; they just wrap longer docker/poetry commands.
#
# Usage: `make <target>` — e.g. `make up`, `make test`.

.PHONY: help up down restart logs test seed migrate psql shell-backend clean

help:           ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'

up:             ## Start all services in the background
	docker compose up -d

down:           ## Stop and remove all services
	docker compose down

restart:        ## Restart all services
	docker compose restart

logs:           ## Tail logs of the backend service
	docker compose logs -f backend

logs-all:       ## Tail logs of all services
	docker compose logs -f

test:           ## Run the backend test suite (creates+migrates test DB on first run)
	@# Idempotent: the CREATE DATABASE only runs if portfolio_builder_test
	@# doesn't yet exist. Repeat invocations are no-ops on the DB side.
	@docker compose exec -T db psql -U portfolio -d postgres -tc \
	  "SELECT 1 FROM pg_database WHERE datname='portfolio_builder_test'" | grep -q 1 \
	  || docker compose exec -T db psql -U portfolio -d postgres -c \
	  "CREATE DATABASE portfolio_builder_test"
	@# Apply migrations to the test DB. Alembic itself is idempotent.
	docker compose exec -T \
	  -e DATABASE_URL=postgresql://portfolio:portfolio@db:5432/portfolio_builder_test \
	  backend alembic upgrade head
	@# Run pytest. The conftest fixture rolls back rows after each test,
	@# so the test DB stays clean across runs and we do not drop it.
	docker compose exec -T \
	  -e TEST_DATABASE_URL=postgresql://portfolio:portfolio@db:5432/portfolio_builder_test \
	  backend pytest -v

migrate:        ## Apply database migrations
	docker compose exec backend alembic upgrade head

migration:      ## Create a new migration. Usage: make migration MSG="add foo"
	docker compose exec backend alembic revision --autogenerate -m "$(MSG)"

seed:           ## Seed curated universe (20 ETFs + 10y prices)
	docker compose exec backend python -m scripts.seed_universe

psql:           ## Open a psql shell on the db
	docker compose exec db psql -U portfolio -d portfolio_builder

shell-backend:  ## Open a bash shell inside the backend container
	docker compose exec backend bash

clean:          ## Remove containers, volumes, and built images (DESTRUCTIVE)
	docker compose down -v --rmi local
