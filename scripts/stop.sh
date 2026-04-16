#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}━━━ Stopping Portfolio Builder ━━━${NC}"

# Kill processes on our ports
lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null && echo -e "${GREEN}✔ Backend stopped${NC}" || true
lsof -ti:5173 2>/dev/null | xargs kill -9 2>/dev/null && echo -e "${GREEN}✔ Frontend stopped${NC}" || true

# Kill celery processes
pkill -f "celery -A app.tasks.celery_app" 2>/dev/null && echo -e "${GREEN}✔ Celery stopped${NC}" || true

# Stop Docker containers
docker compose down 2>/dev/null && echo -e "${GREEN}✔ Docker containers stopped${NC}" || true

echo ""
echo -e "${GREEN}All services stopped.${NC}"
