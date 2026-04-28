#!/usr/bin/env bash
# dev.sh — start the full Portfolio Builder stack and tail logs.
#
# What it does:
#   1. Builds and starts all 3 containers (db, backend, frontend).
#   2. Waits for the database to become healthy.
#   3. Applies any pending Alembic migrations.
#   4. Prints clickable links for the frontend and backend.
#   5. Tails the logs so you can see what's happening.
#
# To stop: Ctrl+C in this terminal, or run `make down` in another.

set -e  # bail on any error

# ANSI colors for prettier output (optional but nice).
GREEN="\033[0;32m"
BLUE="\033[0;34m"
YELLOW="\033[1;33m"
RESET="\033[0m"

cd "$(dirname "$0")"

echo -e "${BLUE}▶ Starting Portfolio Builder stack...${RESET}"
docker compose up -d --build

echo -e "${BLUE}▶ Waiting for database to become healthy...${RESET}"
# Loop until pg_isready succeeds inside the db container.
until docker compose exec -T db pg_isready -U portfolio >/dev/null 2>&1; do
    sleep 1
    echo "   …still waiting"
done

echo -e "${BLUE}▶ Applying migrations...${RESET}"
docker compose exec -T backend alembic upgrade head

# Print the URLs nice and clear.
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════${RESET}"
echo -e "${GREEN}  ✅ Portfolio Builder is up.${RESET}"
echo ""
echo -e "${GREEN}     Frontend:  ${YELLOW}http://localhost:5173${RESET}"
echo -e "${GREEN}     API docs:  ${YELLOW}http://localhost:8000/docs${RESET}"
echo -e "${GREEN}     Health:    ${YELLOW}http://localhost:8000/health${RESET}"
echo ""
echo -e "${GREEN}     Tailing logs below. Ctrl+C to stop watching."
echo -e "${GREEN}     (Stack keeps running in background.)${RESET}"
echo -e "${GREEN}═══════════════════════════════════════════════════════${RESET}"
echo ""

# Tail logs of all services in this terminal.
docker compose logs -f
